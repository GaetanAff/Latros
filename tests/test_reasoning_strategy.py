from pathlib import Path

import pytest
from pydantic import ValidationError

from latros.clinical.migration import migrate_case_v1_to_v2
from latros.clinical.models import ClinicalCase
from latros.clinical.v2 import (
    ClinicalCaseV2,
    Coding,
    ConceptReference,
    ObservationProvenance,
    PhenotypeObservation,
    SignObservation,
)
from latros.common import LatrosError
from latros.reasoning.engine import Engine
from latros.reasoning.profiles import ReasoningProfile, load_reasoning_profile
from latros.reasoning.questions import next_question
from latros.reasoning.semantic_v1_adapter import (
    HPO_SYSTEM,
    SemanticV1Adapter,
    project_v2_for_semantic_v1,
)


def _legacy_case() -> ClinicalCase:
    return ClinicalCase.model_validate(
        {
            "case_id": "strategy-fixture",
            "observations": [
                {"concept_id": "HP:9000001", "status": "present"},
                {"concept_id": "HP:9000003", "status": "unknown"},
            ],
        }
    )


def _phenotype(identifier: str, code: str, status: str = "present") -> PhenotypeObservation:
    return PhenotypeObservation.model_validate(
        {
            "observation_id": identifier,
            "concept": {
                "concept_id": f"concept-{identifier}",
                "coding": {"system": HPO_SYSTEM, "code": code},
            },
            "clinical_status": status,
            "evaluation_status": "assessed",
            "uncertainty_reason": "unknown_to_subject" if status == "unknown" else None,
            "acquisition_method": "reported",
            "provenance": {"provenance_id": f"p-{identifier}", "origin_type": "patient_report"},
        }
    )


def test_semantic_v1_adapter_keeps_legacy_diagnosis_and_question_exact(built) -> None:
    engine = Engine(built[0], "test")
    adapter = SemanticV1Adapter(engine)
    case = _legacy_case()

    assert adapter.diagnose_legacy(case) == engine.diagnose(case)
    assert adapter.next(case).payload == next_question(engine, case)
    candidates = adapter.generate(case)
    assessments = adapter.score(case, candidates)
    assert [item.candidate_id for item in assessments] == candidates.candidate_ids
    assert adapter.build(case, assessments).payload == engine.diagnose(case)


def test_migrated_v2_case_projects_to_the_exact_v1_result(built) -> None:
    engine = Engine(built[0], "test")
    adapter = SemanticV1Adapter(engine)
    legacy = _legacy_case()
    migrated = migrate_case_v1_to_v2(legacy)

    projection = adapter.project(migrated)

    assert projection.source_contract == "clinical_case_v2"
    assert projection.proposal_count == 0
    assert adapter.diagnose_legacy(migrated) == engine.diagnose(legacy)
    assert adapter.next(migrated).payload == next_question(engine, legacy)


def test_unsupported_v2_observations_are_reported_and_never_scored(built) -> None:
    engine = Engine(built[0], "test")
    adapter = SemanticV1Adapter(engine)
    phenotype = _phenotype("hpo", "HP:9000001")
    sign = SignObservation(
        observation_id="generic-sign",
        concept=ConceptReference(
            concept_id="snomed-sign",
            coding=Coding(system="http://snomed.info/sct", code="123456"),
        ),
        clinical_status="present",
        evaluation_status="assessed",
        acquisition_method="observed",
        provenance=ObservationProvenance(
            provenance_id="p-sign", origin_type="clinician_observation"
        ),
    )
    case = ClinicalCaseV2(case_id="mixed", observations=[phenotype, sign])

    projection = adapter.project(case)

    assert [item.reason for item in projection.ignored_inputs] == ["unsupported_observation_type"]
    assert adapter.diagnose_legacy(case) == engine.diagnose(
        ClinicalCase(
            case_id="mixed",
            observations=[{"concept_id": "HP:9000001", "status": "present"}],
        )
    )


def test_multiple_active_temporal_values_are_not_silently_merged() -> None:
    case = ClinicalCaseV2(
        case_id="temporal-conflict",
        observations=[
            _phenotype("first", "HP:9000001"),
            _phenotype("second", "HP:9000001"),
        ],
    )

    with pytest.raises(LatrosError, match="cannot merge"):
        project_v2_for_semantic_v1(case)


def test_superseded_observation_is_not_projected() -> None:
    old = _phenotype("old", "HP:9000001", "present")
    new_payload = _phenotype("new", "HP:9000001", "absent").model_dump(mode="json")
    new_payload["concept"] = old.concept.model_dump(mode="json")
    new_payload["supersedes"] = "old"
    new = PhenotypeObservation.model_validate(new_payload)
    case = ClinicalCaseV2(case_id="corrected", observations=[old, new])

    projection = project_v2_for_semantic_v1(case)

    assert projection.case.observations[0].status == "absent"
    assert projection.used_observation_ids == ["new"]


def test_reasoning_profile_is_hashed_and_snapshot_compatible() -> None:
    root = Path(__file__).resolve().parents[1]
    profile = load_reasoning_profile(root / "profiles/semantic_v1.json")

    assert profile.accepts_snapshot("v0.2.0", 1)
    assert not profile.accepts_snapshot("v0.2.0", 2)
    altered = profile.model_dump(mode="json")
    altered["parameters"]["candidate_limit"] = 99
    with pytest.raises(ValidationError, match="hash"):
        ReasoningProfile.model_validate(altered)
