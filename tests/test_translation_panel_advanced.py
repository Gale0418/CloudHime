from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt

from translation_settings_panel import TranslationSettingsPanel

class DummyWorker:
    google_api_key = ""
    use_gemma_translation = True
    gemma_auto_switch_enabled = False


class DummyController:
    is_dark_mode = False
    gemma_prompt = "test prompt"
    local_gemma_temperature = 0.2
    local_gemma_repeat_penalty = 1.15
    local_multimodal_enabled = True
    local_multimodal_base_url = "http://127.0.0.1:8080/v1"
    local_multimodal_model = "translategemma-4b-it-local"
    local_multimodal_timeout_seconds = 20

    def __init__(self):
        self.worker = DummyWorker()

    class cmb_ai_model:
        @staticmethod
        def currentIndex():
            return 0

    def toggle_ai_translation(self, val):
        pass

    def on_api_key_changed(self, val):
        pass

    def on_ai_model_changed(self, idx):
        pass

    def set_gemma_auto_switch_mode(self, val):
        pass

    def on_local_gemma_temp_changed(self, value):
        self.local_gemma_temperature = value

    def on_local_gemma_repeat_changed(self, value):
        self.local_gemma_repeat_penalty = value

    def on_local_multimodal_enabled_changed(self, value):
        self.local_multimodal_enabled = value

    def on_local_multimodal_base_url_changed(self, value):
        self.local_multimodal_base_url = value

    def on_local_multimodal_model_changed(self, value):
        self.local_multimodal_model = value

    def on_local_multimodal_timeout_changed(self, value):
        self.local_multimodal_timeout_seconds = value

    def get_default_gemma_prompt(self):
        return "default prompt"


def test_translation_panel_advanced_tuning_hidden(qtbot):
    controller = DummyController()
    panel = TranslationSettingsPanel(controller, supported_ai_models=[("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    panel.show()

    panel.sync_from_controller()
    panel.set_translate_mode(True)

    assert not panel.btn_advanced_tuning.isHidden()
    assert panel.tuning_frame.isHidden()
    assert not panel.lbl_gemma_prompt.isHidden()
    assert not panel.input_gemma_prompt.isHidden()
    assert panel.lbl_translate_summary.parentWidget() is not None
    assert not panel.lbl_translate_summary.isWindow()

    qtbot.mouseClick(panel.btn_advanced_tuning, Qt.LeftButton)
    assert not panel.tuning_frame.isHidden()

    assert panel.lbl_translate_summary.text() != ""
    assert "AI" in panel.lbl_translate_summary.text()


def test_translation_panel_local_multimodal_controls_sync(qtbot):
    controller = DummyController()
    panel = TranslationSettingsPanel(controller, supported_ai_models=[("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)

    panel.sync_from_controller()

    assert panel.chk_local_multimodal_enabled.isChecked()
    assert panel.input_local_multimodal_base_url.text() == "http://127.0.0.1:8080/v1"
    assert panel.input_local_multimodal_model.text() == "translategemma-4b-it-local"
    assert panel.spin_local_multimodal_timeout.value() == 20

    panel.chk_local_multimodal_enabled.setChecked(False)
    panel.input_local_multimodal_base_url.setText("http://localhost:11434/v1")
    panel.input_local_multimodal_model.setText("vision-local")
    panel.spin_local_multimodal_timeout.setValue(45)

    assert controller.local_multimodal_enabled is False
    assert controller.local_multimodal_base_url == "http://127.0.0.1:8080/v1"
    assert controller.local_multimodal_model == "translategemma-4b-it-local"

    panel.input_local_multimodal_base_url.editingFinished.emit()
    panel.input_local_multimodal_model.editingFinished.emit()

    assert controller.local_multimodal_base_url == "http://localhost:11434/v1"
    assert controller.local_multimodal_model == "vision-local"
    assert controller.local_multimodal_timeout_seconds == 45


def test_translation_panel_embedded_hides_base_url_and_model(qtbot):
    controller = DummyController()
    # Simulate embedded runtime present
    controller.worker.local_vision_runtime = object()

    panel = TranslationSettingsPanel(controller, supported_ai_models=[("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    panel.show()
    panel.sync_from_controller()

    # Assert fields are hidden
    assert panel.lbl_local_multimodal_base_url.isHidden()
    assert panel.input_local_multimodal_base_url.isHidden()
    assert panel.lbl_local_multimodal_model.isHidden()
    assert panel.input_local_multimodal_model.isHidden()

    # Timeout and enabled checkbox should still be visible
    assert not panel.chk_local_multimodal_enabled.isHidden()
    assert not panel.spin_local_multimodal_timeout.isHidden()

def _health_controller(*, model_id, ai_enabled, local_multimodal=False, runtime_state=None):
    controller = DummyController()
    controller.ui_language = "en"
    controller.local_model_state = "stopped"
    controller.local_model_detail = ""
    controller.local_vision_state = getattr(runtime_state, "name", "stopped")
    controller.local_vision_detail = getattr(runtime_state, "detail", "")
    controller.local_multimodal_enabled = local_multimodal
    runtime = SimpleNamespace(_state=runtime_state) if runtime_state is not None else None
    controller.worker = SimpleNamespace(
        google_api_key="",
        use_gemma_translation=ai_enabled,
        gemma_auto_switch_enabled=False,
        gemma_model=model_id,
        local_vision_runtime=runtime,
        local_gemma_provider=SimpleNamespace(available=lambda: False),
        _local_vision_assets=SimpleNamespace(
            model_path=Path("__cloudhime_missing_model__.gguf"),
            projector_path=Path("__cloudhime_missing_projector__.gguf"),
        ),
    )
    controller.cmb_ai_model = SimpleNamespace(currentIndex=lambda: 0)
    return controller


def test_translation_panel_preserves_remote_ai_intent_when_key_is_missing(qtbot):
    controller = _health_controller(
        model_id="gemma-3-27b-it",
        ai_enabled=False,
    )
    panel = TranslationSettingsPanel(controller, [("Gemma Remote", "gemma-3-27b-it")])
    qtbot.addWidget(panel)
    panel._ai_requested = True
    panel.btn_translate_google.setChecked(True)

    panel.update_translate_summary()
    health = panel._provider_health()

    assert health.code == "remote_key_required"
    assert "Google API key" in panel.lbl_translate_health_detail.text()
    assert panel.lbl_translate_health_detail.parentWidget() is not None
    assert not panel.lbl_translate_health_detail.isWindow()


def test_translation_panel_local_model_needs_no_key_and_shows_managed_download(qtbot):
    state = SimpleNamespace(name="stopped", detail="", mode="")
    controller = _health_controller(
        model_id="gemma-3-4b-it-local",
        ai_enabled=True,
        local_multimodal=True,
        runtime_state=state,
    )
    panel = TranslationSettingsPanel(controller, [("Gemma Local", "gemma-3-4b-it-local")])
    qtbot.addWidget(panel)
    panel.show()
    panel.sync_from_controller()

    panel.set_translate_mode(True)
    health = panel._provider_health()

    assert health.code == "local_download_required"
    assert "Ollama" in panel.lbl_translate_health_detail.text()
    assert not panel.input_api_key.hasFocus()


def test_translation_panel_reports_cpu_ready_as_slow_but_available(qtbot):
    state = SimpleNamespace(name="ready", detail="", mode="cpu")
    controller = _health_controller(
        model_id="gemma-3-4b-it-local",
        ai_enabled=True,
        local_multimodal=True,
        runtime_state=state,
    )
    controller.local_vision_state = "ready"
    panel = TranslationSettingsPanel(controller, [("Gemma Local", "gemma-3-4b-it-local")])
    qtbot.addWidget(panel)
    panel.sync_from_controller()

    health = panel._provider_health()

    assert health.code == "local_ready_cpu"
    assert "slower" in panel.lbl_translate_health_detail.text()

def test_translation_panel_switching_requested_remote_ai_to_local_enables_it(qtbot):
    controller = _health_controller(
        model_id="gemma-3-27b-it",
        ai_enabled=False,
    )
    toggle_calls = []
    controller.toggle_ai_translation = lambda enabled: toggle_calls.append(enabled)
    panel = TranslationSettingsPanel(
        controller,
        [
            ("Gemma Remote", "gemma-3-27b-it"),
            ("Gemma Local", "gemma-3-4b-it-local"),
        ],
    )
    qtbot.addWidget(panel)
    panel._ai_requested = True

    panel.cmb_ai_model.setCurrentIndex(1)

    assert toggle_calls == [True]

def test_translation_health_text_does_not_force_compact_panel_wider(qtbot):
    controller = _health_controller(
        model_id="gemma-3-4b-it-local",
        ai_enabled=True,
        local_multimodal=True,
        runtime_state=SimpleNamespace(name="progress", detail="40|downloading", mode=""),
    )
    controller.local_vision_state = "progress"
    controller.local_vision_detail = "40|downloading"
    panel = TranslationSettingsPanel(controller, [("Gemma 3 4B (Local)", "gemma-3-4b-it-local")])
    qtbot.addWidget(panel)
    panel.resize(430, 720)
    panel.sync_from_controller()
    panel.show()
    qtbot.wait(20)

    assert panel.width() <= 430
    assert panel.lbl_translate_health_detail.width() <= panel.width()
    assert not panel.lbl_translate_health_detail.geometry().intersects(panel.lbl_translate_mode.geometry())


def test_translation_panel_model_refresh_is_explicit_only(qtbot):
    controller = DummyController()
    refresh_calls = []
    controller.refresh_remote_model_availability = lambda: refresh_calls.append(True)
    panel = TranslationSettingsPanel(
        controller,
        [
            ("Local", "gemma-3-4b-it-local"),
            ("Remote", "gemma-4-31b-it"),
        ],
    )
    qtbot.addWidget(panel)
    panel.sync_from_controller()

    panel.input_api_key.setText("new-key")
    panel.cmb_ai_model.setCurrentIndex(1)
    panel.sync_from_controller()

    assert refresh_calls == []
    qtbot.mouseClick(panel.btn_refresh_model_availability, Qt.LeftButton)
    assert refresh_calls == [True]


def test_translation_panel_availability_keeps_selected_unavailable_model(qtbot):
    from remote_model_discovery import DISCOVERY_STATUS_VERIFIED, ModelDiscoveryResult

    controller = DummyController()
    panel = TranslationSettingsPanel(
        controller,
        [
            ("Local", "gemma-3-4b-it-local"),
            ("Available", "gemma-4-31b-it"),
            ("Unavailable", "gemini-2.5-pro"),
        ],
    )
    qtbot.addWidget(panel)
    panel.cmb_ai_model.setCurrentIndex(2)

    panel.set_model_availability_result(
        ModelDiscoveryResult(
            status=DISCOVERY_STATUS_VERIFIED,
            available_model_ids=("gemma-4-31b-it",),
            verified=True,
        )
    )

    ids = [panel.cmb_ai_model.itemData(i) for i in range(panel.cmb_ai_model.count())]
    assert ids == [
        "gemma-3-4b-it-local",
        "gemma-4-31b-it",
        "gemini-2.5-pro",
    ]
    assert panel.cmb_ai_model.currentData() == "gemini-2.5-pro"


def test_removed_text_only_model_has_no_translation_panel_note():
    panel = TranslationSettingsPanel.__new__(TranslationSettingsPanel)
    panel.controller = SimpleNamespace(ui_language="en")

    assert panel._ai_model_note_text("gemma-3-1b-it") == ""