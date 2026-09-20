from datetime import date

import pytest
from pydantic import ValidationError

from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.sources.registry_v2 import RegistryV2


def _registry_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
        "canonical_schema_version": 2,
        "scope": {
            "scope_id": "synthetic-adult-outpatient",
            "domain": "invented outpatient examples",
            "population": "synthetic adults",
            "observation_types": ["symptom", "sign", "exam", "vital"],
            "relations": ["has_symptom", "has_sign", "has_exam_finding"],
            "exclusions": ["not medical knowledge"],
        },
        "compatible_profiles": ["general_v1-default"],
        "sources": [
            {
                "source_id": "invented-terminology",
                "producer": "Latros tests",
                "roles": ["terminology"],
                "code_system": "urn:latros:test-terminology",
                "homepage": "https://example.org/invented-terminology/1",
                "release": "test-1",
                "release_date": "2026-09-01",
                "access_date": "2026-09-17",
                "importer": "latros.tests.synthetic_v2",
                "license": {
                    "name": "Synthetic test fixture",
                    "url": "https://example.org/invented-license/1",
                    "attribution": "Invented by Latros tests",
                    "redistribution": "allowed_with_attribution",
                    "implementation_rights_confirmed": True,
                    "transformation_rights": "allowed",
                    "restrictions": [],
                    "notes": "No external terminology content",
                },
                "dependencies": [],
                "artifacts": [
                    {
                        "filename": "concepts.tsv",
                        "product": "invented concepts",
                        "format": "rf2-concepts-tsv",
                        "language": "en",
                        "source_url": "https://example.org/releases/test-1/concepts.tsv",
                        "sha256": "a" * 64,
                        "access_mode": "manual_local",
                    }
                ],
            }
        ],
    }


def test_registry_v2_accepts_manual_synthetic_source() -> None:
    registry = RegistryV2.model_validate(_registry_payload())

    assert registry.schema_version == 2
    assert registry.sources[0].access_date == date(2026, 9, 17)
    assert registry.sources[0].artifacts[0].access_mode == "manual_local"
    assert registry.sources[0].producer == "Latros tests"


def test_registry_v2_refuses_unreviewed_rights_and_moving_urls() -> None:
    payload = _registry_payload()
    source = payload["sources"][0]  # type: ignore[index]
    source["license"]["implementation_rights_confirmed"] = False  # type: ignore[index]
    with pytest.raises(ValidationError, match="Implementation rights"):
        RegistryV2.model_validate(payload)

    payload = _registry_payload()
    source = payload["sources"][0]  # type: ignore[index]
    source["artifacts"][0]["source_url"] = "https://example.org/latest/concepts.tsv"  # type: ignore[index]
    with pytest.raises(ValidationError, match="moving branch"):
        RegistryV2.model_validate(payload)

    payload = _registry_payload()
    source = payload["sources"][0]  # type: ignore[index]
    source["roles"] = ["diagnostic_assertions"]  # type: ignore[index]
    with pytest.raises(ValidationError, match="Unknown source roles"):
        RegistryV2.model_validate(payload)

    payload = _registry_payload()
    source = payload["sources"][0]  # type: ignore[index]
    del source["importer"]  # type: ignore[index]
    with pytest.raises(ValidationError, match="Source importer"):
        RegistryV2.model_validate(payload)

    payload = _registry_payload()
    source = payload["sources"][0]  # type: ignore[index]
    source["release_identity_method"] = "dated_capture"  # type: ignore[index]
    with pytest.raises(ValidationError, match="capture_identity"):
        RegistryV2.model_validate(payload)


def test_manifest_v2_separates_scope_sources_tables_and_profiles() -> None:
    registry = RegistryV2.model_validate(_registry_payload())
    manifest = KnowledgeSnapshotManifestV2(
        snapshot="test-v2",
        latros_version="0.4.0",
        build_pipeline_sha256="b" * 64,
        duckdb_version="1.4.0",
        scope=registry.scope,
        sources=registry.sources,
        source_dependencies=[],
        evidence_families=[],
        rules={"mapping": "exact_or_equivalent_only"},
        tables={
            "concept": {
                "rows": 1,
                "logical_sha256": "c" * 64,
                "parquet_sha256": "d" * 64,
            }
        },
        compatible_profiles=registry.compatible_profiles,
        redistribution="allowed_with_attribution",
        content_sha256="e" * 64,
    )

    assert manifest.schema_version == 2
    assert manifest.scope.scope_id == "synthetic-adult-outpatient"
    assert manifest.compatible_profiles == ["general_v1-default"]


def test_manifest_v2_refuses_publication_with_errors() -> None:
    registry = RegistryV2.model_validate(_registry_payload())
    with pytest.raises(ValidationError, match="cannot contain errors"):
        KnowledgeSnapshotManifestV2(
            snapshot="test-v2",
            latros_version="0.4.0",
            build_pipeline_sha256="b" * 64,
            duckdb_version="1.4.0",
            scope=registry.scope,
            sources=registry.sources,
            source_dependencies=[],
            evidence_families=[],
            rules={},
            tables={
                "concept": {
                    "rows": 0,
                    "logical_sha256": "c" * 64,
                    "parquet_sha256": "d" * 64,
                }
            },
            compatible_profiles=["general_v1-default"],
            redistribution="restricted",
            content_sha256="e" * 64,
            errors=["invented failure"],
        )
