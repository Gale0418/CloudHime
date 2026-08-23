from __future__ import annotations

import pytest
from pathlib import Path
import threading

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


def test_stale_start_cannot_publish_after_disable_and_restart(monkeypatch):
    first_started = threading.Event()
    release_first = threading.Event()
    calls = []
    created = []

    def ensure(assets, progress_callback=None, cancel_event=None):
        calls.append(cancel_event)
        if len(calls) == 1:
            first_started.set()
            assert release_first.wait(2)
        return assets

    def create(_assets):
        ocr = FakeOCR()
        created.append(ocr)
        return ocr

    monkeypatch.setattr(runtime_module, "ensure_japanese_ocr_assets", ensure)
    monkeypatch.setattr(runtime_module, "_create_meiki_ocr", create)
    runtime = JapaneseOCRRuntime(_assets())
    first_result = []
    thread = threading.Thread(target=lambda: first_result.append(runtime.start()))
    thread.start()
    assert first_started.wait(2)

    runtime.disable()
    assert runtime.start()
    release_first.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert first_result == [False]
    assert runtime.state is JapaneseOCRRuntimeState.ready
    assert runtime._ocr is created[0]
    assert len(calls) == 2
    assert calls[0] is not calls[1]


def test_stale_start_exception_cannot_overwrite_new_generation(monkeypatch):
    first_started = threading.Event()
    second_started = threading.Event()
    release_first = threading.Event()
    release_second = threading.Event()
    calls = []

    def ensure(assets, progress_callback=None, cancel_event=None):
        calls.append(cancel_event)
        if len(calls) == 1:
            first_started.set()
            assert release_first.wait(2)
            raise RuntimeError("stale failure")
        second_started.set()
        assert release_second.wait(2)
        return assets

    monkeypatch.setattr(runtime_module, "ensure_japanese_ocr_assets", ensure)
    monkeypatch.setattr(runtime_module, "_create_meiki_ocr", lambda _assets: FakeOCR())
    runtime = JapaneseOCRRuntime(_assets())
    first_result = []
    second_result = []
    first_thread = threading.Thread(target=lambda: first_result.append(runtime.start()))
    first_thread.start()
    assert first_started.wait(2)

    runtime.disable()
    second_thread = threading.Thread(target=lambda: second_result.append(runtime.start()))
    second_thread.start()
    assert second_started.wait(2)

    release_first.set()
    first_thread.join(timeout=2)
    assert not first_thread.is_alive()
    assert first_result == [False]
    assert runtime.state is JapaneseOCRRuntimeState.starting
    assert runtime.last_error == ""

    release_second.set()
    second_thread.join(timeout=2)
    assert not second_thread.is_alive()
    assert second_result == [True]
    assert runtime.state is JapaneseOCRRuntimeState.ready
    assert len(calls) == 2
    assert calls[0] is not calls[1]

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