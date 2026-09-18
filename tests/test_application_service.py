from pathlib import Path

import pytest

from latros.application.service import ResearchApplicationService
from latros.clinical.v2 import ClinicalCaseV2, QuantityValue, SubjectContext, SymptomObservation
from latros.common import LatrosError
from latros.knowledge.store_v2 import build_snapshot_v2


def _general_case() -> ClinicalCaseV2:
    observations = []
    for index, status in ((1, "present"), (2, "absent")):
        observations.append(
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
        )
    return ClinicalCaseV2(
        case_id="application-case",
        subject_context=SubjectContext(
            age=QuantityValue(
                value=30,
                unit="year",
                system="http://unitsofmeasure.org",
                code="a",
            )
        ),
        observations=observations,
    )


def test_application_service_discovers_only_compatible_available_pairs(built) -> None:
    root, _ = built
    service = ResearchApplicationService(root)

    capabilities = service.capabilities()

    pairs = [(item.snapshot_id, item.strategy_id) for item in capabilities.compatible_selections]
    assert pairs == [("test", "semantic_v1")]
    assert capabilities.offline_only is True
    assert capabilities.telemetry is False
    with pytest.raises(LatrosError, match="Incompatible"):
        service.require_compatible("test", "general_v1")


def test_application_service_runs_general_v1_and_catalog(synthetic_v2) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    service = ResearchApplicationService(root)

    selection = service.require_compatible("test-v2", "general_v1")
    concepts = service.search_concepts("test-v2", "general_v1", "finding", limit=10)
    result = service.diagnose("test-v2", _general_case(), "general_v1", "v2")

    assert selection.profile_id == "general_v1-default"
    assert {item.observation_kind for item in concepts} >= {"symptom"}
    assert hasattr(result, "candidates")
    assert result.candidates[0].candidate_id == "test:condition-1"  # type: ignore[union-attr]


def test_profile_resolution_works_outside_repository_working_directory(
    synthetic_v2, monkeypatch
) -> None:
    root, registry, knowledge = synthetic_v2
    build_snapshot_v2(root, registry, "test-v2", knowledge)
    monkeypatch.chdir(Path(root))

    profile = ResearchApplicationService(root).profile("general_v1", "test-v2")

    assert profile.profile_id == "general_v1-default"
