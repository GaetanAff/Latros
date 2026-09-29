"""Versioned local session and internal transport contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from latros.clinical.v2 import ClinicalCaseV2
from latros.sources.registry import Contract
from latros.ui.patient_context import PatientContext
from latros.ui.refinements import RefinementAnswer


class SessionSelection(Contract):
    snapshot_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SessionRunReference(Contract):
    run_id: str = Field(min_length=1)
    operation: Literal["diagnose", "question"]
    created_at: datetime
    receipt_id: str = Field(min_length=1)


class ConsultationWorkflow(Contract):
    workflow_version: Literal[1] = 1
    phase: Literal["general", "rare"] = "general"
    rare_opted_in_at: datetime | None = None
    general_run: SessionRunReference | None = None
    rare_run: SessionRunReference | None = None


class ResearchSession(Contract):
    schema_version: Literal[1] = 1
    session_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=120)
    created_at: datetime
    updated_at: datetime
    revision: int = Field(ge=0)
    selection: SessionSelection | None = None
    clinical_case: ClinicalCaseV2
    latest_diagnose: SessionRunReference | None = None
    latest_question: SessionRunReference | None = None
    run_counter: int = Field(default=0, ge=0)
    consultation: ConsultationWorkflow | None = None
    patient_context: PatientContext | None = None
    refinement_answers: list[RefinementAnswer] = Field(default_factory=list)


class StoredRun(Contract):
    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    operation: Literal["diagnose", "question"]
    created_at: datetime
    session_revision: int = Field(ge=0)
    selection: SessionSelection
    clinical_case: ClinicalCaseV2
    result: dict[str, Any]


class CreateSessionRequest(Contract):
    display_name: str = Field(default="Nouvelle session R&D", min_length=1, max_length=120)


class SelectionRequest(Contract):
    revision: int = Field(ge=0)
    snapshot_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)


class CaseRequest(Contract):
    revision: int = Field(ge=0)
    clinical_case: ClinicalCaseV2


class RunRequest(Contract):
    revision: int = Field(ge=0)


class QuestionAnswerRequest(Contract):
    revision: int = Field(ge=0)
    question_run_id: str = Field(min_length=1)
    answer: Literal["present", "absent", "unknown", "not_assessed", "unable_to_assess"]


class ErrorDocument(Contract):
    error: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: list[dict[str, Any]] = Field(default_factory=list)
