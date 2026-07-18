from __future__ import annotations

import hashlib
import io
from pathlib import Path
import shutil
from threading import Event

import pytest

import japanese_ocr_assets as assets_module
from japanese_ocr_assets import (
    ASSET_MANIFEST,
    ASSET_VERSION,
    JapaneseOCRAssets,
    ModelAsset,
    ensure_japanese_ocr_assets,
    resolve_japanese_ocr_assets,
    verify_model_asset,
)
from managed_asset_store import AssetDownloadCancelled


TEST_ROOT = Path(__file__).with_name("_japanese_ocr_assets_test_data")


@pytest.fixture(autouse=True)
def _cleanup_test_root():
    yield
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


class _Response(io.BytesIO):
    def __init__(self, payload: bytes, status: int = 200):
        super().__init__(payload)
        self.status = status


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


def _assets_for(root: Path, manifest) -> JapaneseOCRAssets:
    paths = tuple(root / spec.name for spec in manifest)
    return JapaneseOCRAssets(root, *paths)


def _delegate_to_shared_core(monkeypatch, opener, *, cancel_event=None):
    real_ensure = assets_module.ensure_managed_assets

    def offline_ensure(root, manifest, **kwargs):
        kwargs["minimum_free_bytes"] = 0
        kwargs["opener"] = opener
        if cancel_event is not None:
            kwargs["cancel_event"] = cancel_event
        return real_ensure(root, manifest, **kwargs)

    monkeypatch.setattr(assets_module, "ensure_managed_assets", offline_ensure)


def _clean(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)
    if TEST_ROOT.is_dir() and not any(TEST_ROOT.iterdir()):
        TEST_ROOT.rmdir()


def test_asset_contract_is_pinned():
    assert ASSET_VERSION == "meiki-0.3.1"
    assert tuple(
        (spec.name, spec.url, spec.sha256, spec.size)
        for spec in ASSET_MANIFEST
    ) == (
        (
            "meiki.text.detect.v0.1.960x544.onnx",
            "https://huggingface.co/rtr46/meiki.text.detect.v0/resolve/"
            "a9cffa4f60cbf72ddb87edf19c6f98a01cd042e6/"
            "meiki.text.detect.v0.1.960x544.onnx",
            "40b6a016667745cae7d3055929ae3b8b1e7716aac795f5904cd3c2c7c3b8404b",
            14_503_825,
        ),
        (
            "meiki.text.rec.v0.960x32.onnx",
            "https://huggingface.co/rtr46/meiki.txt.recognition.v0/resolve/"
            "a28cf5874dc2438ebb1c86336be26bcec51e3375/"
            "meiki.text.rec.v0.960x32.onnx",
            "3e96bc772fbee9717e536a6353032bb944c3382dd2f6960ef4890decda43b000",
            18_593_254,
        ),
        (
            "meiki.text.rec.v0.vertical.32x480.onnx",
            "https://huggingface.co/rtr46/meiki.txt.recognition.v0/resolve/"
            "a28cf5874dc2438ebb1c86336be26bcec51e3375/"
            "meiki.text.rec.v0.vertical.32x480.onnx",
            "2c2a83a23bc3b7e6c63962175f507ecc6c5e85cc174f17bdec37d9bbd0bf895a",
            12_872_961,
        ),
    )


def test_resolve_assets_uses_local_appdata():
    base = Path("X:/LocalAppData")
    assets = resolve_japanese_ocr_assets(base)
    assert assets.root == base / "CloudHime" / "models" / "japanese-ocr" / "meiki-0.3.1"
    assert assets.detection.parent == assets.root


def test_ensure_fresh_tiny_manifest_is_offline_and_promotes_files(monkeypatch):
    payloads = (b"detect", b"horizontal", b"vertical")
    manifest = _tiny_manifest(payloads)
    root = TEST_ROOT / "fresh"
    assets = _assets_for(root, manifest)
    requests = []
    progress = []

    def opener(request):
        requests.append((request.full_url, request.headers.get("Range")))
        index = int(request.full_url.rsplit("/", 1)[1])
        return _Response(payloads[index])

    _delegate_to_shared_core(monkeypatch, opener)

    assert ensure_japanese_ocr_assets(
        assets,
        manifest=manifest,
        progress_callback=lambda phase, value: progress.append((phase, value)),
    ) == assets
    assert [path.read_bytes() for path in (assets.detection, assets.horizontal, assets.vertical)] == list(payloads)
    assert requests == [(spec.url, None) for spec in manifest]
    assert list(root.glob("*.part")) == []
    assert progress[-1] == ("downloading", 80)


def test_existing_verified_tiny_manifest_is_cache_hit_without_opening(monkeypatch):
    payloads = (b"detect", b"horizontal", b"vertical")
    manifest = _tiny_manifest(payloads)
    root = TEST_ROOT / "cache"
    assets = _assets_for(root, manifest)
    root.mkdir(parents=True)
    for spec, payload in zip(manifest, payloads):
        (root / spec.name).write_bytes(payload)

    def opener(request):
        pytest.fail("verified cache hit must not open a URL")

    _delegate_to_shared_core(monkeypatch, opener)

    assert ensure_japanese_ocr_assets(assets, manifest=manifest) == assets
    assert list(root.glob("*.part")) == []


def test_corrupt_tiny_asset_is_redownloaded_by_shared_core(monkeypatch):
    payloads = (b"detect", b"horizontal", b"vertical")
    manifest = _tiny_manifest(payloads)
    root = TEST_ROOT / "corrupt"
    assets = _assets_for(root, manifest)
    root.mkdir(parents=True)
    assets.detection.write_bytes(payloads[0])
    assets.horizontal.write_bytes(b"corrupt")
    assets.vertical.write_bytes(payloads[2])
    requests = []

    def opener(request):
        requests.append(request.full_url)
        assert request.full_url == manifest[1].url
        return _Response(payloads[1])

    _delegate_to_shared_core(monkeypatch, opener)

    assert ensure_japanese_ocr_assets(assets, manifest=manifest) == assets
    assert assets.horizontal.read_bytes() == payloads[1]
    assert requests == [manifest[1].url]
    assert not assets.horizontal.with_suffix(".onnx.part").exists()


def test_wrapper_delegation_preserves_part_resume_policy(monkeypatch):
    payloads = (b"detect", b"horizontal", b"vertical")
    manifest = _tiny_manifest(payloads)
    root = TEST_ROOT / "partial"
    assets = _assets_for(root, manifest)
    root.mkdir(parents=True)
    assets.detection.write_bytes(payloads[0])
    assets.vertical.write_bytes(payloads[2])
    part = assets.horizontal.with_suffix(assets.horizontal.suffix + ".part")
    part.write_bytes(payloads[1][:3])
    requests = []

    def opener(request):
        requests.append(request.headers.get("Range"))
        assert request.full_url == manifest[1].url
        return _Response(payloads[1][3:], status=206)

    _delegate_to_shared_core(monkeypatch, opener)

    assert ensure_japanese_ocr_assets(assets, manifest=manifest) == assets
    assert assets.horizontal.read_bytes() == payloads[1]
    assert not part.exists()
    assert requests == ["bytes=3-"]


def test_wrapper_delegation_preserves_cancelled_part_policy(monkeypatch):
    payloads = (b"cancel-me", b"second", b"third")
    payload = payloads[0]
    manifest = _tiny_manifest(payloads)
    root = TEST_ROOT / "cancel"
    assets = _assets_for(root, manifest)
    cancel_event = Event()

    class CancellingResponse(_Response):
        def read(self, size=-1):
            chunk = super().read(2 if size < 0 else min(size, 2))
            if chunk:
                cancel_event.set()
            return chunk

    opener = lambda request: CancellingResponse(payload)

    with pytest.raises(AssetDownloadCancelled):
        ensure_japanese_ocr_assets(
            assets,
            manifest=manifest,
            cancel_event=cancel_event,
            opener=opener,
        )

    assert not assets.detection.exists()
    assert assets.detection.with_suffix(assets.detection.suffix + ".part").exists()


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
