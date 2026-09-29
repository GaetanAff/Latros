"""Backend-authored capture refinements, not medical discriminant rules."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, model_validator

from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError
from latros.sources.registry import Contract

# UX capture prompts only, not differential rules or new medical assertions.
# Unknown findings do not automatically receive a generic questionnaire.
RefinementQuestionType = Literal["duration", "reported_severity", "reported_laterality"]
HPO_SYSTEM = "http://purl.obolibrary.org/obo/hp.owl"
REFINEMENT_FIELDS_BY_HPO: dict[str, tuple[RefinementQuestionType, ...]] = {
    "HP:0002315": ("duration", "reported_severity", "reported_laterality"),  # headache
    "HP:0002027": ("duration", "reported_severity"),  # abdominal pain
    "HP:0100749": ("duration", "reported_severity"),  # chest pain
    "HP:0003419": ("duration", "reported_severity", "reported_laterality"),  # back pain
    "HP:0002829": ("duration", "reported_severity", "reported_laterality"),  # joint pain
    "HP:0012735": ("duration",),  # cough
    "HP:0031417": ("duration",),  # rhinorrhea
    "HP:0001742": ("duration",),  # nasal congestion
    "HP:0033050": ("duration", "reported_severity"),  # sore throat
    "HP:0001945": ("duration",),  # fever
    "HP:0002014": ("duration",),  # diarrhea
    "HP:0002321": ("duration",),  # vertigo
}


class RefinementAnswer(Contract):
    definition_id: Literal["reported-observation-context-v1"] = "reported-observation-context-v1"
    observation_id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    duration_value: int | None = Field(default=None, ge=1, le=10000, strict=True)
    duration_unit: Literal["hour", "day", "week", "month", "year"] | None = None
    reported_severity: Literal["mild", "moderate", "severe"] | None = None
    reported_laterality: (
        Literal["left", "right", "bilateral", "midline", "not_applicable"] | None
    ) = None
    evaluation_status: Literal["captured_not_evaluated"] = "captured_not_evaluated"
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def paired_duration(self) -> "RefinementAnswer":
        if (self.duration_value is None) != (self.duration_unit is None):
            raise ValueError("Duration value and unit must be provided together")
        return self


class RefinementAnswerRequest(Contract):
    revision: int = Field(ge=0)
    answer: RefinementAnswer


class SymptomRefinementDefinition(Contract):
    definition_id: Literal["reported-observation-context-v1"] = "reported-observation-context-v1"
    definition_version: Literal[1] = 1
    observation_id: str
    concept_id: str
    source_label: str
    question_types: list[Literal["duration", "reported_severity", "reported_laterality"]]
    duration_units: list[Literal["hour", "day", "week", "month", "year"]]
    severity_options: list[Literal["mild", "moderate", "severe"]]
    laterality_options: list[Literal["left", "right", "bilateral", "midline", "not_applicable"]]
    provenance: Literal["latros-ui-capture-contract-v1"] = "latros-ui-capture-contract-v1"
    review_status: Literal["engineering_definition_not_clinically_validated"] = (
        "engineering_definition_not_clinically_validated"
    )
    reasoning_use: Literal["not_used_by_current_strategies"] = "not_used_by_current_strategies"


def refinement_definitions(case: ClinicalCaseV2) -> list[SymptomRefinementDefinition]:
    superseded = {item.supersedes for item in case.observations if item.supersedes}
    return [
        SymptomRefinementDefinition(
            observation_id=item.observation_id,
            concept_id=item.concept.concept_id,
            source_label=item.concept.coding.display or item.concept.coding.code,
            question_types=list(REFINEMENT_FIELDS_BY_HPO[item.concept.coding.code]),
            duration_units=["hour", "day", "week", "month", "year"],
            severity_options=["mild", "moderate", "severe"]
            if "reported_severity" in REFINEMENT_FIELDS_BY_HPO[item.concept.coding.code]
            else [],
            laterality_options=["left", "right", "bilateral", "midline", "not_applicable"]
            if "reported_laterality" in REFINEMENT_FIELDS_BY_HPO[item.concept.coding.code]
            else [],
        )
        for item in case.observations
        if item.observation_id not in superseded
        and item.kind in {"symptom", "sign", "exam"}
        and item.clinical_status == "present"
        and item.acquisition_method == "reported"
        and item.concept.coding.system == HPO_SYSTEM
        and item.concept.coding.code in REFINEMENT_FIELDS_BY_HPO
    ]


def apply_refinement(case: ClinicalCaseV2, answer: RefinementAnswer) -> ClinicalCaseV2:
    definitions = refinement_definitions(case)
    definition = next(
        (
            item
            for item in definitions
            if item.observation_id == answer.observation_id and item.concept_id == answer.concept_id
        ),
        None,
    )
    if definition is None:
        raise LatrosError("Refinement does not refer to an active reported observation")
    forbidden_duration = (
        answer.duration_value is not None and "duration" not in definition.question_types
    )
    forbidden_severity = (
        answer.reported_severity is not None
        and "reported_severity" not in definition.question_types
    )
    forbidden_laterality = (
        answer.reported_laterality is not None
        and "reported_laterality" not in definition.question_types
    )
    if forbidden_duration or forbidden_severity or forbidden_laterality:
        raise LatrosError("Refinement answer contains a field not offered by its definition")
    payload = case.model_dump(mode="json")
    observation = next(
        item for item in payload["observations"] if item["observation_id"] == answer.observation_id
    )
    if answer.duration_value is not None:
        units = {"hour": "H", "day": "D", "week": "W", "month": "M", "year": "Y"}
        duration = f"P{'T' if answer.duration_unit == 'hour' else ''}{answer.duration_value}"
        duration += units[str(answer.duration_unit)]
        temporal = observation.get("temporal") or {}
        temporal["duration"] = duration
        observation["temporal"] = temporal
    if answer.reported_laterality is not None:
        observation["laterality"] = answer.reported_laterality
    # Severity is uncoded: preserve the answer in session metadata, never invent an HPO ID.
    return ClinicalCaseV2.model_validate(payload)
