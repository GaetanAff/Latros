"""The small UI transport must not alter complete, immutable diagnosis runs."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from latros.common import LatrosError
from latros.ui.models import SessionSelection
from latros.ui.server import create_app
from latros.ui.sessions import SessionStore


def _stored_diagnosis(root: Path, count: int = 25) -> tuple[SessionStore, str, str, dict]:
    store = SessionStore(root)
    session = store.create("Transport test")
    session = store.update(
        session.session_id,
        session.revision,
        lambda current: current.model_copy(
            update={
                "selection": SessionSelection(
                    snapshot_id="test-v2",
                    strategy_id="general_v1",
                    profile_id="general_v1",
                    profile_sha256="0" * 64,
                )
            }
        ),
    )
    result = {
        "case_id": session.clinical_case.case_id,
        "status": "ranked" if count else "abstained",
        "scope_status": "partial",
        "coverage": {"supported": 1},
        "abstention": None if count else {"reason": "insufficient_snapshot_coverage"},
        "research_unreviewed": True,
        "safety": {"status": "not_evaluated"},
        "run_receipt": {"receipt_id": "receipt:test", "mappings_applied": ["mapping:test"]},
        "candidates": [
            {
                "candidate_id": f"test:condition-{index}",
                "label": f"Condition {index}",
                "rank": index,
                "aggregate": {"value": 0.5},
                "favorable": [{"observation": "observation-1", "provenance": ["source:a"]}],
                "unfavorable": [],
                "unknown": [{"assertion": "assertion:a"}],
                "source_views": [{"source_release_id": "monarch:test"}],
                "terminology_mappings": ["mapping:test"],
                "frequency_conflicts": [],
            }
            for index in range(1, count + 1)
        ],
    }
    _, run = store.record_run(session.session_id, session.revision, "diagnose", result)
    return store, session.session_id, run.run_id, result


def test_indexed_run_summary_and_lazy_detail_are_exact(tmp_path: Path) -> None:
    store, session_id, run_id, original = _stored_diagnosis(tmp_path)
    resumed = SessionStore(tmp_path)
    summary = resumed.load_run_summary(session_id, run_id)
    assert summary["result"]["candidate_count"] == 25
    assert len(summary["result"]["candidates"]) == 20
    assert "provenance" not in summary["result"]["candidates"][0]["favorable"][0]
    assert summary["result"]["research_unreviewed"] is True
    assert summary["result"]["safety"]["status"] == "not_evaluated"
    detail = resumed.load_candidate_detail(session_id, run_id, "test:condition-25")
    assert detail["candidate"] == original["candidates"][24]
    assert detail["run_receipt"] == original["run_receipt"]
    assert resumed.load_run(session_id, run_id).result == original


def test_result_transport_http_missing_run_candidate_and_abstention(tmp_path: Path) -> None:
    store, session_id, run_id, original = _stored_diagnosis(tmp_path, count=0)
    app = create_app(tmp_path)
    app.state.sessions = store
    client = TestClient(app)
    base = f"/internal/v1/sessions/{session_id}/runs/{run_id}"
    summary = client.get(f"{base}/summary")
    assert summary.status_code == 200
    assert summary.json()["result"]["status"] == "abstained"
    assert summary.json()["result"]["candidates"] == []
    assert client.get(base).json()["result"] == original
    assert client.get(f"{base}/candidates/test:missing").status_code == 400
    assert client.get(f"{base}-missing/summary").status_code == 400


def test_historic_run_without_index_remains_available(tmp_path: Path) -> None:
    store, session_id, run_id, original = _stored_diagnosis(tmp_path)
    index = store._run_path(session_id, run_id).with_suffix(".index.json")
    index.unlink()
    assert store.load_run_summary(session_id, run_id)["result"]["candidate_count"] == 25
    assert (
        store.load_candidate_detail(session_id, run_id, "test:condition-1")["candidate"]
        == (original["candidates"][0])
    )


def test_transport_index_refuses_modified_immutable_run(tmp_path: Path) -> None:
    store, session_id, run_id, _ = _stored_diagnosis(tmp_path)
    path = store._run_path(session_id, run_id)
    path.write_bytes(path.read_bytes().replace(b"Condition 1", b"Condition X"))
    with pytest.raises(LatrosError, match="integrity"):
        store.load_run_summary(session_id, run_id)
