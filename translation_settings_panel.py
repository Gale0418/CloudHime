from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QToolButton,
    QSizePolicy,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
)

import translation_helpers as translation_tools
from openai_translation_provider import DEFAULT_OPENAI_MODEL
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


ONLINE_GEMMA_MODEL_IDS = ("gemma-4-26b-a4b-it", "gemma-4-31b-it")


class _ProviderDisclosureButton(QToolButton):
    """Keep both native activation keys available across Qt platform styles."""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)


class _ProviderDisclosure(QFrame):
    """Keyboard-first native disclosure for one provider's real settings body."""

    def __init__(self, provider_id, provider_name, capability, parent=None):
        super().__init__(parent)
        self.provider_id = str(provider_id)
        self.provider_name = str(provider_name)
        self.capability = str(capability)
        self.setObjectName(f"providerDisclosure_{self.provider_id}")
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = _ProviderDisclosureButton()
        self.header.setObjectName(f"providerDisclosureHeader_{self.provider_id}")
        self.header.setCheckable(True)
        self.header.setChecked(False)
        self.header.setArrowType(Qt.RightArrow)
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.setFocusPolicy(Qt.StrongFocus)
        self.header.setMinimumWidth(0)
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header.toggled.connect(self._set_expanded)
        layout.addWidget(self.header)

        self.capability_label = QLabel()
        self.capability_label.setObjectName(
            f"providerDisclosureCapability_{self.provider_id}"
        )
        self.capability_label.setWordWrap(True)
        self.capability_label.setMinimumWidth(0)
        self.capability_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.capability_label.setVisible(True)
        layout.addWidget(self.capability_label)

        self.body = QFrame()
        self.body.setObjectName(f"providerDisclosureBody_{self.provider_id}")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(10, 8, 10, 10)
        self.body_layout.setSpacing(8)
        self.body.setMinimumWidth(0)
        self.body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.body.setVisible(False)
        layout.addWidget(self.body)
        self.set_summary("Unverified")

    def set_summary(self, status, capability=None):
        """Update only non-secret summary text exposed by the header."""
        if capability is not None:
            self.capability = str(capability)
        status = str(status or "Unverified")
        self.header.setText(f"{self.provider_name}  ·  {status}")
        self.capability_label.setText(self.capability)
        self.capability_label.updateGeometry()
        self.updateGeometry()
        self.header.setAccessibleName(f"{self.provider_name}: {status}")
        self.header.setAccessibleDescription(self.capability)

    def _sync_capability_height(self):
        width = self.capability_label.width()
        if width <= 0 or not self.capability_label.wordWrap():
            return
        required_height = self.capability_label.heightForWidth(width)
        if required_height > 0 and self.capability_label.minimumHeight() != required_height:
            self.capability_label.setMinimumHeight(required_height)
            self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # QScrollArea may assign the narrowed content width after the parent
        # layout pass; refresh once the child geometry is settled so wrapped
        # capability text cannot be clipped vertically.
        QTimer.singleShot(0, self._sync_capability_height)

    def _set_expanded(self, expanded):
        expanded = bool(expanded)
        if not expanded:
            focus = self.window().focusWidget()
            if focus is self.body or (focus is not None and self.body.isAncestorOf(focus)):
                self.header.setFocus(Qt.OtherFocusReason)
        self.header.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.body.setVisible(expanded)
        self.body.setEnabled(expanded)
        self.body_layout.activate()
        ancestor = self.parentWidget()
        while ancestor is not None:
            layout = ancestor.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            ancestor.updateGeometry()
            ancestor = ancestor.parentWidget()

    def set_expanded(self, expanded):
        self.header.setChecked(bool(expanded))

    @property
    def expanded(self):
        return bool(self.header.isChecked())


class _ProviderChoiceRow(QFrame):
    """A compact, keyboard-friendly single-selection provider row."""

    def __init__(self, provider_id, provider_name, description, parent=None):
        super().__init__(parent)
        self.provider_id = str(provider_id)
        self.setObjectName(f"providerChoiceRow_{self.provider_id}")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.radio = QRadioButton()
        self.radio.setObjectName(f"providerChoice_{self.provider_id}")
        self.radio.setFocusPolicy(Qt.StrongFocus)
        self.radio.setCursor(Qt.PointingHandCursor)
        self.radio.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.radio, 0, Qt.AlignTop)

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(1)
        self.name_label = QLabel(str(provider_name))
        self.name_label.setObjectName(f"providerChoiceName_{self.provider_id}")
        self.name_label.setMinimumWidth(0)
        self.name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.detail_label = QLabel(str(description))
        self.detail_label.setObjectName(f"providerChoiceDetail_{self.provider_id}")
        self.detail_label.setWordWrap(True)
        self.detail_label.setMinimumWidth(0)
        self.detail_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        copy_layout.addWidget(self.name_label)
        copy_layout.addWidget(self.detail_label)
        layout.addLayout(copy_layout, 1)

        self.status_label = QLabel()
        self.status_label.setObjectName(f"providerChoiceStatus_{self.provider_id}")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.status_label.setMinimumWidth(0)
        self.status_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        layout.addWidget(self.status_label, 0, Qt.AlignTop)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.radio.click()
            event.accept()
            return
        super().mousePressEvent(event)


class TranslationSettingsPanel(QWidget):
    def __init__(self, controller, supported_ai_models, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.supported_ai_models = list(supported_ai_models or [])
        self._ai_requested = False
        self._selected_provider_id = "google"
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
        self.card_translate.setObjectName("translationCardHost")
        self.card_translate.setMinimumWidth(300)
        card_layout = QVBoxLayout(self.card_translate)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Keep the Git-era card and its host layout intact, but let the dense
        # provider settings scroll inside this one card when the legacy
        # 1422x800 shell cannot show every control at once.
        self.translation_scroll_area = QScrollArea()
        self.translation_scroll_area.setObjectName("translationSettingsScrollArea")
        self.translation_scroll_area.setMinimumWidth(0)
        self.translation_scroll_area.setWidgetResizable(True)
        self.translation_scroll_area.setFrameShape(QFrame.NoFrame)
        self.translation_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.translation_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.translation_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.translation_scroll_area.viewport().setAutoFillBackground(False)
        self.translation_scroll_area.viewport().setStyleSheet("background: transparent; border: none;")

        self.translation_content = QWidget()
        self.translation_content.setObjectName("translationSettingsContent")
        self.translation_content.setMinimumWidth(0)
        # Long provider summaries must not force the legacy card wider than its
        # scroll viewport; labels and capabilities wrap within the available
        # column instead.
        self.translation_content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        translate_layout = QVBoxLayout(self.translation_content)
        translate_layout.setContentsMargins(20, 16, 20, 18)
        translate_layout.setSpacing(10)
        translate_layout.setAlignment(Qt.AlignTop)
        self.translation_scroll_area.setWidget(self.translation_content)
        card_layout.addWidget(self.translation_scroll_area)

        self.lbl_translate_icon = QLabel("文")
        self.lbl_translate_icon.setFixedSize(46, 46)
        self.lbl_translate_icon.setAlignment(Qt.AlignCenter)
        self.lbl_translate_icon.hide()
        self.lbl_translate = QLabel("")
        self.lbl_translate.setMinimumHeight(32)
        self.lbl_translate.setMinimumWidth(0)
        self.lbl_translate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_translate.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.lbl_translate_hint = QLabel("")
        self.lbl_translate_hint.setWordWrap(True)
        self.lbl_translate_hint.setMinimumWidth(0)
        self.lbl_translate_hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_translate_hint.setMaximumWidth(16777215)
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
        header_row.addWidget(self.lbl_translate)
        header_row.addStretch()
        translate_layout.addLayout(header_row)
        translate_layout.addWidget(self.lbl_translate_hint)
        translate_layout.addWidget(self.lbl_translate_summary)
        translate_layout.addWidget(self.lbl_translate_health_detail)

        # Provider health is embedded in the legacy card as small status cards;
        # it is metadata only and never implies remaining quota.
        self.provider_status_frame = QFrame()
        self.provider_status_frame.setObjectName("providerStatusCards")
        self.provider_status_frame.setMinimumWidth(0)
        self.provider_status_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        provider_status_layout = QVBoxLayout(self.provider_status_frame)
        provider_status_layout.setContentsMargins(0, 2, 0, 2)
        provider_status_layout.setSpacing(8)
        self.provider_status_rows = {}
        self.provider_disclosures = {}
        # Public aliases make the UI-only accordion state discoverable without
        # changing the historical provider_status_rows contract.
        self.provider_accordions = self.provider_disclosures
        self.provider_disclosure_rows = self.provider_disclosures
        self.provider_headers = {}
        for provider_id, provider_name in (
            ("local_gemma", "Local Gemma"),
            ("online_gemma", "Online Gemma"),
            ("luna", "Luna"),
        ):
            capability = {
                "local_gemma": "Local model, no cloud key required",
                "online_gemma": "One key, two Gemma models",
                "luna": "Text + image input; reasoning off",
            }[provider_id]
            disclosure = _ProviderDisclosure(
                provider_id,
                provider_name,
                capability,
                self.provider_status_frame,
            )
            self.provider_disclosures[provider_id] = disclosure
            self.provider_headers[provider_id] = disclosure.header
            row = QFrame()
            row.setObjectName(f"providerStatusCard_{provider_id}")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(10, 7, 10, 7)
            row_layout.setSpacing(2)
            name_label = QLabel(provider_name)
            name_label.setObjectName(f"providerName_{provider_id}")
            status_label = QLabel("")
            status_label.setObjectName(f"providerStatus_{provider_id}")
            detail_label = QLabel("")
            detail_label.setObjectName(f"providerDetail_{provider_id}")
            detail_label.setWordWrap(True)
            scope_label = QLabel("")
            scope_label.setObjectName(f"providerScope_{provider_id}")
            scope_label.setWordWrap(True)
            row_layout.addWidget(name_label)
            row_layout.addWidget(status_label)
            row_layout.addWidget(detail_label)
            row_layout.addWidget(scope_label)
            disclosure.body_layout.addWidget(row)
            provider_status_layout.addWidget(disclosure)
            self.provider_status_rows[provider_id] = {
                "row": row,
                "layout": row_layout,
                "name": name_label,
                "status": status_label,
                "detail": detail_label,
                "scope": scope_label,
                "disclosure": disclosure,
                "header": disclosure.header,
                "body": disclosure.body,
                "capability": disclosure.capability_label,
            }
            if provider_id == "online_gemma":
                self.online_gemma_model_rows = {}
                self.online_gemma_models_frame = QFrame()
                self.online_gemma_models_frame.setObjectName("onlineGemmaModelCards")
                model_layout = QVBoxLayout(self.online_gemma_models_frame)
                model_layout.setContentsMargins(8, 2, 8, 2)
                model_layout.setSpacing(4)
                for model_id in ONLINE_GEMMA_MODEL_IDS:
                    model_row = QFrame()
                    model_row.setObjectName(f"onlineGemmaModelCard_{model_id}")
                    model_row_layout = QVBoxLayout(model_row)
                    model_row_layout.setContentsMargins(8, 5, 8, 5)
                    model_row_layout.setSpacing(2)
                    model_name = QLabel(model_id)
                    model_name.setObjectName(f"onlineGemmaModelName_{model_id}")
                    model_status = QLabel("")
                    model_status.setObjectName(f"onlineGemmaModelStatus_{model_id}")
                    model_detail = QLabel("")
                    model_detail.setObjectName(f"onlineGemmaModelDetail_{model_id}")
                    model_detail.setWordWrap(True)
                    model_row_layout.addWidget(model_name)
                    model_row_layout.addWidget(model_status)
                    model_row_layout.addWidget(model_detail)
                    model_layout.addWidget(model_row)
                    self.online_gemma_model_rows[model_id] = {
                        "row": model_row,
                        "layout": model_row_layout,
                        "name": model_name,
                        "status": model_status,
                        "detail": model_detail,
                    }
                row_layout.addWidget(self.online_gemma_models_frame)
        self.provider_rows = self.provider_status_rows

        # Keep the historical two-button attributes as hidden compatibility
        # controls.  The visible selection surface is the four-provider group
        # below; cloudhime_ui.py still uses these legacy attributes as its
        # bool-based controller contract.
        self.translate_mode_group = QButtonGroup(self)
        self.translate_mode_group.setExclusive(True)
        self.btn_translate_google = QPushButton(self)
        self.btn_translate_google.setObjectName("legacyTranslateGoogle")
        self.btn_translate_google.setCheckable(True)
        self.btn_translate_google.clicked.connect(lambda: self.on_translate_mode_clicked(False))
        self.translate_mode_group.addButton(self.btn_translate_google)
        self.btn_translate_ai = QPushButton(self)
        self.btn_translate_ai.setObjectName("legacyTranslateAI")
        self.btn_translate_ai.setCheckable(True)
        self.btn_translate_ai.clicked.connect(lambda: self.on_translate_mode_clicked(True))
        self.translate_mode_group.addButton(self.btn_translate_ai)
        self.btn_translate_google.hide()
        self.btn_translate_ai.hide()

        mode_buttons = QWidget()
        self.mode_buttons = mode_buttons
        mode_buttons.setObjectName("providerChoiceRows")
        mode_buttons_layout = QVBoxLayout(mode_buttons)
        mode_buttons_layout.setContentsMargins(0, 0, 0, 0)
        mode_buttons_layout.setSpacing(6)
        self.provider_choice_group = QButtonGroup(self)
        self.provider_choice_group.setExclusive(True)
        self.provider_choice_rows = {}
        self.provider_choice_buttons = {}
        provider_choices = (
            ("google", "Google 翻譯", "不需 API Key"),
            ("local_gemma", "本機 Gemma", "本地模型・不需雲端金鑰"),
            ("online_gemma", "線上 Gemma", "單一 Key・雙 Gemma 模型"),
            ("luna", "Luna", "文字＋圖片輸入・需要 Luna Key"),
        )
        for provider_id, provider_name, description in provider_choices:
            row = _ProviderChoiceRow(provider_id, provider_name, description, mode_buttons)
            self.provider_choice_rows[provider_id] = row
            self.provider_choice_buttons[provider_id] = row.radio
            self.provider_choice_group.addButton(row.radio)
            row.radio.clicked.connect(
                lambda checked, selected_id=provider_id: (
                    self.on_provider_selected(selected_id) if checked else None
                )
            )
            mode_buttons_layout.addWidget(row)
        self._set_provider_choice("google")
        translate_layout.addWidget(self.lbl_translate_mode)
        translate_layout.addWidget(mode_buttons)

        self.advanced_translate_frame = QFrame()
        self.advanced_translate_frame.setMinimumWidth(0)
        self.advanced_translate_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        advanced_layout = QVBoxLayout(self.advanced_translate_frame)
        self._advanced_layout = advanced_layout
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
        self.input_api_key.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.input_api_key.textChanged.connect(self.on_api_key_text_changed)
        self.input_api_key.editingFinished.connect(self.on_api_key_editing_finished)
        api_key_row = QHBoxLayout()
        api_key_row.setContentsMargins(0, 0, 0, 0)
        api_key_row.setSpacing(6)
        api_key_row.addWidget(self.input_api_key)
        self.btn_api_key_visible = QPushButton("V")
        self.btn_api_key_visible.setCursor(Qt.PointingHandCursor)
        self.btn_api_key_visible.setMinimumWidth(60)
        self.btn_api_key_visible.setFixedHeight(34)
        self.btn_api_key_visible.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_api_key_visible.setFont(QFont("Segoe UI", 10))
        self.btn_api_key_visible.setToolTip("Show / hide API key")
        self.btn_api_key_visible.clicked.connect(self.toggle_api_key_visible)
        api_key_row.addWidget(self.btn_api_key_visible)
        advanced_layout.addLayout(api_key_row)
        self.api_key_row = api_key_row

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
        self.model_availability_row = model_availability_row

        self.lbl_ai_model_notes = QLabel("")
        self.lbl_ai_model_notes.setWordWrap(True)
        self.lbl_ai_model_notes.setTextFormat(Qt.RichText)
        self.lbl_ai_model_notes.setOpenExternalLinks(True)
        self.lbl_ai_model_notes.setVisible(False)
        self.lbl_ai_model_notes.setMinimumWidth(0)
        self.lbl_ai_model_notes.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        advanced_layout.addWidget(self.lbl_ai_model_notes)

        self.lbl_gemma_prompt = QLabel("")
        advanced_layout.addWidget(self.lbl_gemma_prompt)
        self.input_gemma_prompt = QPlainTextEdit()
        self.input_gemma_prompt.setPlaceholderText("")
        self.input_gemma_prompt.setTabChangesFocus(True)
        self.input_gemma_prompt.setMinimumHeight(122)
        self.input_gemma_prompt.textChanged.connect(self.on_gemma_prompt_changed)
        self.lbl_gemma_prompt.setVisible(False)
        self.input_gemma_prompt.setVisible(False)
        advanced_layout.addWidget(self.input_gemma_prompt)

        self.btn_advanced_tuning = QPushButton("⚙ Advanced prompt & tuning")
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
        self.lbl_auto_switch = QLabel("")
        self.lbl_auto_switch.setWordWrap(True)

        self._build_online_provider_controls(advanced_layout)
        self._organize_provider_bodies()
        advanced_layout.addWidget(self.provider_status_frame)

        self.refresh_localized_texts()
        translate_layout.addWidget(self.advanced_translate_frame)
        outer.addWidget(self.card_translate)

        self.set_translate_advanced_visible(False)
        self.update_translate_summary()

    def _organize_provider_bodies(self):
        """Move the existing controls into their provider's real disclosure body."""
        local_layout = self.provider_disclosures["local_gemma"].body_layout
        online_layout = self.provider_disclosures["online_gemma"].body_layout

        self.btn_use_local_gemma = QPushButton()
        self.btn_use_local_gemma.setObjectName("useLocalGemma")
        self.btn_use_local_gemma.clicked.connect(self.on_use_local_gemma)
        self.btn_use_local_gemma.setEnabled(
            self.cmb_ai_model.findData("gemma-3-4b-it-local") >= 0
        )
        local_layout.addWidget(self.btn_use_local_gemma)
        self.lbl_local_model_terms = QLabel()
        self.lbl_local_model_terms.setWordWrap(True)
        self.lbl_local_model_terms.setOpenExternalLinks(True)
        local_layout.addWidget(self.lbl_local_model_terms)

        # Local Gemma owns prompt and tuning controls; the existing frame and
        # widget identities stay unchanged for controller integrations.
        for widget in (
            self.lbl_gemma_prompt,
            self.input_gemma_prompt,
            self.btn_advanced_tuning,
            self.tuning_frame,
        ):
            local_layout.addWidget(widget)

        # The legacy model selector can contain local and remote entries. It
        # remains one canonical selector, but lives with Online Gemma's model
        # and availability controls where it is actually used.
        for item in (
            self.lbl_api_key,
            self.api_key_row,
            self.separator,
            self.lbl_ai_model,
            self.cmb_ai_model,
            self.model_availability_row,
            self.lbl_ai_model_notes,
        ):
            if isinstance(item, QLayout):
                self._advanced_layout.removeItem(item)
                self.online_provider_layout.addLayout(item)
            else:
                self.online_provider_layout.addWidget(item)

        online_layout.addWidget(self.online_provider_frame)
        self.provider_disclosures["luna"].body_layout.addWidget(self.luna_provider_frame)

    def _build_online_provider_controls(self, parent_layout):
        """Build provider credentials/configuration without requiring a new controller API.

        The panel owns only transient widget state until a controller callback is
        supplied.  This keeps the settings window usable with older controllers.
        API key widgets intentionally have no tooltip or accessibility value that
        could expose their contents.
        """
        self.online_provider_frame = QFrame()
        self.online_provider_frame.setObjectName("onlineGemmaSettings")
        self.online_provider_frame.setMinimumWidth(0)
        self.online_provider_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        online_layout = QVBoxLayout(self.online_provider_frame)
        self.online_provider_layout = online_layout
        online_layout.setContentsMargins(0, 8, 0, 0)
        online_layout.setSpacing(6)
        self.lbl_online_gemma = QLabel("")
        self.lbl_online_gemma.setObjectName("onlineGemmaHeading")
        online_layout.addWidget(self.lbl_online_gemma)
        self.chk_online_gemma_enabled = QCheckBox("")
        self.chk_online_gemma_enabled.toggled.connect(self.on_online_gemma_enabled_changed)
        online_layout.addWidget(self.chk_online_gemma_enabled)

        online_layout.addWidget(self.lbl_auto_switch)
        online_layout.addWidget(self.chk_auto_switch)
        self.lbl_online_gemma_models = QLabel("")
        self.lbl_online_gemma_models.setWordWrap(True)
        self.lbl_online_gemma_models.setMinimumWidth(0)
        self.lbl_online_gemma_models.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        online_layout.addWidget(self.lbl_online_gemma_models)

        # There is one Online Gemma credential.  Keep the historical field
        # aliases pointing at this same widget for integrations still using
        # the old panel attribute name.
        self.input_google_api_key = self.input_api_key
        self.input_gemma_api_key = self.input_api_key

        self.luna_provider_frame = QFrame()
        self.luna_provider_frame.setObjectName("lunaSettings")
        self.luna_provider_frame.setMinimumWidth(0)
        self.luna_provider_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        luna_layout = QVBoxLayout(self.luna_provider_frame)
        self.luna_provider_layout = luna_layout
        luna_layout.setContentsMargins(0, 8, 0, 0)
        luna_layout.setSpacing(6)
        self.lbl_luna = QLabel("")
        self.lbl_luna.setObjectName("lunaHeading")
        luna_layout.addWidget(self.lbl_luna)
        self.chk_luna_enabled = QCheckBox("")
        self.chk_luna_enabled.toggled.connect(self.on_luna_enabled_changed)
        luna_layout.addWidget(self.chk_luna_enabled)
        self.lbl_luna_api_key = QLabel("")
        luna_layout.addWidget(self.lbl_luna_api_key)
        self.input_luna_api_key = QLineEdit()
        self.input_luna_api_key.setObjectName("inputLunaApiKey")
        self.input_luna_api_key.setEchoMode(QLineEdit.Password)
        self.input_luna_api_key.textChanged.connect(self.on_luna_api_key_changed)
        self.input_luna_api_key.editingFinished.connect(self.on_luna_api_key_editing_finished)
        luna_layout.addWidget(self.input_luna_api_key)
        self.lbl_luna_model_label = QLabel("")
        luna_layout.addWidget(self.lbl_luna_model_label)
        self.lbl_luna_model = QLabel(DEFAULT_OPENAI_MODEL)
        self.lbl_luna_model.setObjectName("lunaModel")
        luna_layout.addWidget(self.lbl_luna_model)
        self.lbl_luna_capabilities = QLabel("")
        self.lbl_luna_capabilities.setWordWrap(True)
        self.lbl_luna_capabilities.setMinimumWidth(0)
        self.lbl_luna_capabilities.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        luna_layout.addWidget(self.lbl_luna_capabilities)
        self.lbl_luna_reasoning = QLabel("")
        luna_layout.addWidget(self.lbl_luna_reasoning)
        self.cmb_luna_reasoning = QComboBox()
        self.cmb_luna_reasoning.addItem("None", "none")
        self.cmb_luna_reasoning.setEnabled(False)
        self.cmb_luna_reasoning.currentIndexChanged.connect(self.on_luna_reasoning_changed)
        luna_layout.addWidget(self.cmb_luna_reasoning)
        self.lbl_luna_timeout = QLabel("")
        luna_layout.addWidget(self.lbl_luna_timeout)
        self.spin_luna_timeout = QSpinBox()
        self.spin_luna_timeout.setRange(1, 300)
        self.spin_luna_timeout.setValue(60)
        self.spin_luna_timeout.valueChanged.connect(self.on_luna_timeout_changed)
        luna_layout.addWidget(self.spin_luna_timeout)

        # Names commonly used by the controller contract are aliases, not
        # duplicate controls, so state cannot drift between two fields.
        self.chk_openai_enabled = self.chk_luna_enabled
        self.input_openai_api_key = self.input_luna_api_key
        self.cmb_openai_reasoning = self.cmb_luna_reasoning
        self.spin_openai_timeout = self.spin_luna_timeout
        self.cmb_luna_reasoning_effort = self.cmb_luna_reasoning
        self.spin_luna_timeout_seconds = self.spin_luna_timeout
        self.lbl_luna_capability = self.lbl_luna_capabilities
        parent_layout.addWidget(self.online_provider_frame)
        parent_layout.addWidget(self.luna_provider_frame)
        self._configure_provider_accessibility()
        # Visual provider rows now lead the scroll area.  Rely on Qt's widget
        # order; the old chain started with hidden compatibility buttons and
        # duplicated the API-key field, creating invalid cross-window links.
        self._sync_provider_config_from_controller()

    def _configure_provider_accessibility(self):
        lang = self._ui_language()
        is_en = str(lang).lower().startswith("en")
        is_ja = lang == "ja"
        def set_a11y(widget, name_en, name_zh, description_en, description_zh, name_ja=None, description_ja=None):
            if is_en:
                widget.setAccessibleName(name_en)
                widget.setAccessibleDescription(description_en)
            elif is_ja:
                widget.setAccessibleName(name_ja or name_en)
                widget.setAccessibleDescription(description_ja or description_en)
            else:
                widget.setAccessibleName(name_zh)
                widget.setAccessibleDescription(description_zh)

        set_a11y(self.btn_translate_google, "Use Google Translate", "使用 Google 翻譯", "Select the no-key translation path.", "選擇不需 API Key 的翻譯路徑。", "Google 翻訳を使う", "API キー不要の翻訳方法を選択します。")
        set_a11y(self.btn_translate_ai, "Use AI translation", "使用 AI 翻譯", "Select a configured AI provider.", "選擇已設定的 AI Provider。", "AI 翻訳を使う", "設定済みの AI プロバイダーを選択します。")
        choice_a11y = {
            "google": ("Google Translate", "Google 翻譯", "Select Google Translate; no API key is required.", "選擇 Google 翻譯；不需要 API Key。", "Google 翻訳", "Google 翻訳を選択します。API キーは不要です。"),
            "local_gemma": ("Local Gemma", "本機 Gemma", "Select the local Gemma model; no cloud key is required.", "選擇本機 Gemma；不需要雲端金鑰。", "ローカル Gemma", "ローカル Gemma モデルを選択します。クラウドキーは不要です。"),
            "online_gemma": ("Online Gemma", "線上 Gemma", "Select Online Gemma; a Google API key is required.", "選擇線上 Gemma；需要 Google API Key。", "Online Gemma", "Online Gemma を選択します。Google API キーが必要です。"),
            "luna": ("Luna", "Luna", "Select Luna; a Luna API key is required.", "選擇 Luna；需要 Luna API Key。", "Luna", "Luna を選択します。Luna API キーが必要です。"),
        }
        for provider_id, radio in self.provider_choice_buttons.items():
            set_a11y(radio, *choice_a11y[provider_id])
        set_a11y(self.input_api_key, "Online Gemma API key", "Online Gemma API Key", "Secret input protected by Windows DPAPI; it is never exposed in settings data.", "由 Windows DPAPI 保護的秘密欄位，不會寫入設定資料。", "Online Gemma API キー", "Windows DPAPI で保護される秘密情報です。設定データには保存されません。")
        set_a11y(self.btn_api_key_visible, "Show Online Gemma API key", "顯示 Online Gemma API Key", "Toggle secret visibility locally.", "只在本機切換秘密顯示。", "Online Gemma API キーを表示", "この端末上でのみ秘密情報の表示を切り替えます。")
        set_a11y(self.cmb_ai_model, "AI model", "AI 模型", "Choose the model used by the legacy AI path.", "選擇舊版 AI 路徑使用的模型。", "AI モデル", "従来の AI 経路で使うモデルを選択します。")
        set_a11y(self.btn_advanced_tuning, "Advanced local tuning", "本地進階參數", "Expand optional local model parameters.", "展開可選的本地模型參數。", "ローカルモデルの詳細設定", "ローカルモデルの任意のパラメーターを表示します。")
        set_a11y(self.chk_online_gemma_enabled, "Enable Online Gemma", "啟用 Online Gemma", "Allow Online Gemma to be selected. Connectivity is checked at request time.", "允許選用 Online Gemma；連線會在要求送出時檢查。", "Online Gemma を有効化", "Online Gemma を選択可能にします。接続はリクエスト送信時に確認します。")
        set_a11y(self.input_api_key, "Online Gemma API key", "Online Gemma API Key", "Secret input protected by Windows DPAPI; the value is never exposed in settings data.", "由 Windows DPAPI 保護的秘密欄位，內容不會寫入設定資料。", "Online Gemma API キー", "Windows DPAPI で保護される秘密情報です。設定データには保存されません。")
        set_a11y(self.chk_auto_switch, "Rotate Gemma models automatically", "自動輪替 Gemma 模型", "Rotate between gemma-4-26b-a4b-it and gemma-4-31b-it when enabled.", "啟用後在 gemma-4-26b-a4b-it 與 gemma-4-31b-it 間自動輪替。", "Gemma モデルを自動切替", "有効にすると gemma-4-26b-a4b-it と gemma-4-31b-it を切り替えます。")
        set_a11y(self.chk_luna_enabled, "Enable Luna", "啟用 Luna", "Allow the fixed gpt-6-luna provider.", "允許使用固定的 gpt-6-luna Provider。", "Luna を有効化", "固定の gpt-6-luna プロバイダーを使用可能にします。")
        set_a11y(self.input_luna_api_key, "Luna API key", "Luna API Key", "Secret input. The value is not exposed through accessibility text.", "秘密欄位，內容不會透過輔助功能文字暴露。", "Luna API キー", "秘密情報です。アクセシビリティ用のテキストには表示されません。")
        set_a11y(self.cmb_luna_reasoning, "Luna thinking disabled", "Luna Thinking 已關閉", "Thinking is fixed off for low latency.", "為維持低延遲，Thinking 固定關閉。", "Luna Thinking は無効", "低遅延のため Thinking は常に無効です。")
        set_a11y(self.spin_luna_timeout, "Luna timeout seconds", "Luna 逾時秒數", "Maximum request time in seconds.", "要求的最長等待秒數。", "Luna のタイムアウト（秒）", "リクエストの最大待機時間です。")

    def _sync_provider_config_from_controller(self):
        self.set_provider_config(
            {
                "online_gemma": {
                    "enabled": getattr(self.controller, "online_gemma_enabled", False),
                    "auto_switch": getattr(self.controller.worker, "gemma_auto_switch_enabled", False),
                },
                "luna": {
                    "enabled": getattr(self.controller, "openai_enabled", getattr(self.controller, "luna_enabled", False)),
                    "reasoning_effort": "none",
                    "timeout_seconds": getattr(self.controller, "openai_timeout_seconds", getattr(self.controller, "luna_timeout_seconds", 60)),
                },
            }
        )
        value = self._controller_secret("google_api_key")
        if not value:
            value = str(getattr(self.controller.worker, "google_api_key", "") or "")
        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(value)
        self.input_api_key.blockSignals(False)
        self.input_luna_api_key.blockSignals(True)
        self.input_luna_api_key.setText(self._controller_secret("luna_api_key", "openai_api_key"))
        self.input_luna_api_key.blockSignals(False)

    def _set_provider_choice(self, provider_id):
        """Set the visible provider radio without invoking its gate callback."""
        provider_id = str(provider_id or "google")
        if provider_id not in self.provider_choice_buttons:
            provider_id = "google"
        button = self.provider_choice_buttons[provider_id]
        button.blockSignals(True)
        button.setChecked(True)
        button.blockSignals(False)
        self._selected_provider_id = provider_id
        self._sync_provider_disclosure_visibility()
        for choice_id, row in self.provider_choice_rows.items():
            row.setProperty("selected", choice_id == provider_id)
            style = row.style()
            if style is not None:
                style.unpolish(row)
                style.polish(row)
            row.update()

    def _sync_provider_disclosure_visibility(self):
        """Keep only the selected provider's settings body in the reading path."""
        selected = self._selected_provider_id
        show_disclosure = selected != "google"
        for provider_id, disclosure in self.provider_disclosures.items():
            disclosure.setVisible(show_disclosure and provider_id == selected)
        self.provider_status_frame.setVisible(show_disclosure)

    def _provider_for_current_model(self):
        model_id = str(getattr(self.controller.worker, "gemma_model", "") or "").strip().lower()
        if model_id in LOCAL_MODEL_IDS:
            return "local_gemma"
        return "online_gemma"

    def _controller_route_provider(self, provider_id):
        """Tell newer controllers which concrete registry provider is active."""
        route_id = {
            "google": "google",
            "local_gemma": "local_multimodal",
            "online_gemma": "gemma",
            "luna": "openai",
        }.get(str(provider_id or ""))
        if not route_id:
            return False
        return self._optional_controller_call("select_translation_provider", route_id)

    def _controller_route_choice(self):
        """Read the persisted first provider without exposing any secret."""
        chain = getattr(self.controller, "provider_chain", None)
        if chain is None:
            chain = getattr(getattr(self.controller, "worker", None), "provider_chain", None)
        if isinstance(chain, str):
            chain = [part.strip() for part in chain.split(",") if part.strip()]
        if not isinstance(chain, (list, tuple)) or not chain:
            return None
        first = str(chain[0] or "").strip().lower()
        worker = getattr(self.controller, "worker", None)
        if first != "google" and worker is not None and not getattr(worker, "use_gemma_translation", False):
            return "google"
        if first == "gemma" and self._provider_for_current_model() == "local_gemma":
            return "local_gemma"
        return {
            "google": "google",
            "local_multimodal": "local_gemma",
            "gemma": "online_gemma",
            "openai": "luna",
        }.get(first)

    def _restore_provider_choice(self):
        self._set_provider_choice(self._selected_provider_id or "google")

    def _select_remote_gemma(self):
        """Keep the canonical model selector aligned with Online Gemma."""
        current_model = str(self.cmb_ai_model.currentData() or "").strip().lower()
        if current_model not in LOCAL_MODEL_IDS:
            return True
        for index in range(self.cmb_ai_model.count()):
            model_id = str(self.cmb_ai_model.itemData(index) or "").strip().lower()
            if model_id and model_id not in LOCAL_MODEL_IDS:
                self.cmb_ai_model.setCurrentIndex(index)
                return True
        return False

    def on_provider_selected(self, provider_id):
        """Select one provider while preserving the existing model/key gates."""
        provider_id = str(provider_id or "")
        if provider_id == "google":
            self._set_provider_choice(provider_id)
            self.on_translate_mode_clicked(False)
            return

        if provider_id == "local_gemma":
            if not self._select_local_gemma():
                self._restore_provider_choice()
                self._show_provider_gate_message(
                    "Local Gemma is unavailable in this build. Choose another provider or install the full edition."
                    if str(self._ui_language()).lower().startswith("en") else
                    "このビルドでは Local Gemma を利用できません。他のプロバイダーを選択するか、フル版をインストールしてください。"
                    if self._ui_language() == "ja" else
                    "此版本找不到本機 Gemma 模型選項，請改選其他引擎或安裝完整版本。"
                )
                return
            self._set_provider_choice(provider_id)
            self.on_translate_mode_clicked(True)
            return

        if provider_id == "online_gemma":
            self._set_provider_choice(provider_id)
            self._ai_requested = True
            has_key = bool(self.input_api_key.text().strip() or self._controller_secret("google_api_key"))
            online_disclosure = self.provider_disclosures["online_gemma"]
            online_disclosure.set_expanded(True)
            if not has_key:
                if not self.chk_online_gemma_enabled.isChecked():
                    self.chk_online_gemma_enabled.setChecked(True)
                self._optional_controller_call("stage_translation_provider_setup", provider_id)
                self.input_api_key.setFocus()
                self.update_translate_summary()
                self._show_provider_gate_message(
                    "Online Gemma is paused until its API key is entered. Enter it below to continue."
                    if str(self._ui_language()).lower().startswith("en")
                    else "Online Gemma は API キーが入力されるまで一時停止しています。下に入力して続行してください。"
                    if self._ui_language() == "ja"
                    else "線上 Gemma 暫停翻譯，請在下方輸入 API Key 後繼續。"
                )
                return
            if not self._select_remote_gemma():
                self._optional_controller_call("stage_translation_provider_setup", provider_id)
                self._show_provider_gate_message(
                    "Choose an online Gemma model to continue."
                    if str(self._ui_language()).lower().startswith("en")
                    else "続行するには Online Gemma モデルを選択してください。"
                    if self._ui_language() == "ja"
                    else "請先選擇線上 Gemma 模型後繼續。"
                )
                return
            self.on_translate_mode_clicked(True)
            return

        if provider_id == "luna":
            self._set_provider_choice(provider_id)
            luna_disclosure = self.provider_disclosures["luna"]
            luna_disclosure.set_expanded(True)
            if not (self.input_luna_api_key.text().strip() or self._controller_secret("luna_api_key", "openai_api_key")):
                if not self.chk_luna_enabled.isChecked():
                    self.chk_luna_enabled.setChecked(True)
                self._optional_controller_call("stage_translation_provider_setup", provider_id)
                self.input_luna_api_key.setFocus()
                self._show_provider_gate_message(
                    "Luna is paused until its API key is entered. Enter it below to continue."
                    if str(self._ui_language()).lower().startswith("en")
                    else "Luna は API キーが入力されるまで一時停止しています。下に入力して続行してください。"
                    if self._ui_language() == "ja"
                    else "Luna 暫停翻譯，請在下方輸入 API Key 後繼續。"
                )
                return
            if not self.chk_luna_enabled.isChecked():
                self.chk_luna_enabled.setChecked(True)
            self._controller_route_provider(provider_id)
            self.update_translate_summary()

    def _show_provider_gate_message(self, message):
        self.lbl_translate_health_detail.setText(str(message))
        self.lbl_translate_health_detail.setVisible(True)
        self.lbl_translate_health_detail.setToolTip(str(message))
        if not hasattr(self, "_setup_reveal_timer"):
            self._setup_reveal_timer = QTimer(self)
            self._setup_reveal_timer.setSingleShot(True)
            self._setup_reveal_timer.timeout.connect(self._reveal_provider_setup)
        self._setup_reveal_timer.start(0)

    def _reveal_provider_setup(self):
        field = {
            "online_gemma": self.input_api_key,
            "luna": self.input_luna_api_key,
        }.get(self._selected_provider_id)
        if field is not None and field.isVisible():
            self.translation_scroll_area.ensureWidgetVisible(field, 12, 36)
            field.setFocus()

    def _select_local_gemma(self):
        """選取本地模型，並確保 controller 與面板即使原本同索引也會同步。"""
        index = self.cmb_ai_model.findData("gemma-3-4b-it-local")
        if index < 0:
            return False
        if self.cmb_ai_model.currentIndex() != index:
            self.cmb_ai_model.setCurrentIndex(index)
        elif (getattr(self.controller.worker, "gemma_model", "") or "").strip() not in LOCAL_MODEL_IDS:
            self.on_ai_model_changed(index)
        return (getattr(self.controller.worker, "gemma_model", "") or "").strip() in LOCAL_MODEL_IDS

    def on_use_local_gemma(self):
        """先明確選本地模型，再啟用 AI，不沿用雲端金鑰門檻。"""
        if not self._select_local_gemma():
            return
        self.on_translate_mode_clicked(True)

    def on_translate_mode_clicked(self, use_ai):
        has_key = bool(self.controller.worker.google_api_key.strip())
        is_local_model = (getattr(self.controller.worker, "gemma_model", "") or "").strip() in LOCAL_MODEL_IDS
        self._ai_requested = bool(use_ai)
        if use_ai:
            if not has_key and not is_local_model:
                is_local_model = self._select_local_gemma()
            self._expand_provider_for_model(getattr(self.controller.worker, "gemma_model", ""))
            if has_key or is_local_model:
                if callable(getattr(self.controller, "select_translation_provider", None)):
                    self._controller_route_provider(self._provider_for_current_model())
                else:
                    self.controller.toggle_ai_translation(True)
            else:
                self.controller.toggle_ai_translation(False)
                self.sync_from_controller()
                self.input_api_key.setFocus()
                return
        else:
            if callable(getattr(self.controller, "select_translation_provider", None)):
                self._controller_route_provider("google")
            else:
                self.controller.toggle_ai_translation(False)
        self.sync_from_controller()

    def on_api_key_text_changed(self, text):
        self.on_google_api_key_changed(text)
        if (text.strip() and self._ai_requested
                and not callable(getattr(self.controller, "select_translation_provider", None))
                and not getattr(self.controller.worker, "use_gemma_translation", False)):
            # Preserve the legacy two-button path used by older integrations.
            self.controller.toggle_ai_translation(True)
        self.update_translate_summary()

    def on_api_key_editing_finished(self):
        if (self.input_api_key.text().strip() and self._selected_provider_id == "online_gemma"
                and self._controller_route_choice() != "online_gemma"):
            self.on_provider_selected("online_gemma")

    def toggle_api_key_visible(self):
        visible = self.input_api_key.echoMode() != QLineEdit.Normal
        self.input_api_key.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self._set_visibility_button_text()

    def on_ai_model_changed(self, index):
        model_id = str(self.cmb_ai_model.itemData(index) or "").strip().lower()
        controller_combo = getattr(self.controller, "cmb_ai_model", None)
        controller_index = index
        find_data = getattr(controller_combo, "findData", None)
        if callable(find_data):
            matched_index = find_data(model_id)
            if matched_index >= 0:
                controller_index = matched_index
        self.controller.on_ai_model_changed(controller_index)
        if self._ai_requested or self._selected_provider_id in {"local_gemma", "online_gemma"}:
            self._expand_provider_for_model(model_id)
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

    def _expand_provider_for_model(self, model_id):
        """Reveal the provider the user just selected; never collapse peers."""
        provider_id = "local_gemma" if str(model_id or "").strip().lower() in LOCAL_MODEL_IDS else "online_gemma"
        disclosure = self.provider_disclosures.get(provider_id)
        if disclosure is not None:
            disclosure.set_expanded(True)

    def on_auto_switch_toggled(self, checked):
        self._optional_controller_call("set_gemma_auto_switch_mode", bool(checked))
        self.update_translate_summary()

    def _optional_controller_call(self, method_name, *args):
        callback = getattr(self.controller, method_name, None)
        if callable(callback):
            try:
                callback(*args)
            except Exception:
                # An older controller must not make the settings panel unusable.
                pass
            return True
        return False

    def on_online_gemma_enabled_changed(self, checked):
        if not self._optional_controller_call("on_online_gemma_enabled_changed", bool(checked)):
            self._optional_controller_call("on_gemma_online_enabled_changed", bool(checked))
        self.input_api_key.setEnabled(bool(checked))
        self.btn_api_key_visible.setEnabled(bool(checked))
        self.chk_auto_switch.setEnabled(bool(checked))
        self.update_provider_status_rows()

    def on_google_api_key_changed(self, text):
        if not self._optional_controller_call("on_google_api_key_changed", str(text or "")):
            self._optional_controller_call("on_api_key_changed", str(text or ""))
        self.update_provider_status_rows()

    def on_luna_enabled_changed(self, checked):
        if not self._optional_controller_call("on_luna_enabled_changed", bool(checked)):
            self._optional_controller_call("on_openai_enabled_changed", bool(checked))
        self.input_luna_api_key.setEnabled(bool(checked))
        self.spin_luna_timeout.setEnabled(bool(checked))
        self.update_provider_status_rows()

    def on_luna_api_key_changed(self, text):
        if not self._optional_controller_call("on_luna_api_key_changed", str(text or "")):
            self._optional_controller_call("on_openai_api_key_changed", str(text or ""))
        self.update_provider_status_rows()

    def on_luna_api_key_editing_finished(self):
        if (self.input_luna_api_key.text().strip() and self._selected_provider_id == "luna"
                and self._controller_route_choice() != "luna"):
            self.on_provider_selected("luna")

    def on_luna_reasoning_changed(self, index):
        value = "none"
        if not self._optional_controller_call("on_luna_reasoning_changed", value):
            self._optional_controller_call("on_openai_reasoning_changed", value)

    def on_luna_timeout_changed(self, value):
        if not self._optional_controller_call("on_luna_timeout_changed", int(value)):
            self._optional_controller_call("on_openai_timeout_changed", int(value))

    def _controller_secret(self, *names):
        for owner in (self.controller, getattr(self.controller, "worker", None)):
            for name in names:
                value = getattr(owner, name, None) if owner is not None else None
                if isinstance(value, str) and value:
                    return value
        return ""

    def _set_visibility_button_text(self):
        """Keep secret visibility control explicit and localized."""
        key = "translation_api_key_hide" if self.input_api_key.echoMode() == QLineEdit.Normal else "translation_api_key_show"
        self.btn_api_key_visible.setText(translation_tools.ui_text(self._ui_language(), key))

    @staticmethod
    def _coerce_runtime_snapshot(snapshot):
        """Normalize safe provider metadata into model-scoped records."""
        if snapshot is None:
            return []
        if isinstance(snapshot, dict):
            if snapshot.get("model"):
                return [snapshot]
            records = []
            for model_id, metadata in snapshot.items():
                if isinstance(metadata, dict):
                    record = dict(metadata)
                    record.setdefault("model", model_id)
                    records.append(record)
            return records
        if isinstance(snapshot, (list, tuple)):
            return [item for item in snapshot if isinstance(item, dict) and item.get("model")]
        return []

    def _online_gemma_runtime_snapshot(self):
        """Read an existing runtime snapshot without manufacturing readiness."""
        worker = getattr(self.controller, "worker", None)
        owners = [
            self.controller,
            worker,
            getattr(self.controller, "online_gemma_provider", None),
            getattr(worker, "gemma_translation_provider", None),
            getattr(worker, "gemma_provider", None),
        ]
        registry = getattr(worker, "translation_registry", None)
        if registry is not None:
            owners.append(registry)
            getter = getattr(registry, "get", None)
            if callable(getter):
                try:
                    owners.append(getter("gemma"))
                except Exception:
                    pass
        snapshot_names = (
            "online_gemma_runtime_snapshot",
            "gemma_runtime_snapshot",
            "provider_runtime_snapshot",
            "runtime_snapshot",
        )
        for owner in owners:
            if owner is None:
                continue
            for name in snapshot_names:
                candidate = getattr(owner, name, None)
                if callable(candidate):
                    try:
                        candidate = candidate()
                    except Exception:
                        continue
                records = self._coerce_runtime_snapshot(candidate)
                if records:
                    return records
            pool = getattr(owner, "_credential_pool", None)
            snapshot = getattr(pool, "snapshot", None)
            if callable(snapshot):
                try:
                    records = self._coerce_runtime_snapshot(snapshot())
                except Exception:
                    records = []
                if records:
                    return records
        return []

    def _online_gemma_model_statuses(self):
        records = self._online_gemma_runtime_snapshot()
        status_priority = {"unverified": 0, "ready": 1, "cooldown": 2, "using": 3}
        statuses = {model_id: "unverified" for model_id in ONLINE_GEMMA_MODEL_IDS}
        for record in records:
            model_id = str(record.get("model") or "").strip().lower()
            if model_id not in statuses:
                continue
            raw_status = str(record.get("status") or "").strip().lower().replace("-", "_")
            if bool(record.get("active")) or raw_status in {"leased", "active", "using", "in_use"}:
                status = "using"
            elif raw_status in {"cooldown", "backoff", "rate_limited", "quota"}:
                status = "cooldown"
            elif raw_status in {"ready", "available", "idle"}:
                status = "ready"
            else:
                status = "unverified"
            if status_priority[status] >= status_priority[statuses[model_id]]:
                statuses[model_id] = status
        return statuses, bool(records)

    def _online_gemma_rotation_detail(self, is_en):
        is_ja = self._ui_language() == "ja"
        worker = getattr(self.controller, "worker", None)
        preferred = str(getattr(worker, "gemma_model", "") or "").strip()
        active = str(getattr(worker, "active_gemma_model", "") or "").strip()
        if active not in ONLINE_GEMMA_MODEL_IDS:
            return ""
        if preferred in ONLINE_GEMMA_MODEL_IDS and preferred != active:
            return (
                f"Rotation trail: {preferred} → {active}"
                if is_en
                else f"切替履歴：{preferred} → {active}"
                if is_ja else f"輪替軌跡：{preferred} → {active}"
            )
        return (
            f"Rotation target: {active}"
            if is_en
            else f"切替先：{active}"
            if is_ja else f"輪替目標：{active}"
        )

    @staticmethod
    def _status_tone(status):
        """Map canonical/localized status text to a semantic visual tone."""
        value = str(status or "").strip().lower().replace("-", "_")
        if value in {"ready", "已就緒", "available", "idle"}:
            return "operational"
        if value in {"using", "使用中", "active", "in_use"}:
            return "accent"
        if any(token in value for token in ("cooldown", "冷卻", "quota", "額度", "limited", "受限", "rate_limited")):
            return "quota"
        if any(token in value for token in ("error", "failed", "failure", "unavailable", "auth", "錯誤", "失敗", "不可用")):
            return "error"
        return "subtext"

    @staticmethod
    def _status_label_style(theme, *, size, weight=800):
        return (
            f"QLabel {{ font-size: {int(size)}px; font-weight: {int(weight)}; color: {theme.subtext}; "
            "background: transparent; border: none; }"
            f" QLabel[statusTone=\"operational\"] {{ color: {theme.operational}; }}"
            f" QLabel[statusTone=\"accent\"] {{ color: {theme.accent}; }}"
            f" QLabel[statusTone=\"quota\"] {{ color: {theme.quota}; }}"
            f" QLabel[statusTone=\"error\"] {{ color: {theme.error}; }}"
            f" QLabel[statusTone=\"subtext\"] {{ color: {theme.subtext}; }}"
        )

    def _apply_status_tone(self, label, status):
        label.setProperty("statusTone", self._status_tone(status))
        style = label.style()
        if style is not None:
            style.unpolish(label)
            style.polish(label)
        label.update()

    def get_provider_config(self):
        """Return non-secret provider configuration suitable for settings data."""
        reasoning = "none"
        return {
            "online_gemma": {
                "enabled": self.chk_online_gemma_enabled.isChecked(),
                "auto_switch": self.chk_auto_switch.isChecked(),
                "models": ("gemma-4-26b-a4b-it", "gemma-4-31b-it"),
            },
            "luna": {
                "enabled": self.chk_luna_enabled.isChecked(),
                "model": DEFAULT_OPENAI_MODEL,
                "reasoning_effort": reasoning,
                "timeout_seconds": int(self.spin_luna_timeout.value()),
            },
        }

    def get_google_api_key_slots(self):
        """Legacy compatibility API; the provider now has one key."""
        return []

    def set_google_api_key_slots(self, slots):
        """Ignore legacy multi-key metadata; one DPAPI key is canonical."""
        return None

    def get_luna_config(self):
        """Return Luna's non-secret settings and fixed model identifier."""
        return dict(self.get_provider_config()["luna"])

    def set_luna_config(self, config):
        """Apply Luna's non-secret settings; the model remains fixed."""
        self.set_provider_config({"luna": config})

    def set_provider_config(self, config):
        """Apply non-secret provider config; unknown/secret fields are ignored."""
        if not isinstance(config, dict):
            return
        online = config.get("online_gemma", {})
        if isinstance(online, dict):
            self.chk_online_gemma_enabled.blockSignals(True)
            self.chk_online_gemma_enabled.setChecked(
                bool(online.get("enabled", self.chk_online_gemma_enabled.isChecked()))
            )
            self.chk_online_gemma_enabled.blockSignals(False)
            self.chk_auto_switch.blockSignals(True)
            self.chk_auto_switch.setChecked(bool(online.get("auto_switch", self.chk_auto_switch.isChecked())))
            self.chk_auto_switch.blockSignals(False)
        luna = config.get("luna", {})
        if isinstance(luna, dict):
            self.chk_luna_enabled.blockSignals(True)
            self.chk_luna_enabled.setChecked(bool(luna.get("enabled", self.chk_luna_enabled.isChecked())))
            self.chk_luna_enabled.blockSignals(False)
            index = self.cmb_luna_reasoning.findData("none")
            if index >= 0:
                self.cmb_luna_reasoning.blockSignals(True)
                self.cmb_luna_reasoning.setCurrentIndex(index)
                self.cmb_luna_reasoning.blockSignals(False)
            try:
                timeout = max(1, min(300, int(luna.get("timeout_seconds", 60))))
            except (TypeError, ValueError):
                timeout = 60
            self.spin_luna_timeout.blockSignals(True)
            self.spin_luna_timeout.setValue(timeout)
            self.spin_luna_timeout.blockSignals(False)
        self.update_provider_status_rows()

    def update_provider_status_rows(self):
        """Refresh concise provider state; never invents remaining quota."""
        if not self.provider_status_rows:
            return
        is_en = str(self._ui_language()).lower().startswith("en")
        is_ja = self._ui_language() == "ja"
        ready = "Ready" if is_en else ("準備完了" if is_ja else "已就緒")
        needs_setup = "Needs setup" if is_en else ("設定が必要" if is_ja else "需要設定")
        unverified = "Unverified" if is_en else ("未確認" if is_ja else "未驗證")
        cooldown = "Cooldown" if is_en else ("クールダウン中" if is_ja else "冷卻中")
        using = "Using" if is_en else ("使用中" if is_ja else "使用中")
        local_not_applicable = "Local status" if is_en else ("ローカル状態" if is_ja else "本地狀態")
        health = self._provider_health(local_only=True)
        local_ready = str(health.code).startswith("local_ready")
        local_status = ready if local_ready else (local_not_applicable if health.code == "google_ready" else needs_setup)
        self._set_provider_choice_status("local_gemma", local_status)
        self._set_provider_row(
            "local_gemma",
            local_status,
            health.detail if not local_ready else ("Local model status" if is_en else ("ローカルモデルの状態" if is_ja else "本地模型狀態")),
            local_not_applicable,
        )

        has_key = bool(self.input_api_key.text().strip())
        online_enabled = self.chk_online_gemma_enabled.isChecked()
        online_status = ready if online_enabled and has_key and self.model_availability_result.verified else (unverified if online_enabled and has_key else needs_setup)
        online_detail = ("Single API key configured" if is_en else ("API キーを設定済み" if is_ja else "已設定單一 API Key")) if has_key else ("Add the Gemma API key" if is_en else ("Gemma API キーを入力してください" if is_ja else "請輸入 Gemma API Key"))
        rotation_detail = self._online_gemma_rotation_detail(is_en)
        if rotation_detail:
            online_detail = f"{online_detail} · {rotation_detail}"
        self._set_provider_choice_status("online_gemma", online_status)
        self._set_provider_row("online_gemma", online_status, online_detail, "")

        model_statuses, has_runtime_snapshot = self._online_gemma_model_statuses()
        status_text = {
            "ready": ready,
            "unverified": unverified,
            "cooldown": cooldown,
            "using": using,
        }
        model_detail_text = {
            "ready": "Rate: Ready · Cooldown: None" if is_en else ("レート：利用可能 · クールダウン：なし" if is_ja else "速率：可用 · 冷卻：無"),
            "unverified": "Rate: Unverified · Cooldown: Unverified" if is_en else ("レート：未確認 · クールダウン：未確認" if is_ja else "速率：未驗證 · 冷卻：未驗證"),
            "cooldown": "Rate: Limited · Cooldown: Active" if is_en else ("レート：制限中 · クールダウン：実行中" if is_ja else "速率：受限 · 冷卻：進行中"),
            "using": "Rate: Active · Cooldown: None" if is_en else ("レート：稼働中 · クールダウン：なし" if is_ja else "速率：使用中 · 冷卻：無"),
        }
        for model_id, model_row in self.online_gemma_model_rows.items():
            status = model_statuses.get(model_id, "unverified")
            model_row["status"].setText(status_text[status])
            self._apply_status_tone(model_row["status"], status)
            model_row["detail"].setText(model_detail_text[status])

        luna_key = self.input_luna_api_key.text().strip()
        luna_status = unverified if self.chk_luna_enabled.isChecked() and luna_key else needs_setup
        self._set_provider_choice_status("google", ready)
        self._set_provider_choice_status("luna", luna_status)
        self._set_provider_row("luna", luna_status, "Text + image input" if is_en else ("テキストと画像の入力に対応" if is_ja else "支援文字與圖片輸入"), "")

    def _set_provider_choice_status(self, provider_id, status):
        row = self.provider_choice_rows.get(provider_id)
        if row is None:
            return
        row.status_label.setText(str(status or ""))
        self._apply_status_tone(row.status_label, status)

    def _set_provider_row(self, provider_id, status, detail, scope):
        row = self.provider_status_rows[provider_id]
        row["status"].setText(status)
        self._apply_status_tone(row["status"], status)
        row["detail"].setText(detail)
        row["scope"].setText(scope)
        disclosure = self.provider_disclosures.get(provider_id)
        if disclosure is not None:
            is_en = str(self._ui_language()).lower().startswith("en")
            is_ja = self._ui_language() == "ja"
            capability = {
                "local_gemma": "Local model · no cloud key required" if is_en else ("ローカルモデル · クラウドキー不要" if is_ja else "本地模型・不需雲端金鑰"),
                "online_gemma": "One key · two Gemma models · thinking minimal" if is_en else ("1 つのキー · 2 つの Gemma モデル · thinking minimal" if is_ja else "單一 Key・雙 Gemma 模型・thinking minimal"),
                "luna": "Text + image input · reasoning off" if is_en else ("テキストと画像に対応 · reasoning オフ" if is_ja else "文字＋圖片輸入・reasoning 固定關閉"),
            }.get(provider_id, disclosure.capability)
            disclosure.set_summary(status, capability)
            disclosure.header.setProperty("statusTone", self._status_tone(status))
            style = disclosure.header.style()
            if style is not None:
                style.unpolish(disclosure.header)
                style.polish(disclosure.header)

    def on_advanced_tuning_toggled(self, checked):
        self.lbl_gemma_prompt.setVisible(bool(checked))
        self.input_gemma_prompt.setVisible(bool(checked))
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
            "gemma-3-4b-it-local": {
                "en": "Full edition includes the model; light edition downloads to AppData. Read the <a href=\"https://ai.google.dev/gemma/terms\">Gemma Terms of Use</a> before enabling.",
                "zh-TW": "完整包內附模型；輕量包下載至 AppData。啟用前請閱讀 <a href=\"https://ai.google.dev/gemma/terms\">Gemma 使用條款</a>。",
                "ja": "フル版にはモデルが含まれます。ライト版では AppData にダウンロードします。有効化する前に <a href=\"https://ai.google.dev/gemma/terms\">Gemma 利用規約</a>をお読みください。",
            },
            "gemma-3-27b-it": {
                "en": "Best balance for screenshot translation.",
                "zh-TW": "截圖翻譯的平衡首選。",
                "ja": "スクリーンショット翻訳に適したバランスのモデルです。",
            },
            "gemma-4-31b-it": {
                "en": "Large model with stronger vision, but slower.",
                "zh-TW": "更強的視覺能力，但速度較慢。",
                "ja": "視覚能力に優れた大型モデルですが、処理は遅めです。",
            },
            "gemini-2.5-pro": {
                "en": "Strong paid model; can be slower or rate-limited.",
                "zh-TW": "付費強力模型，可能較慢或受限。",
                "ja": "高性能の有料モデルです。処理が遅い場合や利用制限がかかる場合があります。",
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

    def refresh_localized_texts(self):
        lang = self._ui_language()
        is_en = str(lang).lower().startswith("en")
        is_ja = lang == "ja"

        def localized(en, zh, ja):
            return en if is_en else (ja if is_ja else zh)

        self.lbl_translate.setText(localized("Translation", "翻譯引擎", "翻訳"))
        self.lbl_translate_hint.setText(
            localized("Choose how to translate.", "選擇適合你的翻譯方式", "翻訳方法を選択してください。")
        )
        self.lbl_translate_mode.setText(localized("Provider", "翻譯來源", "プロバイダー"))
        provider_copy = {
            "google": (
                ("Google Translate", "No API key required") if is_en
                else (("Google 翻訳", "API キー不要") if is_ja else ("Google 翻譯", "不需 API Key"))
            ),
            "local_gemma": (
                ("Local Gemma", "Local model · no cloud key required") if is_en
                else (("ローカル Gemma", "ローカルモデル · クラウドキー不要") if is_ja else ("本機 Gemma", "本地模型・不需雲端金鑰"))
            ),
            "online_gemma": (
                ("Online Gemma", "One key · two Gemma models") if is_en
                else (("Online Gemma", "1 つのキー · 2 つの Gemma モデル") if is_ja else ("線上 Gemma", "單一 Key・雙 Gemma 模型"))
            ),
            "luna": (
                ("Luna", "Text + image input · Luna key required") if is_en
                else (("Luna", "テキストと画像に対応 · Luna キーが必要") if is_ja else ("Luna", "文字＋圖片輸入・需要 Luna Key"))
            ),
        }
        for provider_id, (name, description) in provider_copy.items():
            row = self.provider_choice_rows[provider_id]
            row.name_label.setText(name)
            row.detail_label.setText(description)
        self._set_visibility_button_text()
        self.lbl_api_key.setText(localized("Online Gemma API key", "Online Gemma API Key", "Online Gemma API キー"))
        self.input_api_key.setPlaceholderText(localized("Gemma API key", "Gemma API Key", "Gemma API キー"))
        self.lbl_online_gemma.setText("Online Gemma" if is_en else "Online Gemma")
        self.chk_online_gemma_enabled.setText(localized("Enable Online Gemma", "啟用 Online Gemma", "Online Gemma を有効化"))
        self.lbl_auto_switch.setText(
            "When enabled, rotate between gemma-4-26b-a4b-it and gemma-4-31b-it after a model limit."
            if is_en else ("モデルの制限時に gemma-4-26b-a4b-it と gemma-4-31b-it を自動で切り替えます。" if is_ja else "啟用後，模型受限時會在 gemma-4-26b-a4b-it 與 gemma-4-31b-it 間自動輪替。")
        )
        self.lbl_online_gemma_models.setText(
            "Models: gemma-4-26b-a4b-it · gemma-4-31b-it · thinking minimal"
            if is_en else ("モデル：gemma-4-26b-a4b-it · gemma-4-31b-it · thinking minimal" if is_ja else "模型：gemma-4-26b-a4b-it、gemma-4-31b-it；thinking：minimal")
        )
        self.lbl_luna.setText("Luna" if is_en else "Luna")
        self.chk_luna_enabled.setText(localized("Enable Luna", "啟用 Luna", "Luna を有効化"))
        self.lbl_luna_api_key.setText(localized("Luna API key", "Luna API Key", "Luna API キー"))
        self.lbl_luna_model_label.setText(localized("Model (fixed)", "模型（固定）", "モデル（固定）"))
        self.lbl_luna_capabilities.setText(
            "Capabilities: text + image input. Connectivity and quota are checked at request time."
            if is_en
            else ("テキストと画像の入力に対応。接続と利用枠はリクエスト送信時に確認します。" if is_ja else "能力：文字＋圖片輸入。連線與額度會在要求送出時檢查。")
        )
        self.lbl_luna_reasoning.setText(localized("Thinking (fixed off)", "Thinking（固定關閉）", "Thinking（固定オフ）"))
        self.lbl_luna_timeout.setText(localized("Timeout", "逾時", "タイムアウト"))
        self.spin_luna_timeout.setSuffix(" sec" if is_en else (" 秒" if is_ja else " 秒"))
        self.cmb_luna_reasoning.setItemText(0, localized("Off", "關閉", "オフ"))
        self.lbl_ai_model.setText(translation_tools.ui_text(lang, "translation_ai_model"))
        self.btn_use_local_gemma.setText(
            localized("Use local Gemma 3 4B", "使用本地 Gemma 3 4B", "ローカル Gemma 3 4B を使用")
        )
        self.lbl_local_model_terms.setText(self._ai_model_note_text("gemma-3-4b-it-local"))
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
        self.lbl_local_multimodal_base_url.setText(
            translation_tools.ui_text(lang, "translation_local_multimodal_base_url")
        )
        self.lbl_local_multimodal_model.setText(
            translation_tools.ui_text(lang, "translation_local_multimodal_model")
        )
        self.lbl_local_multimodal_timeout.setText(
            translation_tools.ui_text(lang, "translation_local_multimodal_timeout")
        )
        self.spin_local_multimodal_timeout.setSuffix(" sec" if is_en else " 秒")
        self.btn_advanced_tuning.setText(localized("Advanced prompt & tuning", "進階提示詞與參數", "プロンプトと詳細設定"))
        self._configure_provider_accessibility()
        self.update_ai_model_notes()

    def set_translate_mode(self, use_ai):
        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not use_ai)
        self.btn_translate_ai.setChecked(use_ai)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)
        if use_ai:
            if self._selected_provider_id != "luna":
                self._set_provider_choice(self._provider_for_current_model())
        else:
            self._set_provider_choice("google")
        enabled = bool(use_ai or self._ai_requested)
        self.set_translate_advanced_visible(enabled)
        self.update_key_state(enabled)
        model_id = str(self.cmb_ai_model.currentData() or "").strip().lower()
        if use_ai and self._selected_provider_id != "luna" and model_id not in LOCAL_MODEL_IDS and not self.input_api_key.text().strip():
            self.input_api_key.setFocus()
        self.update_translate_summary()

    def set_translate_advanced_visible(self, visible):
        self.advanced_translate_frame.setVisible(True)

    def _provider_health(self, *, local_only=False):
        worker = self.controller.worker
        model_id = str(self.cmb_ai_model.currentData() or "") if self.cmb_ai_model.count() else ""
        model_label = self.cmb_ai_model.currentText() if self.cmb_ai_model.count() else "AI"
        if local_only:
            model_id = "gemma-3-4b-it-local"
            model_label = "Gemma 3 4B (Local)"
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
            ai_requested=local_only or bool(self._ai_requested),
            ai_enabled=local_only or bool(self.btn_translate_ai.isChecked()),
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
        self.update_provider_status_rows()

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
        self.update_local_multimodal_state()
        # Online provider credentials are independently enabled; their
        # checkboxes remain reachable even when legacy AI mode is off.
        self.chk_online_gemma_enabled.setEnabled(True)
        self.input_api_key.setEnabled(self.chk_online_gemma_enabled.isChecked())
        self.btn_api_key_visible.setEnabled(self.chk_online_gemma_enabled.isChecked())
        self.chk_auto_switch.setEnabled(self.chk_online_gemma_enabled.isChecked())
        self.chk_luna_enabled.setEnabled(True)
        luna_enabled = self.chk_luna_enabled.isChecked()
        self.input_luna_api_key.setEnabled(luna_enabled)
        self.cmb_luna_reasoning.setEnabled(False)
        self.spin_luna_timeout.setEnabled(luna_enabled)

    def sync_from_controller(self):
        self.refresh_localized_texts()
        ai_enabled = bool(getattr(self.controller.worker, "use_gemma_translation", False))
        if ai_enabled:
            self._ai_requested = True

        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(self.controller.worker.google_api_key)
        self.input_api_key.blockSignals(False)

        # New provider settings are optional controller attributes during the
        # compatibility window.  Secrets are read only into password fields;
        # they are never copied into the non-secret provider config object.
        self.set_provider_config(
            {
                "online_gemma": {
                    "enabled": getattr(self.controller, "online_gemma_enabled", False),
                    "auto_switch": getattr(self.controller.worker, "gemma_auto_switch_enabled", False),
                },
                "luna": {
                    "enabled": getattr(
                        self.controller,
                        "openai_enabled",
                        getattr(self.controller, "luna_enabled", False),
                    ),
                    "reasoning_effort": getattr(
                        self.controller,
                        "openai_reasoning_effort",
                        "none",
                    ),
                    "timeout_seconds": getattr(
                        self.controller,
                        "openai_timeout_seconds",
                        getattr(self.controller, "luna_timeout_seconds", 60),
                    ),
                },
            }
        )
        secret = self._controller_secret("google_api_key")
        if not secret:
            secret = str(getattr(self.controller.worker, "google_api_key", "") or "")
        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(secret)
        self.input_api_key.blockSignals(False)
        luna_secret = self._controller_secret("luna_api_key", "openai_api_key")
        self.input_luna_api_key.blockSignals(True)
        self.input_luna_api_key.setText(luna_secret)
        self.input_luna_api_key.blockSignals(False)

        controller_combo = self.controller.cmb_ai_model
        controller_index = controller_combo.currentIndex()
        item_data = getattr(controller_combo, "itemData", None)
        controller_model = item_data(controller_index) if callable(item_data) else None
        panel_model_index = (
            self.cmb_ai_model.findData(controller_model)
            if controller_model is not None
            else controller_index
        )
        self.cmb_ai_model.blockSignals(True)
        if panel_model_index >= 0:
            self.cmb_ai_model.setCurrentIndex(panel_model_index)
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

        pending_provider = getattr(self.controller, "pending_translation_provider_id", None)
        persisted_provider = self._controller_route_choice()
        if pending_provider in self.provider_choice_buttons:
            self._set_provider_choice(pending_provider)
        elif persisted_provider is not None:
            self._set_provider_choice(persisted_provider)
        elif ai_enabled:
            self._set_provider_choice(self._provider_for_current_model())
        elif getattr(self.controller, "openai_enabled", False) and self.input_luna_api_key.text().strip():
            self._set_provider_choice("luna")
        else:
            self._set_provider_choice("google")

        enabled = bool(ai_enabled or self._ai_requested)
        self.set_translate_advanced_visible(enabled)
        self.update_key_state(enabled)
        self.update_local_multimodal_state()
        result = getattr(self.controller, "remote_model_availability", None)
        if isinstance(result, ModelDiscoveryResult):
            self.set_model_availability_result(result)
        self.update_key_state(enabled)
        self.update_translate_summary()

    def update_theme(self, theme_mode):
        self._theme_mode = theme_mode
        theme = resolve_theme(theme_mode)
        self.refresh_localized_texts()
        card_bg = theme.get("settings_card_bg", theme.panel_bg)
        card_highlight = theme.get("settings_card_highlight", theme.border)
        card_edge = theme.get("settings_card_edge", theme.panel_border)
        self.card_translate.setStyleSheet(
            f"QFrame#translationCardHost {{ background-color: {card_bg}; border: 1px solid {theme.panel_border}; "
            f"border-top-color: {card_highlight}; border-bottom: 2px solid {card_edge}; border-radius: 16px; }}"
        )
        self.translation_scroll_area.setStyleSheet(
            "QScrollArea#translationSettingsScrollArea { background: transparent; border: none; }"
            " QWidget#qt_scrollarea_viewport { background: transparent; border: none; }"
            f" QScrollBar:vertical {{ background: {theme.control_bg}; width: 10px; margin: 4px 2px; border: none; }}"
            f" QScrollBar::handle:vertical {{ background: {theme.border}; min-height: 32px; border-radius: 5px; }}"
            f" QScrollBar::handle:vertical:hover {{ background: {theme.accent}; }}"
            " QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; border: none; }"
            " QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
        )
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

        provider_surface = theme.get("provider_surface", theme.input_bg)
        provider_border = theme.get("provider_border", theme.border)
        provider_top = theme.get("provider_top_highlight", theme.border)
        provider_edge = theme.get("provider_bottom_edge", theme.border)
        nested_surface = theme.get("nested_model_surface", theme.input_bg)
        nested_border = theme.get("nested_model_border", theme.border)
        provider_metadata = theme.get("provider_metadata", theme.subtext)
        provider_selection_accent = (
            "#AD9AFF" if theme.key == "dark"
            else "#7052D6" if theme.key == "light"
            else theme.accent
        )
        provider_selection_soft = (
            "rgba(173, 154, 255, 42)" if theme.key == "dark"
            else "rgba(112, 82, 214, 30)" if theme.key == "light"
            else theme.accent_soft
        )
        self.mode_buttons.setStyleSheet("QWidget#providerChoiceRows { background: transparent; border: none; }")
        provider_row_style = (
            f"QFrame#providerChoiceRow_google, QFrame#providerChoiceRow_local_gemma, "
            f"QFrame#providerChoiceRow_online_gemma, QFrame#providerChoiceRow_luna {{ "
            f"background-color: {provider_surface}; border: 1px solid {provider_border}; border-radius: 8px; }}"
            f" QFrame#providerChoiceRow_google:hover, QFrame#providerChoiceRow_local_gemma:hover, "
            f"QFrame#providerChoiceRow_online_gemma:hover, QFrame#providerChoiceRow_luna:hover {{ border-color: {provider_selection_accent}; }}"
            f" QFrame#providerChoiceRow_google[selected=\"true\"], QFrame#providerChoiceRow_local_gemma[selected=\"true\"], "
            f"QFrame#providerChoiceRow_online_gemma[selected=\"true\"], QFrame#providerChoiceRow_luna[selected=\"true\"] {{ "
            f"background-color: {provider_selection_soft}; border: 2px solid {provider_selection_accent}; }}"
            f" QRadioButton {{ background: transparent; color: {theme.text}; font-size: 13px; border:2px solid transparent; border-radius:4px; }}"
            f" QRadioButton:focus {{ border:2px solid {theme.focus}; }}"
            f" QRadioButton::indicator {{ width:14px; height:14px; border:2px solid {provider_selection_accent}; border-radius:9px; background:transparent; }}"
            f" QRadioButton::indicator:checked {{ background:{provider_selection_accent}; border-color:{provider_selection_accent}; }}"
        )
        for row in self.provider_choice_rows.values():
            row.setStyleSheet(provider_row_style)
            row.name_label.setStyleSheet(
                f"font-size: 13px; font-weight: 800; color: {theme.text}; background: transparent; border: none;"
            )
            row.detail_label.setStyleSheet(
                f"font-size: 11px; color: {provider_metadata}; background: transparent; border: none;"
            )
            row.status_label.setStyleSheet(self._status_label_style(theme, size=10))
            self._apply_status_tone(row.status_label, row.status_label.text())

        self.input_api_key.setStyleSheet(
            f"QLineEdit {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-top-color: {card_highlight}; border-bottom: 2px solid {card_edge}; "
            f"border-radius: 6px; padding: 7px; font-size: 13px; }}"
            f" QLineEdit:hover {{ border-color: {theme.accent}; border-top-color: {card_highlight}; }}"
            f" QLineEdit:focus {{ border: 2px solid {theme.focus}; padding: 6px; }}"
            f" QLineEdit:disabled {{ background-color: {theme.control_disabled_bg}; color: {theme.control_disabled_fg}; border-color: {theme.control_disabled_bg}; }}"
        )
        self.btn_api_key_visible.setStyleSheet(theme.button_qss(radius=8))
        self.btn_refresh_model_availability.setStyleSheet(theme.button_qss(radius=8))
        self.cmb_ai_model.setStyleSheet(theme.combo_qss(radius=6))
        self.input_gemma_prompt.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-top-color: {card_highlight}; border-bottom: 2px solid {card_edge}; "
            f"border-radius: 6px; padding: 6px; font-size: 13px; }}"
            f" QPlainTextEdit:hover {{ border-color: {theme.accent}; border-top-color: {card_highlight}; }}"
            f" QPlainTextEdit:focus {{ border: 2px solid {theme.focus}; padding: 5px; }}"
            f" QPlainTextEdit:disabled {{ background-color: {theme.control_disabled_bg}; color: {theme.control_disabled_fg}; border-color: {theme.control_disabled_bg}; }}"
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
            f"border-top-color: {card_highlight}; border-bottom: 2px solid {card_edge}; "
            f"border-radius: 6px; padding: 7px; font-size: 13px;"
        )
        self.input_local_multimodal_model.setStyleSheet(
            f"background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-top-color: {card_highlight}; border-bottom: 2px solid {card_edge}; "
            f"border-radius: 6px; padding: 7px; font-size: 13px;"
        )
        self.chk_local_multimodal_enabled.setStyleSheet(
            f"QCheckBox {{ color: {theme.subtext}; background: transparent; border: none; font-size: 12px; font-weight: 700; }}"
        )
        self.chk_local_multimodal_cpu_only.setStyleSheet(
            f"QCheckBox {{ color: {theme.subtext}; background: transparent; border: none; font-size: 12px; font-weight: 700; }}"
        )
        spinbox_style = (
            f"QDoubleSpinBox, QSpinBox {{ background-color: {theme.input_bg}; color: {theme.text}; "
            f"border: 1px solid {theme.border}; border-top-color: {card_highlight}; "
            f"border-bottom: 2px solid {card_edge}; border-radius: 6px; padding: 4px; }} "
            f"QDoubleSpinBox:focus, QSpinBox:focus {{ border: 2px solid {theme.focus}; padding: 3px; }} "
            f"QDoubleSpinBox:disabled, QSpinBox:disabled {{ background-color: {theme.control_disabled_bg}; "
            f"color: {theme.control_disabled_fg}; border-color: {theme.control_disabled_bg}; }}"
        )
        self.spin_local_gemma_temp.setStyleSheet(spinbox_style)
        self.spin_local_gemma_repeat.setStyleSheet(spinbox_style)
        self.spin_local_multimodal_timeout.setStyleSheet(spinbox_style)
        self.tuning_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.provider_status_frame.setStyleSheet(
            f"QFrame#providerStatusCards {{ background: transparent; border: none; }}"
            f"QFrame#providerDisclosure_local_gemma, QFrame#providerDisclosure_online_gemma, QFrame#providerDisclosure_luna {{ "
            f"background: transparent; border: none; }}"
            f"QToolButton#providerDisclosureHeader_local_gemma, QToolButton#providerDisclosureHeader_online_gemma, QToolButton#providerDisclosureHeader_luna {{ "
            f"background-color: {provider_surface}; color: {theme.text}; border: 1px solid {provider_border}; "
            f"border-top-color: {provider_top}; border-bottom: 2px solid {provider_edge}; border-radius: 8px; "
            "padding: 7px 10px; text-align: left; font-size: 13px; font-weight: 700; }"
            f"QToolButton#providerDisclosureHeader_local_gemma:hover, QToolButton#providerDisclosureHeader_online_gemma:hover, QToolButton#providerDisclosureHeader_luna:hover {{ border-color: {theme.accent}; border-top-color: {provider_top}; }}"
            f"QToolButton#providerDisclosureHeader_local_gemma:focus, QToolButton#providerDisclosureHeader_online_gemma:focus, QToolButton#providerDisclosureHeader_luna:focus {{ border: 2px solid {theme.focus}; padding: 6px 9px; }}"
            f"QToolButton#providerDisclosureHeader_local_gemma:checked, QToolButton#providerDisclosureHeader_online_gemma:checked, QToolButton#providerDisclosureHeader_luna:checked {{ border-bottom: 1px solid {provider_border}; border-radius: 8px 8px 0 0; }}"
            f"QToolButton#providerDisclosureHeader_local_gemma[statusTone=\"operational\"], QToolButton#providerDisclosureHeader_online_gemma[statusTone=\"operational\"], QToolButton#providerDisclosureHeader_luna[statusTone=\"operational\"] {{ color: {theme.operational}; }}"
            f"QToolButton#providerDisclosureHeader_local_gemma[statusTone=\"accent\"], QToolButton#providerDisclosureHeader_online_gemma[statusTone=\"accent\"], QToolButton#providerDisclosureHeader_luna[statusTone=\"accent\"] {{ color: {theme.accent}; }}"
            f"QToolButton#providerDisclosureHeader_local_gemma[statusTone=\"quota\"], QToolButton#providerDisclosureHeader_online_gemma[statusTone=\"quota\"], QToolButton#providerDisclosureHeader_luna[statusTone=\"quota\"] {{ color: {theme.quota}; }}"
            f"QToolButton#providerDisclosureHeader_local_gemma[statusTone=\"error\"], QToolButton#providerDisclosureHeader_online_gemma[statusTone=\"error\"], QToolButton#providerDisclosureHeader_luna[statusTone=\"error\"] {{ color: {theme.error}; }}"
            f"QLabel#providerDisclosureCapability_local_gemma, QLabel#providerDisclosureCapability_online_gemma, QLabel#providerDisclosureCapability_luna {{ "
            f"background-color: {provider_surface}; color: {provider_metadata}; border-left: 1px solid {provider_border}; border-right: 1px solid {provider_border}; "
            "padding: 1px 10px 6px; font-size: 10px; }"
            f"QFrame#providerDisclosureBody_local_gemma, QFrame#providerDisclosureBody_online_gemma, QFrame#providerDisclosureBody_luna {{ "
            f"background-color: {provider_surface}; border: 1px solid {provider_border}; border-top: none; "
            f"border-bottom: 2px solid {provider_edge}; border-radius: 0 0 8px 8px; }}"
            f"QFrame#providerStatusCard_local_gemma, QFrame#providerStatusCard_online_gemma, QFrame#providerStatusCard_luna {{ background: transparent; border: none; }}"
            f"QFrame#onlineGemmaModelCards {{ background: transparent; border: none; }}"
            f"QFrame#onlineGemmaModelCard_gemma-4-26b-a4b-it, QFrame#onlineGemmaModelCard_gemma-4-31b-it {{ "
            f"background: {nested_surface}; border: 1px solid {nested_border}; border-radius: 6px; }}"
        )
        provider_name_style = f"font-size: 13px; font-weight: 800; color: {theme.text}; background: transparent; border: none;"
        provider_status_style = self._status_label_style(theme, size=11)
        provider_detail_style = f"font-size: 11px; color: {provider_metadata}; background: transparent; border: none;"
        provider_scope_style = f"font-size: 10px; color: {provider_metadata}; background: transparent; border: none;"
        for row in self.provider_status_rows.values():
            row["name"].setStyleSheet(provider_name_style)
            row["status"].setStyleSheet(provider_status_style)
            self._apply_status_tone(row["status"], row["status"].text())
            row["detail"].setStyleSheet(provider_detail_style)
            row["scope"].setStyleSheet(provider_scope_style)
        model_name_style = f"font-size: 12px; font-weight: 700; color: {theme.text}; background: transparent; border: none;"
        model_status_style = self._status_label_style(theme, size=11)
        model_detail_style = f"font-size: 10px; color: {provider_metadata}; background: transparent; border: none;"
        for row in self.online_gemma_model_rows.values():
            row["name"].setStyleSheet(model_name_style)
            row["status"].setStyleSheet(model_status_style)
            self._apply_status_tone(row["status"], row["status"].text())
            row["detail"].setStyleSheet(model_detail_style)
        self.online_provider_frame.setStyleSheet(
            "QFrame#onlineGemmaSettings { background: transparent; border: none; }"
        )
        self.luna_provider_frame.setStyleSheet(
            "QFrame#lunaSettings { background: transparent; border: none; }"
        )
        self.lbl_auto_switch.setStyleSheet(f"font-size: 11px; color: {provider_metadata}; background: transparent; border: none;")
        self.lbl_online_gemma_models.setStyleSheet(f"font-size: 11px; color: {provider_metadata}; background: transparent; border: none;")
        self.lbl_online_gemma.setStyleSheet(accent_label_style)
        self.lbl_luna.setStyleSheet(accent_label_style)
        self.lbl_luna_api_key.setStyleSheet(field_label_style)
        self.lbl_luna_model_label.setStyleSheet(field_label_style)
        self.lbl_luna_model.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {theme.text}; background: transparent; border: none;")
        self.lbl_luna_capabilities.setStyleSheet(f"font-size: 11px; color: {provider_metadata}; background: transparent; border: none;")
        self.lbl_luna_reasoning.setStyleSheet(field_label_style)
        self.lbl_luna_timeout.setStyleSheet(field_label_style)
        self.chk_online_gemma_enabled.setStyleSheet(f"QCheckBox {{ color: {theme.subtext}; background: transparent; border: none; font-size: 12px; font-weight: 700; }}")
        self.chk_luna_enabled.setStyleSheet(f"QCheckBox {{ color: {theme.subtext}; background: transparent; border: none; font-size: 12px; font-weight: 700; }}")
        self.input_api_key.setStyleSheet(
            f"QLineEdit {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; border-radius: 6px; padding: 7px; font-size: 13px; }}"
            f" QLineEdit:focus {{ border: 2px solid {theme.accent}; }}"
        )
        self.btn_api_key_visible.setStyleSheet(theme.button_qss(radius=8))
        self.btn_refresh_model_availability.setStyleSheet(theme.button_qss(radius=8))
        self.input_luna_api_key.setStyleSheet(
            f"QLineEdit {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; border-radius: 6px; padding: 7px; font-size: 13px; }}"
            f" QLineEdit:focus {{ border: 2px solid {theme.accent}; }}"
        )
        self.cmb_luna_reasoning.setStyleSheet(theme.combo_qss(radius=6))
        self.spin_luna_timeout.setStyleSheet(spinbox_style)
        self.update_translate_summary()
