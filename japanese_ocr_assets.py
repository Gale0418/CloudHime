"""App-managed assets for the optional Japanese OCR rescue path."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable, Iterable

from managed_asset_store import (
    AssetSpec,
    ensure_managed_assets,
    verify_managed_asset,
)


ProgressCallback = Callable[[str, int], None]
ModelAsset = AssetSpec


@dataclass(frozen=True)
class JapaneseOCRAssets:
    root: Path
    detection: Path
    horizontal: Path
    vertical: Path


ASSET_VERSION = "meiki-0.3.1"
ASSET_MANIFEST = (
    ModelAsset(
        "meiki.text.detect.v0.1.960x544.onnx",
        "https://huggingface.co/rtr46/meiki.text.detect.v0/resolve/a9cffa4f60cbf72ddb87edf19c6f98a01cd042e6/meiki.text.detect.v0.1.960x544.onnx",
        "40b6a016667745cae7d3055929ae3b8b1e7716aac795f5904cd3c2c7c3b8404b",
        14_503_825,
    ),
    ModelAsset(
        "meiki.text.rec.v0.960x32.onnx",
        "https://huggingface.co/rtr46/meiki.txt.recognition.v0/resolve/a28cf5874dc2438ebb1c86336be26bcec51e3375/meiki.text.rec.v0.960x32.onnx",
        "3e96bc772fbee9717e536a6353032bb944c3382dd2f6960ef4890decda43b000",
        18_593_254,
    ),
    ModelAsset(
        "meiki.text.rec.v0.vertical.32x480.onnx",
        "https://huggingface.co/rtr46/meiki.txt.recognition.v0/resolve/a28cf5874dc2438ebb1c86336be26bcec51e3375/meiki.text.rec.v0.vertical.32x480.onnx",
        "2c2a83a23bc3b7e6c63962175f507ecc6c5e85cc174f17bdec37d9bbd0bf895a",
        12_872_961,
    ),
)


class JapaneseOCRAssetError(RuntimeError):
    pass


def resolve_japanese_ocr_assets(local_appdata: str | Path | None = None) -> JapaneseOCRAssets:
    base = Path(local_appdata or os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    root = base / "CloudHime" / "models" / "japanese-ocr" / ASSET_VERSION
    return JapaneseOCRAssets(
        root=root,
        detection=root / ASSET_MANIFEST[0].name,
        horizontal=root / ASSET_MANIFEST[1].name,
        vertical=root / ASSET_MANIFEST[2].name,
    )


def verify_model_asset(path: Path, asset: ModelAsset) -> bool:
    return verify_managed_asset(path, asset)


def ensure_japanese_ocr_assets(
    assets: JapaneseOCRAssets,
    *,
    manifest: Iterable[ModelAsset] = ASSET_MANIFEST,
    progress_callback: ProgressCallback | None = None,
    cancel_event: Any = None,
    opener: Callable[[Any], Any] | None = None,
) -> JapaneseOCRAssets:
    specs = tuple(manifest)
    paths = (assets.detection, assets.horizontal, assets.vertical)
    if len(specs) != len(paths):
        raise ValueError("manifest/path count mismatch")

    def report(phase: str, percent: int) -> None:
        if progress_callback:
            progress_callback(
                "downloading" if phase == "verifying" else phase,
                percent,
            )

    try:
        ensure_managed_assets(
            assets.root,
            specs,
            progress_callback=report if progress_callback else None,
            cancel_event=cancel_event,
            opener=opener,
        )
    except ValueError as exc:
        raise JapaneseOCRAssetError(str(exc)) from exc
    return assets
