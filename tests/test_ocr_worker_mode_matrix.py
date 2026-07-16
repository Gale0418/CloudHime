from unittest.mock import Mock

import numpy as np
import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QFont

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
