"""Source-policy tests on explicitly invented, non-medical fixtures."""

from pathlib import Path

import orjson
import pytest
from fastapi.testclient import TestClient
from test_general_v1 import _case, _symptom
from test_ui_server import _create_session, _select

from latros.application.service import ResearchApplicationService
from latros.common import LatrosError, sha256
from latros.knowledge import consultation_repository as repository_module
from latros.knowledge.consultation_repository import ConsultationRepository
from latros.knowledge.store_v2 import build_snapshot_v2
from latros.reasoning import consultation as strategy_module
from latros.reasoning.consultation import ConsultationStrategy
from latros.reasoning.general_v1_lazy import LazyGeneralV1Strategy
from latros.reasoning.profiles import (
    ReasoningProfile,
    load_reasoning_profile,
    reasoning_profile_hash,
)
from latros.ui.server import _case_with_question_answer, create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scoped_fixture(synthetic_v2, monkeypatch):
    root, registry, knowledge = synthetic_v2
    # Deliberately unknown dependency: the historical strategy must still exclude it.
    knowledge.evidence_families[0] = knowledge.evidence_families[0].model_copy(
        update={"dependency_type": "unknown"}
    )
    knowledge.source_dependencies = [
        dep.model_copy(update={"dependency_type": "unknown"})
        for dep in knowledge.source_dependencies
    ]
    # Only symptom assertions enter this invented G4 retained artifact.
    retained = []
    for i, source in enumerate(knowledge.source_assertions):
        candidate_id = f"invented-candidate-{i}"
        source.raw_value["candidate"] = {"candidate_assertion_id": candidate_id}
        if source.relation == "has_symptom":
            retained.append(
                {
                    "candidate_assertion_id": candidate_id,
                    "review_status": "unreviewed",
                    "reviewer_ids": [],
                    "subject_mapping": {"status": "resolved", "relation": "exact"},
                    "object_mapping": {"status": "resolved", "relation": "equivalent"},
                }
            )
    artifact = root / "data/staging/v0.7-g4/quality-v2-release/candidate_assertions_v2.jsonl"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"".join(orjson.dumps(item) + b"\n" for item in retained))
    manifest = build_snapshot_v2(root, registry, "test-v2", knowledge)
    monkeypatch.setattr(repository_module, "SNAPSHOT", "test-v2")
    monkeypatch.setattr(repository_module, "CONTENT", manifest.content_sha256)
    monkeypatch.setattr(repository_module, "G4_HASH", sha256(artifact))
    monkeypatch.setattr(repository_module, "GENERAL_RELEASE", "invented-guidance:test-v2")
    parent = load_reasoning_profile(ROOT / "profiles/general_v1.json")
    monkeypatch.setattr(strategy_module, "load_reasoning_profile", lambda _: parent)
    payload = load_reasoning_profile(ROOT / "profiles/general_question_v2.json").model_dump(
        mode="json"
    )
    payload["compatible_snapshot_ids"] = ["test-v2"]
    payload["parameters"].update(
        {
            "parent_profile_id": parent.profile_id,
            "parent_profile_sha256": parent.profile_sha256,
            "snapshot_content_sha256": manifest.content_sha256,
            "g4_retained_sha256": sha256(artifact),
        }
    )
    payload["profile_sha256"] = reasoning_profile_hash(payload)
    return root, ReasoningProfile.model_validate(payload), parent, artifact


def test_single_source_is_numeric_only_in_explicit_new_policy(scoped_fixture):
    root, profile, parent, _ = scoped_fixture
    old = LazyGeneralV1Strategy(root, "test-v2", parent)
    new = ConsultationStrategy(root, "test-v2", profile)
    try:
        case = _case(_symptom(1, "present"), _symptom(2, "absent"))
        assert old.diagnose(case).abstention.reason == "insufficient_snapshot_coverage"
        assert old._aggregatable == set()
        result = new.diagnose(case)
        assert result.status == "ranked"
        assert [c.aggregate.value for c in result.candidates] == [1.0, 0.0, -1.0]
        assert len(result.run_receipt.evidence_family_ids_used) == 1
        for candidate in result.candidates:
            for contribution in candidate.favorable + candidate.unfavorable + candidate.unknown:
                assert contribution.details["aggregatable"] is False
                assert contribution.details["dependency_type"] == "unknown"
                assert contribution.details["clinical_source_count"] == 1
                assert contribution.details["g4_status"] == "retained_not_clinically_approved"
        assert result.safety.status == "not_evaluated"
        assert "EXPERIMENTAL SINGLE SOURCE" in " ".join(result.run_receipt.warnings)
    finally:
        old.close()
        new.close()


def test_source_scoped_coverage_and_empty_case_abstain(scoped_fixture):
    root, profile, _, _ = scoped_fixture
    strategy = ConsultationStrategy(root, "test-v2", profile)
    try:
        outside = strategy.diagnose(_case(_symptom(3, "present"), _symptom(4, "present")))
        assert outside.coverage.coverage_ratio == 0
        assert all(i.reason == "outside_explicit_source_scope" for i in outside.coverage.inputs)
        assert outside.abstention is not None
        assert strategy.question(_case()).question is None
        assert strategy.question(_case(_symptom(1, "present"), age=12)).question is None
    finally:
        strategy.close()


def test_no_question_repetition_across_history_and_unknown_observations(scoped_fixture):
    root, profile, _, _ = scoped_fixture
    strategy = ConsultationStrategy(root, "test-v2", profile)
    try:
        case = _case(_symptom(1, "present"))
        q = strategy.question(case).question
        assert q is not None and q.concept.code == "TEST:finding-2"
        assert q.expected_contribution["measure"] == "documentation_variation"
        assert "undocumented does not mean absent" in q.justification
        answered = _case_with_question_answer(
            case,
            q.question_id,
            {
                "concept_id": "test:finding-2",
                "system": q.concept.system,
                "code": q.concept.code,
                "label": q.concept.label,
                "observation_kind": "symptom",
            },
            "unknown",
        )
        assert strategy.question(answered).question is None
        # A preserved historical answer also blocks repetition after its observation is removed.
        answered = answered.model_copy(update={"observations": answered.observations[:1]})
        assert strategy.question(answered).question is None
        # An anatomy/search answer has no question_history but is still excluded.
        assert (
            strategy.question(_case(_symptom(1, "present"), _symptom(2, "absent"))).question is None
        )
    finally:
        strategy.close()


def test_engineering_budget_and_profile_binding_fail_closed(scoped_fixture):
    root, profile, _, _ = scoped_fixture
    strategy = ConsultationStrategy(root, "test-v2", profile)
    try:
        case = _case(_symptom(1, "present"))
        q = strategy.question(case).question
        answered = _case_with_question_answer(
            case,
            q.question_id,
            {
                "concept_id": "test:finding-2",
                "system": q.concept.system,
                "code": q.concept.code,
                "label": q.concept.label,
                "observation_kind": "symptom",
            },
            "unknown",
        )
        strategy.profile = profile.model_copy(
            update={"parameters": {**profile.parameters, "maximum_questions": 1}}
        )
        assert strategy.question(answered).stop_reason == "question_budget_reached"
    finally:
        strategy.close()
    invalid = profile.model_copy(
        update={"parameters": {**profile.parameters, "parent_profile_sha256": "0" * 64}}
    )
    with pytest.raises(LatrosError, match="profile binding"):
        ConsultationStrategy(root, "test-v2", invalid)


def test_g4_integrity_and_snapshot_read_only(scoped_fixture):
    root, profile, _, artifact = scoped_fixture
    before = sha256(root / "data/runtime/test-v2/knowledge.duckdb")
    strategy = ConsultationStrategy(root, "test-v2", profile)
    try:
        with pytest.raises(Exception, match="read-only"):
            strategy.repository.connection.execute("CREATE TABLE main.forbidden(id VARCHAR)")
        assert strategy.diagnose(_case(_symptom(1, "present"), _symptom(2, "absent")))
        assert sha256(root / "data/runtime/test-v2/knowledge.duckdb") == before
        artifact.write_bytes(b"corrupt")
        with pytest.raises(LatrosError, match="changed"):
            strategy.repository.assert_unchanged()
    finally:
        strategy.close()
    with pytest.raises(LatrosError, match="missing/corrupt"):
        ConsultationRepository(root, "test-v2", "general")
    artifact.unlink()
    with pytest.raises(LatrosError, match="missing/corrupt"):
        ConsultationRepository(root, "test-v2", "general")


def test_consultation_profiles_are_distinct_and_hash_verified():
    for name in ("general_question_v2", "rare_question_v1"):
        profile = load_reasoning_profile(ROOT / f"profiles/{name}.json")
        assert profile.strategy_id == name
        assert not profile.score_scale.calibrated
        assert profile.parameters["maximum_questions"] in {6, 12}


def test_explicit_rare_opt_in_separate_immutable_runs_and_resume(scoped_fixture, monkeypatch):
    root, general, parent, _ = scoped_fixture
    payload = load_reasoning_profile(ROOT / "profiles/rare_question_v1.json").model_dump(
        mode="json"
    )
    payload["compatible_snapshot_ids"] = ["test-v2"]
    payload["parameters"].update(
        {
            "parent_profile_id": parent.profile_id,
            "parent_profile_sha256": parent.profile_sha256,
            "snapshot_content_sha256": general.parameters["snapshot_content_sha256"],
        }
    )
    payload["profile_sha256"] = reasoning_profile_hash(payload)
    rare = ReasoningProfile.model_validate(payload)
    monkeypatch.setattr(
        ResearchApplicationService,
        "profile",
        lambda self, strategy, snapshot=None: {
            "general_question_v2": general,
            "rare_question_v1": rare,
            "general_v1": parent,
        }.get(strategy, parent),
    )
    with TestClient(create_app(root)) as client:
        session = _select(client, _create_session(client), "test-v2", "general_question_v2")
        path = f"/internal/v1/sessions/{session['session_id']}"
        assert (
            client.put(
                path + "/selection",
                json={
                    "revision": session["revision"],
                    "snapshot_id": "test-v2",
                    "strategy_id": "rare_question_v1",
                },
            ).status_code
            == 400
        )
        assert (
            client.post(
                path + "/consultation/rare", json={"revision": session["revision"]}
            ).status_code
            == 400
        )
        case = _case(_symptom(1, "present"), _symptom(2, "absent")).model_dump(mode="json")
        session = client.put(
            path + "/case", json={"revision": session["revision"], "clinical_case": case}
        ).json()
        diagnosis = client.post(
            path + "/analyses?view=summary", json={"revision": session["revision"]}
        ).json()
        session = diagnosis["session"]
        general_id = diagnosis["run"]["run_id"]
        general_bytes = client.get(path + f"/runs/{general_id}").content
        opted = client.post(path + "/consultation/rare", json={"revision": session["revision"]})
        assert opted.status_code == 200, opted.text
        session = opted.json()
        assert session["clinical_case"] == case
        assert session["consultation"]["phase"] == "rare"
        assert session["consultation"]["rare_opted_in_at"] is not None
        assert session["latest_diagnose"] is None
        rare_result = client.post(
            path + "/analyses?view=summary", json={"revision": session["revision"]}
        ).json()
        resumed = client.get(path).json()
        assert resumed["consultation"]["general_run"]["run_id"] == general_id
        assert resumed["consultation"]["rare_run"]["run_id"] == rare_result["run"]["run_id"]
        assert client.get(path + f"/runs/{general_id}").content == general_bytes
        rare_full = client.get(path + f"/runs/{rare_result['run']['run_id']}").json()
        assert rare_full["selection"]["strategy_id"] == "rare_question_v1"
        assert rare_result["run"]["result"]["safety"]["status"] == "not_evaluated"


def test_ambiguous_identifiers_refused_only_in_new_policy(scoped_fixture):
    root, profile, _, _ = scoped_fixture
    strategy = ConsultationStrategy(root, "test-v2", profile)
    try:
        db = strategy.repository.connection
        db.execute(
            "CREATE TEMP TABLE external_identifier AS SELECT * FROM main.external_identifier"
        )
        for i in (1, 2):
            payload = {"concept_id": f"test:finding-{i}", "system": "ambiguous", "code": "same"}
            db.execute(
                "INSERT INTO external_identifier VALUES (?,?)",
                [str(i), orjson.dumps(payload).decode()],
            )
        assert strategy._resolve_observation("not-direct", "ambiguous", "same") == (None, None)
        resolved, mapping = strategy._resolve_observation(
            "not-direct", "urn:latros:test-alternate", "ALT:F1"
        )
        assert resolved == "test:finding-1" and mapping is not None
    finally:
        strategy.close()
