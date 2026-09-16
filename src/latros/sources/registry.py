from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from latros.common import LatrosError, safe_id


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class License(Contract):
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    redistribution: Literal["allowed_with_attribution", "restricted", "unknown"]
    notes: str = ""


class Artifact(Contract):
    filename: str
    product: str
    format: Literal["obographs-json", "orphadata-product4-xml"]
    language: Literal["en", "fr"]
    url: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @field_validator("filename")
    @classmethod
    def filename_is_safe(cls, value: str) -> str:
        return safe_id(value)

    @field_validator("url")
    @classmethod
    def immutable_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Public HTTPS source URL required")
        if any(x in parsed.path.lower().split("/") for x in ("latest", "main", "master")):
            raise ValueError("Pin a release tag or commit, not a moving branch/latest URL")
        if parsed.query or parsed.fragment:
            raise ValueError("Credentials and query parameters are not permitted in source URLs")
        return value


class Source(Contract):
    id: str
    role: list[str] = Field(min_length=1)
    homepage: str
    release: str
    release_date: str
    license: License
    authentication_required: bool = False
    upstream_dependencies: list[str]
    artifacts: list[Artifact] = Field(min_length=1)

    @field_validator("id", "release")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if value.lower() in {"latest", "main", "master"}:
            raise ValueError("An explicit release is required")
        return safe_id(value)

    @model_validator(mode="after")
    def unique_files(self) -> Self:
        if len({a.filename for a in self.artifacts}) != len(self.artifacts):
            raise ValueError("Duplicate artifact filename")
        return self


class Registry(Contract):
    schema_version: Literal[1] = 1
    sources: list[Source] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        if len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("Duplicate source identifier")
        return self

    def source(self, source_id: str, release: str) -> Source:
        for source in self.sources:
            if (source.id, source.release) == (source_id, release):
                return source
        raise LatrosError(f"Source/release not pinned in registry: {source_id}/{release}")


def load_registry(path: Path) -> Registry:
    return Registry.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
