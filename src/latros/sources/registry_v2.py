"""Versioned source packages for canonical-v2 snapshots.

The v1 registry remains the only input for the historical HPO/Mondo/Orphadata
pipeline.  This module describes public and manually staged inputs without ever
storing credentials.
"""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Self, get_args
from urllib.parse import ParseResult, urlparse

import yaml
from pydantic import Field, field_validator, model_validator

from latros.common import LatrosError, safe_id
from latros.knowledge.models_v2 import RelationType
from latros.sources.registry import Contract

AccessMode = Literal["public_https", "manual_local"]
Redistribution = Literal["allowed_with_attribution", "restricted", "prohibited", "unknown"]
TransformationRights = Literal["allowed", "restricted", "prohibited", "unknown"]
SourceRole = Literal[
    "terminology",
    "clinical_assertion_source",
    "aggregated_knowledge",
    "rare_disease_knowledge",
    "laboratory_terminology",
    "drug_terminology",
    "drug_clinical_knowledge",
    "safety_rule_source",
    "classification",
    "benchmark",
    "synthetic_test_data",
    "curation_metadata",
]
ArtifactFormatV2 = Literal[
    "rf2-concepts-tsv",
    "rf2-descriptions-tsv",
    "rf2-relationships-tsv",
    "curated-assertions-jsonl",
    "obographs-json",
    "html-capture",
    "curation-jsonl",
    "curation-package-json",
    "source-segments-json",
    "medlineplus-health-topics-xml",
    "medlineplus-health-topics-xml-zip",
    "mesh-descriptors-xml",
    "mesh-qualifiers-xml",
    "mesh-supplemental-records-xml",
    "monarch-kg-duckdb",
    "kgx-nodes-tsv-gzip",
    "kgx-edges-tsv-gzip",
    "jsonl-gzip",
    "rdf-ntriples-gzip",
]

_SOURCE_ROLES = set(get_args(SourceRole))


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
    transformation_rights: TransformationRights | None = None
    restrictions: list[str] = Field(default_factory=list)
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
    local_path: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)

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

    @field_validator("local_path")
    @classmethod
    def local_path_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = Path(value)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("Artifact local_path must be a safe relative path")
        return path.as_posix()

    @model_validator(mode="after")
    def local_path_matches_access_mode(self) -> Self:
        if self.local_path is not None and self.access_mode != "manual_local":
            raise ValueError("Only manual_local artifacts may override local_path")
        return self


class SourcePackageV2(Contract):
    source_id: str
    producer: str | None = Field(default=None, min_length=1)
    roles: list[str] = Field(min_length=1)
    code_system: str = Field(min_length=1)
    homepage: str = Field(min_length=1)
    release: str
    release_date: date | None = None
    access_date: date
    importer: str | None = Field(default=None, min_length=1)
    release_identity_method: Literal["publisher_release", "dated_capture"] = "publisher_release"
    capture_identity: str | None = Field(default=None, min_length=1)
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
        if self.release_identity_method == "dated_capture" and self.capture_identity is None:
            raise ValueError("A dated capture requires an explicit capture_identity")
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
        for source in self.sources:
            if source.producer is None:
                raise ValueError(f"Source producer is required: {source.source_id}")
            if source.importer is None:
                raise ValueError(f"Source importer is required: {source.source_id}")
            if source.license.transformation_rights is None:
                raise ValueError(f"Source transformation rights are required: {source.source_id}")
            unknown_roles = set(source.roles) - _SOURCE_ROLES
            if unknown_roles:
                raise ValueError(
                    f"Unknown source roles for {source.source_id}: {sorted(unknown_roles)}"
                )
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
