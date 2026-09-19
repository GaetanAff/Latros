from copy import deepcopy

import duckdb
import pytest

from latros.common import LatrosError
from latros.knowledge.models_v2 import CANONICAL_TABLES_V2
from latros.knowledge.store_v2 import (
    V2_TABLES,
    build_snapshot_v2,
    load_manifest_v2,
    read_knowledge_v2,
    snapshot_path_v2,
)


def test_v2_snapshot_builds_all_tables_and_round_trips(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2

    manifest = build_snapshot_v2(root, registry, "test-v2", knowledge)
    loaded_manifest, loaded_knowledge = read_knowledge_v2(root, "test-v2")

    assert set(manifest.tables) == set(CANONICAL_TABLES_V2) == set(V2_TABLES)
    assert loaded_manifest == manifest
    for _, (collection, identifier, _) in V2_TABLES.items():
        loaded = {
            getattr(item, identifier): item.model_dump(mode="json")
            for item in getattr(loaded_knowledge, collection)
        }
        original = {
            getattr(item, identifier): item.model_dump(mode="json")
            for item in getattr(knowledge, collection)
        }
        assert loaded == original
    assert manifest.scope.scope_id == "synthetic-adult-outpatient"
    assert manifest.redistribution == "allowed_with_attribution"


def test_v2_snapshot_is_reproducible_idempotent_and_read_only(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2

    first = build_snapshot_v2(root, registry, "test-v2", knowledge)
    same = build_snapshot_v2(root, registry, "test-v2", knowledge)
    second = build_snapshot_v2(root, registry, "again-v2", knowledge)

    assert first == same
    assert first.tables == second.tables
    assert first.content_sha256 == second.content_sha256
    with duckdb.connect(str(snapshot_path_v2(root, "test-v2")), read_only=True) as database:
        with pytest.raises(duckdb.InvalidInputException):
            database.execute('DELETE FROM "concept"')


def test_v2_snapshot_refuses_corruption_and_unpublished_directories(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    snapshot_path_v2(root, "test-v2").write_bytes(b"corrupted")

    with pytest.raises(LatrosError, match="checksum"):
        load_manifest_v2(root, "test-v2")

    unpublished = root / "data/canonical/unpublished-v2"
    unpublished.mkdir(parents=True)
    with pytest.raises(LatrosError, match="Unpublished"):
        build_snapshot_v2(root, registry, "unpublished-v2", knowledge)


def test_v2_snapshot_refuses_missing_source_and_registry_drift(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    source_path = root / "data/raw/invented-guidance/test-v2/assertions.jsonl"
    source_path.write_bytes(b"changed")
    with pytest.raises(LatrosError, match="Missing/corrupt"):
        build_snapshot_v2(root, registry, "bad-source-v2", knowledge)

    source_path.write_bytes(b"Invented assertions fixture; not medical knowledge.\n")
    changed = deepcopy(knowledge)
    changed.source_artifacts[0].filename = "different.tsv"
    with pytest.raises(LatrosError, match="artifacts do not match"):
        build_snapshot_v2(root, registry, "bad-registry-v2", changed)


def test_v2_reconstruction_checks_pinned_manifest(synthetic_v2, tmp_path_factory) -> None:
    import shutil

    root, registry, knowledge = synthetic_v2
    expected = build_snapshot_v2(root, registry, "test-v2", knowledge)
    clone = tmp_path_factory.mktemp("v2-clone")
    shutil.copytree(root / "data/raw", clone / "data/raw")
    shutil.copytree(root / "manifests", clone / "manifests")

    rebuilt = build_snapshot_v2(clone, registry, "test-v2", knowledge)

    assert rebuilt == expected
    assert load_manifest_v2(clone, "test-v2") == expected
