from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from themes import resolve_theme


class TranslationSettingsPanel(QFrame):
    def __init__(self, controller, supported_ai_models, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.supported_ai_models = list(supported_ai_models or [])
        self._ai_requested = False
        self.setObjectName("translationSettingsPanel")
        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.card_translate = QFrame()
        translate_layout = QVBoxLayout(self.card_translate)
        translate_layout.setContentsMargins(18, 18, 18, 18)
        translate_layout.setSpacing(12)

        self.lbl_translate = QLabel("翻譯")
        self.lbl_translate_hint = QLabel("Google 翻譯可以直接使用，AI 模式才需要 API KEY。")
        self.lbl_translate_hint.setWordWrap(True)
        self.lbl_translate_summary = QLabel("目前：Google 翻譯 · 免 API KEY")
        self.lbl_translate_summary.setWordWrap(True)
        translate_layout.addWidget(self.lbl_translate)
        translate_layout.addWidget(self.lbl_translate_hint)
        translate_layout.addWidget(self.lbl_translate_summary)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.lbl_translate_mode = QLabel("翻譯模式")
        mode_row.addWidget(self.lbl_translate_mode)
        mode_row.addStretch()
        self.translate_mode_group = QButtonGroup(self)
        self.translate_mode_group.setExclusive(True)

        self.btn_translate_google = QPushButton("Google 翻譯")
        self.btn_translate_google.setCheckable(True)
        self.btn_translate_google.setCursor(Qt.PointingHandCursor)
        self.btn_translate_google.clicked.connect(lambda: self.on_translate_mode_clicked(False))
        self.translate_mode_group.addButton(self.btn_translate_google)
        mode_row.addWidget(self.btn_translate_google)

        self.btn_translate_ai = QPushButton("Gemma AI 翻譯")
        self.btn_translate_ai.setCheckable(True)
        self.btn_translate_ai.setCursor(Qt.PointingHandCursor)
        self.btn_translate_ai.clicked.connect(lambda: self.on_translate_mode_clicked(True))
        self.translate_mode_group.addButton(self.btn_translate_ai)
        mode_row.addWidget(self.btn_translate_ai)
        translate_layout.addLayout(mode_row)

        self.advanced_translate_frame = QFrame()
        advanced_layout = QVBoxLayout(self.advanced_translate_frame)
        advanced_layout.setContentsMargins(14, 14, 14, 14)
        advanced_layout.setSpacing(10)

        self.lbl_advanced_translate = QLabel("進階翻譯設定")
        self.lbl_advanced_hint = QLabel("輸入 Google API KEY 後，AI 模式與自動切換才會生效。")
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

        self.chk_auto_switch = QCheckBox("自動切換")
        self.chk_auto_switch.toggled.connect(self.on_auto_switch_toggled)
        advanced_layout.addWidget(self.chk_auto_switch)

        self.card_key = QFrame()
        key_layout = QVBoxLayout(self.card_key)
        key_layout.setContentsMargins(18, 18, 18, 18)
        key_layout.setSpacing(12)
        self.lbl_advanced_translate_key = QLabel("KEY")
        self.lbl_advanced_hint_key = QLabel("輸入 Google API KEY 後，AI 模式與自動切換才會用到這些設定。")
        self.lbl_advanced_hint_key.setWordWrap(True)
        key_layout.addWidget(self.lbl_advanced_translate_key)
        key_layout.addWidget(self.lbl_advanced_hint_key)
        key_layout.addWidget(self.advanced_translate_frame)

        outer.addWidget(self.card_translate)
        outer.addWidget(self.card_key)
        self.card_key.setVisible(False)

        self.set_translate_advanced_visible(False)
        self.update_translate_summary()

    def on_translate_mode_clicked(self, use_ai):
        has_key = bool(self.controller.worker.google_api_key.strip())
        if use_ai:
            if has_key:
                self._ai_requested = True
                self.set_translate_mode(True)
                self.controller.toggle_ai_translation(True)
            else:
                self._ai_requested = True
                self.set_translate_mode(True)
                self.controller.toggle_ai_translation(False)
                self.input_api_key.setFocus()
        else:
            self._ai_requested = False
            self.set_translate_mode(False)
            self.controller.toggle_ai_translation(False)

    def on_api_key_text_changed(self, text):
        self.controller.on_api_key_changed(text)
        if text.strip() and self.btn_translate_ai.isChecked() and not self.controller.btn_ai_mode.isChecked():
            self.controller.btn_ai_mode.setChecked(True)
            self.controller.toggle_ai_translation(True)
        self.update_translate_summary()

    def on_ai_model_changed(self, index):
        self.controller.on_ai_model_changed(index)
        self.update_translate_summary()

    def on_auto_switch_toggled(self, checked):
        self.controller.set_gemma_auto_switch_mode(checked)
        self.update_translate_summary()

    def set_translate_mode(self, use_ai):
        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not use_ai)
        self.btn_translate_ai.setChecked(use_ai)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)
        self.set_translate_advanced_visible(True)
        self.update_key_state(use_ai or self._ai_requested)
        if use_ai and not self.input_api_key.text().strip():
            self.input_api_key.setFocus()
        self.update_translate_summary()

    def set_translate_advanced_visible(self, visible):
        self.card_key.setVisible(bool(visible))

    def update_translate_summary(self):
        use_ai = self.btn_translate_ai.isChecked()
        model_name = self.cmb_ai_model.currentText() if self.cmb_ai_model.count() else "Gemma"
        if use_ai:
            auto_state = "自動切換 ON" if self.chk_auto_switch.isChecked() else "自動切換 OFF"
            self.lbl_translate_summary.setText(f"目前：AI 翻譯 · {model_name} · {auto_state}")
        else:
            self.lbl_translate_summary.setText("目前：Google 翻譯 · 免 API KEY")

    def update_key_state(self, enabled):
        self.card_key.setEnabled(enabled)
        self.input_api_key.setEnabled(enabled)
        self.cmb_ai_model.setEnabled(enabled)
        self.chk_auto_switch.setEnabled(enabled)
        effect = None
        if not enabled:
            effect = QGraphicsOpacityEffect(self.card_key)
            effect.setOpacity(0.45)
        self.card_key.setGraphicsEffect(effect)

    def sync_from_controller(self):
        ai_requested = self.controller.btn_ai_mode.isChecked()
        if not ai_requested:
            self._ai_requested = False

        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(self.controller.worker.google_api_key)
        self.input_api_key.blockSignals(False)

        self.cmb_ai_model.blockSignals(True)
        self.cmb_ai_model.setCurrentIndex(self.controller.cmb_ai_model.currentIndex())
        self.cmb_ai_model.blockSignals(False)

        self.chk_auto_switch.blockSignals(True)
        self.chk_auto_switch.setChecked(self.controller.worker.gemma_auto_switch_enabled)
        self.chk_auto_switch.blockSignals(False)

        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not ai_requested)
        self.btn_translate_ai.setChecked(ai_requested)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)

        self.set_translate_advanced_visible(True)
        self.update_key_state(ai_requested or self._ai_requested)
        self.update_translate_summary()

    def update_theme(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.card_translate.setStyleSheet(theme.panel_qss("primary", radius=16))
        self.card_key.setStyleSheet(theme.panel_qss("transparent"))
        self.advanced_translate_frame.setStyleSheet(
            f"QFrame {{ background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 12px; }}"
        )
        self.lbl_translate.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text};")
        self.lbl_translate_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_translate_mode.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_translate_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_advanced_translate.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {theme.accent};")
        self.lbl_advanced_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_advanced_translate_key.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {theme.accent};")
        self.lbl_advanced_hint_key.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_api_key.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_ai_model.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.chk_auto_switch.setStyleSheet(f"color: {theme.text}; padding-top: 2px;")
        self.btn_translate_google.setStyleSheet(
            f"QPushButton {{ color: {theme.text}; background-color: transparent; border: 1px solid {theme.border}; "
            f"border-radius: 10px; padding: 6px 10px; }}"
            f"QPushButton:checked {{ background-color: {theme.accent}; color: #FFFFFF; border-color: {theme.accent}; }}"
        )
        self.btn_translate_ai.setStyleSheet(
            f"QPushButton {{ color: {theme.text}; background-color: transparent; border: 1px solid {theme.border}; "
            f"border-radius: 10px; padding: 6px 10px; }}"
            f"QPushButton:checked {{ background-color: {theme.accent}; color: #FFFFFF; border-color: {theme.accent}; }}"
        )
        self.input_api_key.setStyleSheet(
            f"background-color: {theme.card_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 6px; padding: 6px;"
        )
        self.cmb_ai_model.setStyleSheet(theme.combo_qss(radius=6))
