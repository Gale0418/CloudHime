"""User-facing recovery and lifecycle contracts; no live services or secrets."""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QMessageBox

from cloudhime_ui import Controller, OverlayWindow, SelectionOverlay
from celestial_ui import chrome_icon


def test_selection_overlay_handles_synchronous_fullscreen_resize(qtbot, monkeypatch):
    states = []

    def synchronous_resize(overlay, state):
        states.append(state)
        overlay.resizeEvent(QResizeEvent(QSize(800, 600), overlay.size()))

    monkeypatch.setattr(SelectionOverlay, "setWindowState", synchronous_resize)
    overlay = SelectionOverlay()
    qtbot.addWidget(overlay)
    assert states == [Qt.WindowFullScreen]
    assert overlay.selection_hint.parent() is overlay
    assert overlay.selection_hint.y() == 16
    assert not overlay.isVisible()


@pytest.fixture
def controller(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None))
    monkeypatch.setattr("cloudhime_ui.SecretStore.get", lambda self: "")
    monkeypatch.setattr("cloudhime_ui.SecretStore.legacy_sources_disabled", lambda self: True)
    monkeypatch.delenv("CLOUDHIME_GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args: None)
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    window = Controller(overlay)
    qtbot.addWidget(window)
    window.show()
    yield window
    monkeypatch.setattr(window, "_persist_pending_api_key", lambda: True)
    monkeypatch.setattr(window, "_persist_pending_openai_api_key", lambda: True)
    monkeypatch.setattr(window, "save_settings", lambda: True)
    window.close_app()


@pytest.mark.parametrize("language", ["zh-TW", "en", "ja"])
def test_cooldown_preserves_progress_and_terminal_status(controller, monkeypatch, language):
    controller.set_ui_language(language, persist=False)
    monkeypatch.setattr(controller, "trigger_scan_sequence", lambda: setattr(controller, "scan_in_progress", True))
    controller.on_immediate_click()
    assert controller.cooldown_timer.isActive()
    controller.update_status("Network unavailable — retry")
    controller.update_cooldown_progress()
    assert controller.lbl_status.text() == "Network unavailable — retry"
    assert controller.btn_now.text() == controller._tr("controller.button.wait", seconds=5)
    controller.scan_in_progress = False
    controller.cooldown_timer.stop()
    controller.reset_immediate_btn()
    assert controller.lbl_status.text() == "Network unavailable — retry"
    assert controller.btn_now.isEnabled()


def test_stop_releases_cooldown_and_busy_buttons(controller, monkeypatch):
    monkeypatch.setattr(controller, "trigger_scan_sequence", lambda: setattr(controller, "scan_in_progress", True))
    controller.on_immediate_click()
    controller.stop_scan()
    assert not controller.scan_in_progress
    assert not controller.cooldown_timer.isActive()
    assert not controller.cooldown_progress_timer.isActive()
    assert controller.btn_now.isEnabled()
    assert controller.btn_hotkey.isEnabled()
    assert controller.btn_now.text() == controller.get_hotkey_button_text()


def test_completion_releases_busy_buttons_after_cooldown(controller):
    controller.scan_in_progress = True
    controller.reset_immediate_btn()
    assert not controller.btn_now.isEnabled()
    controller.on_scan_complete([])
    assert controller.btn_now.isEnabled()


@pytest.mark.parametrize("message", ["Network error: retry", "文字が検出されませんでした", "沒有偵測到文字"])
def test_auto_scan_accepts_status_in_every_language(controller, message):
    controller.display_timer.start()
    controller.update_status(message)
    assert controller.lbl_status.text() == message


def test_language_switch_updates_idle_status_and_preserves_worker_error(controller):
    controller._set_status_text("controller.status.ready")
    for language in ("zh-TW", "en", "ja"):
        controller.set_ui_language(language, persist=False)
        assert controller.lbl_status.text() == controller._tr("controller.status.ready")
    controller.update_status("Service unavailable")
    controller.set_ui_language("zh-TW", persist=False)
    assert controller.lbl_status.text() == "Service unavailable"


def test_scan_requests_are_not_queued_while_busy(controller, monkeypatch, qtbot):
    dispatch = Mock()
    monkeypatch.setattr(controller, "_emit_scan_signal", dispatch)
    controller.trigger_scan_sequence()
    controller.trigger_scan_sequence()
    controller.on_immediate_click()
    qtbot.waitUntil(lambda: dispatch.call_count == 1)
    qtbot.wait(60)
    assert dispatch.call_count == 1


def test_translate_button_dispatches_worker_and_displays_result(controller, monkeypatch, qtbot):
    calls = []

    def scan(worker):
        calls.append(worker._active_scan_request.generation)
        worker._emit_scan_finished([("測試翻譯", 100, 100, 180, 40)])

    monkeypatch.setattr("cloudhime_workers.OCRWorker._run_scan_once", scan)
    controller.select_translation_provider("google")
    qtbot.mouseClick(controller.btn_now, Qt.LeftButton)
    qtbot.waitUntil(lambda: bool(calls), timeout=2000)
    qtbot.waitUntil(lambda: bool(controller.overlay.bubbles), timeout=2000)
    assert not controller.scan_in_progress
    assert controller.last_scan_results[0][0] == "測試翻譯"


def test_taskbar_icon_uses_product_artwork(controller):
    image = controller.windowIcon().pixmap(64, 64).toImage()
    assert not image.isNull()
    assert any(
        image.pixelColor(x, y).blue() > image.pixelColor(x, y).red() + 40
        for y in range(image.height()) for x in range(image.width())
    )


@pytest.mark.parametrize("provider", ["luna", "online_gemma"])
@pytest.mark.parametrize("exit_path", ["button", "toggle", "native"])
def test_abandoned_key_setup_keeps_previous_route(controller, provider, exit_path):
    controller.toggle_settings_window()
    settings = controller.settings_window
    original_chain = tuple(controller.provider_chain)
    settings.translation_panel.on_provider_selected(provider)
    assert controller._required_provider_setup() == provider
    if exit_path == "button":
        settings.btn_cancel.click()
    elif exit_path == "toggle":
        controller.toggle_settings_window()
    else:
        settings.close()
    assert not settings.isVisible()
    assert controller.pending_translation_provider_id is None
    assert controller._required_provider_setup() is None
    assert tuple(controller.provider_chain) == original_chain


def test_save_keeps_unconfigured_provider_visible(controller):
    controller.toggle_settings_window()
    settings = controller.settings_window
    settings.translation_panel.on_provider_selected("luna")
    settings.btn_save.click()
    assert settings.isVisible()
    assert controller.pending_translation_provider_id == "luna"
    assert settings.settings_tabs.currentIndex() == 0


def test_settings_fit_short_desktop_and_hide_portrait(controller, monkeypatch, qtbot):
    available = QRect(1000, 0, 800, 600)
    monkeypatch.setattr(controller, "screen", lambda: type("Screen", (), {"availableGeometry": lambda self: available})())
    controller.toggle_settings_window()
    settings = controller.settings_window
    qtbot.wait(10)
    assert available.contains(settings.geometry())
    assert not settings.princess_portrait.isVisible()
    assert settings.btn_save.isVisible()
    settings.resize(1120, 760)
    qtbot.wait(10)
    assert settings.princess_portrait.isVisible()
    controller.set_theme_mode("high_contrast")
    assert not settings.princess_portrait.isVisible()


def test_native_close_stops_threads_and_overlay(controller, qtbot):
    controller.overlay.show()
    controller.close()
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False))
    assert not controller.ocr_thread.isRunning()
    assert not controller.isVisible()
    assert not controller.overlay.isVisible()


def test_native_close_is_rejected_when_secret_save_fails(controller, monkeypatch, qtbot):
    original_status = controller.lbl_status.text()
    monkeypatch.setattr(controller, "_persist_pending_api_key", lambda: False)
    controller.close()
    assert controller.isVisible()
    assert not controller._close_app_started
    assert controller.ocr_thread.isRunning()
    assert controller.lbl_status.text() == original_status
    assert controller.btn_now.isEnabled()
    assert controller.btn_hotkey.isEnabled()
    assert controller.btn_30.isEnabled()
    monkeypatch.setattr(controller, "_persist_pending_api_key", lambda: True)
    controller.close_app()
    # Async shutdown follows the rejected-close assertions so qtbot can drain
    # all owned Qt objects before its widget teardown.
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False))


def test_dark_window_icons_resolve_css_rgba_foreground(qapp):
    image = chrome_icon("close", "rgba(255, 255, 255, 220)").pixmap(16, 16).toImage()
    ink = image.pixelColor(8, 8)
    assert ink.red() > 240
    assert ink.green() > 240
    assert ink.blue() > 240
    assert ink.alpha() > 0


def test_native_close_is_rejected_when_settings_save_fails(controller, monkeypatch, qtbot):
    monkeypatch.setattr(controller, "save_settings", lambda: False)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.No)
    controller.close()
    assert controller.isVisible()
    assert not controller._close_app_started
    assert controller.ocr_thread.isRunning()
    assert controller.lbl_status.text() == controller._tr("settings_save_failed")
    assert controller.btn_now.isEnabled()
    assert controller.btn_hotkey.isEnabled()
    assert controller.btn_30.isEnabled()
    monkeypatch.setattr(controller, "save_settings", lambda: True)
    controller.close_app()
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False))


def test_native_close_can_discard_settings_after_save_failure(controller, monkeypatch, qtbot):
    monkeypatch.setattr(controller, "save_settings", lambda: False)
    prompt = Mock(return_value=QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "question", prompt)
    controller.close()
    prompt.assert_called_once()
    assert prompt.call_args.args[-1] == QMessageBox.No
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False))
    assert not controller.isVisible()
    assert not controller.ocr_thread.isRunning()


def test_discard_choice_never_bypasses_secret_save_failure(controller, monkeypatch, qtbot):
    monkeypatch.setattr(controller, "_persist_pending_api_key", lambda: False)
    prompt = Mock(return_value=QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "question", prompt)
    controller.close()
    prompt.assert_not_called()
    assert controller.isVisible()
    assert controller.ocr_thread.isRunning()
    monkeypatch.setattr(controller, "_persist_pending_api_key", lambda: True)
    controller.close_app()
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False))


@pytest.mark.parametrize("mode", ["region", "fullscreen"])
@pytest.mark.parametrize("cancel_action", ["escape", "small_drag"])
def test_cancelled_reselection_keeps_previous_area_and_mode(controller, qtbot, mode, cancel_action):
    original = (40, 120, 220, 100)
    controller.on_region_selected(original)
    controller.set_scan_mode(mode)
    generation = controller.scan_generation
    controller.begin_region_selection()
    selection = controller.selection_overlay
    if cancel_action == "escape":
        qtbot.keyClick(selection, Qt.Key_Escape)
    else:
        qtbot.mousePress(selection, Qt.LeftButton, pos=QPoint(60, 150))
        qtbot.mouseMove(selection, QPoint(62, 152))
        qtbot.mouseRelease(selection, Qt.LeftButton, pos=QPoint(62, 152))
    assert not selection.isVisible()
    assert controller.isVisible()
    assert controller.selected_region == original
    assert controller.worker.scan_region == original
    assert controller.scan_mode == mode
    assert controller.btn_mode_region.isChecked() == (mode == "region")
    assert controller.region_frame.isVisible() == (mode == "region")
    assert controller.scan_generation == generation + 1
    assert controller.current_auto_interval == 0
    assert controller.lbl_status.text() == controller._tr("controller.status.selection_cancelled")


def test_first_selection_cancel_stays_in_fullscreen(controller, qtbot):
    controller.begin_region_selection()
    qtbot.keyClick(controller.selection_overlay, Qt.Key_Escape)
    assert controller.selected_region is None
    assert controller.scan_mode == "fullscreen"
    assert controller.btn_mode_full.isChecked()


@pytest.mark.parametrize("language", ["zh-TW", "en", "ja"])
def test_selection_feedback_tracks_drag_and_commits_the_shown_area(controller, qtbot, language):
    controller.set_ui_language(language, persist=False)
    controller.begin_region_selection()
    selection = controller.selection_overlay
    assert "Esc" in selection.selection_hint.text()
    assert selection.selection_hint.testAttribute(Qt.WA_TransparentForMouseEvents)
    qtbot.mousePress(selection, Qt.LeftButton, pos=QPoint(320, 280))
    qtbot.mouseMove(selection, QPoint(100, 150))
    rect = selection.current_rect.normalized()
    assert f"{rect.width()} × {rect.height()}" in selection.selection_hint.text()
    assert selection.selection_hint.accessibleName() == selection.selection_hint.text()
    qtbot.mouseRelease(selection, Qt.LeftButton, pos=QPoint(100, 150))
    assert controller.selected_region == (rect.x(), rect.y(), rect.width(), rect.height())
    assert controller.scan_mode == "region"
    assert not selection.isVisible()


@pytest.mark.parametrize("language", ["zh-TW", "en", "ja"])
def test_auto_scan_feedback_follows_timer_and_preserves_worker_status(controller, monkeypatch, language):
    controller.set_ui_language(language, persist=False)
    monkeypatch.setattr(controller, "get_random_scan_delay_ms", lambda: 2400)
    monkeypatch.setattr(controller, "_emit_scan_signal", lambda *args: None)
    controller.start_auto_scan()
    assert controller.auto_timer.isActive()
    assert controller.countdown_seconds == 3
    assert controller._tr("controller.button.auto_wait", seconds=3) in controller.btn_30.text()
    controller.update_status("Service unavailable — retry")
    controller.update_countdown_label()
    assert controller.lbl_status.text() == "Service unavailable — retry"
    controller.trigger_scan_sequence()
    assert controller._tr("controller.button.auto_busy") in controller.btn_30.text()
    assert not controller.btn_now.isEnabled()
    assert not controller.btn_hotkey.isEnabled()
    assert controller.btn_now.text() == controller._tr("controller.button.translating")
    controller.on_scan_complete([])
    assert controller._tr("controller.button.auto_wait", seconds=3) in controller.btn_30.text()
    assert controller.btn_now.isEnabled()
    controller.stop_scan()
    assert not controller.auto_timer.isActive()
    assert controller._tr("controller.button.auto_scan") in controller.btn_30.text()
