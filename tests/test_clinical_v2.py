from copy import deepcopy

import pytest
from pydantic import ValidationError

from latros.clinical import ClinicalCaseV1, ClinicalCaseV2, load_clinical_case
from latros.clinical.migration import migrate_case_v1_to_v2
from latros.clinical.v2 import (
    BooleanValue,
    ClinicalObservation,
    Coding,
    ConceptReference,
    DatePoint,
    ExamResult,
    ExtractionMethod,
    FamilyHistoryItem,
    ImagingResult,
    LaboratoryResult,
    MedicalHistoryItem,
    MedicationExposure,
    ObservationProposal,
    ObservationProvenance,
    PhenotypeObservation,
    ProposalCandidate,
    QuantityValue,
    RangeValue,
    RiskFactorObservation,
    SignObservation,
    SourceStatement,
    SymptomObservation,
    TemporalContext,
    TextSpan,
    TextValue,
    VitalMeasurement,
)
from latros.common import LatrosError


def _concept(code: str = "HP:0001945") -> ConceptReference:
    return ConceptReference(
        concept_id=f"concept-{code}",
        coding=Coding(system="http://purl.obolibrary.org/obo/hp.owl", code=code),
    )


def _direct_provenance(identifier: str = "p1") -> ObservationProvenance:
    return ObservationProvenance(
        provenance_id=identifier,
        origin_type="patient_report",
    )


def _base(identifier: str, code: str = "HP:0001945") -> dict[str, object]:
    return {
        "observation_id": identifier,
        "concept": _concept(code),
        "clinical_status": "present",
        "evaluation_status": "assessed",
        "acquisition_method": "reported",
        "provenance": _direct_provenance(f"provenance-{identifier}"),
    }


def test_load_dispatches_unversioned_v1_explicit_v2_and_rejects_unknown() -> None:
    legacy = load_clinical_case('{"case_id":"legacy","observations":[]}')
    current = load_clinical_case({"schema_version": 2, "case_id": "current"})

    assert isinstance(legacy, ClinicalCaseV1)
    assert isinstance(current, ClinicalCaseV2)
    with pytest.raises(LatrosError, match="Unsupported clinical case schema_version"):
        load_clinical_case({"schema_version": 3, "case_id": "future"})


def test_v1_migration_is_deterministic_and_idempotent() -> None:
    legacy = ClinicalCaseV1.model_validate(
        {
            "case_id": "migration-case",
            "age": 42,
            "sex": "female",
            "observations": [
                {"concept_id": "HP:0001945", "status": "present"},
                {"concept_id": "HP:0002014", "status": "absent"},
            ],
            "question_history": [{"concept_id": "HP:0001250", "answer": "unknown"}],
        }
    )

    migrated = migrate_case_v1_to_v2(legacy)
    repeated = migrate_case_v1_to_v2(legacy)

    assert migrated.model_dump(mode="json") == repeated.model_dump(mode="json")
    assert migrate_case_v1_to_v2(migrated) is migrated
    assert migrated.subject_context.age is not None
    assert migrated.subject_context.age.code == "a"
    assert migrated.subject_context.age.system == "http://unitsofmeasure.org"
    assert len(migrated.observations) == 3
    unknown = next(item for item in migrated.observations if item.clinical_status == "unknown")
    assert unknown.evaluation_status == "assessed"
    assert unknown.uncertainty_reason == "unknown_to_subject"


@pytest.mark.parametrize(
    ("clinical_status", "evaluation_status", "reason"),
    [
        ("present", "not_assessed", "not_asked"),
        ("absent", "unable_to_assess", "unable_to_assess"),
        ("unknown", "assessed", None),
        ("unknown", "not_assessed", "unable_to_assess"),
    ],
)
def test_invalid_state_combinations_are_rejected(
    clinical_status: str, evaluation_status: str, reason: str | None
) -> None:
    payload = _base("invalid")
    payload.update(
        clinical_status=clinical_status,
        evaluation_status=evaluation_status,
        uncertainty_reason=reason,
    )
    with pytest.raises(ValidationError):
        PhenotypeObservation.model_validate(payload)


def test_unable_to_assess_is_unknown_with_an_evaluation_reason() -> None:
    payload = _base("unable")
    payload.update(
        clinical_status="unknown",
        evaluation_status="unable_to_assess",
        uncertainty_reason="unable_to_assess",
    )

    observation = SymptomObservation.model_validate(payload)

    assert observation.clinical_status == "unknown"
    assert observation.evaluation_status == "unable_to_assess"


def test_each_observation_kind_serializes_with_a_closed_value_union() -> None:
    quantity = QuantityValue(
        value=38.4,
        comparator="eq",
        unit="degree Celsius",
        system="http://unitsofmeasure.org",
        code="Cel",
    )
    observation_types: list[type[ClinicalObservation]] = [
        PhenotypeObservation,
        SymptomObservation,
        SignObservation,
        MedicationExposure,
        MedicalHistoryItem,
        RiskFactorObservation,
        ExamResult,
        ImagingResult,
    ]
    observations: list[ClinicalObservation] = [
        observation_type(**_base(f"o-{index}"))
        for index, observation_type in enumerate(observation_types)
    ]
    observations.extend(
        [
            VitalMeasurement(**_base("vital"), value=quantity),
            LaboratoryResult(**_base("lab"), value=quantity),
            FamilyHistoryItem(
                **_base("family"),
                experiencer="family_member",
            ),
        ]
    )

    case = ClinicalCaseV2(case_id="all-types", observations=observations)
    restored = ClinicalCaseV2.model_validate_json(case.model_dump_json())

    assert [item.kind for item in restored.observations] == [item.kind for item in observations]


def test_measurements_and_temporal_ranges_are_validated() -> None:
    low = QuantityValue(value=2, unit="mg/L", system="http://unitsofmeasure.org", code="mg/L")
    high = QuantityValue(value=1, unit="mg/L", system="http://unitsofmeasure.org", code="mg/L")
    with pytest.raises(ValidationError, match="Range low"):
        RangeValue(low=low, high=high)
    with pytest.raises(ValidationError, match="identical coded units"):
        RangeValue(
            low=low,
            high=QuantityValue(
                value=3,
                unit="g/L",
                system="http://unitsofmeasure.org",
                code="g/L",
            ),
        )
    with pytest.raises(ValidationError, match="Onset range is reversed"):
        TemporalContext(
            onset=DatePoint(value="2025-05-02"),
            onset_end=DatePoint(value="2025-05-01"),
        )
    with pytest.raises(ValidationError):
        QuantityValue.model_validate({"value": 1, "unit": "mg/L", "code": "mg/L"})


def test_non_direct_provenance_requires_a_traceable_reference() -> None:
    with pytest.raises(ValidationError, match="source_reference"):
        ObservationProvenance(provenance_id="lab-p", origin_type="laboratory")


def test_proposals_are_separate_from_confirmed_observations() -> None:
    statement = SourceStatement(statement_id="s1", text="J'ai de la fièvre", author_type="patient")
    proposal = ObservationProposal(
        proposal_id="proposal-1",
        source_statement_id="s1",
        span=TextSpan(start=10, end=16, text="fièvre"),
        candidates=[ProposalCandidate(concept=_concept(), extraction_confidence=0.91)],
        method=ExtractionMethod(kind="rule", tool="fixture", version="1"),
    )

    case = ClinicalCaseV2(
        case_id="proposal-only",
        source_statements=[statement],
        observation_proposals=[proposal],
    )

    assert case.observations == []
    assert case.observation_proposals[0].state == "proposed"


def test_correction_requires_supersedes_and_the_same_concept() -> None:
    initial = PhenotypeObservation(**_base("initial"))
    contradictory = deepcopy(_base("contradictory"))
    contradictory.update(clinical_status="absent", question_response_id="qr-1")
    answer_provenance = ObservationProvenance(
        provenance_id="question-p",
        origin_type="question_response",
    )
    from latros.clinical.v2 import QuestionResponseV2

    response = QuestionResponseV2(
        response_id="qr-1",
        question_id="q-1",
        concept=_concept(),
        clinical_status="absent",
        evaluation_status="assessed",
        resulting_observation_id="contradictory",
        provenance=answer_provenance,
    )
    with pytest.raises(ValidationError, match="must supersede"):
        ClinicalCaseV2(
            case_id="conflict",
            observations=[initial, PhenotypeObservation.model_validate(contradictory)],
            question_history=[response],
        )

    contradictory["supersedes"] = "initial"
    corrected = ClinicalCaseV2(
        case_id="corrected",
        observations=[initial, PhenotypeObservation.model_validate(contradictory)],
        question_history=[response],
    )
    assert corrected.observations[-1].supersedes == "initial"


def test_absent_observation_cannot_carry_a_value() -> None:
    payload = _base("absent-value")
    payload.update(clinical_status="absent", value=BooleanValue(value=True))
    with pytest.raises(ValidationError, match="Only present"):
        SignObservation.model_validate(payload)


def test_text_values_are_non_empty() -> None:
    with pytest.raises(ValidationError):
        TextValue(value="")
