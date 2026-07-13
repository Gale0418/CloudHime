from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import numpy as np

from ocr_backends import OCRBackend, discover_backends
from ocr_quality import normalize_ocr_text, score_ocr_items


DEFAULT_MANIFEST = Path("benchmarks") / "ocr_accuracy_cases.json"
DEFAULT_THRESHOLDS = (70, 90, 110, 130, 150, 170, 190)
DEFAULT_PREPROCESSES = ("gray", "binary_invert", "adaptive_invert", "clahe_otsu_invert")
DEFAULT_SCALES = (1.5, 2.0, 2.5)


@dataclass(frozen=True)
class SearchStrategy:
    preprocess: str
    threshold: int
    scale: float = 2.0

    @property
    def name(self) -> str:
        return f"{self.preprocess}:t{self.threshold}:x{self.scale:g}"


@dataclass(frozen=True)
class TrialResult:
    strategy: SearchStrategy
    cases: int
    hits: int
    avg_score: float
    avg_latency_ms: float
    pruned: bool = False

    @property
    def hit_rate(self) -> float:
        return self.hits / self.cases if self.cases else 0.0


def choose_best_result(results: Sequence[TrialResult]) -> TrialResult | None:
    if not results:
        return None
    return max(
        results,
        key=lambda result: (
            result.hit_rate,
            result.avg_score,
            -result.avg_latency_ms,
            result.hits,
        ),
    )


def should_prune_strategy(
    *,
    current_hits: int,
    evaluated_cases: int,
    total_cases: int,
    best_hits: int,
    min_cases: int = 3,
) -> bool:
    if evaluated_cases < max(1, min_cases):
        return False
    remaining = max(0, total_cases - evaluated_cases)
    return current_hits + remaining < best_hits


def build_default_search_space(
    *,
    thresholds: Sequence[int] = DEFAULT_THRESHOLDS,
    preprocesses: Sequence[str] = DEFAULT_PREPROCESSES,
    scales: Sequence[float] = DEFAULT_SCALES,
) -> list[SearchStrategy]:
    strategies: list[SearchStrategy] = []
    for preprocess in preprocesses:
        for scale in scales:
            for threshold in thresholds:
                strategies.append(
                    SearchStrategy(
                        preprocess=str(preprocess),
                        threshold=int(threshold),
                        scale=float(scale),
                    )
                )
    return strategies


def _load_manifest(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("hybrid search manifest must be a JSON object")
    return payload


def _extract_cases(manifest: dict[str, Any], *, max_cases: int | None = None) -> list[dict[str, Any]]:
    cases = [case for case in manifest.get("cases", []) if isinstance(case, dict)]
    cases = [case for case in cases if case.get("sample_source") and case.get("expected") is not None]
    if max_cases is not None:
        cases = cases[: max(1, int(max_cases))]
    return cases


def _normalize_for_compare(text: Any) -> str:
    return "".join(normalize_ocr_text(text).split()).strip().lower()


def _expected_matches(expected: Any, actual_text: str) -> bool:
    actual = _normalize_for_compare(actual_text)
    if not actual:
        return False
    if isinstance(expected, list):
        return actual in {_normalize_for_compare(item) for item in expected}
    return actual == _normalize_for_compare(expected)


def _items_to_text(items: Sequence[dict[str, Any]]) -> str:
    return "\n".join(
        normalize_ocr_text(item.get("text", ""))
        for item in items
        if normalize_ocr_text(item.get("text", ""))
    )


def _line_to_item(line: Any, scale: float) -> dict[str, Any]:
    box = getattr(line, "box", None)
    x = int(getattr(box, "x", 0) / scale) if box is not None else 0
    y = int(getattr(box, "y", 0) / scale) if box is not None else 0
    w = max(1, int(getattr(box, "w", 1) / scale)) if box is not None else 1
    h = max(1, int(getattr(box, "h", 1) / scale)) if box is not None else 1
    return {
        "text": normalize_ocr_text(getattr(line, "text", "") or ""),
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "confidence": getattr(line, "confidence", None),
    }


def _prepare_image(image: np.ndarray, strategy: SearchStrategy) -> np.ndarray:
    height, width = image.shape[:2]
    scaled = cv2.resize(
        image,
        (max(1, int(width * strategy.scale)), max(1, int(height * strategy.scale))),
        interpolation=cv2.INTER_CUBIC,
    )
    gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    if strategy.preprocess == "gray":
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if strategy.preprocess == "binary_invert":
        _, binary = cv2.threshold(gray, strategy.threshold, 255, cv2.THRESH_BINARY)
        return cv2.cvtColor(cv2.bitwise_not(binary), cv2.COLOR_GRAY2BGR)
    if strategy.preprocess == "adaptive_invert":
        adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        return cv2.cvtColor(cv2.bitwise_not(adaptive), cv2.COLOR_GRAY2BGR)
    if strategy.preprocess == "clahe_otsu_invert":
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        _, binary = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.cvtColor(cv2.bitwise_not(binary), cv2.COLOR_GRAY2BGR)
    raise ValueError(f"unknown preprocess: {strategy.preprocess}")


def evaluate_strategy(
    strategy: SearchStrategy,
    cases: Sequence[dict[str, Any]],
    *,
    backend: OCRBackend,
    root: str | Path = ".",
    best_hits: int = 0,
    min_prune_cases: int = 3,
) -> TrialResult:
    hits = 0
    scores: list[int] = []
    latencies: list[float] = []
    evaluated = 0
    root_path = Path(root)
    total_cases = len(cases)

    for case in cases:
        image_path = root_path / str(case.get("sample_source", ""))
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        start = time.perf_counter()
        prepared = _prepare_image(image, strategy)
        result = backend.recognize(prepared)
        latency_ms = (time.perf_counter() - start) * 1000.0
        raw_items = [_line_to_item(line, strategy.scale) for line in getattr(result, "lines", [])]
        score, filtered_items = score_ocr_items(raw_items)
        text = _items_to_text(filtered_items)

        evaluated += 1
        hits += 1 if _expected_matches(case.get("expected"), text) else 0
        scores.append(score)
        latencies.append(latency_ms)

        if should_prune_strategy(
            current_hits=hits,
            evaluated_cases=evaluated,
            total_cases=total_cases,
            best_hits=best_hits,
            min_cases=min_prune_cases,
        ):
            return TrialResult(
                strategy=strategy,
                cases=evaluated,
                hits=hits,
                avg_score=sum(scores) / len(scores) if scores else 0.0,
                avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
                pruned=True,
            )

    return TrialResult(
        strategy=strategy,
        cases=evaluated,
        hits=hits,
        avg_score=sum(scores) / len(scores) if scores else 0.0,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
    )


def evaluate_search_space(
    strategies: Iterable[SearchStrategy],
    cases: Sequence[dict[str, Any]],
    *,
    backend: OCRBackend,
    root: str | Path = ".",
) -> list[TrialResult]:
    results: list[TrialResult] = []
    best_hits = 0
    for strategy in strategies:
        result = evaluate_strategy(strategy, cases, backend=backend, root=root, best_hits=best_hits)
        results.append(result)
        best_hits = max(best_hits, result.hits)
    return results


def _print_summary(results: Sequence[TrialResult]) -> None:
    best = choose_best_result(results)
    if best is None:
        print("No hybrid search results.")
        return
    print(
        "Hybrid Search Summary: "
        f"best={best.strategy.name} "
        f"hit_rate={best.hit_rate:.1%} "
        f"hits={best.hits}/{best.cases} "
        f"avg_score={best.avg_score:.2f} "
        f"avg_latency_ms={best.avg_latency_ms:.2f}"
    )
    for result in sorted(results, key=lambda item: (item.hit_rate, item.avg_score), reverse=True)[:8]:
        suffix = " pruned=true" if result.pruned else ""
        print(
            f"- strategy={result.strategy.name} "
            f"hit_rate={result.hit_rate:.1%} "
            f"hits={result.hits}/{result.cases} "
            f"avg_score={result.avg_score:.2f} "
            f"avg_latency_ms={result.avg_latency_ms:.2f}{suffix}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CloudHime local OCR hybrid search benchmark")
    parser.add_argument("manifest", nargs="?", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--backend", default="windows", help="OCR backend name, defaults to windows.")
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = _load_manifest(args.manifest)
    cases = _extract_cases(manifest, max_cases=args.max_cases)
    if not cases:
        raise ValueError("hybrid search needs at least one case with sample_source and expected")
    backends = discover_backends([args.backend])
    if not backends:
        raise ValueError(f"ocr backend unavailable: {args.backend}")
    results = evaluate_search_space(build_default_search_space(), cases, backend=backends[0])
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "strategy": result.strategy.name,
                        "cases": result.cases,
                        "hits": result.hits,
                        "hit_rate": result.hit_rate,
                        "avg_score": result.avg_score,
                        "avg_latency_ms": result.avg_latency_ms,
                        "pruned": result.pruned,
                    }
                    for result in results
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
