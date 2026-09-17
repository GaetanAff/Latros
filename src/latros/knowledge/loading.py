"""Manifest version dispatch kept outside both immutable storage implementations."""

from pathlib import Path
from typing import Any, TypeAlias

import orjson

from latros.common import LatrosError, safe_id
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.knowledge.store import load_manifest
from latros.knowledge.store_v2 import load_manifest_v2

ManifestDocument: TypeAlias = dict[str, Any] | KnowledgeSnapshotManifestV2


def load_manifest_document(root: Path, snapshot: str) -> ManifestDocument:
    safe_id(snapshot)
    path = root / "manifests" / f"{snapshot}.json"
    if not path.is_file():
        raise LatrosError(f"Snapshot is not published: {snapshot}")
    payload = orjson.loads(path.read_bytes())
    version = payload.get("schema_version") if isinstance(payload, dict) else None
    if version == 1:
        return load_manifest(root, snapshot)
    if version == 2:
        return load_manifest_v2(root, snapshot)
    raise LatrosError(f"Unsupported snapshot manifest schema_version: {version}")
