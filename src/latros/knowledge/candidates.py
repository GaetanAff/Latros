"""Non-clinically-validated staging contracts for local knowledge extraction."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from latros.common import stable_id
from latros.knowledge.frequency import Frequency
from latros.sources.registry import Contract

CandidateStatus = Literal[
    "agent_extracted",
    "pending_mapping",
    "normalized_unreviewed",
    "approved",
    "rejected",
]
MappingStatus = Literal["resolved", "ambiguous", "unresolved", "not_attempted"]
MappingRelation = Literal["exact", "equivalent", "broader", "narrower", "related", "unresolved"]


class ExtractionProvenance(Contract):
    extractor_id: str = Field(min_length=1)
    extractor_version: str = Field(min_length=1)
    method: Literal["deterministic_parser", "rule_based", "agent", "manual"]


class MappingProposal(Contract):
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    concept_id: str | None = Field(default=None, min_length=1)
    relation: MappingRelation
    status: MappingStatus
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def resolved_mapping_has_concept(self) -> Self:
        if (self.status == "resolved") != (self.concept_id is not None):
            raise ValueError("Only a resolved mapping proposal may reference a concept")
        return self


class CandidateAssertion(Contract):
    """A proposed assertion that must never be mistaken for canonical knowledge."""

    candidate_assertion_id: str = Field(min_length=1)
    source_release_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    artifact_sha256: list[Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]] = Field(min_length=1)
    subject_text: str = Field(min_length=1)
    subject_type: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_text: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    polarity: Literal["present", "excluded", "unknown"] = "present"
    population: list[str] = Field(default_factory=list)
    age: str | None = Field(default=None, min_length=1)
    sex: Literal["male", "female", "intersex", "any", "unknown"] | None = None
    context: str | None = Field(default=None, min_length=1)
    temporality: str | None = Field(default=None, min_length=1)
    onset: str | None = Field(default=None, min_length=1)
    duration: str | None = Field(default=None, min_length=1)
    severity: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    laterality: Literal["left", "right", "bilateral", "midline", "unspecified"] | None = None
    frequency: Frequency | None = None
    quantitative_value: float | None = None
    unit_system: str | None = Field(default=None, min_length=1)
    unit_code: str | None = Field(default=None, min_length=1)
    evidence_family: str = Field(min_length=1)
    dependency_group: str = Field(min_length=1)
    subject_mapping: MappingProposal | None = None
    object_mapping: MappingProposal | None = None
    extraction: ExtractionProvenance
    review_status: CandidateStatus
    reviewer_ids: list[str] = Field(default_factory=list)
    transformation_chain: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def preserve_review_and_quantity_semantics(self) -> Self:
        if self.review_status == "approved" and not self.reviewer_ids:
            raise ValueError("Approved candidate assertions require recorded reviewers")
        if (self.quantitative_value is None) != (self.unit_code is None):
            raise ValueError("Quantitative values and unit codes must be retained together")
        if self.unit_code is not None and self.unit_system is None:
            raise ValueError("A quantitative unit requires its unit system")
        return self

    @property
    def usable(self) -> bool:
        mappings = (self.subject_mapping, self.object_mapping)
        return self.review_status == "approved" and all(
            item is not None
            and item.status == "resolved"
            and item.relation in {"exact", "equivalent"}
            for item in mappings
        )


def make_candidate_assertion_id(
    source_release_id: str,
    source_record_id: str,
    source_locator: str,
    ordinal: int,
) -> str:
    return stable_id(
        "candidate_assertion",
        source_release_id,
        source_record_id,
        source_locator,
        str(ordinal),
    )
