"""Compatibility adapter around semantic_v1; its mathematics remains in Engine."""

import re
from typing import Literal

from pydantic import Field

from latros.clinical.loading import ClinicalCaseDocument
from latros.clinical.models import ClinicalCase, Observation, QuestionAnswer, Status
from latros.clinical.v2 import ClinicalCaseV2, PhenotypeObservation, QuantityValue
from latros.common import LatrosError
from latros.reasoning.engine import Engine
from latros.reasoning.interfaces import (
    CandidateAssessment,
    CandidateSet,
    ExplanationDocument,
    QuestionSelection,
    ReasoningStrategyDescriptor,
)
from latros.reasoning.questions import next_question
from latros.sources.registry import Contract

HPO_SYSTEM = "http://purl.obolibrary.org/obo/hp.owl"


class IgnoredClinicalInput(Contract):
    input_id: str = Field(min_length=1)
    input_kind: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class SemanticV1Projection(Contract):
    case: ClinicalCase
    source_contract: Literal["clinical_case_v1", "clinical_case_v2"]
    used_observation_ids: list[str] = Field(default_factory=list)
    ignored_inputs: list[IgnoredClinicalInput] = Field(default_factory=list)
    proposal_count: int = Field(ge=0, default=0)


SEMANTIC_V1_DESCRIPTOR = ReasoningStrategyDescriptor(
    strategy_id="semantic_v1",
    strategy_version="1",
    accepted_case_versions=[1, 2],
    accepted_observation_types=["phenotype"],
    accepted_relations=["has_sign"],
    score_scale_id="semantic_v1.compatibility",
    score_kind="compatibility",
    candidate_generation="HPO ancestry intersection from confirmed present phenotypes",
    question_strategy="question_v1",
    explanation_strategy="semantic_v1 legacy evidence",
)


class SemanticV1Adapter:
    descriptor = SEMANTIC_V1_DESCRIPTOR

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def project(self, case: ClinicalCaseDocument) -> SemanticV1Projection:
        if isinstance(case, ClinicalCase):
            return SemanticV1Projection(case=case, source_contract="clinical_case_v1")
        return project_v2_for_semantic_v1(case)

    def generate(self, case: ClinicalCaseDocument) -> CandidateSet:
        projection = self.project(case)
        ranked = self.engine.rank(projection.case)
        return CandidateSet(
            strategy_id=self.descriptor.strategy_id,
            candidate_ids=[item["_key"] for item in ranked],
            generation_details={"candidate_count": len(ranked)},
        )

    def score(
        self, case: ClinicalCaseDocument, candidates: CandidateSet
    ) -> list[CandidateAssessment]:
        if candidates.strategy_id != self.descriptor.strategy_id:
            raise LatrosError("Candidate set belongs to another strategy")
        allowed = set(candidates.candidate_ids)
        ranked = [
            item for item in self.engine.rank(self.project(case).case) if item["_key"] in allowed
        ]
        return [
            CandidateAssessment(
                candidate_id=item["_key"],
                rank=rank,
                score=item["score"],
                scale_id=self.descriptor.score_scale_id,
                details={key: value for key, value in item.items() if key != "_key"},
            )
            for rank, item in enumerate(ranked, start=1)
        ]

    def next(self, case: ClinicalCaseDocument) -> QuestionSelection:
        return QuestionSelection(
            strategy_id=self.descriptor.strategy_id,
            payload=next_question(self.engine, self.project(case).case),
        )

    def build(
        self, case: ClinicalCaseDocument, assessments: list[CandidateAssessment]
    ) -> ExplanationDocument:
        del assessments
        return ExplanationDocument(
            strategy_id=self.descriptor.strategy_id,
            payload=self.engine.diagnose(self.project(case).case),
        )

    def diagnose_legacy(self, case: ClinicalCaseDocument) -> dict[str, object]:
        return self.engine.diagnose(self.project(case).case)


def project_v2_for_semantic_v1(case: ClinicalCaseV2) -> SemanticV1Projection:
    superseded = {item.supersedes for item in case.observations if item.supersedes is not None}
    active = [item for item in case.observations if item.observation_id not in superseded]
    accepted: dict[str, tuple[Status, str]] = {}
    ignored: list[IgnoredClinicalInput] = []
    for item in active:
        if not isinstance(item, PhenotypeObservation):
            ignored.append(
                IgnoredClinicalInput(
                    input_id=item.observation_id,
                    input_kind=item.kind,
                    reason="unsupported_observation_type",
                )
            )
            continue
        coding = item.concept.coding
        if coding.system != HPO_SYSTEM or not re.fullmatch(r"HP:\d{7}", coding.code):
            ignored.append(
                IgnoredClinicalInput(
                    input_id=item.observation_id,
                    input_kind=item.kind,
                    reason="unsupported_or_unresolved_terminology",
                )
            )
            continue
        if coding.code in accepted:
            raise LatrosError(
                "semantic_v1 cannot merge multiple active temporal observations for one HPO concept"
            )
        accepted[coding.code] = (item.clinical_status, item.observation_id)
    question_codes: list[str] = []
    question_answers: list[QuestionAnswer] = []
    for response in case.question_history:
        coding = response.concept.coding
        if coding.system != HPO_SYSTEM or coding.code not in accepted:
            continue
        if coding.code in question_codes:
            raise LatrosError("semantic_v1 cannot project repeated question concepts")
        question_codes.append(coding.code)
        question_answers.append(
            QuestionAnswer(concept_id=coding.code, answer=response.clinical_status)
        )
    if len(question_answers) > 12:
        question_answers = question_answers[:12]
    observations = [
        Observation(concept_id=code, status=status)
        for code, (status, _) in sorted(accepted.items())
        if code not in question_codes
    ]
    return SemanticV1Projection(
        case=ClinicalCase(
            case_id=case.case_id,
            age=_legacy_age(case),
            sex=case.subject_context.sex,
            observations=observations,
            question_history=question_answers,
        ),
        source_contract="clinical_case_v2",
        used_observation_ids=sorted(identifier for _, identifier in accepted.values()),
        ignored_inputs=ignored,
        proposal_count=len(case.observation_proposals),
    )


def _legacy_age(case: ClinicalCaseV2) -> float | None:
    age = case.subject_context.age
    if (
        isinstance(age, QuantityValue)
        and age.comparator == "eq"
        and age.system == "http://unitsofmeasure.org"
        and age.code == "a"
    ):
        return age.value
    return None
