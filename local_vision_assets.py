"""CloudHime 內嵌 Gemma 視覺資產的路徑、下載與完整性契約。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from managed_asset_store import AssetSpec, ensure_managed_assets


_SERVER_REL = Path("runtime") / "llama-server.exe"
_MODEL_REL = Path("models") / "gemma-3-4b-it.Q4_K_M.gguf"
_PROJECTOR_REL = Path("models") / "mmproj-model-f16.gguf"
_SHA256_CHUNK_BYTES = 8 * 1024 * 1024

GEMMA_ASSET_REVISION = "ab31416aceb30cd095cb34cc27eea120940964e4"
GEMMA_MODEL_SIZE = 2_489_758_304
GEMMA_PROJECTOR_SIZE = 851_251_104
GEMMA_MODEL_SHA256 = "882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863"
GEMMA_PROJECTOR_SHA256 = "8c0fb064b019a6972856aaae2c7e4792858af3ca4561be2dbf649123ba6c40cb"
_GEMMA_REPOSITORY = "https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF"
_MANAGED_DIR = Path("CloudHime") / "models" / "gemma-3-4b-it" / f"ggml-org-{GEMMA_ASSET_REVISION[:8]}"
_RECEIPT_NAME = ".verified.json"
_LEGACY_RECEIPT_DIR = Path("CloudHime") / "models"
_LEGACY_RECEIPT_NAME = ".legacy-gemma-3-4b-it.verified.json"
_ASSET_LOCK = threading.Lock()

GEMMA_ASSET_MANIFEST = (
    AssetSpec(
        name="gemma-3-4b-it.Q4_K_M.gguf",
        url=f"{_GEMMA_REPOSITORY}/resolve/{GEMMA_ASSET_REVISION}/gemma-3-4b-it-Q4_K_M.gguf",
        sha256=GEMMA_MODEL_SHA256,
        size=GEMMA_MODEL_SIZE,
    ),
    AssetSpec(
        name="mmproj-model-f16.gguf",
        url=f"{_GEMMA_REPOSITORY}/resolve/{GEMMA_ASSET_REVISION}/mmproj-model-f16.gguf",
        sha256=GEMMA_PROJECTOR_SHA256,
        size=GEMMA_PROJECTOR_SIZE,
    ),
)

ASSET_MINIMUM_BYTES: dict[str, int] = {
    "server_path": 5_000,
    "model_path": 2_000_000_000,
    "projector_path": 800_000_000,
}
ASSET_SHA256: dict[str, Optional[str]] = {
    "server_path": None,
    "model_path": GEMMA_MODEL_SHA256,
    "projector_path": GEMMA_PROJECTOR_SHA256,
}


class VisionAssetError(Exception):
    def __init__(self, code: str, *, path: Path, detail: str = "") -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(self._format())

    def _format(self) -> str:
        message = f"{self.code}: {self.path}"
        return f"{message} ({self.detail})" if self.detail else message


@dataclass(frozen=True)
class VisionAssets:
    server_path: Path
    model_path: Path
    projector_path: Path
    managed: bool = False


def resolve_vision_assets(app_root: Path) -> VisionAssets:
    """解析舊版隨程式模型路徑；保留給既有開發環境與安裝相容。"""
    root = Path(app_root).resolve()
    return VisionAssets(
        server_path=root / _SERVER_REL,
        model_path=root / _MODEL_REL,
        projector_path=root / _PROJECTOR_REL,
    )


def _local_appdata_root(local_appdata: Path | None = None) -> Path:
    if local_appdata is not None:
        return Path(local_appdata).expanduser().resolve()
    configured = os.environ.get("LOCALAPPDATA")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "AppData" / "Local").resolve()


def resolve_managed_vision_assets(
    app_root: Path,
    local_appdata: Path | None = None,
) -> VisionAssets:
    """解析 Store 友善的受管模型路徑；可執行 runtime 仍由套件提供。"""
    app = Path(app_root).resolve()
    model_root = _local_appdata_root(local_appdata) / _MANAGED_DIR
    return VisionAssets(
        server_path=app / _SERVER_REL,
        model_path=model_root / GEMMA_ASSET_MANIFEST[0].name,
        projector_path=model_root / GEMMA_ASSET_MANIFEST[1].name,
        managed=True,
    )


def resolve_preferred_vision_assets(
    app_root: Path,
    local_appdata: Path | None = None,
) -> VisionAssets:
    """快速解析隨程式模型；完整性驗證在背景資產暖身階段執行。"""
    legacy = resolve_vision_assets(app_root)
    if (
        _has_exact_size(legacy.model_path, GEMMA_MODEL_SIZE)
        and _has_exact_size(legacy.projector_path, GEMMA_PROJECTOR_SIZE)
    ):
        return legacy
    return resolve_managed_vision_assets(app_root, local_appdata)


def ensure_vision_model_assets(
    assets: VisionAssets,
    progress_callback=None,
    cancel_event=None,
    opener=None,
) -> VisionAssets:
    """背景驗證模型資產；receipt 可避免後續啟動重算 3.34 GB 雜湊。"""
    if not assets.managed:
        with _ASSET_LOCK:
            if _legacy_receipt_matches(assets, None):
                if progress_callback:
                    progress_callback("checking_assets", 80)
                return assets
            if progress_callback:
                progress_callback("checking_disk", 0)
            failures = _verify_resolved_assets(assets)
            if failures:
                raise VisionAssetError(
                    "legacy_asset_invalid",
                    path=assets.model_path,
                    detail=failures[0].strip(),
                )
            try:
                _write_legacy_receipt(assets, None)
            except OSError:
                # A read-only packaged install may not be able to cache the receipt;
                # the current asset is still verified and can be used this run.
                pass
            if progress_callback:
                progress_callback("checking_assets", 80)
        return assets
    root = assets.model_path.parent
    with _ASSET_LOCK:
        if _receipt_matches(root):
            if progress_callback:
                progress_callback("checking_assets", 80)
            return assets
        if progress_callback:
            progress_callback("checking_disk", 0)
        ensure_managed_assets(
            root,
            GEMMA_ASSET_MANIFEST,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            opener=opener,
        )
        _write_receipt(root)
    return assets


def verify_asset(path: Path, expected_sha256: Optional[str], minimum_bytes: int) -> None:
    if not path.exists():
        raise VisionAssetError("asset_missing", path=path)
    if minimum_bytes > 0:
        actual_bytes = path.stat().st_size
        if actual_bytes < minimum_bytes:
            raise VisionAssetError(
                "asset_too_small",
                path=path,
                detail=f"got {actual_bytes}, want >={minimum_bytes}",
            )
    if expected_sha256 is not None:
        actual_sha = _sha256_file(path)
        if actual_sha != expected_sha256.lower():
            raise VisionAssetError(
                "asset_sha256_mismatch",
                path=path,
                detail=f"got {actual_sha}, want {expected_sha256.lower()}",
            )


def _verify_resolved_assets(assets: VisionAssets) -> list[str]:
    failures = []
    for field_name, path in (
        ("server_path", assets.server_path),
        ("model_path", assets.model_path),
        ("projector_path", assets.projector_path),
    ):
        try:
            verify_asset(
                path,
                ASSET_SHA256[field_name],
                ASSET_MINIMUM_BYTES[field_name],
            )
        except VisionAssetError as exc:
            failures.append(f"  [ERROR] {field_name}: {path} -> {exc.code}")
    return failures


def _has_exact_size(path: Path, expected_size: int) -> bool:
    try:
        return path.is_file() and path.stat().st_size == expected_size
    except OSError:
        return False


def _legacy_receipt_path(local_appdata: Path | None) -> Path:
    return _local_appdata_root(local_appdata) / _LEGACY_RECEIPT_DIR / _LEGACY_RECEIPT_NAME


def _legacy_receipt_matches(assets: VisionAssets, local_appdata: Path | None) -> bool:
    try:
        payload = json.loads(_legacy_receipt_path(local_appdata).read_text(encoding="utf-8"))
        if payload.get("revision") != GEMMA_ASSET_REVISION:
            return False
        entries = payload.get("assets", {})
        for field_name, expected_sha in ASSET_SHA256.items():
            path = getattr(assets, field_name)
            stat = path.stat()
            entry = entries.get(field_name, {})
            if (
                entry.get("path") != str(path.resolve())
                or entry.get("size") != stat.st_size
                or entry.get("mtime_ns") != stat.st_mtime_ns
                or entry.get("sha256") != expected_sha
            ):
                return False
        return True
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def _write_legacy_receipt(assets: VisionAssets, local_appdata: Path | None) -> None:
    receipt = _legacy_receipt_path(local_appdata)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    entries = {}
    for field_name, expected_sha in ASSET_SHA256.items():
        path = getattr(assets, field_name)
        stat = path.stat()
        entries[field_name] = {
            "path": str(path.resolve()),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": expected_sha,
        }
    payload = {"revision": GEMMA_ASSET_REVISION, "assets": entries}
    temporary: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(
            prefix=f"{receipt.name}.{os.getpid()}.",
            suffix=".tmp",
            dir=receipt.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
        os.replace(temporary, receipt)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except (FileNotFoundError, OSError):
                pass



def _receipt_matches(root: Path) -> bool:
    try:
        payload = json.loads((root / _RECEIPT_NAME).read_text(encoding="utf-8"))
        if payload.get("revision") != GEMMA_ASSET_REVISION:
            return False
        entries = payload.get("assets", {})
        for spec in GEMMA_ASSET_MANIFEST:
            path = root / spec.name
            stat = path.stat()
            entry = entries.get(spec.name, {})
            if (
                stat.st_size != spec.size
                or entry.get("size") != stat.st_size
                or entry.get("mtime_ns") != stat.st_mtime_ns
                or entry.get("sha256") != spec.sha256
            ):
                return False
        return True
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def _write_receipt(root: Path) -> None:
    entries = {}
    for spec in GEMMA_ASSET_MANIFEST:
        stat = (root / spec.name).stat()
        entries[spec.name] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": spec.sha256,
        }
    payload = {"revision": GEMMA_ASSET_REVISION, "assets": entries}
    receipt = root / _RECEIPT_NAME
    temporary: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(
            prefix=f"{receipt.name}.{os.getpid()}.",
            suffix=".tmp",
            dir=root,
        )
        temporary = Path(temporary_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
        os.replace(temporary, receipt)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_SHA256_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Verify CloudHime local vision assets.")
    parser.add_argument("--app-root", default=".", help="Application root directory")
    args = parser.parse_args()
    resolved = resolve_preferred_vision_assets(Path(args.app_root))
    failures = _verify_resolved_assets(resolved)
    for field_name, path in (
        ("server_path", resolved.server_path),
        ("model_path", resolved.model_path),
        ("projector_path", resolved.projector_path),
    ):
        if not any(line.startswith(f"  [ERROR] {field_name}:") for line in failures):
            print(f"  [OK] {field_name}: {path} ({path.stat().st_size:,} bytes)")
    if failures:
        print("\n[local_vision_assets] Missing or invalid assets:")
        print("\n".join(failures))
        sys.exit(2)
    print("\n[local_vision_assets] All assets OK.")