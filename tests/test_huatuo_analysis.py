"""Local independent-model transport tests; all cases are invented fixtures."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_ui_server import _create_session, _general_case, _select

from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError
from latros.knowledge.store_v2 import build_snapshot_v2
from latros.ui.huatuo_analysis import (
    case_digest,
    huatuo_messages,
    independent_case_payload,
    parse_huatuo_output,
)
from latros.ui.models import ResearchSession, SessionRunReference
from latros.ui.patient_context import PatientContext, PatientDemographics
from latros.ui.server import _case_with_question_answer, create_app

SYNTHETIC_OUTPUT = json.dumps(
    {
        "hypotheses": [
            {
                "name": "Invented possibility",
                "reason": "Invented symptom was reported.",
                "uncertainty": "The rest of the invented case is unknown.",
            }
        ],
        "uncertainties": ["No independent confirmation"],
        "limitations": "Experimental model output; not a diagnosis.",
    }
)


def test_allowlisted_prompt_contains_complete_case_but_no_latros_result() -> None:
    case = _case_with_question_answer(
        ClinicalCaseV2(case_id="invented-case"),
        "result_verification_v1:invented",
        {
            "concept_id": "test:finding-1",
            "system": "urn:latros:test-terminology",
            "code": "TEST:finding-1",
            "label": "Invented symptom",
            "observation_kind": "symptom",
        },
        "absent",
    )
    session = ResearchSession(
        session_id="session-invented",
        display_name="Invented session",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        revision=5,
        clinical_case=case,
        patient_context=PatientContext(
            demographics=PatientDemographics(first_name="Pat", last_name="Local", age_years=30),
            symptom_narrative="I have an invented symptom.",
        ),
        latest_diagnose=SessionRunReference(
            run_id="secret-latros-run-id",
            operation="diagnose",
            created_at=datetime.now(UTC),
            receipt_id="secret-latros-receipt",
        ),
    )
    payload = independent_case_payload(session)
    assert set(payload) == {"patient_context", "clinical_case", "refinement_answers"}
    assert payload["patient_context"]["demographics"]["first_name"] == "Pat"
    assert payload["patient_context"]["symptom_narrative"] == "I have an invented symptom."
    assert payload["clinical_case"]["question_history"][0]["clinical_status"] == "absent"
    messages = huatuo_messages(payload, "fr")
    user = json.loads(messages[1]["content"])
    assert set(user) == {"output_language", "patient_case"}
    assert user["patient_case"] == payload
    assert "secret-latros-run-id" not in messages[1]["content"]
    assert "secret-latros-receipt" not in messages[1]["content"]
    assert "candidates" not in messages[1]["content"]
    assert case_digest(payload) == case_digest(independent_case_payload(session))


def test_malformed_or_probabilistic_model_text_is_refused() -> None:
    assert parse_huatuo_output(SYNTHETIC_OUTPUT).hypotheses[0].name == "Invented possibility"
    for raw in ("not JSON", '{"hypotheses": []}', SYNTHETIC_OUTPUT.replace("Invented", "87%")):
        with pytest.raises(LatrosError):
            parse_huatuo_output(raw)


def test_huatuo_requires_explicit_click_and_stale_case_is_flagged(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    application = create_app(root)
    captured: list[dict[str, str]] = []

    async def fake_model(model: str, messages: list[dict[str, str]]) -> str:
        assert model == "huatuo"
        captured.extend(messages)
        return SYNTHETIC_OUTPUT

    application.state.local_llm.complete = fake_model
    with TestClient(application) as client:
        session = _select(client, _create_session(client), "test-v2", "general_v1")
        path = f"/internal/v1/sessions/{session['session_id']}"
        first = client.get(path + "/local-ai/huatuo/latest")
        assert first.status_code == 200 and first.json()["analysis"] is None
        assert captured == []
        patient = {
            "demographics": {"first_name": "Pat", "last_name": "Local", "age_years": 30},
            "symptom_narrative": "Invented symptom history.",
            "allergies": [{"label": "Invented allergy"}],
        }
        session = client.put(
            path + "/patient-context",
            json={"revision": session["revision"], "patient_context": patient},
        ).json()
        no_result = client.post(path + "/local-ai/huatuo", json={"revision": session["revision"]})
        assert no_result.status_code == 400
        assert captured == []
        case = _general_case(session["clinical_case"]["case_id"])
        session = client.put(
            path + "/case", json={"revision": session["revision"], "clinical_case": case}
        ).json()
        first_run = client.post(
            path + "/analyses?view=summary", json={"revision": session["revision"]}
        )
        assert first_run.status_code == 200, first_run.text
        session = first_run.json()["session"]
        assert captured == []
        response = client.post(
            path + "/local-ai/huatuo",
            json={"revision": session["revision"], "language": "fr"},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["analysis"]["output"]["hypotheses"][0]["name"] == "Invented possibility"
        assert result["analysis"]["safety_status"] == "not_evaluated"
        assert result["analysis"]["clinical_validation"] is False
        assert "input_case" not in result["analysis"]
        assert "raw_model_response" not in result["analysis"]
        assert (
            json.loads(captured[1]["content"])["patient_case"]["patient_context"]["allergies"][0][
                "label"
            ]
            == "Invented allergy"
        )
        stored = application.state.sessions.latest_ai_analysis(session["session_id"])
        assert stored is not None and stored.input_case["clinical_case"] == session["clinical_case"]
        changed = client.put(
            path + "/patient-context",
            json={
                "revision": result["session"]["revision"],
                "patient_context": {**patient, "symptom_narrative": "Changed invented history."},
            },
        )
        assert changed.status_code == 200, changed.text
        latest = client.get(path + "/local-ai/huatuo/latest").json()
        assert latest["stale"] is True
        assert latest["analysis"]["analysis_id"] == result["analysis"]["analysis_id"]
        assert len(captured) == 2  # No automatic rerun after the case changes.
