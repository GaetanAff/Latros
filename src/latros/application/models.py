"""Read-only capabilities exposed to local research clients."""

from typing import Literal

from pydantic import Field

from latros.sources.registry import Contract


class SnapshotCapability(Contract):
    snapshot_id: str = Field(min_length=1)
    schema_version: int | None = Field(default=None, ge=1)
    runtime_status: Literal["available", "missing", "corrupt"]
    domain: str | None = None
    population: str | None = None
    validation_status: str | None = None
    intended_use: str | None = None
    clinical_validation: bool | None = None
    human_review_complete: bool | None = None
    publishable: bool | None = None
    research_unreviewed: bool = False
    unreviewed_assertion_count: int = Field(default=0, ge=0)
    unreviewed_mapping_count: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class StrategyCapability(Contract):
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    accepted_case_versions: list[int]
    accepted_observation_types: list[str]
    score_scale_id: str = Field(min_length=1)
    score_kind: Literal["compatibility", "probability", "ordinal"]
    safety_status: Literal["not_evaluated"] = "not_evaluated"


class CompatibleSelection(Contract):
    snapshot_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    available: bool
    reason: str | None = None


class ApplicationCapabilities(Contract):
    snapshots: list[SnapshotCapability]
    strategies: list[StrategyCapability]
    compatible_selections: list[CompatibleSelection]
    offline_only: Literal[True] = True
    telemetry: Literal[False] = False


class ConceptOption(Contract):
    snapshot_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    language: str = Field(min_length=1)
    observation_kind: Literal["phenotype", "symptom", "sign", "exam", "vital"]
