from __future__ import annotations

import hashlib
import io
from pathlib import Path

import japanese_ocr_assets as assets_module
from japanese_ocr_assets import (
    JapaneseOCRAssets,
    ModelAsset,
    ensure_japanese_ocr_assets,
    resolve_japanese_ocr_assets,
    verify_model_asset,
)


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


def test_resolve_assets_uses_local_appdata():
    base = Path("X:/LocalAppData")
    assets = resolve_japanese_ocr_assets(base)
    assert assets.root == base / "CloudHime" / "models" / "japanese-ocr" / "meiki-0.3.1"
    assert assets.detection.parent == assets.root


def test_existing_verified_assets_skip_download(monkeypatch):
    payloads = (b"detect", b"horizontal", b"vertical")
    manifest = _tiny_manifest(payloads)
    root = Path("unused")
    paths = tuple(root / spec.name for spec in manifest)
    assets = JapaneseOCRAssets(root, *paths)

    monkeypatch.setattr(assets_module.Path, "mkdir", lambda *args, **kwargs: None)
    monkeypatch.setattr(assets_module, "verify_model_asset", lambda path, spec: True)
    monkeypatch.setattr(
        assets_module,
        "_download",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("downloaded")),
    )
    progress = []
    assert ensure_japanese_ocr_assets(
        assets,
        manifest=manifest,
        progress_callback=lambda phase, value: progress.append((phase, value)),
    ) == assets
    assert progress[-1] == ("downloading", 80)


def test_download_verifies_then_atomically_promotes(monkeypatch):
    payload = b"model-data"
    spec = _tiny_manifest((payload,))[0]
    destination = Path("tests/_temporary_japanese_ocr_asset.onnx")
    destination.unlink(missing_ok=True)
    destination.with_suffix(destination.suffix + ".part").unlink(missing_ok=True)

    class Response(io.BytesIO):
        status = 200

    monkeypatch.setattr(assets_module.request, "urlopen", lambda *args, **kwargs: Response(payload))
    seen = []
    assets_module._download(spec, destination, seen.append)

    assert destination.read_bytes() == payload
    assert verify_model_asset(destination, spec)
    assert seen[-1] == len(payload)
    assert not destination.with_suffix(destination.suffix + ".part").exists()
    destination.unlink()