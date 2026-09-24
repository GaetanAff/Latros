from pathlib import Path

import orjson
import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from latros.cli import app
from latros.common import LatrosError, sha256
from latros.knowledge.importers_v2 import import_registry_v2
from latros.sources.registry_v2 import RegistryV2


def _write_import_fixture(root: Path) -> tuple[RegistryV2, Path]:
    terminology = root / "data/raw/invented-rf2/test-v2"
    terminology.mkdir(parents=True, exist_ok=True)
    concepts = terminology / "concepts.tsv"
    descriptions = terminology / "descriptions.tsv"
    relationships = terminology / "relationships.tsv"
    concepts.write_text(
        "id\teffectiveTime\tactive\tmoduleId\tdefinitionStatusId\n"
        + "\n".join(
            f"{code}\t20260901\t1\tTEST-MODULE\tTEST-DEFINITION"
            for code in ("CROOT", "FROOT", "C1", "C2", "F1", "F2")
        )
        + "\n",
        encoding="utf-8",
    )
    terms = {
        "CROOT": "Invented condition root (disorder)",
        "FROOT": "Invented finding root (finding)",
        "C1": "Invented condition one (disorder)",
        "C2": "Invented condition two (disorder)",
        "F1": "Invented finding one (finding)",
        "F2": "Invented finding two (finding)",
    }
    descriptions.write_text(
        "id\teffectiveTime\tactive\tmoduleId\tconceptId\tlanguageCode\ttypeId\tterm\t"
        "caseSignificanceId\n"
        + "\n".join(
            f"D{index}\t20260901\t1\tTEST-MODULE\t{code}\ten\tTEST-FSN\t{term}\tTEST-CASE"
            for index, (code, term) in enumerate(terms.items(), 1)
        )
        + "\n",
        encoding="utf-8",
    )
    relationships.write_text(
        "id\teffectiveTime\tactive\tmoduleId\tsourceId\tdestinationId\trelationshipGroup\t"
        "typeId\tcharacteristicTypeId\tmodifierId\n"
        "R1\t20260901\t1\tTEST-MODULE\tC1\tCROOT\t0\tTEST-IS-A\tTEST\tTEST\n"
        "R2\t20260901\t1\tTEST-MODULE\tC2\tCROOT\t0\tTEST-IS-A\tTEST\tTEST\n"
        "R3\t20260901\t1\tTEST-MODULE\tF1\tFROOT\t0\tTEST-IS-A\tTEST\tTEST\n"
        "R4\t20260901\t1\tTEST-MODULE\tF2\tFROOT\t0\tTEST-IS-A\tTEST\tTEST\n",
        encoding="utf-8",
    )
    guidance = root / "data/raw/invented-guidance-import/test-v2"
    guidance.mkdir(parents=True, exist_ok=True)
    assertions = guidance / "assertions.jsonl"
    rows = []
    for index, (condition, finding, polarity) in enumerate(
        (
            ("C1", "F1", "present"),
            ("C1", "F2", "excluded"),
            ("C2", "F1", "present"),
            ("C2", "F2", "present"),
        ),
        1,
    ):
        rows.append(
            {
                "record_id": f"A{index}",
                "record_locator": f"invented-section-{index}",
                "source_text_sha256": f"{index:x}" * 64,
                "subject": {"system": "urn:latros:test-rf2", "code": condition},
                "relation": "has_symptom",
                "object": {"system": "urn:latros:test-rf2", "code": finding},
                "polarity": polarity,
                "population": ["synthetic adults"],
                "clinical_context": "invented outpatient context",
                "evidence_type": "synthetic fixture",
                "curator_id": "invented-curator",
                "reviewers": [
                    {"reviewer_id": "invented-clinical-reviewer", "role": "clinical"},
                    {"reviewer_id": "invented-mapping-reviewer", "role": "mapping"},
                ],
                "status": "approved",
                "evidence_family": {
                    "family_id": "evidence-family:invented-import",
                    "dependency_type": "primary",
                    "primary_reference": "invented-guidance-import:test-v2",
                },
            }
        )
    assertions.write_bytes(b"\n".join(orjson.dumps(row) for row in rows) + b"\n")
    registry = RegistryV2.model_validate(
        {
            "schema_version": 2,
            "canonical_schema_version": 2,
            "scope": {
                "scope_id": "synthetic-import",
                "domain": "invented import validation",
                "population": "synthetic adults aged 18 years or older",
                "observation_types": ["symptom"],
                "relations": ["has_symptom"],
                "exclusions": ["not medical knowledge"],
            },
            "compatible_profiles": ["general_v1-default"],
            "sources": [
                _source(
                    "invented-rf2",
                    "urn:latros:test-rf2",
                    "terminology",
                    [
                        _artifact(concepts, "rf2-concepts-tsv"),
                        _artifact(descriptions, "rf2-descriptions-tsv"),
                        _artifact(relationships, "rf2-relationships-tsv"),
                    ],
                ),
                _source(
                    "invented-guidance-import",
                    "urn:latros:test-guidance",
                    "clinical_assertion_source",
                    [_artifact(assertions, "curated-assertions-jsonl")],
                ),
            ],
        }
    )
    registry_path = root / "sources/registry-v2.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(registry.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )
    return registry, registry_path


def _source(source_id: str, system: str, role: str, artifacts: list[dict[str, str]]):
    return {
        "source_id": source_id,
        "producer": "Latros tests",
        "roles": [role],
        "code_system": system,
        "homepage": f"https://example.test/{source_id}/test-v2",
        "release": "test-v2",
        "release_date": "2026-09-01",
        "access_date": "2026-09-17",
        "importer": "latros.knowledge.importers_v2:import_registry_v2",
        "license": {
            "name": "Synthetic fixture",
            "url": "https://example.test/licenses/synthetic-v2",
            "attribution": "Invented by Latros tests",
            "redistribution": "allowed_with_attribution",
            "implementation_rights_confirmed": True,
            "transformation_rights": "allowed",
            "restrictions": [],
        },
        "dependencies": [],
        "artifacts": artifacts,
    }


def _artifact(path: Path, artifact_format: str):
    return {
        "filename": path.name,
        "product": "Invented fixture",
        "format": artifact_format,
        "language": "en",
        "source_url": f"https://example.test/releases/test-v2/{path.name}",
        "sha256": sha256(path),
        "access_mode": "manual_local",
    }


def test_rf2_and_curated_assertions_import_with_full_provenance(tmp_path) -> None:
    registry, _ = _write_import_fixture(tmp_path)

    knowledge = import_registry_v2(tmp_path, registry)

    assert len(knowledge.concepts) == 6
    assert len(knowledge.hierarchy_edges) == 4
    assert len(knowledge.source_records) == 4
    assert len(knowledge.source_assertions) == 4
    assert len(knowledge.canonical_assertions) == 4
    assert knowledge.concept_mappings == []
    assert len(knowledge.evidence_families) == 1
    assert all(assertion.artifact_ids for assertion in knowledge.source_assertions)
    assert all(assertion.source_record_id for assertion in knowledge.source_assertions)


def test_curated_assertions_refuse_unknown_codes_and_duplicate_records(tmp_path) -> None:
    registry, _ = _write_import_fixture(tmp_path)
    path = tmp_path / "data/raw/invented-guidance-import/test-v2/assertions.jsonl"
    lines = path.read_bytes().splitlines()
    changed = orjson.loads(lines[0])
    changed["object"]["code"] = "UNKNOWN"
    path.write_bytes(orjson.dumps(changed) + b"\n" + b"\n".join(lines[1:]) + b"\n")
    registry.sources[1].artifacts[0].sha256 = sha256(path)
    with pytest.raises(LatrosError, match="unknown code"):
        import_registry_v2(tmp_path, registry)

    registry, _ = _write_import_fixture(tmp_path)
    path = tmp_path / "data/raw/invented-guidance-import/test-v2/assertions.jsonl"
    lines = path.read_bytes().splitlines()
    path.write_bytes(b"\n".join(lines + [lines[0]]) + b"\n")
    registry.sources[1].artifacts[0].sha256 = sha256(path)
    with pytest.raises(LatrosError, match="Duplicate curated record"):
        import_registry_v2(tmp_path, registry)


def test_curated_assertion_requires_distinct_clinical_and_mapping_reviewers(tmp_path) -> None:
    registry, _ = _write_import_fixture(tmp_path)
    path = tmp_path / "data/raw/invented-guidance-import/test-v2/assertions.jsonl"
    lines = path.read_bytes().splitlines()
    changed = orjson.loads(lines[0])
    changed["reviewers"][1]["role"] = "clinical"
    path.write_bytes(orjson.dumps(changed) + b"\n" + b"\n".join(lines[1:]) + b"\n")
    registry.sources[1].artifacts[0].sha256 = sha256(path)

    with pytest.raises(ValidationError, match="clinical and mapping"):
        import_registry_v2(tmp_path, registry)


def test_rf2_cycle_and_missing_columns_are_rejected(tmp_path) -> None:
    registry, _ = _write_import_fixture(tmp_path)
    relationships = tmp_path / "data/raw/invented-rf2/test-v2/relationships.tsv"
    with relationships.open("a", encoding="utf-8") as handle:
        handle.write("R5\t20260901\t1\tTEST-MODULE\tCROOT\tC1\t0\tTEST-IS-A\tTEST\tTEST\n")
    registry.sources[0].artifacts[2].sha256 = sha256(relationships)
    with pytest.raises(ValidationError, match="Hierarchy cycle"):
        import_registry_v2(tmp_path, registry)

    registry, _ = _write_import_fixture(tmp_path)
    concepts = tmp_path / "data/raw/invented-rf2/test-v2/concepts.tsv"
    concepts.write_text("id\nC1\n", encoding="utf-8")
    registry.sources[0].artifacts[0].sha256 = sha256(concepts)
    with pytest.raises(LatrosError, match="missing columns"):
        import_registry_v2(tmp_path, registry)


def test_cli_dispatches_v2_registry_build_and_inspection(tmp_path) -> None:
    _, registry_path = _write_import_fixture(tmp_path)
    runner = CliRunner()
    prefix = ["--root", str(tmp_path), "--registry", str(registry_path)]

    for command in (
        ["sources", "validate"],
        ["sources", "fetch", "--source", "invented-rf2", "--release", "test-v2"],
        ["data", "build", "--snapshot", "test-imported-v2"],
        ["data", "inspect", "--snapshot", "test-imported-v2"],
    ):
        result = runner.invoke(app, prefix + command)
        assert result.exit_code == 0, result.output
        assert orjson.loads(result.stdout)
    inspected = orjson.loads(
        runner.invoke(app, prefix + ["data", "inspect", "--snapshot", "test-imported-v2"]).stdout
    )
    assert inspected["schema_version"] == 2
    assert inspected["snapshot"] == "test-imported-v2"
