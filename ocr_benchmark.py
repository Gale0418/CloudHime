from __future__ import annotations

import argparse
import json
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


def _process_case(case: dict[str, Any]) -> dict[str, Any]:
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
        "backend": backend,
        "preprocess": preprocess,
        "expected": _render_expected(expected),
        "actual": actual_text,
        "score": score,
        "hit": hit,
    }


def _print_row(index: int, result: dict[str, Any]) -> None:
    hit_label = "是" if result["hit"] else "否"
    print(
        f"[{index}] backend={result['backend'] or '-'} "
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
    avg_score = (sum(scored) / len(scored)) if scored else 0.0
    pass_rate = (hits / total * 100.0) if total else 0.0
    print(
        f"Summary: {hits}/{total} 通過，通過率={pass_rate:.1f}% ，平均分={avg_score:.2f}"
    )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[(result["backend"], result["preprocess"])].append(result)

    print("Variants:")
    for (backend, preprocess), items in sorted(grouped.items(), key=lambda pair: (pair[0][0], pair[0][1])):
        variant_hits = sum(1 for item in items if item["hit"])
        variant_scores = [item["score"] for item in items if isinstance(item["score"], Real)]
        variant_avg = (sum(variant_scores) / len(variant_scores)) if variant_scores else 0.0
        variant_rate = (variant_hits / len(items) * 100.0) if items else 0.0
        print(
            f"- backend={backend or '-'} preprocess={preprocess or '-'} "
            f"count={len(items)} hit_rate={variant_rate:.1f}% avg_score={variant_avg:.2f}"
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
