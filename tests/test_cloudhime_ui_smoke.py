from pathlib import Path
import json
import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from CloudHime import Controller, OverlayWindow
from cloudhime_ui import StatusChargeBar, _resource_path
from PySide6.QtCore import QTimer


def test_resource_path_resolves_bundled_assets():
    asset_path = Path(_resource_path("assets/bg_dark.jpg"))

    assert asset_path == (Path(__file__).resolve().parents[1] / "assets/bg_dark.jpg")
    assert asset_path.is_file()


def test_cloudhime_startup(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)

    window = Controller(overlay)
    qtbot.addWidget(window)

    assert overlay is not None
    assert window is not None

    overlay.show()
    window.show()
    assert window.isVisible()
    assert overlay.isVisible()

    window.close_app()
    qtbot.waitUntil(lambda: not window.isVisible() and not overlay.isVisible(), timeout=2000)


def test_cloudhime_startup_loads_local_multimodal_settings(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr(
        "cloudhime_ui.load_settings_data",
        lambda paths: (
            {
                "local_multimodal_enabled": True,
                "local_multimodal_base_url": "http://localhost:11434/v1",
                "local_multimodal_model": "vision-local",
                "local_multimodal_timeout_seconds": 45,
            },
            None,
        ),
        raising=False,
    )
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    window = Controller(overlay)
    qtbot.addWidget(window)

    assert window.local_multimodal_enabled is True
    assert window.local_multimodal_base_url == "http://localhost:11434/v1"
    assert window.local_multimodal_model == "vision-local"
    assert window.local_multimodal_timeout_seconds == 45
    assert window.worker.local_multimodal_enabled is True
    assert window.worker.local_multimodal_base_url == "http://localhost:11434/v1"
    assert window.worker.local_multimodal_model == "vision-local"
    assert window.worker.local_multimodal_timeout_seconds == 45

    window.close_app()
    qtbot.waitUntil(lambda: not window.isVisible() and not overlay.isVisible(), timeout=2000)


def test_controller_settings_payload_includes_local_multimodal_config():
    controller = Controller.__new__(Controller)
    controller.worker = SimpleNamespace(
        gemma_model="gemma-3-4b-it-local",
        use_gemma_translation=True,
        auto_threshold_enabled=True,
        gemma_auto_switch_enabled=False,
        google_api_key="",
        ocr_backend_chain=["windows"],
        binary_threshold=100,
        local_multimodal_enabled=True,
        local_multimodal_base_url="http://localhost:11434/v1",
        local_multimodal_model="vision-local",
        local_multimodal_timeout_seconds=45,
    )
    controller.gemma_prompt = "prompt"
    controller.screenshot_gemma_prompt = "screenshot prompt"
    controller.auto_threshold_refresh_minutes = 10
    controller.google_ocr_enabled = False
    controller.random_scan_center_seconds = 10
    controller.random_scan_jitter_percent = 20
    controller.region_pass_through = False
    controller.region_render_mode = "bubble"
    controller.region_relief_offset_x = 0
    controller.region_relief_offset_y = 0
    controller.region_relief_font_pt = 18
    controller.region_frame_opacity = 40
    controller.scan_mode = "fullscreen"
    controller.selected_region = None
    controller.is_dark_mode = False
    controller.theme_mode = "light"
    controller.ui_language = "zh-TW"

    payload = Controller.get_settings_payload(controller)

    assert payload["local_multimodal_enabled"] is True
    assert payload["local_multimodal_base_url"] == "http://localhost:11434/v1"
    assert payload["local_multimodal_model"] == "vision-local"
    assert payload["local_multimodal_timeout_seconds"] == 45


def test_controller_provider_metadata_payload_excludes_all_secret_slots():
    controller = Controller.__new__(Controller)
    controller.worker = SimpleNamespace(
        gemma_model="gemma-3-4b-it-local",
        use_gemma_translation=False,
        auto_threshold_enabled=False,
        gemma_auto_switch_enabled=False,
        google_api_key="primary-secret",
        ocr_backend_chain=["windows"],
        binary_threshold=100,
    )
    controller.gemma_prompt = "prompt"
    controller.screenshot_gemma_prompt = "screenshot"
    controller.auto_threshold_refresh_minutes = 10
    controller.google_ocr_enabled = False
    controller.random_scan_center_seconds = 10
    controller.random_scan_jitter_percent = 20
    controller.region_pass_through = False
    controller.region_render_mode = "bubble"
    controller.region_relief_offset_x = 0
    controller.region_relief_offset_y = 0
    controller.region_relief_font_pt = 18
    controller.region_frame_opacity = 40
    controller.scan_mode = "fullscreen"
    controller.selected_region = None
    controller.is_dark_mode = False
    controller.theme_mode = "light"
    controller.ui_language = "zh-TW"
    controller.online_gemma_enabled = True
    controller.google_api_key = "primary-secret"
    controller.openai_enabled = True
    controller.openai_reasoning_effort = "none"
    controller.openai_timeout_seconds = 30
    controller.provider_chain = ["gemma", "openai"]

    payload = Controller.get_settings_payload(controller)

    assert payload["schema_version"] == 7
    assert "google_api_key_slots" not in payload
    assert "primary-secret" not in json.dumps(payload)
    assert "openai_api_key" not in payload


def test_controller_applies_single_google_credential():
    calls = []
    controller = Controller.__new__(Controller)
    controller.worker = SimpleNamespace(
        set_google_api_key=lambda value: calls.append(value)
    )
    controller.google_api_key = "single-secret"

    Controller._apply_google_credentials_to_worker(controller)

    assert calls == ["single-secret"]


def test_settings_revamp_keeps_legacy_three_column_shell(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    controller.toggle_settings_window()
    settings = controller.settings_window
    assert settings.minimumWidth() == 1400
    assert settings.minimumHeight() == 780
    assert not hasattr(settings, "settings_scroll_area")
    assert not hasattr(settings, "settings_nav_buttons")
    assert settings.card_translate.parent() is settings.translation_panel
    controller.close_app()


def test_controller_local_gemma_tuning_schedules_save():
    controller = Controller.__new__(Controller)
    calls = []
    controller.worker = SimpleNamespace(
        set_local_gemma_params=lambda temperature, repeat_penalty: calls.append(
            (temperature, repeat_penalty)
        )
    )
    controller.local_gemma_repeat_penalty = 1.15
    controller.save_count = 0
    controller.schedule_save_settings = lambda: setattr(controller, "save_count", controller.save_count + 1)

    Controller.on_local_gemma_temp_changed(controller, 0.3)

    assert calls == [(0.3, 1.15)]
    assert controller.save_count == 1


def test_controller_local_multimodal_toggle_pushes_complete_config():
    controller = Controller.__new__(Controller)
    calls = []
    controller.worker = SimpleNamespace(
        set_local_multimodal_config=lambda **config: calls.append(config)
    )
    controller.local_multimodal_base_url = "http://localhost:11434/v1"
    controller.local_multimodal_model = "vision-local"
    controller.local_multimodal_timeout_seconds = 45
    controller.save_count = 0
    controller.schedule_save_settings = lambda: setattr(controller, "save_count", controller.save_count + 1)

    Controller.on_local_multimodal_enabled_changed(controller, True)

    assert controller.local_multimodal_enabled is True
    assert calls == [{
        "enabled": True,
        "base_url": "http://localhost:11434/v1",
        "model_name": "vision-local",
        "timeout_seconds": 45,
        "cpu_only": False,
    }]
    assert controller.save_count == 1


def test_status_charge_bar_indeterminate_starts_and_stops(qtbot):
    bar = StatusChargeBar()
    qtbot.addWidget(bar)

    bar.set_indeterminate(True, "載入中")

    assert bar.indeterminate is True
    assert bar._animation_timer.isActive() is True

    bar.set_progress(100, "完成")

    assert bar.indeterminate is False
    assert bar._animation_timer.isActive() is False


def test_controller_local_model_loading_uses_indeterminate_charge_bar(qtbot):
    controller = Controller.__new__(Controller)
    controller.ui_language = "zh-TW"
    controller.theme_mode = "light"
    controller.charge_bar = StatusChargeBar()
    qtbot.addWidget(controller.charge_bar)
    messages = []
    controller.lbl_status = SimpleNamespace(setText=lambda text: messages.append(text))
    health_refreshes = []
    controller._refresh_translation_provider_health = lambda: health_refreshes.append(True)

    Controller.on_local_model_status(controller, "loading", "")

    assert controller.local_model_state == "loading"
    assert controller.charge_bar.indeterminate is True
    assert "Local Gemma3" in controller.charge_bar.label
    assert messages
    assert health_refreshes == [True]


def test_controller_local_vision_states_update_ui(qtbot):
    controller = Controller.__new__(Controller)
    controller.ui_language = "zh-TW"
    controller.theme_mode = "light"
    controller.charge_bar = StatusChargeBar()
    qtbot.addWidget(controller.charge_bar)
    messages = []
    controller.lbl_status = SimpleNamespace(setText=lambda text: messages.append(text))
    health_refreshes = []
    controller._refresh_translation_provider_health = lambda: health_refreshes.append(True)

    Controller.on_local_vision_status(controller, "starting", "")
    assert controller.charge_bar.indeterminate is True
    assert messages[-1] == "正在準備內嵌多模態引擎..."

    Controller.on_local_vision_status(controller, "progress", "85|warming_up")
    assert controller.charge_bar.indeterminate is False
    assert controller.charge_bar.progress == 85
    assert "執行模型暖身" in controller.charge_bar.label
    assert messages[-1] == "執行模型暖身... (85%)"

    Controller.on_local_vision_status(controller, "ready", "")
    assert controller.charge_bar.indeterminate is False
    assert controller.charge_bar.progress == 100
    assert messages[-1] == "內嵌 Gemma Vision 已就緒"

    Controller.on_local_vision_status(controller, "missing", "path/to/model")
    assert controller.charge_bar.progress == 0
    assert "找不到內嵌多模態模型檔案" in messages[-1]
    assert "path/to/model" in messages[-1]

    Controller.on_local_vision_status(controller, "stopped", "")
    assert controller.charge_bar.progress == 0
    assert messages[-1] == "內嵌多模態伺服器已停止"
    assert len(health_refreshes) == 5


def test_controller_local_vision_download_status_is_bilingual(qtbot):
    for language, expected in (
        ("zh-TW", "下載 Gemma 模型"),
        ("en", "Downloading Gemma model"),
    ):
        controller = Controller.__new__(Controller)
        controller.ui_language = language
        controller.theme_mode = "light"
        controller.charge_bar = StatusChargeBar()
        qtbot.addWidget(controller.charge_bar)
        messages = []
        controller.lbl_status = SimpleNamespace(setText=lambda text: messages.append(text))

        Controller.on_local_vision_status(controller, "progress", "40|downloading")

        assert controller.charge_bar.progress == 40
        assert expected in controller.charge_bar.label
        assert expected in messages[-1]


def test_controller_japanese_rescue_status_is_bilingual(qtbot):
    for language, expected in (
        ("zh-TW", "下載日文 OCR 模型"),
        ("en", "Downloading Japanese OCR model"),
    ):
        controller = Controller.__new__(Controller)
        controller.ui_language = language
        controller.theme_mode = "light"
        controller.charge_bar = StatusChargeBar()
        qtbot.addWidget(controller.charge_bar)
        messages = []
        controller.lbl_status = SimpleNamespace(setText=lambda text: messages.append(text))

        Controller.on_japanese_rescue_status(controller, "progress", "40|downloading")

        assert controller.charge_bar.progress == 40
        assert expected in controller.charge_bar.label
        assert expected in messages[-1]


def test_api_key_uses_encrypted_store_and_does_not_write_plaintext_env(monkeypatch, tmp_path):
    import cloudhime_ui

    class FakeLineEdit:
        def __init__(self):
            self.value = ""

        def text(self):
            return self.value

        def blockSignals(self, _blocked):
            return None

        def setText(self, value):
            self.value = value

    class FakeSecretStore:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

        def delete(self):
            self.value = None

        def mark_legacy_sources_disabled(self):
            self.legacy_sources_disabled = True

    store = FakeSecretStore()
    env_path = tmp_path / "CloudHime" / ".env"
    monkeypatch.setattr(cloudhime_ui, "APPDATA_ENV_PATH", str(env_path))

    controller = Controller.__new__(Controller)
    controller.secret_store = store
    controller.worker = SimpleNamespace(
        google_api_key="",
        use_gemma_translation=False,
        set_google_api_key=lambda value: setattr(controller.worker, "google_api_key", value),
    )
    controller.input_api_key = FakeLineEdit()
    controller.settings_window = None
    controller.schedule_save_settings = lambda: None
    controller.toggle_ai_translation = lambda _enabled: None

    Controller.on_api_key_changed(controller, "secret-key")
    assert store.value is None
    assert not env_path.exists()
    Controller._persist_pending_api_key(controller)
    assert store.value == "secret-key"
    assert store.legacy_sources_disabled is True
    assert controller.worker.google_api_key == "secret-key"


def test_clearing_api_key_does_not_disable_local_gemma(monkeypatch):
    import cloudhime_ui

    class FakeLineEdit:
        def __init__(self):
            self.value = "secret-key"

        def text(self):
            return self.value

        def blockSignals(self, _blocked):
            return None

        def setText(self, value):
            self.value = value

    class FakeSecretStore:
        def set(self, _value):
            return None

        def delete(self):
            return None

        def mark_legacy_sources_disabled(self):
            return None

    toggles = []
    controller = Controller.__new__(Controller)
    controller.secret_store = FakeSecretStore()
    controller.worker = SimpleNamespace(
        google_api_key="secret-key",
        use_gemma_translation=True,
        gemma_model="gemma-3-4b-it-local",
        set_google_api_key=lambda value: setattr(controller.worker, "google_api_key", value),
    )
    controller.input_api_key = FakeLineEdit()
    controller.settings_window = None
    controller.schedule_save_settings = lambda: None
    controller.toggle_ai_translation = lambda enabled: toggles.append(enabled)

    Controller.on_api_key_changed(controller, "")

    assert controller.worker.google_api_key == ""
    assert toggles == []


def test_api_key_reader_skips_corrupt_appdata_for_legacy(monkeypatch, tmp_path):
    import cloudhime_ui

    appdata_path = tmp_path / "appdata.env"
    legacy_path = tmp_path / "legacy.env"
    appdata_path.write_bytes(b"CLOUDHIME_GOOGLE_API_KEY=\xff")
    legacy_path.write_text(
        f"{cloudhime_ui.API_KEY_ENV_VAR}=legacy-key\n",
        encoding="utf-8",
    )

    assert cloudhime_ui._read_api_key_from_env_files(
        (str(appdata_path), str(legacy_path))
    ) == "legacy-key"


def test_history_export_payload_is_json_safe_and_preserves_unicode():
    from cloudhime_ui import build_translation_history_export_payload

    payload = build_translation_history_export_payload({("日文", "zh-TW"): "繁體中文"})

    assert payload == {
        "schema_version": 1,
        "records": [{"key": ["日文", "zh-TW"], "value": "繁體中文"}],
    }
    json.dumps(payload, ensure_ascii=False)


def test_history_export_payload_supports_empty_history():
    from cloudhime_ui import build_translation_history_export_payload

    assert build_translation_history_export_payload({}) == {
        "schema_version": 1,
        "records": [],
    }


def test_history_export_payload_rejects_colliding_nested_dict_keys():
    from cloudhime_ui import build_translation_history_export_payload

    with pytest.raises(TypeError, match="translation_history_not_serializable"):
        build_translation_history_export_payload({("key",): {1: "A", "1": "B"}})

def test_history_export_payload_rejects_unserializable_value():
    from cloudhime_ui import build_translation_history_export_payload

    with pytest.raises(TypeError, match="translation_history_not_serializable"):
        build_translation_history_export_payload({("key",): object()})


def test_history_export_payload_rejects_non_finite_value():
    from cloudhime_ui import build_translation_history_export_payload

    with pytest.raises(TypeError, match="translation_history_not_serializable"):
        build_translation_history_export_payload({("key",): float("nan")})


def test_history_export_write_failure_is_explicit(monkeypatch, tmp_path):
    from cloudhime_ui import write_translation_history_export

    def fail_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", fail_open)

    with pytest.raises(OSError, match="disk full"):
        write_translation_history_export(tmp_path / "history.json", {("key",): "value"})


def test_emit_scan_signal_enqueues_current_generation_before_signal():
    controller = Controller.__new__(Controller)
    controller.scan_in_progress = True
    controller.scan_generation = 3
    calls = []
    controller.worker = SimpleNamespace(
        enqueue_scan_request=lambda generation: calls.append(("enqueue", generation))
    )
    controller.request_scan = SimpleNamespace(
        emit=lambda: calls.append(("emit", None))
    )

    Controller._emit_scan_signal(controller)

    assert calls == [("enqueue", 3), ("emit", None)]


def test_emit_scan_signal_ignores_pending_single_shot_after_stop():
    controller = Controller.__new__(Controller)
    controller.scan_in_progress = False
    controller.scan_generation = 3
    controller.worker = SimpleNamespace(enqueue_scan_request=Mock())
    controller.request_scan = SimpleNamespace(emit=Mock())

    Controller._emit_scan_signal(controller)

    controller.worker.enqueue_scan_request.assert_not_called()
    controller.request_scan.emit.assert_not_called()


def test_controller_rejects_stale_generation_at_render_admission():
    controller = Controller.__new__(Controller)
    controller.scan_generation = 5
    controller.on_scan_complete = Mock()

    controller.scan_in_progress = True
    Controller.on_scan_complete_for_generation(controller, 4, [["stale"]])
    assert controller.scan_in_progress is True
    Controller.on_scan_complete_for_generation(controller, 5, [["current"]])

    controller.on_scan_complete.assert_called_once_with([["current"]])


def test_stop_scan_invalidates_worker_generation_and_clears_overlay():
    controller = Controller.__new__(Controller)
    controller.scan_generation = 8
    controller.scan_in_progress = True
    controller.current_auto_interval = 1000
    controller.auto_timer = Mock()
    controller.display_timer = Mock()
    controller.auto_group = Mock()
    controller.btn_30 = Mock()
    controller.worker = SimpleNamespace(set_scan_generation=Mock())
    controller.overlay = SimpleNamespace(clear_all=Mock())
    controller._set_status_text = Mock()

    Controller.stop_scan(controller)

    assert controller.scan_generation == 9
    controller.worker.set_scan_generation.assert_called_once_with(9)
    assert controller.scan_in_progress is False
    assert controller.current_auto_interval == 0
    controller.overlay.clear_all.assert_called_once()


def test_controller_rejects_stale_stream_chunk_at_render_admission():
    controller = Controller.__new__(Controller)
    controller.scan_generation = 5
    controller.on_translation_stream_update = Mock()

    Controller.on_translation_stream_update_for_generation(
        controller, 4, 0, "stale", "google", 1, 2, 3, 4
    )
    Controller.on_translation_stream_update_for_generation(
        controller, 5, 0, "current", "google", 1, 2, 3, 4
    )

    controller.on_translation_stream_update.assert_called_once_with(
        0, "current", "google", 1, 2, 3, 4
    )


def test_controller_coalesces_stream_updates_until_render_flush(qtbot):
    controller = Controller.__new__(Controller)
    controller.scan_generation = 5
    controller._pending_stream_updates = {}
    controller._stream_render_timer = QTimer()
    controller._stream_render_timer.setSingleShot(True)
    controller._stream_render_timer.setInterval(1000)
    controller.on_translation_stream_update = Mock()

    Controller.on_translation_stream_update_for_generation(
        controller, 5, 0, 'first', 'google', 1, 2, 3, 4
    )
    Controller.on_translation_stream_update_for_generation(
        controller, 5, 0, 'latest', 'google', 1, 2, 3, 4
    )

    controller.on_translation_stream_update.assert_not_called()
    Controller._flush_stream_updates(controller)

    controller.on_translation_stream_update.assert_called_once_with(
        0, 'latest', 'google', 1, 2, 3, 4
    )
    controller._stream_render_timer.deleteLater()


def test_controller_flushes_latest_stream_chunk_before_scan_complete(qtbot):
    controller = Controller.__new__(Controller)
    controller.scan_generation = 5
    controller._pending_stream_updates = {}
    controller._stream_render_timer = QTimer()
    controller._stream_render_timer.setSingleShot(True)
    controller._stream_render_timer.setInterval(1000)
    events = []
    controller.on_translation_stream_update = lambda *args: events.append(('stream', args))
    controller.on_scan_complete = lambda results: events.append(('complete', results))

    Controller.on_translation_stream_update_for_generation(
        controller, 5, 0, 'latest', 'google', 1, 2, 3, 4
    )
    Controller.on_scan_complete_for_generation(controller, 5, [['final']])

    assert [kind for kind, _payload in events] == ['stream', 'complete']
    assert events[0][1][1] == 'latest'
    controller._stream_render_timer.deleteLater()


def test_controller_rejects_stale_status_at_generation_admission():
    controller = Controller.__new__(Controller)
    controller.scan_generation = 5
    controller.update_status = Mock()

    Controller.update_scan_status_for_generation(controller, 4, "stale")
    Controller.update_scan_status_for_generation(controller, 5, "current")

    controller.update_status.assert_called_once_with("current")


def test_emit_scan_signal_rejects_old_timer_after_new_generation_started():
    controller = Controller.__new__(Controller)
    controller.scan_in_progress = True
    controller.scan_generation = 3
    controller.worker = SimpleNamespace(enqueue_scan_request=Mock())
    controller.request_scan = SimpleNamespace(emit=Mock())

    Controller._emit_scan_signal(controller, 2)

    controller.worker.enqueue_scan_request.assert_not_called()
    controller.request_scan.emit.assert_not_called()

def test_generation_invalidation_cancels_active_scan_and_rearms_auto_scan():
    controller = Controller.__new__(Controller)
    controller.scan_generation = 2
    controller.scan_in_progress = True
    controller.current_auto_interval = 1000
    controller.worker = SimpleNamespace(set_scan_generation=Mock())
    controller.schedule_next_scan = Mock()

    generation = Controller._advance_scan_generation(
        controller, cancel_active=True, rearm_auto=True
    )

    assert generation == controller.scan_generation == 3
    assert controller.scan_in_progress is False
    controller.worker.set_scan_generation.assert_called_once_with(3)
    controller.schedule_next_scan.assert_called_once_with()

def test_controller_promotes_knowledge_update_into_existing_pack_id():
    promoted = []
    emitted = []
    saved = {"pack_id": "existing-pack", "revision": 2}

    class Builder:
        def promote(self, result, **kwargs):
            promoted.append(kwargs)
            return saved

    controller = Controller.__new__(Controller)
    controller.knowledge_build_worker = Builder()
    controller.knowledge_build_pack_id = "existing-pack"
    controller.knowledge_build_title = "Princess Synergy"
    controller.knowledge_pack_store = SimpleNamespace(
        get_pack=lambda pack_id, revision: {
            "pack_id": pack_id,
            "revision": revision,
            "title": "Princess Synergy",
        }
    )
    controller.knowledge_build_finished = SimpleNamespace(
        emit=lambda title, pack: emitted.append((title, pack))
    )
    controller._on_knowledge_build_error = Mock()
    result = SimpleNamespace(
        job_id="job",
        research_draft={"title": "Princess Synergy"},
    )

    Controller._on_knowledge_build_finished(controller, result)

    assert promoted == [{"owner_confirmed": True, "pack_id": "existing-pack"}]
    assert emitted[0][1]["revision"] == 2
    controller._on_knowledge_build_error.assert_not_called()


def test_controller_new_knowledge_build_does_not_reuse_unrelated_pack_id():
    promoted = []

    class Builder:
        def promote(self, result, **kwargs):
            promoted.append(kwargs)
            return {"pack_id": "generated", "revision": 1}

    controller = Controller.__new__(Controller)
    controller.knowledge_build_worker = Builder()
    controller.knowledge_build_pack_id = None
    controller.knowledge_build_title = "New Work"
    controller.knowledge_pack_store = SimpleNamespace(get_pack=lambda *_args: None)
    controller.knowledge_build_finished = SimpleNamespace(emit=lambda *_args: None)
    controller._on_knowledge_build_error = Mock()
    result = SimpleNamespace(job_id="job", research_draft={"title": "New Work"})

    Controller._on_knowledge_build_finished(controller, result)

    assert promoted == [{"owner_confirmed": True, "pack_id": None}]
    controller._on_knowledge_build_error.assert_not_called()

def test_loading_new_pack_invalidates_scan_before_runtime_context_change():
    events = []
    old_pack = {"pack_id": "work", "revision": 1, "title": "Work"}
    new_pack = {"pack_id": "work", "revision": 2, "title": "Work"}
    controller = Controller.__new__(Controller)
    controller.active_knowledge_pack = old_pack
    controller.knowledge_pack_store = SimpleNamespace(
        find_pack_for_title=lambda _title: new_pack,
        activate=lambda pack_id, revision: events.append(("activate", pack_id, revision)) or True,
        clear_active=lambda: events.append(("clear",)),
    )
    controller.worker = SimpleNamespace(
        set_knowledge_pack=lambda pack: events.append(("set", pack["revision"]))
    )
    controller.scan_generation = 3
    controller._advance_scan_generation = lambda **kwargs: events.append(("cancel", kwargs))

    loaded = Controller._load_knowledge_pack_for_title(controller, "Work")

    assert loaded == new_pack
    assert events[0] == (
        "cancel",
        {"cancel_active": True, "rearm_auto": True},
    )
    assert events[1] == ("set", 2)
    assert events[2] == ("activate", "work", 2)


def test_failed_runtime_pack_load_clears_worker_context_and_active_catalog():
    events = []
    pack = {"pack_id": "work", "revision": 2, "title": "Work"}
    controller = Controller.__new__(Controller)
    controller.active_knowledge_pack = {"pack_id": "old", "revision": 1}
    controller.knowledge_pack_store = SimpleNamespace(
        find_pack_for_title=lambda _title: pack,
        activate=lambda *_args: events.append(("activate",)),
        clear_active=lambda: events.append(("clear",)),
    )

    def set_knowledge_pack(value):
        events.append(("set", value))
        if value is pack:
            raise RuntimeError("invalid pack")

    controller.worker = SimpleNamespace(set_knowledge_pack=set_knowledge_pack)
    controller.scan_generation = 3
    controller._advance_scan_generation = lambda **_kwargs: None

    loaded = Controller._load_knowledge_pack_for_title(controller, "Work")

    assert loaded is None
    assert controller.active_knowledge_pack is None
    assert events == [("set", pack), ("set", None), ("clear",)]


def test_clearing_work_pack_invalidates_scan_and_clears_active_catalog():
    events = []
    controller = Controller.__new__(Controller)
    controller.active_knowledge_pack = {"pack_id": "work", "revision": 1, "title": "Work"}
    controller.knowledge_pack_store = SimpleNamespace(
        find_pack_for_title=lambda _title: None,
        activate=lambda *_args: False,
        clear_active=lambda: events.append(("clear",)),
    )
    controller.worker = SimpleNamespace(
        set_knowledge_pack=lambda pack: events.append(("set", pack))
    )
    controller.scan_generation = 3
    controller._advance_scan_generation = lambda **kwargs: events.append(("cancel", kwargs))

    Controller._load_knowledge_pack_for_title(controller, "")

    assert events[0][0] == "cancel"
    assert events[1] == ("set", None)
    assert events[2] == ("clear",)


def test_settings_save_failure_rolls_back_work_context_and_stays_open():
    from cloudhime_ui import SettingsWindowRevamp

    calls = []
    controller = SimpleNamespace(active_work_title="Old Work")

    def commit(title):
        calls.append(title)
        controller.active_work_title = title.strip()

    controller.commit_active_work_title = commit
    controller.save_settings = lambda: False
    view = SimpleNamespace(
        controller=controller,
        input_knowledge_title=SimpleNamespace(text=lambda: "New Work"),
        _knowledge_title_dirty=True,
        lbl_knowledge_status=SimpleNamespace(setText=lambda text: calls.append(("status", text))),
        _current_ui_language=lambda: "en",
        hide=Mock(),
    )

    SettingsWindowRevamp.on_save_clicked(view)

    assert calls[:2] == ["New Work", "Old Work"]
    assert calls[2] == ("status", "Settings could not be saved")
    assert view._knowledge_title_dirty is True
    view.hide.assert_not_called()


def test_settings_save_success_commits_work_context_and_closes():
    from cloudhime_ui import SettingsWindowRevamp

    calls = []
    controller = SimpleNamespace(
        active_work_title="Old Work",
        commit_active_work_title=lambda title: calls.append(title),
        save_settings=lambda: True,
    )
    view = SimpleNamespace(
        controller=controller,
        input_knowledge_title=SimpleNamespace(text=lambda: "New Work"),
        _knowledge_title_dirty=True,
        hide=Mock(),
    )

    SettingsWindowRevamp.on_save_clicked(view)

    assert calls == ["New Work"]
    assert view._knowledge_title_dirty is False
    view.hide.assert_called_once_with()

def test_editing_work_title_only_refreshes_local_status_without_research():
    from cloudhime_ui import SettingsWindowRevamp

    research = Mock()
    view = SimpleNamespace(
        controller=SimpleNamespace(start_knowledge_research=research),
        _knowledge_is_building=lambda: False,
        _knowledge_title_dirty=False,
        _refresh_knowledge_status=Mock(),
    )

    SettingsWindowRevamp.on_knowledge_title_changed(view, "Princess Synergy")

    assert view._knowledge_title_dirty is True
    view._refresh_knowledge_status.assert_called_once_with()
    research.assert_not_called()


def test_explicit_research_remembers_existing_local_pack_id(monkeypatch):
    import cloudhime_ui

    created = []

    class Service:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def build_research_draft(self, *_args):
            raise AssertionError("background work is owned by the builder")

        def extract_candidate(self, *_args):
            raise AssertionError("background work is owned by the builder")

    class Builder:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created.append(self)

        def is_running(self):
            return False

        def start(self):
            return "job"

    monkeypatch.setattr(cloudhime_ui, "KnowledgeResearchService", Service)
    monkeypatch.setattr(cloudhime_ui, "KnowledgeBuildWorker", Builder)
    controller = Controller.__new__(Controller)
    controller.worker = SimpleNamespace(google_api_key="key")
    controller.knowledge_build_worker = None
    controller.knowledge_pack_store = object()
    controller.find_knowledge_pack = lambda title: {
        "pack_id": "existing-pack",
        "revision": 3,
        "title": title,
    }
    controller.knowledge_build_progress = SimpleNamespace(emit=lambda *_args: None)
    controller.knowledge_build_finished = SimpleNamespace(emit=lambda *_args: None)
    controller.knowledge_build_error = SimpleNamespace(emit=lambda *_args: None)
    controller.knowledge_build_cancelled = SimpleNamespace(emit=lambda *_args: None)

    assert Controller.start_knowledge_research(controller, " Princess   Synergy ") is True

    assert controller.knowledge_build_title == "Princess Synergy"
    assert controller.knowledge_build_pack_id == "existing-pack"
    assert len(created) == 1


def test_controller_ignores_stale_remote_model_availability_result(qtbot):
    from PySide6.QtWidgets import QComboBox
    from remote_model_discovery import DISCOVERY_STATUS_VERIFIED, ModelDiscoveryResult

    controller = Controller.__new__(Controller)
    controller._remote_model_availability_generation = 2
    controller.remote_model_availability = ModelDiscoveryResult(
        status="no_key",
        error_code="no_key",
    )
    controller.worker = SimpleNamespace(gemma_model="gemini-2.5-pro")
    controller.cmb_ai_model = QComboBox()
    controller.cmb_ai_model.addItem("Gemini", "gemini-2.5-pro")
    controller.settings_window = None

    stale = ModelDiscoveryResult(
        status=DISCOVERY_STATUS_VERIFIED,
        available_model_ids=("gemma-4-31b-it",),
        verified=True,
    )
    Controller.on_remote_model_availability_finished(controller, 1, stale)

    assert controller.remote_model_availability.error_code == "no_key"
    assert controller.cmb_ai_model.currentData() == "gemini-2.5-pro"


def test_controller_applies_availability_without_switching_worker_model(qtbot):
    from PySide6.QtWidgets import QComboBox
    from remote_model_discovery import DISCOVERY_STATUS_VERIFIED, ModelDiscoveryResult

    controller = Controller.__new__(Controller)
    controller._remote_model_availability_generation = 2
    controller.remote_model_availability = ModelDiscoveryResult(
        status="no_key",
        error_code="no_key",
    )
    controller.worker = SimpleNamespace(gemma_model="gemini-2.5-pro")
    controller.cmb_ai_model = QComboBox()
    controller.cmb_ai_model.addItem("Gemini Pro", "gemini-2.5-pro")
    controller.settings_window = None

    result = ModelDiscoveryResult(
        status=DISCOVERY_STATUS_VERIFIED,
        available_model_ids=("gemma-4-31b-it",),
        verified=True,
    )
    Controller.on_remote_model_availability_finished(controller, 2, result)

    ids = [controller.cmb_ai_model.itemData(i) for i in range(controller.cmb_ai_model.count())]
    assert "gemma-4-31b-it" in ids
    assert "gemini-2.5-pro" in ids
    assert controller.cmb_ai_model.currentData() == "gemini-2.5-pro"
    assert controller.worker.gemma_model == "gemini-2.5-pro"


def test_controller_without_api_key_does_not_emit_remote_refresh(qtbot):
    from PySide6.QtWidgets import QComboBox
    from remote_model_discovery import DISCOVERY_STATUS_NO_KEY

    controller = Controller.__new__(Controller)
    controller._remote_model_availability_generation = 0
    controller.remote_model_availability = None
    controller.worker = SimpleNamespace(
        google_api_key="",
        gemma_model="gemma-3-4b-it-local",
    )
    controller.cmb_ai_model = QComboBox()
    controller.cmb_ai_model.addItem("Local", "gemma-3-4b-it-local")
    controller.settings_window = None
    controller.remote_model_availability_thread = None

    assert Controller.refresh_remote_model_availability(controller) is False
    assert controller.remote_model_availability.status == DISCOVERY_STATUS_NO_KEY
