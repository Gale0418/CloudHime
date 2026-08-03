"""
tests/test_local_vision_assets.py
----------------------------------
Task 1：真機資產契約 – RED/GREEN 單元測試。

不啟動任何真實模型或子程序；所有 I/O 皆以 tmp_path 操控。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

import local_vision_assets as vision_assets_module
from local_vision_assets import (
    GEMMA_ASSET_REVISION,
    GEMMA_MODEL_SHA256,
    GEMMA_PROJECTOR_SHA256,
    VisionAssetError,
    ensure_vision_model_assets,
    resolve_managed_vision_assets,
    resolve_preferred_vision_assets,
    resolve_vision_assets,
    verify_asset,
)


# ──────────────────────────────────────────────────────────────────────────────
# resolve_vision_assets
# ──────────────────────────────────────────────────────────────────────────────


def test_assets_resolve_from_app_root_not_cwd(tmp_path, monkeypatch):
    """路徑解析必須以 app_root 為基準，不受 cwd 影響。"""
    app = tmp_path / "app"
    monkeypatch.chdir(tmp_path)  # cwd != app_root

    assets = resolve_vision_assets(app)

    assert assets.server_path == app / "runtime" / "llama-server.exe"
    assert assets.model_path == app / "models" / "gemma-3-4b-it.Q4_K_M.gguf"
    assert assets.projector_path == app / "models" / "mmproj-model-f16.gguf"


def test_assets_are_frozen_dataclass(tmp_path):
    """VisionAssets 為 frozen=True，欄位不可修改。"""
    app = tmp_path / "app"

    assets = resolve_vision_assets(app)

    with pytest.raises((AttributeError, TypeError)):
        assets.server_path = Path("/other")  # type: ignore[misc]


def test_assets_paths_are_path_objects(tmp_path):
    """所有欄位都是 pathlib.Path，而非字串。"""
    app = tmp_path / "app"

    assets = resolve_vision_assets(app)

    assert isinstance(assets.server_path, Path)
    assert isinstance(assets.model_path, Path)
    assert isinstance(assets.projector_path, Path)


# ──────────────────────────────────────────────────────────────────────────────
# verify_asset – 大小限制
# ──────────────────────────────────────────────────────────────────────────────


def test_verify_asset_rejects_truncated_file(tmp_path):
    """檔案小於 minimum_bytes 時必須拋出 VisionAssetError，match='asset_too_small'。"""
    path = tmp_path / "mmproj.gguf"
    path.write_bytes(b"short")

    with pytest.raises(VisionAssetError, match="asset_too_small"):
        verify_asset(path, None, minimum_bytes=800_000_000)


def test_verify_asset_raises_when_file_missing(tmp_path):
    """檔案不存在時拋出 VisionAssetError，match='asset_missing'。"""
    path = tmp_path / "nonexistent.gguf"

    with pytest.raises(VisionAssetError, match="asset_missing"):
        verify_asset(path, None, minimum_bytes=0)


def test_verify_asset_passes_large_enough_file(tmp_path):
    """大小符合且不驗證 SHA 時不拋出任何例外。"""
    path = tmp_path / "model.gguf"
    path.write_bytes(b"x" * 100)

    verify_asset(path, None, minimum_bytes=50)  # must not raise


def test_verify_asset_passes_when_minimum_bytes_is_zero(tmp_path):
    """minimum_bytes=0 時，空檔案也應通過。"""
    path = tmp_path / "empty.gguf"
    path.write_bytes(b"")

    verify_asset(path, None, minimum_bytes=0)  # must not raise


# ──────────────────────────────────────────────────────────────────────────────
# verify_asset – SHA-256 驗證
# ──────────────────────────────────────────────────────────────────────────────


def test_verify_asset_accepts_correct_sha256(tmp_path):
    """SHA-256 正確時通過驗證。"""
    content = b"hello gemma vision"
    expected_sha = hashlib.sha256(content).hexdigest()
    path = tmp_path / "model.gguf"
    path.write_bytes(content)

    verify_asset(path, expected_sha, minimum_bytes=0)  # must not raise


def test_verify_asset_rejects_wrong_sha256(tmp_path):
    """SHA-256 不符時拋出 VisionAssetError，match='asset_sha256_mismatch'。"""
    path = tmp_path / "model.gguf"
    path.write_bytes(b"corrupted content")

    with pytest.raises(VisionAssetError, match="asset_sha256_mismatch"):
        verify_asset(path, "0" * 64, minimum_bytes=0)


def test_verify_asset_skips_sha256_when_none(tmp_path):
    """expected_sha256=None 時不執行雜湊計算，不拋出例外。"""
    path = tmp_path / "model.gguf"
    path.write_bytes(b"any content")

    verify_asset(path, None, minimum_bytes=0)  # must not raise


# ──────────────────────────────────────────────────────────────────────────────
# VisionAssetError 本身
# ──────────────────────────────────────────────────────────────────────────────


def test_vision_asset_error_is_exception():
    """VisionAssetError 必須繼承自 Exception。"""
    err = VisionAssetError("asset_missing", path=Path("/some/file.gguf"))
    assert isinstance(err, Exception)


def test_vision_asset_error_str_contains_code():
    """VisionAssetError.__str__() 應包含錯誤代碼。"""
    err = VisionAssetError("asset_too_small", path=Path("/some/file.gguf"), detail="got 5, want 800000000")
    assert "asset_too_small" in str(err)

# ──────────────────────────────────────────────────────────────────────────────
# Store-friendly managed assets
# ──────────────────────────────────────────────────────────────────────────────


def test_managed_assets_put_models_in_local_appdata_and_runtime_in_app(tmp_path):
    app = tmp_path / "app"
    local_appdata = tmp_path / "local"

    assets = resolve_managed_vision_assets(app, local_appdata)

    assert assets.managed is True
    assert assets.server_path == app / "runtime" / "llama-server.exe"
    assert str(assets.model_path).startswith(str(local_appdata.resolve()))
    assert GEMMA_ASSET_REVISION[:8] in str(assets.model_path)
    assert assets.projector_path.parent == assets.model_path.parent


def test_preferred_assets_keep_complete_legacy_install(tmp_path, monkeypatch):
    app = tmp_path / "app"
    legacy = resolve_vision_assets(app)
    complete = {legacy.model_path, legacy.projector_path}
    monkeypatch.setattr(
        vision_assets_module,
        "_has_exact_size",
        lambda path, expected: path in complete,
    )
    selected = resolve_preferred_vision_assets(app, tmp_path / "local")

    assert selected == legacy
    assert selected.managed is False


def test_ensure_legacy_assets_rejects_hash_mismatch(tmp_path, monkeypatch):
    assets = resolve_vision_assets(tmp_path / "app")
    monkeypatch.setattr(
        vision_assets_module,
        "_legacy_receipt_matches",
        lambda assets, local_appdata: False,
    )
    monkeypatch.setattr(
        vision_assets_module,
        "_verify_resolved_assets",
        lambda assets: ["  [ERROR] model_path: asset_sha256_mismatch"],
    )

    with pytest.raises(VisionAssetError, match="legacy_asset_invalid"):
        ensure_vision_model_assets(assets)


def test_ensure_legacy_assets_writes_receipt_after_verification(tmp_path, monkeypatch):
    assets = resolve_vision_assets(tmp_path / "app")
    writes = []
    monkeypatch.setattr(
        vision_assets_module,
        "_legacy_receipt_matches",
        lambda assets, local_appdata: False,
    )
    monkeypatch.setattr(
        vision_assets_module,
        "_verify_resolved_assets",
        lambda assets: [],
    )
    monkeypatch.setattr(
        vision_assets_module,
        "_write_legacy_receipt",
        lambda assets, local_appdata: writes.append((assets, local_appdata)),
    )

    assert ensure_vision_model_assets(assets) is assets
    assert writes == [(assets, None)]

def test_ensure_managed_assets_writes_and_reuses_verification_receipt(tmp_path, monkeypatch):
    assets = resolve_managed_vision_assets(tmp_path / "app", tmp_path / "local")
    calls = []

    def fake_ensure(root, manifest, **kwargs):
        calls.append((root, tuple(manifest)))
        root.mkdir(parents=True, exist_ok=True)
        for spec in manifest:
            path = root / spec.name
            path.write_bytes(b"x")

    # Frozen AssetSpec cannot be patched; use a small manifest with the same paths.
    small_manifest = tuple(
        vision_assets_module.AssetSpec(spec.name, spec.url, spec.sha256, 1)
        for spec in vision_assets_module.GEMMA_ASSET_MANIFEST
    )
    monkeypatch.setattr(vision_assets_module, "GEMMA_ASSET_MANIFEST", small_manifest)
    monkeypatch.setattr(vision_assets_module, "ensure_managed_assets", fake_ensure)

    ensure_vision_model_assets(assets)
    ensure_vision_model_assets(assets)

    assert len(calls) == 1
    assert (assets.model_path.parent / ".verified.json").is_file()

def test_verify_resolved_assets_uses_manifest_sha_and_unpinned_server(
    tmp_path,
    monkeypatch,
):
    assets = vision_assets_module.VisionAssets(
        server_path=tmp_path / "llama-server.exe",
        model_path=tmp_path / "model.gguf",
        projector_path=tmp_path / "projector.gguf",
    )
    calls = []
    monkeypatch.setattr(
        vision_assets_module,
        "verify_asset",
        lambda path, expected_sha256, minimum_bytes: calls.append(
            (path, expected_sha256, minimum_bytes)
        ),
    )

    assert vision_assets_module._verify_resolved_assets(assets) == []
    assert [expected for _, expected, _ in calls] == [
        None,
        GEMMA_MODEL_SHA256,
        GEMMA_PROJECTOR_SHA256,
    ]


def test_write_receipt_uses_process_unique_temp_and_cleans_on_replace_failure(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "receipt"
    root.mkdir()
    small_manifest = tuple(
        vision_assets_module.AssetSpec(spec.name, spec.url, spec.sha256, 1)
        for spec in vision_assets_module.GEMMA_ASSET_MANIFEST
    )
    monkeypatch.setattr(vision_assets_module, "GEMMA_ASSET_MANIFEST", small_manifest)
    for spec in small_manifest:
        (root / spec.name).write_bytes(b"x")

    replaced_from = []
    real_replace = vision_assets_module.os.replace

    def recording_replace(source, destination):
        replaced_from.append(Path(source))
        return real_replace(source, destination)

    monkeypatch.setattr(vision_assets_module.os, "replace", recording_replace)
    vision_assets_module._write_receipt(root)

    assert replaced_from[0].name.startswith(
        f".verified.json.{os.getpid()}."
    )
    assert replaced_from[0].suffix == ".tmp"
    assert not replaced_from[0].exists()

    receipt = root / ".verified.json"
    receipt.unlink()

    def failing_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(vision_assets_module.os, "replace", failing_replace)
    with pytest.raises(OSError, match="replace failed"):
        vision_assets_module._write_receipt(root)

    assert list(root.glob(".verified.json.*.tmp")) == []