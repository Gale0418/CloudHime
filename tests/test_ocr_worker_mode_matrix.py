from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QFont

import cloudhime_workers as workers_module
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

        assert worker.build_screenshot_text_hint.call_count == 1
        assert worker.build_ai_image_parts.call_count == 1
        assert worker.translate_screenshot_gemma.call_count == 1
        assert finished[0] == [["Screenshot", 7, 11, 160, 80]]
        assert finished[1] == finished[0]
    finally:
        worker.cleanup()


def test_screenshot_cache_uses_threshold_after_hint_processing(monkeypatch, qtbot):
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

        assert worker.binary_threshold == 120
        assert worker.build_screenshot_text_hint.call_count == 1
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
