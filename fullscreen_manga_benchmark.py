from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import cv2

from cloudhime_workers import (
    AUTO_THRESHOLD_MAX,
    AUTO_THRESHOLD_MIN,
    OCRWorker,
    SCAN_MODE_FULLSCREEN,
)


DEFAULT_BACKEND_CHAIN = ("windows",)


def _ensure_console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


def _parse_backend_chain(values: Sequence[str] | None) -> list[str]:
    if values is None:
        return list(DEFAULT_BACKEND_CHAIN)

    chain: list[str] = []
    for value in values:
        for name in str(value).split(","):
            name = name.strip()
            if name and name not in chain:
                chain.append(name)
    return chain


def _as_rect(value: Any) -> list[int] | None:
    if value is None:
        return None
    try:
        values = [int(part) for part in value]
    except (TypeError, ValueError):
        return None
    if len(values) != 4:
        return None
    return values


def _normalize_items(items: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "text": str(item.get("text", "") or ""),
                "x": int(item.get("x", 0)),
                "y": int(item.get("y", 0)),
                "w": int(item.get("w", 0)),
                "h": int(item.get("h", 0)),
            }
        )
    return normalized


def _fallback_thresholds(threshold: Any) -> list[int]:
    try:
        base = int(threshold)
    except (TypeError, ValueError):
        base = 100
    return sorted(
        {
            max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, base + offset))
            for offset in (-10, 0, 10)
        }
    )


def _configure_ocr_only_worker(worker: OCRWorker) -> None:
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.auto_threshold_enabled = False
    worker.google_api_key = ""
    worker.use_gemma_translation = False
    worker.gemma_auto_switch_enabled = False
    worker.local_multimodal_enabled = False
    worker.japanese_rescue_enabled = False


def _run_fullscreen_ocr(
    worker: OCRWorker,
    image: Any,
    *,
    grid_recovery: bool = False,
) -> dict[str, Any]:
    detected_page_region = worker.detect_manga_page_region(image)
    page_region = worker.normalize_manga_page_region(image, detected_page_region)
    if page_region:
        ocr_regions = [page_region]
        orientations = [0, 90, 270]
    else:
        ocr_regions = worker.get_ocr_regions(image, page_region=None)
        orientations = [0]

    threshold, items = worker.run_ocr_with_best_threshold(
        image,
        0,
        0,
        ocr_regions,
        None,
        orientations,
    )
    items = _normalize_items(items)
    tile_triggered = False

    # Keep the product's sparse-page fallback: only a detected manga page
    # with at most one OCR item enters the formal 2x3 tile retry.
    if page_region and len(items) <= 1:
        tile_regions = worker.split_region_into_tiles(
            page_region,
            cols=2,
            rows=3,
            overlap=0.10,
        )
        if tile_regions:
            tile_triggered = True
            threshold, items = worker.run_ocr_with_best_threshold(
                image,
                0,
                0,
                tile_regions,
                _fallback_thresholds(threshold),
                orientations,
            )
            items = _normalize_items(items)

    grid_recovery_triggered = False
    grid_recovery_accepted = False
    if grid_recovery and page_region and not tile_triggered:
        recover = getattr(worker, "try_manga_grid_recovery", None)
        if callable(recover) and 2 <= len(items) <= 6:
            grid_recovery_triggered = True
            baseline_items = list(items)
            try:
                threshold, recovered_items = recover(
                    image,
                    tuple(page_region),
                    baseline_items,
                    threshold,
                    [0, 90, 270],
                    0,
                    0,
                )
                recovered_items = _normalize_items(recovered_items)
                if recovered_items != baseline_items:
                    grid_recovery_accepted = True
                items = recovered_items
            except Exception:
                pass

    # Mirror the existing fullscreen multi-region retry without invoking any
    # translation or visual-model path.
    if not page_region and len(ocr_regions) > 1 and len(items) <= 1:
        threshold, items = worker.run_ocr_with_best_threshold(
            image,
            0,
            0,
            [(0, 0, image.shape[1], image.shape[0])],
        )
        items = _normalize_items(items)

    if page_region and len(items) >= 2:
        refine = getattr(worker, "refine_manga_ocr_items", None)
        if callable(refine):
            try:
                items = _normalize_items(refine(image, items, threshold, 0, 0))
            except Exception:
                pass

    return {
        "page_region": _as_rect(page_region),
        "threshold": int(threshold) if threshold is not None else None,
        "items": items,
        "tile_triggered": tile_triggered,
        "grid_recovery_triggered": grid_recovery_triggered,
        "grid_recovery_accepted": grid_recovery_accepted,
    }


def _empty_image_result(image_path: Path, elapsed_ms: float, error: str) -> dict[str, Any]:
    return {
        "image": str(image_path),
        "page_region": None,
        "threshold": None,
        "items": [],
        "item_count": 0,
        "joined_text": "",
        "elapsed_ms": elapsed_ms,
        "tile_triggered": False,
        "grid_recovery_triggered": False,
        "grid_recovery_accepted": False,
        "error": error,
    }


def _process_image(
    worker: OCRWorker,
    image_path: str | Path,
    *,
    grid_recovery: bool = False,
    base_threshold: int = 100,
) -> dict[str, Any]:
    path = Path(image_path)
    started = time.perf_counter()
    if hasattr(worker, "binary_threshold"):
        worker.binary_threshold = int(base_threshold)
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return _empty_image_result(path, elapsed_ms, "image_unreadable")

    try:
        result = _run_fullscreen_ocr(
            worker,
            image,
            grid_recovery=grid_recovery,
        )
        items = result["items"]
        result.update(
            {
                "image": str(path),
                "item_count": len(items),
                "joined_text": "\n".join(
                    item["text"] for item in items if item["text"].strip()
                ),
                "elapsed_ms": (time.perf_counter() - started) * 1000.0,
                "error": "",
            }
        )
        return result
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return _empty_image_result(
            path,
            elapsed_ms,
            f"{type(exc).__name__}: {exc}",
        )


def _is_complete(result: dict[str, Any]) -> bool:
    images = result["images"]
    return bool(images) and all(
        not image["error"] and image["item_count"] > 0
        for image in images
    )


def run_benchmark(
    image_paths: Sequence[str | Path],
    *,
    backend_chain: Sequence[str] | None = None,
    grid_recovery: bool = False,
    base_threshold: int = 100,
) -> dict[str, Any]:
    chain = _parse_backend_chain(backend_chain)
    worker = OCRWorker()
    previous_grid_env = os.environ.get("CLOUDHIME_MANGA_GRID_RECOVERY")
    if grid_recovery:
        os.environ["CLOUDHIME_MANGA_GRID_RECOVERY"] = "1"
    else:
        os.environ.pop("CLOUDHIME_MANGA_GRID_RECOVERY", None)
    try:
        _configure_ocr_only_worker(worker)
        worker.reload_ocr_backends(chain, log=False)
        images = [
            _process_image(
                worker,
                path,
                grid_recovery=grid_recovery,
                base_threshold=base_threshold,
            )
            for path in image_paths
        ]
        if hasattr(worker, "ocr_backends") and not worker.ocr_backends:
            for image in images:
                if not image["error"]:
                    image["error"] = "no_ocr_backend_available"
        result = {
            "backend_chain": chain,
            "image_count": len(images),
            "complete": False,
            "images": images,
        }
        result["complete"] = _is_complete(result)
        return result
    finally:
        try:
            worker.cleanup()
        finally:
            if previous_grid_env is None:
                os.environ.pop("CLOUDHIME_MANGA_GRID_RECOVERY", None)
            else:
                os.environ["CLOUDHIME_MANGA_GRID_RECOVERY"] = previous_grid_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CloudHime 全螢幕漫畫 OCR extraction benchmark"
    )
    parser.add_argument("images", nargs="+", help="一個或多個圖片路徑")
    parser.add_argument(
        "--backend",
        action="append",
        dest="backend_chain",
        help="OCR backend chain；可重複指定或用逗號分隔，預設 windows",
    )
    parser.add_argument(
        "--grid-recovery",
        action="store_true",
        help="啟用 opt-in 漫畫 2x3 網格恢復",
    )
    parser.add_argument(
        "--base-threshold",
        type=int,
        default=100,
        help="每張圖片開始時重設的基準 threshold",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="所有圖片都必須成功擷取至少一個 OCR item，否則回傳非零",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _ensure_console_utf8()
    args = build_parser().parse_args(argv)
    try:
        result = run_benchmark(
            args.images,
            backend_chain=args.backend_chain,
            grid_recovery=args.grid_recovery,
            base_threshold=args.base_threshold,
        )
    except Exception as exc:
        result = {
            "backend_chain": _parse_backend_chain(args.backend_chain),
            "image_count": len(args.images),
            "complete": False,
            "images": [],
            "error": f"{type(exc).__name__}: {exc}",
        }

    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    if args.require_complete and not result.get("complete", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
