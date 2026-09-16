from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from latros.sources.registry import Contract

HpoId = Annotated[str, Field(pattern=r"^HP:\d{7}$")]
Status = Literal["present", "absent", "unknown"]


class Observation(Contract):
    concept_id: HpoId
    status: Status


class QuestionAnswer(Contract):
    concept_id: HpoId
    answer: Status


class ClinicalCase(Contract):
    case_id: str = Field(min_length=1, max_length=120)
    age: float | None = Field(default=None, ge=0, le=130)
    sex: Literal["male", "female", "intersex", "unknown"] | None = None
    observations: list[Observation] = Field(default_factory=list)
    question_history: list[QuestionAnswer] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def check_observations(self) -> Self:
        ids = [o.concept_id for o in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("One observation per concept; contradictory duplicates are rejected")
        history = [q.concept_id for q in self.question_history]
        if len(history) != len(set(history)):
            raise ValueError("Question history cannot repeat a concept")
        observations = {o.concept_id: o.status for o in self.observations}
        for q in self.question_history:
            if q.concept_id in observations and observations[q.concept_id] != q.answer:
                raise ValueError("Question answer conflicts with observation")
        return self

    def effective_observations(self) -> dict[str, Status]:
        result = {o.concept_id: o.status for o in self.observations}
        result.update({q.concept_id: q.answer for q in self.question_history})
        return result
