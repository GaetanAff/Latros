"""Invented findings only: policy mechanics, not medical validation."""

import pytest
from pydantic import ValidationError

from latros.clinical.v2 import ClinicalCaseV2
from latros.ui.result_verification import (
    MAX_VERIFICATION_QUESTIONS,
    VerificationItem,
    VerificationPlanV1,
    next_item,
    plan_matches_case,
    ranked_findings,
)
from latros.ui.server import _case_with_question_answer


def _unknown(finding: str, *, eligible: bool = True) -> dict:
    return {
        "finding": finding,
        "observation": "not_observed",
        "reason": "finding_not_observed",
        "value": None,
        "details": {
            "assertion_polarity": "present",
            "aggregatable": False,
            "single_source_numeric_eligible": eligible,
        },
    }


def test_top_five_ranking_deduplicates_and_never_infers_absence() -> None:
    case = ClinicalCaseV2(case_id="case-invented")
    details = [
        {
            "candidate_id": f"condition-{index}",
            "unknown": [
                _unknown("finding-shared"),
                *[_unknown(f"finding-{j}") for j in range(index + 1)],
                _unknown("not-eligible", eligible=False),
            ],
        }
        for index in range(5)
    ]
    ranked = ranked_findings(case, details)
    assert "finding-shared" not in [item[0] for item in ranked]
    assert "not-eligible" not in [item[0] for item in ranked]
    assert len([item for item in ranked if item[0] == "finding-2"]) == 1
    assert len(ranked) <= MAX_VERIFICATION_QUESTIONS


def test_plan_answers_are_independent_and_unknown_is_not_a_contradiction() -> None:
    case = ClinicalCaseV2(case_id="case-invented")
    item = VerificationItem(
        question_id="result_verification_v1:example",
        concept_id="test:finding-1",
        system="urn:latros:test-terminology",
        code="TEST:finding-1",
        label="Invented sign",
        observation_kind="symptom",
        candidate_ids=["condition-a"],
    )
    plan = VerificationPlanV1(
        base_run_id="000001-diagnose-example",
        case_id=case.case_id,
        baseline_observation_ids=[],
        baseline_question_ids=[],
        top_candidate_ids=["condition-a", "condition-b"],
        items=[item],
    )
    assert plan_matches_case(plan, case)
    assert next_item(plan, case) == item
    answered = _case_with_question_answer(
        case,
        item.question_id,
        {
            "concept_id": item.concept_id,
            "system": item.system,
            "code": item.code,
            "label": item.label,
            "observation_kind": item.observation_kind,
        },
        "unknown",
    )
    assert answered.observations[-1].clinical_status == "unknown"
    assert next_item(plan, answered) is None
    assert plan_matches_case(plan, answered)
    assert not plan_matches_case(plan, answered.model_copy(update={"observations": []}))
    edited = answered.model_dump(mode="json")
    edited["question_history"] = []
    edited["observations"] = [
        {
            "kind": "symptom",
            "observation_id": "manual-correction",
            "concept": answered.observations[-1].concept.model_dump(mode="json"),
            "clinical_status": "present",
            "evaluation_status": "assessed",
            "acquisition_method": "reported",
            "provenance": {"provenance_id": "manual-provenance", "origin_type": "patient_report"},
        }
    ]
    corrected = ClinicalCaseV2.model_validate(edited)
    assert corrected.observations[-1].clinical_status == "present"
    assert not plan_matches_case(plan, corrected)  # Old plan must not silently follow edits.


def test_six_question_limit_is_a_contract_not_six_per_condition() -> None:
    items = [
        VerificationItem(
            question_id=f"result_verification_v1:{index}",
            concept_id=f"test:finding-{index}",
            system="urn:latros:test-terminology",
            code=f"TEST:finding-{index}",
            label=f"Invented sign {index}",
            observation_kind="symptom",
            candidate_ids=["condition-a"],
        )
        for index in range(7)
    ]
    with pytest.raises(ValidationError):
        VerificationPlanV1(
            base_run_id="000001-diagnose-example",
            case_id="invented-case",
            baseline_observation_ids=[],
            baseline_question_ids=[],
            top_candidate_ids=["condition-a", "condition-b"],
            items=items,
        )
