import json

import numpy as np

from exact_image_cache import ExactImageCache
from exact_image_cache_benchmark import (
    BENCHMARK_METADATA_HEADROOM,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    build_parser,
    main,
    make_one_pixel_miss,
    make_synthetic_bgr,
    run_benchmark,
)


def test_parser_defaults_and_custom_arguments():
    defaults = build_parser().parse_args([])
    assert defaults.width == DEFAULT_WIDTH
    assert defaults.height == DEFAULT_HEIGHT
    assert defaults.iterations > 0
    assert defaults.warmup >= 0
    assert not defaults.json

    custom = build_parser().parse_args(
        ["--width", "1920", "--height", "1080", "--iterations", "3", "--warmup", "1", "--json"]
    )
    assert (custom.width, custom.height, custom.iterations, custom.warmup) == (1920, 1080, 3, 1)
    assert custom.json


def test_output_schema_and_json_option(capsys):
    result = run_benchmark(width=8, height=6, iterations=3, warmup=1)

    assert set(result) == {"width", "height", "iterations", "warmup", "bytes", "retained_bytes", "metrics"}
    assert result["bytes"] == 8 * 6 * 3
    assert result["retained_bytes"] > result["bytes"]
    assert result["retained_bytes"] <= result["bytes"] + BENCHMARK_METADATA_HEADROOM
    assert set(result["metrics"]) == {"cold_put", "exact_hit_get", "one_pixel_miss_get"}
    for metric in result["metrics"].values():
        assert set(metric) == {"avg_ms", "p95_ms", "bytes"}
        assert metric["avg_ms"] >= 0
        assert metric["p95_ms"] >= 0
        assert metric["bytes"] == result["bytes"]

    assert main(["--width", "8", "--height", "6", "--iterations", "1", "--warmup", "0", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["width"] == 8
    assert output["retained_bytes"] > output["bytes"]
    assert set(output["metrics"]) == {"cold_put", "exact_hit_get", "one_pixel_miss_get"}


def test_same_synthetic_image_is_an_exact_hit():
    image = make_synthetic_bgr(4, 3)
    cache = ExactImageCache(max_bytes=image.nbytes + BENCHMARK_METADATA_HEADROOM)

    assert cache.put(image, "benchmark", (), None, None)
    assert cache.get(image, "benchmark") is not None


def test_one_pixel_synthetic_difference_is_a_miss():
    image = make_synthetic_bgr(4, 3)
    miss = make_one_pixel_miss(image)
    cache = ExactImageCache(max_bytes=image.nbytes + BENCHMARK_METADATA_HEADROOM)

    assert isinstance(image, np.ndarray)
    assert image.shape == (3, 4, 3)
    assert image.dtype == np.uint8
    assert np.count_nonzero(image != miss) == 1
    assert cache.put(image, "benchmark", (), None, None)
    assert cache.get(miss, "benchmark") is None
