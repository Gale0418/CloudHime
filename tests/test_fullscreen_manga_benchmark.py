from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import fullscreen_manga_benchmark as benchmark


def _synthetic_image() -> np.ndarray:
    image = np.zeros((180, 120, 3), dtype=np.uint8)
    image[12:169, 12:109] = 255
    return image


def _mock_image_load(monkeypatch) -> None:
    monkeypatch.setattr(
        benchmark.cv2,
        "imread",
        lambda *_args, **_kwargs: _synthetic_image(),
    )


class FakeWorker:
    instances: list["FakeWorker"] = []

    def __init__(self) -> None:
        self.scan_mode = ""
        self.auto_threshold_enabled = True
        self.binary_threshold = 100
        self.calls: list[tuple[object, ...]] = []
        self.cleaned = False
        self.page_region = (12, 12, 96, 156)
        FakeWorker.instances.append(self)

    def reload_ocr_backends(self, chain, log=True) -> None:
        self.calls.append(("reload", tuple(chain), log))

    def detect_manga_page_region(self, image):
        self.calls.append(("detect", image.shape))
        return self.page_region

    def normalize_manga_page_region(self, image, detected_region):
        self.calls.append(("normalize_page", detected_region))
        return detected_region

    def get_ocr_regions(self, image, page_region=None):
        self.calls.append(("regions", page_region))
        return [(0, 0, image.shape[1], image.shape[0])]

    def run_ocr_with_best_threshold(
        self,
        image,
        offset_x,
        offset_y,
        ocr_regions=None,
        candidate_thresholds=None,
        orientation_candidates=None,
    ):
        self.calls.append(
            (
                "ocr",
                tuple(ocr_regions or ()),
                tuple(candidate_thresholds or ()),
                tuple(orientation_candidates or ()),
            )
        )
        if len(ocr_regions or ()) == 6:
            return 112, [
                {"text": "切片一", "x": 20, "y": 20, "w": 30, "h": 12},
                {"text": "切片二", "x": 22, "y": 50, "w": 30, "h": 12},
            ]
        return 100, [
            {"text": "整頁文字", "x": 20, "y": 20, "w": 50, "h": 12},
            {"text": "第二行", "x": 20, "y": 50, "w": 40, "h": 12},
        ]

    def split_region_into_tiles(self, rect, cols=2, rows=3, overlap=0.12):
        self.calls.append(("split", rect, cols, rows, overlap))
        return [
            (12, 12, 52, 57),
            (56, 12, 52, 57),
            (12, 59, 52, 62),
            (56, 59, 52, 62),
            (12, 111, 52, 57),
            (56, 111, 52, 57),
        ]

    def cleanup(self) -> None:
        self.cleaned = True


def test_whole_page_extraction_does_not_trigger_tiles(monkeypatch):
    FakeWorker.instances.clear()
    monkeypatch.setattr(benchmark, "OCRWorker", FakeWorker)
    _mock_image_load(monkeypatch)

    result = benchmark.run_benchmark([Path("whole.png")], backend_chain=["windows"])

    assert result["complete"] is True
    image_result = result["images"][0]
    assert image_result["page_region"] == [12, 12, 96, 156]
    assert image_result["item_count"] == 2
    assert image_result["joined_text"] == "整頁文字\n第二行"
    assert image_result["tile_triggered"] is False
    assert not any(call[0] == "split" for call in FakeWorker.instances[0].calls)
    assert FakeWorker.instances[0].cleaned is True


def test_sparse_page_triggers_formal_2x3_tile_retry(monkeypatch):
    class SparseWorker(FakeWorker):
        def run_ocr_with_best_threshold(
            self,
            image,
            offset_x,
            offset_y,
            ocr_regions=None,
            candidate_thresholds=None,
            orientation_candidates=None,
        ):
            self.calls.append(
                (
                    "ocr",
                    tuple(ocr_regions or ()),
                    tuple(candidate_thresholds or ()),
                    tuple(orientation_candidates or ()),
                )
            )
            if len(ocr_regions or ()) == 6:
                return 112, [
                    {"text": "切片一", "x": 20, "y": 20, "w": 30, "h": 12},
                    {"text": "切片二", "x": 22, "y": 50, "w": 30, "h": 12},
                ]
            return 100, [{"text": "稀疏", "x": 20, "y": 20, "w": 30, "h": 12}]

    SparseWorker.instances.clear()
    monkeypatch.setattr(benchmark, "OCRWorker", SparseWorker)
    _mock_image_load(monkeypatch)

    result = benchmark.run_benchmark([Path("sparse.png")], backend_chain=["windows"])

    image_result = result["images"][0]
    assert image_result["tile_triggered"] is True
    ocr_calls = [call for call in SparseWorker.instances[0].calls if call[0] == "ocr"]
    assert len(ocr_calls) == 2
    assert ocr_calls[1][1] == (
        (12, 12, 52, 57),
        (56, 12, 52, 57),
        (12, 59, 52, 62),
        (56, 59, 52, 62),
        (12, 111, 52, 57),
        (56, 111, 52, 57),
    )
    assert ocr_calls[1][2] == (90, 100, 110)
    split_calls = [call for call in SparseWorker.instances[0].calls if call[0] == "split"]
    assert split_calls == [("split", (12, 12, 96, 156), 2, 3, 0.10)]
    assert result["complete"] is True


def test_json_schema_and_backend_override(monkeypatch, capsys):
    FakeWorker.instances.clear()
    monkeypatch.setattr(benchmark, "OCRWorker", FakeWorker)
    _mock_image_load(monkeypatch)

    assert benchmark.main(
        ["--backend", "tesseract,windows", "schema.png"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["backend_chain"] == ["tesseract", "windows"]
    assert FakeWorker.instances[0].calls[0] == (
        "reload",
        ("tesseract", "windows"),
        False,
    )
    assert payload["image_count"] == 1
    assert payload["complete"] is True
    item = payload["images"][0]
    assert set(item) == {
        "image",
        "page_region",
        "threshold",
        "items",
        "item_count",
        "joined_text",
        "elapsed_ms",
        "tile_triggered",
        "error",
    }
    assert set(item["items"][0]) == {"text", "x", "y", "w", "h"}


def test_error_and_require_complete_gate(monkeypatch, capsys):
    FakeWorker.instances.clear()
    monkeypatch.setattr(benchmark, "OCRWorker", FakeWorker)
    monkeypatch.setattr(benchmark.cv2, "imread", lambda *_args, **_kwargs: None)

    assert benchmark.main(["--require-complete", "missing.png"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["complete"] is False
    assert payload["images"][0]["error"] == "image_unreadable"
    assert payload["images"][0]["item_count"] == 0
    assert FakeWorker.instances[0].cleaned is True
