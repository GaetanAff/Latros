"""Immutable snapshots; the manifest is the final publication marker."""

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb
import orjson

from latros import __version__
from latros.common import LatrosError, encoded, safe_id, sha256, write_json
from latros.knowledge.importers import TABLES, import_registry
from latros.sources.registry import Registry

RULES = {
    "schema": "canonical_v1",
    "ontology": "obographs_v1",
    "associations": "orphadata_product4_v1",
    "bilingual": "same_record_verified_then_combined",
    "mapping": "explicit_exactMatch_only; xrefs_not_equivalence; ORPHA_identity_preserved",
    "obsolete_hpo": (
        "follow_unique_replaced_by; retain_inactive_without_replacement_unscored; unknown_fail"
    ),
    "frequency": "lossless; counts_Beta_1_1; category_interval_midpoint_only_for_reasoning",
    "scoring": "semantic_v1",
    "safety": "not_evaluated",
    "runtime_integrity": "local_receipt; canonical_hashes_define_snapshot_identity",
}


def code_hash() -> str:
    package = Path(__file__).resolve().parents[1]
    items = [(p.relative_to(package).as_posix(), sha256(p)) for p in sorted(package.rglob("*.py"))]
    return hashlib.sha256(encoded(items)).hexdigest()


def verify_raw(root: Path, registry: Registry) -> None:
    for source in registry.sources:
        for artifact in source.artifacts:
            path = root / "data/raw" / source.id / source.release / artifact.filename
            if not path.is_file() or sha256(path) != artifact.sha256:
                raise LatrosError(f"Missing/corrupt source: {path}. Run sources fetch first.")


def snapshot_path(root: Path, snapshot: str) -> Path:
    return root / "data/runtime" / safe_id(snapshot) / "knowledge.duckdb"


def load_manifest(root: Path, snapshot: str, *, verify: bool = True) -> dict[str, Any]:
    safe_id(snapshot)
    path = root / "manifests" / f"{snapshot}.json"
    if not path.is_file():
        raise LatrosError(f"Snapshot is not published: {snapshot}")
    manifest: dict[str, Any] = orjson.loads(path.read_bytes())
    if manifest["snapshot"] != snapshot or manifest["schema_version"] != 1:
        raise LatrosError("Snapshot manifest version/identity mismatch")
    if verify:
        # Only fixed paths derived from safe IDs, never paths supplied by a manifest.
        for table in TABLES:
            path = root / "data/canonical" / snapshot / f"{table}.parquet"
            if not path.exists() or sha256(path) != manifest["tables"][table]["parquet_sha256"]:
                raise LatrosError(f"Snapshot table checksum mismatch: {table}")
        db = snapshot_path(root, snapshot)
        receipt_path = db.parent / "integrity.json"
        if not receipt_path.is_file():
            raise LatrosError("Snapshot runtime integrity receipt is missing")
        receipt = orjson.loads(receipt_path.read_bytes())
        if (
            receipt.get("snapshot") != snapshot
            or receipt.get("content_sha256") != manifest["content_sha256"]
            or not db.exists()
            or sha256(db) != receipt.get("database_sha256")
        ):
            raise LatrosError("Snapshot database checksum mismatch")
    return manifest


def build_snapshot(root: Path, registry: Registry, snapshot: str) -> dict[str, Any]:
    safe_id(snapshot)
    root = root.resolve()
    verify_raw(root, registry)
    canonical = root / "data/canonical" / snapshot
    runtime = root / "data/runtime" / snapshot
    manifest_path = root / "manifests" / f"{snapshot}.json"
    expected = None
    if manifest_path.exists():
        expected = load_manifest(root, snapshot, verify=False)
        if expected["sources"] != registry.model_dump(mode="json")["sources"]:
            raise LatrosError("Snapshot ID already belongs to different source pins")
        if expected["build_code_sha256"] != code_hash():
            raise LatrosError("Implementation changed: use a new snapshot ID")
        if canonical.exists() and runtime.exists():
            return load_manifest(root, snapshot)
    if canonical.exists() or runtime.exists():
        raise LatrosError("Unpublished snapshot directory exists; use a new ID (no overwrite)")
    (root / "data").mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".build-", dir=root / "data"))
    try:
        kb = import_registry(root, registry)
        (staging / "canonical").mkdir()
        (staging / "runtime").mkdir()
        db = staging / "runtime/knowledge.duckdb"
        table_info: dict[str, Any] = {}
        with duckdb.connect(str(db)) as connection:
            connection.execute("SET threads=1")
            for table, columns in TABLES.items():
                records = sorted(kb.rows[table].values(), key=lambda row: row["id"])
                jsonl = staging / f"{table}.jsonl"
                with jsonl.open("wb") as handle:
                    for row in records:
                        handle.write(orjson.dumps(row, option=orjson.OPT_SORT_KEYS) + b"\n")
                definitions = ", ".join(f'"{key}" {kind}' for key, kind in columns.items())
                connection.execute(f'CREATE TABLE "{table}" ({definitions}, PRIMARY KEY (id))')
                if records:
                    connection.execute(
                        f'INSERT INTO "{table}" SELECT * FROM read_json(?, '
                        "columns=?, format='newline_delimited') ORDER BY id",
                        [str(jsonl), columns],
                    )
                parquet = staging / "canonical" / f"{table}.parquet"
                connection.execute(
                    f'COPY (SELECT * FROM "{table}" ORDER BY id) TO ? '
                    "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)",
                    [str(parquet)],
                )
                table_info[table] = dict(
                    rows=len(records), logical_sha256=sha256(jsonl), parquet_sha256=sha256(parquet)
                )
            connection.execute("CHECKPOINT")
        logical_hashes = {t: v["logical_sha256"] for t, v in table_info.items()}
        manifest = dict(
            schema_version=1,
            snapshot=snapshot,
            latros_version=__version__,
            build_code_sha256=code_hash(),
            duckdb_version=duckdb.__version__,
            sources=registry.model_dump(mode="json")["sources"],
            rules=RULES,
            tables=table_info,
            content_sha256=hashlib.sha256(encoded(logical_hashes)).hexdigest(),
            errors=[],
            warnings=sorted(kb.warnings),
        )
        # A clean clone has the tracked manifest but none of the local data. Rebuild
        # against it, including Parquet hashes, and never silently rewrite its pins.
        # DuckDB container bytes are not deterministic on the full corpus. Its
        # checksum is a local integrity receipt, not a canonical snapshot identity.
        if expected is not None and manifest != expected:
            raise LatrosError("Reconstruction differs from pinned manifest; snapshot not published")
        write_json(
            db.parent / "integrity.json",
            dict(
                snapshot=snapshot,
                content_sha256=manifest["content_sha256"],
                database_sha256=sha256(db),
            ),
        )
        canonical.parent.mkdir(parents=True, exist_ok=True)
        runtime.parent.mkdir(parents=True, exist_ok=True)
        (staging / "canonical").rename(canonical)
        (staging / "runtime").rename(runtime)
        if expected is None:
            write_json(manifest_path, manifest)
        return manifest
    except Exception as exc:
        write_json(
            root / "data/failures" / f"{snapshot}.json",
            {"snapshot": snapshot, "errors": [str(exc)], "published": False},
        )
        raise
    finally:
        # Only this function's tempfile directory is removed; source data is never touched.
        shutil.rmtree(staging)


def read_tables(
    root: Path, snapshot: str
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    manifest = load_manifest(root, snapshot)
    result: dict[str, list[dict[str, Any]]] = {}
    with duckdb.connect(str(snapshot_path(root, snapshot)), read_only=True) as connection:
        for table in TABLES:
            cursor = connection.execute(f'SELECT * FROM "{table}" ORDER BY id')
            names = [c[0] for c in cursor.description]
            result[table] = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    return manifest, result
