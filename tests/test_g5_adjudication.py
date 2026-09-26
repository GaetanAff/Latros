"""Synthetic software reviewers only; real G5 data remains decision-free."""

import csv
import hashlib
import io
import json
import socket
from pathlib import Path

import orjson
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from latros.common import LatrosError
from latros.review.adjudication import (
    AdjudicationStore,
    HumanDecisionInput,
    agreement,
    create_adjudication_app,
)
from latros.review.g07 import SNAPSHOT, SNAPSHOT_SHA256, DecisionInput, ReviewStore
from latros.review.sampling import control_sample


def fixture(root: Path) -> tuple[Path, dict[str, tuple[str, str]], str]:
    target = root / "data/staging/g5-test"
    target.mkdir(parents=True)
    expected = {}
    for dataset in ("g1", "g2_medline", "g2_upstream", "g4"):
        rows = [
            {
                "candidate_assertion_id": f"TEST-{i}",
                "topic_id": str(i),
                "topic_title": f"Synthetic disease {i}",
                "candidate_disease_code": "TEST:DISEASE",
                "disease_label": "Synthetic disease",
                "finding_label": "Synthetic sign",
                "auto_filter_decision": status,
                "auto_filter_rule": "modifier" if i else "context",
                "domains": "TEST",
                "subject_mapping_status": "resolved",
                "medlineplus_only": "true",
                "occurrence_count": "2",
                "source_context": f"Synthetic context {i}",
                "human_decision": "",
            }
            for i, status in enumerate(
                ("needs_human_review", "reject_from_auto_extraction", "auto_keep")
            )
        ]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        data = stream.getvalue().encode()
        filename = f"{dataset}.csv"
        (target / filename).write_bytes(data)
        expected[dataset] = (filename, hashlib.sha256(data).hexdigest())
    samples = orjson.dumps({"rejected_control": ["TEST-1"], "retained_control": ["TEST-2"]}) + b"\n"
    (target / "control-samples.json").write_bytes(samples)
    sample_hash = hashlib.sha256(samples).hexdigest()
    (target / "summary.json").write_text(
        json.dumps(
            {
                "snapshot": SNAPSHOT,
                "snapshot_sha256": SNAPSHOT_SHA256,
                "files_sha256": {f: h for f, h in expected.values()},
                "sampling_sha256": sample_hash,
            }
        )
    )
    return target, expected, sample_hash


def store(root: Path) -> AdjudicationStore:
    target, expected, sample_hash = fixture(root)
    return AdjudicationStore(
        root, target, expected_exports=expected, expected_samples_sha256=sample_hash
    )


def decision(
    item: dict,
    reviewer: str,
    final: str = "reject",
    category: str = "wrong_semantic_role",
    **extra: object,
) -> HumanDecisionInput:
    return HumanDecisionInput.model_validate(
        {
            "dataset": item["dataset"],
            "index": item["index"],
            "row_id": item["row_id"],
            "stage": "review",
            "category": category,
            "final_decision": final,
            "reviewer_name": "Synthetic Software Reviewer",
            "reviewer_id": reviewer,
            "attests_identity": True,
            **extra,
        }
    )


@pytest.mark.parametrize(
    "missing", ["category", "final_decision", "reviewer_id", "attests_identity"]
)
def test_g5_no_decision_or_identity_default(tmp_path: Path, missing: str) -> None:
    s = store(tmp_path)
    item = s.item("g4", 0)
    data = decision(item, "TEST-A").model_dump()
    data.pop(missing)
    with pytest.raises(ValidationError):
        HumanDecisionInput.model_validate(data)
    assert not s.audit_path.exists()


def test_independent_reviews_and_disagreement_survive_resume(tmp_path: Path) -> None:
    s = store(tmp_path)
    item = s.item("g4", 0)
    first = s.record_human(decision(item, "TEST-A", "approve", "correct_clinical_manifestation"))
    assert s.human_item("g4", 0, "TEST-B", "review")["history"] == []
    second = s.record_human(decision(item, "TEST-B"))
    assert second["previous_hash"] == first["event_hash"]
    events = s.item("g4", 0)["history"]
    assert agreement(events)["disagreement"]
    assert len(s.human_item("g4", 0, "TEST-A", "review")["history"]) == 1
    resumed = AdjudicationStore(
        tmp_path,
        s.exports_dir,
        expected_exports=s.expected_exports,
        expected_samples_sha256=s.samples_hash,
    )
    assert resumed.item("g4", 0)["history"] == events
    assert resumed.export_kind("disagreements") == resumed.export_kind("disagreements")
    assert len(json.loads(resumed.export_kind("individual_decisions"))["events"]) == 2


def test_separate_adjudication_and_stale_basis(tmp_path: Path) -> None:
    s = store(tmp_path)
    item = s.item("g4", 0)
    s.record_human(decision(item, "TEST-A", "approve", "correct_clinical_manifestation"))
    s.record_human(decision(item, "TEST-B"))
    basis = s.human_item("g4", 0, "TEST-C", "adjudication")["basis_event_hashes"]
    with pytest.raises(LatrosError, match="distinct"):
        s.record_human(
            decision(
                item,
                "TEST-A",
                stage="adjudication",
                basis_event_hashes=basis,
                comment="Synthetic adjudication",
            )
        )
    with pytest.raises(LatrosError, match="hashes"):
        s.record_human(
            decision(
                item,
                "TEST-C",
                stage="adjudication",
                basis_event_hashes=[],
                comment="Synthetic adjudication",
            )
        )
    s.record_human(
        decision(
            item,
            "TEST-C",
            stage="adjudication",
            basis_event_hashes=basis,
            comment="Synthetic adjudication only",
        )
    )
    assert agreement(s.item("g4", 0)["history"])["adjudicated"]
    s.record_human(decision(item, "TEST-B", "defer", "ambiguous"))
    state = agreement(s.item("g4", 0)["history"])
    assert not state["adjudicated"] and state["deferred"] and state["unresolved"]
    assert len(json.loads(s.export_kind("adjudications"))["events"]) == 1


def test_agreement_never_promotes_snapshot_and_audit_is_append_only(tmp_path: Path) -> None:
    s = store(tmp_path)
    item = s.item("g4", 2)
    sentinel = tmp_path / "snapshot.json"
    sentinel.write_bytes(b"immutable")
    for reviewer in ("TEST-A", "TEST-B"):
        s.record_human(decision(item, reviewer, "approve", "correct_clinical_manifestation"))
    assert agreement(s.item("g4", 2)["history"])["agreement"]
    assert sentinel.read_bytes() == b"immutable"
    for kind in (
        "individual_decisions",
        "disagreements",
        "adjudications",
        "retained_control",
        "rejected_control",
        "summary",
    ):
        data = s.export_kind(kind)
        assert data == s.export_kind(kind)
        payload = json.loads(data)
        assert (
            not payload["clinical_validation"]
            and not payload["publishable"]
            and not payload["applies_to_snapshot"]
        )
        assert payload["research_unreviewed"] and payload["safety_status"] == "not_evaluated"
    assert len(s.audit_path.read_bytes().splitlines()) == 2
    s.audit_path.write_bytes(
        s.audit_path.read_bytes().replace(b"correct_clinical_manifestation", b"wrong_semantic_role")
    )
    with pytest.raises(LatrosError, match="chain"):
        s.export_kind("summary")


def test_g4_queue_filters_and_source_context_are_associated(tmp_path: Path) -> None:
    s = store(tmp_path)
    assert s.queue("g4", {"auto_filter_decision": "needs_human_review"})["indices"] == [0]
    assert s.queue(
        "g4", {"sample": "rejected_control", "domains": "TEST", "multiple_occurrences": "true"}
    )["indices"] == [1]
    assert s.queue(
        "g4",
        {
            "source_context": "context 2",
            "subject_mapping_status": "resolved",
            "medlineplus_only": "true",
        },
    )["indices"] == [2]
    assert s.item("g4", 2)["row"]["source_context"] == "Synthetic context 2"
    assert s.queue("g4", {})["progress"]["reviewed"] == 0


def test_samples_stratify_each_rejection_rule_and_are_order_independent() -> None:
    rows = [
        {
            "candidate_assertion_id": f"TEST-{rule}-{i}",
            "topic_id": str(i),
            "auto_filter_decision": status,
            "auto_filter_rule": rule,
            "domains": f"domain-{i % 3}",
        }
        for status in ("reject_from_auto_extraction", "auto_keep")
        for rule in ("generic", "temporal", "laterality", "self-reference")
        for i in range(70)
    ]
    rejected = control_sample(rows, "reject_from_auto_extraction")
    assert len(set(rejected)) == 180
    assert rejected == control_sample(list(reversed(rows)), "reject_from_auto_extraction")
    for rule in ("generic", "temporal", "laterality", "self-reference"):
        assert sum(value.startswith(f"TEST-{rule}-") for value in rejected) == 45
    assert len(control_sample(rows, "auto_keep")) == 180


def test_legacy_chain_stays_readable_without_becoming_double_review(tmp_path: Path) -> None:
    target, expected, sample_hash = fixture(tmp_path)
    legacy = ReviewStore(tmp_path, target, expected_exports=expected)
    item = legacy.item("g1", 0)
    legacy.record(
        DecisionInput.model_validate(
            {
                "dataset": "g1",
                "index": 0,
                "row_id": item["row_id"],
                "action": "reject",
                "reviewer_name": "Synthetic Legacy Reviewer",
                "reviewer_id": "TEST-OLD",
                "attests_identity": True,
            }
        )
    )
    s = AdjudicationStore(
        tmp_path, target, expected_exports=expected, expected_samples_sha256=sample_hash
    )
    assert len(json.loads(s.export_kind("individual_decisions"))["events"]) == 1
    assert not agreement(s.item("g1", 0)["history"])["reviewed"]


def test_g5_http_offline_explicit_taxonomy_and_rejects_stale_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_connect = socket.socket.connect

    def blocked(sock: socket.socket, address: object) -> None:
        # Windows asyncio creates a loopback socket pair even for in-process HTTP.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        raise AssertionError("Network forbidden")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    target, expected, sample_hash = fixture(tmp_path)
    client = TestClient(
        create_adjudication_app(
            tmp_path, target, expected_exports=expected, expected_samples_sha256=sample_hash
        )
    )
    assert "Aucun choix n’est présélectionné" in client.get("/").text
    assert "https://" not in client.get("/").text
    assert client.get("/assets/adjudication.js").status_code == 200
    item = client.get("/api/v2/item", params={"dataset": "g4", "index": 0}).json()
    token = client.get("/api/v2/token").json()["token"]
    data = decision(item, "TEST-A").model_dump(mode="json")
    assert client.post("/api/v2/decision", json=data).status_code == 400
    headers = {"X-Latros-Review-Token": token}
    assert (
        client.post("/api/v2/decision", json={**data, "category": ""}, headers=headers).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v2/decision", json={**data, "row_id": "0" * 64}, headers=headers
        ).status_code
        == 400
    )
    assert client.post("/api/v2/decision", json=data, headers=headers).status_code == 200
    assert client.get("/api/v2/queue").json()["progress"]["reviewed"] == 1
    assert client.get("/api/v2/export/individual_decisions", headers=headers).status_code == 200
