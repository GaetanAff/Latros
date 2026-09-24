"""Immutable canonical-v2 snapshots built from validated knowledge objects."""

import hashlib
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import duckdb
import orjson
from pydantic import BaseModel

from latros import __version__
from latros.common import LatrosError, encoded, safe_id, sha256, write_json
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2, SnapshotTableV2
from latros.knowledge.models_v2 import (
    AssertionDerivation,
    CanonicalAssertion,
    CanonicalKnowledgeV2,
    ConceptMappingV2,
    ConceptV2,
    DesignationV2,
    EvidenceFamily,
    ExternalIdentifierV2,
    HierarchyEdgeV2,
    SourceArtifactV2,
    SourceAssertion,
    SourceDependency,
    SourceRecordV2,
    SourceReleaseV2,
)
from latros.sources.registry_v2 import RegistryV2

V2_TABLES: dict[str, tuple[str, str, type[BaseModel]]] = {
    "source_release": ("source_releases", "source_release_id", SourceReleaseV2),
    "source_artifact": ("source_artifacts", "artifact_id", SourceArtifactV2),
    "source_record": ("source_records", "source_record_id", SourceRecordV2),
    "concept": ("concepts", "concept_id", ConceptV2),
    "designation": ("designations", "designation_id", DesignationV2),
    "external_identifier": (
        "external_identifiers",
        "external_identifier_id",
        ExternalIdentifierV2,
    ),
    "hierarchy_edge": ("hierarchy_edges", "hierarchy_edge_id", HierarchyEdgeV2),
    "concept_mapping": ("concept_mappings", "mapping_id", ConceptMappingV2),
    "source_assertion": ("source_assertions", "source_assertion_id", SourceAssertion),
    "canonical_assertion": (
        "canonical_assertions",
        "canonical_assertion_id",
        CanonicalAssertion,
    ),
    "assertion_derivation": (
        "assertion_derivations",
        "derivation_id",
        AssertionDerivation,
    ),
    "evidence_family": ("evidence_families", "evidence_family_id", EvidenceFamily),
    "source_dependency": (
        "source_dependencies",
        "source_dependency_id",
        SourceDependency,
    ),
}

V2_RULES = {
    "schema": "canonical_v2",
    "row_encoding": "canonical_json_sorted_keys",
    "ordering": "stable_identifier_ascending",
    "mapping": "resolved_exact_or_equivalent_only_for_reasoning",
    "deduplication": "source_rows_preserved; canonical_signature_deduplicated",
    "evidence": "aggregate_independent_families_only; unknown_dependency_excluded",
    "manifest_evidence": "full_below_5000_rows; otherwise table_authoritative_summary",
    "runtime_integrity": "local_receipt; manifest_and_canonical_hashes_define_identity",
    "safety": "not_evaluated",
}


def pipeline_hash_v2() -> str:
    root = Path(__file__).resolve().parents[1]
    relative_paths = [
        "knowledge/adapter_v1.py",
        "knowledge/candidates.py",
        "knowledge/manifest_v2.py",
        "knowledge/models_v2.py",
        "knowledge/importers.py",
        "knowledge/importers_v2.py",
        "knowledge/general_factory.py",
        "knowledge/medlineplus.py",
        "knowledge/mesh.py",
        "knowledge/monarch.py",
        "knowledge/research_unreviewed.py",
        "knowledge/store_v2.py",
        "sources/registry_v2.py",
    ]
    items = [(relative, sha256(root / relative)) for relative in relative_paths]
    return hashlib.sha256(encoded(items)).hexdigest()


def snapshot_path_v2(root: Path, snapshot: str) -> Path:
    return root / "data/runtime" / safe_id(snapshot) / "knowledge.duckdb"


def verify_raw_v2(root: Path, registry: RegistryV2) -> None:
    for source in registry.sources:
        for artifact in source.artifacts:
            path = (
                root / artifact.local_path
                if artifact.local_path is not None
                else root / "data/raw" / source.source_id / source.release / artifact.filename
            )
            path = path.resolve()
            try:
                path.relative_to(root.resolve())
            except ValueError as exc:
                raise LatrosError("Artifact local_path escapes the project root") from exc
            if not path.is_file() or sha256(path) != artifact.sha256:
                raise LatrosError(f"Missing/corrupt v2 source: {path}")


def load_manifest_v2(
    root: Path, snapshot: str, *, verify: bool = True
) -> KnowledgeSnapshotManifestV2:
    safe_id(snapshot)
    path = root / "manifests" / f"{snapshot}.json"
    if not path.is_file():
        raise LatrosError(f"Snapshot is not published: {snapshot}")
    manifest = KnowledgeSnapshotManifestV2.model_validate_json(path.read_bytes())
    if manifest.snapshot != snapshot:
        raise LatrosError("Snapshot manifest identity mismatch")
    if verify:
        for table in V2_TABLES:
            parquet = root / "data/canonical" / snapshot / f"{table}.parquet"
            expected = manifest.tables.get(table)
            if (
                expected is None
                or not parquet.is_file()
                or sha256(parquet) != expected.parquet_sha256
            ):
                raise LatrosError(f"Snapshot v2 table checksum mismatch: {table}")
        database = snapshot_path_v2(root, snapshot)
        receipt_path = database.parent / "integrity.json"
        if not receipt_path.is_file():
            raise LatrosError("Snapshot v2 runtime integrity receipt is missing")
        receipt = orjson.loads(receipt_path.read_bytes())
        if (
            receipt.get("snapshot") != snapshot
            or receipt.get("content_sha256") != manifest.content_sha256
            or not database.is_file()
            or receipt.get("database_sha256") != sha256(database)
        ):
            raise LatrosError("Snapshot v2 database checksum mismatch")
    return manifest


def build_snapshot_v2(
    root: Path,
    registry: RegistryV2,
    snapshot: str,
    knowledge: CanonicalKnowledgeV2,
    *,
    research_metadata: dict[str, Any] | None = None,
) -> KnowledgeSnapshotManifestV2:
    safe_id(snapshot)
    if snapshot.endswith("-dev-unreviewed") != (research_metadata is not None):
        raise LatrosError(
            "A *-dev-unreviewed snapshot requires explicit unreviewed research metadata, "
            "and that metadata is forbidden for other snapshot IDs"
        )
    root = root.resolve()
    verify_raw_v2(root, registry)
    _validate_registry_alignment(registry, knowledge)
    canonical = root / "data/canonical" / snapshot
    runtime = root / "data/runtime" / snapshot
    manifest_path = root / "manifests" / f"{snapshot}.json"
    expected: KnowledgeSnapshotManifestV2 | None = None
    if manifest_path.exists():
        expected = load_manifest_v2(root, snapshot, verify=False)
        if expected.sources != registry.sources or expected.scope != registry.scope:
            raise LatrosError("Snapshot ID already belongs to different v2 source pins or scope")
        if expected.build_pipeline_sha256 != pipeline_hash_v2():
            raise LatrosError("V2 build implementation changed: use a new snapshot ID")
        expected_research = {
            "validation_status": expected.validation_status,
            "intended_use": expected.intended_use,
            "clinical_validation": expected.clinical_validation,
            "human_review_complete": expected.human_review_complete,
            "publishable": expected.publishable,
            "research_override_used": expected.research_override_used,
            "unreviewed_assertion_ids": expected.unreviewed_assertion_ids,
            "unreviewed_mapping_ids": expected.unreviewed_mapping_ids,
            "reviewer_count": expected.reviewer_count,
            "limitations": expected.limitations,
            "metrics": expected.metrics,
        }
        if expected_research != (research_metadata or expected_research):
            raise LatrosError("Snapshot ID already belongs to different research safeguards")
        if canonical.exists() and runtime.exists():
            return load_manifest_v2(root, snapshot)
    if canonical.exists() or runtime.exists():
        raise LatrosError("Unpublished v2 snapshot directory exists; use a new ID")
    (root / "data").mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".build-v2-", dir=root / "data"))
    try:
        (staging / "canonical").mkdir()
        (staging / "runtime").mkdir()
        database = staging / "runtime/knowledge.duckdb"
        table_info: dict[str, SnapshotTableV2] = {}
        with duckdb.connect(str(database)) as connection:
            connection.execute("SET threads=1")
            for table, (collection, id_field, _) in V2_TABLES.items():
                items = sorted(
                    getattr(knowledge, collection), key=lambda item: getattr(item, id_field)
                )
                jsonl = staging / f"{table}.jsonl"
                with jsonl.open("wb") as handle:
                    for item in items:
                        identifier = str(getattr(item, id_field))
                        payload = orjson.dumps(
                            item.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS
                        )
                        handle.write(
                            orjson.dumps({"id": identifier, "payload_json": payload.decode()})
                            + b"\n"
                        )
                definition = "id VARCHAR PRIMARY KEY, payload_json VARCHAR NOT NULL"
                connection.execute(f'CREATE TABLE "{table}" ({definition})')
                if items:
                    connection.execute(
                        f'INSERT INTO "{table}" SELECT id, payload_json FROM read_json(?, '
                        "columns={id: 'VARCHAR', payload_json: 'VARCHAR'}, "
                        "format='newline_delimited') ORDER BY id",
                        [str(jsonl)],
                    )
                parquet = staging / "canonical" / f"{table}.parquet"
                connection.execute(
                    f'COPY (SELECT * FROM "{table}" ORDER BY id) TO ? '
                    "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)",
                    [str(parquet)],
                )
                table_info[table] = SnapshotTableV2(
                    rows=len(items),
                    logical_sha256=sha256(jsonl),
                    parquet_sha256=sha256(parquet),
                )
            connection.execute("CHECKPOINT")
        logical_hashes = {
            table: details.logical_sha256 for table, details in sorted(table_info.items())
        }
        identity = {
            "tables": logical_hashes,
            "scope": registry.scope.model_dump(mode="json"),
            "rules": V2_RULES,
            "research_metadata": research_metadata,
        }
        redistributions = {source.license.redistribution for source in registry.sources}
        redistribution: Literal["allowed_with_attribution", "restricted", "prohibited"]
        if "prohibited" in redistributions:
            redistribution = "prohibited"
        elif "restricted" in redistributions:
            redistribution = "restricted"
        else:
            redistribution = "allowed_with_attribution"
        manifest_payload: dict[str, Any] = {
            **(research_metadata or {}),
        }
        evidence_manifest: list[dict[str, Any]]
        evidence_memberships = sum(
            len(item.source_assertion_ids) for item in knowledge.evidence_families
        )
        if evidence_memberships <= 5000:
            evidence_manifest = [
                item.model_dump(mode="json") for item in knowledge.evidence_families
            ]
        else:
            dependency_counts = Counter(
                item.dependency_type for item in knowledge.evidence_families
            )
            evidence_manifest = [
                {
                    "summary": True,
                    "table": "evidence_family",
                    "count": len(knowledge.evidence_families),
                    "source_assertion_membership_count": evidence_memberships,
                    "dependency_type_counts": dict(sorted(dependency_counts.items())),
                    "logical_sha256": table_info["evidence_family"].logical_sha256,
                    "note": "Every family remains in the canonical evidence_family table.",
                }
            ]
        manifest = KnowledgeSnapshotManifestV2(
            snapshot=snapshot,
            latros_version=__version__,
            build_pipeline_sha256=pipeline_hash_v2(),
            duckdb_version=duckdb.__version__,
            scope=registry.scope,
            sources=registry.sources,
            source_dependencies=[
                item.model_dump(mode="json") for item in knowledge.source_dependencies
            ],
            evidence_families=evidence_manifest,
            rules=V2_RULES,
            tables=table_info,
            compatible_profiles=registry.compatible_profiles,
            redistribution=redistribution,
            content_sha256=hashlib.sha256(encoded(identity)).hexdigest(),
            warnings=(
                [
                    "UNREVIEWED LOCAL RESEARCH DATA: not clinically validated, not publishable, "
                    "and not suitable for clinical use"
                ]
                if research_metadata is not None
                else []
            ),
            **manifest_payload,
        )
        if expected is not None and manifest != expected:
            raise LatrosError("Reconstruction differs from pinned v2 manifest")
        write_json(
            database.parent / "integrity.json",
            {
                "snapshot": snapshot,
                "content_sha256": manifest.content_sha256,
                "database_sha256": sha256(database),
            },
        )
        canonical.parent.mkdir(parents=True, exist_ok=True)
        runtime.parent.mkdir(parents=True, exist_ok=True)
        (staging / "canonical").rename(canonical)
        (staging / "runtime").rename(runtime)
        if expected is None:
            write_json(manifest_path, manifest.model_dump(mode="json"))
        return manifest
    except Exception as exc:
        write_json(
            root / "data/failures" / f"{snapshot}.json",
            {"snapshot": snapshot, "schema_version": 2, "errors": [str(exc)], "published": False},
        )
        raise
    finally:
        shutil.rmtree(staging)


def read_knowledge_v2(
    root: Path, snapshot: str
) -> tuple[KnowledgeSnapshotManifestV2, CanonicalKnowledgeV2]:
    manifest = load_manifest_v2(root, snapshot)
    payload: dict[str, Any] = {"schema_version": 2}
    with duckdb.connect(str(snapshot_path_v2(root, snapshot)), read_only=True) as connection:
        for table, (collection, _, model) in V2_TABLES.items():
            rows = connection.execute(f'SELECT payload_json FROM "{table}" ORDER BY id').fetchall()
            payload[collection] = [
                model.model_validate_json(row[0]).model_dump(mode="json") for row in rows
            ]
    return manifest, CanonicalKnowledgeV2.model_validate(payload)


def _validate_registry_alignment(registry: RegistryV2, knowledge: CanonicalKnowledgeV2) -> None:
    registry_releases = {
        f"{source.source_id}:{source.release}": source for source in registry.sources
    }
    knowledge_releases = {item.source_release_id: item for item in knowledge.source_releases}
    if set(registry_releases) != set(knowledge_releases):
        raise LatrosError("Canonical v2 source releases do not match the registry")
    registry_artifacts = {
        (f"{source.source_id}:{source.release}", artifact.filename): artifact
        for source in registry.sources
        for artifact in source.artifacts
    }
    canonical_artifacts = {
        (item.source_release_id, item.filename): item for item in knowledge.source_artifacts
    }
    if set(registry_artifacts) != set(canonical_artifacts):
        raise LatrosError("Canonical v2 artifacts do not match the registry")
    for key, artifact in canonical_artifacts.items():
        if artifact.sha256 != registry_artifacts[key].sha256:
            raise LatrosError("Canonical v2 artifact hash does not match the registry")
