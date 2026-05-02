from __future__ import annotations

import argparse
import json
import math
from numbers import Real
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from ocr_quality import normalize_ocr_text, score_ocr_items, summarize_threshold_candidate


def _load_manifest(source: str) -> Any:
    if source == "-":
        raw = sys.stdin.buffer.read()
        for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            try:
                decoded = raw.decode(encoding)
            except UnicodeDecodeError:
                continue
            return json.loads(decoded)
        return json.loads(raw.decode())
    path = Path(source)
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _extract_cases(manifest: Any) -> list[dict[str, Any]]:
    if isinstance(manifest, list):
        return [case for case in manifest if isinstance(case, dict)]
    if isinstance(manifest, dict):
        if isinstance(manifest.get("cases"), list):
            return [case for case in manifest["cases"] if isinstance(case, dict)]
        return [manifest]
    raise ValueError("manifest must be a JSON object or array")


def _normalize_for_compare(text: Any) -> str:
    normalized = normalize_ocr_text(text)
    normalized = "".join(normalized.split())
    return normalized.strip().lower()


def _render_expected(expected: Any) -> str:
    if isinstance(expected, list):
        return " | ".join(str(item) for item in expected)
    return str(expected or "")


def _expected_matches(expected: Any, actual_text: str) -> bool:
    actual_norm = _normalize_for_compare(actual_text)
    if isinstance(expected, list):
        expected_values = [_normalize_for_compare(item) for item in expected]
        return bool(actual_norm) and actual_norm in expected_values
    return bool(actual_norm) and _normalize_for_compare(expected) == actual_norm


def _render_actual_text(filtered_items: list[dict[str, Any]]) -> str:
    summary = summarize_threshold_candidate(filtered_items, max_items=8, max_chars=240)
    return summary.replace("\n", " / ")


def _get_case_value(case: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in case:
            return case[key]
    return None


def _get_numeric_case_value(case: dict[str, Any], *keys: str) -> float | None:
    value = _get_case_value(case, *keys)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_timing_ms(case: dict[str, Any]) -> float | None:
    value = _get_numeric_case_value(case, "timing_ms", "elapsed_ms", "duration_ms", "latency_ms")
    if value is not None:
        return value
    timing = case.get("timing")
    if isinstance(timing, dict):
        return _get_numeric_case_value(timing, "ms", "elapsed_ms", "duration_ms", "latency_ms")
    return None


def _format_text_value(value: Any) -> str:
    text = str(value or "").strip()
    return text or "-"


def _format_timing_value(value: float | None) -> str:
    if value is None:
        return "-"
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}ms"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = max(1, math.ceil(len(sorted_values) * (percentile / 100.0)))
    index = min(len(sorted_values) - 1, rank - 1)
    return sorted_values[index]


def _process_case(case: dict[str, Any]) -> dict[str, Any]:
    category = _format_text_value(_get_case_value(case, "category", "suite", "type"))
    sample_source = _format_text_value(_get_case_value(case, "sample_source", "source", "dataset", "origin"))
    note = _format_text_value(_get_case_value(case, "note", "notes", "comment"))
    backend = str(_get_case_value(case, "backend", "ocr_backend") or "")
    preprocess = str(_get_case_value(case, "preprocess", "preprocessing", "variant") or "")
    expected = _get_case_value(case, "expected", "expected_text", "target")
    actual_items = _get_case_value(case, "actual", "actual_items", "items", "raw_items")
    if not isinstance(actual_items, list):
        raise ValueError("each case needs an OCR item list in 'actual' (or 'actual_items')")
    score, filtered_items = score_ocr_items(actual_items)
    actual_text = _render_actual_text(filtered_items)
    hit = _expected_matches(expected, actual_text)
    return {
        "category": category,
        "sample_source": sample_source,
        "note": note,
        "backend": backend,
        "preprocess": preprocess,
        "expected": _render_expected(expected),
        "actual": actual_text,
        "score": score,
        "hit": hit,
        "timing_ms": _get_timing_ms(case),
    }


def _print_row(index: int, result: dict[str, Any]) -> None:
    hit_label = "是" if result["hit"] else "否"
    print(
        f"[{index}] category={result['category'] or '-'} "
        f"source={result['sample_source'] or '-'} "
        f"note={result['note'] or '-'} "
        f"timing_ms={_format_timing_value(result['timing_ms'])} "
        f"backend={result['backend'] or '-'} "
        f"preprocess={result['preprocess'] or '-'} "
        f"expected={result['expected'] or '-'} "
        f"actual={result['actual'] or '-'} "
        f"score={result['score']} "
        f"命中={hit_label}"
    )


def _print_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    hits = sum(1 for result in results if result["hit"])
    scored = [result["score"] for result in results if isinstance(result["score"], Real)]
    timings = [result["timing_ms"] for result in results if isinstance(result["timing_ms"], Real)]
    avg_score = (sum(scored) / len(scored)) if scored else 0.0
    pass_rate = (hits / total * 100.0) if total else 0.0
    avg_timing = (sum(timings) / len(timings)) if timings else None
    p95_timing = _percentile(timings, 95.0)
    timing_bits = []
    if avg_timing is not None:
        timing_bits.append(f"avg_timing_ms={avg_timing:.2f}")
    if p95_timing is not None:
        timing_bits.append(f"p95_timing_ms={p95_timing:.2f}")
    timing_suffix = f" {' '.join(timing_bits)}" if timing_bits else ""
    print(
        f"Summary: {hits}/{total} 通過，通過率={pass_rate:.1f}% ，平均分={avg_score:.2f}{timing_suffix}"
    )

    categories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        categories[result["category"]].append(result)
        grouped[(result["backend"], result["preprocess"])].append(result)

    print("Categories:")
    for category, items in sorted(categories.items(), key=lambda pair: pair[0] or "-"):
        category_hits = sum(1 for item in items if item["hit"])
        category_scores = [item["score"] for item in items if isinstance(item["score"], Real)]
        category_timing = [item["timing_ms"] for item in items if isinstance(item["timing_ms"], Real)]
        category_avg = (sum(category_scores) / len(category_scores)) if category_scores else 0.0
        category_rate = (category_hits / len(items) * 100.0) if items else 0.0
        category_timing_avg = (sum(category_timing) / len(category_timing)) if category_timing else None
        category_timing_p95 = _percentile(category_timing, 95.0)
        timing_bits = []
        if category_timing_avg is not None:
            timing_bits.append(f"avg_timing_ms={category_timing_avg:.2f}")
        if category_timing_p95 is not None:
            timing_bits.append(f"p95_timing_ms={category_timing_p95:.2f}")
        timing_label = f" {' '.join(timing_bits)}" if timing_bits else ""
        print(
            f"- category={category or '-'} count={len(items)} "
            f"hit_rate={category_rate:.1f}% avg_score={category_avg:.2f}{timing_label}"
        )

    print("Variants:")
    for (backend, preprocess), items in sorted(grouped.items(), key=lambda pair: (pair[0][0], pair[0][1])):
        variant_hits = sum(1 for item in items if item["hit"])
        variant_scores = [item["score"] for item in items if isinstance(item["score"], Real)]
        variant_avg = (sum(variant_scores) / len(variant_scores)) if variant_scores else 0.0
        variant_rate = (variant_hits / len(items) * 100.0) if items else 0.0
        variant_timing = [item["timing_ms"] for item in items if isinstance(item["timing_ms"], Real)]
        variant_timing_avg = (sum(variant_timing) / len(variant_timing)) if variant_timing else None
        variant_timing_p95 = _percentile(variant_timing, 95.0)
        timing_bits = []
        if variant_timing_avg is not None:
            timing_bits.append(f"avg_timing_ms={variant_timing_avg:.2f}")
        if variant_timing_p95 is not None:
            timing_bits.append(f"p95_timing_ms={variant_timing_p95:.2f}")
        timing_label = f" {' '.join(timing_bits)}" if timing_bits else ""
        print(
            f"- backend={backend or '-'} preprocess={preprocess or '-'} "
            f"count={len(items)} hit_rate={variant_rate:.1f}% avg_score={variant_avg:.2f}{timing_label}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OCR benchmark CLI")
    parser.add_argument("manifest", help="JSON manifest path, or '-' for stdin")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest = _load_manifest(args.manifest)
    cases = _extract_cases(manifest)
    if not cases:
        print("No benchmark cases found.", file=sys.stderr)
        return 1

    results = [_process_case(case) for case in cases]
    for index, result in enumerate(results, start=1):
        _print_row(index, result)
    _print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
