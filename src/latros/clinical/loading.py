"""Explicit dispatch between the legacy and versioned clinical case contracts."""

from typing import Any, TypeAlias

import orjson

from latros.clinical.models import ClinicalCase
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError

ClinicalCaseDocument: TypeAlias = ClinicalCase | ClinicalCaseV2


def load_clinical_case(value: bytes | str | dict[str, Any]) -> ClinicalCaseDocument:
    payload: Any = orjson.loads(value) if isinstance(value, (bytes, str)) else value
    if not isinstance(payload, dict):
        raise LatrosError("Clinical case must be a JSON object")
    version = payload.get("schema_version")
    if version is None:
        return ClinicalCase.model_validate(payload)
    if version == 2:
        return ClinicalCaseV2.model_validate(payload)
    raise LatrosError(f"Unsupported clinical case schema_version: {version!r}")
