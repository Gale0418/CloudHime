"""Resource lifetime regression tests for the real asset downloader, using tiny streams."""
import hashlib
import io
from pathlib import Path
import threading

import pytest

from managed_asset_store import AssetSpec, AssetDownloadCancelled, download_managed_asset


def spec(data=b"model"):
    return AssetSpec("small.gguf", "https://example.invalid/small", hashlib.sha256(data).hexdigest(), len(data))


class Response(io.BytesIO):
    status = 200


@pytest.mark.parametrize("failure", ["progress", "status", "disk"])
def test_response_closes_on_pre_read_error(tmp_path, failure, monkeypatch):
    response = Response(b"model")
    if failure == "status":
        response.status = "not-a-status"
    def progress(_):
        if failure == "progress":
            raise RuntimeError("callback failed")
    if failure == "disk":
        original = Path.open
        def open_file(path, *a, **kw):
            if path.name.endswith(".part"):
                raise PermissionError("not writable")
            return original(path, *a, **kw)
        monkeypatch.setattr(Path, "open", open_file)
    with pytest.raises((ValueError, RuntimeError, PermissionError)):
        download_managed_asset(spec(), tmp_path / "small.gguf", byte_progress=progress,
                               opener=lambda _: response)
    assert response.closed
    assert not (tmp_path / "small.gguf").exists()


def test_normal_download_is_verified_and_promoted(tmp_path):
    response = Response(b"model")
    destination = tmp_path / "small.gguf"
    assert download_managed_asset(spec(), destination, opener=lambda _: response) == destination
    assert destination.read_bytes() == b"model"
    assert response.closed
    assert not destination.with_suffix(".gguf.part").exists()


def test_bad_digest_never_replaces_existing_destination(tmp_path):
    response = Response(b"wrong")
    destination = tmp_path / "small.gguf"
    destination.write_bytes(b"old-good-file")
    with pytest.raises(ValueError, match="asset verification failed"):
        download_managed_asset(spec(), destination, opener=lambda _: response)
    assert destination.read_bytes() == b"old-good-file"
    assert response.closed


def test_cancel_after_open_closes_stream_and_does_not_promote(tmp_path):
    response = Response(b"model")
    cancelled = threading.Event()
    def opener(_):
        cancelled.set()
        return response
    with pytest.raises(AssetDownloadCancelled):
        download_managed_asset(spec(), tmp_path / "small.gguf", cancel_event=cancelled, opener=opener)
    assert response.closed
    assert not (tmp_path / "small.gguf").exists()
