from __future__ import annotations

import hashlib
import json
from pathlib import Path

from frame_gate_benchmark import REPEATS, SEQUENCE_NAMES, main, run_benchmark


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "benchmarks" / "benchmark_lock.json"


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_paired_dynamic_sequence_preserves_every_quality_output():
    result = run_benchmark()

    assert REPEATS == result["repeats"] == 5
    assert SEQUENCE_NAMES == (
        "baseline",
        "exact_repeat",
        "one_pixel_noise",
        "subtitle_a",
        "subtitle_b_transition",
        "single_frame_subtitle",
        "return_to_background",
    )
    assert result["output_sequence_equal"] is True
    assert result["baseline_outputs"] == result["candidate_outputs"]
    assert result["single_frame_recall"] == 1.0
    assert result["transition_recall"] == 1.0
    assert result["nonexact_false_skips"] == 0


def test_candidate_processes_every_nonexact_frame_and_only_saves_exact_duplicates():
    result = run_benchmark()
    total_frames = REPEATS * len(SEQUENCE_NAMES)

    assert result["baseline_process_calls"] == total_frames == 35
    assert result["exact_hits"] == REPEATS * 2 == 10
    assert result["candidate_process_calls"] == total_frames - result["exact_hits"] == 25
    for frame in result["candidate_frames"]:
        assert frame["processed"] is (not frame["exact_hit"])
        if frame["name"] not in {"exact_repeat", "return_to_background"}:
            assert frame["processed"] is True
            assert frame["exact_hit"] is False
        assert frame["frame_gate_skip_ocr"] is False

    assert result["shadow_classification_counts"] == {
        "baseline": 5,
        "identical": 5,
        "near": 5,
        "changed": 20,
    }


def test_summary_has_paired_metrics_and_locked_hash_identity(capsys):
    result = run_benchmark()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))

    assert result["benchmark_lock_id"] == lock["lock_id"]
    assert result["manifest_hash"] == _canonical_hash(lock["datasets"])
    assert result["condition_hash"] == _canonical_hash(lock["conditions"])
    for condition in ("baseline", "candidate"):
        metrics = result["latency_ms"][condition]
        assert set(metrics) == {"avg_ms", "p95_ms", "coverage"}
        assert metrics["avg_ms"] >= 0.0
        assert metrics["p95_ms"] >= 0.0
        assert metrics["coverage"] == 1.0

    assert main(["--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["repeats"] == 5
    assert output["output_sequence_equal"] is True
    assert output["exact_hits"] == 10
    assert output["nonexact_false_skips"] == 0