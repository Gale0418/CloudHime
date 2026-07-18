import base64
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest
import numpy as np

import vision_smoke_benchmark as benchmark
from japanese_ocr_rescue import MeikiCandidate, MeikiCharacter
from vision_smoke_benchmark import (
    build_parser,
    group_cases_by_image,
    run_smoke,
    image_parts,
    line_match,
    load_cases,
    percentile,
    score_match,
)


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


def test_parser_exposes_gpu_only_controls() -> None:
    args = build_parser().parse_args(["--gpu-layers", "20", "--require-gpu"])

    assert args.gpu_layers == 20
    assert args.require_gpu is True
    assert args.japanese_rescue is False


def test_parser_exposes_optional_japanese_rescue() -> None:
    args = build_parser().parse_args(["--japanese-rescue"])

    assert args.japanese_rescue is True
    assert args.require_complete is False


def test_parser_exposes_require_complete() -> None:
    args = build_parser().parse_args(["--require-complete"])

    assert args.require_complete is True


def test_japanese_rescue_uses_runtime_lifecycle_without_network(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    assert cv2.imwrite(str(image_path), np.zeros((95, 617, 3), dtype=np.uint8))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"cases": [{"sample_source": "sample.png", "category": "jp", "expected": "救出"}]}),
        encoding="utf-8",
    )
    events = []

    class FakeVisionRuntime:
        def __init__(self, *args, **kwargs):
            self.state = SimpleNamespace(name="ready", detail="", mode="cpu", base_url="http://vision")

        def start(self):
            events.append("vision_start")
            return self.state

        def stop(self):
            events.append("vision_stop")

    class FakeJapaneseRuntime:
        def __init__(self, assets):
            events.append(("japanese_init", assets))
            self.candidate = MeikiCandidate(
                text="候選",
                characters=(MeikiCharacter("候", 0.9), MeikiCharacter("選", 0.4)),
            )
            self.last_error = ""

        def start(self):
            events.append("japanese_start")
            return True

        def run(self, image):
            events.append("japanese_run")
            return self.candidate

        def disable(self):
            events.append("japanese_disable")

    class FakeProvider:
        def __init__(self, **kwargs):
            pass

        def transcribe_screenshot(self, parts, **kwargs):
            events.append("provider_run")
            return SimpleNamespace(text="かなかな" if events.count("provider_run") == 1 else "救出")

    sentinel_assets = object()
    monkeypatch.setattr(benchmark, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "LocalVisionRuntime", FakeVisionRuntime)
    monkeypatch.setattr(benchmark, "LocalMultimodalProvider", FakeProvider)
    monkeypatch.setattr(benchmark, "JapaneseOCRRuntime", FakeJapaneseRuntime)
    monkeypatch.setattr(benchmark, "resolve_japanese_ocr_assets", lambda: sentinel_assets)
    monkeypatch.setattr(benchmark, "rescue_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(benchmark, "is_usable_meiki_candidate", lambda *args, **kwargs: True)
    monkeypatch.setattr(benchmark, "build_verification_hint", lambda candidate: "verify")
    monkeypatch.setattr(
        benchmark,
        "decide_rescue_text",
        lambda first, second, candidate: SimpleNamespace(adopted=True, selected_text=second),
    )

    result = benchmark.run_smoke(manifest_path, japanese_rescue=True)

    assert result["rescue_startup_ms"] >= 0.0
    assert result["image_results"][0]["rescue_triggered"] is True
    assert events[0] == "vision_start"
    assert events[1] == ("japanese_init", sentinel_assets)
    assert events[2] == "japanese_start"
    assert "japanese_run" in events
    assert events[-2] == "vision_stop"
    assert events[-1] == "japanese_disable"


def test_require_complete_returns_nonzero_for_incomplete_result(monkeypatch, capsys) -> None:
    incomplete = {
        "image_count": 2,
        "case_count": 2,
        "successful_images": 1,
        "successful_cases": 1,
    }
    monkeypatch.setattr(benchmark, "run_smoke", lambda *args, **kwargs: incomplete)

    assert benchmark.main(["--json", "--require-complete"]) == 1
    assert json.loads(capsys.readouterr().out)["successful_images"] == 1


def test_require_complete_accepts_complete_result(monkeypatch, capsys) -> None:
    complete = {
        "image_count": 2,
        "case_count": 3,
        "successful_images": 2,
        "successful_cases": 3,
    }
    monkeypatch.setattr(benchmark, "run_smoke", lambda *args, **kwargs: complete)

    assert benchmark.main(["--json", "--require-complete"]) == 0
    assert json.loads(capsys.readouterr().out)["successful_cases"] == 3


def test_require_gpu_rejects_cpu_controls() -> None:
    with pytest.raises(ValueError, match="force_cpu"):
        run_smoke(require_gpu=True, force_cpu=True)

    with pytest.raises(ValueError, match="gpu_layers"):
        run_smoke(require_gpu=True, gpu_layers=0)
