"""Deterministic serialization and identifiers shared by the pipeline."""

import hashlib
import re
from pathlib import Path
from typing import Any

import orjson


class LatrosError(ValueError):
    """An actionable data or input error, safe to display in the CLI."""


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value):
        raise LatrosError(f"Invalid identifier: {value!r}")
    return value


def encoded(value: Any) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2) + b"\n"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def stable_id(kind: str, *parts: str) -> str:
    digest = hashlib.sha256(orjson.dumps(parts)).hexdigest()
    return f"{kind}:{digest}"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded(value))
    temporary.replace(path)
