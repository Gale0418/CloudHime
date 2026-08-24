import json
from pathlib import Path

import pytest

import manga_repeated_run_evaluator as evaluator


def _write_manifest(tmp_path: Path, *, anchors: bool = True) -> Path:
    (tmp_path / "a.png").write_bytes(b"a")
    (tmp_path / "b.png").write_bytes(b"b")
    cases = [
        {
            "id": "case-a",
            "image": "a.png",
            "anchors": ["魔法"],
        },
        {
            "id": "case-b",
            "image": "b.png",
            "anchors": ["世界"] if anchors else [],
        },
    ]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"version": 1, "cases": cases}), encoding="utf-8")
    return path


def _image_result(text: str, elapsed_ms: float, *, accepted: bool = False) -> dict:
    return {
        "joined_text": text,
        "item_count": 1 if text else 0,
        "elapsed_ms": elapsed_ms,
        "error": "",
        "grid_recovery_triggered": accepted,
        "grid_recovery_accepted": accepted,
    }


def test_anchor_matching_normalizes_unicode_and_whitespace(tmp_path):
    manifest = _write_manifest(tmp_path)
    suite = evaluator.load_suite(manifest)
    record = evaluator._score_case(
        suite["cases"][0],
        _image_result("  魔 法\n", elapsed_ms=0.0),
        repeat=1,
        condition="baseline",
    )

    assert record["anchor_hits"] == 1
    assert record["anchor_recall"] == 1.0


def test_load_suite_rejects_duplicate_normalized_anchors(tmp_path):
    (tmp_path / "a.png").write_bytes(b"a")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "image": "a.png",
                        "anchors": ["魔法", " 魔 法 "],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate anchors"):
        evaluator.load_suite(manifest)


def test_compare_conditions_reports_pooled_and_page_regression():
    baseline = [
        {
            "case_id": "a",
            "anchor_count": 2,
            "anchor_hits": 1,
            "anchor_recall": 0.5,
            "item_count": 1,
            "elapsed_ms": 10,
            "error": "",
            "grid_recovery_triggered": False,
            "grid_recovery_accepted": False,
        },
        {
            "case_id": "b",
            "anchor_count": 2,
            "anchor_hits": 2,
            "anchor_recall": 1.0,
            "item_count": 1,
            "elapsed_ms": 20,
            "error": "",
            "grid_recovery_triggered": False,
            "grid_recovery_accepted": False,
        },
    ]
    variant = [
        {**baseline[0], "anchor_hits": 2, "anchor_recall": 1.0, "elapsed_ms": 30},
        {**baseline[1], "anchor_hits": 1, "anchor_recall": 0.5, "elapsed_ms": 40},
    ]

    comparison = evaluator.compare_conditions(baseline, variant)

    assert comparison["anchor_recall"]["delta"] == 0.0
    assert comparison["page_regression"] == {
        "improved_pages": 1,
        "equal_pages": 0,
        "regressed_pages": 1,
        "compared_pages": 2,
    }
    assert comparison["latency_ms"]["avg_delta"] == 20.0


def test_empty_anchor_holdout_has_null_recall_and_latency_p95():
    records = [
        {
            "case_id": "holdout",
            "anchor_count": 0,
            "anchor_hits": 0,
            "anchor_recall": None,
            "item_count": 1,
            "elapsed_ms": 12,
            "error": "runtime",
            "grid_recovery_triggered": False,
            "grid_recovery_accepted": False,
        }
    ]

    summary = evaluator.summarize_records(records)

    assert summary["anchor_recall"] is None
    assert summary["page_macro_recall"] is None
    assert summary["latency_ms"]["p95"] == 12.0
    assert summary["successful_latency_ms"]["p95"] is None
    assert summary["error_pages"] == 1
    assert summary["nonempty_page_rate"] == 0.0
    assert summary["successful_nonempty_page_rate"] is None


def test_public_manga_holdout_manifest_is_evaluator_ready(monkeypatch):
    manifest = Path(__file__).resolve().parents[1] / "benchmarks" / "manga_cover_cases.json"
    suite = evaluator.load_suite(manifest)

    assert len(suite["cases"]) == 6
    assert all(case["anchors"] for case in suite["cases"])

    def fake_run(image_paths, **kwargs):
        return {
            "images": [_image_result("", elapsed_ms=1.0) for _ in image_paths],
        }

    monkeypatch.setattr(evaluator.fullscreen_benchmark, "run_benchmark", fake_run)
    report = evaluator.run_repeated_benchmark(manifest, repeats=1)

    assert report["suite"]["case_count"] == 6
    assert report["comparison"]["page_regression"]["compared_pages"] == 6
    assert all("joined_text" not in record for record in report["records"])

def test_repeated_benchmark_pairs_conditions_and_keeps_raw_text_out(
    monkeypatch,
    tmp_path,
):
    manifest = _write_manifest(tmp_path)

    def fake_run(image_paths, **kwargs):
        grid = kwargs["grid_recovery"]
        base = 30 if grid else 10
        images = [
            _image_result("魔法" if grid else "", base),
            _image_result("世界" if not grid else "", base + 1),
        ]
        return {"images": images}

    monkeypatch.setattr(evaluator.fullscreen_benchmark, "run_benchmark", fake_run)
    report = evaluator.run_repeated_benchmark(manifest, repeats=2)

    assert report["metadata"]["base_threshold"] == 100
    assert report["suite"]["case_count"] == 2
    assert report["conditions"]["baseline"]["anchor_recall"] == 0.5
    assert report["conditions"]["grid_recovery"]["anchor_recall"] == 0.5
    assert report["comparison"]["page_regression"] == {
        "improved_pages": 1,
        "equal_pages": 0,
        "regressed_pages": 1,
        "compared_pages": 2,
    }
    assert all("joined_text" not in record for record in report["records"])
def test_compare_conditions_exposes_per_repeat_regression():
    def record(repeat, recall):
        return {
            "case_id": "a",
            "repeat": repeat,
            "anchor_count": 2,
            "anchor_hits": int(recall * 2),
            "anchor_recall": recall,
            "item_count": 1,
            "elapsed_ms": 10,
            "error": "",
            "grid_recovery_triggered": False,
            "grid_recovery_accepted": False,
        }

    comparison = evaluator.compare_conditions(
        [record(1, 1.0), record(2, 0.0)],
        [record(1, 0.0), record(2, 1.0)],
    )

    assert comparison["page_regression"]["equal_pages"] == 1
    assert comparison["paired_repeat_regression"] == {
        "improved_observations": 1,
        "equal_observations": 0,
        "regressed_observations": 1,
        "compared_observations": 2,
        "repeats_with_regression": 1,
        "repeats_without_regression": 1,
        "repeats_without_comparison": 0,
    }
    assert [item["page_regression"]["regressed_pages"] for item in comparison["repeat_deltas"]] == [1, 0]

def test_load_suite_rejects_unconfirmed_ground_truth_manifest(tmp_path):
    image = tmp_path / "draft.png"
    image.write_bytes(b"draft")
    manifest = tmp_path / "draft.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "draft_requires_owner_confirmation",
                "ground_truth_eligible": False,
                "cases": [{"image": "draft.png", "anchors": ["文字"]}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ground-truth eligible"):
        evaluator.load_suite(manifest)

def test_load_suite_rejects_false_ground_truth_without_status(tmp_path):
    manifest = tmp_path / "draft.json"
    manifest.write_text(
        json.dumps({"ground_truth_eligible": False, "cases": [{"image": "missing.png", "anchors": ["文字"]}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ground-truth eligible"):
        evaluator.load_suite(manifest)


def test_load_suite_rejects_non_boolean_ground_truth_flag(tmp_path):
    manifest = tmp_path / "draft.json"
    manifest.write_text(
        json.dumps({"ground_truth_eligible": "false", "cases": [{"image": "missing.png", "anchors": ["文字"]}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be a boolean"):
        evaluator.load_suite(manifest)


def test_load_suite_rejects_normalized_draft_status(tmp_path):
    manifest = tmp_path / "draft.json"
    manifest.write_text(
        json.dumps({"status": "  DRAFT_REQUIRES_OWNER_CONFIRMATION  ", "cases": [{"image": "missing.png", "anchors": ["文字"]}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ground-truth eligible"):
        evaluator.load_suite(manifest)

def test_compare_conditions_does_not_count_uncompared_repeat_as_clean():
    base = {
        "case_id": "a",
        "repeat": 3,
        "anchor_count": 0,
        "anchor_hits": 0,
        "anchor_recall": None,
        "item_count": 0,
        "elapsed_ms": 10,
        "error": "runtime",
        "grid_recovery_triggered": False,
        "grid_recovery_accepted": False,
    }
    comparison = evaluator.compare_conditions([base], [dict(base)])

    summary = comparison["paired_repeat_regression"]
    assert summary["repeats_with_regression"] == 0
    assert summary["repeats_without_regression"] == 0
    assert summary["repeats_without_comparison"] == 1

def test_promotion_gate_fails_closed_when_pairs_are_incomplete():
    baseline = [{
        "case_id": "a",
        "repeat": 1,
        "anchor_count": 1,
        "anchor_hits": 1,
        "anchor_recall": 1.0,
        "item_count": 1,
        "elapsed_ms": 10,
        "error": "",
        "grid_recovery_triggered": False,
        "grid_recovery_accepted": False,
    }]

    gate = evaluator.evaluate_promotion_gate(
        baseline,
        [],
        expected_case_count=1,
        expected_repeats=1,
    )

    assert gate["passed"] is False
    assert gate["complete"] is False
    assert "paired_coverage_incomplete" in gate["reasons"]


def test_promotion_gate_rejects_candidate_empty_output_even_without_anchor_regression():
    def record(text, recall):
        return {
            "case_id": "a",
            "repeat": 1,
            "anchor_count": 1,
            "anchor_hits": recall,
            "anchor_recall": float(recall),
            "item_count": 1 if text else 0,
            "elapsed_ms": 10,
            "error": "",
            "grid_recovery_triggered": False,
            "grid_recovery_accepted": False,
        }

    gate = evaluator.evaluate_promotion_gate(
        [record("文字", 1)],
        [record("", 1)],
        expected_case_count=1,
        expected_repeats=1,
    )

    assert gate["passed"] is False
    assert "candidate_empty_output" in gate["reasons"]


def test_main_require_no_regression_is_fail_closed(monkeypatch, tmp_path):
    manifest = _write_manifest(tmp_path)
    report = {
        "schema_version": 2,
        "promotion_gate": {
            "passed": False,
            "complete": False,
            "reasons": ["paired_coverage_incomplete"],
        },
    }
    monkeypatch.setattr(evaluator, "run_repeated_benchmark", lambda *args, **kwargs: report)

    assert evaluator.main([str(manifest), "--require-no-regression"]) == 1


def test_owner_confirmed_heavy_knight_manifest_is_locked_and_scored_only_on_explicit_anchors():
    manifest_path = Path(__file__).resolve().parents[1] / 'benchmarks' / 'tensei_heavy_knight_owner_confirmed_ocr.json'
    payload = json.loads(manifest_path.read_text(encoding='utf-8'))

    assert payload['status'] == 'locked_owner_confirmed'
    assert payload['ground_truth_eligible'] is True
    assert len(payload['cases']) == 10
    assert all(case['anchors'] for case in payload['cases'])
    assert all(isinstance(case.get('image_sha256'), str) and len(case['image_sha256']) == 64 for case in payload['cases'])
    assert payload['excluded_cases']
    assert all(item['reason'] for item in payload['excluded_cases'])

    suite = evaluator.load_suite(manifest_path)
    assert len(suite['cases']) == 10
    assert [case['image_sha256'] for case in payload['cases']] == [case['image_sha256'] for case in suite['cases']]
    assert {case['id'] for case in suite['cases']} == {
        'heavy-knight-001', 'heavy-knight-004', 'heavy-knight-006',
        'heavy-knight-007', 'heavy-knight-008', 'heavy-knight-013',
        'heavy-knight-021', 'heavy-knight-026', 'heavy-knight-029',
        'heavy-knight-034',
    }
    assert suite['cases'][0]['image_sha256']
