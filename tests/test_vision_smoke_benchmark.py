import base64
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import vision_smoke_benchmark as benchmark
from japanese_ocr_rescue import MeikiCandidate, MeikiCharacter
from vision_smoke_benchmark import (
    build_parser,
    case_image_source,
    group_cases_by_image,
    run_smoke,
    image_parts,
    line_match,
    load_cases,
    percentile,
    score_match,
    expected_variants,
    summarize_rescue_quality,
    evaluate_rescue_quality_gate,
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

def test_manga_manifest_uses_image_and_visible_text_anchors() -> None:
    cases = load_cases(PROJECT_ROOT / "benchmarks" / "manga_cover_cases.json", max_cases=2)

    assert len(cases) == 2
    assert case_image_source(cases[0]).startswith("example/manga_cover_")
    assert expected_variants(cases[0]) == cases[0]["visible_text_anchors"]


def test_group_cases_accepts_image_manifest_key() -> None:
    grouped = group_cases_by_image([
        {"image": "example/manga.jpg", "visible_text_anchors": ["標題"]},
    ])

    assert list(grouped) == ["example/manga.jpg"]


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



def test_parser_exposes_technical_coverage_gate() -> None:
    args = build_parser().parse_args(["--require-technical-coverage"])

    assert args.require_technical_coverage is True


def test_require_technical_coverage_accepts_empty_output_without_quality_claim(monkeypatch, capsys) -> None:
    result = {
        "evaluation_mode": "technical_coverage",
        "image_count": 1,
        "case_count": 1,
        "successful_images": 0,
        "successful_cases": 0,
        "request_success_images": 1,
        "request_success_cases": 1,
        "quality_basis": "coverage_only",
    }
    monkeypatch.setattr(benchmark, "run_smoke", lambda *args, **kwargs: result)

    assert benchmark.main(["--json", "--require-technical-coverage"]) == 0
    assert json.loads(capsys.readouterr().out)["quality_basis"] == "coverage_only"

def test_parser_exposes_require_complete() -> None:
    args = build_parser().parse_args(["--require-complete"])

    assert args.require_complete is True


def test_heavy_knight_coverage_manifest_has_no_quality_targets() -> None:
    manifest = benchmark.load_manifest(
        PROJECT_ROOT / "benchmarks" / "tensei_heavy_knight_coverage_smoke.json"
    )

    assert manifest["evaluation_mode"] == "technical_coverage"
    assert len(manifest["cases"]) == 38
    assert all("expected" not in case for case in manifest["cases"])
    assert all("visible_text_anchors" not in case for case in manifest["cases"])
    assert all(case["sha256"] for case in manifest["cases"])

def test_technical_manifest_rejects_embedded_ground_truth(tmp_path) -> None:
    manifest_path = tmp_path / "technical.json"
    manifest_path.write_text(
        json.dumps(
            {
                "evaluation_mode": "technical_coverage",
                "cases": [{"sample_source": "sample.png", "expected": "不要猜"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not contain expected text"):
        benchmark.load_manifest(manifest_path)

def test_run_smoke_marks_path_only_cases_as_coverage_not_accuracy(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    assert cv2.imwrite(str(image_path), np.zeros((95, 617, 3), dtype=np.uint8))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"cases": [{"sample_source": "sample.png", "category": "coverage_only"}]}),
        encoding="utf-8",
    )

    class FakeVisionRuntime:
        def __init__(self, *args, **kwargs):
            self.state = SimpleNamespace(name="ready", detail="", mode="cpu", base_url="http://vision")

        def start(self):
            return self.state

        def stop(self):
            pass

    class FakeProvider:
        def __init__(self, **kwargs):
            pass

        def transcribe_screenshot(self, parts, **kwargs):
            return SimpleNamespace(text="讀到的內容")

    monkeypatch.setattr(benchmark, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "LocalVisionRuntime", FakeVisionRuntime)
    monkeypatch.setattr(benchmark, "LocalMultimodalProvider", FakeProvider)

    result = benchmark.run_smoke(manifest_path, max_cases=1)

    assert result["image_count"] == 1
    assert result["successful_images"] == 1
    assert result["quality_basis"] == "coverage_only"
    assert result["ground_truth_case_count"] == 0
    assert result["ground_truth_complete"] is False
    assert result["average_match_score"] is None
    assert result["results"][0]["quality_scored"] is False
    assert result["results"][0]["match_score"] is None


def test_rescue_quality_gate_rejects_unscored_coverage() -> None:
    summary = evaluate_rescue_quality_gate(
        [{"sample_source": "coverage", "quality_scored": False}],
        complete=True,
        enabled=True,
        ground_truth_complete=False,
    )

    assert summary["quality_basis"] == "coverage_only"
    assert summary["quality_scored_cases"] == 0
    assert summary["passed"] is False


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
        lambda first, second, candidate: SimpleNamespace(
            adopted=True,
            selected_text=second,
            trusted_text=candidate.text,
            first_similarity=0.25,
            second_similarity=0.75,
        ),
    )

    result = benchmark.run_smoke(manifest_path, japanese_rescue=True)

    assert result["rescue_startup_ms"] >= 0.0
    image_result = result["image_results"][0]
    case_result = result["results"][0]
    assert image_result["rescue_triggered"] is True
    assert image_result["rescue_gate_reason"] == "adopted"
    assert image_result["rescue_decision_completed"] is True
    assert image_result["actual"] == "救出"
    assert image_result["rescue_baseline"] == "かなかな"
    assert image_result["rescue_second"] == "救出"
    assert image_result["rescue_trusted_text"] == "候選"
    assert image_result["rescue_first_similarity"] == 0.25
    assert image_result["rescue_second_similarity"] == 0.75
    assert image_result["rescue_shadow_actual"] == "救出"
    assert case_result["baseline_actual"] == "かなかな"
    assert case_result["shadow_actual"] == "救出"
    assert result["baseline_average_match_score"] == case_result["baseline_match_score"]
    assert result["shadow_average_match_score"] == case_result["shadow_match_score"]
    assert result["shadow_improved_cases"] == 1
    assert result["shadow_equal_cases"] == 0
    assert result["shadow_regressed_cases"] == 0
    assert result["rescue_shadow_candidate_fallbacks"] == 0
    assert events.count("provider_run") == 2
    assert events[0] == "vision_start"
    assert events[1] == ("japanese_init", sentinel_assets)
    assert events[2] == "japanese_start"
    assert "japanese_run" in events
    assert events[-2] == "vision_stop"
    assert events[-1] == "japanese_disable"


@pytest.mark.parametrize("second_raises", [False, True])
def test_japanese_rescue_rejection_keeps_actual_and_shadows_candidate(
    monkeypatch, tmp_path, second_raises
) -> None:
    image_path = tmp_path / "sample.png"
    assert cv2.imwrite(str(image_path), np.zeros((95, 617, 3), dtype=np.uint8))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"cases": [{"sample_source": "sample.png", "category": "jp", "expected": "候選"}]}),
        encoding="utf-8",
    )
    events = []

    class FakeVisionRuntime:
        def __init__(self, *args, **kwargs):
            self.state = SimpleNamespace(name="ready", detail="", mode="cpu", base_url="http://vision")

        def start(self):
            return self.state

        def stop(self):
            pass

    class FakeJapaneseRuntime:
        def __init__(self, assets):
            self.candidate = MeikiCandidate(
                text="候選",
                characters=(MeikiCharacter("候", 0.9), MeikiCharacter("選", 0.4)),
            )
            self.last_error = ""

        def start(self):
            return True

        def run(self, image):
            return self.candidate

        def disable(self):
            pass

    class FakeProvider:
        def __init__(self, **kwargs):
            self.calls = 0

        def transcribe_screenshot(self, parts, **kwargs):
            self.calls += 1
            events.append("provider_run")
            if second_raises and self.calls == 2:
                raise RuntimeError("second transcription failed")
            return SimpleNamespace(text="baseline" if self.calls == 1 else "second")

    monkeypatch.setattr(benchmark, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "LocalVisionRuntime", FakeVisionRuntime)
    monkeypatch.setattr(benchmark, "LocalMultimodalProvider", FakeProvider)
    monkeypatch.setattr(benchmark, "JapaneseOCRRuntime", FakeJapaneseRuntime)
    monkeypatch.setattr(benchmark, "resolve_japanese_ocr_assets", lambda: object())
    monkeypatch.setattr(benchmark, "rescue_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(benchmark, "is_usable_meiki_candidate", lambda *args, **kwargs: True)
    monkeypatch.setattr(benchmark, "build_verification_hint", lambda candidate: "verify")
    monkeypatch.setattr(
        benchmark,
        "decide_rescue_text",
        lambda first, second, candidate: SimpleNamespace(
            adopted=False,
            selected_text=first,
            trusted_text=candidate.text,
            first_similarity=0.8,
            second_similarity=0.2,
        ),
    )

    result = benchmark.run_smoke(manifest_path, japanese_rescue=True)

    image_result = result["image_results"][0]
    case_result = result["results"][0]
    assert events.count("provider_run") == 2
    assert image_result["actual"] == "baseline"
    assert image_result["rescue_baseline"] == "baseline"
    assert image_result["rescue_decision_completed"] is (not second_raises)
    assert image_result["rescue_second"] == ("" if second_raises else "second")
    assert image_result["rescue_gate_reason"] == ("verification_error" if second_raises else "verification_rejected")
    assert image_result["rescue_shadow_actual"] == ("baseline" if second_raises else "候選")
    assert case_result["baseline_actual"] == "baseline"
    assert case_result["shadow_actual"] == ("baseline" if second_raises else "候選")
    assert result["rescue_shadow_candidate_fallbacks"] == (0 if second_raises else 1)
    assert bool(image_result["rescue_error"]) is second_raises
    assert result["successful_images"] == 1
    assert result["successful_cases"] == 1
    assert benchmark._is_complete(result)


def test_japanese_rescue_without_trigger_does_not_add_provider_call(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    assert cv2.imwrite(str(image_path), np.zeros((95, 617, 3), dtype=np.uint8))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"cases": [{"sample_source": "sample.png", "category": "jp", "expected": "baseline"}]}),
        encoding="utf-8",
    )
    events = []

    class FakeVisionRuntime:
        def __init__(self, *args, **kwargs):
            self.state = SimpleNamespace(name="ready", detail="", mode="cpu", base_url="http://vision")

        def start(self):
            return self.state

        def stop(self):
            pass

    class FakeJapaneseRuntime:
        last_error = ""

        def __init__(self, assets):
            pass

        def start(self):
            return True

        def run(self, image):
            raise AssertionError("rescue runtime must not run when the gate rejects")

        def disable(self):
            pass

    class FakeProvider:
        def __init__(self, **kwargs):
            pass

        def transcribe_screenshot(self, parts, **kwargs):
            events.append("provider_run")
            return SimpleNamespace(text="baseline")

    monkeypatch.setattr(benchmark, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "LocalVisionRuntime", FakeVisionRuntime)
    monkeypatch.setattr(benchmark, "LocalMultimodalProvider", FakeProvider)
    monkeypatch.setattr(benchmark, "JapaneseOCRRuntime", FakeJapaneseRuntime)
    monkeypatch.setattr(benchmark, "resolve_japanese_ocr_assets", lambda: object())
    monkeypatch.setattr(benchmark, "rescue_gate", lambda *args, **kwargs: False)

    result = benchmark.run_smoke(manifest_path, japanese_rescue=True)

    image_result = result["image_results"][0]
    case_result = result["results"][0]
    assert events.count("provider_run") == 1
    assert image_result["rescue_triggered"] is False
    assert image_result["rescue_gate_reason"] == "geometry_rejected"
    assert image_result["rescue_decision_completed"] is False
    assert image_result["actual"] == image_result["rescue_baseline"] == image_result["rescue_shadow_actual"] == "baseline"
    assert image_result["rescue_second"] == ""
    assert case_result["baseline_actual"] == case_result["shadow_actual"] == "baseline"
    assert result["rescue_shadow_candidate_fallbacks"] == 0


def test_json_output_reconfigures_non_utf8_windows_console(monkeypatch) -> None:
    class Cp950Console:
        encoding = "cp950"

        def __init__(self):
            self.writes = []

        def reconfigure(self, *, encoding, errors):
            self.encoding = encoding

        def write(self, value):
            value.encode(self.encoding)
            self.writes.append(value)
            return len(value)

        def flush(self):
            pass

    console = Cp950Console()
    result = {
        "image_count": 1,
        "case_count": 1,
        "successful_images": 1,
        "successful_cases": 1,
        "actual": "来",
    }
    monkeypatch.setattr(benchmark, "run_smoke", lambda *args, **kwargs: result)
    monkeypatch.setattr(benchmark.sys, "stdout", console)

    assert benchmark.main(["--json"]) == 0
    assert "来" in "".join(console.writes)


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

def test_unicode_path_loader_uses_path_bytes_and_cv2_imdecode(monkeypatch):
    class FakePath:
        def read_bytes(self):
            return b"encoded-image"

    received = {}

    def fake_decode(payload, flags):
        received["payload"] = bytes(payload)
        received["flags"] = flags
        return "pixels"

    monkeypatch.setattr(benchmark.cv2, "imread", lambda *args, **kwargs: pytest.fail("cv2.imread must not load Unicode paths"))
    monkeypatch.setattr(benchmark.cv2, "imdecode", fake_decode)

    assert benchmark._load_color_image(FakePath()) == "pixels"
    assert received == {"payload": b"encoded-image", "flags": cv2.IMREAD_COLOR}


def test_summarize_rescue_quality_compares_final_output_to_baseline() -> None:
    summary = summarize_rescue_quality(
        [
            {"sample_source": "improved", "baseline_match_score": 0.4, "match_score": 0.8},
            {"sample_source": "equal", "baseline_match_score": 0.7, "match_score": 0.7},
            {"sample_source": "regressed", "baseline_match_score": 0.9, "match_score": 0.6},
        ]
    )

    assert summary["compared_cases"] == 3
    assert summary["improved_cases"] == 1
    assert summary["equal_cases"] == 1
    assert summary["regressed_cases"] == 1
    assert summary["regressions"] == [
        {
            "sample_source": "regressed",
            "baseline_match_score": 0.9,
            "match_score": 0.6,
            "delta": -0.30000000000000004,
        }
    ]


def test_require_rescue_no_regression_is_a_fail_closed_cli_gate(monkeypatch, capsys) -> None:
    result = {
        "image_count": 1,
        "case_count": 1,
        "successful_images": 1,
        "successful_cases": 1,
        "rescue_quality_gate_passed": False,
    }
    monkeypatch.setattr(benchmark, "run_smoke", lambda *args, **kwargs: result)

    assert benchmark.main(["--json", "--japanese-rescue", "--require-rescue-no-regression"]) == 1
    assert json.loads(capsys.readouterr().out)["rescue_quality_gate_passed"] is False


def test_rescue_quality_gate_requires_complete_results() -> None:
    summary = evaluate_rescue_quality_gate(
        [
            {"sample_source": "complete", "baseline_match_score": 0.5, "match_score": 0.5},
        ],
        complete=False,
        enabled=True,
    )

    assert summary["regressed_cases"] == 0
    assert summary["complete"] is False
    assert summary["passed"] is False
