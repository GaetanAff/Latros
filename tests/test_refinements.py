"""Optional structured symptom context, not a new clinical question policy."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError
from latros.ui.refinements import RefinementAnswer, apply_refinement, refinement_definitions
from latros.ui.server import create_app


def _case() -> ClinicalCaseV2:
    return ClinicalCaseV2.model_validate(
        {
            "case_id": "case-test",
            "observations": [
                {
                    "kind": "symptom",
                    "observation_id": "observation-headache",
                    "concept": {
                        "concept_id": "test:headache",
                        "coding": {
                            "system": "http://purl.obolibrary.org/obo/hp.owl",
                            "code": "HP:0002315",
                            "display": "Headache",
                        },
                    },
                    "clinical_status": "present",
                    "evaluation_status": "assessed",
                    "acquisition_method": "reported",
                    "provenance": {
                        "provenance_id": "provenance-1",
                        "origin_type": "patient_report",
                    },
                }
            ],
        }
    )


def test_refinement_is_not_a_medical_rule_and_preserves_canonical_identity() -> None:
    original = _case()
    definition = refinement_definitions(original)[0]
    assert definition.review_status == "engineering_definition_not_clinically_validated"
    assert definition.reasoning_use == "not_used_by_current_strategies"
    assert definition.question_types == [
        "duration",
        "reported_severity",
        "reported_laterality",
    ]
    answer = RefinementAnswer(
        observation_id="observation-headache",
        concept_id="test:headache",
        duration_value=3,
        duration_unit="day",
        reported_severity="moderate",
    )
    result = apply_refinement(original, answer)
    assert result.observations[0].observation_id == original.observations[0].observation_id
    assert result.observations[0].concept == original.observations[0].concept
    assert result.observations[0].temporal.duration == "P3D"
    assert result.observations[0].severity is None
    assert original.observations[0].temporal is None


def test_refinement_rejects_stale_or_unresolved_observation() -> None:
    with pytest.raises(LatrosError):
        apply_refinement(
            _case(), RefinementAnswer(observation_id="missing", concept_id="test:headache")
        )
    with pytest.raises(ValueError):
        RefinementAnswer(
            observation_id="observation-headache",
            concept_id="test:headache",
            duration_value=3,
        )


def test_refinement_only_offers_contextual_fields() -> None:
    case = _case().model_dump(mode="json")
    case["observations"][0]["concept"]["coding"]["code"] = "HP:0012735"
    cough = ClinicalCaseV2.model_validate(case)
    definition = refinement_definitions(cough)[0]
    assert definition.question_types == ["duration"]
    assert definition.laterality_options == []
    assert definition.severity_options == []
    with pytest.raises(LatrosError, match="not offered"):
        apply_refinement(
            cough,
            RefinementAnswer(
                observation_id="observation-headache",
                concept_id="test:headache",
                reported_laterality="left",
            ),
        )
    case["observations"][0]["concept"]["coding"]["code"] = "HP:0000123"
    assert refinement_definitions(ClinicalCaseV2.model_validate(case)) == []


def test_refinement_http_requires_current_case_and_revision(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        session = client.post("/internal/v1/sessions", json={"display_name": "local"}).json()
        sid = session["session_id"]
        response = client.put(
            f"/internal/v1/sessions/{sid}/case",
            json={"revision": 0, "clinical_case": _case().model_dump(mode="json")},
        )
        assert response.status_code == 200, response.text
        definitions = client.get(f"/internal/v1/sessions/{sid}/refinements").json()
        assert len(definitions["items"]) == 1
        assert definitions["answers"] == []
        answer = {
            "observation_id": "observation-headache",
            "concept_id": "test:headache",
            "duration_value": 2,
            "duration_unit": "week",
        }
        stored = client.put(
            f"/internal/v1/sessions/{sid}/refinements", json={"revision": 1, "answer": answer}
        )
        assert stored.status_code == 200, stored.text
        assert stored.json()["clinical_case"]["observations"][0]["temporal"]["duration"] == "P2W"
        assert stored.json()["refinement_answers"][0]["reported_severity"] is None
        duplicate = client.put(
            f"/internal/v1/sessions/{sid}/refinements",
            json={"revision": stored.json()["revision"], "answer": answer},
        )
        assert duplicate.status_code == 400
        assert (
            client.put(
                f"/internal/v1/sessions/{sid}/refinements", json={"revision": 1, "answer": answer}
            ).status_code
            == 409
        )
        changed = stored.json()["clinical_case"]
        changed["observations"][0]["clinical_status"] = "absent"
        changed["observations"][0]["temporal"] = None
        updated = client.put(
            f"/internal/v1/sessions/{sid}/case",
            json={"revision": stored.json()["revision"], "clinical_case": changed},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["refinement_answers"] == []
