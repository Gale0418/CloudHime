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
from ocr_quality import (
    normalize_ocr_text,
    score_ocr_items,
    select_bounded_ocr_rescue_items,
    should_try_bounded_ocr_rescue,
)
from ocr_preprocess import apply_ocr_preprocess


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
    complete: bool = True
    evaluated_sources: int = 0

    @property
    def hit_rate(self) -> float:
        return self.hits / self.cases if self.cases else 0.0


@dataclass(frozen=True)
class RuntimePolicyResult:
    cases: int
    evaluated_cases: int
    evaluated_sources: int
    baseline_hits: int
    selected_hits: int
    adoptions: int
    improvements: int
    regressions: int
    baseline_avg_latency_ms: float
    policy_avg_latency_ms: float
    complete: bool

    @property
    def promotion_safe(self) -> bool:
        return (
            self.complete
            and self.regressions == 0
            and self.selected_hits >= self.baseline_hits
        )

    @property
    def accuracy_promoted(self) -> bool:
        return (
            self.promotion_safe
            and self.improvements > 0
            and self.selected_hits > self.baseline_hits
        )


def choose_best_result(results: Sequence[TrialResult]) -> TrialResult | None:
    complete_results = [result for result in results if result.complete]
    if not complete_results:
        return None
    return max(
        complete_results,
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


def select_bounded_strategies(
    strategies: Sequence[SearchStrategy],
    max_strategies: int | None,
) -> list[SearchStrategy]:
    """Select evenly spaced strategies under an explicit offline budget."""

    available = list(strategies)
    if max_strategies is None:
        return available
    budget = int(max_strategies)
    if budget <= 0:
        raise ValueError("strategy budget must be positive")
    if budget >= len(available):
        return available
    if budget == 1:
        return [available[0]]

    last_index = len(available) - 1
    return [
        available[(position * last_index) // (budget - 1)]
        for position in range(budget)
    ]

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


def _load_image(image_path: Path) -> np.ndarray | None:
    """Decode image bytes so Windows paths containing Unicode remain readable."""

    try:
        encoded = np.frombuffer(image_path.read_bytes(), dtype=np.uint8)
    except OSError:
        return None
    if encoded.size == 0:
        return None
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)

def _prepare_image(image: np.ndarray, strategy: SearchStrategy) -> np.ndarray:
    height, width = image.shape[:2]
    scaled = cv2.resize(
        image,
        (max(1, int(width * strategy.scale)), max(1, int(height * strategy.scale))),
        interpolation=cv2.INTER_CUBIC,
    )
    gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    return apply_ocr_preprocess(
        gray,
        threshold=strategy.threshold,
        preprocess=strategy.preprocess,
    )

def _expected_matches_items(
    expected: Any,
    filtered_items: Sequence[dict[str, Any]],
) -> bool:
    return any(
        _expected_matches(expected, item.get("text", ""))
        for item in filtered_items
    )


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
    evaluated_cases = 0
    evaluated_sources = 0
    cases_by_source: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        source = str(case.get("sample_source", ""))
        cases_by_source.setdefault(source, []).append(case)

    root_path = Path(root)
    total_cases = len(cases)

    for source, source_cases in cases_by_source.items():
        image_path = root_path / source
        image = _load_image(image_path)
        if image is None:
            continue

        start = time.perf_counter()
        prepared = _prepare_image(image, strategy)
        result = backend.recognize(prepared)
        latency_ms = (time.perf_counter() - start) * 1000.0
        raw_items = [
            _line_to_item(line, strategy.scale)
            for line in getattr(result, "lines", [])
        ]
        score, filtered_items = score_ocr_items(raw_items)

        evaluated_sources += 1
        evaluated_cases += len(source_cases)
        hits += sum(
            1
            for case in source_cases
            if _expected_matches_items(case.get("expected"), filtered_items)
        )
        scores.append(score)
        latencies.append(latency_ms)

        if should_prune_strategy(
            current_hits=hits,
            evaluated_cases=evaluated_cases,
            total_cases=total_cases,
            best_hits=best_hits,
            min_cases=min_prune_cases,
        ):
            return TrialResult(
                strategy=strategy,
                cases=evaluated_cases,
                hits=hits,
                avg_score=sum(scores) / len(scores) if scores else 0.0,
                avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
                pruned=True,
                complete=False,
                evaluated_sources=evaluated_sources,
            )

    return TrialResult(
        strategy=strategy,
        cases=evaluated_cases,
        hits=hits,
        avg_score=sum(scores) / len(scores) if scores else 0.0,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        complete=evaluated_cases == total_cases,
        evaluated_sources=evaluated_sources,
    )


def _recognize_strategy_with_backends(
    image: np.ndarray,
    strategy: SearchStrategy,
    backends: Sequence[OCRBackend],
) -> tuple[list[dict[str, Any]], int, float]:
    started = time.perf_counter()
    prepared = _prepare_image(image, strategy)
    best_items: list[dict[str, Any]] = []
    best_score = -1
    for backend in backends:
        try:
            result = backend.recognize(prepared)
        except Exception:
            continue
        raw_items = [
            _line_to_item(line, strategy.scale)
            for line in getattr(result, "lines", [])
        ]
        score, filtered_items = score_ocr_items(raw_items, allow_relaxed=True)
        if filtered_items and (not best_items or score > best_score):
            best_items = filtered_items
            best_score = score
    latency_ms = (time.perf_counter() - started) * 1000.0
    return best_items, best_score, latency_ms


def evaluate_runtime_policy(
    cases: Sequence[dict[str, Any]],
    *,
    backends: Sequence[OCRBackend],
    baseline_strategy: SearchStrategy,
    rescue_strategies: Sequence[SearchStrategy],
    root: str | Path = ".",
) -> RuntimePolicyResult:
    """Replay a fixed strategy profile with production selection and no target leakage."""
    if not backends:
        raise ValueError("runtime policy needs at least one OCR backend")

    cases_by_source: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        source = str(case.get("sample_source", ""))
        cases_by_source.setdefault(source, []).append(case)

    baseline_hits = 0
    selected_hits = 0
    adoptions = 0
    improvements = 0
    regressions = 0
    evaluated_cases = 0
    evaluated_sources = 0
    baseline_latencies: list[float] = []
    policy_latencies: list[float] = []
    root_path = Path(root)

    for source, source_cases in cases_by_source.items():
        image = _load_image(root_path / source)
        if image is None:
            continue

        baseline_items, _baseline_score, baseline_latency = (
            _recognize_strategy_with_backends(
                image,
                baseline_strategy,
                backends,
            )
        )
        selected_items = baseline_items
        policy_latency = baseline_latency

        if should_try_bounded_ocr_rescue(
            baseline_items,
            allow_nonempty=True,
        ):
            best_rescue_items: list[dict[str, Any]] = []
            best_rescue_score = -1
            for strategy in rescue_strategies:
                candidate_items, candidate_score, candidate_latency = (
                    _recognize_strategy_with_backends(
                        image,
                        strategy,
                        backends,
                    )
                )
                policy_latency += candidate_latency
                if candidate_items and (
                    not best_rescue_items or candidate_score > best_rescue_score
                ):
                    best_rescue_items = candidate_items
                    best_rescue_score = candidate_score
            selected_items = select_bounded_ocr_rescue_items(
                baseline_items,
                best_rescue_items,
            )

        if selected_items != baseline_items:
            adoptions += 1

        source_baseline_hits = 0
        source_selected_hits = 0
        for case in source_cases:
            expected = case.get("expected")
            source_baseline_hits += int(
                _expected_matches_items(expected, baseline_items)
            )
            source_selected_hits += int(
                _expected_matches_items(expected, selected_items)
            )
        baseline_hits += source_baseline_hits
        selected_hits += source_selected_hits
        improvements += int(source_selected_hits > source_baseline_hits)
        regressions += int(source_selected_hits < source_baseline_hits)

        evaluated_cases += len(source_cases)
        evaluated_sources += 1
        baseline_latencies.append(baseline_latency)
        policy_latencies.append(policy_latency)

    complete = evaluated_cases == len(cases)
    return RuntimePolicyResult(
        cases=len(cases),
        evaluated_cases=evaluated_cases,
        evaluated_sources=evaluated_sources,
        baseline_hits=baseline_hits,
        selected_hits=selected_hits,
        adoptions=adoptions,
        improvements=improvements,
        regressions=regressions,
        baseline_avg_latency_ms=(
            sum(baseline_latencies) / len(baseline_latencies)
            if baseline_latencies
            else 0.0
        ),
        policy_avg_latency_ms=(
            sum(policy_latencies) / len(policy_latencies)
            if policy_latencies
            else 0.0
        ),
        complete=complete,
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
        if result.complete:
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
    for result in sorted(
        (item for item in results if item.complete),
        key=lambda item: (item.hit_rate, item.avg_score),
        reverse=True,
    )[:8]:
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
    parser.add_argument(
        "--backend",
        default="windows",
        help="OCR backend name or comma-separated runtime chain; defaults to windows.",
    )
    parser.add_argument(
        "--runtime-policy",
        action="store_true",
        help="Evaluate a fixed-profile confidence-aware bounded rescue candidate.",
    )
    parser.add_argument("--runtime-threshold", type=int, default=100)
    parser.add_argument("--runtime-scale", type=float, default=2.0)
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument(
        "--max-strategies",
        type=int,
        default=None,
        help="Optional deterministic budget for offline strategy screening.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = _load_manifest(args.manifest)
    cases = _extract_cases(manifest, max_cases=args.max_cases)
    if not cases:
        raise ValueError("hybrid search needs at least one case with sample_source and expected")

    backend_names = [
        name.strip()
        for name in str(args.backend).split(",")
        if name.strip()
    ]
    backends = discover_backends(backend_names)
    discovered_names = [backend.name for backend in backends]
    missing_names = [name for name in backend_names if name not in discovered_names]
    if missing_names:
        raise ValueError(f"ocr backend unavailable: {','.join(missing_names)}")

    if args.runtime_policy:
        threshold = int(args.runtime_threshold)
        scale = float(args.runtime_scale)
        baseline_strategy = SearchStrategy("binary_invert", threshold, scale)
        rescue_strategies = [
            SearchStrategy("adaptive_invert", threshold, scale),
            SearchStrategy("clahe_otsu_invert", threshold, scale),
        ]
        result = evaluate_runtime_policy(
            cases,
            backends=backends,
            baseline_strategy=baseline_strategy,
            rescue_strategies=rescue_strategies,
        )
        payload = {
            "backends": discovered_names,
            "baseline_strategy": baseline_strategy.name,
            "rescue_strategies": [item.name for item in rescue_strategies],
            "cases": result.cases,
            "evaluated_cases": result.evaluated_cases,
            "evaluated_sources": result.evaluated_sources,
            "baseline_hits": result.baseline_hits,
            "selected_hits": result.selected_hits,
            "adoptions": result.adoptions,
            "improvements": result.improvements,
            "regressions": result.regressions,
            "baseline_avg_latency_ms": result.baseline_avg_latency_ms,
            "policy_avg_latency_ms": result.policy_avg_latency_ms,
            "complete": result.complete,
            "promotion_safe": result.promotion_safe,
            "accuracy_promoted": result.accuracy_promoted,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                "Runtime Policy Summary: "
                f"hits={result.baseline_hits}->{result.selected_hits}/{result.cases} "
                f"adoptions={result.adoptions} "
                f"improvements={result.improvements} "
                f"regressions={result.regressions} "
                f"latency_ms={result.baseline_avg_latency_ms:.2f}"
                f"->{result.policy_avg_latency_ms:.2f} "
                f"complete={str(result.complete).lower()} "
                f"promotion_safe={str(result.promotion_safe).lower()} "
                f"accuracy_promoted={str(result.accuracy_promoted).lower()}"
            )
        return 0 if result.accuracy_promoted else 2

    strategies = select_bounded_strategies(
        build_default_search_space(),
        args.max_strategies,
    )
    results = evaluate_search_space(strategies, cases, backend=backends[0])
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
                        "complete": result.complete,
                        "evaluated_sources": result.evaluated_sources,
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
