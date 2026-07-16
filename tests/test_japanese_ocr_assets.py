from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

from japanese_ocr_assets import (
    JapaneseOCRAssets,
    ModelAsset,
    ensure_japanese_ocr_assets,
    resolve_japanese_ocr_assets,
    verify_model_asset,
)


TEST_ROOT = Path(__file__).with_name("_japanese_ocr_assets_test_data")


def _tiny_manifest(payloads):
    return tuple(
        ModelAsset(
            name=f"asset-{index}.onnx",
            url=f"https://example.invalid/{index}",
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
        )
        for index, payload in enumerate(payloads)
    )


def _clean(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)
    if TEST_ROOT.is_dir() and not any(TEST_ROOT.iterdir()):
        TEST_ROOT.rmdir()


def test_resolve_assets_uses_local_appdata():
    base = Path("X:/LocalAppData")
    assets = resolve_japanese_ocr_assets(base)
    assert assets.root == base / "CloudHime" / "models" / "japanese-ocr" / "meiki-0.3.1"
    assert assets.detection.parent == assets.root


def test_existing_verified_assets_skip_download():
    payloads = (b"detect", b"horizontal", b"vertical")
    manifest = _tiny_manifest(payloads)
    root = TEST_ROOT / "skip"
    assets = JapaneseOCRAssets(
        root,
        root / manifest[0].name,
        root / manifest[1].name,
        root / manifest[2].name,
    )
    progress = []
    try:
        root.mkdir(parents=True)
        for spec, payload in zip(manifest, payloads):
            (root / spec.name).write_bytes(payload)

        assert ensure_japanese_ocr_assets(
            assets,
            manifest=manifest,
            progress_callback=lambda phase, value: progress.append((phase, value)),
        ) == assets
        assert progress[-1] == ("downloading", 80)
    finally:
        _clean(root)


def test_verify_model_asset_delegates_to_shared_core():
    payload = b"model-data"
    spec = _tiny_manifest((payload,))[0]
    path = TEST_ROOT / "verify" / spec.name
    try:
        path.parent.mkdir(parents=True)
        path.write_bytes(payload)
        assert verify_model_asset(path, spec)
    finally:
        _clean(path.parent)
