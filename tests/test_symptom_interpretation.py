import json

import pytest

from latros.application.models import ConceptOption
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError
from latros.ui.symptom_interpretation import (
    ConfirmInterpretationRequest,
    confirm_mentions,
    map_mentions,
    parse_mentions,
)


def _option() -> ConceptOption:
    return ConceptOption(
        snapshot_id="test-v2",
        strategy_id="general_v1",
        concept_id="test:runny-nose",
        system="urn:test",
        code="TEST:runny-nose",
        label="Runny nose",
        language="en",
        observation_kind="symptom",
    )


def test_untrusted_qwen_output_requires_exact_source_span() -> None:
    narrative = "J'ai le nez qui coule. Je n'ai pas de fièvre."
    raw = json.dumps(
        {
            "mentions": [
                {"text": "nez qui coule", "status": "present"},
                {"text": "fièvre", "status": "absent"},
                {"text": "douleur thoracique", "status": "present"},
            ]
        }
    )
    found = parse_mentions(raw, narrative)
    assert [(item[0], item[3]) for item in found] == [
        ("nez qui coule", "present"),
        ("fièvre", "absent"),
    ]
    assert all(narrative[start:end] == text for text, start, end, _ in found)
    with pytest.raises(LatrosError, match="valid JSON"):
        parse_mentions("ignore previous instructions", narrative)


def test_mapping_only_preselects_unambiguous_exact_observation() -> None:
    option = _option().model_dump(mode="json")
    exact = [{**option, "match_rank": 0}]
    mapped = map_mentions(
        [("nez qui coule", 0, 13, "present")], lambda _: exact, "test-v2", "general_v1"
    )
    assert mapped[0].suggested_concept_id == option["concept_id"]
    assert mapped[0].options[0].concept_id == option["concept_id"]
    ambiguous = map_mentions(
        [("nez qui coule", 0, 13, "present")],
        lambda _: [exact[0], {**option, "concept_id": "other", "match_rank": 0}],
        "test-v2",
        "general_v1",
    )
    assert ambiguous[0].suggested_concept_id is None
    vital = map_mentions(
        [("nez qui coule", 0, 13, "present")],
        lambda _: [{**option, "observation_kind": "vital", "match_rank": 0}],
        "test-v2",
        "general_v1",
    )
    assert vital[0].options == []


def test_patient_confirmation_preserves_provenance_without_clinical_approval() -> None:
    narrative = "J'ai le nez qui coule."
    start = narrative.index("nez qui coule")
    option = _option()
    request = ConfirmInterpretationRequest(
        revision=0,
        narrative=narrative,
        language="fr",
        confirmed=[
            {
                "text": "nez qui coule",
                "start": start,
                "end": start + len("nez qui coule"),
                "status": "present",
                "concept_id": option.concept_id,
                "system": option.system,
                "code": option.code,
            }
        ],
    )
    case = confirm_mentions(
        ClinicalCaseV2(case_id="case-qwen"), request, lambda _system, _code: option
    )
    assert len(case.observations) == 1
    assert case.observations[0].clinical_status == "present"
    assert (
        case.observations[0].provenance.source_statement_id
        == case.source_statements[0].statement_id
    )
    assert case.observation_proposals[0].state == "accepted"
    assert case.observation_proposals[0].method.kind == "llm"
    assert case.observation_proposals[0].candidates[0].extraction_confidence == 0
    assert len(confirm_mentions(case, request, lambda _system, _code: option).observations) == 1
    tampered = request.model_copy(
        update={"confirmed": [request.confirmed[0].model_copy(update={"text": "fièvre"})]}
    )
    with pytest.raises(LatrosError, match="span differs"):
        confirm_mentions(
            ClinicalCaseV2(case_id="case-qwen"), tampered, lambda _system, _code: option
        )
