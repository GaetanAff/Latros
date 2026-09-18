from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from latros.cli import app
from latros.knowledge.store_v2 import build_snapshot_v2
from latros.ui.server import create_app


def _create_session(client: TestClient) -> dict:
    response = client.post("/internal/v1/sessions", json={"display_name": "Test interface locale"})
    assert response.status_code == 201
    return response.json()


def _select(client: TestClient, session: dict, snapshot: str, strategy: str) -> dict:
    response = client.put(
        f"/internal/v1/sessions/{session['session_id']}/selection",
        json={
            "revision": session["revision"],
            "snapshot_id": snapshot,
            "strategy_id": strategy,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _general_case(case_id: str) -> dict:
    observations = []
    for index, status in ((1, "present"), (2, "absent")):
        observations.append(
            {
                "kind": "symptom",
                "observation_id": f"observation-{index}",
                "concept": {
                    "concept_id": f"test:finding-{index}",
                    "coding": {
                        "system": "urn:latros:test-terminology",
                        "code": f"TEST:finding-{index}",
                    },
                },
                "clinical_status": status,
                "evaluation_status": "assessed",
                "acquisition_method": "reported",
                "provenance": {
                    "provenance_id": f"provenance-{index}",
                    "origin_type": "patient_report",
                },
            }
        )
    return {
        "schema_version": 2,
        "case_id": case_id,
        "subject_context": {
            "age": {
                "kind": "quantity",
                "value": 30,
                "comparator": "eq",
                "unit": "year",
                "system": "http://unitsofmeasure.org",
                "code": "a",
            }
        },
        "source_statements": [],
        "observation_proposals": [],
        "observations": observations,
        "question_history": [],
    }


def test_ui_shell_is_local_static_and_explicit_about_limits(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "Interface interne v0.6" in response.text
    assert "SAFETY STATUS" in response.text
    assert "DONNÉES NON REVUES" in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "https://" not in response.text
    assert client.get("/docs").status_code == 404
    script = client.get("/assets/app.js").text
    assert "research_unreviewed: true" in script
    assert "unreviewed_assertion_count" in script
    assert "unreviewed_mapping_count" in script


def test_ui_general_v1_workflow_persists_exact_v2_run(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    client = TestClient(create_app(root))
    session = _select(client, _create_session(client), "test-v2", "general_v1")
    clinical_case = _general_case(session["clinical_case"]["case_id"])
    saved = client.put(
        f"/internal/v1/sessions/{session['session_id']}/case",
        json={"revision": session["revision"], "clinical_case": clinical_case},
    ).json()

    response = client.post(
        f"/internal/v1/sessions/{session['session_id']}/analyses",
        json={"revision": saved["revision"]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    result = payload["run"]["result"]
    assert result["candidates"][0]["candidate_id"] == "test:condition-1"
    assert result["candidates"][0]["aggregate"]["kind"] == "compatibility"
    assert result["safety"]["status"] == "not_evaluated"
    assert payload["session"]["latest_diagnose"]["run_id"] == payload["run"]["run_id"]


def test_ui_semantic_v1_workflow_preserves_safety_and_scale(built) -> None:
    root, _ = built
    client = TestClient(create_app(root))
    session = _select(client, _create_session(client), "test", "semantic_v1")
    clinical_case = {
        "schema_version": 2,
        "case_id": session["clinical_case"]["case_id"],
        "subject_context": {},
        "source_statements": [],
        "observation_proposals": [],
        "observations": [
            {
                "kind": "phenotype",
                "observation_id": "semantic-observation-1",
                "concept": {
                    "concept_id": "test-hpo-sign-1",
                    "coding": {
                        "system": "http://purl.obolibrary.org/obo/hp.owl",
                        "code": "HP:9000001",
                    },
                },
                "clinical_status": "present",
                "evaluation_status": "assessed",
                "acquisition_method": "reported",
                "provenance": {
                    "provenance_id": "semantic-provenance-1",
                    "origin_type": "patient_report",
                },
            }
        ],
        "question_history": [],
    }
    saved = client.put(
        f"/internal/v1/sessions/{session['session_id']}/case",
        json={"revision": session["revision"], "clinical_case": clinical_case},
    ).json()

    response = client.post(
        f"/internal/v1/sessions/{session['session_id']}/analyses",
        json={"revision": saved["revision"]},
    )

    assert response.status_code == 200, response.text
    result = response.json()["run"]["result"]
    assert result["run_receipt"]["strategy_id"] == "semantic_v1"
    assert result["candidates"][0]["aggregate"]["scale_id"] == "semantic_v1.compatibility"
    assert result["safety"]["status"] == "not_evaluated"


def test_ui_question_answer_creates_confirmed_observation(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    client = TestClient(create_app(root))
    session = _select(client, _create_session(client), "test-v2", "general_v1")
    clinical_case = _general_case(session["clinical_case"]["case_id"])
    clinical_case["observations"] = []
    session = client.put(
        f"/internal/v1/sessions/{session['session_id']}/case",
        json={"revision": session["revision"], "clinical_case": clinical_case},
    ).json()
    question_response = client.post(
        f"/internal/v1/sessions/{session['session_id']}/questions/next",
        json={"revision": session["revision"]},
    )
    assert question_response.status_code == 200, question_response.text
    question_payload = question_response.json()

    answer_response = client.post(
        f"/internal/v1/sessions/{session['session_id']}/questions/answer",
        json={
            "revision": question_payload["session"]["revision"],
            "question_run_id": question_payload["run"]["run_id"],
            "answer": "unable_to_assess",
        },
    )

    assert answer_response.status_code == 200, answer_response.text
    clinical_case = answer_response.json()["clinical_case"]
    assert clinical_case["observations"][0]["clinical_status"] == "unknown"
    assert clinical_case["observations"][0]["evaluation_status"] == "unable_to_assess"
    assert clinical_case["question_history"][0]["uncertainty_reason"] == "unable_to_assess"


def test_ui_refuses_incompatible_pair_invalid_case_and_external_origin(built) -> None:
    root, _ = built
    client = TestClient(create_app(root))
    session = _create_session(client)

    incompatible = client.put(
        f"/internal/v1/sessions/{session['session_id']}/selection",
        json={"revision": 0, "snapshot_id": "test", "strategy_id": "general_v1"},
    )
    invalid_case = client.put(
        f"/internal/v1/sessions/{session['session_id']}/case",
        json={"revision": 0, "clinical_case": {"schema_version": 2, "case_id": ""}},
    )
    hostile_origin = client.post(
        "/internal/v1/sessions",
        json={"display_name": "Refusée"},
        headers={"origin": "https://example.test"},
    )

    assert incompatible.status_code == 400
    assert invalid_case.status_code == 422
    assert hostile_origin.status_code == 403
    assert invalid_case.json()["error"] == "invalid_request"


def test_ui_reports_missing_snapshot_runtime(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    source = Path(__file__).resolve().parents[1] / "manifests" / "v0.2.0.json"
    (manifests / "missing.json").write_bytes(source.read_bytes())
    client = TestClient(create_app(tmp_path))

    payload = client.get("/internal/v1/capabilities").json()

    assert payload["snapshots"][0]["runtime_status"] in {"missing", "corrupt"}
    assert payload["compatible_selections"] == []


def test_cli_ui_launches_with_loopback_only_contract(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[Path, int, bool]] = []

    def fake_run_ui(root: Path, port: int, *, open_browser: bool) -> None:
        calls.append((root, port, open_browser))

    monkeypatch.setattr("latros.ui.server.run_ui", fake_run_ui)

    result = CliRunner().invoke(
        app,
        ["--root", str(tmp_path), "ui", "--port", "8877", "--no-open"],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(tmp_path.resolve(), 8877, False)]
