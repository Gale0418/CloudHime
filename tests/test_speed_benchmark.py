from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import speed_benchmark


MANIFEST_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "ocr_accuracy_cases.json"


def test_speed_benchmark_reports_core_pipeline_stages():
    result = speed_benchmark.run_benchmark(
        MANIFEST_PATH,
        iterations=1,
        warmup=0,
        max_cases=3,
    )

    stage_names = {stage["name"] for stage in result["stages"]}

    assert result["case_count"] == 3
    assert {
        "ocr_postprocess",
        "translate_prepare_cache",
        "render_bubble_layout",
    } == stage_names
    for stage in result["stages"]:
        assert stage["avg_ms"] >= 0
        assert stage["p95_ms"] >= 0


def test_speed_benchmark_cli_prints_summary():
    buffer = io.StringIO()

    with redirect_stdout(buffer):
        exit_code = speed_benchmark.main(
            [
                str(MANIFEST_PATH),
                "--iterations",
                "1",
                "--warmup",
                "0",
                "--max-cases",
                "3",
            ]
        )

    output = buffer.getvalue()

    assert exit_code == 0
    assert "Speed Summary:" in output
    assert "stage=ocr_postprocess" in output
    assert "stage=translate_prepare_cache" in output
    assert "stage=render_bubble_layout" in output
