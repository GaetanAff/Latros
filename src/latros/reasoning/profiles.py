"""Versioned reasoning configuration, separate from knowledge snapshots."""

import hashlib
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from latros.common import encoded
from latros.sources.registry import Contract


class ScoreScale(Contract):
    scale_id: str = Field(min_length=1)
    kind: Literal["compatibility", "probability", "ordinal"]
    description: str = Field(min_length=1)
    calibrated: bool = False

    @model_validator(mode="after")
    def probability_requires_calibration(self) -> Self:
        if self.kind == "probability" and not self.calibrated:
            raise ValueError("A probability scale requires explicit calibration")
        return self


class ReasoningProfile(Contract):
    schema_version: Literal[1] = 1
    profile_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    accepted_observation_types: list[str] = Field(min_length=1)
    accepted_relations: list[str] = Field(min_length=1)
    score_scale: ScoreScale
    parameters: dict[str, Any] = Field(default_factory=dict)
    aggregation_rules: list[str] = Field(default_factory=list)
    coverage_rules: list[str] = Field(default_factory=list)
    out_of_scope_rules: list[str] = Field(default_factory=list)
    abstention_rules: list[str] = Field(default_factory=list)
    compatible_snapshot_schema_versions: list[int] = Field(min_length=1)
    compatible_snapshot_ids: list[str] = Field(default_factory=list)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def hash_matches_payload(self) -> Self:
        if self.profile_sha256 != reasoning_profile_hash(self):
            raise ValueError("Reasoning profile hash does not match its canonical payload")
        return self

    def accepts_snapshot(self, snapshot_id: str, schema_version: int) -> bool:
        return schema_version in self.compatible_snapshot_schema_versions and (
            not self.compatible_snapshot_ids or snapshot_id in self.compatible_snapshot_ids
        )


def reasoning_profile_hash(profile: ReasoningProfile | dict[str, Any]) -> str:
    if isinstance(profile, ReasoningProfile):
        payload = profile.model_dump(mode="json", exclude={"profile_sha256"})
    else:
        payload = {key: value for key, value in profile.items() if key != "profile_sha256"}
    return hashlib.sha256(encoded(payload)).hexdigest()


def load_reasoning_profile(path: Path) -> ReasoningProfile:
    return ReasoningProfile.model_validate_json(path.read_bytes())
