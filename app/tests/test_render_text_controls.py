from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QRect, Qt

from cloudhime_ui import (
    Controller,
    OverlayWindow,
    REGION_RENDER_BUBBLE,
    REGION_RENDER_RELIEF,
    REGION_RENDER_SCREENSHOT,
    SCAN_MODE_FULLSCREEN,
    SCAN_MODE_REGION,
)


REGION_RENDER_MODES = (
    REGION_RENDER_BUBBLE,
    REGION_RENDER_RELIEF,
    REGION_RENDER_SCREENSHOT,
)


def _overlay(qtbot, mode, *, offset_x=0, offset_y=0, font_pt=18):
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    overlay.setGeometry(0, 0, 1000, 700)
    overlay.set_render_context(
        SCAN_MODE_REGION,
        mode,
        relief_offset_x=offset_x,
        relief_offset_y=offset_y,
        relief_font_pt=font_pt,
        scan_region=(400, 260, 200, 120),
    )
    return overlay


@pytest.mark.parametrize("mode", REGION_RENDER_MODES)
@pytest.mark.parametrize("font_pt", [8, 32, 48])
def test_region_render_modes_apply_requested_text_size(qtbot, mode, font_pt):
    overlay = _overlay(qtbot, mode, font_pt=font_pt)
    overlay.update_bubbles([("可調整字級", 440, 300, 90, 32)])

    assert len(overlay.bubbles) == 1
    assert overlay.bubbles[0].font().pointSizeF() == pytest.approx(font_pt)


@pytest.mark.parametrize("mode", REGION_RENDER_MODES)
def test_region_render_modes_apply_offsets_and_clamp_to_overlay(qtbot, mode):
    source = [("字幕位置", 440, 300, 90, 32)]
    base_overlay = _overlay(qtbot, mode)
    base_overlay.update_bubbles(source)
    base = base_overlay.bubbles[0].geometry()

    moved_overlay = _overlay(qtbot, mode, offset_x=24, offset_y=-17)
    moved_overlay.update_bubbles(source)
    moved = moved_overlay.bubbles[0].geometry()

    assert (moved.x() - base.x(), moved.y() - base.y()) == (24, -17)
    assert moved.left() >= 0
    assert moved.top() >= 0
    assert moved.right() < moved_overlay.width()
    assert moved.bottom() < moved_overlay.height()


def test_screenshot_zero_offset_covers_selection_before_user_offset(qtbot):
    source = [("截圖翻譯內容", 440, 300, 90, 32)]
    base_overlay = _overlay(qtbot, REGION_RENDER_SCREENSHOT)
    base_overlay.update_bubbles(source)
    base = base_overlay.bubbles[0].geometry()

    moved_overlay = _overlay(
        qtbot, REGION_RENDER_SCREENSHOT, offset_x=18, offset_y=12
    )
    moved_overlay.update_bubbles(source)
    moved = moved_overlay.bubbles[0].geometry()

    assert base == QRect(*base_overlay.scan_region)
    assert (moved.x() - base.x(), moved.y() - base.y()) == (18, 12)


@pytest.mark.parametrize("region", [(0, 0, 200, 120), (800, 580, 200, 120), (80, 34, 260, 414)])
def test_screenshot_zero_offset_uses_whole_selection_at_screen_edges(qtbot, region):
    overlay = _overlay(qtbot, REGION_RENDER_SCREENSHOT)
    overlay.scan_region = region
    # A child OCR box must not replace the whole selection as the anchor.
    overlay.update_bubbles([("譯文", region[0] + 20, region[1] + 30, 80, 30)])
    assert overlay.bubbles[0].geometry() == QRect(*region)


def test_screenshot_growing_stream_stays_anchored_and_matches_final(qtbot):
    overlay = _overlay(qtbot, REGION_RENDER_SCREENSHOT, offset_x=-18, offset_y=12)
    text = "A longer translated paragraph with many words. " * 12
    for partial in ("Hello", text[:60], text):
        overlay.update_translation_stream(0, partial, "test", 440, 300, 90, 32)
    streamed = overlay.bubbles[0].geometry()
    font_size = overlay.bubbles[0].font().pointSizeF()
    overlay.update_bubbles([(text, 440, 300, 90, 32)])
    bubble = overlay.bubbles[0]
    assert bubble.geometry() == streamed
    assert bubble.font().pointSizeF() == font_size
    assert bubble.measure_text_height(text, bubble.width(), font_size) <= bubble.height() - bubble.text_padding * 2


@pytest.mark.parametrize("mode", REGION_RENDER_MODES)
@pytest.mark.parametrize("offset", [-1000, 1000])
def test_maximum_offsets_keep_caption_within_overlay(qtbot, mode, offset):
    overlay = _overlay(qtbot, mode, offset_x=offset, offset_y=offset, font_pt=32)
    overlay.update_bubbles([("Edge caption", 440, 300, 90, 32)])
    assert overlay.rect().contains(overlay.bubbles[0].geometry())


@pytest.mark.parametrize("mode", [REGION_RENDER_BUBBLE, REGION_RENDER_SCREENSHOT])
def test_long_caption_expands_or_fits_instead_of_clipping_at_requested_size(qtbot, mode):
    overlay = _overlay(qtbot, mode, font_pt=48)
    text = "A longer translated paragraph with many words. " * 12
    overlay.update_bubbles([(text, 440, 300, 90, 32)])
    bubble = overlay.bubbles[0]
    assert 8 <= bubble.font().pointSizeF() <= 48
    assert overlay.rect().contains(bubble.geometry())
    required = bubble.measure_text_height(text, bubble.width(), bubble.font().pointSizeF())
    assert required <= bubble.height() - bubble.text_padding * 2


@pytest.mark.parametrize("mode", REGION_RENDER_MODES)
def test_streaming_and_final_render_use_same_font_and_position(qtbot, mode):
    overlay = _overlay(qtbot, mode, offset_x=15, offset_y=-9, font_pt=32)
    overlay.update_translation_stream(0, "同一段翻譯", "test", 440, 300, 90, 32)
    streamed = overlay.bubbles[0]
    stream_geometry = streamed.geometry()
    stream_font_size = streamed.font().pointSizeF()

    overlay.update_bubbles([("同一段翻譯", 440, 300, 90, 32)])
    final = overlay.bubbles[0]

    assert final.geometry() == stream_geometry
    assert final.font().pointSizeF() == pytest.approx(stream_font_size)
    assert stream_font_size == pytest.approx(32)


def test_fullscreen_render_context_keeps_bubble_fallback(qtbot):
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    overlay.setGeometry(0, 0, 1000, 700)
    overlay.set_render_context(
        SCAN_MODE_FULLSCREEN,
        REGION_RENDER_RELIEF,
        relief_offset_x=20,
        relief_offset_y=10,
        relief_font_pt=32,
    )
    overlay.update_bubbles([("全螢幕字幕", 440, 300, 90, 32)])

    bubble = overlay.bubbles[0]
    assert bubble.render_mode == REGION_RENDER_BUBBLE
    assert bubble.wordWrap()


def test_controller_setting_change_refreshes_visible_bubbles_and_payload(qtbot):
    overlay = _overlay(qtbot, REGION_RENDER_BUBBLE)
    results = [("既有字幕", 440, 300, 90, 32)]
    overlay.update_bubbles(results)

    worker = SimpleNamespace(
        gemma_model="model",
        gemma_prompt="",
        use_gemma_translation=False,
        auto_threshold_enabled=False,
        auto_threshold_refresh_minutes=10,
        gemma_auto_switch_enabled=False,
        ocr_backend_chain=[],
        binary_threshold=100,
    )
    controller = SimpleNamespace(
        overlay=overlay,
        worker=worker,
        scan_mode=SCAN_MODE_REGION,
        region_render_mode=REGION_RENDER_BUBBLE,
        region_relief_offset_x=0,
        region_relief_offset_y=0,
        region_relief_font_pt=18,
        region_frame_opacity=40,
        selected_region=(400, 260, 200, 120),
        last_scan_results=results,
        theme_mode="light",
        is_dark_mode=False,
        settings_window=None,
        region_frame=SimpleNamespace(
            set_theme_mode=lambda _mode: None,
            set_frame_opacity=lambda _opacity: None,
        ),
        gemma_prompt="",
        screenshot_gemma_prompt="",
        auto_threshold_refresh_minutes=10,
        google_ocr_enabled=False,
        random_scan_center_seconds=10,
        random_scan_jitter_percent=0,
        region_pass_through=False,
        get_ui_language=lambda: "zh-TW",
        schedule_save_settings=lambda: None,
        refresh_overlay_from_last_results=lambda: Controller.refresh_overlay_from_last_results(controller),
    )
    reference = _overlay(qtbot, REGION_RENDER_BUBBLE, font_pt=32)
    reference.update_bubbles(results)
    previous_geometry = reference.bubbles[0].geometry()

    Controller.on_region_relief_settings_changed(controller, 21, -13, 32, 55)

    bubble = overlay.bubbles[0]
    assert bubble.font().pointSizeF() == pytest.approx(32)
    assert (bubble.x() - previous_geometry.x(), bubble.y() - previous_geometry.y()) == (
        21,
        -13,
    )
    payload = Controller.get_settings_payload(controller)
    assert payload["region_relief_offset_x"] == 21
    assert payload["region_relief_offset_y"] == -13
    assert payload["region_relief_font_pt"] == 32


@pytest.mark.parametrize("mode", REGION_RENDER_MODES)
def test_revamp_common_text_controls_remain_enabled(qtbot, monkeypatch, mode):
    monkeypatch.setattr(
        "cloudhime_ui.GlobalHotKeyFilter.register_hotkey",
        lambda self, hwnd: None,
        raising=False,
    )
    monkeypatch.setattr(
        "cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey",
        lambda self, hwnd: None,
        raising=False,
    )
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda _paths: ({}, None))
    monkeypatch.setattr("cloudhime_ui.SecretStore.get", lambda self: "")
    monkeypatch.setattr("cloudhime_ui.SecretStore.legacy_sources_disabled", lambda self: True)
    monkeypatch.delenv("CLOUDHIME_GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda _self: True)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args: None)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    settings = None
    try:
        controller.region_render_mode = mode
        controller.toggle_settings_window()
        settings = controller.settings_window
        controller.set_ui_language("en", persist=False, refresh=True)
        settings.resize(760, 520)
        settings.settings_tabs.setCurrentIndex(1)
        settings.activateWindow()
        qtbot.wait(10)
        settings.update_region_render_summary()

        assert settings.slider_relief_offset_x.isEnabled()
        assert settings.slider_relief_offset_y.isEnabled()
        assert settings.spin_relief_font.isEnabled()
        assert settings.spin_relief_offset_x.minimum() == -1000
        assert settings.spin_relief_offset_x.maximum() == 1000
        assert settings.spin_relief_offset_y.minimum() == -1000
        assert settings.spin_relief_offset_y.maximum() == 1000

        for name, typed, dragged, attribute in (
            ("offset_x", "-875", 1000, "region_relief_offset_x"),
            ("offset_y", "935", -1000, "region_relief_offset_y"),
            ("opacity", "73", 0, "region_frame_opacity"),
        ):
            spin = getattr(settings, f"spin_relief_{name}")
            slider = getattr(settings, f"slider_relief_{name}")
            spin_rect = QRect(spin.mapTo(settings, QPoint()), spin.size())
            slider_rect = QRect(slider.mapTo(settings, QPoint()), slider.size())
            assert not spin_rect.intersects(slider_rect)
            spin.setFocus()
            spin.selectAll()
            qtbot.keyClicks(spin, typed)
            qtbot.keyClick(spin, Qt.Key_Tab)
            assert spin.value() == slider.value() == int(typed)
            assert getattr(controller, attribute) == int(typed)
            slider.setValue(dragged)
            assert spin.value() == dragged
            assert getattr(controller, attribute) == dragged
            assert controller.get_settings_payload()[attribute] == dragged
    finally:
        if settings is not None:
            settings.close()
        controller.close_app()
        overlay.clear_all()
        overlay.close()
