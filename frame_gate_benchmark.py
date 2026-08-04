"""CH-T61 deterministic paired dynamic-sequence contract benchmark.

This benchmark uses a synthetic processor only. It never invokes OCR, a model,
or a remote API. FrameGate remains shadow-only; only ExactImageCache hits reuse
an output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from benchmark_lock import load_lock, validate_benchmark_lock
from exact_image_cache import ExactImageCache
from frame_gate import FrameGate


PROJECT_ROOT = Path(__file__).resolve().parent
LOCK_PATH = PROJECT_ROOT / "benchmarks" / "benchmark_lock.json"
REPEATS = 5
SEQUENCE_NAMES = (
    "baseline",
    "exact_repeat",
    "one_pixel_noise",
    "subtitle_a",
    "subtitle_b_transition",
    "single_frame_subtitle",
    "return_to_background",
)
_CONTEXT = "ch-t61-dynamic-sequence"
_SUBTITLE_VALUES = {64: "subtitle_a", 128: "subtitle_b", 192: "single_frame_subtitle"}


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_dynamic_sequence() -> tuple[tuple[str, np.ndarray], ...]:
    """Build the same seven-frame uint8 sequence on every invocation."""
    background = np.zeros((64, 96, 3), dtype=np.uint8)
    one_pixel_noise = background.copy()
    one_pixel_noise[0, 0, 0] = 1

    def subtitle(value: int) -> np.ndarray:
        frame = background.copy()
        frame[-12:-4, 12:-12] = np.uint8(value)
        return frame

    return (
        ("baseline", background),
        ("exact_repeat", background.copy()),
        ("one_pixel_noise", one_pixel_noise),
        ("subtitle_a", subtitle(64)),
        ("subtitle_b_transition", subtitle(128)),
        ("single_frame_subtitle", subtitle(192)),
        ("return_to_background", background.copy()),
    )


def _synthetic_process(frame: np.ndarray) -> str:
    """Return a deterministic label from synthetic pixels; this is not OCR."""
    marker = int(frame[-8, frame.shape[1] // 2, 0])
    return _SUBTITLE_VALUES.get(marker, "background")


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.95
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _latency_summary(values: list[float], expected: int) -> dict[str, float]:
    return {
        "avg_ms": sum(values) / len(values),
        "p95_ms": _p95(values),
        "coverage": len(values) / expected,
    }


def _timed(action: Any) -> tuple[Any, float]:
    started = time.perf_counter_ns()
    result = action()
    return result, (time.perf_counter_ns() - started) / 1_000_000.0


def run_benchmark() -> dict[str, Any]:
    """Run five paired repeats and return quality, reuse, and timing evidence."""
    lock_status = validate_benchmark_lock(PROJECT_ROOT, LOCK_PATH)
    if not lock_status["ok"]:
        raise RuntimeError(f"benchmark lock validation failed: {lock_status['errors']}")
    lock = load_lock(LOCK_PATH)

    baseline_outputs: list[str] = []
    candidate_outputs: list[str] = []
    baseline_latencies: list[float] = []
    candidate_latencies: list[float] = []
    candidate_frames: list[dict[str, Any]] = []
    classifications: Counter[str] = Counter()
    baseline_process_calls = 0
    candidate_process_calls = 0
    exact_hits = 0
    nonexact_false_skips = 0

    for repeat in range(REPEATS):
        sequence = build_dynamic_sequence()
        for _, frame in sequence:
            output, elapsed = _timed(lambda current=frame: _synthetic_process(current))
            baseline_outputs.append(output)
            baseline_latencies.append(elapsed)
            baseline_process_calls += 1

        cache = ExactImageCache(max_entries=len(sequence), max_bytes=1024 * 1024)
        frame_gate = FrameGate()
        for name, frame in sequence:
            started = time.perf_counter_ns()
            observation = frame_gate.observe(frame, context=_CONTEXT)
            classifications[observation.classification] += 1
            payload = cache.get(frame, _CONTEXT)
            exact_hit = payload is not None
            processed = not exact_hit

            if exact_hit:
                exact_hits += 1
                output = payload.results[0]
            else:
                if observation.skip_ocr:
                    nonexact_false_skips += 1
                output = _synthetic_process(frame)
                candidate_process_calls += 1
                if not cache.put(frame, _CONTEXT, (output,), None, None):
                    raise RuntimeError("synthetic frame did not fit ExactImageCache")

            candidate_latencies.append((time.perf_counter_ns() - started) / 1_000_000.0)
            candidate_outputs.append(output)
            candidate_frames.append(
                {
                    "repeat": repeat + 1,
                    "name": name,
                    "exact_hit": exact_hit,
                    "processed": processed,
                    "frame_gate_skip_ocr": observation.skip_ocr,
                    "shadow_classification": observation.classification,
                }
            )

    expected_frames = REPEATS * len(SEQUENCE_NAMES)
    single_indices = [
        index for index, frame in enumerate(candidate_frames)
        if frame["name"] == "single_frame_subtitle"
    ]
    transition_indices = [
        index for index, frame in enumerate(candidate_frames)
        if frame["name"] in {"subtitle_a", "subtitle_b_transition"}
    ]
    single_hits = sum(candidate_outputs[index] == "single_frame_subtitle" for index in single_indices)
    transition_hits = sum(
        candidate_outputs[index] == ("subtitle_a" if candidate_frames[index]["name"] == "subtitle_a" else "subtitle_b")
        for index in transition_indices
    )

    return {
        "repeats": REPEATS,
        "sequence": list(SEQUENCE_NAMES),
        "output_sequence_equal": baseline_outputs == candidate_outputs,
        "exact_hits": exact_hits,
        "nonexact_false_skips": nonexact_false_skips,
        "single_frame_recall": single_hits / len(single_indices),
        "transition_recall": transition_hits / len(transition_indices),
        "baseline_process_calls": baseline_process_calls,
        "candidate_process_calls": candidate_process_calls,
        "shadow_classification_counts": {
            name: classifications[name]
            for name in ("baseline", "identical", "near", "changed")
        },
        "latency_ms": {
            "baseline": _latency_summary(baseline_latencies, expected_frames),
            "candidate": _latency_summary(candidate_latencies, expected_frames),
        },
        "benchmark_lock_id": lock["lock_id"],
        "manifest_hash": _canonical_hash(lock["datasets"]),
        "condition_hash": _canonical_hash(lock["conditions"]),
        "baseline_outputs": baseline_outputs,
        "candidate_outputs": candidate_outputs,
        "candidate_frames": candidate_frames,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CH-T61 paired FrameGate contract benchmark")
    parser.add_argument("--json", action="store_true", help="emit the complete JSON result")
    return parser


def _print_text(result: dict[str, Any]) -> None:
    print("CH-T61 FrameGate Dynamic Sequence Contract Benchmark")
    for key in (
        "repeats",
        "output_sequence_equal",
        "exact_hits",
        "nonexact_false_skips",
        "single_frame_recall",
        "transition_recall",
        "baseline_process_calls",
        "candidate_process_calls",
        "benchmark_lock_id",
        "manifest_hash",
        "condition_hash",
    ):
        print(f"{key}={result[key]}")
    print(f"shadow_classification_counts={json.dumps(result['shadow_classification_counts'], sort_keys=True)}")
    for condition, metrics in result["latency_ms"].items():
        print(
            f"{condition}: avg_ms={metrics['avg_ms']:.6f} "
            f"p95_ms={metrics['p95_ms']:.6f} coverage={metrics['coverage']:.1f}"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark()
    if args.json:
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    else:
        _print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())