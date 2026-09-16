"""Downloads are transactional per artifact and always verified against the registry."""

from pathlib import Path
from typing import Any

import httpx

from latros.common import LatrosError, sha256, write_json
from latros.sources.registry import Artifact, Source


def download(client: httpx.Client, artifact: Artifact, destination: Path) -> None:
    if destination.exists():
        if sha256(destination) != artifact.sha256:
            raise LatrosError(f"Corrupt existing raw artifact (not overwritten): {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    # A rerun resumes the batch; interrupted artifacts restart cleanly, never append blindly.
    with client.stream("GET", artifact.url) as response:
        response.raise_for_status()
        with part.open("wb") as output:
            for chunk in response.iter_bytes():
                output.write(chunk)
    if sha256(part) != artifact.sha256:
        raise LatrosError(f"SHA-256 mismatch for {artifact.filename}; untrusted .part retained")
    part.replace(destination)


def fetch_source(root: Path, source: Source, client: httpx.Client | None = None) -> dict[str, Any]:
    if source.authentication_required:
        raise LatrosError("Authenticated downloads are not supported in this tranche")
    if source.license.redistribution == "unknown":
        raise LatrosError("Review source license before downloading")
    folder = root / "data" / "raw" / source.id / source.release
    if client is None:
        with httpx.Client(follow_redirects=True, timeout=120) as owned:
            return fetch_source(root, source, owned)
    for artifact in source.artifacts:
        download(client, artifact, folder / artifact.filename)
    manifest = source.model_dump(mode="json")
    manifest["files"] = [
        {"filename": a.filename, "sha256": sha256(folder / a.filename)} for a in source.artifacts
    ]
    write_json(folder / "manifest.json", manifest)
    return manifest
