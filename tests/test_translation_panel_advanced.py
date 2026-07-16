from PySide6.QtCore import Qt
from translation_settings_panel import TranslationSettingsPanel


class DummyWorker:
    google_api_key = ""
    use_gemma_translation = True
    gemma_auto_switch_enabled = False


class DummyController:
    worker = DummyWorker()
    is_dark_mode = False
    gemma_prompt = "test prompt"
    local_gemma_temperature = 0.2
    local_gemma_repeat_penalty = 1.15
    local_multimodal_enabled = True
    local_multimodal_base_url = "http://127.0.0.1:8080/v1"
    local_multimodal_model = "translategemma-4b-it-local"
    local_multimodal_timeout_seconds = 20

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

