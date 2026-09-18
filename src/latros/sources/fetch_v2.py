"""Verified v2 source acquisition with explicit manual-access handling."""

from pathlib import Path
from typing import Any

import httpx

from latros.common import LatrosError, sha256, write_json
from latros.sources.registry_v2 import RegistryArtifactV2, SourcePackageV2


def fetch_source_v2(
    root: Path, source: SourcePackageV2, client: httpx.Client | None = None
) -> dict[str, Any]:
    folder = root / "data/raw" / source.source_id / source.release
    public = [artifact for artifact in source.artifacts if artifact.access_mode == "public_https"]
    manual = [artifact for artifact in source.artifacts if artifact.access_mode == "manual_local"]
    for artifact in manual:
        path = _artifact_path(root, source, artifact)
        if not path.is_file():
            raise LatrosError(
                f"Manual source artifact required at {path}; acquire it under its license"
            )
        if sha256(path) != artifact.sha256:
            raise LatrosError(f"Manual source artifact checksum mismatch: {path}")
    if public and client is None:
        with httpx.Client(follow_redirects=True, timeout=120) as owned:
            return fetch_source_v2(root, source, owned)
    for artifact in public:
        if client is None:  # pragma: no cover - guarded by owned client above
            raise AssertionError("HTTP client required")
        _download(client, artifact, folder / artifact.filename)
    payload = source.model_dump(mode="json")
    payload["files"] = [
        {
            "filename": artifact.filename,
            "sha256": sha256(_artifact_path(root, source, artifact)),
        }
        for artifact in source.artifacts
    ]
    write_json(folder / "manifest.json", payload)
    return payload


def _download(client: httpx.Client, artifact: RegistryArtifactV2, destination: Path) -> None:
    if destination.exists():
        if sha256(destination) != artifact.sha256:
            raise LatrosError(f"Corrupt existing v2 artifact (not overwritten): {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    with client.stream("GET", artifact.source_url) as response:
        response.raise_for_status()
        with part.open("wb") as output:
            for chunk in response.iter_bytes():
                output.write(chunk)
    if sha256(part) != artifact.sha256:
        raise LatrosError(f"SHA-256 mismatch for {artifact.filename}; untrusted .part retained")
    part.replace(destination)


def _artifact_path(root: Path, source: SourcePackageV2, artifact: RegistryArtifactV2) -> Path:
    if artifact.local_path is not None:
        resolved = (root / artifact.local_path).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError as exc:
            raise LatrosError("Artifact local_path escapes the project root") from exc
        return resolved
    return root / "data/raw" / source.source_id / source.release / artifact.filename
