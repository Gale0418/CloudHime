"""App-managed assets for the optional Japanese OCR rescue path."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Callable, Iterable
from urllib import request


ProgressCallback = Callable[[str, int], None]


@dataclass(frozen=True)
class ModelAsset:
    name: str
    url: str
    sha256: str
    size: int


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_asset(path: Path, asset: ModelAsset) -> bool:
    return path.is_file() and path.stat().st_size == asset.size and _sha256(path) == asset.sha256


def _download(asset: ModelAsset, destination: Path, on_bytes: Callable[[int], None]) -> None:
    part = destination.with_suffix(destination.suffix + ".part")
    existing = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": "CloudHime/1.0"}
    if 0 < existing < asset.size:
        headers["Range"] = f"bytes={existing}-"
    else:
        existing = 0

    response = request.urlopen(request.Request(asset.url, headers=headers), timeout=30)
    append = existing > 0 and getattr(response, "status", 200) == 206
    if not append:
        existing = 0
    mode = "ab" if append else "wb"
    downloaded = existing
    on_bytes(downloaded)
    with response, part.open(mode) as stream:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            stream.write(chunk)
            downloaded += len(chunk)
            on_bytes(downloaded)
    if part.stat().st_size != asset.size or _sha256(part) != asset.sha256:
        raise JapaneseOCRAssetError(f"asset verification failed: {asset.name}")
    os.replace(part, destination)


def ensure_japanese_ocr_assets(
    assets: JapaneseOCRAssets,
    *,
    manifest: Iterable[ModelAsset] = ASSET_MANIFEST,
    progress_callback: ProgressCallback | None = None,
) -> JapaneseOCRAssets:
    specs = tuple(manifest)
    paths = (assets.detection, assets.horizontal, assets.vertical)
    if len(specs) != len(paths):
        raise ValueError("manifest/path count mismatch")
    assets.root.mkdir(parents=True, exist_ok=True)
    total = sum(spec.size for spec in specs)
    completed = 0

    def report(current: int) -> None:
        if progress_callback:
            progress_callback("downloading", min(80, int((completed + current) * 80 / max(1, total))))

    for spec, path in zip(specs, paths):
        if verify_model_asset(path, spec):
            completed += spec.size
            report(0)
            continue
        _download(spec, path, report)
        completed += spec.size
        report(0)
    return assets
