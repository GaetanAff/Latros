"""Local self-reported session context, deliberately outside scientific cases."""

from typing import Literal

from pydantic import Field, field_validator

from latros.clinical.v2 import ClinicalCaseV2
from latros.sources.registry import Contract


class PatientDemographics(Contract):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    age_years: int = Field(ge=0, le=130, strict=True)

    @field_validator("first_name", "last_name")
    @classmethod
    def explicit_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A local name or explicit pseudonym is required")
        return value.strip()


class SelfReportedContextItem(Contract):
    """Not a confirmed allergy, condition, coded drug or diagnostic observation."""

    label: str = Field(min_length=1, max_length=200)
    origin: Literal["self_reported"] = "self_reported"
    evaluation_status: Literal["captured_not_evaluated"] = "captured_not_evaluated"

    @field_validator("label")
    @classmethod
    def explicit_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("An empty context item is not meaningful")
        return value.strip()


class PatientContext(Contract):
    context_version: Literal[1] = 1
    demographics: PatientDemographics
    allergies: list[SelfReportedContextItem] = Field(default_factory=list, max_length=30)
    known_conditions: list[SelfReportedContextItem] = Field(default_factory=list, max_length=30)
    medications: list[SelfReportedContextItem] = Field(default_factory=list, max_length=30)
    relevant_history: list[SelfReportedContextItem] = Field(default_factory=list, max_length=30)
    symptom_narrative: str | None = Field(default=None, max_length=4000)
    clinical_evaluation: Literal["not_evaluated"] = "not_evaluated"


class PatientContextRequest(Contract):
    revision: int = Field(ge=0)
    patient_context: PatientContext


def project_age(case: ClinicalCaseV2, context: PatientContext) -> ClinicalCaseV2:
    """Project ONLY age; identifiers and uncoded background stay session-local."""
    payload = case.model_dump(mode="json")
    payload["subject_context"]["age"] = {
        "kind": "quantity",
        "value": context.demographics.age_years,
        "comparator": "eq",
        "unit": "year",
        "system": "http://unitsofmeasure.org",
        "code": "a",
    }
    return ClinicalCaseV2.model_validate(payload)
