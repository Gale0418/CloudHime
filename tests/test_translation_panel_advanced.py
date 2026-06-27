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

    qtbot.mouseClick(panel.btn_advanced_tuning, Qt.LeftButton)
    assert not panel.tuning_frame.isHidden()

    assert panel.lbl_translate_summary.text() != ""
    assert "AI" in panel.lbl_translate_summary.text()
