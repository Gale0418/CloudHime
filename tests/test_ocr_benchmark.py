from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import ocr_benchmark


MANIFEST_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "ocr_accuracy_cases.json"


def test_seed_manifest_contains_expected_case_volume_and_categories():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = manifest["cases"]

    assert len(cases) >= 20
    categories = {case["category"] for case in cases}
    assert {"quote_cn", "lyric_jp", "article_en", "docs_en", "title_mixed"}.issubset(categories)


def test_ocr_benchmark_cli_runs_on_seed_manifest():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = ocr_benchmark.main([str(MANIFEST_PATH)])

    output = buffer.getvalue()

    assert exit_code == 0
    assert "Summary:" in output
    assert "Categories:" in output
    assert "Variants:" in output
    assert "category=article_en" in output
    assert "category=docs_en" in output
    assert "backend=windows preprocess=-" in output
