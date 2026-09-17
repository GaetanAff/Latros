from pathlib import Path

import orjson
import pytest
from typer.testing import CliRunner

from latros.cli import app
from latros.clinical.migration import migrate_case_v1_to_v2
from latros.clinical.models import ClinicalCase
from latros.clinical.v2 import (
    ClinicalCaseV2,
    Coding,
    ConceptReference,
    ObservationProvenance,
    SignObservation,
)
from latros.common import LatrosError, write_json
from latros.reasoning.engine import Engine
from latros.reasoning.profiles import (
    ReasoningProfile,
    load_reasoning_profile,
    reasoning_profile_hash,
)
from latros.reasoning.results_v2 import build_differential_v2, build_question_v2
from latros.reasoning.semantic_v1_adapter import SemanticV1Adapter


def _profile() -> ReasoningProfile:
    root = Path(__file__).resolve().parents[1]
    return load_reasoning_profile(root / "profiles/semantic_v1.json")


def _legacy(code: str = "HP:9000001") -> ClinicalCase:
    return ClinicalCase.model_validate(
        {
            "case_id": "v2-result",
            "observations": [{"concept_id": code, "status": "present"}],
        }
    )


def _unsupported_sign() -> SignObservation:
    return SignObservation(
        observation_id="snomed-sign",
        concept=ConceptReference(
            concept_id="snomed:sign",
            coding=Coding(system="http://snomed.info/sct", code="123456"),
        ),
        clinical_status="present",
        evaluation_status="assessed",
        acquisition_method="observed",
        provenance=ObservationProvenance(
            provenance_id="p-snomed", origin_type="clinician_observation"
        ),
    )


def test_differential_v2_is_explainable_per_source_and_receipt_is_stable(built) -> None:
    root, _ = built
    adapter = SemanticV1Adapter(Engine(root, "test"))
    case = migrate_case_v1_to_v2(_legacy())

    result = build_differential_v2(root, case, adapter, _profile())
    repeated = build_differential_v2(root, case, adapter, _profile())

    assert result == repeated
    assert result.status == "ranked"
    assert result.scope_status == "in_scope"
    assert result.safety.status == "not_evaluated"
    assert result.run_receipt == repeated.run_receipt
    assert result.run_receipt.source_releases_used == ["orphadata:test-v1"]
    assert result.run_receipt.snapshot_content_sha256 == adapter.engine.manifest["content_sha256"]
    assert result.candidates[0].aggregate.kind == "compatibility"
    assert not result.candidates[0].aggregate.calibrated
    for candidate in result.candidates:
        numeric = [*candidate.favorable, *candidate.unfavorable]
        assert sum(item.value for item in numeric if item.value is not None) == pytest.approx(
            candidate.aggregate.value
        )
        assert sum(view.subtotal for view in candidate.source_views) == pytest.approx(
            candidate.aggregate.value
        )


def test_mixed_case_is_partial_and_unsupported_data_is_explicit(built) -> None:
    root, _ = built
    adapter = SemanticV1Adapter(Engine(root, "test"))
    migrated = migrate_case_v1_to_v2(_legacy())
    case = migrated.model_copy(
        update={"observations": [*migrated.observations, _unsupported_sign()]}
    )
    case = ClinicalCaseV2.model_validate(case.model_dump(mode="json"))

    result = build_differential_v2(root, case, adapter, _profile())

    assert result.status == "ranked"
    assert result.scope_status == "partial"
    assert result.coverage.coverage_ratio == 0.5
    ignored = [item for item in result.coverage.inputs if item.disposition == "ignored"]
    assert ignored[0].reason == "unsupported_observation_type"
    assert result.run_receipt.warnings


def test_case_with_no_supported_phenotype_abstains_out_of_scope(built) -> None:
    root, _ = built
    adapter = SemanticV1Adapter(Engine(root, "test"))
    case = ClinicalCaseV2(case_id="outside", observations=[_unsupported_sign()])

    result = build_differential_v2(root, case, adapter, _profile())

    assert result.status == "abstained"
    assert result.scope_status == "out_of_scope"
    assert result.abstention is not None
    assert result.abstention.reason == "no_supported_present_observation"
    assert result.candidates == []


def test_supported_but_uncovered_phenotype_abstains_without_false_reassurance(built) -> None:
    root, _ = built
    adapter = SemanticV1Adapter(Engine(root, "test"))
    case = migrate_case_v1_to_v2(_legacy("HP:9000015"))

    result = build_differential_v2(root, case, adapter, _profile())

    assert result.status == "abstained"
    assert result.scope_status == "partial"
    assert result.abstention is not None
    assert result.abstention.reason == "insufficient_snapshot_coverage"


def test_question_v2_exposes_unable_to_assess_and_evidence(built) -> None:
    root, _ = built
    adapter = SemanticV1Adapter(Engine(root, "test"))
    case = migrate_case_v1_to_v2(_legacy())

    result = build_question_v2(root, case, adapter, _profile())

    assert result.status == "question"
    assert result.question is not None
    assert "unable_to_assess" in result.question.allowed_answers
    assert result.question.assertion_ids
    assert result.question.source_release_ids == ["orphadata:test-v1"]
    assert result.question.expected_contribution["not_a_clinical_probability"] is True
    assert result.safety.status == "not_evaluated"


def test_snapshot_profile_mismatch_is_rejected(built) -> None:
    root, _ = built
    adapter = SemanticV1Adapter(Engine(root, "test"))
    payload = _profile().model_dump(mode="json")
    payload["compatible_snapshot_schema_versions"] = [2]
    payload["profile_sha256"] = reasoning_profile_hash(payload)
    incompatible = ReasoningProfile.model_validate(payload)

    with pytest.raises(LatrosError, match="incompatible"):
        build_differential_v2(root, _legacy(), adapter, incompatible)


def test_cli_auto_selects_v2_for_v2_cases_and_preserves_v1_default(built) -> None:
    root, _ = built
    runner = CliRunner()
    legacy_path = root / "legacy.json"
    v2_path = root / "v2.json"
    write_json(legacy_path, _legacy().model_dump(mode="json"))
    write_json(v2_path, migrate_case_v1_to_v2(_legacy()).model_dump(mode="json"))
    prefix = ["--root", str(root), "diagnose", "--snapshot", "test"]

    legacy = runner.invoke(app, [*prefix, "--case", str(legacy_path)])
    explicit_v2 = runner.invoke(
        app,
        [*prefix, "--case", str(legacy_path), "--output-contract", "v2"],
    )
    automatic_v2 = runner.invoke(app, [*prefix, "--case", str(v2_path)])

    assert legacy.exit_code == 0, legacy.output
    assert "schema_version" not in orjson.loads(legacy.stdout)
    for result in (explicit_v2, automatic_v2):
        assert result.exit_code == 0, result.output
        payload = orjson.loads(result.stdout)
        assert payload["schema_version"] == 2
        assert payload["run_receipt"]["profile_sha256"] == _profile().profile_sha256


def test_cli_rejects_unknown_strategy(built) -> None:
    root, _ = built
    case = root / "legacy.json"
    write_json(case, _legacy().model_dump(mode="json"))
    result = CliRunner().invoke(
        app,
        [
            "--root",
            str(root),
            "diagnose",
            "--snapshot",
            "test",
            "--case",
            str(case),
            "--strategy",
            "unknown",
        ],
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, LatrosError)
    assert "Unknown reasoning strategy" in str(result.exception)
