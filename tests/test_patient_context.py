"""Local identity never becomes a scientific case field or run input."""

from pathlib import Path

from fastapi.testclient import TestClient

from latros.clinical.v2 import ClinicalCaseV2
from latros.ui.patient_context import PatientContext, project_age
from latros.ui.server import create_app


def _context() -> dict:
    return {
        "context_version": 1,
        "demographics": {"first_name": "Pat", "last_name": "Local", "age_years": 34},
        "allergies": [{"label": "Reported pollen"}],
        "known_conditions": [{"label": "Reported background"}],
        "medications": [{"label": "Reported treatment"}],
        "relevant_history": [],
    }


def test_patient_context_projects_only_age_and_preserves_self_reported_status() -> None:
    context = PatientContext.model_validate(_context())
    case = project_age(ClinicalCaseV2(case_id="case-test"), context)
    encoded = case.model_dump_json()
    assert case.subject_context.age is not None
    assert case.subject_context.age.value == 34
    assert "Pat" not in encoded and "pollen" not in encoded
    assert context.allergies[0].evaluation_status == "captured_not_evaluated"


def test_patient_first_endpoint_is_local_revisioned_and_backward_compatible(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        session = client.post("/internal/v1/sessions", json={"display_name": "local"}).json()
        sid = session["session_id"]
        assert session["patient_context"] is None
        response = client.put(
            f"/internal/v1/sessions/{sid}/patient-context",
            json={"revision": 0, "patient_context": _context()},
        )
        assert response.status_code == 200, response.text
        saved = response.json()
        assert saved["revision"] == 1
        assert saved["clinical_case"]["subject_context"]["age"]["value"] == 34
        assert "Pat" not in str(saved["clinical_case"])
        assert client.get("/internal/v1/sessions").status_code == 200
        assert (
            client.put(
                f"/internal/v1/sessions/{sid}/patient-context",
                json={"revision": 0, "patient_context": _context()},
            ).status_code
            == 409
        )


def test_patient_context_rejects_empty_identity_or_invalid_age() -> None:
    for first, age in ((" ", 34), ("Pat", -1), ("Pat", "34")):
        payload = _context()
        payload["demographics"]["first_name"] = first
        payload["demographics"]["age_years"] = age
        try:
            PatientContext.model_validate(payload)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid local patient context was accepted")
