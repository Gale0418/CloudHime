"""Repeatable CPU-only microbenchmark for ExactImageCache."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from exact_image_cache import ExactImageCache


DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 360
DEFAULT_ITERATIONS = 10
DEFAULT_WARMUP = 2
BENCHMARK_METADATA_HEADROOM = 4 * 1024
_CONTEXT = "exact-image-cache-benchmark"


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def make_synthetic_bgr(width: int, height: int) -> np.ndarray:
    """Create a deterministic BGR uint8 image without external assets."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than zero")
    generator = np.random.default_rng(0)
    return generator.integers(
        0,
        256,
        size=(int(height), int(width), 3),
        dtype=np.uint8,
    )


def make_one_pixel_miss(image: np.ndarray) -> np.ndarray:
    """Return an image differing from image at exactly one BGR channel."""
    miss = np.array(image, copy=True, order="C")
    miss[0, 0, 0] = np.uint8((int(miss[0, 0, 0]) + 1) % 256)
    return miss


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.95
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _measure(
    action: Callable[[], Any],
    *,
    iterations: int,
    warmup: int,
    bytes_count: int,
    prepare: Callable[[], Any] | None = None,
) -> dict[str, float | int]:
    for _ in range(warmup):
        if prepare is not None:
            prepare()
        action()

    samples: list[float] = []
    for _ in range(iterations):
        if prepare is not None:
            prepare()
        started_ns = time.perf_counter_ns()
        action()
        samples.append((time.perf_counter_ns() - started_ns) / 1_000_000.0)

    return {
        "avg_ms": sum(samples) / len(samples),
        "p95_ms": _p95(samples),
        "bytes": int(bytes_count),
    }


def run_benchmark(
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    iterations: int = DEFAULT_ITERATIONS,
    warmup: int = DEFAULT_WARMUP,
) -> dict[str, Any]:
    """Measure cold put, exact hit get, and one-pixel miss get."""
    width = int(width)
    height = int(height)
    iterations = int(iterations)
    warmup = int(warmup)
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than zero")
    if iterations <= 0:
        raise ValueError("iterations must be greater than zero")
    if warmup < 0:
        raise ValueError("warmup must not be negative")

    image = make_synthetic_bgr(width, height)
    miss = make_one_pixel_miss(image)
    image_bytes = int(image.nbytes)
    max_bytes = image_bytes + BENCHMARK_METADATA_HEADROOM
    cache = ExactImageCache(max_entries=2, max_bytes=max_bytes)

    def put_image() -> None:
        if not cache.put(image, _CONTEXT, (), None, None):
            raise RuntimeError("synthetic image did not fit in ExactImageCache")

    def get_hit() -> None:
        if cache.get(image, _CONTEXT) is None:
            raise RuntimeError("exact image cache hit unexpectedly missed")

    def get_miss() -> None:
        if cache.get(miss, _CONTEXT) is not None:
            raise RuntimeError("one-pixel image miss unexpectedly hit")

    metrics = {
        "cold_put": _measure(
            put_image,
            iterations=iterations,
            warmup=warmup,
            bytes_count=image_bytes,
            prepare=cache.clear,
        ),
        "exact_hit_get": _measure(
            get_hit,
            iterations=iterations,
            warmup=warmup,
            bytes_count=image_bytes,
            prepare=put_image,
        ),
        "one_pixel_miss_get": _measure(
            get_miss,
            iterations=iterations,
            warmup=warmup,
            bytes_count=image_bytes,
            prepare=put_image,
        ),
    }
    return {
        "width": width,
        "height": height,
        "iterations": iterations,
        "warmup": warmup,
        "bytes": image_bytes,
        "retained_bytes": cache.total_bytes,
        "metrics": metrics,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CPU-only ExactImageCache microbenchmark")
    parser.add_argument("--width", type=_positive_int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=_positive_int, default=DEFAULT_HEIGHT)
    parser.add_argument("--iterations", type=_positive_int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--warmup", type=_nonnegative_int, default=DEFAULT_WARMUP)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    return parser


def _print_text(result: dict[str, Any]) -> None:
    print("Exact Image Cache Benchmark")
    print(
        f"image={result['width']}x{result['height']} "
        f"iterations={result['iterations']} warmup={result['warmup']} "
        f"bytes={result['bytes']} retained_bytes={result['retained_bytes']}"
    )
    for name, metric in result["metrics"].items():
        print(
            f"{name}: avg_ms={metric['avg_ms']:.4f} "
            f"p95_ms={metric['p95_ms']:.4f} bytes={metric['bytes']}"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(
        width=args.width,
        height=args.height,
        iterations=args.iterations,
        warmup=args.warmup,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        _print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
