from __future__ import annotations

import pytest
from pathlib import Path

import japanese_ocr_runtime as runtime_module
from japanese_ocr_assets import JapaneseOCRAssets
from japanese_ocr_runtime import JapaneseOCRRuntime, JapaneseOCRRuntimeState


class FakeOCR:
    def __init__(self):
        self.warmup_calls = 0

    def run_ocr(self, image):
        self.warmup_calls += 1
        return [{"text": "日本語", "chars": [{"char": "日", "conf": 0.9}]}]

    def run_recognition(self, images):
        self.warmup_calls += 1
        return []


def _assets():
    root = Path("tests/_runtime_tmp")
    return JapaneseOCRAssets(
        root,
        root / "detect.onnx",
        root / "horizontal.onnx",
        root / "vertical.onnx",
    )


def test_runtime_reports_progress_and_runs(monkeypatch):
    progress = []
    monkeypatch.setattr(
        runtime_module,
        "ensure_japanese_ocr_assets",
        lambda assets, progress_callback=None, cancel_event=None: (
            progress_callback("downloading", 80) if progress_callback else None
        ) or assets,
    )
    monkeypatch.setattr(runtime_module, "_create_meiki_ocr", lambda assets: FakeOCR())
    runtime = JapaneseOCRRuntime(_assets(), lambda phase, value: progress.append((phase, value)))

    assert runtime.start()
    assert runtime.state is JapaneseOCRRuntimeState.ready
    assert progress == [("downloading", 80), ("warming_up", 85), ("ready", 100)]
    assert runtime.run(object()).text == "日本語"


def test_runtime_passes_cancel_event_to_asset_download(monkeypatch):
    seen = {}

    def ensure(assets, progress_callback=None, cancel_event=None):
        seen["cancel_event"] = cancel_event
        return assets

    monkeypatch.setattr(runtime_module, "ensure_japanese_ocr_assets", ensure)
    monkeypatch.setattr(runtime_module, "_create_meiki_ocr", lambda assets: FakeOCR())
    runtime = JapaneseOCRRuntime(_assets())

    assert runtime.start()
    assert seen["cancel_event"] is runtime._cancel


def test_runtime_failure_is_non_throwing_and_run_requires_ready(monkeypatch):
    monkeypatch.setattr(
        runtime_module,
        "ensure_japanese_ocr_assets",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    runtime = JapaneseOCRRuntime(_assets())

    assert not runtime.start()
    assert runtime.state is JapaneseOCRRuntimeState.failed
    assert "offline" in runtime.last_error
    with pytest.raises(RuntimeError, match="not ready"):
        runtime.run(object())