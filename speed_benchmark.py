from __future__ import annotations

import argparse
import json
import sys
import time
from collections import OrderedDict
from pathlib import Path
from statistics import mean
from typing import Any, Callable

from ocr_quality import normalize_ocr_text, score_ocr_items, summarize_threshold_candidate
from translation_helpers import (
    build_gemma_multimodal_prompt,
    build_segmented_ocr_payload,
    get_cached_translation,
    parse_segmented_translation_json,
    remember_translation,
)


DEFAULT_MANIFEST = Path("benchmarks") / "ocr_accuracy_cases.json"


def _ensure_console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


def _load_manifest(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    if isinstance(manifest, dict):
        return manifest
    raise ValueError("speed benchmark manifest must be a JSON object")


def _extract_cases(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("speed benchmark manifest must contain a 'cases' list")
    return [case for case in cases if isinstance(case, dict)]


def _case_items(case: dict[str, Any]) -> list[dict[str, Any]]:
    items = case.get("actual") or case.get("actual_items") or case.get("items")
    return items if isinstance(items, list) else []


def _case_text(case: dict[str, Any]) -> str:
    items = _case_items(case)
    if items:
        _, filtered_items = score_ocr_items(items)
        text = summarize_threshold_candidate(filtered_items, max_items=8, max_chars=240)
        if text:
            return text
    expected = case.get("expected")
    if isinstance(expected, list):
        return normalize_ocr_text(expected[0] if expected else "")
    return normalize_ocr_text(expected)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = max(1, int(round(len(sorted_values) * percentile / 100.0)))
    return sorted_values[min(len(sorted_values) - 1, rank - 1)]


def _measure_stage(
    name: str,
    operation: Callable[[], dict[str, Any]],
    *,
    iterations: int,
    warmup: int,
) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for _ in range(max(0, warmup)):
        details = operation()

    samples: list[float] = []
    for _ in range(max(1, iterations)):
        start = time.perf_counter()
        details = operation()
        samples.append((time.perf_counter() - start) * 1000.0)

    return {
        "name": name,
        "iterations": max(1, iterations),
        "avg_ms": mean(samples),
        "p95_ms": _percentile(samples, 95.0),
        "min_ms": min(samples),
        "max_ms": max(samples),
        **details,
    }


def _run_ocr_postprocess(cases: list[dict[str, Any]]) -> dict[str, Any]:
    item_count = 0
    output_chars = 0
    for case in cases:
        items = _case_items(case)
        item_count += len(items)
        _, filtered_items = score_ocr_items(items)
        output_chars += len(summarize_threshold_candidate(filtered_items, max_items=8, max_chars=240))
    return {
        "cases": len(cases),
        "items": item_count,
        "output_chars": output_chars,
    }


def _run_translate_prepare_cache(cases: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [text for text in (_case_text(case) for case in cases) if text]
    payload = build_segmented_ocr_payload(texts)
    prompt = build_gemma_multimodal_prompt(texts)
    fake_response = {
        "segments": [
            {"index": index, "translation": f"translated line {index}"}
            for index, _ in enumerate(texts)
        ]
    }
    parsed = parse_segmented_translation_json(json.dumps(fake_response), len(texts))

    cache: OrderedDict[Any, Any] = OrderedDict()
    for source_text, translated_text in zip(texts, parsed):
        cache_key = ("speed-benchmark", "zh-TW", normalize_ocr_text(source_text))
        remember_translation(cache, cache_key, translated_text, cache_limit=512)
        _ = get_cached_translation(cache, cache_key)

    return {
        "cases": len(cases),
        "texts": len(texts),
        "prompt_chars": len(prompt),
        "payload_chars": len(payload),
        "cache_entries": len(cache),
    }


def _run_render_bubble_layout(cases: list[dict[str, Any]]) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication, QWidget

    from cloudhime_ui import REGION_RENDER_BUBBLE, TransBubble

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.setGeometry(0, 0, 2560, 1440)
    bubbles = []
    try:
        for case in cases:
            text = _case_text(case)
            items = _case_items(case)
            item = items[0] if items else {}
            x = int(item.get("x", 0) or 0)
            y = int(item.get("y", 0) or 0)
            w = max(1, int(item.get("w", 160) or 160))
            h = max(1, int(item.get("h", 48) or 48))
            bubbles.append(
                TransBubble(
                    parent,
                    text,
                    x,
                    y,
                    w,
                    h,
                    "dark",
                    REGION_RENDER_BUBBLE,
                )
            )
        app.processEvents()
        return {
            "cases": len(cases),
            "bubbles": len(bubbles),
            "viewport": "2560x1440",
        }
    finally:
        for bubble in bubbles:
            bubble.close()
            bubble.deleteLater()
        parent.close()
        parent.deleteLater()
        app.processEvents()


def run_benchmark(
    manifest_path: str | Path = DEFAULT_MANIFEST,
    *,
    iterations: int = 5,
    warmup: int = 1,
    max_cases: int | None = None,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    cases = _extract_cases(manifest)
    if max_cases is not None:
        cases = cases[: max(1, int(max_cases))]
    if not cases:
        raise ValueError("speed benchmark needs at least one case")

    stages = [
        _measure_stage(
            "ocr_postprocess",
            lambda: _run_ocr_postprocess(cases),
            iterations=iterations,
            warmup=warmup,
        ),
        _measure_stage(
            "translate_prepare_cache",
            lambda: _run_translate_prepare_cache(cases),
            iterations=iterations,
            warmup=warmup,
        ),
        _measure_stage(
            "render_bubble_layout",
            lambda: _run_render_bubble_layout(cases),
            iterations=iterations,
            warmup=warmup,
        ),
    ]
    return {
        "manifest": str(manifest_path),
        "dataset": manifest.get("dataset", ""),
        "case_count": len(cases),
        "iterations": max(1, iterations),
        "warmup": max(0, warmup),
        "stages": stages,
        "total_avg_ms": sum(stage["avg_ms"] for stage in stages),
    }


def _format_ms(value: float) -> str:
    return f"{value:.3f}ms"


def _print_summary(result: dict[str, Any]) -> None:
    print(
        f"Speed Summary: dataset={result.get('dataset') or '-'} "
        f"cases={result['case_count']} iterations={result['iterations']} warmup={result['warmup']}"
    )
    for stage in result["stages"]:
        details = " ".join(
            f"{key}={value}"
            for key, value in stage.items()
            if key
            not in {
                "name",
                "iterations",
                "avg_ms",
                "p95_ms",
                "min_ms",
                "max_ms",
            }
        )
        print(
            f"- stage={stage['name']} avg={_format_ms(stage['avg_ms'])} "
            f"p95={_format_ms(stage['p95_ms'])} min={_format_ms(stage['min_ms'])} "
            f"max={_format_ms(stage['max_ms'])} {details}".rstrip()
        )
    print(f"Total avg pipeline marker: {_format_ms(result['total_avg_ms'])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CloudHime local speed benchmark CLI")
    parser.add_argument(
        "manifest",
        nargs="?",
        default=str(DEFAULT_MANIFEST),
        help="OCR accuracy manifest path used as the speed workload seed.",
    )
    parser.add_argument("--iterations", type=int, default=5, help="Timed iterations per stage.")
    parser.add_argument("--warmup", type=int, default=1, help="Untimed warmup iterations per stage.")
    parser.add_argument("--max-cases", type=int, default=None, help="Limit cases for a quick smoke run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    _ensure_console_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_benchmark(
        args.manifest,
        iterations=args.iterations,
        warmup=args.warmup,
        max_cases=args.max_cases,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
