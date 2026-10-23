import base64
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import vision_smoke_benchmark as benchmark
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


@pytest.mark.parametrize("height, expected_height, expected_width", [
    (95, 190, 1234),
    (159, 318, 1234),
    (160, 160, 617),
])
def test_small_image_scale_upscales_short_fixture_only(
    tmp_path, height, expected_height, expected_width,
) -> None:
    image_path = tmp_path / "synthetic.png"
    success, encoded = cv2.imencode(".png", np.zeros((height, 617, 3), dtype=np.uint8))
    assert success
    image_path.write_bytes(encoded.tobytes())

    baseline = image_parts(image_path)
    scaled = image_parts(image_path, small_image_scale=2.0)
    baseline_bytes = base64.b64decode(baseline[0]["inline_data"]["data"])
    scaled_bytes = base64.b64decode(scaled[0]["inline_data"]["data"])
    baseline_image = cv2.imdecode(np.frombuffer(baseline_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    scaled_image = cv2.imdecode(np.frombuffer(scaled_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)

    assert baseline_image.shape[:2] == (height, 617)
    assert scaled_image.shape[:2] == (expected_height, expected_width)

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


@pytest.mark.parametrize("flag", ["--japanese-rescue", "--require-rescue-no-regression"])
def test_parser_rejects_retired_rescue_flags(flag):
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args([flag])
    assert error.value.code == 2


def test_parser_exposes_gpu_only_controls() -> None:
    args = build_parser().parse_args(["--gpu-layers", "20", "--require-gpu"])

    assert args.gpu_layers == 20
    assert args.require_gpu is True


def test_parser_exposes_technical_coverage_gate() -> None:
    args = build_parser().parse_args(["--require-technical-coverage"])

    assert args.require_technical_coverage is True


def test_parser_exposes_anchor_coverage_gate() -> None:
    args = build_parser().parse_args(["--require-anchor-coverage"])

    assert args.require_anchor_coverage is True

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


def test_run_smoke_passes_runtime_api_key_to_provider(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    assert cv2.imwrite(str(image_path), np.zeros((95, 617, 3), dtype=np.uint8))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"cases": [{"sample_source": "sample.png", "category": "coverage_only"}]}),
        encoding="utf-8",
    )
    captured = {}

    class FakeVisionRuntime:
        api_key = "smoke-runtime-key"

        def __init__(self, *args, **kwargs):
            self.state = SimpleNamespace(
                name="ready",
                detail="",
                mode="cpu",
                base_url="http://vision",
            )

        def start(self):
            return self.state

        def stop(self):
            pass

    class FakeProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def transcribe_screenshot(self, parts, **kwargs):
            return SimpleNamespace(text="讀到的內容")

    monkeypatch.setattr(benchmark, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "LocalVisionRuntime", FakeVisionRuntime)
    monkeypatch.setattr(benchmark, "LocalMultimodalProvider", FakeProvider)

    benchmark.run_smoke(manifest_path, max_cases=1)

    assert captured["api_key"] == "smoke-runtime-key"


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


def test_require_anchor_coverage_rejects_fuzzy_only_result(monkeypatch, capsys) -> None:
    fuzzy_only = {
        "quality_basis": "ground_truth",
        "ground_truth_complete": True,
        "ground_truth_case_count": 1,
        "image_count": 1,
        "case_count": 1,
        "successful_images": 1,
        "successful_cases": 1,
        "line_match_cases": 0.0,
    }
    monkeypatch.setattr(benchmark, "run_smoke", lambda *args, **kwargs: fuzzy_only)

    assert benchmark.main(["--json", "--require-anchor-coverage"]) == 1
    assert json.loads(capsys.readouterr().out)["line_match_cases"] == 0.0


def test_require_anchor_coverage_accepts_complete_exact_result(monkeypatch, capsys) -> None:
    exact = {
        "quality_basis": "ground_truth",
        "ground_truth_complete": True,
        "ground_truth_case_count": 2,
        "image_count": 2,
        "case_count": 2,
        "successful_images": 2,
        "successful_cases": 2,
        "line_match_cases": 2.0,
    }
    monkeypatch.setattr(benchmark, "run_smoke", lambda *args, **kwargs: exact)

    assert benchmark.main(["--json", "--require-anchor-coverage"]) == 0
    assert json.loads(capsys.readouterr().out)["line_match_cases"] == 2.0

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
