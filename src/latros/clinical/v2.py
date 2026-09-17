"""Versioned general clinical contracts; no reasoning is performed in this module."""

from datetime import date, datetime
from typing import Annotated, Literal, Self, TypeAlias, TypeVar

from pydantic import Field, model_validator

from latros.sources.registry import Contract

ClinicalStatus = Literal["present", "absent", "unknown"]
EvaluationStatus = Literal["assessed", "not_assessed", "unable_to_assess"]
UncertaintyReason = Literal[
    "unknown_to_subject", "uncertain", "not_asked", "unable_to_assess", "not_applicable", "other"
]


def validate_clinical_state(
    clinical_status: ClinicalStatus,
    evaluation_status: EvaluationStatus,
    reason: UncertaintyReason | None,
) -> None:
    if clinical_status in {"present", "absent"}:
        if evaluation_status != "assessed" or reason is not None:
            raise ValueError("Present/absent require assessed and no uncertainty reason")
        return
    allowed: dict[EvaluationStatus, set[UncertaintyReason]] = {
        "assessed": {"unknown_to_subject", "uncertain", "other"},
        "not_assessed": {"not_asked"},
        "unable_to_assess": {"unable_to_assess", "not_applicable"},
    }
    if reason not in allowed[evaluation_status]:
        raise ValueError("Unknown requires a reason compatible with evaluation_status")


class Coding(Contract):
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    version: str | None = Field(default=None, min_length=1)
    display: str | None = Field(default=None, min_length=1)


class ConceptReference(Contract):
    concept_id: str = Field(min_length=1)
    coding: Coding
    status: Literal["active", "obsolete"] = "active"
    original_coding: Coding | None = None


class CodedValue(Contract):
    kind: Literal["coded"] = "coded"
    value: ConceptReference


class QuantityValue(Contract):
    kind: Literal["quantity"] = "quantity"
    value: float
    comparator: Literal["eq", "lt", "le", "gt", "ge"] = "eq"
    unit: str = Field(min_length=1)
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)


class RangeValue(Contract):
    kind: Literal["range"] = "range"
    low: QuantityValue
    high: QuantityValue

    @model_validator(mode="after")
    def compatible_bounds(self) -> Self:
        if (self.low.system, self.low.code) != (self.high.system, self.high.code):
            raise ValueError("Range bounds require identical coded units")
        if self.low.value > self.high.value:
            raise ValueError("Range low must not exceed high")
        return self


class BooleanValue(Contract):
    kind: Literal["boolean"] = "boolean"
    value: bool


class TextValue(Contract):
    kind: Literal["text"] = "text"
    value: str = Field(min_length=1)


ClinicalValue: TypeAlias = Annotated[
    CodedValue | QuantityValue | RangeValue | BooleanValue | TextValue,
    Field(discriminator="kind"),
]


class DatePoint(Contract):
    kind: Literal["date"] = "date"
    value: date


class DateTimePoint(Contract):
    kind: Literal["date_time"] = "date_time"
    value: datetime


class AgePoint(Contract):
    kind: Literal["age"] = "age"
    value: QuantityValue


TemporalPoint: TypeAlias = Annotated[
    DatePoint | DateTimePoint | AgePoint, Field(discriminator="kind")
]


class TemporalContext(Contract):
    onset: TemporalPoint | None = None
    onset_end: TemporalPoint | None = None
    duration: str | None = Field(default=None, pattern=r"^P.+$")
    course: (
        Literal[
            "acute",
            "gradual",
            "continuous",
            "intermittent",
            "improving",
            "worsening",
            "stable",
            "recurrent",
        ]
        | None
    ) = None
    recurrence_count: int | None = Field(default=None, ge=0)
    trigger: ConceptReference | None = None

    @model_validator(mode="after")
    def compatible_onset_range(self) -> Self:
        if self.onset_end is not None and self.onset is None:
            raise ValueError("onset_end requires onset")
        if self.onset is not None and self.onset_end is not None:
            if self.onset.kind != self.onset_end.kind:
                raise ValueError("Onset range endpoints require the same kind")
            if self.onset.kind == "age" and self.onset_end.kind == "age":
                reversed_range = self.onset.value.value > self.onset_end.value.value
            elif self.onset.kind == "date" and self.onset_end.kind == "date":
                reversed_range = self.onset.value > self.onset_end.value
            elif self.onset.kind == "date_time" and self.onset_end.kind == "date_time":
                reversed_range = self.onset.value > self.onset_end.value
            else:  # pragma: no cover - guarded by the kind comparison above
                reversed_range = False
            if reversed_range:
                raise ValueError("Onset range is reversed")
        return self


class ObservationProvenance(Contract):
    provenance_id: str = Field(min_length=1)
    origin_type: Literal[
        "patient_report",
        "clinician_observation",
        "device",
        "laboratory",
        "imaging",
        "health_record",
        "question_response",
        "legacy_case_v1_migration",
    ]
    source_statement_id: str | None = Field(default=None, min_length=1)
    source_reference: str | None = Field(default=None, min_length=1)
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def non_direct_origin_is_traceable(self) -> Self:
        direct = {"patient_report", "clinician_observation", "question_response"}
        if self.origin_type not in direct and self.source_reference is None:
            raise ValueError("Non-direct observations require source_reference")
        return self


class SourceStatement(Contract):
    statement_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    author_type: Literal["patient", "clinician", "other"]
    language: str | None = Field(default=None, min_length=2, max_length=35)
    recorded_at: datetime | None = None


class TextSpan(Contract):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def ordered_span(self) -> Self:
        if self.start >= self.end:
            raise ValueError("Text span start must precede end")
        return self


class ProposalCandidate(Contract):
    concept: ConceptReference
    extraction_confidence: float = Field(ge=0, le=1)


class ExtractionMethod(Contract):
    kind: Literal["rule", "nlp", "llm", "manual"]
    tool: str = Field(min_length=1)
    version: str = Field(min_length=1)
    parameters: dict[str, str] = Field(default_factory=dict)


class ObservationProposal(Contract):
    proposal_id: str = Field(min_length=1)
    source_statement_id: str = Field(min_length=1)
    span: TextSpan
    candidates: list[ProposalCandidate] = Field(min_length=1)
    method: ExtractionMethod
    state: Literal["proposed", "accepted", "corrected", "rejected"] = "proposed"
    confirmed_observation_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def confirmation_matches_state(self) -> Self:
        confirmed = self.state in {"accepted", "corrected"}
        if confirmed != (self.confirmed_observation_id is not None):
            raise ValueError("Accepted/corrected proposals require a confirmed observation")
        return self


class ObservationBase(Contract):
    observation_id: str = Field(min_length=1)
    concept: ConceptReference
    clinical_status: ClinicalStatus
    evaluation_status: EvaluationStatus
    uncertainty_reason: UncertaintyReason | None = None
    value: ClinicalValue | None = None
    certainty: Literal["asserted", "uncertain"] = "asserted"
    temporal: TemporalContext | None = None
    severity: ConceptReference | None = None
    body_site: ConceptReference | None = None
    laterality: Literal["left", "right", "bilateral", "midline", "not_applicable"] | None = None
    experiencer: Literal["patient", "family_member"] = "patient"
    acquisition_method: Literal[
        "reported", "observed", "measured", "recorded", "question_answer", "legacy_migration"
    ]
    provenance: ObservationProvenance
    supersedes: str | None = Field(default=None, min_length=1)
    question_response_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def valid_state_and_value(self) -> Self:
        validate_clinical_state(
            self.clinical_status, self.evaluation_status, self.uncertainty_reason
        )
        if self.clinical_status != "present" and self.value is not None:
            raise ValueError("Only present observations may carry a value")
        return self


class PhenotypeObservation(ObservationBase):
    kind: Literal["phenotype"] = "phenotype"


class SymptomObservation(ObservationBase):
    kind: Literal["symptom"] = "symptom"


class SignObservation(ObservationBase):
    kind: Literal["sign"] = "sign"


class VitalMeasurement(ObservationBase):
    kind: Literal["vital"] = "vital"

    @model_validator(mode="after")
    def measured_value_required(self) -> Self:
        if self.clinical_status == "present" and not isinstance(
            self.value, (QuantityValue, RangeValue)
        ):
            raise ValueError("A present vital requires a quantity or range")
        return self


class LaboratoryResult(ObservationBase):
    kind: Literal["laboratory"] = "laboratory"
    reference_range: RangeValue | None = None

    @model_validator(mode="after")
    def laboratory_value_required(self) -> Self:
        if self.clinical_status == "present" and not isinstance(
            self.value, (QuantityValue, RangeValue, CodedValue)
        ):
            raise ValueError("A present laboratory result requires a structured value")
        return self


class MedicationExposure(ObservationBase):
    kind: Literal["medication"] = "medication"


class MedicalHistoryItem(ObservationBase):
    kind: Literal["medical_history"] = "medical_history"


class RiskFactorObservation(ObservationBase):
    kind: Literal["risk_factor"] = "risk_factor"


class ExamResult(ObservationBase):
    kind: Literal["exam"] = "exam"


class ImagingResult(ObservationBase):
    kind: Literal["imaging"] = "imaging"


class FamilyHistoryItem(ObservationBase):
    kind: Literal["family_history"] = "family_history"
    experiencer: Literal["family_member"] = "family_member"


ClinicalObservation: TypeAlias = Annotated[
    PhenotypeObservation
    | SymptomObservation
    | SignObservation
    | VitalMeasurement
    | LaboratoryResult
    | MedicationExposure
    | MedicalHistoryItem
    | RiskFactorObservation
    | ExamResult
    | ImagingResult
    | FamilyHistoryItem,
    Field(discriminator="kind"),
]


class QuestionResponseV2(Contract):
    response_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    concept: ConceptReference
    clinical_status: ClinicalStatus
    evaluation_status: EvaluationStatus
    uncertainty_reason: UncertaintyReason | None = None
    resulting_observation_id: str = Field(min_length=1)
    answered_at: datetime | None = None
    provenance: ObservationProvenance

    @model_validator(mode="after")
    def valid_state(self) -> Self:
        validate_clinical_state(
            self.clinical_status, self.evaluation_status, self.uncertainty_reason
        )
        return self


class SubjectContext(Contract):
    age: QuantityValue | RangeValue | None = None
    sex: Literal["male", "female", "intersex", "unknown"] | None = None


class ClinicalCaseV2(Contract):
    schema_version: Literal[2] = 2
    case_id: str = Field(min_length=1, max_length=120)
    subject_context: SubjectContext = Field(default_factory=SubjectContext)
    source_statements: list[SourceStatement] = Field(default_factory=list)
    observation_proposals: list[ObservationProposal] = Field(default_factory=list)
    observations: list[ClinicalObservation] = Field(default_factory=list)
    question_history: list[QuestionResponseV2] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        statements = _unique(self.source_statements, "statement_id", "source statement")
        proposals = _unique(self.observation_proposals, "proposal_id", "proposal")
        observations = _unique(self.observations, "observation_id", "observation")
        responses = _unique(self.question_history, "response_id", "question response")
        del proposals, responses
        for proposal in self.observation_proposals:
            if proposal.source_statement_id not in statements:
                raise ValueError("Proposal references an unknown source statement")
            if (
                proposal.confirmed_observation_id is not None
                and proposal.confirmed_observation_id not in observations
            ):
                raise ValueError("Proposal references an unknown confirmed observation")
        for observation in self.observations:
            source = observation.provenance.source_statement_id
            if source is not None and source not in statements:
                raise ValueError("Observation provenance references an unknown statement")
            if observation.supersedes is not None:
                previous = observations.get(observation.supersedes)
                if previous is None:
                    raise ValueError("Observation supersedes an unknown observation")
                if previous.concept.concept_id != observation.concept.concept_id:
                    raise ValueError("An observation may only supersede the same concept")
        for response in self.question_history:
            resulting_observation = observations.get(response.resulting_observation_id)
            if resulting_observation is None:
                raise ValueError("Question response requires its resulting observation")
            if resulting_observation.concept.concept_id != response.concept.concept_id:
                raise ValueError("Question response and resulting observation disagree")
            conflicting = [
                item
                for item in self.observations
                if item.observation_id != resulting_observation.observation_id
                and item.concept.concept_id == resulting_observation.concept.concept_id
                and item.clinical_status != resulting_observation.clinical_status
                and item.observation_id != resulting_observation.supersedes
            ]
            if conflicting:
                raise ValueError("A contradictory question answer must supersede the old value")
        return self


UniqueItem = TypeVar("UniqueItem")


def _unique(items: list[UniqueItem], field: str, label: str) -> dict[str, UniqueItem]:
    result: dict[str, UniqueItem] = {}
    for item in items:
        key = getattr(item, field)
        if key in result:
            raise ValueError(f"Duplicate {label} identifier: {key}")
        result[key] = item
    return result
