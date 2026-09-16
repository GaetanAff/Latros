import hashlib

import httpx
import pytest

from latros.common import LatrosError
from latros.sources.fetch import download


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
