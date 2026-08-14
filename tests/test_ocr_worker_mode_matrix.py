from types import SimpleNamespace
from concurrent.futures import TimeoutError as FutureTimeoutError
from unittest.mock import Mock

import numpy as np
import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QFont

import cloudhime_workers as workers_module
from translation_providers import LocalRequestCancelled, TranslationResult
from scan_pipeline import ScanErrorCode, ScanOutcome, ScanStage
from cloudhime_ui import OverlayWindow
from cloudhime_workers import (
    OCRWorker,
    REGION_RENDER_BUBBLE,
    REGION_RENDER_RELIEF,
    REGION_RENDER_SCREENSHOT,
    SCAN_MODE_FULLSCREEN,
    SCAN_MODE_REGION,
)


def _configure_text_worker(worker, image):
    worker.ocr_backends = [object()]
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.detect_manga_page_region = lambda _img: None
    worker.get_ocr_regions = Mock(return_value=[(0, 0, image.shape[1], image.shape[0])])
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(100, [{"text": "Hello", "x": 10, "y": 12, "w": 40, "h": 16}])
    )
    worker.has_any_multimodal_ai = lambda: False
    worker.has_ai_text_provider = lambda: False
    worker.get_current_ai_provider = lambda: "google"
    worker.translate_items_with_ai_and_providers = lambda texts, _parts, _items: (
        ["你好"] * len(texts),
        ["google"] * len(texts),
    )
    worker.trigger_background_threshold_refresh = lambda *args, **kwargs: None


@pytest.mark.parametrize(
    ("scan_mode", "render_mode", "expect_region_detection"),
    [
        (SCAN_MODE_FULLSCREEN, REGION_RENDER_BUBBLE, True),
        (SCAN_MODE_REGION, REGION_RENDER_BUBBLE, False),
        (SCAN_MODE_REGION, REGION_RENDER_RELIEF, False),
    ],
)


def test_scan_worker_routes_fullscreen_region_bubble_and_relief_modes(
    qtbot, scan_mode, render_mode, expect_region_detection
):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = scan_mode
    worker.region_render_mode = render_mode
    worker.scan_region = (20, 10, 80, 40)
    finished = []
    worker.finished.connect(finished.append)

    try:
        worker.run_scan_once()

        assert finished == [[["你好", 10, 12, 40, 16]]]
        if expect_region_detection:
            worker.get_ocr_regions.assert_called_once()
            assert worker.run_ocr_with_best_threshold.call_args.args[3] == [(0, 0, 160, 80)]
        else:
            worker.get_ocr_regions.assert_not_called()
            assert worker.run_ocr_with_best_threshold.call_args.args[3] is None
    finally:
        worker.cleanup()


def test_scan_worker_routes_screenshot_mode_without_traditional_ocr(qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = []
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_SCREENSHOT
    worker.scan_region = (20, 10, 80, 40)
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.build_screenshot_text_hint = lambda _img: "Hello"
    worker.build_ai_image_parts = lambda _img: [{"inline_data": {"data": "Zm9v"}}]
    worker.translate_screenshot_gemma = lambda parts, hint: "截圖翻譯"
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.run_ocr_with_best_threshold = Mock(side_effect=AssertionError("screenshot must bypass OCR"))
    finished = []
    worker.finished.connect(finished.append)

    try:
        worker.run_scan_once()

        assert finished == [[["截圖翻譯", 7, 11, 160, 80]]]
        worker.run_ocr_with_best_threshold.assert_not_called()
    finally:
        worker.cleanup()


@pytest.mark.parametrize("render_mode", [REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF, REGION_RENDER_SCREENSHOT])


def test_overlay_builds_each_region_render_mode(qtbot, render_mode):
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    overlay.setGeometry(0, 0, 1000, 700)
    overlay.set_render_context(
        SCAN_MODE_REGION,
        render_mode,
        relief_offset_x=12,
        relief_offset_y=-8,
        scan_region=(400, 250, 200, 120),
    )

    try:
        overlay.update_bubbles([("翻譯", 450, 280, 80, 30)])

        assert len(overlay.bubbles) == 1
        bubble = overlay.bubbles[0]
        assert bubble.render_mode == render_mode
        assert bubble.geometry().width() > 0
        assert bubble.geometry().height() > 0
        if render_mode == REGION_RENDER_RELIEF:
            assert bubble.wordWrap() == 0
        if render_mode == REGION_RENDER_SCREENSHOT:
            assert not bubble.geometry().intersects(QRect(*overlay.scan_region))
    finally:
        overlay.clear_all()
        overlay.close()


def test_transbubble_font_inheritance(qtbot):
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)

    test_font = QFont("Arial", 12)
    overlay.setFont(test_font)

    overlay.set_render_context(
        SCAN_MODE_REGION,
        REGION_RENDER_BUBBLE,
        scan_region=(0, 0, 100, 100),
    )
    overlay.update_bubbles([("Test", 10, 10, 50, 20)])

    assert len(overlay.bubbles) == 1
    bubble = overlay.bubbles[0]

    assert bubble.font().family() == "Arial"
    assert bubble._get_bubble_font(16).family() == "Arial"
    assert bubble.font().bold() is True

    overlay.clear_all()
    overlay.close()


def _configure_region_cache_worker(worker, image):
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_BUBBLE
    worker.scan_region = (20, 10, image.shape[1], image.shape[0])


def test_region_exact_image_hit_bypasses_ocr_and_translation(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    ocr = worker.run_ocr_with_best_threshold
    translate = Mock(return_value=(["Nihao"], ["google"]))
    worker.translate_items_with_ai_and_providers = translate
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        worker.run_scan_once()

        assert ocr.call_count == 1
        assert translate.call_count == 1
        assert finished[0] == [["Nihao", 10, 12, 40, 16]]
        assert finished[1] == finished[0]
    finally:
        worker.cleanup()


def test_region_one_pixel_change_repeats_ocr_even_when_text_is_same(monkeypatch, qtbot):
    first = np.zeros((40, 80, 3), dtype=np.uint8)
    second = first.copy()
    second[0, 0, 0] = 1
    images = iter([first, second])
    worker = OCRWorker()
    _configure_region_cache_worker(worker, first)
    worker.capture_scan_area = lambda: (next(images), 7, 11)
    ocr = worker.run_ocr_with_best_threshold
    translate = Mock(return_value=(["Nihao"], ["google"]))
    worker.translate_items_with_ai_and_providers = translate
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        worker.run_scan_once()

        assert ocr.call_count == 2
        assert translate.call_count == 2
        assert finished[0] == [["Nihao", 10, 12, 40, 16]]
        assert finished[1] == finished[0]
        shadow_event = next(
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.FRAME_CACHE
        )
        assert shadow_event.detail == "frame_cache_shadow_near"
        assert shadow_event.item_count <= 64 * 64
    finally:
        worker.cleanup()


@pytest.mark.parametrize("change", ["offset", "target", "prompt", "region", "auto_switch", "rescue_ready"])


def test_region_same_image_context_change_is_a_cache_miss(monkeypatch, qtbot, change):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    captures = [(image, 7, 11), (image, 8, 11)] if change == "offset" else [(image, 7, 11)] * 2
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    if change == "target":
        worker.translation_target_lang = "zh-TW"
    elif change == "rescue_ready":
        worker.japanese_rescue_enabled = True
        worker.has_any_multimodal_ai = lambda: True
    worker.capture_scan_area = lambda: captures.pop(0)
    ocr = worker.run_ocr_with_best_threshold
    translate = Mock(return_value=(["Nihao"], ["google"]))
    worker.translate_items_with_ai_and_providers = translate
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        if change == "target":
            worker.translation_target_lang = "en"
        elif change == "prompt":
            worker.gemma_prompt = "changed prompt"
        elif change == "region":
            worker.scan_region = (30, 10, image.shape[1], image.shape[0])
        elif change == "auto_switch":
            worker.gemma_auto_switch_enabled = not worker.gemma_auto_switch_enabled
        elif change == "rescue_ready":
            worker.japanese_rescue_runtime.state = workers_module.JapaneseOCRRuntimeState.ready
        worker.run_scan_once()

        assert ocr.call_count == 2
        assert translate.call_count == 2
        assert len(finished) == 2
    finally:
        worker.cleanup()


def test_screenshot_exact_hit_bypasses_hint_parts_and_translation(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = []
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_SCREENSHOT
    worker.scan_region = (20, 10, 80, 40)
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.build_screenshot_text_hint = Mock(return_value="Hello")
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "Zm9v"}}])
    worker.translate_screenshot_gemma = Mock(return_value="Screenshot")
    worker.run_ocr_with_best_threshold = Mock(side_effect=AssertionError("screenshot must bypass OCR"))
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        worker.build_screenshot_text_hint.side_effect = AssertionError("cache hit must bypass hint")
        worker.build_ai_image_parts.side_effect = AssertionError("cache hit must bypass parts")
        worker.translate_screenshot_gemma.side_effect = AssertionError("cache hit must bypass translation")
        worker.run_scan_once()
        assert worker.build_screenshot_text_hint.call_count == 0
        assert worker.build_ai_image_parts.call_count == 1
        assert worker.translate_screenshot_gemma.call_count == 1
        assert finished[0] == [["Screenshot", 7, 11, 160, 80]]
        assert finished[1] == finished[0]
    finally:
        worker.cleanup()


def test_screenshot_cache_skips_ocr_hint_after_local_vision_success(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = []
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = True
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_SCREENSHOT
    worker.scan_region = (20, 10, 80, 40)
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"

    def build_hint(_image):
        worker.set_binary_threshold(120)
        return "Hello"

    worker.build_screenshot_text_hint = Mock(side_effect=build_hint)
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "Zm9v"}}])
    worker.translate_screenshot_gemma = Mock(return_value="Screenshot")
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        worker.run_scan_once()

        assert worker.binary_threshold == 100
        assert worker.build_screenshot_text_hint.call_count == 0
        assert worker.translate_screenshot_gemma.call_count == 1
        assert finished[1] == finished[0]
    finally:
        worker.cleanup()

@pytest.mark.parametrize("failure", ["exception", "empty"])


def test_screenshot_failure_or_empty_result_is_not_cached(monkeypatch, qtbot, failure):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = []
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_SCREENSHOT
    worker.scan_region = (20, 10, 80, 40)
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.build_screenshot_text_hint = Mock(return_value="Hello")
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "Zm9v"}}])
    first_result = RuntimeError("temporary failure") if failure == "exception" else ""
    worker.translate_screenshot_gemma = Mock(side_effect=[first_result, "Screenshot"])
    worker.translate_text_preferred_with_provider = Mock(side_effect=RuntimeError("fallback failure"))
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        assert len(worker.exact_image_cache) == 0
        expected_hint_calls = 1 if failure == "exception" else 0
        assert worker.build_screenshot_text_hint.call_count == expected_hint_calls
        worker.run_scan_once()

        assert worker.translate_screenshot_gemma.call_count == 2
        assert len(worker.exact_image_cache) == 1
        assert finished[0] == []
        assert finished[1] == [["Screenshot", 7, 11, 160, 80]]
    finally:
        worker.cleanup()


def test_fullscreen_ocr_scale_caps_large_inputs_without_changing_normal_screens(qtbot):
    worker = OCRWorker()
    try:
        worker.scan_mode = SCAN_MODE_FULLSCREEN
        assert worker.get_ocr_scale_factor(1920, 1080) == 3.0
        assert worker.get_ocr_scale_factor(2809, 4096) == 1.5

        worker.scan_mode = SCAN_MODE_REGION
        assert worker.get_ocr_scale_factor(1200, 800) == 1.5
    finally:
        worker.cleanup()


def test_manga_page_region_uses_full_portrait_image_for_missing_or_tiny_detection(qtbot):
    worker = OCRWorker()
    image = np.zeros((1200, 900, 3), dtype=np.uint8)
    try:
        assert worker.normalize_manga_page_region(image, None) == (0, 0, 900, 1200)
        assert worker.normalize_manga_page_region(image, (0, 850, 300, 250)) == (0, 0, 900, 1200)
        assert worker.normalize_manga_page_region(image, (20, 80, 820, 1050)) == (20, 80, 820, 1050)
    finally:
        worker.cleanup()


def test_manga_page_region_accepts_tall_manga_screenshot_boundaries(qtbot):
    worker = OCRWorker()
    tall_page = np.zeros((1235, 788, 3), dtype=np.uint8)
    narrow_page = np.zeros((1283, 825, 3), dtype=np.uint8)
    try:
        assert worker.normalize_manga_page_region(tall_page, (22, 72, 190, 311)) == (0, 0, 788, 1235)
        assert worker.normalize_manga_page_region(narrow_page, None) == (0, 0, 825, 1283)
    finally:
        worker.cleanup()


def test_manga_page_region_does_not_treat_landscape_screen_as_page(qtbot):
    worker = OCRWorker()
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    try:
        assert worker.normalize_manga_page_region(image, None) is None
    finally:
        worker.cleanup()


def test_manga_visual_rescue_gate_detects_fragments_but_keeps_reasonable_text(qtbot):
    worker = OCRWorker()
    image = np.zeros((4096, 2809, 3), dtype=np.uint8)
    sparse_items = [
        {"text": "プイ、", "x": 602, "y": 1674, "w": 117, "h": 266},
        {"text": ": こヾ:", "x": 303, "y": 2167, "w": 14, "h": 60},
        {"text": "、 子気ジ", "x": 481, "y": 2169, "w": 12, "h": 68},
        {"text": "いと 3", "x": 2223, "y": 3120, "w": 8, "h": 25},
        {"text": "、 ゞ:を", "x": 874, "y": 3487, "w": 42, "h": 7},
        {"text": "・ 0: 0 ン", "x": 1483, "y": 3485, "w": 32, "h": 6},
    ]
    reasonable_items = [
        {"text": "誌雜局見て眼", "x": 715, "y": 2178, "w": 447, "h": 41},
        {"text": "另一段合理文字", "x": 300, "y": 1200, "w": 220, "h": 50},
    ]
    short_fragment = [
        {"text": "物ツノ /", "x": 48, "y": 391, "w": 23, "h": 119},
    ]
    try:
        assert worker.should_rescue_manga_ocr(
            image,
            (0, 0, 2809, 4096),
            sparse_items,
        ) is True
        assert worker.should_rescue_manga_ocr(
            image,
            (0, 0, 1562, 2260),
            reasonable_items,
        ) is False
        assert worker.should_rescue_manga_ocr(
            image,
            (0, 0, 411, 480),
            short_fragment,
        ) is True
        repeated = "ロ" * 40 + " ご" + "ロ" * 20
        assert worker.is_degenerate_manga_transcription(repeated) is True
    finally:
        worker.cleanup()


def test_manga_ocr_reliability_gate_is_conservative():
    assert OCRWorker.is_unreliable_manga_ocr([]) is True
    assert OCRWorker.is_unreliable_manga_ocr([{"text": "S : / S -- ???"}]) is True
    assert OCRWorker.is_unreliable_manga_ocr([{"text": "君は私の呪いも解いてくれた"}]) is False
    assert OCRWorker.is_unreliable_manga_ocr([{"text": "短文"}]) is False


def test_manga_adaptive_regions_are_bounded_and_offset_aware(qtbot):
    worker = OCRWorker()
    items = [
        {"text": "大きい", "x": 120, "y": 220, "w": 300, "h": 120},
        {"text": "重複", "x": 130, "y": 230, "w": 280, "h": 110},
        {"text": "縦書き", "x": 610, "y": 220, "w": 70, "h": 280},
        {"text": "小さすぎる", "x": 20, "y": 30, "w": 5, "h": 5},
        {"text": "拡張すると広すぎる", "x": 100, "y": 200, "w": 500, "h": 400},
        {"text": "広すぎる", "x": 100, "y": 200, "w": 790, "h": 900},
    ]
    try:
        regions = worker.build_manga_adaptive_regions(
            items,
            800,
            1000,
            offset_x=100,
            offset_y=200,
        )

        assert len(regions) == 2
        assert any(region[3] >= region[2] * 1.3 for region in regions)
        assert all(0 <= x and 0 <= y and w > 0 and h > 0 and x + w <= 800 and y + h <= 1000 for x, y, w, h in regions)
    finally:
        worker.cleanup()


def test_manga_adaptive_refine_routes_orientation_and_replaces_only_better(qtbot):
    worker = OCRWorker()
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    baseline = [
        {"text": "改善前的横文", "x": 100, "y": 100, "w": 300, "h": 100},
        {"text": "改善前的縦文", "x": 520, "y": 100, "w": 70, "h": 300},
    ]
    calls = []

    def run_ocr(_img, _ox, _oy, regions, thresholds, orientations, **_kwargs):
        calls.append((list(regions), list(thresholds), list(orientations)))
        if orientations == [90, 270]:
            return 100, [
                {"text": "改善された縦書き", "x": 520, "y": 100, "w": 70, "h": 300}
            ]
        return 100, [
            {"text": "改善された横書き", "x": 100, "y": 100, "w": 300, "h": 100}
        ]

    def score(items):
        total = sum(20 if "改善された" in item["text"] else 10 for item in items)
        return total, list(items)

    worker.run_ocr_with_best_threshold = run_ocr
    worker.score_ocr_items = score
    try:
        refined = worker.refine_manga_ocr_items(image, baseline, 100)

        assert [item["text"] for item in refined] == [
            "改善された横書き",
            "改善された縦書き",
        ]
        assert {tuple(call[2]) for call in calls} == {(90, 270), (0,)}
        assert all(call[1] == [100] for call in calls)
    finally:
        worker.cleanup()


def test_manga_adaptive_refine_keeps_baseline_when_candidate_is_weaker(qtbot):
    worker = OCRWorker()
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    baseline = [
        {"text": "十分に良い文章", "x": 100, "y": 100, "w": 300, "h": 100},
        {"text": "別の文章", "x": 500, "y": 100, "w": 80, "h": 300},
    ]
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(
            100,
            [{"text": "弱い", "x": 100, "y": 100, "w": 300, "h": 100}],
        )
    )
    worker.score_ocr_items = lambda items: (
        sum(20 if "良い" in item["text"] or "別の" in item["text"] else 1 for item in items),
        list(items),
    )
    try:
        assert worker.refine_manga_ocr_items(image, baseline, 100) == baseline
    finally:
        worker.cleanup()


def test_manga_adaptive_refine_rejects_partial_candidate(qtbot):
    worker = OCRWorker()
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    baseline = [
        {"text": "第一段文字", "x": 100, "y": 100, "w": 200, "h": 100},
        {"text": "第二段文字", "x": 500, "y": 300, "w": 200, "h": 100},
    ]
    worker.build_manga_adaptive_regions = Mock(return_value=[(50, 50, 700, 500)])
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(
            100,
            [{"text": "第一段文字修正", "x": 100, "y": 100, "w": 200, "h": 100}],
        )
    )
    worker.score_ocr_items = lambda items: (
        sum(100 if "修正" in item["text"] else 10 for item in items),
        list(items),
    )
    try:
        assert worker.refine_manga_ocr_items(image, baseline, 100) == baseline
    finally:
        worker.cleanup()


def test_manga_adaptive_refine_rejects_partial_geometry_candidate(qtbot):
    worker = OCRWorker()
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    baseline = [
        {"text": "第一段文字", "x": 100, "y": 100, "w": 200, "h": 100},
        {"text": "第二段文字", "x": 500, "y": 300, "w": 200, "h": 100},
    ]
    worker.build_manga_adaptive_regions = Mock(return_value=[(50, 50, 700, 500)])
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(
            100,
            [
                {"text": "第一段文字修正", "x": 100, "y": 100, "w": 100, "h": 100},
                {"text": "第二段文字修正", "x": 500, "y": 300, "w": 200, "h": 100},
            ],
        )
    )
    worker.score_ocr_items = lambda items: (
        sum(100 if "修正" in item["text"] else 10 for item in items),
        list(items),
    )
    try:
        assert worker.refine_manga_ocr_items(image, baseline, 100) == baseline
    finally:
        worker.cleanup()


def test_manga_adaptive_refine_rejects_unrelated_longer_candidate(qtbot):
    worker = OCRWorker()
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    baseline = [
        {"text": "第一段文字", "x": 100, "y": 100, "w": 200, "h": 100},
        {"text": "第二段文字", "x": 500, "y": 300, "w": 200, "h": 100},
    ]
    worker.build_manga_adaptive_regions = Mock(return_value=[(50, 50, 700, 500)])
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(
            100,
            [
                {"text": "完全不同的錯誤長句一", "x": 100, "y": 100, "w": 200, "h": 100},
                {"text": "完全不同的錯誤長句二", "x": 500, "y": 300, "w": 200, "h": 100},
            ],
        )
    )
    worker.score_ocr_items = lambda items: (
        sum(100 if "錯誤" in item["text"] else 10 for item in items),
        list(items),
    )
    try:
        assert worker.refine_manga_ocr_items(image, baseline, 100) == baseline
    finally:
        worker.cleanup()


def test_manga_adaptive_region_uses_half_open_boundaries(qtbot):
    worker = OCRWorker()
    try:
        assert worker.item_center_in_region(
            {"x": 110, "y": 10, "w": 20, "h": 20},
            (0, 0, 120, 120),
        ) is False
    finally:
        worker.cleanup()


def test_scan_worker_invokes_manga_refine_with_capture_offset(monkeypatch, qtbot):
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.detect_manga_page_region = lambda _img: (0, 0, 800, 1000)
    baseline = [
        {"text": "第一段文字", "x": 100, "y": 100, "w": 200, "h": 100},
        {"text": "第二段文字", "x": 500, "y": 300, "w": 200, "h": 100},
    ]
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, baseline))
    worker.refine_manga_ocr_items = Mock(
        return_value=[
            {"text": "第一段文字修正", "x": 107, "y": 111, "w": 200, "h": 100},
            {"text": "第二段文字修正", "x": 507, "y": 311, "w": 200, "h": 100},
        ]
    )
    finished = []
    worker.finished.connect(finished.append)

    try:
        worker.run_scan_once()

        worker.refine_manga_ocr_items.assert_called_once()
        call = worker.refine_manga_ocr_items.call_args.args
        assert call[1] == baseline
        assert call[2:] == (100, 7, 11)
        assert finished == [[
            ["你好", 107, 111, 200, 100],
            ["你好", 507, 311, 200, 100],
        ]]
    finally:
        worker.cleanup()


def test_manga_rescue_crops_detected_page_before_multimodal_ocr(qtbot):
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    worker = OCRWorker()
    provider = SimpleNamespace(
        transcribe_screenshot=Mock(
            return_value=SimpleNamespace(text="何を言うんだ！")
        )
    )
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker._get_translation_provider = lambda _name: provider
    worker.build_screenshot_text_hint = Mock(return_value="")
    worker.build_ai_image_parts = Mock(
        return_value=[{"inline_data": {"data": "cropped"}}]
    )

    try:
        rescued, parts = worker.rescue_unreliable_manga_items(
            image,
            (100, 200, 400, 500),
            [{"text": "S : / S -- ???"}],
            7,
            11,
            image_parts=[{"inline_data": {"data": "full"}}],
        )

        assert worker.build_screenshot_text_hint.call_args.args[0].shape == (500, 400, 3)
        assert worker.build_ai_image_parts.call_args.args[0].shape == (500, 400, 3)
        assert parts == [{"inline_data": {"data": "cropped"}}]
        assert rescued == [
            {
                "text": "何を言うんだ！",
                "x": 107,
                "y": 211,
                "w": 400,
                "h": 500,
                "confidence": None,
            }
        ]
    finally:
        worker.cleanup()


@pytest.mark.parametrize(
    ("candidate_score", "accepted"),
    [(24, True), (22, False)],
)


def test_manga_grid_recovery_is_opt_in_and_score_gated(
    monkeypatch,
    qtbot,
    candidate_score,
    accepted,
):
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    worker = OCRWorker()
    baseline = [
        {"text": "基準文字一", "x": 20, "y": 20, "w": 60, "h": 30},
        {"text": "基準文字二", "x": 120, "y": 120, "w": 60, "h": 30},
    ]
    candidate = [
        {"text": "候選文字一", "x": 20, "y": 20, "w": 60, "h": 30},
        {"text": "候選文字二", "x": 120, "y": 120, "w": 60, "h": 30},
    ]
    worker.split_region_into_tiles = Mock(return_value=[(0, 0, 200, 200)])
    worker.run_ocr_with_best_threshold = Mock(return_value=(110, candidate))
    worker.score_ocr_items = Mock(
        side_effect=[(20, baseline), (candidate_score, candidate)]
    )

    try:
        assert worker.try_manga_grid_recovery(
            image,
            (0, 0, 400, 400),
            baseline,
            100,
            [0, 90, 270],
        ) == (100, baseline)
        worker.run_ocr_with_best_threshold.assert_not_called()

        monkeypatch.setenv("CLOUDHIME_MANGA_GRID_RECOVERY", "1")
        threshold, recovered = worker.try_manga_grid_recovery(
            image,
            (0, 0, 400, 400),
            baseline,
            100,
            [0, 90, 270],
        )
        if accepted:
            assert threshold == 110
            assert recovered == candidate
        else:
            assert threshold == 100
            assert recovered == baseline
        worker.run_ocr_with_best_threshold.assert_called_once()
    finally:
        worker.cleanup()


def test_local_manga_crop_context_is_opt_in_and_preserves_all_items(monkeypatch, qtbot):
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.has_local_multimodal_ai = lambda: True
    provider = SimpleNamespace(available=lambda: True, transcribe_screenshot=Mock())
    worker._get_translation_provider = lambda name: provider if name == "local_multimodal" else None
    worker.build_ai_image_parts = Mock(side_effect=lambda crop: [{"inline_data": {"data": str(crop.shape)}}])
    items = [
        {"text": "第一段文字", "x": 80, "y": 90, "w": 60, "h": 36},
        {"text": "第二段文字", "x": 250, "y": 260, "w": 60, "h": 36},
    ]

    try:
        monkeypatch.setenv("CLOUDHIME_MANGA_CROP_CONTEXT", "1")
        parts = worker.build_local_manga_crop_context(image, (0, 0, 400, 400), items)

        assert parts is not None
        assert len(parts) == 2
        assert worker.build_ai_image_parts.call_count == 2
        assert all(item["text"].startswith("第") for item in items)
    finally:
        worker.cleanup()


def test_local_manga_crop_regions_group_nearby_items_and_cover_centers(qtbot):
    worker = OCRWorker()
    items = [
        {"text": "第一段文字", "x": 20, "y": 20, "w": 30, "h": 24},
        {"text": "第二段文字", "x": 95, "y": 20, "w": 30, "h": 24},
        {"text": "第三段文字", "x": 170, "y": 20, "w": 30, "h": 24},
        {"text": "第四段文字", "x": 20, "y": 110, "w": 30, "h": 24},
        {"text": "第五段文字", "x": 95, "y": 110, "w": 30, "h": 24},
    ]
    try:
        regions = worker.build_local_manga_crop_regions(items, 400, 400)
        assert 1 <= len(regions) <= 4
        assert all(
            any(worker.item_center_in_region(item, region) for region in regions)
            for item in items
        )
        assert all(width * height <= 400 * 400 * 0.30 for _, _, width, height in regions)
    finally:
        worker.cleanup()


def test_local_manga_crop_batches_fail_open_when_provider_is_unavailable(monkeypatch, qtbot):
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.has_local_multimodal_ai = lambda: True
    provider = SimpleNamespace(available=False, transcribe_screenshot=Mock())
    worker._get_translation_provider = lambda name: provider if name == "local_multimodal" else None
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "crop"}}])
    items = [
        {"text": "第一段文字", "x": 20, "y": 20, "w": 40, "h": 30},
        {"text": "第二段文字", "x": 120, "y": 120, "w": 40, "h": 30},
    ]

    try:
        monkeypatch.setenv("CLOUDHIME_MANGA_CROP_CONTEXT", "1")
        assert worker.build_local_manga_crop_batches(image, (0, 0, 200, 200), items) is None
        assert worker.build_local_manga_crop_context(image, (0, 0, 200, 200), items) is None
        worker.build_ai_image_parts.assert_not_called()
    finally:
        worker.cleanup()


def test_local_manga_crop_context_fails_open_when_disabled_or_not_all_items_fit(monkeypatch, qtbot):
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.has_local_multimodal_ai = lambda: True
    provider = SimpleNamespace(available=lambda: True, transcribe_screenshot=Mock())
    worker._get_translation_provider = lambda name: provider if name == "local_multimodal" else None
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "crop"}}])
    items = [
        {"text": "第一段文字", "x": 20 + (index % 5) * 75, "y": 40 + (index // 5) * 90, "w": 30, "h": 24}
        for index in range(4)
    ] + [
        {"text": "過大的文字區塊", "x": 0, "y": 0, "w": 390, "h": 390}
    ]

    try:
        assert worker.build_local_manga_crop_context(image, (0, 0, 400, 400), items) is None
        monkeypatch.setenv("CLOUDHIME_MANGA_CROP_CONTEXT", "1")
        assert worker.build_local_manga_crop_context(image, (0, 0, 400, 400), items) is None
        worker.build_ai_image_parts.assert_not_called()
    finally:
        worker.cleanup()


def test_local_manga_crop_batches_map_indexes_and_keep_region_parts(monkeypatch, qtbot):
    image = np.zeros((120, 240, 3), dtype=np.uint8)
    image[:, 120:, 0] = 2
    worker = OCRWorker()
    worker.has_local_multimodal_ai = lambda: True
    provider = SimpleNamespace(available=lambda: True, transcribe_screenshot=Mock())
    worker._get_translation_provider = lambda name: provider if name == "local_multimodal" else None
    worker.build_local_manga_crop_regions = Mock(
        return_value=[(0, 0, 110, 120), (130, 0, 110, 120)]
    )
    worker.build_ai_image_parts = Mock(
        side_effect=lambda crop: [{"inline_data": {"data": str(int(crop[0, 0, 0]))}}]
    )
    items = [
        {"text": "左一", "x": 10, "y": 20, "w": 30, "h": 24},
        {"text": "左二", "x": 60, "y": 60, "w": 30, "h": 24},
        {"text": "右一", "x": 150, "y": 20, "w": 30, "h": 24},
        {"text": "右二", "x": 190, "y": 60, "w": 30, "h": 24},
    ]

    try:
        monkeypatch.setenv("CLOUDHIME_MANGA_CROP_CONTEXT", "1")
        batches = worker.build_local_manga_crop_batches(
            image,
            (0, 0, 240, 120),
            items,
        )

        assert [batch["item_indexes"] for batch in batches] == [[0, 1], [2, 3]]
        assert [batch["image_parts"] for batch in batches] == [
            [{"inline_data": {"data": "0"}}],
            [{"inline_data": {"data": "2"}}],
        ]
        assert worker.build_ai_image_parts.call_count == 2
    finally:
        worker.cleanup()


@pytest.mark.parametrize("failure", ["exception", "length"])


def test_local_manga_crop_batch_translation_fails_open_per_region(failure, qtbot):
    worker = OCRWorker()
    items = [
        {"text": "左邊", "x": 10, "y": 20, "w": 30, "h": 24},
        {"text": "右邊", "x": 150, "y": 20, "w": 30, "h": 24},
    ]
    batches = [
        {"item_indexes": [0], "image_parts": [{"inline_data": {"data": "left"}}]},
        {"item_indexes": [1], "image_parts": [{"inline_data": {"data": "right"}}]},
    ]
    calls = []

    def translate(texts, parts, batch_items):
        calls.append((texts, parts, batch_items))
        if parts[0]["inline_data"]["data"] == "right":
            if failure == "exception":
                raise RuntimeError("region failed")
            return ["太多", "結果"], ["local_multimodal", "local_multimodal"]
        return ["左翻譯"], ["local_multimodal"]

    worker.translate_items_with_ai_and_providers = Mock(side_effect=translate)
    try:
        translated, providers = worker.translate_local_manga_crop_batches(
            [item["text"] for item in items],
            items,
            batches,
        )

        assert translated == ["左翻譯", None]
        assert providers == ["local_multimodal", None]
        assert calls[0] == (
            ["左邊"],
            [{"inline_data": {"data": "left"}}],
            [items[0]],
        )
        assert calls[1][0] == ["右邊"]
        assert calls[1][1] == [{"inline_data": {"data": "right"}}]
    finally:
        worker.cleanup()


def test_manga_tile_retry_exception_preserves_previous_ocr_items(monkeypatch, qtbot):
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.detect_manga_page_region = lambda _img: (0, 0, 800, 1000)
    baseline = [{"text": "守りに特化で", "x": 20, "y": 30, "w": 120, "h": 36}]
    worker.run_ocr_with_best_threshold = Mock(
        side_effect=[(100, baseline), RuntimeError("tile retry failed")]
    )
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert worker.last_results == [("你好", 20, 30, 120, 36)]
        assert worker.run_ocr_with_best_threshold.call_count == 2
        ocr_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.OCR
        ]
        assert ocr_events[-1].outcome is not ScanOutcome.NO_TEXT
    finally:
        worker.cleanup()

def test_scan_worker_uses_local_manga_crop_batches_before_full_page_parts(monkeypatch, qtbot):
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.detect_manga_page_region = lambda _img: (0, 0, 400, 400)
    baseline = [
        {"text": "第一段文字", "x": 80, "y": 90, "w": 60, "h": 36},
        {"text": "第二段文字", "x": 250, "y": 260, "w": 60, "h": 36},
    ]
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, baseline))
    worker.refine_manga_ocr_items = Mock(return_value=baseline)
    worker.has_any_multimodal_ai = lambda: True
    worker.build_local_manga_crop_batches = Mock(
        return_value=[
            {
                "item_indexes": [0, 1],
                "image_parts": [{"inline_data": {"data": "crop"}}],
            }
        ]
    )
    worker.translate_items_with_ai_and_providers = Mock(
        return_value=(["第一段翻譯", "第二段翻譯"], ["local_multimodal", "local_multimodal"])
    )
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setenv("CLOUDHIME_MANGA_CROP_CONTEXT", "1")

    try:
        worker.run_scan_once()

        worker.build_local_manga_crop_batches.assert_called_once()
        call = worker.translate_items_with_ai_and_providers.call_args.args
        assert call[0] == ["第一段文字", "第二段文字"]
        assert call[1] == [{"inline_data": {"data": "crop"}}]
        assert call[2] == baseline
    finally:
        worker.cleanup()


def test_scan_worker_falls_back_to_full_page_when_all_crop_batches_fail(monkeypatch, qtbot):
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.detect_manga_page_region = lambda _img: (0, 0, 400, 400)
    baseline = [
        {"text": "第一段文字", "x": 80, "y": 90, "w": 60, "h": 36},
        {"text": "第二段文字", "x": 250, "y": 260, "w": 60, "h": 36},
    ]
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, baseline))
    worker.refine_manga_ocr_items = Mock(return_value=baseline)
    worker.has_any_multimodal_ai = lambda: True
    worker.build_local_manga_crop_batches = Mock(
        return_value=[
            {
                "item_indexes": [0, 1],
                "image_parts": [{"inline_data": {"data": "crop"}}],
            }
        ]
    )
    worker.build_ai_image_parts = Mock(
        return_value=[{"inline_data": {"data": "full"}}]
    )
    worker.translate_items_with_ai_and_providers = Mock(
        side_effect=[
            ([None, None], [None, None]),
            (["第一段翻譯", "第二段翻譯"], ["local_multimodal", "local_multimodal"]),
        ]
    )
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setenv("CLOUDHIME_MANGA_CROP_CONTEXT", "1")

    try:
        worker.run_scan_once()

        assert worker.build_ai_image_parts.call_count == 1
        assert worker.build_ai_image_parts.call_args.args[0] is image
        assert worker.translate_items_with_ai_and_providers.call_count == 2
    finally:
        worker.cleanup()


def test_portrait_latin_screen_does_not_trigger_manga_rescue(monkeypatch, qtbot):
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(100, [{"text": "S : / S -- ???", "x": 10, "y": 12, "w": 40, "h": 16}])
    )
    worker.has_any_multimodal_ai = lambda: True
    worker.rescue_unreliable_manga_items = Mock()
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        worker.rescue_unreliable_manga_items.assert_not_called()
    finally:
        worker.cleanup()


def test_fullscreen_unreliable_manga_ocr_uses_multimodal_page_rescue(monkeypatch, qtbot):
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.detect_manga_page_region = lambda _img: (0, 0, 800, 1000)
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(100, [{"text": "S : / S -- ???", "x": 10, "y": 12, "w": 40, "h": 16}])
    )
    worker.has_any_multimodal_ai = lambda: True
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    provider = SimpleNamespace(
        transcribe_screenshot=Mock(
            return_value=SimpleNamespace(text="何を言うんだ！\n君は私の呪いも解いてくれた")
        )
    )
    worker._get_translation_provider = lambda name: provider if name == "local_multimodal" else None
    worker.build_screenshot_text_hint = Mock(return_value="何を言うんだ")
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "abc"}}])
    worker.translate_items_with_ai_and_providers = Mock(
        return_value=(["你說什麼！你不是也替我解除了詛咒嗎！"], ["local_multimodal"])
    )
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        provider.transcribe_screenshot.assert_called_once()
        assert finished == [[["你說什麼！你不是也替我解除了詛咒嗎！", 7, 11, 800, 1000]]]
    finally:
        worker.cleanup()


def test_deadline_executor_barrier_is_evaluator_opt_in(monkeypatch, qtbot):
    shutdown_calls = []

    class FakeFuture:
        def result(self):
            return None

    class FakeExecutor:
        def __init__(self, max_workers):
            self.futures = []

        def submit(self, callback, task):
            future = FakeFuture()
            self.futures.append(future)
            return future

        def shutdown(self, **kwargs):
            shutdown_calls.append(kwargs)

    monkeypatch.setattr(workers_module, "ThreadPoolExecutor", FakeExecutor)
    monkeypatch.setattr(
        workers_module,
        "wait",
        lambda futures, timeout=None: (set(), set(futures)),
    )
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker._recognize_with_backends = lambda _image: None
    worker.extract_raw_items = lambda *_args: []
    worker.remap_items_from_orientation = lambda items, *_args: items
    worker.score_ocr_items = lambda items: (0, list(items))
    try:
        worker.drain_deadline_futures = False
        worker.run_ocr_with_best_threshold(
            image,
            0,
            0,
            ocr_regions=[(0, 0, 80, 80)],
            candidate_thresholds=[100],
            orientation_candidates=[0, 90],
            deadline=1e100,
        )
        assert shutdown_calls[-1] == {"wait": False, "cancel_futures": True}

        worker.drain_deadline_futures = True
        worker.run_ocr_with_best_threshold(
            image,
            0,
            0,
            ocr_regions=[(0, 0, 80, 80)],
            candidate_thresholds=[100],
            orientation_candidates=[0, 90],
            deadline=1e100,
        )
        assert shutdown_calls[-1] == {"wait": True, "cancel_futures": True}
    finally:
        worker.cleanup()


def test_screenshot_hint_filter_keeps_question_text_and_drops_known_status_markers(qtbot):
    worker = OCRWorker()
    worker.convert_to_trad = lambda text: text
    box = SimpleNamespace(x=1, y=2, w=30, h=12)
    ocr_result = SimpleNamespace(
        lines=[
            SimpleNamespace(text="這是問題??", confidence=0.9, box=box),
            SimpleNamespace(text="Gemma OCR v3.0 5s", confidence=0.9, box=box),
        ]
    )

    try:
        items = worker._collect_screenshot_hint_items(ocr_result)

        assert [item["text"] for item in items] == ["這是問題??"]
    finally:
        worker.cleanup()


@pytest.mark.parametrize(
    ("future_error", "expected_warning"),
    [
        (FutureTimeoutError(), "[Google OCR prefetch] timeout"),
        (RuntimeError("private future failure"), "[Google OCR prefetch] failed type=%s"),
    ],
)
def test_google_ocr_prefetch_has_bounded_wait_and_executor_cleanup(
    monkeypatch, qtbot, future_error, expected_warning
):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.google_ocr_enabled = True
    worker.google_api_key = "test-key"
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "abc"}}])
    provider = SimpleNamespace(
        transcribe_screenshot=Mock(return_value=SimpleNamespace(text="Google OCR"))
    )
    worker._get_translation_provider = lambda name: provider if name == "gemma" else None
    result_timeouts = []
    shutdown_calls = []
    warning_messages = []

    class FakeFuture:
        def result(self, timeout=None):
            result_timeouts.append(timeout)
            raise future_error

        def add_done_callback(self, callback):
            callback(self)

        def cancel(self):
            return True

    class FakeExecutor:
        def __init__(self, max_workers):
            self.future = FakeFuture()

        def submit(self, callback):
            return self.future

        def shutdown(self, **kwargs):
            shutdown_calls.append(kwargs)

    monkeypatch.setattr(workers_module, "ThreadPoolExecutor", FakeExecutor)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(workers_module.logger, "warning", lambda *args: warning_messages.append(args))

    try:
        worker.run_scan_once()

        assert result_timeouts == [30]
        assert shutdown_calls == [{"wait": False}]
        assert any(args[0] == expected_warning for args in warning_messages)
    finally:
        worker.cleanup()


def test_scan_trace_records_successful_stage_order_without_source_text(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        trace = worker.last_scan_trace
        assert [(event.stage, event.outcome) for event in trace.events] == [
            (ScanStage.CAPTURE, ScanOutcome.SUCCESS),
            (ScanStage.FRAME_CACHE, ScanOutcome.MISS),
            (ScanStage.OCR, ScanOutcome.SUCCESS),
            (ScanStage.TRANSLATION, ScanOutcome.SUCCESS),
            (ScanStage.RENDER_DISPATCH, ScanOutcome.SUCCESS),
        ]
        assert trace.events[2].item_count == 1
        assert trace.events[3].provider == "google"
        assert all(event.elapsed_ms >= 0 for event in trace.events)
        assert "Hello" not in repr(trace)
        assert "你好" not in repr(trace)
    finally:
        worker.cleanup()


def test_scan_trace_cache_hit_bypasses_downstream_stages(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        worker.run_scan_once()

        assert [(event.stage, event.outcome) for event in worker.last_scan_trace.events] == [
            (ScanStage.CAPTURE, ScanOutcome.SUCCESS),
            (ScanStage.FRAME_CACHE, ScanOutcome.HIT),
            (ScanStage.RENDER_DISPATCH, ScanOutcome.SUCCESS),
        ]
    finally:
        worker.cleanup()


def test_scan_trace_records_capture_failure_without_exception_message(monkeypatch, qtbot):
    worker = OCRWorker()
    worker.ocr_backends = [object()]
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_BUBBLE
    worker.capture_scan_area = Mock(
        side_effect=RuntimeError("OCR_SECRET api-key=do-not-record")
    )
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert [
            (event.stage, event.outcome)
            for event in worker.last_scan_trace.events
        ] == [
            (ScanStage.CAPTURE, ScanOutcome.FAILURE),
            (ScanStage.RENDER_DISPATCH, ScanOutcome.SUCCESS),
        ]
        event = worker.last_scan_trace.events[0]
        assert event.error_code is ScanErrorCode.CAPTURE_FAILED
        assert event.exception_token == "RuntimeError"
        assert "OCR_SECRET" not in repr(worker.last_scan_trace)
        assert "do-not-record" not in repr(worker.last_scan_trace)
    finally:
        worker.cleanup()


def test_scan_trace_distinguishes_no_text_from_ocr_failure(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, []))
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        ocr_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.OCR
        ]
        assert ocr_events[-1].outcome is ScanOutcome.NO_TEXT
        assert ocr_events[-1].error_code is ScanErrorCode.NONE
    finally:
        worker.cleanup()


def test_scan_trace_uses_actual_fallback_provider(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.has_ai_text_provider = lambda: True
    worker.get_current_ai_provider = lambda: "gemma"
    worker.translate_items_with_ai_and_providers = Mock(
        return_value=(["你好"], ["google"])
    )
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        event = next(
            item for item in worker.last_scan_trace.events
            if item.stage is ScanStage.TRANSLATION
        )
        assert event.outcome is ScanOutcome.FALLBACK
        assert event.provider == "google"
        assert event.fallback_reason == "translation_provider_fallback"
    finally:
        worker.cleanup()


def test_screenshot_scan_trace_skips_ocr_and_records_translation(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = []
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_SCREENSHOT
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.build_screenshot_text_hint = lambda _image: "hint"
    worker.build_ai_image_parts = lambda _image: [{"inline_data": {"data": "ignored"}}]
    worker.translate_screenshot_gemma = lambda _parts, _hint: "translated"
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert [(event.stage, event.outcome) for event in worker.last_scan_trace.events] == [
            (ScanStage.CAPTURE, ScanOutcome.SUCCESS),
            (ScanStage.FRAME_CACHE, ScanOutcome.MISS),
            (ScanStage.TRANSLATION, ScanOutcome.SUCCESS),
            (ScanStage.RENDER_DISPATCH, ScanOutcome.SUCCESS),
        ]
        assert worker.last_scan_trace.events[2].provider == "local_multimodal"
    finally:
        worker.cleanup()


def test_screenshot_scan_trace_records_text_fallback_actual_provider(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = []
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_SCREENSHOT
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.build_screenshot_text_hint = lambda _image: "hint"
    worker.build_ai_image_parts = lambda _image: [{"inline_data": {"data": "ignored"}}]
    worker.translate_screenshot_gemma = Mock(side_effect=RuntimeError("private failure"))
    debug_messages = []
    worker.log_ai_debug = debug_messages.append
    worker.translate_text_preferred_with_provider = Mock(
        return_value=("translated", "google")
    )
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        event = next(
            item for item in worker.last_scan_trace.events
            if item.stage is ScanStage.TRANSLATION
        )
        assert event.outcome is ScanOutcome.FALLBACK
        assert event.provider == "google"
        assert event.fallback_reason == "translation_provider_fallback"
        assert "private failure" not in repr(worker.last_scan_trace)
        assert "private failure" not in "\n".join(debug_messages)
        assert debug_messages == ["MULTIMODAL FAILED: RuntimeError"]
    finally:
        worker.cleanup()


def test_multimodal_request_cancellation_does_not_text_fallback(qtbot):
    worker = OCRWorker()
    worker.has_any_multimodal_ai = lambda: True
    worker.translate_multimodal_gemma = Mock(
        side_effect=LocalRequestCancelled("local_request_scheduler_closed")
    )
    worker.translate_items_in_batches_with_providers = Mock(
        return_value=(["錯誤文字 fallback"], ["google"])
    )

    try:
        with pytest.raises(LocalRequestCancelled):
            worker.translate_items_with_ai_and_providers(
                ["原文"],
                [{"inline_data": {"data": "vision"}}],
                [{"text": "原文", "x": 0, "y": 0, "w": 20, "h": 20}],
            )

        worker.translate_items_in_batches_with_providers.assert_not_called()
    finally:
        worker.cleanup()

def test_screenshot_request_cancellation_does_not_text_fallback(qtbot):
    worker = OCRWorker()
    provider = SimpleNamespace(
        translate_screenshot=Mock(
            side_effect=LocalRequestCancelled("local_request_scheduler_closed")
        )
    )
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker._get_translation_provider = lambda _name: provider
    worker.translate_text_preferred_with_provider = Mock(
        return_value=("錯誤文字 fallback", "google")
    )

    try:
        with pytest.raises(LocalRequestCancelled):
            worker.translate_screenshot_gemma(
                [{"inline_data": {"data": "vision"}}],
                source_text_hint="原文",
            )

        worker.translate_text_preferred_with_provider.assert_not_called()
    finally:
        worker.cleanup()

def test_scan_trace_marks_partial_source_fallback(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.run_ocr_with_best_threshold = Mock(return_value=(
        100,
        [
            {"text": "One", "x": 10, "y": 12, "w": 40, "h": 16},
            {"text": "Two", "x": 10, "y": 32, "w": 40, "h": 16},
        ],
    ))
    worker.translate_items_with_ai_and_providers = Mock(
        return_value=(["一", None], ["google", None])
    )
    worker.translate_items_in_batches_with_providers = Mock(
        return_value=([None], [None])
    )
    worker.translate_text_preferred_with_provider = Mock(
        side_effect=RuntimeError("private fallback failure")
    )
    worker.get_best_known_translation = Mock(return_value=("", ""))
    warning_messages = []
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(workers_module.logger, "warning", lambda *args: warning_messages.append(args))

    try:
        worker.run_scan_once()

        event = next(
            item for item in worker.last_scan_trace.events
            if item.stage is ScanStage.TRANSLATION
        )
        assert event.outcome is ScanOutcome.FALLBACK
        assert event.provider == "google"
        assert event.fallback_reason == "translation_source_fallback"
        worker.translate_text_preferred_with_provider.assert_called_once_with("Two")
        assert any(
            args[0] == "[Translation fallback] failed index=%d type=%s; retaining source"
            and args[1:] == (1, "RuntimeError")
            for args in warning_messages
        )
    finally:
        worker.cleanup()


def test_text_only_screenshot_trace_does_not_mislabel_gemma_as_fallback(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = []
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = REGION_RENDER_SCREENSHOT
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: False
    worker.has_ai_text_provider = lambda: True
    worker.get_current_ai_provider = lambda: "gemma"
    worker.build_screenshot_text_hint = lambda _image: "hint"
    worker.translate_text_preferred_with_provider = Mock(
        return_value=("translated", "gemma")
    )
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        event = next(
            item for item in worker.last_scan_trace.events
            if item.stage is ScanStage.TRANSLATION
        )
        assert event.outcome is ScanOutcome.SUCCESS
        assert event.provider == "gemma"
        assert event.fallback_reason == ""
    finally:
        worker.cleanup()


def test_stale_queued_scan_is_cancelled_before_capture(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.capture_scan_area = Mock(return_value=(image, 7, 11))
    worker.set_scan_generation(2)
    worker.enqueue_scan_request(1)
    finished = []
    tokenized = []
    worker.finished.connect(finished.append)
    worker.scan_finished.connect(lambda generation, results: tokenized.append((generation, results)))
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        worker.capture_scan_area.assert_not_called()
        assert finished == []
        assert tokenized == []
        assert worker.last_scan_trace.events[-1].outcome is ScanOutcome.CANCELLED
        assert worker.last_scan_trace.events[-1].error_code is ScanErrorCode.SCAN_CANCELLED
    finally:
        worker.cleanup()


def test_inflight_generation_change_suppresses_result_and_cache(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.set_scan_generation(1)
    worker.enqueue_scan_request(1)

    def invalidate_during_translation(texts, _parts, _items):
        worker.set_scan_generation(2)
        return (["translated"] * len(texts), ["google"] * len(texts))

    worker.translate_items_with_ai_and_providers = Mock(
        side_effect=invalidate_during_translation
    )
    finished = []
    tokenized = []
    worker.finished.connect(finished.append)
    worker.scan_finished.connect(lambda generation, results: tokenized.append((generation, results)))
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == []
        assert tokenized == []
        assert len(worker.exact_image_cache) == 0
        assert worker.translation_cache == {}
        assert worker.last_scan_trace.events[-1].outcome is ScanOutcome.CANCELLED
    finally:
        worker.cleanup()


def test_current_generation_emits_legacy_and_tokenized_results(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.set_scan_generation(4)
    request = worker.enqueue_scan_request(4)
    finished = []
    tokenized = []
    worker.finished.connect(finished.append)
    worker.scan_finished.connect(lambda generation, results: tokenized.append((generation, results)))
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert request.generation == 4
        assert finished == [[["你好", 10, 12, 40, 16]]]
        assert tokenized == [(4, finished[0])]
    finally:
        worker.cleanup()


def test_same_generation_requests_remain_fifo_and_do_not_coalesce(monkeypatch, qtbot):
    first = np.zeros((40, 80, 3), dtype=np.uint8)
    second = first.copy()
    second[0, 0, 0] = 1
    images = iter([first, second])
    worker = OCRWorker()
    _configure_region_cache_worker(worker, first)
    worker.capture_scan_area = lambda: (next(images), 7, 11)
    worker.set_scan_generation(7)
    first_request = worker.enqueue_scan_request(7)
    second_request = worker.enqueue_scan_request(7)
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        worker.run_scan_once()

        assert first_request.request_id < second_request.request_id
        assert len(finished) == 2
        assert worker.run_ocr_with_best_threshold.call_count == 2
    finally:
        worker.cleanup()


def test_streaming_translation_returns_actual_fallback_provider():
    worker = OCRWorker()
    worker.has_any_multimodal_ai = lambda: False
    worker.has_ai_text_provider = lambda: True
    worker.get_current_ai_provider = lambda: "gemma"
    worker.translation_target_lang = "zh-TW"
    worker._get_translation_provider = lambda _name: SimpleNamespace(
        translate_stream=lambda _text: iter(["翻譯結果"]),
        last_stream_result=TranslationResult(
            text="翻譯結果",
            provider="google",
            requested_provider="local_gemma",
            fallback_reason="bad_translation",
        ),
    )
    merged_items = [{"x": 1, "y": 2, "w": 30, "h": 12}]

    try:
        translated, providers = worker.translate_items_with_ai_and_providers(
            ["source"], [], merged_items
        )
        assert translated == ["翻譯結果"]
        assert providers == ["google"]
    finally:
        worker.cleanup()

def test_streaming_generation_change_suppresses_later_chunks_and_final_result(
    monkeypatch, qtbot
):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.set_scan_generation(1)
    worker.enqueue_scan_request(1)
    worker.has_ai_text_provider = lambda: True
    worker.get_current_ai_provider = lambda: "gemma"
    worker.translate_items_with_ai_and_providers = (
        OCRWorker.translate_items_with_ai_and_providers.__get__(worker, OCRWorker)
    )

    def stream(_text):
        yield "first"
        worker.set_scan_generation(2)
        yield "stale"

    worker._get_translation_provider = lambda _name: SimpleNamespace(
        translate_stream=stream
    )
    legacy_chunks = []
    tokenized_chunks = []
    finished = []
    worker.translation_stream_update.connect(
        lambda *args: legacy_chunks.append(args)
    )
    worker.scan_translation_stream_update.connect(
        lambda *args: tokenized_chunks.append(args)
    )
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert len(legacy_chunks) == 1
        assert len(tokenized_chunks) == 1
        assert tokenized_chunks[0][0] == 1
        assert "stale" not in tokenized_chunks[0]
        assert finished == []
        assert worker.last_scan_trace.events[-1].outcome is ScanOutcome.CANCELLED
    finally:
        worker.cleanup()


def test_scan_status_emits_legacy_and_generation_tagged_signals(qtbot):
    worker = OCRWorker()
    worker.set_scan_generation(6)
    worker.enqueue_scan_request(6)
    worker._active_scan_request = worker._take_scan_request()
    legacy = []
    tokenized = []
    worker.status_msg.connect(legacy.append)
    worker.scan_status_msg.connect(
        lambda generation, message: tokenized.append((generation, message))
    )

    try:
        worker._emit_scan_status("scan_test_status")

        assert legacy == ["scan_test_status"]
        assert tokenized == [(6, "scan_test_status")]
    finally:
        worker.cleanup()

def test_stale_scan_status_is_suppressed_for_both_signal_shapes(qtbot):
    worker = OCRWorker()
    worker.set_scan_generation(1)
    worker.enqueue_scan_request(1)
    worker._active_scan_request = worker._take_scan_request()
    legacy = []
    tokenized = []
    worker.status_msg.connect(legacy.append)
    worker.scan_status_msg.connect(
        lambda generation, message: tokenized.append((generation, message))
    )

    try:
        worker.set_scan_generation(2)
        assert worker._emit_scan_status("stale_status") is False

        assert legacy == []
        assert tokenized == []
    finally:
        worker.cleanup()


def test_stale_fullscreen_retry_stops_before_later_ocr_phases_and_translation(
    monkeypatch, qtbot
):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.detect_manga_page_region = lambda _image: None
    worker.get_ocr_regions = Mock(
        return_value=[(0, 0, 80, 80), (80, 0, 80, 80)]
    )
    item = {"text": "Hello", "x": 10, "y": 12, "w": 40, "h": 16}
    calls = 0

    def ocr_then_invalidate(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            worker.set_scan_generation(2)
        return 100, [item]

    worker.run_ocr_with_best_threshold = Mock(side_effect=ocr_then_invalidate)
    worker.try_manga_grid_recovery = Mock()
    worker.refine_manga_ocr_items = Mock()
    worker.rescue_unreliable_manga_items = Mock()
    worker.translate_items_with_ai_and_providers = Mock()
    worker.set_scan_generation(1)
    worker.enqueue_scan_request(1)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert worker.run_ocr_with_best_threshold.call_count == 2
        worker.try_manga_grid_recovery.assert_not_called()
        worker.refine_manga_ocr_items.assert_not_called()
        worker.rescue_unreliable_manga_items.assert_not_called()
        worker.translate_items_with_ai_and_providers.assert_not_called()
        assert worker.last_scan_trace.events[-1].outcome is ScanOutcome.CANCELLED
    finally:
        worker.cleanup()


def test_exact_cache_hit_refreshes_frame_gate_consecutive_baseline(monkeypatch, qtbot):
    first = np.zeros((40, 80, 3), dtype=np.uint8)
    different = np.full((40, 80, 3), 255, dtype=np.uint8)
    first_again = first.copy()
    near_first = first.copy()
    near_first[0, 0, 0] = 1
    images = iter([first, different, first_again, near_first])
    worker = OCRWorker()
    _configure_region_cache_worker(worker, first)
    worker.capture_scan_area = lambda: (next(images), 7, 11)
    worker.translate_items_with_ai_and_providers = Mock(
        return_value=(["Nihao"], ["google"])
    )
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        for _ in range(4):
            worker.run_scan_once()

        assert worker.last_combined_text == "Hello"
        assert worker.last_results == [("Nihao", 10, 12, 40, 16)]
        assert worker.run_ocr_with_best_threshold.call_count == 3
        shadow_event = next(
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.FRAME_CACHE
        )
        assert shadow_event.detail == "frame_cache_shadow_near"
    finally:
        worker.cleanup()


def _configure_region_vision_worker(worker, image, render_mode, provider):
    worker.ocr_backends = [object()]
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_REGION
    worker.region_render_mode = render_mode
    worker.scan_region = (20, 10, 80, 40)
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker._get_translation_provider = lambda name: provider if name == "local_multimodal" else None
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "vision"}}])
    worker.trigger_background_threshold_refresh = lambda *args, **kwargs: None


def test_region_vision_skips_provider_when_generation_changes_before_request(
    monkeypatch, qtbot
):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(
        interpret_regions=Mock(return_value=[
            SimpleNamespace(id=0, source_text="不應送出", translation="不應送出")
        ])
    )
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_BUBBLE, provider)
    worker.set_scan_generation(1)
    worker.enqueue_scan_request(1)
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, [
        {"text": "hint", "x": 17, "y": 21, "w": 40, "h": 16}
    ]))

    def invalidate_after_provider_resolution():
        worker.set_scan_generation(2)
        return "local_multimodal"

    worker.resolve_multimodal_provider_name = invalidate_after_provider_resolution
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        provider.interpret_regions.assert_not_called()
        assert worker.last_scan_trace.events[-1].outcome is ScanOutcome.CANCELLED
        assert worker.last_scan_trace.events[-1].error_code is ScanErrorCode.SCAN_CANCELLED
    finally:
        worker.cleanup()


def test_cleanup_cancels_shutdown_queued_vision_without_fallback(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(close=Mock())
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_BUBBLE, provider)
    worker.local_multimodal_provider = provider
    worker.build_local_vision_image_parts = Mock(
        return_value=[{"inline_data": {"data": "vision"}}]
    )
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, [
        {"text": "shutdown", "x": 17, "y": 21, "w": 40, "h": 16}
    ]))
    worker.set_scan_generation(1)
    worker.enqueue_scan_request(1)

    def cancel_during_request(*_args, **_kwargs):
        worker.cleanup()
        raise LocalRequestCancelled("local_request_scheduler_closed")

    provider.interpret_regions = Mock(side_effect=cancel_during_request)
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == []
        assert provider.interpret_regions.call_count == 1
        assert any(
            event.outcome is ScanOutcome.CANCELLED
            and event.error_code is ScanErrorCode.SCAN_CANCELLED
            for event in worker.last_scan_trace.events
        )
        assert not any(
            event.detail == "translation_region_vision_failed"
            for event in worker.last_scan_trace.events
        )
    finally:
        worker.cleanup()

@pytest.mark.parametrize("render_mode", [REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF])
def test_region_vision_uses_image_source_and_relative_ocr_hints(monkeypatch, qtbot, render_mode):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(interpret_regions=Mock(return_value=[
        SimpleNamespace(id=0, source_text="正確原文", translation="正確翻譯")
    ]))
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, render_mode, provider)
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, [
        {"text": "WRONG OCR", "x": 17, "y": 21, "w": 40, "h": 16}
    ]))
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[["正確翻譯", 17, 21, 40, 16]]]
        assert worker.last_combined_text == "正確原文"
        assert worker.last_provider == "local_multimodal"
        assert worker.build_ai_image_parts.call_count == 1
        hints = provider.interpret_regions.call_args.args[1]
        assert hints == [{"id": 0, "x": 10, "y": 10, "w": 40, "h": 16, "text": "WRONG OCR"}]
        assert worker.last_results == [("正確翻譯", 17, 21, 40, 16)]
        translation_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.TRANSLATION
        ]
        assert translation_events[-1].detail == "translation_region_vision_completed"
    finally:
        worker.cleanup()


def test_region_vision_attributes_model_time_to_translation_stage(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    clock = {"value": 0.0}

    def fake_perf_counter():
        clock["value"] += 0.001
        return clock["value"]

    def delayed_interpret_regions(*_args, **_kwargs):
        clock["value"] += 1.0
        return [SimpleNamespace(id=0, source_text="正確原文", translation="正確翻譯")]

    provider = SimpleNamespace(interpret_regions=delayed_interpret_regions)
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_BUBBLE, provider)
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, []))
    monkeypatch.setattr(workers_module.time, "perf_counter", fake_perf_counter)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        ocr_event = next(
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.OCR and event.detail == "ocr_optional_unavailable"
        )
        translation_event = next(
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.TRANSLATION
            and event.detail == "translation_region_vision_completed"
        )
        assert ocr_event.elapsed_ms < translation_event.elapsed_ms
    finally:
        worker.cleanup()


def test_region_vision_without_ocr_backend_uses_whole_region_hint(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(interpret_regions=Mock(return_value=[
        SimpleNamespace(id=0, source_text="完整原文", translation="完整翻譯")
    ]))
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_BUBBLE, provider)
    worker.ocr_backends = []
    worker.run_ocr_with_best_threshold = Mock(side_effect=AssertionError("OCR must be optional"))
    worker.handle_empty = Mock(side_effect=AssertionError("must not handle_empty"))
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[["完整翻譯", 7, 11, 160, 80]]]
        worker.run_ocr_with_best_threshold.assert_not_called()
        assert provider.interpret_regions.call_args.args[1] == [
            {"id": 0, "x": 0, "y": 0, "w": 160, "h": 80, "text": ""}
        ]
        assert worker.build_ai_image_parts.call_count == 1
    finally:
        worker.cleanup()


def test_fullscreen_local_vision_first_success_skips_ocr(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker.local_multimodal_provider = SimpleNamespace(available=lambda: True)
    worker.build_local_vision_image_parts = Mock(
        return_value=[{"inline_data": {"data": "vision"}}]
    )
    worker.translate_screenshot_gemma = Mock(return_value="整頁 Vision 翻譯")
    worker.run_ocr_with_best_threshold = Mock(
        side_effect=AssertionError("local fullscreen Vision-first must bypass OCR")
    )
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[['整頁 Vision 翻譯', 7, 11, 160, 80]]]
        worker.run_ocr_with_best_threshold.assert_not_called()
        worker.build_local_vision_image_parts.assert_called_once_with(image, [])
        worker.translate_screenshot_gemma.assert_called_once_with(
            [{"inline_data": {"data": "vision"}}], ""
        )
        translation_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.TRANSLATION
        ]
        assert translation_events[-1].detail == "translation_fullscreen_vision_completed"
    finally:
        worker.cleanup()


def test_fullscreen_local_vision_first_uses_vision_ocr_rescue_when_translation_is_empty(
    monkeypatch, qtbot
):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(
        available=lambda: True,
        transcribe_screenshot=Mock(
            return_value=TranslationResult(
                text="守りに特化で",
                provider="local_multimodal",
                model="gemma-3-4b-it",
            )
        ),
        translate=Mock(
            return_value=TranslationResult(
                text="專精於防守",
                provider="local_multimodal",
                model="gemma-3-4b-it",
            )
        ),
    )
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker.local_multimodal_provider = provider
    worker._get_translation_provider = lambda name: provider if name == "local_multimodal" else None
    worker.build_local_vision_image_parts = Mock(
        return_value=[{"inline_data": {"data": "vision"}}]
    )
    worker.translate_screenshot_gemma = Mock(
        side_effect=ValueError("empty_local_multimodal_screenshot_response")
    )
    worker.run_ocr_with_best_threshold = Mock(
        side_effect=AssertionError("Vision OCR rescue must not use Windows OCR")
    )
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[['專精於防守', 7, 11, 160, 80]]]
        provider.transcribe_screenshot.assert_called_once_with(
            [{"inline_data": {"data": "vision"}}]
        )
        provider.translate.assert_called_once_with(
            "守りに特化で",
            target_lang=worker.translation_target_lang,
        )
        worker.run_ocr_with_best_threshold.assert_not_called()
        translation_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.TRANSLATION
        ]
        assert translation_events[-1].detail == (
            "translation_fullscreen_vision_ocr_rescue_completed"
        )
    finally:
        worker.cleanup()


def test_fullscreen_local_vision_first_failure_falls_open_to_ocr(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker.local_multimodal_provider = SimpleNamespace(available=lambda: True)
    worker.build_local_vision_image_parts = Mock(
        return_value=[{"inline_data": {"data": "vision"}}]
    )
    worker.translate_screenshot_gemma = Mock(side_effect=RuntimeError("vision failed"))
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(100, [{"text": "OCR text", "x": 10, "y": 12, "w": 40, "h": 16}])
    )
    worker.translate_items_with_ai_and_providers = Mock(
        return_value=(["OCR fallback"], ["local_multimodal"])
    )
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[['OCR fallback', 10, 12, 40, 16]]]
        assert worker.translate_screenshot_gemma.call_count == 1
        assert worker.run_ocr_with_best_threshold.call_count == 1
        translation_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.TRANSLATION
        ]
        assert translation_events[0].outcome is ScanOutcome.FALLBACK
        assert translation_events[0].fallback_reason == "translation_fullscreen_vision_local_failed"
    finally:
        worker.cleanup()


def test_fullscreen_local_vision_first_stale_response_does_not_write_state_or_cache(
    monkeypatch, qtbot
):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker.local_multimodal_provider = SimpleNamespace(available=lambda: True)
    worker.build_local_vision_image_parts = Mock(
        return_value=[{"inline_data": {"data": "vision"}}]
    )

    def return_stale_result(*_args, **_kwargs):
        worker.set_scan_generation(2)
        return "過期 Vision 結果"

    worker.translate_screenshot_gemma = Mock(side_effect=return_stale_result)
    worker.set_scan_generation(1)
    worker.enqueue_scan_request(1)
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == []
        assert worker.last_results == []
        assert len(worker.exact_image_cache) == 0
        assert worker.last_scan_trace.events[-1].outcome is ScanOutcome.CANCELLED
        assert worker.last_scan_trace.events[-1].error_code is ScanErrorCode.SCAN_CANCELLED
    finally:
        worker.cleanup()


def test_fullscreen_remote_provider_keeps_ocr_first(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_text_worker(worker, image)
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.has_any_multimodal_ai = lambda: True
    worker.get_current_ai_provider = lambda: "gemma"
    worker.resolve_multimodal_provider_name = lambda: "gemma"
    worker.local_multimodal_provider = SimpleNamespace(available=lambda: True)
    worker.translate_screenshot_gemma = Mock(
        side_effect=AssertionError("remote fullscreen provider must remain OCR-first")
    )
    worker.run_ocr_with_best_threshold = Mock(
        return_value=(100, [{"text": "OCR text", "x": 10, "y": 12, "w": 40, "h": 16}])
    )
    worker.translate_items_with_ai_and_providers = Mock(
        return_value=(["OCR translation"], ["gemma"])
    )
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[['OCR translation', 10, 12, 40, 16]]]
        worker.translate_screenshot_gemma.assert_not_called()
        worker.run_ocr_with_best_threshold.assert_called_once()
    finally:
        worker.cleanup()


def test_fullscreen_vision_fallback_survives_missing_ocr(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = []
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.region_render_mode = REGION_RENDER_BUBBLE
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "vision"}}])
    worker.build_local_vision_image_parts = worker.build_ai_image_parts
    worker.translate_screenshot_gemma = Mock(return_value="整頁 Vision 翻譯")
    worker.run_ocr_with_best_threshold = Mock(
        side_effect=AssertionError("OCR must remain optional for Vision fallback")
    )
    worker.handle_empty = Mock(side_effect=AssertionError("Vision result must not be empty"))
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[['整頁 Vision 翻譯', 7, 11, 160, 80]]]
        worker.run_ocr_with_best_threshold.assert_not_called()
        worker.translate_screenshot_gemma.assert_called_once_with(
            [{"inline_data": {"data": "vision"}}], ""
        )
        assert worker.last_provider == "local_multimodal"
        translation_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.TRANSLATION
        ]
        assert translation_events[-1].detail == "translation_fullscreen_vision_completed"
    finally:
        worker.cleanup()

def test_fullscreen_vision_fallback_survives_ocr_failure(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    worker = OCRWorker()
    worker.ocr_backends = [object()]
    worker.google_ocr_enabled = False
    worker.auto_threshold_enabled = False
    worker.scan_mode = SCAN_MODE_FULLSCREEN
    worker.region_render_mode = REGION_RENDER_BUBBLE
    worker.capture_scan_area = lambda: (image, 7, 11)
    worker.has_any_multimodal_ai = lambda: True
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.build_ai_image_parts = Mock(return_value=[{"inline_data": {"data": "vision"}}])
    worker.build_local_vision_image_parts = worker.build_ai_image_parts
    worker.translate_screenshot_gemma = Mock(return_value="OCR 失敗後的 Vision 翻譯")
    worker.run_ocr_with_best_threshold = Mock(
        side_effect=RuntimeError("backend unavailable")
    )
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[['OCR 失敗後的 Vision 翻譯', 7, 11, 160, 80]]]
        assert worker.run_ocr_with_best_threshold.call_count == 2
        assert worker.translate_screenshot_gemma.call_count == 1
        ocr_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.OCR
        ]
        assert ocr_events[0].detail == "ocr_optional_failed"
        assert worker.last_provider == "local_multimodal"
    finally:
        worker.cleanup()

def test_region_vision_exception_falls_open_to_ocr_translation(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(interpret_regions=Mock(side_effect=RuntimeError("private output")))
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_BUBBLE, provider)
    item = {"text": "OCR fallback", "x": 17, "y": 21, "w": 40, "h": 16}
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, [item]))
    worker.translate_items_with_ai_and_providers = Mock(return_value=(["OCR 翻譯"], ["google"]))
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[["OCR 翻譯", 17, 21, 40, 16]]]
        assert worker.build_ai_image_parts.call_count == 1
        assert worker.last_provider == "google"
        translation_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.TRANSLATION
        ]
        assert translation_events[-1].outcome is ScanOutcome.FALLBACK
        assert (
            translation_events[-1].fallback_reason
            == "translation_region_vision_failed"
        )
    finally:
        worker.cleanup()


def test_region_vision_exception_without_ocr_safely_emits_empty(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(interpret_regions=Mock(side_effect=RuntimeError("secret prompt/raw output")))
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_RELIEF, provider)
    worker.ocr_backends = []
    worker.run_ocr_with_best_threshold = Mock(side_effect=AssertionError("OCR must be optional"))
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[]]
        worker.run_ocr_with_best_threshold.assert_not_called()
        assert worker.last_results == []
        failure = next(
            event for event in worker.last_scan_trace.events
            if event.detail == "translation_region_vision_failed"
        )
        assert failure.exception_token == "RuntimeError"
        assert failure.fallback_reason == "translation_region_vision_provider_error"
        assert "secret" not in failure.detail
    finally:
        worker.cleanup()


def test_region_vision_failure_trace_keeps_safe_response_reason(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(
        interpret_regions=Mock(side_effect=ValueError("empty_region_vision_response"))
    )
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_RELIEF, provider)
    worker.ocr_backends = []
    worker.run_ocr_with_best_threshold = Mock(side_effect=AssertionError("OCR must be optional"))
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        failure = next(
            event for event in worker.last_scan_trace.events
            if event.detail == "translation_region_vision_failed"
        )
        assert failure.fallback_reason == "translation_region_vision_response_empty"
        assert failure.exception_token == "ValueError"
    finally:
        worker.cleanup()


def test_region_vision_takes_over_when_ocr_backend_raises(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(interpret_regions=Mock(return_value=[
        SimpleNamespace(id=0, source_text="Vision 原文", translation="Vision 翻譯")
    ]))
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_BUBBLE, provider)
    worker.run_ocr_with_best_threshold = Mock(side_effect=RuntimeError("ocr backend failure"))
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert finished == [[["Vision 翻譯", 7, 11, 160, 80]]]
        assert provider.interpret_regions.call_args.args[1] == [
            {"id": 0, "x": 0, "y": 0, "w": 160, "h": 80, "text": ""}
        ]
        assert worker.build_ai_image_parts.call_count == 1
        assert worker.last_combined_text == "Vision 原文"
    finally:
        worker.cleanup()

def test_region_vision_partial_response_falls_back_without_dropping_items(monkeypatch, qtbot):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    provider = SimpleNamespace(interpret_regions=Mock(return_value=[
        SimpleNamespace(id=0, source_text="Vision 原文", translation="Vision 翻譯")
    ]))
    worker = OCRWorker()
    _configure_region_vision_worker(worker, image, REGION_RENDER_BUBBLE, provider)
    items = [
        {"text": "OCR one", "x": 17, "y": 21, "w": 40, "h": 16},
        {"text": "OCR two", "x": 60, "y": 45, "w": 50, "h": 18},
    ]
    worker.run_ocr_with_best_threshold = Mock(return_value=(100, items))
    worker.translate_items_with_ai_and_providers = Mock(
        return_value=(["Fallback one", "Fallback two"], ["google", "google"])
    )
    finished = []
    worker.finished.connect(finished.append)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()
        fallback_args = worker.translate_items_with_ai_and_providers.call_args.args
        assert fallback_args[0] == ["OCR one", "OCR two"]

        assert finished == [[
            ["Fallback one", 17, 21, 40, 16],
            ["Fallback two", 60, 45, 50, 18],
        ]]
        assert worker.last_provider == "google"
        translation_events = [
            event for event in worker.last_scan_trace.events
            if event.stage is ScanStage.TRANSLATION
        ]
        assert translation_events[-1].outcome is ScanOutcome.FALLBACK
        assert translation_events[-1].fallback_reason == "translation_region_vision_failed"
    finally:
        worker.cleanup()

def test_fast_path_hit_does_not_request_hybrid_rescue(monkeypatch, qtbot):
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    worker.run_ocr_with_best_threshold = Mock(return_value=(
        100,
        [{"text": "One", "x": 10, "y": 12, "w": 40, "h": 16}],
    ))
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert worker.run_ocr_with_best_threshold.call_count == 1
        assert all(
            "preprocess_candidates" not in call.kwargs
            for call in worker.run_ocr_with_best_threshold.call_args_list
        )
    finally:
        worker.cleanup()


def test_no_text_uses_bounded_hybrid_rescue(monkeypatch, qtbot):
    from ocr_preprocess import BOUNDED_RESCUE_PREPROCESSES

    image = np.zeros((40, 80, 3), dtype=np.uint8)
    worker = OCRWorker()
    _configure_region_cache_worker(worker, image)
    recovered_item = {"text": "Recovered", "x": 10, "y": 12, "w": 40, "h": 16}
    worker.run_ocr_with_best_threshold = Mock(side_effect=[
        (100, []),
        (100, []),
        (100, [recovered_item]),
    ])
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    try:
        worker.run_scan_once()

        assert worker.last_combined_text == "Recovered"
        assert worker.last_results == [("你好", 10, 12, 40, 16)]
        assert worker.run_ocr_with_best_threshold.call_count == 3
        rescue_call = worker.run_ocr_with_best_threshold.call_args_list[-1]
        assert rescue_call.kwargs["preprocess_candidates"] == BOUNDED_RESCUE_PREPROCESSES
        assert len(BOUNDED_RESCUE_PREPROCESSES) == 2
    finally:
        worker.cleanup()


def test_hybrid_rescue_preprocess_registry_is_strict_and_bounded():
    from ocr_preprocess import (
        BOUNDED_RESCUE_PREPROCESSES,
        normalize_preprocess_candidates,
    )

    assert normalize_preprocess_candidates(BOUNDED_RESCUE_PREPROCESSES) == (
        "adaptive_invert",
        "clahe_otsu_invert",
    )
    with pytest.raises(ValueError, match="unknown OCR preprocess"):
        normalize_preprocess_candidates(("not-a-real-preprocess",))


def test_ocr_hint_consensus_divergent_candidates_revoked():
    from ocr_quality import evaluate_ocr_hint_consensus

    variant_outputs = [
        {"name": "color_scaled", "is_primary": True, "score": 20, "items": [{"text": "鬼滅の刃", "confidence": 0.9}], "summary": "鬼滅の刃"},
        {"name": "gray_scaled", "is_primary": True, "score": 20, "items": [{"text": "海賊王", "confidence": 0.9}], "summary": "海賊王"},
        {"name": "clahe_gray", "is_primary": True, "score": 20, "items": [{"text": "七龍珠", "confidence": 0.9}], "summary": "七龍珠"},
    ]
    hint, items = evaluate_ocr_hint_consensus(variant_outputs)
    assert hint == ""
    assert items == []


def test_ocr_hint_consensus_short_japanese_passes():
    from ocr_quality import evaluate_ocr_hint_consensus

    variant_outputs = [
        {"name": "color_scaled", "is_primary": True, "score": 15, "items": [{"text": "なに", "confidence": 0.9}], "summary": "なに"},
        {"name": "gray_scaled", "is_primary": True, "score": 15, "items": [{"text": "なに", "confidence": 0.9}], "summary": "なに"},
        {"name": "binary_invert", "is_primary": False, "score": 10, "items": [{"text": "噪訊", "confidence": 0.5}], "summary": "噪訊"},
    ]
    hint, items = evaluate_ocr_hint_consensus(variant_outputs)
    assert hint == "なに"
    assert len(items) == 1
    assert items[0]["text"] == "なに"


def test_ocr_hint_consensus_destructive_variant_noise_cannot_pass_alone():
    from ocr_quality import evaluate_ocr_hint_consensus

    variant_outputs = [
        {"name": "color_scaled", "is_primary": True, "score": 5, "items": [{"text": "文", "confidence": 0.9}], "summary": "文"},
        {"name": "binary_invert", "is_primary": False, "score": 30, "items": [{"text": "噪訊邊緣文字ABC", "confidence": 0.9}], "summary": "噪訊邊緣文字ABC"},
        {"name": "adaptive_invert", "is_primary": False, "score": 30, "items": [{"text": "噪訊邊緣文字ABC", "confidence": 0.9}], "summary": "噪訊邊緣文字ABC"},
    ]
    hint, items = evaluate_ocr_hint_consensus(variant_outputs)
    assert hint == ""
    assert items == []


def test_build_screenshot_text_hint_uses_two_fast_consensus_variants():
    from cloudhime_workers import OCRWorker
    import numpy as np

    worker = OCRWorker()
    worker.ocr_backends = [object()]

    recognized_count = 0
    def mock_recognize(variant_img):
        nonlocal recognized_count
        recognized_count += 1
        if recognized_count in (1, 2):
            line = SimpleNamespace(
                text="共通文字標籤",
                confidence=0.9,
                box=SimpleNamespace(x=10, y=10, w=50, h=20),
            )
            return SimpleNamespace(lines=[line])
        line = SimpleNamespace(
            text="獨立文字",
            confidence=0.5,
            box=SimpleNamespace(x=10, y=10, w=50, h=20),
        )
        return SimpleNamespace(lines=[line])

    worker._recognize_with_backends = mock_recognize

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    hint = worker.build_screenshot_text_hint(img)

    assert recognized_count == 2
    assert hint == "共通文字標籤"
