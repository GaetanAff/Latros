"""Versioned, optional verification policy over an immutable general result.

This is a transport/question-selection policy, not a clinical assertion or a
change to general_v1. Missing findings are never treated as contradictions.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import Field

from latros.clinical.v2 import ClinicalCaseV2
from latros.sources.registry import Contract

MAX_VERIFICATION_QUESTIONS = 6
TOP_CANDIDATES = 5


class VerificationItem(Contract):
    question_id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    observation_kind: Literal["symptom", "sign", "exam"]
    candidate_ids: list[str] = Field(min_length=1, max_length=TOP_CANDIDATES)


class VerificationPlanV1(Contract):
    policy_id: Literal["result_verification_v1"] = "result_verification_v1"
    base_run_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    baseline_observation_ids: list[str]
    baseline_question_ids: list[str]
    top_candidate_ids: list[str] = Field(max_length=TOP_CANDIDATES)
    items: list[VerificationItem] = Field(max_length=MAX_VERIFICATION_QUESTIONS)


class VerificationAnswerRequest(Contract):
    revision: int = Field(ge=0)
    question_id: str = Field(min_length=1)
    answer: Literal["present", "absent", "unknown", "not_assessed"]


def ranked_findings(
    case: ClinicalCaseV2, candidate_details: list[dict[str, Any]]
) -> list[tuple[str, list[str]]]:
    """Return unanswered, numerically eligible findings that distinguish top five.

    Frequency across candidate models is an engineering ordering heuristic only;
    it is not an information-gain estimate or a medical recommendation.
    """
    known = {item.concept.concept_id for item in case.observations}
    known.update(item.concept.concept_id for item in case.question_history)
    candidate_ids = [str(item["candidate_id"]) for item in candidate_details]
    mentions: dict[str, set[str]] = defaultdict(set)
    for candidate in candidate_details:
        candidate_id = str(candidate["candidate_id"])
        for contribution in candidate.get("unknown", []):
            finding = contribution.get("finding")
            details = contribution.get("details") or {}
            if (
                not isinstance(finding, str)
                or finding in known
                or contribution.get("reason") != "finding_not_observed"
                or contribution.get("observation") != "not_observed"
                or contribution.get("value") is not None
                or details.get("assertion_polarity") != "present"
                or not (
                    details.get("aggregatable") or details.get("single_source_numeric_eligible")
                )
            ):
                continue
            mentions[finding].add(candidate_id)
    # A finding shared by every hypothesis cannot distinguish these hypotheses.
    eligible = [
        (finding, sorted(ids))
        for finding, ids in mentions.items()
        if 0 < len(ids) < len(candidate_ids)
    ]
    return sorted(
        eligible,
        key=lambda item: (-min(len(item[1]), len(candidate_ids) - len(item[1])), item[0]),
    )


def next_item(plan: VerificationPlanV1, case: ClinicalCaseV2) -> VerificationItem | None:
    answered = {item.question_id for item in case.question_history}
    observed = {item.concept.concept_id for item in case.observations}
    return next(
        (
            item
            for item in plan.items
            if item.question_id not in answered and item.concept_id not in observed
        ),
        None,
    )


def plan_matches_case(plan: VerificationPlanV1, case: ClinicalCaseV2) -> bool:
    """Only answers to this plan may extend its immutable baseline."""
    if plan.case_id != case.case_id:
        return False
    expected_obs = set(plan.baseline_observation_ids)
    expected_questions = set(plan.baseline_question_ids)
    plan_ids = {item.question_id for item in plan.items}
    for response in case.question_history:
        if response.question_id in expected_questions:
            continue
        if response.question_id not in plan_ids:
            return False
        expected_obs.add(response.resulting_observation_id)
        expected_questions.add(response.question_id)
    return expected_obs == {item.observation_id for item in case.observations} and (
        expected_questions == {item.question_id for item in case.question_history}
    )
