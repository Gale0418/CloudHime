from types import SimpleNamespace

from CloudHime import Controller, OverlayWindow
from cloudhime_ui import StatusChargeBar


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

    Controller.on_local_model_status(controller, "loading", "")

    assert controller.local_model_state == "loading"
    assert controller.charge_bar.indeterminate is True
    assert "Local Gemma3" in controller.charge_bar.label
    assert messages


def test_controller_local_vision_states_update_ui(qtbot):
    controller = Controller.__new__(Controller)
    controller.ui_language = "zh-TW"
    controller.theme_mode = "light"
    controller.charge_bar = StatusChargeBar()
    qtbot.addWidget(controller.charge_bar)
    messages = []
    controller.lbl_status = SimpleNamespace(setText=lambda text: messages.append(text))

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
def test_api_key_is_persisted_beside_appdata_settings(monkeypatch, tmp_path):
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

    env_path = tmp_path / "CloudHime" / ".env"
    monkeypatch.setattr(cloudhime_ui, "APPDATA_ENV_PATH", str(env_path))

    controller = Controller.__new__(Controller)
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

    assert env_path.read_text(encoding="utf-8") == f"{cloudhime_ui.API_KEY_ENV_VAR}=secret-key\n"
    assert controller.worker.google_api_key == "secret-key"

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