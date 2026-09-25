"""Synthetic, offline review UI tests; no actual clinical decision is made."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from latros.common import LatrosError
from latros.review.g07 import (
    SNAPSHOT,
    SNAPSHOT_SHA256,
    DecisionInput,
    ReviewStore,
    create_review_app,
)


def _fixture(root: Path) -> tuple[Path, dict[str, tuple[str, str]]]:
    exports = root / "data/staging/v0.7-g"
    exports.mkdir(parents=True)
    sets = {
        "g1": (
            "g1-mapping-review.csv",
            [
                {
                    "topic_id": "1",
                    "topic_title": "Invented topic",
                    "candidate_disease_code": "",
                    "human_mapping_decision": "",
                },
                {
                    "topic_id": "2",
                    "topic_title": "Invented condition",
                    "candidate_disease_code": "TEST:1",
                    "human_mapping_decision": "",
                },
            ],
        ),
        "g2_medline": (
            "g2-medline-assertion-review.csv",
            [
                {
                    "candidate_assertion_id": "test:assertion",
                    "finding_label": "Invented sign",
                    "human_assertion_decision": "",
                }
            ],
        ),
        "g2_upstream": (
            "g2-upstream-dependency-review.csv",
            [
                {
                    "source_assertion_id": "test:source",
                    "dependency_type": "derived_from",
                    "human_provenance_decision": "",
                }
            ],
        ),
    }
    expected = {}
    for dataset, (filename, rows) in sets.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        content = stream.getvalue().encode()
        (exports / filename).write_bytes(content)
        expected[dataset] = (filename, hashlib.sha256(content).hexdigest())
    (exports / "summary.json").write_text(
        json.dumps(
            {
                "snapshot": SNAPSHOT,
                "snapshot_sha256": SNAPSHOT_SHA256,
                "files_sha256": {filename: digest for filename, digest in expected.values()},
            }
        ),
        encoding="utf-8",
    )
    return exports, expected


def _decision(item: dict, *, action: str = "reject") -> dict:
    return {
        "dataset": item["dataset"],
        "index": item["index"],
        "row_id": item["row_id"],
        "action": action,
        "reviewer_name": "Synthetic Test Reviewer",
        "reviewer_id": "TEST-REVIEWER-1",
        "attests_identity": True,
        "comment": "Only a synthetic software test",
    }


def test_review_ui_requires_real_identity_and_preserves_append_only_history(tmp_path: Path) -> None:
    exports, expected = _fixture(tmp_path)
    client = TestClient(create_review_app(tmp_path, exports, expected_exports=expected))
    home = client.get("/")
    assert home.status_code == 200
    assert "Aucun choix n’est présélectionné" in home.text
    assert "https://" not in home.text
    assert "script-src 'self'" in home.headers["content-security-policy"]
    assert client.get("/assets/review.js").status_code == 200
    assert client.get("/logo.svg").status_code == 200
    css = client.get("/assets/review.css").text
    assert all(color in css for color in ("#0f6472", "#6ea07a", "#b7cfaf"))
    token = client.get("/api/token").json()["token"]
    item = client.get("/api/item", params={"dataset": "g1", "index": 0}).json()
    assert item["history"] == []
    assert client.get("/api/metadata").json()["datasets"]["g1"]["decided"] == 0
    assert client.post("/api/decision", json=_decision(item)).status_code == 400
    headers = {"X-Latros-Review-Token": token}
    assert (
        client.post(
            "/api/decision",
            json=_decision(item),
            headers={**headers, "Origin": "https://not-local.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/decision",
            json=_decision(item, action="approve_exact"),
            headers=headers,
        ).status_code
        == 400
    )  # No candidate disease was proposed.
    assert (
        client.post(
            "/api/decision",
            json={**_decision(item), "reviewer_id": " "},
            headers=headers,
        ).status_code
        == 422
    )
    first = client.post("/api/decision", json=_decision(item), headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["timestamp_utc"]
    assert first.json()["event_hash"]
    second = client.post(
        "/api/decision",
        json=_decision(item, action="ambiguous"),
        headers=headers,
    )
    assert second.status_code == 200, second.text
    history = client.get("/api/item", params={"dataset": "g1", "index": 0}).json()["history"]
    assert [event["action"] for event in history] == ["reject", "ambiguous"]
    assert history[1]["previous_hash"] == history[0]["event_hash"]
    assert client.get("/api/metadata").json()["datasets"]["g1"]["decided"] == 1
    assert client.get("/api/export").status_code == 400
    first_export = client.get("/api/export", headers=headers).content
    assert first_export == client.get("/api/export", headers=headers).content
    exported = json.loads(first_export)
    assert exported["current_decisions"][0]["action"] == "ambiguous"
    assert exported["clinical_validation"] is False
    assert exported["publishable"] is False
    assert exported["applies_to_snapshot"] is False
    assert len(exports.joinpath("review-events.jsonl").read_text().splitlines()) == 2


def test_review_ui_approvals_are_only_local_decisions(tmp_path: Path) -> None:
    exports, expected = _fixture(tmp_path)
    client = TestClient(create_review_app(tmp_path, exports, expected_exports=expected))
    headers = {"X-Latros-Review-Token": client.get("/api/token").json()["token"]}
    mapping = client.get("/api/item", params={"dataset": "g1", "index": 1}).json()
    assert (
        client.post(
            "/api/decision",
            json=_decision(mapping, action="approve_exact"),
            headers=headers,
        ).status_code
        == 200
    )
    assertion = client.get("/api/item", params={"dataset": "g2_medline", "index": 0}).json()
    assert (
        client.post(
            "/api/decision",
            json=_decision(assertion, action="approve_for_review"),
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/decision",
            json=_decision(assertion, action="approve_equivalent"),
            headers=headers,
        ).status_code
        == 400
    )
    assert (
        expected["g1"][1]
        == hashlib.sha256((exports / "g1-mapping-review.csv").read_bytes()).hexdigest()
    )
    assert (
        json.loads(client.get("/api/export", headers=headers).content)["applies_to_snapshot"]
        is False
    )


def test_review_ui_rejects_changed_exports_and_tampered_audit(tmp_path: Path) -> None:
    exports, expected = _fixture(tmp_path)
    store = ReviewStore(tmp_path, exports, expected_exports=expected)
    item = store.item("g1", 0)
    store.record(DecisionInput.model_validate(_decision(item)))
    log = exports / "review-events.jsonl"
    log.write_bytes(log.read_bytes().replace(b"reject", b"accept"))
    with pytest.raises(LatrosError, match="audit chain"):
        ReviewStore(tmp_path, exports, expected_exports=expected)
    log.unlink()
    csv_path = exports / "g1-mapping-review.csv"
    csv_path.write_bytes(csv_path.read_bytes() + b"modified")
    with pytest.raises(LatrosError, match="hash mismatch"):
        ReviewStore(tmp_path, exports, expected_exports=expected)


def test_review_ui_rejects_exports_outside_staging(tmp_path: Path) -> None:
    with pytest.raises(LatrosError, match="under data/staging"):
        ReviewStore(tmp_path, tmp_path)


def test_review_ui_refuses_export_changed_during_session(tmp_path: Path) -> None:
    exports, expected = _fixture(tmp_path)
    store = ReviewStore(tmp_path, exports, expected_exports=expected)
    item = store.item("g1", 1)
    path = exports / "g1-mapping-review.csv"
    path.write_bytes(path.read_bytes() + b"altered")
    with pytest.raises(LatrosError, match="changed after startup"):
        store.record(DecisionInput.model_validate(_decision(item, action="approve_exact")))
    assert not (exports / "review-events.jsonl").exists()
