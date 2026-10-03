"""User-facing recovery and lifecycle contracts; no live services or secrets."""
from unittest.mock import Mock

from types import SimpleNamespace

import pytest
import celestial_ui
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QMessageBox

from cloudhime_ui import Controller, OverlayWindow, SelectionOverlay
from celestial_ui import chrome_icon
from ocr_backend_catalog import optional_backend_names
from ocr_backend_panel import OcrBackendSettingsPanel
from provider_health import local_model_failure_message


@pytest.mark.parametrize("language", ["zh-TW", "en", "ja"])
@pytest.mark.parametrize("vision", [False, True])
def test_local_startup_failure_shows_safe_recovery(controller, language, vision):
    controller.set_ui_language(language, persist=False)
    controller.worker.use_gemma_translation = True
    controller.worker.gemma_model = "gemma-3-4b-it-local"
    controller.local_multimodal_enabled = vision
    controller.provider_chain = ()
    detail = "health_timeout: PRIVATE_USER_PATH <b>RAW_STDERR</b> " * 100
    controller.update_status("Previous message")
    handler = controller.on_local_vision_status if vision else controller.on_local_model_status
    handler("failed", detail)
    message = controller.lbl_status.text()
    assert local_model_failure_message(detail, language) in message
    assert "PRIVATE_USER_PATH" not in message
    assert "RAW_STDERR" not in message
    assert len(message) < 500
    assert controller.lbl_status.toolTip() == message
    assert controller.lbl_status.statusTip() == message
    assert controller.lbl_status.textFormat() == Qt.PlainText


@pytest.mark.parametrize("state", ["starting", "progress", "ready", "failed", "stopped"])
def test_inactive_local_engine_cannot_replace_current_translation_status(controller, state):
    controller.update_status("Google translation failed — retry")
    controller.on_local_vision_status(state, "40|downloading")
    controller.on_local_model_status(state, "PRIVATE_DIAGNOSTICS")
    assert controller.local_vision_state == state
    assert controller.local_model_state == state
    assert controller.lbl_status.text() == "Google translation failed — retry"


def test_localized_status_keeps_accessible_hints_current(controller):
    controller.update_status("Previous error")
    controller._set_status_text("controller.status.ready")
    assert controller.lbl_status.toolTip() == controller.lbl_status.text()
    assert controller.lbl_status.statusTip() == controller.lbl_status.text()


@pytest.mark.parametrize("language", ["zh-TW", "en", "ja"])
@pytest.mark.parametrize("provider", ["google", "local_gemma", "online_gemma", "luna"])
def test_main_window_explains_current_engine_and_data_destination(controller, language, provider):
    controller.set_ui_language(language, persist=False)
    controller.worker.use_gemma_translation = provider != "google"
    controller.worker.gemma_model = "gemma-3-4b-it-local" if provider == "local_gemma" else "gemma-3-27b-it"
    controller.provider_chain = ("openai",) if provider == "luna" else ("gemma", "google")
    controller.worker.google_api_key = "PRIVATE_GOOGLE_KEY"
    controller.openai_api_key = "PRIVATE_OPENAI_KEY"
    controller.local_multimodal_enabled = False
    controller.local_model_state = "ready"
    controller.update_status("Translation error — retry")
    assert controller._tr(f"controller.engine.{provider}") in controller.lbl_engine_summary.text()
    assert controller.lbl_engine_data.text() == controller._tr(f"controller.engine.data.{provider}")
    if provider in {"online_gemma", "luna"}:
        assert controller._tr("controller.engine.state.configured") in controller.lbl_engine_summary.text()
    assert "PRIVATE_" not in controller.lbl_engine_summary.text() + controller.lbl_engine_data.text()
    assert controller.lbl_status.text() == "Translation error — retry"


def test_pending_engine_keeps_actual_route_and_data_destination_visible(controller):
    controller.worker.use_gemma_translation = False
    controller.pending_translation_provider_id = "luna"
    controller._refresh_main_engine_summary()
    assert controller._tr("controller.engine.google") in controller.lbl_engine_summary.text()
    assert controller._tr("controller.engine.pending", name="Luna") in controller.lbl_engine_summary.text()
    assert controller.lbl_engine_data.text() == controller._tr("controller.engine.data.google")


def test_engine_settings_entry_can_be_used_again_without_closing_or_switching_route(controller, qtbot):
    controller.worker.use_gemma_translation = False
    chain = controller.provider_chain
    qtbot.mouseClick(controller.btn_engine_settings, Qt.LeftButton)
    assert controller.settings_window.isVisible()
    controller.settings_window.settings_tabs.setCurrentIndex(2)
    qtbot.mouseClick(controller.btn_engine_settings, Qt.LeftButton)
    assert controller.settings_window.isVisible()
    assert controller.settings_window.settings_tabs.currentIndex() == 0
    assert controller.provider_chain == chain
    assert not controller.worker.use_gemma_translation


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


@pytest.mark.parametrize("language", ["zh-TW", "en", "ja"])
def test_auto_scan_can_pause_to_read_and_resume_without_erasing_captions(controller, qtbot, language):
    controller.set_ui_language(language, persist=False)
    result = [("慢慢讀完這一句", 100, 100, 180, 40)]
    controller.on_scan_complete(result)
    bubble = controller.overlay.bubbles[0]
    controller.start_auto_scan(base_interval=5000)
    generation = controller.scan_generation
    qtbot.mouseClick(controller.btn_30, Qt.LeftButton)
    assert not controller.auto_timer.isActive()
    assert not controller.display_timer.isActive()
    assert controller.current_auto_interval == 0
    assert controller.scan_generation > generation
    assert controller.overlay.bubbles[0] is bubble
    assert controller.last_scan_results == result
    assert controller._tr("controller.button.auto_resume") in controller.btn_30.text()
    assert controller.lbl_status.text() == controller._tr("controller.status.auto_paused")
    controller.set_ui_language(language, persist=False)
    assert controller.lbl_status.text() == controller._tr("controller.status.auto_paused")
    controller.on_scan_complete_for_generation(generation, [("晚到的下一句", 100, 100, 180, 40)])
    assert controller.overlay.bubbles[0] is bubble
    controller.btn_30.setFocus()
    qtbot.keyClick(controller.btn_30, Qt.Key_Space)
    assert controller.current_auto_interval == 5000
    assert controller.auto_timer.isActive()
    assert not controller.scan_in_progress
    assert controller.overlay.bubbles[0] is bubble


def test_pause_freezes_visible_stream_and_discards_pending_or_late_chunks(controller, qtbot):
    controller.on_scan_complete([("上一段完整翻譯", 100, 100, 180, 40)])
    controller.start_auto_scan()
    generation = controller.scan_generation
    controller.scan_in_progress = True
    controller.on_translation_stream_update(0, "目前看得到的半句", "google", 100, 100, 180, 40)
    controller.on_translation_stream_update_for_generation(generation, 0, "還沒顯示的句子", "google", 100, 100, 180, 40)
    qtbot.mouseClick(controller.btn_30, Qt.LeftButton)
    controller.on_translation_stream_update_for_generation(generation, 0, "晚到的串流", "google", 100, 100, 180, 40)
    controller.set_theme_mode("dark")
    assert controller.overlay.bubbles[0].text() == "目前看得到的半句"
    assert not controller._pending_stream_updates
    assert not controller.scan_in_progress
    assert controller.btn_now.isEnabled()
    assert controller.btn_hotkey.isEnabled()


@pytest.mark.parametrize("theme", ["light", "dark", "high_contrast"])
def test_stop_clears_reading_state_so_theme_changes_cannot_restore_old_captions(controller, theme):
    controller.on_scan_complete([("已經停止閱讀的舊句子", 100, 100, 180, 40)])
    controller.stop_scan()
    controller.set_theme_mode(theme)
    assert not controller.overlay.bubbles
    assert controller.last_scan_results == []
    assert controller._tr("controller.button.auto_scan") in controller.btn_30.text()


def test_stop_after_pause_returns_to_idle_and_clears_frozen_caption(controller, qtbot):
    controller.on_scan_complete([("暫停中的句子", 100, 100, 180, 40)])
    controller.start_auto_scan()
    qtbot.mouseClick(controller.btn_30, Qt.LeftButton)
    qtbot.mouseClick(controller.btn_stop, Qt.LeftButton)
    assert not controller.overlay.bubbles
    assert controller.last_scan_results == []
    assert controller._tr("controller.button.auto_scan") in controller.btn_30.text()


def test_pause_before_capture_prevents_the_delayed_scan_request(controller, qtbot):
    requests = []
    controller.request_scan.connect(lambda: requests.append(True))
    controller.start_auto_scan(base_interval=5000)
    controller.trigger_scan_sequence()
    qtbot.mouseClick(controller.btn_30, Qt.LeftButton)
    qtbot.wait(80)
    assert requests == []
    assert not controller.scan_in_progress


def test_resume_honors_interval_changed_while_paused(controller, qtbot):
    controller.start_auto_scan(base_interval=5000)
    qtbot.mouseClick(controller.btn_30, Qt.LeftButton)
    controller.cmb_scan_interval.setCurrentIndex(controller.cmb_scan_interval.findData(15))
    qtbot.mouseClick(controller.btn_30, Qt.LeftButton)
    assert controller.current_auto_interval == 15000
    assert controller.random_scan_center_seconds == 15
    assert controller.auto_timer.isActive()


def test_manual_translation_while_paused_updates_caption_without_restarting_auto_scan(controller, qtbot, monkeypatch):
    def scan(worker):
        worker._emit_scan_finished([("手動翻譯的下一句", 100, 100, 180, 40)])

    monkeypatch.setattr("cloudhime_workers.OCRWorker._run_scan_once", scan)
    controller.on_scan_complete([("慢慢閱讀中的句子", 100, 100, 180, 40)])
    controller.start_auto_scan()
    qtbot.mouseClick(controller.btn_30, Qt.LeftButton)
    qtbot.mouseClick(controller.btn_now, Qt.LeftButton)
    qtbot.waitUntil(lambda: controller.last_scan_results[0][0] == "手動翻譯的下一句", timeout=2000)
    assert controller.current_auto_interval == 0
    assert not controller.auto_timer.isActive()
    assert not controller.btn_30.isChecked()
    assert controller._tr("controller.button.auto_resume") in controller.btn_30.text()


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


@pytest.mark.parametrize(
    ("alpha", "expected"),
    [("0.5", 128), ("1.0", 255), ("1", 1), ("220", 220)],
)
def test_chrome_icon_rgba_alpha_supports_fractional_and_qt_integer_values(qapp, monkeypatch, alpha, expected):
    captured = []
    original_qpen = celestial_ui.QPen

    def record_pen(color, width):
        captured.append(color.alpha())
        return original_qpen(color, width)

    monkeypatch.setattr(celestial_ui, "QPen", record_pen)
    chrome_icon("close", f"rgba(255, 255, 255, {alpha})")
    assert captured == [expected]


def test_ocr_backend_unknown_state_still_starts_install(qtbot, monkeypatch):
    panel = OcrBackendSettingsPanel(SimpleNamespace(ui_language="en"))
    qtbot.addWidget(panel)
    backend_name = optional_backend_names()[0]
    started = []
    warnings = []
    monkeypatch.setattr("ocr_backend_panel.detect_backend_state", lambda _name: None)
    monkeypatch.setattr("ocr_backend_panel.QMessageBox.warning", lambda *_args: warnings.append(_args[-1]))
    monkeypatch.setattr(panel, "_start_backend_install", lambda name: started.append(name))
    monkeypatch.setattr(panel, "_set_controller_backend_enabled", lambda *_args: None)
    monkeypatch.setattr(panel, "sync_from_controller", lambda: None)

    panel.on_backend_toggled(backend_name, True)
    panel._on_install_finished(backend_name, True, "Install succeeded but backend state is unknown.")

    assert started == [backend_name]
    assert warnings == ["Install succeeded but backend state is unknown."]


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
