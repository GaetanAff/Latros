"""Rebuild the historical MedlinePlus candidates without rebuilding the snapshot.

This replay is read-only against the immutable runtime and the pinned local XML.
The historical factory is deliberately not edited: it participates in the v0.7
snapshot's pipeline hash. Generated candidate sets remain under data/staging.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import duckdb
import orjson

from latros.common import LatrosError, sha256
from latros.knowledge.candidates import CandidateAssertion
from latros.knowledge.general_factory import _import_medlineplus
from latros.knowledge.models_v2 import ConceptV2, DesignationV2
from latros.knowledge.store_v2 import load_manifest_v2, snapshot_path_v2
from latros.sources.registry_v2 import load_registry_v2

SNAPSHOT = "v0.7.0-general-dev-unreviewed"
CONTENT_SHA256 = "bfda708aba44dcc5d12896ac7523d9d6bb577dea53bdc3810e499c15f64b1fb0"
BASELINE_SHA256 = "5eea9600f726e5306a07afb9405cce3f5795bd620c0efb9c53ae06d55b6ca704"


def replay(root: Path) -> list[CandidateAssertion]:
    manifest = load_manifest_v2(root, SNAPSHOT)
    if manifest.content_sha256 != CONTENT_SHA256:
        raise LatrosError("G4 requires the pinned immutable v0.7 snapshot")
    registry = load_registry_v2(root / "sources/registry-general-v0.7.yaml")
    source = registry.source("medlineplus", "2026-09-19")
    artifact = source.artifacts[0]
    raw = root / "data/raw" / source.source_id / source.release / artifact.filename
    if not raw.is_file() or sha256(raw) != artifact.sha256:
        raise LatrosError("G4 requires the pinned local MedlinePlus XML ZIP and SHA-256")
    concepts: dict[str, ConceptV2] = {}
    designations: dict[str, DesignationV2] = {}
    with duckdb.connect(str(snapshot_path_v2(root, SNAPSHOT)), read_only=True) as connection:
        rows = connection.execute(
            "SELECT payload_json FROM concept WHERE "
            "json_extract_string(payload_json, '$.primary_code') LIKE 'HP:%' OR "
            "json_extract_string(payload_json, '$.primary_code') LIKE 'MONDO:%' OR "
            "json_extract_string(payload_json, '$.primary_code') LIKE 'DOID:%'"
        ).fetchall()
        for (payload,) in rows:
            concept = ConceptV2.model_validate_json(payload)
            concepts[concept.concept_id] = concept
        connection.execute(
            "CREATE TEMP TABLE replay_concept_id AS SELECT id FROM concept WHERE "
            "json_extract_string(payload_json, '$.primary_code') LIKE 'HP:%' OR "
            "json_extract_string(payload_json, '$.primary_code') LIKE 'MONDO:%' OR "
            "json_extract_string(payload_json, '$.primary_code') LIKE 'DOID:%'"
        )
        rows = connection.execute(
            "SELECT d.payload_json FROM designation d JOIN replay_concept_id c "
            "ON c.id = json_extract_string(d.payload_json, '$.concept_id')"
        ).fetchall()
        for (payload,) in rows:
            designation = DesignationV2.model_validate_json(payload)
            designations[designation.designation_id] = designation
    candidates, _ = _import_medlineplus(root, source, concepts, designations, {}, {}, {}, {}, {})
    generated = b"".join(
        orjson.dumps(item.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS) + b"\n"
        for item in sorted(candidates, key=lambda item: item.candidate_assertion_id)
    )
    if hashlib.sha256(generated).hexdigest() != BASELINE_SHA256:
        raise LatrosError("Historical MedlinePlus candidate replay differs from the pinned set")
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    candidates = replay(args.root.resolve())
    print(f"Replayed {len(candidates)} historical candidates; SHA-256 {BASELINE_SHA256}")


if __name__ == "__main__":
    main()
