from __future__ import annotations

from PySide6.QtCore import Qt
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
    QVBoxLayout,
    QWidget,
)

from themes import resolve_theme


class TranslationSettingsPanel(QWidget):
    def __init__(self, controller, supported_ai_models, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.supported_ai_models = list(supported_ai_models or [])
        self._ai_requested = False
        self.setObjectName("translationSettingsPanel")
        self.setStyleSheet("QWidget { background: transparent; border: none; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.card_translate = QFrame()
        self.card_key = self.card_translate
        translate_layout = QVBoxLayout(self.card_translate)
        translate_layout.setContentsMargins(18, 18, 18, 18)
        translate_layout.setSpacing(10)

        self.lbl_translate = QLabel("翻譯功能")
        self.lbl_translate_hint = QLabel("Google 翻譯可以直接使用，AI 模式才需要 API KEY。")
        self.lbl_translate_hint.setWordWrap(True)
        self.lbl_translate_summary = QLabel("目前：Google 翻譯 · 免 API KEY")
        self.lbl_translate_summary.setWordWrap(False)

        translate_layout.addWidget(self.lbl_translate)
        translate_layout.addWidget(self.lbl_translate_hint)
        translate_layout.addWidget(self.lbl_translate_summary)

        self.lbl_translate_mode = QLabel("")
        self.lbl_translate_mode.setVisible(False)

        self.translate_mode_group = QButtonGroup(self)
        self.translate_mode_group.setExclusive(True)

        mode_buttons = QWidget()
        mode_buttons_layout = QHBoxLayout(mode_buttons)
        mode_buttons_layout.setContentsMargins(0, 0, 0, 0)
        mode_buttons_layout.setSpacing(8)

        self.btn_translate_google = QPushButton("Google 翻譯")
        self.btn_translate_google.setCheckable(True)
        self.btn_translate_google.setCursor(Qt.PointingHandCursor)
        self.btn_translate_google.clicked.connect(lambda: self.on_translate_mode_clicked(False))
        self.translate_mode_group.addButton(self.btn_translate_google)
        self.btn_translate_google.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_translate_ai = QPushButton("Gemma AI 翻譯")
        self.btn_translate_ai.setCheckable(True)
        self.btn_translate_ai.setCursor(Qt.PointingHandCursor)
        self.btn_translate_ai.clicked.connect(lambda: self.on_translate_mode_clicked(True))
        self.translate_mode_group.addButton(self.btn_translate_ai)
        self.btn_translate_ai.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        mode_buttons_layout.addWidget(self.btn_translate_google)
        mode_buttons_layout.addWidget(self.btn_translate_ai)
        translate_layout.addWidget(mode_buttons)

        self.advanced_translate_frame = QFrame()
        advanced_layout = QVBoxLayout(self.advanced_translate_frame)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(10)

        self.lbl_advanced_translate = QLabel("進階翻譯設定")
        self.lbl_advanced_hint = QLabel("Gemma Prompt 會套用到 AI 翻譯與截圖模式。")
        self.lbl_advanced_hint.setWordWrap(True)
        advanced_layout.addWidget(self.lbl_advanced_translate)
        advanced_layout.addWidget(self.lbl_advanced_hint)

        self.lbl_api_key = QLabel("Google API KEY")
        advanced_layout.addWidget(self.lbl_api_key)
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.input_api_key.setPlaceholderText("輸入 Google API KEY")
        self.input_api_key.textChanged.connect(self.on_api_key_text_changed)
        advanced_layout.addWidget(self.input_api_key)

        self.lbl_ai_model = QLabel("AI 模型")
        advanced_layout.addWidget(self.lbl_ai_model)
        self.cmb_ai_model = QComboBox()
        for label, model_name in self.supported_ai_models:
            self.cmb_ai_model.addItem(label, model_name)
        self.cmb_ai_model.currentIndexChanged.connect(self.on_ai_model_changed)
        advanced_layout.addWidget(self.cmb_ai_model)

        self.lbl_gemma_prompt = QLabel("Gemma Prompt")
        advanced_layout.addWidget(self.lbl_gemma_prompt)
        self.input_gemma_prompt = QPlainTextEdit()
        self.input_gemma_prompt.setPlaceholderText("輸入自訂的 AI 翻譯提示詞...")
        self.input_gemma_prompt.setTabChangesFocus(True)
        self.input_gemma_prompt.setMinimumHeight(92)
        self.input_gemma_prompt.textChanged.connect(self.on_gemma_prompt_changed)
        advanced_layout.addWidget(self.input_gemma_prompt)

        self.chk_auto_switch = QCheckBox("自動切換")
        self.chk_auto_switch.toggled.connect(self.on_auto_switch_toggled)
        self.chk_auto_switch.setVisible(False)

        translate_layout.addWidget(self.advanced_translate_frame)
        outer.addWidget(self.card_translate)

        self.set_translate_advanced_visible(False)
        self.update_translate_summary()

    def on_translate_mode_clicked(self, use_ai):
        has_key = bool(self.controller.worker.google_api_key.strip())
        self._ai_requested = bool(use_ai)
        if use_ai:
            if has_key:
                self.controller.toggle_ai_translation(True)
            else:
                self.controller.toggle_ai_translation(False)
                self.input_api_key.setFocus()
        else:
            self.controller.toggle_ai_translation(False)

    def on_api_key_text_changed(self, text):
        self.controller.on_api_key_changed(text)
        if text.strip() and self._ai_requested and not self.controller.btn_ai_mode.isChecked():
            self.controller.toggle_ai_translation(True)
        self.update_translate_summary()

    def on_ai_model_changed(self, index):
        self.controller.on_ai_model_changed(index)
        self.update_translate_summary()

    def on_auto_switch_toggled(self, checked):
        self.controller.set_gemma_auto_switch_mode(checked)
        self.update_translate_summary()

    def on_gemma_prompt_changed(self):
        if hasattr(self.controller, "on_gemma_prompt_changed"):
            self.controller.on_gemma_prompt_changed(self.input_gemma_prompt.toPlainText())

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
        if use_ai and not self.input_api_key.text().strip():
            self.input_api_key.setFocus()
        self.update_translate_summary()

    def set_translate_advanced_visible(self, visible):
        self.advanced_translate_frame.setVisible(bool(visible))

    def update_translate_summary(self):
        use_ai = self.btn_translate_ai.isChecked()
        model_name = self.cmb_ai_model.currentText() if self.cmb_ai_model.count() else "Gemma"
        if use_ai:
            self.lbl_translate_summary.setText(f"目前：AI 翻譯 · {model_name}")
        else:
            self.lbl_translate_summary.setText("目前：Google 翻譯 · 免 API KEY")

    def update_key_state(self, enabled):
        self.input_api_key.setEnabled(enabled)
        self.cmb_ai_model.setEnabled(enabled)
        self.input_gemma_prompt.setEnabled(enabled)
        self.chk_auto_switch.setEnabled(enabled)

    def sync_from_controller(self):
        ai_requested = self.controller.btn_ai_mode.isChecked()
        if ai_requested:
            self._ai_requested = True

        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(self.controller.worker.google_api_key)
        self.input_api_key.blockSignals(False)

        self.cmb_ai_model.blockSignals(True)
        self.cmb_ai_model.setCurrentIndex(self.controller.cmb_ai_model.currentIndex())
        self.cmb_ai_model.blockSignals(False)

        self.input_gemma_prompt.blockSignals(True)
        self.input_gemma_prompt.setPlainText(getattr(self.controller, "gemma_prompt", ""))
        self.input_gemma_prompt.blockSignals(False)

        self.chk_auto_switch.blockSignals(True)
        self.chk_auto_switch.setChecked(self.controller.worker.gemma_auto_switch_enabled)
        self.chk_auto_switch.blockSignals(False)

        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not ai_requested)
        self.btn_translate_ai.setChecked(ai_requested)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)

        enabled = bool(ai_requested or self._ai_requested)
        self.set_translate_advanced_visible(enabled)
        self.update_key_state(enabled)
        self.update_translate_summary()

    def update_theme(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.card_translate.setStyleSheet(theme.panel_qss("subtle", radius=16))
        self.advanced_translate_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.lbl_translate.setStyleSheet(f"font-size: 17px; font-weight: 900; color: {theme.text}; background: transparent; border: none;")
        self.lbl_translate_hint.setStyleSheet(f"color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_translate_mode.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_translate_summary.setStyleSheet(f"color: {theme.accent}; font-size: 11px; font-weight: 700; background: transparent; border: none;")
        self.lbl_advanced_translate.setVisible(False)
        self.lbl_advanced_translate.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {theme.accent}; background: transparent; border: none;")
        self.lbl_advanced_hint.setStyleSheet(f"color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_api_key.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_ai_model.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_gemma_prompt.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext}; background: transparent; border: none;")
        button_style = (
            f"QPushButton {{ color: {theme.text}; background-color: transparent; border: 1px solid {theme.border}; "
            f"border-radius: 10px; padding: 6px 12px; }}"
            f"QPushButton:checked {{ background-color: {theme.accent}; color: #FFFFFF; border-color: {theme.accent}; }}"
        )
        self.btn_translate_google.setStyleSheet(button_style)
        self.btn_translate_ai.setStyleSheet(button_style)
        self.input_api_key.setStyleSheet(
            f"background-color: {theme.card_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 6px; padding: 7px;"
        )
        self.cmb_ai_model.setStyleSheet(theme.combo_qss(radius=6))
        self.input_gemma_prompt.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 6px; padding: 6px; }}"
        )
        self.update_translate_summary()
