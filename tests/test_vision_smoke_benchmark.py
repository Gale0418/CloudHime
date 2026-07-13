import base64
from pathlib import Path

import cv2
import numpy as np

from vision_smoke_benchmark import group_cases_by_image, image_parts, line_match, load_cases, percentile, score_match


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_line_match_accepts_expected_line_inside_multiline_ocr() -> None:
    case = {"expected": "Wine Club"}
    actual = "Exclusive Invite: Forbes\nWine Club"

    assert line_match(actual, case) == 1.0
    assert score_match(actual, case) == 1.0


def test_score_match_keeps_similarity_for_near_miss() -> None:
    case = {"expected": "the market for humanoids reaches a fever pitch"}

    score = score_match("the market for humanoids reaches a fever p1tch", case)

    assert 0.0 < score < 1.0


def test_load_cases_honors_max_cases() -> None:
    cases = load_cases(PROJECT_ROOT / "benchmarks" / "ocr_accuracy_cases.json", max_cases=3)

    assert len(cases) == 3
    assert all(case["sample_source"] for case in cases)

def test_small_image_scale_upscales_short_fixture_only() -> None:
    image_path = PROJECT_ROOT / "example" / "2026-04-30 20 47 05.png"

    baseline = image_parts(image_path)
    scaled = image_parts(image_path, small_image_scale=2.0)
    baseline_bytes = base64.b64decode(baseline[0]["inline_data"]["data"])
    scaled_bytes = base64.b64decode(scaled[0]["inline_data"]["data"])
    baseline_image = cv2.imdecode(np.frombuffer(baseline_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    scaled_image = cv2.imdecode(np.frombuffer(scaled_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)

    assert baseline_image.shape[:2] == (95, 617)
    assert scaled_image.shape[:2] == (190, 1234)

def test_group_cases_deduplicates_same_image_requests() -> None:
    cases = [
        {"sample_source": "example/ui.png", "category": "ui_en"},
        {"sample_source": "example/ui.png", "category": "ui_en"},
        {"sample_source": "example/article.png", "category": "article_en"},
    ]

    grouped = group_cases_by_image(cases)

    assert list(grouped) == ["example/ui.png", "example/article.png"]
    assert len(grouped["example/ui.png"]) == 2


def test_percentile_uses_image_latency_values() -> None:
    assert percentile([10.0, 20.0, 30.0, 40.0]) == 40.0
