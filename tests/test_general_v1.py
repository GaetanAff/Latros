from pathlib import Path

import orjson
import pytest
from typer.testing import CliRunner

from latros.cli import app
from latros.clinical.models import ClinicalCase
from latros.clinical.v2 import (
    ClinicalCaseV2,
    QuantityValue,
    SubjectContext,
    SymptomObservation,
)
from latros.common import LatrosError, write_json
from latros.knowledge.models_v2 import CanonicalKnowledgeV2
from latros.knowledge.store_v2 import build_snapshot_v2
from latros.reasoning.general_v1 import GeneralV1Strategy
from latros.reasoning.profiles import load_reasoning_profile


def _profile():
    root = Path(__file__).resolve().parents[1]
    return load_reasoning_profile(root / "profiles/general_v1.json")


def _age(value: float = 30) -> SubjectContext:
    return SubjectContext(
        age=QuantityValue(
            value=value,
            unit="year",
            system="http://unitsofmeasure.org",
            code="a",
        )
    )


def _symptom(
    index: int,
    status: str,
    *,
    evaluation: str = "assessed",
    reason: str | None = None,
    system: str = "urn:latros:test-terminology",
    code: str | None = None,
    concept_id: str | None = None,
) -> SymptomObservation:
    return SymptomObservation.model_validate(
        {
            "observation_id": f"observation-{index}-{status}-{evaluation}",
            "concept": {
                "concept_id": concept_id or f"test:finding-{index}",
                "coding": {
                    "system": system,
                    "code": code or f"TEST:finding-{index}",
                },
            },
            "clinical_status": status,
            "evaluation_status": evaluation,
            "uncertainty_reason": reason,
            "acquisition_method": "reported",
            "provenance": {
                "provenance_id": f"provenance-{index}-{status}-{evaluation}",
                "origin_type": "patient_report",
            },
        }
    )


def _case(*observations: SymptomObservation, age: float = 30) -> ClinicalCaseV2:
    return ClinicalCaseV2(
        case_id="general-v1-case",
        subject_context=_age(age),
        observations=list(observations),
    )


def _strategy(synthetic_v2, *, snapshot: str = "test-v2") -> GeneralV1Strategy:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, snapshot, knowledge)
    return GeneralV1Strategy(root, snapshot, _profile())


def test_general_v1_ranks_explicit_matches_without_calling_them_probabilities(
    synthetic_v2,
) -> None:
    strategy = _strategy(synthetic_v2)
    case = _case(_symptom(1, "present"), _symptom(2, "absent"))

    result = strategy.diagnose(case)
    repeated = strategy.diagnose(case)

    assert result == repeated
    assert result.status == "ranked"
    assert [item.candidate_id for item in result.candidates] == [
        "test:condition-1",
        "test:condition-2",
        "test:condition-4",
    ]
    assert [item.aggregate.value for item in result.candidates] == [1.0, 0.0, -1.0]
    assert result.candidates[0].aggregate.scale_id == "general_v1.compatibility"
    assert not result.candidates[0].aggregate.calibrated
    assert result.candidates[0].source_views[0].source_release_id == ("invented-guidance:test-v2")
    assert result.run_receipt == repeated.run_receipt
    assert result.run_receipt.evidence_family_ids_used == ["evidence-family:invented-guidance"]
    assert result.safety.status == "not_evaluated"


def test_exact_mapping_scores_and_is_recorded_in_receipt(synthetic_v2) -> None:
    strategy = _strategy(synthetic_v2)
    alternate = _symptom(
        1,
        "present",
        system="urn:latros:test-alternate",
        code="ALT:F1",
        concept_id="external:alternate-finding-1",
    )

    result = strategy.diagnose(_case(alternate, _symptom(2, "absent")))

    assert result.status == "ranked"
    assert result.candidates[0].candidate_id == "test:condition-1"
    assert len(result.run_receipt.mappings_applied) == 1
    assert result.candidates[0].terminology_mappings == result.run_receipt.mappings_applied


@pytest.mark.parametrize(
    ("evaluation", "reason"),
    [("assessed", "unknown_to_subject"), ("unable_to_assess", "unable_to_assess")],
)
def test_unknown_and_unable_to_assess_are_neutral(
    synthetic_v2, evaluation: str, reason: str
) -> None:
    strategy = _strategy(synthetic_v2)
    unknown = _symptom(1, "unknown", evaluation=evaluation, reason=reason)

    result = strategy.diagnose(_case(unknown, _symptom(2, "present")))

    assert result.status == "abstained"
    assert result.abstention is not None
    assert result.abstention.reason == "insufficient_supported_findings"


def test_population_and_coverage_gates_are_explicit(synthetic_v2) -> None:
    strategy = _strategy(synthetic_v2)
    child = strategy.diagnose(_case(_symptom(1, "present"), _symptom(2, "absent"), age=12))
    missing_age = strategy.diagnose(
        ClinicalCaseV2(
            case_id="missing-age",
            observations=[_symptom(1, "present"), _symptom(2, "absent")],
        )
    )
    unsupported = _symptom(
        3,
        "present",
        system="urn:latros:unsupported",
        code="UNKNOWN",
        concept_id="external:unknown",
    )
    unsupported_second = _symptom(
        4,
        "present",
        system="urn:latros:unsupported",
        code="UNKNOWN-2",
        concept_id="external:unknown-2",
    )
    low_coverage = strategy.diagnose(_case(_symptom(1, "present"), unsupported, unsupported_second))

    assert child.abstention is not None
    assert child.abstention.reason == "outside_snapshot_population"
    assert missing_age.abstention is not None
    assert missing_age.abstention.reason == "missing_required_context"
    assert low_coverage.abstention is not None
    assert low_coverage.abstention.reason == "insufficient_case_coverage"
    assert low_coverage.coverage.coverage_ratio == pytest.approx(1 / 3)


def test_unknown_source_dependency_is_visible_but_not_aggregated(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    dependencies = [
        item.model_copy(
            update={
                "dependency_type": (
                    "unknown"
                    if item.source_release_id == "invented-guidance:test-v2"
                    else item.dependency_type
                )
            }
        )
        for item in knowledge.source_dependencies
    ]
    payload = knowledge.model_dump(mode="json")
    payload["source_dependencies"] = [item.model_dump(mode="json") for item in dependencies]
    restricted = CanonicalKnowledgeV2.model_validate(payload)
    build_snapshot_v2(root, registry, "test-v2-unknown-dependency", restricted)
    strategy = GeneralV1Strategy(root, "test-v2-unknown-dependency", _profile())

    result = strategy.diagnose(_case(_symptom(1, "present"), _symptom(2, "absent")))

    assert result.status == "abstained"
    assert result.abstention is not None
    assert result.abstention.reason == "insufficient_snapshot_coverage"
    assert result.candidates == []


def test_question_requires_explicit_opposing_assertions(synthetic_v2) -> None:
    strategy = _strategy(synthetic_v2)

    selected = strategy.question(_case())
    exhausted = strategy.question(_case(_symptom(2, "present"), _symptom(3, "absent")))

    assert selected.status == "question"
    assert selected.question is not None
    assert selected.question.concept.code == "TEST:finding-2"
    assert "unable_to_assess" in selected.question.allowed_answers
    assert selected.question.expected_contribution["not_a_clinical_probability"] is True
    assert selected.question.assertion_ids
    assert exhausted.status == "stopped"
    assert exhausted.stop_reason == "insufficient_question_evidence"


def test_candidate_generation_scoring_and_explanation_interfaces(synthetic_v2) -> None:
    strategy = _strategy(synthetic_v2)
    case = _case(_symptom(1, "present"), _symptom(2, "absent"))

    candidates = strategy.generate(case)
    assessments = strategy.score(case, candidates)
    explanation = strategy.build(case, assessments)

    assert len(candidates.candidate_ids) == 4
    assert assessments[0].candidate_id == "test:condition-1"
    assert explanation.payload["status"] == "ranked"


def test_cli_runs_general_v1_and_rejects_v1_contract(synthetic_v2) -> None:
    strategy = _strategy(synthetic_v2)
    root = strategy.root
    v2_path = root / "general-v2.json"
    v1_path = root / "legacy-v1.json"
    write_json(
        v2_path,
        _case(_symptom(1, "present"), _symptom(2, "absent")).model_dump(mode="json"),
    )
    write_json(
        v1_path,
        ClinicalCase(
            case_id="legacy",
            observations=[{"concept_id": "HP:9000001", "status": "present"}],
        ).model_dump(mode="json"),
    )
    runner = CliRunner()
    prefix = [
        "--root",
        str(root),
        "diagnose",
        "--snapshot",
        "test-v2",
        "--strategy",
        "general_v1",
    ]

    success = runner.invoke(app, [*prefix, "--case", str(v2_path)])
    legacy = runner.invoke(app, [*prefix, "--case", str(v1_path)])

    assert success.exit_code == 0, success.output
    payload = orjson.loads(success.stdout)
    assert payload["schema_version"] == 2
    assert payload["candidates"][0]["candidate_id"] == "test:condition-1"
    assert legacy.exit_code == 1
    assert isinstance(legacy.exception, LatrosError)
    assert "only ClinicalCaseV2" in str(legacy.exception)
