from __future__ import annotations

import logging
from types import SimpleNamespace


import numpy as np

from cloudhime_workers import OCRWorker
from japanese_ocr_rescue import MeikiCandidate, MeikiCharacter
from japanese_ocr_runtime import JapaneseOCRRuntimeState


FIRST = "過ぎた街並は終りの愛と遠ぐ"
SECOND = "過ぎた街並は終わりの愛と遠くへ"
MEIKI = "過ぎた街並は終わりの愛と遠くた"


class FakeRuntime:
    state = JapaneseOCRRuntimeState.ready

    def __init__(self):
        chars = tuple(
            MeikiCharacter(char, 0.4 if index == len(MEIKI) - 1 else 0.99)
            for index, char in enumerate(MEIKI)
        )
        self.candidate = MeikiCandidate(MEIKI, chars)
        self.calls = 0

    def run(self, image):
        self.calls += 1
        return self.candidate


class FakeProvider:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def available(self):
        return True

    def transcribe_screenshot(self, image_parts, **kwargs):
        self.calls += 1
        return SimpleNamespace(text=self.text)


def _worker(second=SECOND):
    worker = OCRWorker.__new__(OCRWorker)
    worker.japanese_rescue_enabled = True
    worker.japanese_rescue_runtime = FakeRuntime()
    worker.local_multimodal_provider = FakeProvider(second)
    worker.build_ai_image_parts = lambda image: [{"inline_data": {"data": "x"}}]
    return worker


def test_worker_adopts_only_improved_wide_japanese_rescue():
    worker = _worker()
    image = np.zeros((50, 300, 3), dtype=np.uint8)

    assert worker.rescue_japanese_text(image, FIRST) == SECOND
    assert worker.japanese_rescue_runtime.calls == 1
    assert worker.local_multimodal_provider.calls == 1


def test_worker_gate_and_disabled_path_do_not_call_optional_runtime():
    worker = _worker()
    narrow = np.zeros((100, 100, 3), dtype=np.uint8)

    assert worker.rescue_japanese_text(narrow, FIRST) == FIRST
    worker.japanese_rescue_enabled = False
    assert worker.rescue_japanese_text(np.zeros((50, 300, 3), dtype=np.uint8), FIRST) == FIRST
    assert worker.japanese_rescue_runtime.calls == 0


def test_worker_keeps_baseline_when_second_transcription_is_worse():
    worker = _worker("完全不同")
    image = np.zeros((50, 300, 3), dtype=np.uint8)

    assert worker.rescue_japanese_text(image, FIRST) == FIRST
    assert worker.local_multimodal_provider.calls == 1


def test_worker_rejected_log_contains_outcome_and_scores_without_ocr_text(caplog):
    worker = _worker("完全不同")
    image = np.zeros((50, 300, 3), dtype=np.uint8)

    with caplog.at_level(logging.INFO, logger="CloudHime"):
        assert worker.rescue_japanese_text(image, FIRST) == FIRST

    messages = [
        record.getMessage()
        for record in caplog.records
        if "[Japanese rescue]" in record.getMessage()
    ]
    assert len(messages) == 1
    message = messages[0]
    assert "outcome=rejected" in message
    assert "first_similarity=" in message
    assert "second_similarity=" in message
    assert FIRST not in message
    assert "完全不同" not in message
