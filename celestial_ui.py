"""CloudHime 天宮書房：經使用者核准的桌面 UI 概念。

THESIS: 小窗負責翻譯，大窗按任務分頁；不再同時攤開所有設定。
OWN-WORLD: 珍珠白／星夜藍紫、紫色主操作，右側獨立偵探公主插畫。
STORY: 選擇引擎，設定擷取與顯示，需要時研究作品，再回小窗翻譯。
FIRST VIEWPORT: 左側四分頁操作區、右側等比例插畫、固定儲存列。
FORM: 使用者已核准概念圖；沿用 PySide6 原生控制與既有訊號。
FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QTabBar, QStackedWidget, QBoxLayout, QToolButton


class PrincessPortrait(QWidget):
    """Paint the right-hand character without stretching or clipping her hat."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = QPixmap()
        self.setMinimumWidth(250)
        self.setAccessibleName("CloudHime")

    def set_art(self, path):
        self._image = QPixmap(str(path)) if path else QPixmap()
        self.update()

    def paintEvent(self, event):
        if self._image.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        # The authored character occupies the right 44% of the landscape asset.
        source = QRectF(self._image.width() * .56, 0, self._image.width() * .44, self._image.height())
        ratio = self.width() / max(1, self.height())
        if source.width() / source.height() > ratio:
            width = source.height() * ratio
            source.setLeft(source.center().x() - width / 2)
            source.setWidth(width)
        else:
            height = source.width() / ratio
            source.setTop((source.height() - height) / 2)
            source.setHeight(height)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 14, 14)
        painter.setClipPath(clip)
        painter.drawPixmap(QRectF(self.rect()), self._image, source)


class PrincessAvatar(PrincessPortrait):
    """Small identity mark, using the same artwork as the settings portrait."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setFixedSize(40, 40)

    def paintEvent(self, event):
        if self._image.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addEllipse(QRectF(self.rect()))
        painter.setClipPath(clip)
        side = self._image.height() * .36
        source = QRectF(self._image.width() * .79 - side / 2,
                        self._image.height() * .13, side, side)
        painter.drawPixmap(QRectF(self.rect()), self._image, source)


def _page(*widgets):
    content = QWidget()
    content.setObjectName("celestialPageContent")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(18, 16, 18, 28)
    layout.setSpacing(18)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    return scroll


def compose_settings(window, top, theme_chip, language_chip, knowledge_chip,
                     knowledge_options, body, footer_layout):
    """Move controls, preserving signal wiring and Save/Cancel semantics."""
    window.setMinimumSize(900, 620)
    window.resize(1120, 760)
    window.lbl_page_subtitle.hide()
    window.lbl_brand_icon.hide()
    footer_layout.insertWidget(0, window.btn_export_history)
    window.btn_reset_defaults.setMinimumWidth(0)
    window.btn_reset_defaults.setMaximumWidth(220)

    # Detach old top-level rows before installing the research page.
    top.removeItem(knowledge_options)
    research_options = QWidget()
    research_options.setLayout(knowledge_options)
    research_options.layout().setContentsMargins(0, 0, 0, 0)
    knowledge_options.setDirection(QBoxLayout.TopToBottom)
    if knowledge_options.itemAt(0).spacerItem() is not None:
        knowledge_options.takeAt(0)
    knowledge_options.setSpacing(8)
    knowledge_chip.layout().setDirection(QBoxLayout.TopToBottom)
    window.research_title_label = QLabel()
    window.research_title_label.setBuddy(window.input_knowledge_title)
    knowledge_chip.layout().insertWidget(0, window.research_title_label)
    window.research_model_label = QLabel()
    window.research_model_label.setBuddy(window.cmb_knowledge_model)
    knowledge_options.insertWidget(0, window.research_model_label)
    window.research_source_label = QLabel()
    window.research_source_label.setBuddy(window.input_knowledge_sources)
    knowledge_options.insertWidget(2, window.research_source_label)
    window.lbl_knowledge_work.hide()
    window.input_knowledge_title.setMaximumWidth(16777215)
    window.lbl_knowledge_status.setMaximumWidth(16777215)
    window.lbl_knowledge_status.setWordWrap(True)
    window.research_hint = QLabel()
    window.research_hint.setWordWrap(True)
    window.research_heading = QLabel()
    window.appearance_heading = QLabel()
    window.appearance_hint = QLabel()
    window.appearance_hint.setWordWrap(True)
    window.screenshot_prompt_toggle = QToolButton()
    window.screenshot_prompt_toggle.setCheckable(True)
    window.screenshot_prompt_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    window.screenshot_prompt_toggle.setArrowType(Qt.RightArrow)
    window.screenshot_prompt_body = QWidget()
    prompt_layout = QVBoxLayout(window.screenshot_prompt_body)
    prompt_layout.setContentsMargins(0, 0, 0, 0)
    prompt_layout.addWidget(window.input_screenshot_gemma_prompt)
    window.screenshot_prompt_body.hide()
    window.screenshot_prompt_toggle.toggled.connect(window.toggle_screenshot_prompt)
    window.card_region_render.layout().addWidget(window.screenshot_prompt_toggle)
    window.card_region_render.layout().addWidget(window.screenshot_prompt_body)
    window.settings_tabs = QTabBar()
    window.settings_tabs.setExpanding(False)
    window.settings_tabs.setDrawBase(False)
    window.settings_tabs.setObjectName("celestialTabs")
    for _ in range(4):
        window.settings_tabs.addTab("")
    top.addWidget(window.settings_tabs)

    window.settings_pages = QStackedWidget()
    window.settings_pages.setObjectName("celestialPages")
    window.settings_pages.addWidget(window.translation_panel)
    window.settings_pages.addWidget(_page(window.card_ocr, window.card_region_render, window.card_relief))
    window.settings_pages.addWidget(_page(window.research_heading, window.research_hint, knowledge_chip, research_options))
    window.settings_pages.addWidget(_page(window.appearance_heading, theme_chip, language_chip, window.appearance_hint))
    window.settings_tabs.currentChanged.connect(window.settings_pages.setCurrentIndex)
    # An empty legacy row has no useful minimum height.
    for index in range(top.count() - 1, -1, -1):
        item = top.itemAt(index)
        if item.layout() is not None and item.layout().count() <= 1:
            top.removeItem(item)
    body.hide()
    host = window.body_host.layout()
    host.removeWidget(body)
    while host.count():
        host.takeAt(0)
    window.princess_portrait = PrincessPortrait()
    host.addWidget(window.settings_pages, 3)
    host.addWidget(window.princess_portrait, 2)
    host.setSpacing(16)
    window.shell_panel.layout().setContentsMargins(18, 0, 18, 14)
    top.setContentsMargins(22, 12, 22, 0)
    top.setSpacing(8)
    window.backdrop_panel.layout().setStretch(1, 1)
    window.frame.layout().setStretch(0, 1)


def localize_settings(window, language):
    if not hasattr(window, "settings_tabs"):
        return
    if language == "ja":
        labels = ("翻訳", "キャプチャと表示", "作品リサーチ", "外観")
        work_title, research_model = "作品名", "調査モデル"
        sources = "公開ソース URL（任意）"
        screenshot_prompt = "スクリーンショット翻訳プロンプト"
        research_hint = "作品名を入力すると、登場人物や用語を調べて物語の文脈に沿った翻訳を支援します。公開ソース URL は任意です。"
        appearance_hint = "読書のペースに合わせてライトとダークを切り替えられます。ハイコントラストではシンプルで読みやすい画面を表示します。"
        theme_label, language_label = "テーマ", "表示言語"
    elif language == "en":
        labels = ("Translation", "Capture & display", "Work research", "Appearance")
        work_title, research_model = "Work title", "Research model"
        sources = "Public source URLs (optional)"
        screenshot_prompt = "Screenshot translation prompt"
        research_hint = "Research characters and terminology to keep translations in context. Enter a work title; public source URLs are optional."
        appearance_hint = "Choose daylight or starlight for your reading. High contrast uses a plain, readable surface."
        theme_label, language_label = "Theme", "Language"
    else:
        labels = ("翻譯引擎", "擷取與顯示", "作品研究", "外觀")
        work_title, research_model = "作品名稱", "研究模型"
        sources = "公開來源網址（選填）"
        screenshot_prompt = "截圖翻譯提示詞"
        research_hint = "輸入作品名稱，整理角色與專有名詞，協助翻譯保留故事脈絡。可選填公開來源網址。"
        appearance_hint = "白晝與星夜，隨你的閱讀步調切換。高對比模式提供純色操作介面。"
        theme_label, language_label = "主題", "語言"
    for index, text in enumerate(labels):
        window.settings_tabs.setTabText(index, text)
    window.research_heading.setText(labels[2])
    window.research_title_label.setText(work_title)
    window.research_model_label.setText(research_model)
    window.research_source_label.setText(sources)
    window.screenshot_prompt_toggle.setText(screenshot_prompt)
    window.research_hint.setText(research_hint)
    window.appearance_heading.setText(labels[3])
    window.appearance_hint.setText(appearance_hint)
    window.lbl_theme_mode.setText(theme_label)
    window.lbl_ui_language.setText(language_label)
    window.lbl_theme_mode.setFixedWidth(80)
    window.lbl_ui_language.setFixedWidth(80)


def style_settings(window, theme, image_path):
    if not hasattr(window, "settings_tabs"):
        return
    dark = theme.key != "light"
    high = theme.key == "high_contrast"
    surface = "#121212" if high else ("#23263D" if dark else "#F8F7FD")
    accent = theme.accent if high else ("#AD9AFF" if dark else "#7052D6")
    secondary_text = theme.text if high else ("#C5C2D7" if dark else "#615B72")
    window.princess_portrait.set_art(None if high else image_path)
    window.princess_portrait.setVisible(not high)
    window.backdrop_panel.setStyleSheet(f"QFrame#settingsBackdropPanel {{background:{surface}; border:1px solid {theme.border}; border-radius:18px;}}")
    window.settings_tabs.setStyleSheet(
        f"QTabBar::tab {{ color:{theme.text}; padding:12px 16px; border-bottom:2px solid transparent; }}"
        f"QTabBar::tab:selected {{color:{accent}; border-bottom:2px solid {accent}; font-weight:600;}}"
        f"QTabBar::tab:hover {{background:{theme.accent_soft};}}"
        f"QTabBar::tab:focus {{border:1px solid {accent};}}"
    )
    window.settings_pages.setStyleSheet(f"QStackedWidget#celestialPages, QWidget#celestialPageContent {{background:{surface}; border:none; color:{theme.text};}} QScrollArea {{border:none; background:transparent;}}")
    scroll_style = (
        "QScrollArea {border:none; background:transparent;}"
        "QScrollBar:vertical {background:transparent; width:8px; margin:0;}"
        f"QScrollBar::handle:vertical {{background:{theme.border}; min-height:28px; border-radius:4px;}}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height:0;}"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {background:transparent;}"
    )
    for index in range(1, window.settings_pages.count()):
        window.settings_pages.widget(index).setStyleSheet(scroll_style)
    for label in window.settings_pages.findChildren(QLabel):
        if theme.subtext in label.styleSheet():
            label.setStyleSheet(label.styleSheet().replace(theme.subtext, secondary_text))
    window.research_hint.setStyleSheet(f"color:{secondary_text}; background:transparent;")
    for label in (window.research_title_label, window.research_model_label, window.research_source_label):
        label.setStyleSheet(f"color:{theme.text}; background:transparent;")
    window.appearance_hint.setStyleSheet(f"color:{secondary_text}; background:transparent;")
    window.screenshot_prompt_toggle.setStyleSheet(f"QToolButton {{color:{theme.text}; background:transparent; padding:8px; border:1px solid {theme.border}; border-radius:6px;}} QToolButton:focus {{border:2px solid {theme.focus};}}")
    for card in (window.card_translate, window.card_ocr, window.card_region_render, window.card_relief):
        card.setStyleSheet(f"QFrame {{background:transparent; border:none; color:{theme.text};}}")
    for label in (window.lbl_translate, window.lbl_ocr, window.lbl_region_render, window.lbl_relief, window.research_heading, window.appearance_heading):
        label.setStyleSheet(f"color:{theme.text}; font-size:20px; font-weight:600; background:transparent; border:none;")
    window.btn_save.setStyleSheet(f"QPushButton {{background:{accent}; color:{'#121212' if dark else '#FFFFFF'}; border:none; border-radius:8px; padding:10px 24px; font-weight:600;}} QPushButton:focus {{border:2px solid {theme.text};}}")
