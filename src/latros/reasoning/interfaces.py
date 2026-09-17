"""Composable reasoning boundaries; strategies declare rather than imply capabilities."""

from typing import Any, Literal, Protocol

from pydantic import Field

from latros.clinical.loading import ClinicalCaseDocument
from latros.sources.registry import Contract


class ReasoningStrategyDescriptor(Contract):
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    accepted_case_versions: list[int] = Field(min_length=1)
    accepted_observation_types: list[str] = Field(min_length=1)
    accepted_relations: list[str] = Field(min_length=1)
    score_scale_id: str = Field(min_length=1)
    score_kind: Literal["compatibility", "probability", "ordinal"]
    candidate_generation: str = Field(min_length=1)
    question_strategy: str = Field(min_length=1)
    explanation_strategy: str = Field(min_length=1)
    safety_component: Literal["separate"] = "separate"


class CandidateSet(Contract):
    strategy_id: str = Field(min_length=1)
    candidate_ids: list[str]
    generation_details: dict[str, Any] = Field(default_factory=dict)


class CandidateAssessment(Contract):
    candidate_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    score: float
    scale_id: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class QuestionSelection(Contract):
    strategy_id: str = Field(min_length=1)
    payload: dict[str, Any]


class ExplanationDocument(Contract):
    strategy_id: str = Field(min_length=1)
    payload: dict[str, Any]


class CandidateGenerator(Protocol):
    descriptor: ReasoningStrategyDescriptor

    def generate(self, case: ClinicalCaseDocument) -> CandidateSet: ...


class ScoringStrategy(Protocol):
    descriptor: ReasoningStrategyDescriptor

    def score(
        self, case: ClinicalCaseDocument, candidates: CandidateSet
    ) -> list[CandidateAssessment]: ...


class QuestionStrategy(Protocol):
    descriptor: ReasoningStrategyDescriptor

    def next(self, case: ClinicalCaseDocument) -> QuestionSelection: ...


class ExplanationBuilder(Protocol):
    descriptor: ReasoningStrategyDescriptor

    def build(
        self, case: ClinicalCaseDocument, assessments: list[CandidateAssessment]
    ) -> ExplanationDocument: ...
