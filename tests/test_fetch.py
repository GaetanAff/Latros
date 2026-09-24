import hashlib

import httpx
import pytest

from latros.common import LatrosError
from latros.sources.fetch import download
from latros.sources.fetch_v2 import fetch_source_v2
from latros.sources.registry_v2 import SourcePackageV2


def test_download_reuses_valid_artifact(registry, tmp_path):
    payload = b"synthetic content"
    artifact = (
        registry.sources[0]
        .artifacts[0]
        .model_copy(update={"sha256": hashlib.sha256(payload).hexdigest()})
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=payload)

    target = tmp_path / "new/hp.json"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        download(client, artifact, target)
        download(client, artifact, target)
    assert target.read_bytes() == payload
    assert len(calls) == 1


def test_wrong_hash_never_published(registry, tmp_path):
    target = tmp_path / "bad.json"
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"bad"))
    ) as c:
        with pytest.raises(LatrosError, match="SHA-256"):
            download(c, registry.sources[0].artifacts[0], target)
    assert not target.exists()
    assert target.with_suffix(".json.part").exists()


def test_restart_interrupted_artifact(registry, tmp_path):
    payload = b"complete synthetic data"
    artifact = (
        registry.sources[0]
        .artifacts[0]
        .model_copy(update={"sha256": hashlib.sha256(payload).hexdigest()})
    )

    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"partial"
            raise httpx.ReadError("interrupted")

    target = tmp_path / "download.json"
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=BrokenStream()))
    ) as c:
        with pytest.raises(httpx.ReadError):
            download(c, artifact, target)
    assert not target.exists()
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=payload))
    ) as c:
        download(c, artifact, target)
    assert target.read_bytes() == payload
    assert not target.with_suffix(".json.part").exists()


def test_corrupt_existing_file_not_overwritten(registry, tmp_path):
    target = tmp_path / "existing.json"
    target.write_bytes(b"corrupt")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("must not download"))
    ) as c:
        with pytest.raises(LatrosError, match="not overwritten"):
            download(c, registry.sources[0].artifacts[0], target)
    assert target.read_bytes() == b"corrupt"


def _v2_source(payload: bytes, access_mode: str) -> SourcePackageV2:
    return SourcePackageV2.model_validate(
        {
            "source_id": "invented-v2-source",
            "producer": "Latros tests",
            "roles": ["synthetic_test_data"],
            "code_system": "urn:latros:test-v2",
            "homepage": "https://example.test/invented-v2/test-1",
            "release": "test-1",
            "release_date": "2026-09-01",
            "access_date": "2026-09-17",
            "importer": "latros.tests.synthetic_v2",
            "license": {
                "name": "Synthetic fixture",
                "url": "https://example.test/licenses/synthetic-v2",
                "attribution": "Invented by Latros tests",
                "redistribution": "allowed_with_attribution",
                "implementation_rights_confirmed": True,
                "transformation_rights": "allowed",
                "restrictions": [],
            },
            "dependencies": [],
            "artifacts": [
                {
                    "filename": "concepts.tsv",
                    "product": "Invented fixture",
                    "format": "rf2-concepts-tsv",
                    "language": "en",
                    "source_url": "https://example.test/releases/test-1/concepts.tsv",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "access_mode": access_mode,
                }
            ],
        }
    )


def test_v2_manual_source_requires_pre_staged_verified_file(tmp_path):
    payload = b"invented manual fixture"
    source = _v2_source(payload, "manual_local")
    with pytest.raises(LatrosError, match="Manual source artifact required"):
        fetch_source_v2(tmp_path, source)

    path = tmp_path / "data/raw/invented-v2-source/test-1/concepts.tsv"
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    manifest = fetch_source_v2(tmp_path, source)
    assert manifest["files"][0]["sha256"] == hashlib.sha256(payload).hexdigest()


def test_v2_public_source_download_is_verified(tmp_path):
    payload = b"invented public fixture"
    source = _v2_source(payload, "public_https")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=payload))
    ) as client:
        manifest = fetch_source_v2(tmp_path, source, client)

    assert manifest["files"][0]["filename"] == "concepts.tsv"
