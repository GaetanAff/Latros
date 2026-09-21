"""Machine-readable manifest contract for canonical-v2 knowledge snapshots."""

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from latros.sources.registry import Contract
from latros.sources.registry_v2 import SnapshotScopeV2, SourcePackageV2


class SnapshotTableV2(Contract):
    rows: int = Field(ge=0)
    logical_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parquet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class KnowledgeSnapshotManifestV2(Contract):
    schema_version: Literal[2] = 2
    canonical_schema_version: Literal[2] = 2
    snapshot: str = Field(min_length=1)
    latros_version: str = Field(min_length=1)
    build_pipeline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duckdb_version: str = Field(min_length=1)
    scope: SnapshotScopeV2
    sources: list[SourcePackageV2] = Field(min_length=1)
    source_dependencies: list[dict[str, Any]]
    evidence_families: list[dict[str, Any]]
    rules: dict[str, str]
    tables: dict[str, SnapshotTableV2]
    compatible_profiles: list[str] = Field(min_length=1)
    redistribution: Literal["allowed_with_attribution", "restricted", "prohibited"]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_status: Literal["unreviewed"] | None = None
    intended_use: Literal["local_research_only"] | None = None
    clinical_validation: bool | None = None
    human_review_complete: bool | None = None
    publishable: bool | None = None
    research_override_used: bool = False
    unreviewed_assertion_ids: list[str] = Field(default_factory=list)
    unreviewed_mapping_ids: list[str] = Field(default_factory=list)
    reviewer_count: int | None = Field(default=None, ge=0)
    limitations: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def publication_is_complete(self) -> Self:
        if self.errors:
            raise ValueError("A published snapshot manifest cannot contain errors")
        if not self.tables:
            raise ValueError("A published snapshot manifest requires canonical tables")
        research_fields_present = any(
            value is not None
            for value in (
                self.validation_status,
                self.intended_use,
                self.clinical_validation,
                self.human_review_complete,
                self.publishable,
                self.reviewer_count,
            )
        ) or bool(self.unreviewed_assertion_ids or self.unreviewed_mapping_ids)
        if self.snapshot.endswith("-dev-unreviewed") and not (
            research_fields_present or self.research_override_used
        ):
            raise ValueError("A *-dev-unreviewed snapshot must declare research safeguards")
        if research_fields_present or self.research_override_used:
            if not self.snapshot.endswith("-dev-unreviewed"):
                raise ValueError(
                    "Unreviewed research metadata requires a *-dev-unreviewed snapshot"
                )
            if (
                self.validation_status != "unreviewed"
                or self.intended_use != "local_research_only"
                or self.clinical_validation is not False
                or self.human_review_complete is not False
                or self.publishable is not False
                or not self.research_override_used
            ):
                raise ValueError("Unreviewed research manifest safeguards are incomplete")
            if not self.unreviewed_assertion_ids or not self.unreviewed_mapping_ids:
                raise ValueError("Unreviewed research manifest must list pending items")
        return self
