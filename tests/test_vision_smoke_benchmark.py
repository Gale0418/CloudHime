from pathlib import Path

from vision_smoke_benchmark import line_match, load_cases, score_match


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