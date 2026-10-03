"""手動開發資產準備；runtime 必須提供固定版本、來源 commit 與 SHA-256。"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess

from local_vision_assets import (ASSET_MINIMUM_BYTES, ASSET_SHA256, GEMMA_ASSET_MANIFEST,
                                 resolve_vision_assets, verify_asset)
from managed_asset_store import download_managed_asset, verify_managed_asset


def pinned_runtime_url(tag: str, asset: str) -> str:
    """拒絕浮動別名與路徑片段；不查詢 latest release。"""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tag) or tag.lower() in {
        "latest", "main", "master", "nightly",
    }:
        raise ValueError("runtime_tag_must_be_pinned")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.zip", asset):
        raise ValueError("runtime_asset_must_be_zip_name")
    return f"https://github.com/ggml-org/llama.cpp/releases/download/{tag}/{asset}"


def fetch_runtime(root: Path, tag: str, asset: str, sha256: str,
                  source_commit: str, *, backend: str = "cuda", force: bool = False) -> None:
    url = pinned_runtime_url(tag, asset)
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", sha256):
        raise ValueError("runtime_sha256_required")
    if not re.fullmatch(r"[0-9A-Fa-f]{7,64}", source_commit):
        raise ValueError("runtime_source_commit_required")
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise RuntimeError("PowerShell is required for the verified runtime fetcher")
    command = [shell, "-NoLogo", "-NoProfile", "-File",
               str(root / "packaging" / "fetch_runtime_assets.ps1"),
               "-ArchiveUrl", url, "-ExpectedSha256", sha256,
               "-SourceCommit", source_commit, "-Backend", backend,
               "-OutputRuntimeDir", str(root / "runtime")]
    if force:
        command.append("-Force")
    # Shared fetcher checks the archive before extraction and writes provenance.
    subprocess.run(command, check=True)


def ensure_projector(root: Path) -> Path:
    spec = GEMMA_ASSET_MANIFEST[1]
    destination = root / "models" / spec.name
    if not verify_managed_asset(destination, spec):
        # Pinned revision, size and SHA-256; promote only after verification.
        download_managed_asset(spec, destination)
    verify_asset(destination, spec.sha256, ASSET_MINIMUM_BYTES["projector_path"])
    return destination


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-tag", required=True)
    parser.add_argument("--runtime-asset", required=True,
                        help="Pinned ZIP containing llama-server and required DLLs")
    parser.add_argument("--runtime-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--backend", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--force", action="store_true", help="Explicitly replace existing runtime")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    fetch_runtime(root, args.runtime_tag, args.runtime_asset, args.runtime_sha256,
                  args.source_commit, backend=args.backend, force=args.force)
    ensure_projector(root)
    assets = resolve_vision_assets(root)
    for field in ("server_path", "model_path", "projector_path"):
        verify_asset(getattr(assets, field), ASSET_SHA256[field], ASSET_MINIMUM_BYTES[field])
    print("Pinned runtime and model assets verified successfully.")


if __name__ == "__main__":
    main()
