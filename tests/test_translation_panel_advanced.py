from pathlib import Path
from types import SimpleNamespace
import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QSizePolicy

from translation_settings_panel import TranslationSettingsPanel
from themes import resolve_theme

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


def test_pending_provider_selection_survives_panel_sync(qtbot):
    controller = DummyController()
    controller.provider_chain = ("google",)
    controller.pending_translation_provider_id = "luna"
    panel = TranslationSettingsPanel(controller, [("Local", "gemma-3-4b-it-local")])
    qtbot.addWidget(panel)

    panel.sync_from_controller()

    assert panel.provider_choice_buttons["luna"].isChecked()


def test_inactive_ai_route_displays_google_as_active_provider(qtbot):
    controller = DummyController()
    controller.provider_chain = ("openai",)
    controller.worker.use_gemma_translation = False
    panel = TranslationSettingsPanel(controller, [("Local", "gemma-3-4b-it-local")])
    qtbot.addWidget(panel)

    panel.sync_from_controller()

    assert panel.provider_choice_buttons["google"].isChecked()


def test_explicit_local_selection_from_remote_without_key(qtbot):
    controller = DummyController()
    controller.worker.gemma_model = "gemma-4-31b-it"
    controller.worker.use_gemma_translation = False
    controller.worker.google_api_key = ""
    selected = [0]
    controller.cmb_ai_model = SimpleNamespace(currentIndex=lambda: selected[0])
    models = [("Remote", "gemma-4-31b-it"), ("Local", "gemma-3-4b-it-local")]
    def select(index):
        selected[0] = index
        controller.worker.gemma_model = models[index][1]
    controller.on_ai_model_changed = select
    controller.toggle_ai_translation = lambda value: setattr(
        controller.worker, "use_gemma_translation", value
    )
    panel = TranslationSettingsPanel(controller, models)
    qtbot.addWidget(panel)
    panel.btn_use_local_gemma.click()
    assert selected[0] == 1
    assert controller.worker.use_gemma_translation
    assert panel.btn_translate_ai.isChecked()
    assert panel.provider_disclosures["local_gemma"].header.isChecked()
    assert not controller.worker.google_api_key


def test_explicit_local_selection_maps_model_id_when_combos_have_different_order(qtbot):
    controller = DummyController()
    controller.worker.gemma_model = "gemma-4-31b-it"
    controller.worker.use_gemma_translation = False
    controller.worker.google_api_key = ""
    controller.cmb_ai_model = QComboBox()
    controller.cmb_ai_model.addItem("Local", "gemma-3-4b-it-local")
    controller.cmb_ai_model.addItem("Remote", "gemma-4-31b-it")
    controller.cmb_ai_model.setCurrentIndex(1)

    def select(index):
        controller.cmb_ai_model.setCurrentIndex(index)
        controller.worker.gemma_model = controller.cmb_ai_model.itemData(index)

    controller.on_ai_model_changed = select
    controller.toggle_ai_translation = lambda value: setattr(
        controller.worker, "use_gemma_translation", value
    )
    panel = TranslationSettingsPanel(
        controller,
        [("Remote", "gemma-4-31b-it"), ("Local", "gemma-3-4b-it-local")],
    )
    qtbot.addWidget(panel)
    panel.cmb_ai_model.setCurrentIndex(0)

    panel.btn_use_local_gemma.click()

    assert controller.worker.gemma_model == "gemma-3-4b-it-local"
    assert controller.worker.use_gemma_translation
    assert panel.btn_translate_ai.isChecked()


def test_local_status_never_inherits_remote_key_requirement(qtbot):
    controller = DummyController()
    controller.worker.gemma_model = "gemma-4-31b-it"
    panel = TranslationSettingsPanel(controller, [("Remote", "gemma-4-31b-it")])
    qtbot.addWidget(panel)
    panel._ai_requested = True
    panel.update_provider_status_rows()
    assert panel._provider_health().code == "remote_key_required"
    assert panel._provider_health(local_only=True).code != "remote_key_required"
    assert not panel.btn_use_local_gemma.isEnabled()


def test_translation_panel_advanced_tuning_hidden(qtbot):
    controller = DummyController()
    panel = TranslationSettingsPanel(controller, supported_ai_models=[("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    panel.show()

    panel.sync_from_controller()
    panel.set_translate_mode(True)

    assert not hasattr(panel, "chk_japanese_ocr_rescue_enabled")

    assert not panel.btn_advanced_tuning.isHidden()
    assert panel.tuning_frame.isHidden()
    assert panel.lbl_gemma_prompt.isHidden()
    assert panel.input_gemma_prompt.isHidden()
    assert panel.lbl_translate_summary.parentWidget() is not None
    assert not panel.lbl_translate_summary.isWindow()

    qtbot.mouseClick(panel.btn_advanced_tuning, Qt.LeftButton)
    assert not panel.tuning_frame.isHidden()
    assert not panel.lbl_gemma_prompt.isHidden()
    assert not panel.input_gemma_prompt.isHidden()

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


def test_translation_panel_local_model_discloses_appdata_and_gemma_terms(qtbot):
    controller = _health_controller(model_id="gemma-3-4b-it-local", ai_enabled=True)
    panel = TranslationSettingsPanel(controller, [("Gemma Local", "gemma-3-4b-it-local")])
    qtbot.addWidget(panel)
    panel.sync_from_controller()
    panel.update_ai_model_notes()

    assert "AppData" in panel.lbl_ai_model_notes.text()
    assert "https://ai.google.dev/gemma/terms" in panel.lbl_ai_model_notes.text()
    assert panel.lbl_ai_model_notes.openExternalLinks()


def test_translation_panel_model_note_wraps_without_clipping_terms_link(qtbot):
    controller = _health_controller(model_id="gemma-3-4b-it-local", ai_enabled=True)
    panel = TranslationSettingsPanel(controller, [("Gemma Local", "gemma-3-4b-it-local")])
    qtbot.addWidget(panel)
    panel.show()
    panel.sync_from_controller()

    # Exercise the narrow-card geometry that wraps the rich-text terms link
    # onto multiple lines instead of relying on the panel's default width.
    notes = panel.lbl_ai_model_notes
    notes.setMaximumWidth(220)
    panel._advanced_layout.activate()
    qtbot.wait(10)

    assert notes.heightForWidth(notes.width()) <= notes.height()
    assert notes.maximumHeight() >= notes.heightForWidth(notes.width())
    assert "Gemma Terms of Use" in notes.text()


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


def test_provider_settings_expose_redacted_config_and_accessible_controls(qtbot):
    controller = DummyController()
    controller.online_gemma_enabled = True
    controller.google_api_key = "primary-secret"
    controller.openai_enabled = True
    controller.openai_reasoning_effort = "none"
    controller.openai_timeout_seconds = 75

    panel = TranslationSettingsPanel(controller, [("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)

    assert panel.input_google_api_key.echoMode() != 0
    assert panel.input_google_api_key.accessibleName()
    assert panel.input_google_api_key.accessibleDescription()
    assert panel.input_luna_api_key.echoMode() != 0
    assert panel.lbl_luna_model.text() == "gpt-6-luna"
    assert panel.cmb_luna_reasoning.currentData() == "none"
    assert panel.spin_luna_timeout.value() == 75
    assert panel.btn_api_key_visible.minimumWidth() >= 56
    assert panel.btn_api_key_visible.height() == 34
    assert panel.input_api_key.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding

    config = panel.get_provider_config()
    assert config["online_gemma"]["enabled"] is True
    assert config["online_gemma"]["models"] == ("gemma-4-26b-a4b-it", "gemma-4-31b-it")
    assert "primary-secret" not in repr(config)
    assert "secondary-secret" not in repr(config)
    assert "api_key" not in config["luna"]


def test_provider_metadata_uses_theme_contrast_token(qtbot):
    panel = TranslationSettingsPanel(DummyController(), [("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    for mode in ("light", "dark", "high_contrast"):
        theme = resolve_theme(mode)
        panel.update_theme(mode)
        capability_style = panel.provider_status_frame.styleSheet()
        detail_style = panel.provider_status_rows["online_gemma"]["detail"].styleSheet()
        assert theme.provider_metadata in capability_style
        assert theme.provider_metadata in detail_style


def test_provider_settings_metadata_and_luna_changes_use_optional_controller_callbacks(qtbot):
    controller = DummyController()
    calls = []
    controller.on_api_key_changed = lambda value: calls.append(("google_api_key", value))
    controller.on_luna_enabled_changed = lambda value: calls.append(("luna_enabled", value))
    controller.on_luna_reasoning_changed = lambda value: calls.append(("luna_reasoning", value))
    controller.on_luna_timeout_changed = lambda value: calls.append(("luna_timeout", value))

    panel = TranslationSettingsPanel(controller, [("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    panel.input_google_api_key.setText("secret-a")
    panel.chk_luna_enabled.setChecked(True)
    panel.spin_luna_timeout.setValue(90)

    assert ("google_api_key", "secret-a") in calls
    assert ("luna_enabled", True) in calls
    assert ("luna_timeout", 90) in calls


def test_provider_status_rows_do_not_claim_remaining_quota(qtbot):
    panel = TranslationSettingsPanel(DummyController(), [("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)

    status_text = " ".join(
        row["status"].text() + " " + row["detail"].text()
        for row in panel.provider_status_rows.values()
    )
    assert "quota remaining" not in status_text.lower()
    assert "剩餘額度" not in status_text
    assert panel.provider_status_rows["local_gemma"]["status"].text()


def test_online_gemma_rows_separate_rate_and_cooldown_state(qtbot):
    controller = DummyController()
    controller.ui_language = "en"
    controller.worker.gemma_runtime_snapshot = lambda: [
        {"model": "gemma-4-26b-a4b-it", "status": "cooldown"},
        {"model": "gemma-4-31b-it", "status": "using"},
    ]
    panel = TranslationSettingsPanel(controller, [("Gemma 4 31B", "gemma-4-31b-it")])
    qtbot.addWidget(panel)

    panel.update_provider_status_rows()

    model_26 = panel.online_gemma_model_rows["gemma-4-26b-a4b-it"]
    model_31 = panel.online_gemma_model_rows["gemma-4-31b-it"]
    assert model_26["status"].text() == "Cooldown"
    assert model_26["detail"].text() == "Rate: Limited · Cooldown: Active"
    assert model_31["status"].text() == "Using"
    assert model_31["detail"].text() == "Rate: Active · Cooldown: None"


def test_provider_status_tones_preserve_semantic_colors(qtbot):
    controller = DummyController()
    controller.ui_language = "en"
    panel = TranslationSettingsPanel(controller, [("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    panel.update_theme("light")
    theme = resolve_theme("light")

    panel._set_provider_row("online_gemma", "Ready", "", "")
    ready = panel.provider_status_rows["online_gemma"]["status"]
    assert ready.property("statusTone") == "operational"
    assert f'QLabel[statusTone="operational"] {{ color: {theme.operational}; }}' in ready.styleSheet()

    panel._set_provider_row("online_gemma", "Cooldown", "", "")
    cooldown = panel.provider_status_rows["online_gemma"]["status"]
    assert cooldown.property("statusTone") == "quota"
    assert f'QLabel[statusTone="quota"] {{ color: {theme.quota}; }}' in cooldown.styleSheet()

    panel._set_provider_row("online_gemma", "Authentication failed", "", "")
    failed = panel.provider_status_rows["online_gemma"]["status"]
    assert failed.property("statusTone") == "error"
    assert f'QLabel[statusTone="error"] {{ color: {theme.error}; }}' in failed.styleSheet()


def test_model_status_tones_follow_ready_cooldown_and_using_rows(qtbot):
    controller = DummyController()
    controller.ui_language = "en"
    controller.worker.gemma_runtime_snapshot = lambda: [
        {"model": "gemma-4-26b-a4b-it", "status": "cooldown"},
        {"model": "gemma-4-31b-it", "status": "ready"},
    ]
    panel = TranslationSettingsPanel(controller, [("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    panel.update_theme("dark")
    panel.update_provider_status_rows()

    cooldown = panel.online_gemma_model_rows["gemma-4-26b-a4b-it"]["status"]
    ready = panel.online_gemma_model_rows["gemma-4-31b-it"]["status"]
    assert cooldown.property("statusTone") == "quota"
    assert ready.property("statusTone") == "operational"


def test_provider_disclosures_are_keyboard_checkable_and_preserve_state(qtbot):
    controller = DummyController()
    panel = TranslationSettingsPanel(controller, [("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    panel.show()
    panel.resize(500, 900)
    qtbot.wait(1)

    assert set(panel.provider_disclosures) == {"local_gemma", "online_gemma", "luna"}
    assert all(not item.body.isVisible() for item in panel.provider_disclosures.values())
    panel._set_provider_choice("online_gemma")
    online = panel.provider_disclosures["online_gemma"]
    assert online.isVisible()
    assert not panel.provider_disclosures["local_gemma"].isVisible()
    assert not panel.provider_disclosures["luna"].isVisible()
    online.header.setFocus()
    qtbot.keyClick(online.header, Qt.Key_Space)
    assert online.header.isChecked() is True
    assert online.body.isVisible() is True
    assert "\n" not in online.header.text()
    assert online.capability_label.isVisible() is True
    assert online.capability_label.wordWrap() is True
    assert online.capability_label.minimumWidth() == 0
    assert online.capability_label.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored
    assert online.capability_label.text()
    assert panel.input_google_api_key is panel.input_api_key is panel.input_gemma_api_key
    assert panel.online_gemma_model_rows["gemma-4-26b-a4b-it"]["row"].height() > 0
    assert panel.online_gemma_model_rows["gemma-4-31b-it"]["row"].height() > 0

    panel.input_api_key.setFocus()
    qtbot.mouseClick(online.header, Qt.LeftButton)
    assert online.header.isChecked() is False
    assert online.body.isVisible() is False
    assert online.header.hasFocus()
    before = [item.header.isChecked() for item in panel.provider_disclosures.values()]
    panel.update_provider_status_rows()
    assert [item.header.isChecked() for item in panel.provider_disclosures.values()] == before
    assert "secret" not in online.header.accessibleName().lower()
    assert "api" not in online.header.accessibleDescription().lower()


def test_provider_summary_and_translation_hint_wrap_in_narrow_column(qtbot):
    panel = TranslationSettingsPanel(DummyController(), [("Gemma Test", "gemma-test")])
    qtbot.addWidget(panel)
    panel.resize(337, 720)
    panel.show()
    panel.lbl_translate_hint.setText(
        "This is a deliberately long translation hint that must wrap naturally "
        "without horizontal clipping in the legacy three-column card."
    )
    long_capability = (
        "Supports screenshot translation, local fallback, model health and "
        "request-time connectivity checks without exposing credentials."
    )
    for disclosure in panel.provider_disclosures.values():
        disclosure.set_summary("Needs setup", long_capability)
    panel._set_provider_choice("online_gemma")
    qtbot.wait(10)

    viewport_width = panel.translation_scroll_area.viewport().width()
    assert panel.translation_content.width() <= viewport_width
    assert panel.lbl_translate_hint.width() <= viewport_width
    assert panel.lbl_translate_hint.heightForWidth(panel.lbl_translate_hint.width()) <= panel.lbl_translate_hint.height()
    visible_disclosures = [
        disclosure
        for disclosure in panel.provider_disclosures.values()
        if disclosure.isVisible()
    ]
    assert visible_disclosures == [panel.provider_disclosures["online_gemma"]]
    for disclosure in visible_disclosures:
        assert "\n" not in disclosure.header.text()
        assert disclosure.capability_label.width() <= viewport_width
        assert disclosure.capability_label.heightForWidth(disclosure.capability_label.width()) <= disclosure.capability_label.height()


def test_provider_choice_rows_are_exclusive_and_local_needs_no_key(qtbot):
    controller = DummyController()
    controller.worker.google_api_key = ""
    controller.worker.gemma_model = "gemma-4-31b-it"
    controller.worker.use_gemma_translation = False
    models = [
        ("Remote", "gemma-4-31b-it"),
        ("Local", "gemma-3-4b-it-local"),
    ]
    selected = []
    controller.cmb_ai_model = SimpleNamespace(currentIndex=lambda: 0)
    controller.on_ai_model_changed = lambda index: (
        selected.append(index),
        setattr(controller.worker, "gemma_model", models[index][1]),
    )
    controller.toggle_ai_translation = lambda enabled: setattr(
        controller.worker, "use_gemma_translation", bool(enabled)
    )

    panel = TranslationSettingsPanel(controller, models)
    qtbot.addWidget(panel)

    assert tuple(panel.provider_choice_buttons) == (
        "google",
        "local_gemma",
        "online_gemma",
        "luna",
    )
    assert sum(button.isChecked() for button in panel.provider_choice_buttons.values()) == 1

    panel.provider_choice_buttons["local_gemma"].click()

    assert panel.provider_choice_buttons["local_gemma"].isChecked()
    assert not panel.provider_choice_buttons["google"].isChecked()
    assert sum(button.isChecked() for button in panel.provider_choice_buttons.values()) == 1
    assert controller.worker.gemma_model == "gemma-3-4b-it-local"
    assert controller.worker.use_gemma_translation is True
    assert not controller.worker.google_api_key


def test_provider_choice_remote_gate_stays_selected_and_opens_key_field(qtbot):
    controller = DummyController()
    controller.worker.gemma_model = "gemma-4-31b-it"
    controller.worker.use_gemma_translation = False
    panel = TranslationSettingsPanel(controller, [("Remote", "gemma-4-31b-it")])
    qtbot.addWidget(panel)
    panel.show()

    panel.provider_choice_buttons["online_gemma"].click()
    qtbot.wait(10)

    assert panel.provider_choice_buttons["online_gemma"].isChecked()
    assert panel._selected_provider_id == "online_gemma"
    assert panel.provider_disclosures["online_gemma"].body.isVisible()
    assert panel.input_api_key.isVisible()
    assert panel.input_api_key.isEnabled()
    assert panel.input_api_key.hasFocus()
    assert "API key" in panel.lbl_translate_health_detail.text()
    center = panel.input_api_key.mapTo(panel.translation_scroll_area.viewport(), panel.input_api_key.rect().center())
    assert panel.translation_scroll_area.viewport().rect().contains(center)


@pytest.mark.parametrize(
    ("provider_id", "field_name"),
    [("online_gemma", "input_api_key"), ("luna", "input_luna_api_key")],
)
def test_provider_gate_enables_key_field_after_sync_from_disabled_controller(
    qtbot, provider_id, field_name
):
    controller = DummyController()
    controller.worker.gemma_model = "gemma-4-31b-it"
    controller.worker.use_gemma_translation = False
    controller.online_gemma_enabled = False
    controller.openai_enabled = False
    panel = TranslationSettingsPanel(controller, [("Remote", "gemma-4-31b-it")])
    qtbot.addWidget(panel)
    panel.show()
    panel.sync_from_controller()
    field = getattr(panel, field_name)
    assert not field.isEnabled()

    panel.provider_choice_buttons[provider_id].click()
    qtbot.wait(10)

    assert field.isEnabled()
    assert field.hasFocus()
    assert panel.provider_choice_buttons[provider_id].isChecked()


def test_provider_choice_routes_valid_google_local_and_luna_selection(qtbot):
    controller = DummyController()
    controller.worker.gemma_model = "gemma-3-4b-it-local"
    controller.worker.use_gemma_translation = False
    controller.openai_api_key = "luna-secret"
    controller.cmb_ai_model = SimpleNamespace(currentIndex=lambda: 0)
    routes = []
    controller.select_translation_provider = routes.append
    controller.on_ai_model_changed = lambda index: setattr(
        controller.worker, "gemma_model", "gemma-3-4b-it-local"
    )
    controller.toggle_ai_translation = lambda enabled: setattr(
        controller.worker, "use_gemma_translation", bool(enabled)
    )
    panel = TranslationSettingsPanel(
        controller,
        [("Local", "gemma-3-4b-it-local"), ("Remote", "gemma-4-31b-it")],
    )
    qtbot.addWidget(panel)

    panel.provider_choice_buttons["google"].click()
    panel.provider_choice_buttons["local_gemma"].click()
    panel.provider_choice_buttons["luna"].click()

    assert routes == ["google", "local_multimodal", "openai"]
    assert panel.provider_choice_buttons["luna"].isChecked()
    assert panel.chk_luna_enabled.isChecked()
    panel.update_theme("dark")
    assert "QRadioButton::indicator:checked" in panel.provider_choice_rows["luna"].styleSheet()


@pytest.mark.parametrize(
    ("provider_id", "field_name", "route_id"),
    [("online_gemma", "input_api_key", "gemma"), ("luna", "input_luna_api_key", "openai")],
)
def test_provider_choice_activates_route_after_entering_required_key(
    qtbot, provider_id, field_name, route_id
):
    controller = DummyController()
    controller.worker.gemma_model = "gemma-4-31b-it"
    controller.worker.use_gemma_translation = False
    controller.worker.google_api_key = ""
    controller.openai_api_key = ""
    routes = []

    def select_provider(value):
        routes.append(value)
        controller.provider_chain = (value,)
        controller.worker.use_gemma_translation = value != "google"
        return True

    controller.select_translation_provider = select_provider
    controller.on_google_api_key_changed = lambda value: setattr(
        controller.worker, "google_api_key", value
    )
    controller.on_luna_api_key_changed = lambda value: setattr(
        controller, "openai_api_key", value
    )
    panel = TranslationSettingsPanel(controller, [("Remote", "gemma-4-31b-it")])
    qtbot.addWidget(panel)

    panel.provider_choice_buttons[provider_id].click()
    assert routes == []
    field = getattr(panel, field_name)
    field.setText("t")
    assert routes == []
    field.setText("test-key")
    assert routes == []
    field.editingFinished.emit()

    assert routes == [route_id]
    field.setText("test-key-updated")
    field.editingFinished.emit()
    assert routes == [route_id]
    assert panel.provider_choice_buttons[provider_id].isChecked()


@pytest.mark.parametrize(
    ("old_route", "target", "field_name", "new_route"),
    [
        ("openai", "online_gemma", "input_api_key", "gemma"),
        ("gemma", "luna", "input_luna_api_key", "openai"),
        ("local_multimodal", "luna", "input_luna_api_key", "openai"),
    ],
)
def test_missing_key_stages_provider_and_clears_pending_after_key_entry(
    qtbot, old_route, target, field_name, new_route
):
    controller = DummyController()
    controller.worker.gemma_model = "gemma-4-31b-it"
    controller.worker.google_api_key = "" if target == "online_gemma" else "google-key"
    controller.openai_api_key = "" if target == "luna" else "luna-key"
    controller.provider_chain = (old_route,)
    staged = []
    routed = []

    def stage(provider):
        staged.append(provider)
        controller.pending_translation_provider_id = provider

    def route(provider):
        routed.append(provider)
        controller.provider_chain = (provider,)
        controller.pending_translation_provider_id = None
        controller.worker.use_gemma_translation = True
        return True

    controller.stage_translation_provider_setup = stage
    controller.select_translation_provider = route
    controller.on_google_api_key_changed = lambda value: setattr(controller.worker, "google_api_key", value)
    controller.on_luna_api_key_changed = lambda value: setattr(controller, "openai_api_key", value)
    panel = TranslationSettingsPanel(controller, [("Remote", "gemma-4-31b-it")])
    qtbot.addWidget(panel)

    panel.provider_choice_buttons[target].click()
    assert staged == [target]
    assert routed == []
    assert controller.pending_translation_provider_id == target
    field = getattr(panel, field_name)
    field.setText("n")
    assert routed == []
    assert controller.pending_translation_provider_id == target
    field.setText("new-key")
    field.editingFinished.emit()

    assert routed == [new_route]
    assert controller.pending_translation_provider_id is None


def test_provider_chain_gemma_legacy_restores_local_choice(qtbot):
    controller = DummyController()
    controller.provider_chain = ("gemma", "google")
    controller.worker.gemma_model = "gemma-3-4b-it-local"
    panel = TranslationSettingsPanel(
        controller,
        [("Local", "gemma-3-4b-it-local"), ("Remote", "gemma-4-31b-it")],
    )
    qtbot.addWidget(panel)

    panel.sync_from_controller()

    assert panel.provider_choice_buttons["local_gemma"].isChecked()

    controller.provider_chain = ("openai",)
    controller.openai_enabled = True
    controller.openai_api_key = "luna-secret"
    panel.sync_from_controller()

    assert panel.provider_choice_buttons["luna"].isChecked()
    assert not panel.provider_disclosures["luna"].isHidden()


def test_local_choice_replaces_luna_route_before_applying_key_gate(qtbot):
    controller = DummyController()
    controller.provider_chain = ("openai",)
    controller.openai_api_key = ""
    controller.worker.google_api_key = ""
    controller.worker.gemma_model = "gemma-3-4b-it-local"
    controller.worker.use_gemma_translation = False
    controller.cmb_ai_model = SimpleNamespace(currentIndex=lambda: 0)
    routes = []

    def select(provider):
        routes.append(provider)
        controller.provider_chain = (provider,)
        controller.worker.use_gemma_translation = True
        return True

    controller.select_translation_provider = select
    controller.toggle_ai_translation = lambda _: pytest.fail("must replace the old route before gating")
    panel = TranslationSettingsPanel(controller, [("Local", "gemma-3-4b-it-local")])
    qtbot.addWidget(panel)
    panel.provider_choice_buttons["local_gemma"].click()
    assert routes == ["local_multimodal"]
    assert panel.provider_choice_buttons["local_gemma"].isChecked()
    assert controller.worker.use_gemma_translation


def test_luna_selection_survives_ai_enabled_refresh(qtbot):
    controller = DummyController()
    panel = TranslationSettingsPanel(controller, [("Remote", "gemma-4-31b-it")])
    qtbot.addWidget(panel)
    panel._set_provider_choice("luna")
    panel.set_translate_mode(True)
    assert panel.provider_choice_buttons["luna"].isChecked()
    panel.update_theme("light")
    assert "QRadioButton:focus { border:2px solid" in panel.provider_choice_rows["luna"].styleSheet()


def test_missing_local_model_explains_recovery(qtbot):
    controller = DummyController()
    panel = TranslationSettingsPanel(controller, [("Remote", "gemma-4-31b-it")])
    qtbot.addWidget(panel)
    panel.on_provider_selected("local_gemma")
    assert "full edition" in panel.lbl_translate_health_detail.text()


@pytest.mark.parametrize("previous_provider", ["google", "online_gemma", "luna"])
def test_missing_local_model_restores_previous_provider(qtbot, previous_provider):
    controller = DummyController()
    panel = TranslationSettingsPanel(controller, [("Remote", "gemma-4-31b-it")])
    qtbot.addWidget(panel)
    panel._set_provider_choice(previous_provider)

    panel.provider_choice_buttons["local_gemma"].click()

    assert panel.provider_choice_buttons[previous_provider].isChecked()
    assert panel._selected_provider_id == previous_provider
