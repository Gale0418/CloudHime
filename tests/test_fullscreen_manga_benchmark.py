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
        benchmark,
        "_read_image",
        lambda *_args, **_kwargs: _synthetic_image(),
    )


def test_read_image_uses_unicode_safe_decode(monkeypatch):
    encoded = np.array([1, 2, 3], dtype=np.uint8)
    decoded = _synthetic_image()
    image_path = Path("轉生重騎士_テスト") / "001.jpg"
    file_calls = []
    decode_calls = []

    monkeypatch.setattr(
        benchmark.np,
        "fromfile",
        lambda path, dtype: file_calls.append((path, dtype)) or encoded,
    )

    def fake_decode(buffer, flags):
        decode_calls.append((buffer, flags))
        return decoded

    monkeypatch.setattr(benchmark.cv2, "imdecode", fake_decode)

    result = benchmark._read_image(image_path)

    assert result is decoded
    assert file_calls == [(str(image_path), np.uint8)]
    assert len(decode_calls) == 1
    received_buffer, received_flags = decode_calls[0]
    assert np.array_equal(received_buffer, encoded)
    assert received_flags == benchmark.cv2.IMREAD_COLOR


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


def test_benchmark_uses_product_manga_refinement_when_available(monkeypatch):
    class RefiningWorker(FakeWorker):
        def refine_manga_ocr_items(
            self,
            image,
            items,
            threshold,
            offset_x,
            offset_y,
        ):
            self.calls.append(("refine", threshold, offset_x, offset_y))
            return [
                {"text": "精修文字", "x": 20, "y": 20, "w": 50, "h": 12},
                items[1],
            ]

    RefiningWorker.instances.clear()
    monkeypatch.setattr(benchmark, "OCRWorker", RefiningWorker)
    _mock_image_load(monkeypatch)

    result = benchmark.run_benchmark([Path("refined.png")])

    assert result["images"][0]["joined_text"] == "精修文字\n第二行"
    assert ("refine", 100, 0, 0) in RefiningWorker.instances[0].calls


def test_benchmark_keeps_coarse_items_when_product_refinement_fails(monkeypatch):
    class FailingRefineWorker(FakeWorker):
        def refine_manga_ocr_items(self, *_args):
            raise RuntimeError("refine failed")

    FailingRefineWorker.instances.clear()
    monkeypatch.setattr(benchmark, "OCRWorker", FailingRefineWorker)
    _mock_image_load(monkeypatch)

    result = benchmark.run_benchmark([Path("refine-fallback.png")])

    assert result["complete"] is True
    assert result["images"][0]["joined_text"] == "整頁文字\n第二行"


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
        "grid_recovery_triggered",
        "grid_recovery_accepted",
        "error",
    }
    assert set(item["items"][0]) == {"text", "x", "y", "w", "h"}


def test_error_and_require_complete_gate(monkeypatch, capsys):
    FakeWorker.instances.clear()
    monkeypatch.setattr(benchmark, "OCRWorker", FakeWorker)
    monkeypatch.setattr(benchmark, "_read_image", lambda *_args, **_kwargs: None)

    assert benchmark.main(["--require-complete", "missing.png"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["complete"] is False
    assert payload["images"][0]["error"] == "image_unreadable"
    assert payload["images"][0]["item_count"] == 0
    assert FakeWorker.instances[0].cleaned is True
