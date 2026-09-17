"""Load either source registry version without guessing from filenames."""

from pathlib import Path
from typing import TypeAlias

import yaml

from latros.common import LatrosError
from latros.sources.registry import Registry
from latros.sources.registry_v2 import RegistryV2

RegistryDocument: TypeAlias = Registry | RegistryV2


def load_registry_document(path: Path) -> RegistryDocument:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LatrosError("Source registry must be a mapping")
    version = payload.get("schema_version", 1)
    if version == 1:
        return Registry.model_validate(payload)
    if version == 2:
        return RegistryV2.model_validate(payload)
    raise LatrosError(f"Unsupported source registry schema_version: {version}")
