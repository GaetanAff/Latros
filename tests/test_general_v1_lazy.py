"""Equivalence of eager reference and read-only lazy runtime on invented data."""

from pathlib import Path

import pytest

from latros.application.service import ResearchApplicationService
from latros.clinical.v2 import ClinicalCaseV2, QuantityValue, SubjectContext, SymptomObservation
from latros.common import LatrosError
from latros.knowledge.models_v2 import ConceptObject
from latros.knowledge.repository_v2 import CanonicalKnowledgeRepositoryV2
from latros.knowledge.store_v2 import build_snapshot_v2, snapshot_path_v2
from latros.reasoning.general_v1 import GeneralV1Strategy
from latros.reasoning.general_v1_lazy import LazyGeneralV1Strategy
from latros.reasoning.profiles import load_reasoning_profile


def _case(statuses: tuple[str, str] = ("present", "absent")) -> ClinicalCaseV2:
    return ClinicalCaseV2(
        case_id="lazy-regression-case",
        subject_context=SubjectContext(
            age=QuantityValue(value=30, unit="year", system="http://unitsofmeasure.org", code="a")
        ),
        observations=[
            SymptomObservation.model_validate(
                {
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
            for index, status in enumerate(statuses, 1)
        ],
    )


def test_lazy_matches_eager_complete_results_and_question(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    profile = load_reasoning_profile(
        Path(__file__).resolve().parents[1] / "profiles/general_v1.json"
    )
    eager = GeneralV1Strategy(root, "test-v2", profile)
    lazy = LazyGeneralV1Strategy(root, "test-v2", profile)
    try:
        for case in (_case(), _case(("absent", "present")), _case(("present", "present"))):
            assert lazy.generate(case).model_dump_json() == eager.generate(case).model_dump_json()
            assert lazy.diagnose(case).model_dump_json() == eager.diagnose(case).model_dump_json()
            assert lazy.question(case).model_dump_json() == eager.question(case).model_dump_json()
        assert (
            lazy.question(ClinicalCaseV2(case_id="empty")).model_dump_json()
            == eager.question(ClinicalCaseV2(case_id="empty")).model_dump_json()
        )
    finally:
        lazy.close()


def test_service_general_search_never_materializes_full_knowledge(
    synthetic_v2, monkeypatch
) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("full CanonicalKnowledgeV2 load is forbidden in runtime")

    monkeypatch.setattr("latros.knowledge.store_v2.read_knowledge_v2", forbidden)
    service = ResearchApplicationService(root)
    matches = service.search_concepts("test-v2", "general_v1", "finding", limit=10)
    assert matches
    assert (
        service.resolve_question_concept(
            "test-v2", "general_v1", matches[0].system, matches[0].code
        )
        == matches[0]
    )
    assert service.diagnose("test-v2", _case(), "general_v1").status == "ranked"


def test_repository_rejects_changed_runtime_hash(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    database = snapshot_path_v2(root, "test-v2")
    with database.open("ab") as handle:
        handle.write(b"corrupt")
    with pytest.raises(LatrosError, match="checksum mismatch"):
        CanonicalKnowledgeRepositoryV2(root, "test-v2")


def test_candidate_rows_does_not_send_assertion_id_lists_to_duckdb(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    repository = CanonicalKnowledgeRepositoryV2(root, "test-v2")

    class ParameterGuard:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, parameters=None):
            for parameter in parameters or []:
                if isinstance(parameter, list):
                    assert len(parameter) <= 1, sql
            return (
                self.connection.execute(sql, parameters)
                if parameters is not None
                else self.connection.execute(sql)
            )

        def close(self):
            self.connection.close()

    repository.connection = ParameterGuard(repository.connection)
    try:
        rows = repository.candidate_rows(["test:condition-1"])
        assert len(rows.assertions["test:condition-1"]) == 2
        assert len(rows.provenance) == 2
    finally:
        repository.close()


def test_matched_candidate_projection_reuses_exact_ids_and_provenance(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    repository = CanonicalKnowledgeRepositoryV2(root, "test-v2")
    try:
        matched = repository.matching_candidate_ids(
            [("test:finding-1", "has_symptom")], repository.aggregatable_family_ids()
        )
        assert matched == ["test:condition-1", "test:condition-2"]
        reused = repository.candidate_rows(matched, reuse_last_match=True)
        independent = repository.candidate_rows(matched)
        assert reused == independent
        with pytest.raises(LatrosError, match="no longer match"):
            repository.candidate_rows(["test:condition-4"], reuse_last_match=True)
    finally:
        repository.close()


def test_compact_scoring_assertions_preserve_canonical_fields(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    repository = CanonicalKnowledgeRepositoryV2(root, "test-v2")
    try:
        rows = repository.candidate_rows(repository.all_candidate_ids())
        compact = {
            item.canonical_assertion_id: item
            for items in rows.assertions.values()
            for item in items
        }
        assert set(compact) == {
            item.canonical_assertion_id for item in knowledge.canonical_assertions
        }
        for original in knowledge.canonical_assertions:
            projected = compact[original.canonical_assertion_id]
            assert projected.subject_concept_id == original.subject_concept_id
            assert projected.relation == original.relation
            assert projected.polarity == original.qualifiers.polarity
            assert projected.object_concept_id == (
                original.object.concept_id if isinstance(original.object, ConceptObject) else None
            )
    finally:
        repository.close()


def test_cached_repository_fails_closed_if_manifest_changes(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    service = ResearchApplicationService(root)
    assert service.search_concepts("test-v2", "general_v1", "finding")
    manifest = root / "manifests/test-v2.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(LatrosError, match="changed during this process"):
        service.search_concepts("test-v2", "general_v1", "finding")
