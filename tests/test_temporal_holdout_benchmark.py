from __future__ import annotations

import json
from pathlib import Path

import pytest

from temporal_holdout_benchmark import (
    SEQUENCE_TRANSFORMS,
    load_manifest,
    main,
    read_image_unicode_safe,
    run_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_contains_only_source_identity_category_and_transforms():
    manifest = load_manifest()
    cases = manifest["cases"]

    assert manifest["evaluation_scope"] == "frame_policy_only"
    assert len(cases) == 12
    assert all(tuple(case["sequence_transforms"]) == SEQUENCE_TRANSFORMS for case in cases)
    assert all(not {"expected", "actual", "visible_text_anchors", "ocr", "ground_truth"}.intersection(case) for case in cases)
    assert {case["category"] for case in cases} == {
        "owner_confirmed_example",
        "user_provided_example",
        "synthetic_adversarial",
    }


def test_unicode_safe_loader_reads_owner_confirmed_path():
    image = read_image_unicode_safe(ROOT / "example" / "\u8ee2\u751f\u91cd\u9a0e\u58eb" / "001.jpg")

    assert image.ndim == 3
    assert image.shape[2] == 3


def test_safe_policy_is_lossless_and_near_skip_has_counterexample():
    result = run_benchmark()
    safe = result["safe_exact_only_shadow_policy"]
    hypothetical = result["hypothetical_near_skip_policy"]

    assert result["not_an_ocr_or_model_benchmark"] is True
    lock = json.loads((ROOT / "benchmarks" / "benchmark_lock.json").read_text(encoding="utf-8"))
    locked_dataset = next(
        item for item in lock["datasets"] if item["id"] == "temporal_holdout"
    )
    assert result["manifest_hash"] == locked_dataset["sha256"]
    assert safe["false_event_skips"] == 0
    assert safe["event_recall"] == 1.0
    assert safe["single_frame_recall"] == 1.0
    assert safe["exact_hits"] > 0
    assert safe["coverage"] == 1.0
    assert safe["gate_p95_ms"] >= 0.0
    assert hypothetical["false_event_skips"] > 0
    assert result["near_skip_counterexample"]["repeatable"] is True
    assert result["near_skip_counterexample"]["contains_text_ground_truth"] is False
    assert all(
        item["transform"] != "same_semantic_1px_noise"
        for item in hypothetical["counterexamples"]
    )
    assert any(
        item["case_id"] == "synthetic-adversarial-local-event"
        and item["transform"] == "source"
        for item in hypothetical["counterexamples"]
    )


def test_cli_emits_locked_frame_policy_metrics(capsys):
    assert main(["--json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["benchmark"] == "CH-T61 locked temporal holdout"
    assert result["sequence_transforms"] == list(SEQUENCE_TRANSFORMS)
    assert set(result["safe_exact_only_shadow_policy"]).issuperset(
        {"event_recall", "single_frame_recall", "false_event_skips", "exact_hits", "coverage", "gate_p95_ms"}
    )


def test_manifest_rejects_ocr_ground_truth_and_unsafe_source(tmp_path):
    manifest = load_manifest()
    manifest["cases"][0]["ground_truth"] = "not allowed"
    path = tmp_path / "ground-truth.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="must not carry OCR"):
        load_manifest(path)

    manifest = load_manifest()
    manifest["cases"][0]["semantic_target"] = "hidden hint"
    path = tmp_path / "unknown-field.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown field"):
        load_manifest(path)

    manifest = load_manifest()
    manifest["cases"][0]["source"] = "../outside.png"
    path = tmp_path / "unsafe-source.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="must stay relative"):
        load_manifest(path)


def test_run_benchmark_rejects_manifest_outside_locked_path(tmp_path):
    manifest = load_manifest()
    manifest["description"] = "mutated but structurally valid"
    path = tmp_path / "mutated-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="only accepts the locked manifest"):
        run_benchmark(path)
