"""The developer downloader cannot use floating or unchecked runtime assets."""
from unittest.mock import Mock

import pytest
import download_task5 as downloader


@pytest.mark.parametrize("tag", ["latest", "LATEST", "main", "nightly", "../b123", ""])
def test_floating_or_path_tag_is_rejected_before_fetch(tag, monkeypatch, tmp_path):
    run = Mock()
    monkeypatch.setattr(downloader.subprocess, "run", run)
    with pytest.raises(ValueError, match="pinned"):
        downloader.fetch_runtime(tmp_path, tag, "llama.zip", "a" * 64, "b" * 40)
    run.assert_not_called()


@pytest.mark.parametrize("sha,commit", [("", "b" * 40), ("a" * 63, "b" * 40),
                                        ("z" * 64, "b" * 40), ("a" * 64, "latest")])
def test_missing_integrity_metadata_is_rejected(sha, commit, monkeypatch, tmp_path):
    run = Mock()
    monkeypatch.setattr(downloader.subprocess, "run", run)
    with pytest.raises(ValueError):
        downloader.fetch_runtime(tmp_path, "b123", "llama.zip", sha, commit)
    run.assert_not_called()


def test_pinned_runtime_delegates_verification_without_replacing_existing(monkeypatch, tmp_path):
    monkeypatch.setattr(downloader.shutil, "which", lambda _: "pwsh")
    run = Mock()
    monkeypatch.setattr(downloader.subprocess, "run", run)
    downloader.fetch_runtime(tmp_path, "b123", "llama.zip", "a" * 64, "b" * 40)
    args = run.call_args.args[0]
    assert "https://github.com/ggml-org/llama.cpp/releases/download/b123/llama.zip" in args
    assert args[args.index("-ExpectedSha256") + 1] == "a" * 64
    assert args[args.index("-SourceCommit") + 1] == "b" * 40
    assert "-Force" not in args
    assert run.call_args.kwargs == {"check": True}


@pytest.mark.parametrize("verified", [False, True])
def test_projector_uses_pinned_manifest_and_enforces_digest(monkeypatch, tmp_path, verified):
    spec = downloader.GEMMA_ASSET_MANIFEST[1]
    monkeypatch.setattr(downloader, "verify_managed_asset", lambda *_: verified)
    download, verify = Mock(), Mock()
    monkeypatch.setattr(downloader, "download_managed_asset", download)
    monkeypatch.setattr(downloader, "verify_asset", verify)
    destination = downloader.ensure_projector(tmp_path)
    assert "/resolve/main/" not in spec.url
    verify.assert_called_once_with(destination, spec.sha256,
                                   downloader.ASSET_MINIMUM_BYTES["projector_path"])
    if verified:
        download.assert_not_called()
    else:
        download.assert_called_once_with(spec, destination)


def test_projector_integrity_failure_propagates(monkeypatch, tmp_path):
    monkeypatch.setattr(downloader, "verify_managed_asset", lambda *_: True)
    monkeypatch.setattr(downloader, "verify_asset", Mock(side_effect=ValueError("hash mismatch")))
    with pytest.raises(ValueError, match="hash mismatch"):
        downloader.ensure_projector(tmp_path)


def test_no_arguments_cannot_download_latest(monkeypatch):
    fetch = Mock()
    monkeypatch.setattr(downloader, "fetch_runtime", fetch)
    with pytest.raises(SystemExit) as exc:
        downloader.main([])
    assert exc.value.code == 2
    fetch.assert_not_called()
