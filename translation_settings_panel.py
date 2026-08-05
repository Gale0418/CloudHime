from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
)

import translation_helpers as translation_tools
from provider_health import LOCAL_MODEL_IDS, assess_provider_health
from remote_model_discovery import (
    DISCOVERY_STATUS_INVALID_KEY,
    DISCOVERY_STATUS_NO_KEY,
    DISCOVERY_STATUS_OFFLINE_SNAPSHOT,
    DISCOVERY_STATUS_RATE_LIMITED,
    DISCOVERY_STATUS_UNVERIFIED,
    DISCOVERY_STATUS_VERIFIED,
    ModelDiscoveryResult,
    filter_model_choices_for_availability,
)
from themes import resolve_theme


class TranslationSettingsPanel(QWidget):
    def __init__(self, controller, supported_ai_models, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.supported_ai_models = list(supported_ai_models or [])
        self._ai_requested = False
        self.model_availability_result = ModelDiscoveryResult(
            status=DISCOVERY_STATUS_NO_KEY,
            error_code="no_key",
        )
        self._model_availability_checking = False
        self._theme_mode = getattr(controller, "theme_mode", "light")
        self.setObjectName("translationSettingsPanel")
        self.setStyleSheet("QWidget { background: transparent; border: none; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.card_translate = QFrame()
        self.card_key = self.card_translate
        translate_layout = QVBoxLayout(self.card_translate)
        translate_layout.setContentsMargins(20, 16, 20, 18)
        translate_layout.setSpacing(10)
        translate_layout.setAlignment(Qt.AlignTop)

        self.lbl_translate_icon = QLabel("文")
        self.lbl_translate_icon.setFixedSize(46, 46)
        self.lbl_translate_icon.setAlignment(Qt.AlignCenter)
        self.lbl_translate = QLabel("")
        self.lbl_translate.setMinimumHeight(46)
        self.lbl_translate.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.lbl_translate_hint = QLabel("")
        self.lbl_translate_hint.setWordWrap(True)
        self.lbl_translate_hint.setMinimumWidth(0)
        self.lbl_translate_hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_translate_hint.setVisible(True)
        self.lbl_translate_summary = QLabel("")
        self.lbl_translate_summary.setWordWrap(True)
        self.lbl_translate_summary.setMinimumWidth(0)
        self.lbl_translate_summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_translate_summary.setVisible(True)
        self.lbl_translate_health_detail = QLabel("")
        self.lbl_translate_health_detail.setWordWrap(True)
        self.lbl_translate_health_detail.setMinimumWidth(0)
        self.lbl_translate_health_detail.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_translate_health_detail.setVisible(True)
        self.lbl_translate_mode = QLabel("")
        self.lbl_translate_mode.setVisible(True)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(12)
        header_row.addWidget(self.lbl_translate_icon)
        header_row.addWidget(self.lbl_translate)
        header_row.addStretch()
        translate_layout.addLayout(header_row)
        translate_layout.addWidget(self.lbl_translate_hint)
        translate_layout.addWidget(self.lbl_translate_summary)
        translate_layout.addWidget(self.lbl_translate_health_detail)

        self.translate_mode_group = QButtonGroup(self)
        self.translate_mode_group.setExclusive(True)

        mode_buttons = QWidget()
        self.mode_buttons = mode_buttons
        mode_buttons_layout = QHBoxLayout(mode_buttons)
        mode_buttons_layout.setContentsMargins(3, 3, 3, 3)
        mode_buttons_layout.setSpacing(3)

        self.btn_translate_google = QPushButton("")
        self.btn_translate_google.setCheckable(True)
        self.btn_translate_google.setCursor(Qt.PointingHandCursor)
        self.btn_translate_google.clicked.connect(lambda: self.on_translate_mode_clicked(False))
        self.translate_mode_group.addButton(self.btn_translate_google)
        self.btn_translate_google.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_translate_google.setFont(QFont("Segoe UI Emoji", 10))

        self.btn_translate_ai = QPushButton("")
        self.btn_translate_ai.setCheckable(True)
        self.btn_translate_ai.setCursor(Qt.PointingHandCursor)
        self.btn_translate_ai.clicked.connect(lambda: self.on_translate_mode_clicked(True))
        self.translate_mode_group.addButton(self.btn_translate_ai)
        self.btn_translate_ai.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_translate_ai.setFont(QFont("Segoe UI Emoji", 10))

        mode_buttons_layout.addWidget(self.btn_translate_google)
        mode_buttons_layout.addWidget(self.btn_translate_ai)
        translate_layout.addWidget(self.lbl_translate_mode)
        translate_layout.addWidget(mode_buttons)

        self.advanced_translate_frame = QFrame()
        advanced_layout = QVBoxLayout(self.advanced_translate_frame)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(10)

        self.lbl_advanced_translate = QLabel("")
        self.lbl_advanced_translate.setVisible(False)
        self.lbl_advanced_hint = QLabel("")
        self.lbl_advanced_hint.setVisible(False)

        self.lbl_api_key = QLabel("")
        self.lbl_api_key.setVisible(False)
        advanced_layout.addWidget(self.lbl_api_key)
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.input_api_key.setPlaceholderText("")
        self.input_api_key.textChanged.connect(self.on_api_key_text_changed)
        api_key_row = QHBoxLayout()
        api_key_row.setContentsMargins(0, 0, 0, 0)
        api_key_row.setSpacing(6)
        api_key_row.addWidget(self.input_api_key)
        self.btn_api_key_visible = QPushButton("V")
        self.btn_api_key_visible.setCursor(Qt.PointingHandCursor)
        self.btn_api_key_visible.setFixedSize(34, 34)
        self.btn_api_key_visible.setFont(QFont("Segoe UI", 10))
        self.btn_api_key_visible.setToolTip("Show / hide API key")
        self.btn_api_key_visible.clicked.connect(self.toggle_api_key_visible)
        api_key_row.addWidget(self.btn_api_key_visible)
        advanced_layout.addLayout(api_key_row)

        self.separator = QFrame()
        advanced_layout.addWidget(self.separator)

        self.lbl_ai_model = QLabel("")
        advanced_layout.addWidget(self.lbl_ai_model)
        self.cmb_ai_model = QComboBox()
        for label, model_name in self.supported_ai_models:
            self.cmb_ai_model.addItem(label, model_name)
        self.cmb_ai_model.currentIndexChanged.connect(self.on_ai_model_changed)
        advanced_layout.addWidget(self.cmb_ai_model)

        model_availability_row = QHBoxLayout()
        model_availability_row.setContentsMargins(0, 0, 0, 0)
        model_availability_row.setSpacing(6)
        self.btn_refresh_model_availability = QPushButton("")
        self.btn_refresh_model_availability.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_model_availability.clicked.connect(
            self.on_refresh_model_availability_clicked
        )
        model_availability_row.addWidget(self.btn_refresh_model_availability)
        self.lbl_model_availability = QLabel("")
        self.lbl_model_availability.setWordWrap(True)
        self.lbl_model_availability.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        model_availability_row.addWidget(self.lbl_model_availability, 1)
        advanced_layout.addLayout(model_availability_row)

        self.lbl_ai_model_notes = QLabel("")
        self.lbl_ai_model_notes.setWordWrap(False)
        self.lbl_ai_model_notes.setVisible(False)
        self.lbl_ai_model_notes.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        advanced_layout.addWidget(self.lbl_ai_model_notes)

        self.lbl_gemma_prompt = QLabel("")
        advanced_layout.addWidget(self.lbl_gemma_prompt)
        self.input_gemma_prompt = QPlainTextEdit()
        self.input_gemma_prompt.setPlaceholderText("")
        self.input_gemma_prompt.setTabChangesFocus(True)
        self.input_gemma_prompt.setMinimumHeight(122)
        self.input_gemma_prompt.textChanged.connect(self.on_gemma_prompt_changed)
        advanced_layout.addWidget(self.input_gemma_prompt)

        self.btn_advanced_tuning = QPushButton("⚙ Advanced Local Tuning")
        self.btn_advanced_tuning.setCheckable(True)
        self.btn_advanced_tuning.setCursor(Qt.PointingHandCursor)
        self.btn_advanced_tuning.clicked.connect(self.on_advanced_tuning_toggled)
        advanced_layout.addWidget(self.btn_advanced_tuning)

        self.tuning_frame = QFrame()
        tuning_layout = QVBoxLayout(self.tuning_frame)
        tuning_layout.setContentsMargins(0, 0, 0, 0)
        tuning_layout.setSpacing(10)

        self.lbl_local_gemma_temp = QLabel("Local Gemma Temperature (0.0 - 1.0)")
        tuning_layout.addWidget(self.lbl_local_gemma_temp)
        self.spin_local_gemma_temp = QDoubleSpinBox()
        self.spin_local_gemma_temp.setRange(0.0, 1.0)
        self.spin_local_gemma_temp.setSingleStep(0.1)
        self.spin_local_gemma_temp.valueChanged.connect(self.on_local_gemma_temp_changed)
        tuning_layout.addWidget(self.spin_local_gemma_temp)

        self.lbl_local_gemma_repeat = QLabel("Local Gemma Repeat Penalty (1.0 - 2.0)")
        tuning_layout.addWidget(self.lbl_local_gemma_repeat)
        self.spin_local_gemma_repeat = QDoubleSpinBox()
        self.spin_local_gemma_repeat.setRange(1.0, 2.0)
        self.spin_local_gemma_repeat.setSingleStep(0.05)
        self.spin_local_gemma_repeat.valueChanged.connect(self.on_local_gemma_repeat_changed)
        tuning_layout.addWidget(self.spin_local_gemma_repeat)

        self.lbl_local_multimodal = QLabel("")
        tuning_layout.addWidget(self.lbl_local_multimodal)
        self.chk_local_multimodal_enabled = QCheckBox("")
        self.chk_local_multimodal_enabled.toggled.connect(self.on_local_multimodal_enabled_changed)
        tuning_layout.addWidget(self.chk_local_multimodal_enabled)
        self.chk_local_multimodal_cpu_only = QCheckBox("")
        self.chk_local_multimodal_cpu_only.toggled.connect(self.on_local_multimodal_cpu_only_changed)
        tuning_layout.addWidget(self.chk_local_multimodal_cpu_only)

        self.chk_japanese_ocr_rescue_enabled = QCheckBox("")
        self.chk_japanese_ocr_rescue_enabled.toggled.connect(self.on_japanese_ocr_rescue_enabled_changed)
        tuning_layout.addWidget(self.chk_japanese_ocr_rescue_enabled)

        self.lbl_local_multimodal_base_url = QLabel("")
        tuning_layout.addWidget(self.lbl_local_multimodal_base_url)
        self.input_local_multimodal_base_url = QLineEdit()
        self.input_local_multimodal_base_url.editingFinished.connect(self.on_local_multimodal_base_url_changed)
        tuning_layout.addWidget(self.input_local_multimodal_base_url)

        self.lbl_local_multimodal_model = QLabel("")
        tuning_layout.addWidget(self.lbl_local_multimodal_model)
        self.input_local_multimodal_model = QLineEdit()
        self.input_local_multimodal_model.editingFinished.connect(self.on_local_multimodal_model_changed)
        tuning_layout.addWidget(self.input_local_multimodal_model)

        self.lbl_local_multimodal_timeout = QLabel("")
        tuning_layout.addWidget(self.lbl_local_multimodal_timeout)
        self.spin_local_multimodal_timeout = QSpinBox()
        self.spin_local_multimodal_timeout.setRange(1, 300)
        self.spin_local_multimodal_timeout.valueChanged.connect(self.on_local_multimodal_timeout_changed)
        tuning_layout.addWidget(self.spin_local_multimodal_timeout)

        self.tuning_frame.setVisible(False)
        advanced_layout.addWidget(self.tuning_frame)

        self.chk_auto_switch = QCheckBox("")
        self.chk_auto_switch.toggled.connect(self.on_auto_switch_toggled)
        self.chk_auto_switch.setVisible(False)

        self.refresh_localized_texts()
        translate_layout.addWidget(self.advanced_translate_frame)
        outer.addWidget(self.card_translate)

        self.set_translate_advanced_visible(False)
        self.update_translate_summary()

    def on_translate_mode_clicked(self, use_ai):
        has_key = bool(self.controller.worker.google_api_key.strip())
        is_local_model = (getattr(self.controller.worker, "gemma_model", "") or "").strip() in LOCAL_MODEL_IDS
        self._ai_requested = bool(use_ai)
        if use_ai:
            if has_key or is_local_model:
                self.controller.toggle_ai_translation(True)
            else:
                self.controller.toggle_ai_translation(False)
                self.sync_from_controller()
                self.input_api_key.setFocus()
                return
        else:
            self.controller.toggle_ai_translation(False)
        self.sync_from_controller()

    def on_api_key_text_changed(self, text):
        self.controller.on_api_key_changed(text)
        if text.strip() and self._ai_requested and not getattr(self.controller.worker, "use_gemma_translation", False):
            self.controller.toggle_ai_translation(True)
        self.update_translate_summary()

    def toggle_api_key_visible(self):
        visible = self.input_api_key.echoMode() != QLineEdit.Normal
        self.input_api_key.setEchoMode(QLineEdit.Normal if visible else QLineEdit.PasswordEchoOnEdit)
        self.btn_api_key_visible.setText("H" if visible else "V")

    def on_ai_model_changed(self, index):
        self.controller.on_ai_model_changed(index)
        model_id = str(self.cmb_ai_model.itemData(index) or "").strip().lower()
        if (
            self._ai_requested
            and model_id in LOCAL_MODEL_IDS
            and not getattr(self.controller.worker, "use_gemma_translation", False)
        ):
            self.controller.toggle_ai_translation(True)
        self.update_ai_model_notes()
        self.update_translate_summary()

    def on_refresh_model_availability_clicked(self):
        starter = getattr(self.controller, "refresh_remote_model_availability", None)
        self.set_model_availability_checking(True)
        started = False
        try:
            started = bool(starter()) if callable(starter) else False
        except Exception:
            started = False
        if not started:
            self.set_model_availability_checking(False)
            result = getattr(self.controller, "remote_model_availability", None)
            if isinstance(result, ModelDiscoveryResult):
                self.set_model_availability_result(result)

    def set_model_availability_checking(self, checking):
        self._model_availability_checking = bool(checking)
        self.btn_refresh_model_availability.setEnabled(not self._model_availability_checking)
        if self._model_availability_checking:
            self.btn_refresh_model_availability.setText(
                translation_tools.ui_text(
                    self._ui_language(),
                    "translation_model_availability_checking",
                )
            )
            self.lbl_model_availability.setText(
                translation_tools.ui_text(
                    self._ui_language(),
                    "translation_model_availability_checking",
                )
            )
        else:
            self._refresh_model_availability_text()

    def _refresh_model_availability_text(self):
        result = self.model_availability_result
        lang = self._ui_language()
        status_key = {
            DISCOVERY_STATUS_VERIFIED: "translation_model_availability_verified",
            DISCOVERY_STATUS_OFFLINE_SNAPSHOT: "translation_model_availability_offline",
            DISCOVERY_STATUS_NO_KEY: "translation_model_availability_no_key",
            DISCOVERY_STATUS_INVALID_KEY: "translation_model_availability_invalid_key",
            DISCOVERY_STATUS_RATE_LIMITED: "translation_model_availability_rate_limited",
            DISCOVERY_STATUS_UNVERIFIED: "translation_model_availability_unverified",
        }.get(result.status, "translation_model_availability_unverified")
        self.btn_refresh_model_availability.setText(
            translation_tools.ui_text(lang, "translation_model_availability_refresh")
        )
        self.lbl_model_availability.setText(
            translation_tools.ui_text(
                lang,
                status_key,
                count=len(result.available_model_ids),
            )
        )

    def set_model_availability_result(self, result):
        if not isinstance(result, ModelDiscoveryResult):
            return
        current_model = str(self.cmb_ai_model.currentData() or "").strip()
        self.model_availability_result = result
        choices = filter_model_choices_for_availability(
            self.supported_ai_models,
            result,
            current_model=current_model,
        )
        self.cmb_ai_model.blockSignals(True)
        self.cmb_ai_model.clear()
        for label, model_id in choices:
            self.cmb_ai_model.addItem(label, model_id)
        selected_index = self.cmb_ai_model.findData(current_model)
        if selected_index >= 0:
            self.cmb_ai_model.setCurrentIndex(selected_index)
            if (
                result.status in {DISCOVERY_STATUS_VERIFIED, DISCOVERY_STATUS_OFFLINE_SNAPSHOT}
                and current_model not in LOCAL_MODEL_IDS
                and current_model not in result.available_model_ids
            ):
                self.cmb_ai_model.setItemData(
                    selected_index,
                    translation_tools.ui_text(
                        self._ui_language(),
                        "translation_model_availability_selected_unavailable",
                    ),
                    Qt.ToolTipRole,
                )
        self.cmb_ai_model.blockSignals(False)
        self.set_model_availability_checking(False)
        self.update_ai_model_notes()
        self.update_translate_summary()

    def on_auto_switch_toggled(self, checked):
        self.controller.set_gemma_auto_switch_mode(checked)
        self.update_translate_summary()

    def on_advanced_tuning_toggled(self, checked):
        self.tuning_frame.setVisible(checked)

    def on_gemma_prompt_changed(self):
        if hasattr(self.controller, "on_gemma_prompt_changed"):
            self.controller.on_gemma_prompt_changed(self.input_gemma_prompt.toPlainText())

    def on_local_gemma_temp_changed(self, value):
        if hasattr(self.controller, "on_local_gemma_temp_changed"):
            self.controller.on_local_gemma_temp_changed(value)

    def on_local_gemma_repeat_changed(self, value):
        if hasattr(self.controller, "on_local_gemma_repeat_changed"):
            self.controller.on_local_gemma_repeat_changed(value)

    def on_local_multimodal_enabled_changed(self, checked):
        if hasattr(self.controller, "on_local_multimodal_enabled_changed"):
            self.controller.on_local_multimodal_enabled_changed(checked)
        self.update_local_multimodal_state()
        self.update_translate_summary()

    def on_japanese_ocr_rescue_enabled_changed(self, checked):
        if hasattr(self.controller, "on_japanese_ocr_rescue_enabled_changed"):
            self.controller.on_japanese_ocr_rescue_enabled_changed(checked)

    def on_local_multimodal_base_url_changed(self):
        if hasattr(self.controller, "on_local_multimodal_base_url_changed"):
            self.controller.on_local_multimodal_base_url_changed(self.input_local_multimodal_base_url.text())

    def on_local_multimodal_cpu_only_changed(self, checked):
        if hasattr(self.controller, "on_local_multimodal_cpu_only_changed"):
            self.controller.on_local_multimodal_cpu_only_changed(checked)
        self.update_local_multimodal_state()

    def on_local_multimodal_model_changed(self):
        if hasattr(self.controller, "on_local_multimodal_model_changed"):
            self.controller.on_local_multimodal_model_changed(self.input_local_multimodal_model.text())
        self.update_translate_summary()

    def on_local_multimodal_timeout_changed(self, value):
        if hasattr(self.controller, "on_local_multimodal_timeout_changed"):
            self.controller.on_local_multimodal_timeout_changed(value)

    def update_local_multimodal_state(self):
        enabled = self.chk_local_multimodal_enabled.isEnabled() and self.chk_local_multimodal_enabled.isChecked()
        has_embedded = getattr(self.controller.worker, "local_vision_runtime", None) is not None
        self.chk_local_multimodal_cpu_only.setEnabled(enabled and has_embedded)
        self.chk_japanese_ocr_rescue_enabled.setEnabled(enabled)
        is_custom_url_visible = not has_embedded

        self.lbl_local_multimodal_base_url.setVisible(is_custom_url_visible)
        self.input_local_multimodal_base_url.setVisible(is_custom_url_visible)
        self.lbl_local_multimodal_model.setVisible(is_custom_url_visible)
        self.input_local_multimodal_model.setVisible(is_custom_url_visible)

        for widget in (
            self.lbl_local_multimodal_base_url,
            self.input_local_multimodal_base_url,
            self.lbl_local_multimodal_model,
            self.input_local_multimodal_model,
            self.lbl_local_multimodal_timeout,
            self.spin_local_multimodal_timeout,
        ):
            widget.setEnabled(enabled)

    def _ui_language(self):
        return translation_tools.get_ui_language(self.controller)

    def _ai_model_note_text(self, model_name):
        model_name = (model_name or "").strip().lower()
        lang = self._ui_language()
        notes = {
            "gemma-3-1b-it": {
                "en": "Fast text-only model; screenshots fall back to OCR.",
                "zh-TW": "快速純文字模型，截圖會回退 OCR。",
            },
            "gemma-3-27b-it": {
                "en": "Best balance for screenshot translation.",
                "zh-TW": "截圖翻譯的平衡首選。",
            },
            "gemma-4-31b-it": {
                "en": "Large model with stronger vision, but slower.",
                "zh-TW": "更強的視覺能力，但速度較慢。",
            },
            "gemini-2.5-pro": {
                "en": "Strong paid model; can be slower or rate-limited.",
                "zh-TW": "付費強力模型，可能較慢或受限。",
            },
        }
        model_note = notes.get(model_name)
        if not model_note:
            return ""
        return model_note.get(lang) or model_note.get("en") or ""

    def update_ai_model_notes(self):
        current_model = ""
        if self.cmb_ai_model.count() > 0:
            current_model = str(self.cmb_ai_model.currentData() or "")
        text = self._ai_model_note_text(current_model)
        self.lbl_ai_model_notes.setText(text)
        self.lbl_ai_model_notes.setVisible(bool(text))
        self.lbl_ai_model_notes.setMaximumHeight(self.fontMetrics().height() + 6)

    def refresh_localized_texts(self):
        lang = self._ui_language()
        self.lbl_translate.setText(translation_tools.ui_text(lang, "translation_panel_title"))
        self.lbl_translate_hint.setText(translation_tools.ui_text(lang, "translation_panel_hint"))
        self.lbl_translate_mode.setText("Provider" if lang == "en" else "\u7ffb\u8b6f\u4f86\u6e90")
        self.btn_translate_google.setText(translation_tools.ui_text(lang, "translation_mode_google"))
        self.btn_translate_ai.setText(translation_tools.ui_text(lang, "translation_mode_ai"))
        self.lbl_api_key.setText(translation_tools.ui_text(lang, "translation_api_key"))
        self.input_api_key.setPlaceholderText(translation_tools.ui_text(lang, "translation_api_key_placeholder"))
        self.lbl_ai_model.setText(translation_tools.ui_text(lang, "translation_ai_model"))
        self._refresh_model_availability_text()
        self.lbl_gemma_prompt.setText(translation_tools.ui_text(lang, "translation_gemma_prompt"))
        self.input_gemma_prompt.setPlaceholderText(
            translation_tools.ui_text(lang, "translation_gemma_prompt_placeholder")
        )
        self.chk_auto_switch.setText(translation_tools.ui_text(lang, "translation_auto_switch"))
        self.lbl_local_multimodal.setText(translation_tools.ui_text(lang, "translation_local_multimodal_group"))
        self.chk_local_multimodal_enabled.setText(
            translation_tools.ui_text(lang, "translation_local_multimodal_enabled")
        )
        self.chk_local_multimodal_cpu_only.setText(
            translation_tools.ui_text(lang, "translation_local_multimodal_cpu_only")
        )
        self.chk_japanese_ocr_rescue_enabled.setText(
            translation_tools.ui_text(lang, "translation_japanese_ocr_rescue_enabled")
        )
        self.lbl_local_multimodal_base_url.setText(
            translation_tools.ui_text(lang, "translation_local_multimodal_base_url")
        )
        self.lbl_local_multimodal_model.setText(
            translation_tools.ui_text(lang, "translation_local_multimodal_model")
        )
        self.lbl_local_multimodal_timeout.setText(
            translation_tools.ui_text(lang, "translation_local_multimodal_timeout")
        )
        self.spin_local_multimodal_timeout.setSuffix(" sec" if lang == "en" else " 秒")
        self.btn_advanced_tuning.setText("⚙ Advanced Local Tuning" if lang == "en" else "⚙ 本地進階參數")
        self.update_ai_model_notes()

    def set_translate_mode(self, use_ai):
        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not use_ai)
        self.btn_translate_ai.setChecked(use_ai)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)
        enabled = bool(use_ai or self._ai_requested)
        self.set_translate_advanced_visible(enabled)
        self.update_key_state(enabled)
        model_id = str(self.cmb_ai_model.currentData() or "").strip().lower()
        if use_ai and model_id not in LOCAL_MODEL_IDS and not self.input_api_key.text().strip():
            self.input_api_key.setFocus()
        self.update_translate_summary()

    def set_translate_advanced_visible(self, visible):
        self.advanced_translate_frame.setVisible(True)

    def _provider_health(self):
        worker = self.controller.worker
        model_id = str(self.cmb_ai_model.currentData() or "") if self.cmb_ai_model.count() else ""
        model_label = self.cmb_ai_model.currentText() if self.cmb_ai_model.count() else "AI"
        runtime = getattr(worker, "local_vision_runtime", None)
        runtime_state = getattr(runtime, "_state", None)
        runtime_name = str(getattr(runtime_state, "name", "") or "")
        controller_vision_state = str(getattr(self.controller, "local_vision_state", "") or "")
        if controller_vision_state and controller_vision_state != "stopped":
            vision_state = controller_vision_state
        else:
            vision_state = runtime_name or controller_vision_state or "stopped"
        vision_detail = str(
            getattr(self.controller, "local_vision_detail", "")
            or getattr(runtime_state, "detail", "")
            or ""
        )
        vision_mode = str(getattr(runtime_state, "mode", "") or "")

        local_provider = getattr(worker, "local_gemma_provider", None)
        try:
            local_text_ready = bool(local_provider is not None and local_provider.available())
        except Exception:
            local_text_ready = False

        assets = getattr(worker, "_local_vision_assets", None)
        asset_paths = [
            getattr(assets, "model_path", None),
            getattr(assets, "projector_path", None),
        ]
        model_assets_present = bool(asset_paths) and all(
            path is not None and path.exists() for path in asset_paths
        )

        return assess_provider_health(
            ui_language=self._ui_language(),
            ai_requested=bool(self._ai_requested),
            ai_enabled=bool(self.btn_translate_ai.isChecked()),
            model_id=model_id,
            model_label=model_label,
            has_api_key=bool(self.input_api_key.text().strip() or getattr(worker, "google_api_key", "").strip()),
            local_multimodal_enabled=bool(self.chk_local_multimodal_enabled.isChecked()),
            embedded_runtime_available=runtime is not None,
            local_vision_state=vision_state,
            local_vision_detail=vision_detail,
            local_vision_mode=vision_mode,
            local_model_state=str(getattr(self.controller, "local_model_state", "stopped") or "stopped"),
            local_model_detail=str(getattr(self.controller, "local_model_detail", "") or ""),
            local_text_ready=local_text_ready,
            model_assets_present=model_assets_present,
        )

    def update_translate_summary(self):
        health = self._provider_health()
        self.lbl_translate_summary.setText(health.summary)
        self.lbl_translate_health_detail.setText(health.detail)
        self.lbl_translate_health_detail.setVisible(bool(health.detail))
        self.lbl_translate_summary.setProperty("healthTone", health.tone)
        theme_mode = self._theme_mode
        summary_kind = "danger" if health.tone == "danger" else "accent"
        self.lbl_translate_summary.setStyleSheet(resolve_theme(theme_mode).pill_qss(summary_kind))
        self.lbl_translate_summary.setToolTip(health.detail)

    def update_key_state(self, enabled):
        self.input_api_key.setEnabled(enabled)
        self.btn_api_key_visible.setEnabled(enabled)
        self.cmb_ai_model.setEnabled(enabled)
        self.input_gemma_prompt.setEnabled(enabled)
        self.chk_auto_switch.setEnabled(enabled)
        self.btn_advanced_tuning.setEnabled(enabled)
        self.btn_refresh_model_availability.setEnabled(not self._model_availability_checking)
        self.spin_local_gemma_temp.setEnabled(enabled)
        self.spin_local_gemma_repeat.setEnabled(enabled)
        self.lbl_local_gemma_temp.setEnabled(enabled)
        self.lbl_local_gemma_repeat.setEnabled(enabled)
        self.lbl_local_multimodal.setEnabled(enabled)
        self.chk_local_multimodal_enabled.setEnabled(enabled)
        self.chk_japanese_ocr_rescue_enabled.setEnabled(enabled)
        self.update_local_multimodal_state()

    def sync_from_controller(self):
        self.refresh_localized_texts()
        ai_enabled = bool(getattr(self.controller.worker, "use_gemma_translation", False))
        if ai_enabled:
            self._ai_requested = True

        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(self.controller.worker.google_api_key)
        self.input_api_key.blockSignals(False)

        self.cmb_ai_model.blockSignals(True)
        self.cmb_ai_model.setCurrentIndex(self.controller.cmb_ai_model.currentIndex())
        self.cmb_ai_model.blockSignals(False)
        self.update_ai_model_notes()

        self.input_gemma_prompt.blockSignals(True)
        prompt_text = getattr(self.controller, "gemma_prompt", "") or self.controller.get_default_gemma_prompt()
        self.input_gemma_prompt.setPlainText(prompt_text)
        self.input_gemma_prompt.blockSignals(False)

        self.spin_local_gemma_temp.blockSignals(True)
        self.spin_local_gemma_temp.setValue(getattr(self.controller, "local_gemma_temperature", 0.2))
        self.spin_local_gemma_temp.blockSignals(False)

        self.spin_local_gemma_repeat.blockSignals(True)
        self.spin_local_gemma_repeat.setValue(getattr(self.controller, "local_gemma_repeat_penalty", 1.15))
        self.spin_local_gemma_repeat.blockSignals(False)

        self.chk_local_multimodal_enabled.blockSignals(True)
        self.chk_local_multimodal_enabled.setChecked(getattr(self.controller, "local_multimodal_enabled", False))
        self.chk_local_multimodal_enabled.blockSignals(False)

        self.chk_local_multimodal_cpu_only.blockSignals(True)
        self.chk_local_multimodal_cpu_only.setChecked(getattr(self.controller, "local_multimodal_cpu_only", False))
        self.chk_local_multimodal_cpu_only.blockSignals(False)

        self.chk_japanese_ocr_rescue_enabled.blockSignals(True)
        self.chk_japanese_ocr_rescue_enabled.setChecked(
            getattr(self.controller, "japanese_ocr_rescue_enabled", False)
        )
        self.chk_japanese_ocr_rescue_enabled.blockSignals(False)

        self.input_local_multimodal_base_url.blockSignals(True)
        self.input_local_multimodal_base_url.setText(
            getattr(self.controller, "local_multimodal_base_url", "http://127.0.0.1:8080/v1")
        )
        self.input_local_multimodal_base_url.blockSignals(False)

        self.input_local_multimodal_model.blockSignals(True)
        self.input_local_multimodal_model.setText(getattr(self.controller, "local_multimodal_model", ""))
        self.input_local_multimodal_model.blockSignals(False)

        self.spin_local_multimodal_timeout.blockSignals(True)
        self.spin_local_multimodal_timeout.setValue(getattr(self.controller, "local_multimodal_timeout_seconds", 20))
        self.spin_local_multimodal_timeout.blockSignals(False)

        self.chk_auto_switch.blockSignals(True)
        self.chk_auto_switch.setChecked(self.controller.worker.gemma_auto_switch_enabled)
        self.chk_auto_switch.blockSignals(False)

        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not ai_enabled)
        self.btn_translate_ai.setChecked(ai_enabled)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)

        enabled = bool(ai_enabled or self._ai_requested)
        self.set_translate_advanced_visible(enabled)
        self.update_key_state(enabled)
        self.update_local_multimodal_state()
        result = getattr(self.controller, "remote_model_availability", None)
        if isinstance(result, ModelDiscoveryResult):
            self.set_model_availability_result(result)
        self.update_translate_summary()

    def update_theme(self, theme_mode):
        self._theme_mode = theme_mode
        theme = resolve_theme(theme_mode)
        self.refresh_localized_texts()
        self.card_translate.setStyleSheet(theme.panel_qss("subtle", radius=16))
        self.advanced_translate_frame.setStyleSheet("QFrame { background: transparent; border: none; }")

        self.lbl_translate.setStyleSheet(
            f"font-size: 20px; font-weight: 900; color: {theme.text}; background: transparent; border: none;"
        )
        icon_bg = "rgba(65, 150, 255, 51)" if theme.key != "light" else "rgba(80, 165, 255, 46)"
        icon_border = "rgba(93, 155, 255, 158)" if theme.key != "light" else "rgba(90, 167, 247, 138)"
        icon_text = "#8FC4FF" if theme.key != "light" else "#3A8BDA"
        self.lbl_translate_icon.setStyleSheet(
            f"font-size: 19px; font-weight: 900; color: {icon_text}; background-color: {icon_bg}; "
            f"border: 1px solid {icon_border}; border-radius: 13px;"
        )
        self.lbl_translate_hint.setStyleSheet(
            f"font-size: 12px; color: {theme.subtext}; background: transparent; border: none;"
        )
        self.lbl_translate_mode.setStyleSheet(
            f"font-size: 12px; font-weight: 800; color: {theme.subtext}; background: transparent; border: none; margin-top: 2px;"
        )
        self.lbl_translate_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_translate_health_detail.setStyleSheet(
            f"font-size: 11px; color: {theme.subtext}; background: transparent; border: none;"
        )
        self.lbl_advanced_translate.setStyleSheet("background: transparent; border: none; color: transparent;")
        self.lbl_advanced_hint.setStyleSheet("background: transparent; border: none; color: transparent;")

        self.separator.setStyleSheet(f"border: none; border-bottom: 1px dotted {theme.border}; background: transparent;")
        field_label_style = (
            f"font-size: 12px; font-weight: 700; color: {theme.subtext}; "
            "background: transparent; border: none;"
        )
        accent_label_style = (
            f"font-size: 12px; font-weight: 700; color: {theme.accent}; "
            "background: transparent; border: none;"
        )
        self.lbl_api_key.setStyleSheet(field_label_style)
        self.lbl_ai_model.setStyleSheet(accent_label_style)
        self.lbl_gemma_prompt.setStyleSheet(accent_label_style)
        self.lbl_ai_model_notes.setStyleSheet(
            f"font-size: 11px; color: {theme.subtext}; background: transparent; border: none; "
            "line-height: 1.2; margin-top: 2px;"
        )

        self.mode_buttons.setStyleSheet(
            f"QWidget {{ background-color: {theme.input_bg}; border: 1px solid {theme.border}; border-radius: 12px; }}"
        )
        button_style = (
            f"QPushButton {{ color: {theme.subtext}; background-color: transparent; border: none; "
            f"border-radius: 9px; padding: 8px 12px; font-size: 13px; font-weight: 800; }}"
            f"QPushButton:hover {{ color: {theme.text}; background-color: {theme.accent_soft}; }}"
            f"QPushButton:checked {{ background-color: {theme.accent}; color: #FFFFFF; }}"
        )
        self.btn_translate_google.setStyleSheet(button_style)
        self.btn_translate_ai.setStyleSheet(button_style)

        self.input_api_key.setStyleSheet(
            f"background-color: {theme.card_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 6px; padding: 7px; font-size: 13px;"
        )
        self.btn_api_key_visible.setStyleSheet(theme.button_qss(radius=8))
        self.cmb_ai_model.setStyleSheet(theme.combo_qss(radius=6))
        self.input_gemma_prompt.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 6px; padding: 6px; font-size: 13px; }}"
        )
        self.lbl_local_gemma_temp.setStyleSheet(accent_label_style)
        self.lbl_local_gemma_repeat.setStyleSheet(accent_label_style)
        self.lbl_local_multimodal.setStyleSheet(accent_label_style)
        self.lbl_local_multimodal_base_url.setStyleSheet(field_label_style)
        self.lbl_local_multimodal_model.setStyleSheet(field_label_style)
        self.lbl_local_multimodal_timeout.setStyleSheet(field_label_style)
        self.btn_advanced_tuning.setStyleSheet(
            f"QPushButton {{ color: {theme.subtext}; text-align: left; background: transparent; border: none; font-size: 12px; font-weight: 700; padding: 4px 0; }}"
            f"QPushButton:hover {{ color: {theme.text}; }}"
        )
        self.input_local_multimodal_base_url.setStyleSheet(
            f"background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 6px; padding: 7px; font-size: 13px;"
        )
        self.input_local_multimodal_model.setStyleSheet(
            f"background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 6px; padding: 7px; font-size: 13px;"
        )
        self.chk_local_multimodal_enabled.setStyleSheet(
            f"QCheckBox {{ color: {theme.subtext}; background: transparent; border: none; font-size: 12px; font-weight: 700; }}"
        )
        self.chk_local_multimodal_cpu_only.setStyleSheet(
            f"QCheckBox {{ color: {theme.subtext}; background: transparent; border: none; font-size: 12px; font-weight: 700; }}"
        )
        spinbox_style = f"QDoubleSpinBox, QSpinBox {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; border-radius: 6px; padding: 4px; }}"
        self.spin_local_gemma_temp.setStyleSheet(spinbox_style)
        self.spin_local_gemma_repeat.setStyleSheet(spinbox_style)
        self.spin_local_multimodal_timeout.setStyleSheet(spinbox_style)
        self.tuning_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.update_translate_summary()
