"""Deterministic, explicit migration from the unversioned HPO case contract."""

from latros.clinical.models import ClinicalCase
from latros.clinical.v2 import (
    ClinicalCaseV2,
    ClinicalObservation,
    Coding,
    ConceptReference,
    ObservationProvenance,
    PhenotypeObservation,
    QuantityValue,
    QuestionResponseV2,
    SubjectContext,
)
from latros.common import stable_id

HPO_SYSTEM = "http://purl.obolibrary.org/obo/hp.owl"
UCUM_SYSTEM = "http://unitsofmeasure.org"


def migrate_case_v1_to_v2(case: ClinicalCase | ClinicalCaseV2) -> ClinicalCaseV2:
    if isinstance(case, ClinicalCaseV2):
        return case
    history = {item.concept_id: item for item in case.question_history}
    observations: list[ClinicalObservation] = []
    for concept_id, status in sorted(case.effective_observations().items()):
        observation_id = stable_id("clinical_observation", case.case_id, concept_id)
        response = history.get(concept_id)
        observations.append(
            PhenotypeObservation(
                observation_id=observation_id,
                concept=_hpo(concept_id),
                clinical_status=status,
                evaluation_status="assessed",
                uncertainty_reason="unknown_to_subject" if status == "unknown" else None,
                acquisition_method="legacy_migration",
                question_response_id=(
                    stable_id("question_response", case.case_id, concept_id)
                    if response is not None
                    else None
                ),
                provenance=ObservationProvenance(
                    provenance_id=stable_id(
                        "provenance", "ClinicalCaseV1", case.case_id, concept_id
                    ),
                    origin_type="legacy_case_v1_migration",
                    source_reference="ClinicalCaseV1",
                ),
            )
        )
    question_history = [
        QuestionResponseV2(
            response_id=stable_id("question_response", case.case_id, answer.concept_id),
            question_id=stable_id("legacy_question", case.case_id, answer.concept_id),
            concept=_hpo(answer.concept_id),
            clinical_status=answer.answer,
            evaluation_status="assessed",
            uncertainty_reason=("unknown_to_subject" if answer.answer == "unknown" else None),
            resulting_observation_id=stable_id(
                "clinical_observation", case.case_id, answer.concept_id
            ),
            provenance=ObservationProvenance(
                provenance_id=stable_id(
                    "provenance", "ClinicalCaseV1Question", case.case_id, answer.concept_id
                ),
                origin_type="legacy_case_v1_migration",
                source_reference="ClinicalCaseV1.question_history",
            ),
        )
        for answer in case.question_history
    ]
    age = (
        QuantityValue(value=case.age, unit="year", system=UCUM_SYSTEM, code="a")
        if case.age is not None
        else None
    )
    return ClinicalCaseV2(
        case_id=case.case_id,
        subject_context=SubjectContext(age=age, sex=case.sex),
        observations=observations,
        question_history=question_history,
    )


def _hpo(code: str) -> ConceptReference:
    return ConceptReference(
        concept_id=stable_id("concept", code),
        coding=Coding(system=HPO_SYSTEM, code=code),
    )
