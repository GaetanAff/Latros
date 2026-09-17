"""Versioned source packages for canonical-v2 snapshots.

The v1 registry remains the only input for the historical HPO/Mondo/Orphadata
pipeline.  This module describes public and manually staged inputs without ever
storing credentials.
"""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import ParseResult, urlparse

import yaml
from pydantic import Field, field_validator, model_validator

from latros.common import LatrosError, safe_id
from latros.knowledge.models_v2 import RelationType
from latros.sources.registry import Contract

AccessMode = Literal["public_https", "manual_local"]
Redistribution = Literal["allowed_with_attribution", "restricted", "prohibited", "unknown"]
ArtifactFormatV2 = Literal[
    "rf2-concepts-tsv",
    "rf2-descriptions-tsv",
    "rf2-relationships-tsv",
    "curated-assertions-jsonl",
]


class RegistryDependencyV2(Contract):
    upstream_reference: str = Field(min_length=1)
    dependency_type: Literal[
        "primary", "derived_from", "republication", "shared_upstream", "unknown"
    ]
    evidence: str = Field(min_length=1)


class SnapshotScopeV2(Contract):
    scope_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    population: str = Field(min_length=1)
    observation_types: list[str] = Field(min_length=1)
    relations: list[RelationType] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)


class LicenseV2(Contract):
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    redistribution: Redistribution
    implementation_rights_confirmed: bool
    notes: str = ""

    @field_validator("url")
    @classmethod
    def public_license_url(cls, value: str) -> str:
        _public_https(value)
        return value


class RegistryArtifactV2(Contract):
    filename: str
    product: str = Field(min_length=1)
    format: ArtifactFormatV2
    language: str | None = Field(default=None, min_length=2, max_length=35)
    source_url: str = Field(min_length=1)
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    access_mode: AccessMode

    @field_validator("filename")
    @classmethod
    def filename_is_safe(cls, value: str) -> str:
        return safe_id(value)

    @field_validator("source_url")
    @classmethod
    def immutable_source_url(cls, value: str) -> str:
        parsed = _public_https(value)
        if parsed.query or parsed.fragment:
            raise ValueError("Source URLs must not contain credentials, queries, or fragments")
        if any(part in {"latest", "main", "master"} for part in parsed.path.lower().split("/")):
            raise ValueError("Pin a release, not a moving branch/latest URL")
        return value


class SourcePackageV2(Contract):
    source_id: str
    roles: list[str] = Field(min_length=1)
    code_system: str = Field(min_length=1)
    homepage: str = Field(min_length=1)
    release: str
    release_date: date | None = None
    access_date: date
    license: LicenseV2
    dependencies: list[RegistryDependencyV2] = Field(default_factory=list)
    artifacts: list[RegistryArtifactV2] = Field(min_length=1)

    @field_validator("source_id", "release")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if value.lower() in {"latest", "main", "master"}:
            raise ValueError("An explicit source release is required")
        return safe_id(value)

    @field_validator("homepage")
    @classmethod
    def public_homepage(cls, value: str) -> str:
        _public_https(value)
        return value

    @model_validator(mode="after")
    def unique_artifacts(self) -> Self:
        filenames = [artifact.filename for artifact in self.artifacts]
        if len(set(filenames)) != len(filenames):
            raise ValueError("Duplicate artifact filename")
        if not self.license.implementation_rights_confirmed:
            raise ValueError("Implementation rights must be confirmed before registry publication")
        if self.license.redistribution == "unknown":
            raise ValueError("Source redistribution status must be reviewed")
        return self


class RegistryV2(Contract):
    schema_version: Literal[2] = 2
    canonical_schema_version: Literal[2] = 2
    scope: SnapshotScopeV2
    compatible_profiles: list[str] = Field(min_length=1)
    sources: list[SourcePackageV2] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        identities = [(source.source_id, source.release) for source in self.sources]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate source/release")
        return self

    def source(self, source_id: str, release: str) -> SourcePackageV2:
        for source in self.sources:
            if (source.source_id, source.release) == (source_id, release):
                return source
        raise LatrosError(f"Source/release not pinned in v2 registry: {source_id}/{release}")


def load_registry_v2(path: Path) -> RegistryV2:
    return RegistryV2.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _public_https(value: str) -> ParseResult:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Public HTTPS URL required")
    return parsed
