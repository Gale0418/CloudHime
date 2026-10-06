from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QScrollArea, QStackedWidget, QTabBar

from CloudHime import Controller, OverlayWindow
import pytest

from themes import resolve_theme, build_bubble_style, ThemeRegistry


@pytest.mark.parametrize("mode", ThemeRegistry.available_modes())
@pytest.mark.parametrize("relief", [False, True])
def test_bubble_stylesheet_is_a_balanced_qss_rule(mode, relief):
    stylesheet = build_bubble_style(resolve_theme(mode), relief)["stylesheet"]
    assert stylesheet.count("{") == stylesheet.count("}") == 1


def test_settings_window_theme_polish(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    window = Controller(overlay)
    qtbot.addWidget(window)
    overlay.show()
    window.show()

    window.toggle_settings_window()
    settings = window.settings_window
    assert settings is not None
    settings.resize(1120, 760)

    for mode in ("dark", "light", "high_contrast"):
        settings.update_theme(mode)
        theme = resolve_theme(mode)

        backdrop_style = settings.backdrop_panel.styleSheet()
        expected_surface = (
            "#121212" if mode == "high_contrast"
            else "#23263D" if mode == "dark"
            else "#F8F7FD"
        )
        if mode == "high_contrast":
            assert f"background:{expected_surface};" in backdrop_style
            assert "background-image" not in backdrop_style
        else:
            assert f"background:{expected_surface};" in backdrop_style
            assert "border-image:url(" not in backdrop_style
            assert not QPixmap(settings._celestial_image_path).isNull()
        assert f"color: {theme.text};" in settings.lbl_page_title.styleSheet()
        subtitle_color = theme.text if mode == "high_contrast" else ("#C5C2D7" if mode == "dark" else "#615B72")
        assert f"color: {subtitle_color};" in settings.lbl_page_subtitle.styleSheet()
        export_style = settings.btn_export_history.styleSheet()
        assert export_style == theme.jelly_button_qss()
        assert "QPushButton:focus" in export_style
        top_style = settings.top_panel.styleSheet()
        expected_top_bg = (
            "#121212" if mode == "high_contrast"
            else "rgba(20, 21, 47, 146)" if mode == "dark"
            else "rgba(255, 255, 255, 140)"
        )
        assert f"background-color: {expected_top_bg};" in top_style
        assert "background: transparent" not in top_style
        if mode == "high_contrast":
            assert QColor(expected_top_bg).alpha() == 255
        else:
            assert int(expected_top_bg.rstrip(")").split(",")[-1]) < 255
        assert settings.btn_save.styleSheet() == theme.jelly_button_qss("primary")
        assert not settings.btn_close.icon().isNull()
        assert settings.top_panel.objectName() == "settingsTopPanel"
        assert settings.shell_panel.objectName() == "settingsShellPanel"

        tab_style = settings.settings_tabs.styleSheet()
        assert f"color:{theme.text};" in tab_style
        assert "QTabBar::tab:selected" in tab_style
        assert "QTabBar::tab:focus" in tab_style
        assert settings.princess_portrait.isVisible() is (mode != "high_contrast")
        if mode != "high_contrast":
            assert "rgba(" in settings.settings_pages.styleSheet()

        assert settings.lbl_random_scan_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_auto_threshold_refresh_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_region_render_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_relief_summary.styleSheet() == theme.pill_qss("accent")

    window.close_app()


def test_theme_selection_refreshes_open_settings_without_losing_edits(qtbot, monkeypatch):
    class PaintObserver(QObject):
        def __init__(self, parent):
            super().__init__(parent)
            self.paints = 0

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Paint:
                self.paints += 1
            return False

    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    controller.toggle_settings_window()
    settings = controller.settings_window
    settings.settings_tabs.setCurrentIndex(3)
    settings.input_knowledge_title.setText("Unsaved work title")
    qtbot.wait(10)
    observer = PaintObserver(settings)
    settings.backdrop_panel.installEventFilter(observer)

    for mode in ("dark", "high_contrast", "light"):
        observer.paints = 0
        settings.cmb_theme_mode_chip.setCurrentIndex(settings.cmb_theme_mode_chip.findData(mode))
        qtbot.waitUntil(lambda: settings._celestial_theme.key == mode)
        # Process queued paint requests without hover, resize, reopening, or
        # grab(), which would itself force a redraw and conceal stale pixels.
        qtbot.waitUntil(lambda: observer.paints > 0)
        assert controller.theme_mode == mode
        assert settings.cmb_theme_mode_chip.currentData() == mode
        assert settings.settings_tabs.currentIndex() == 3
        assert settings.input_knowledge_title.text() == "Unsaved work title"
        assert settings.btn_save.styleSheet() == resolve_theme(mode).jelly_button_qss("primary")
        assert settings.princess_portrait.isVisible() is (mode != "high_contrast")
    controller.close_app()


def test_settings_window_uses_celestial_tabs_and_fixed_footer(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    controller.toggle_settings_window()
    settings = controller.settings_window
    qtbot.wait(10)

    settings.show()
    assert settings.minimumWidth() == 760
    assert settings.minimumHeight() == 520
    assert isinstance(settings.settings_tabs, QTabBar)
    assert settings.settings_tabs.count() == 4
    assert isinstance(settings.settings_pages, QStackedWidget)
    assert settings.settings_pages.count() == 4
    assert [settings.settings_tabs.tabText(index) for index in range(4)] == [
        "Translation",
        "Capture & display",
        "Work research",
        "Appearance",
    ]

    translation_page = settings.settings_pages.widget(0)
    capture_page = settings.settings_pages.widget(1)
    research_page = settings.settings_pages.widget(2)
    appearance_page = settings.settings_pages.widget(3)
    assert translation_page.isAncestorOf(settings.translation_panel)
    for control in (settings.card_ocr, settings.card_region_render, settings.card_relief):
        assert capture_page.isAncestorOf(control)
    for control in (settings.research_heading, settings.cmb_knowledge_model, settings.input_knowledge_sources):
        assert research_page.isAncestorOf(control)
    assert settings.research_title_label.buddy() is settings.input_knowledge_title
    assert settings.research_model_label.buddy() is settings.cmb_knowledge_model
    assert settings.research_source_label.buddy() is settings.input_knowledge_sources
    assert settings.research_model_label.text() == "Research model"
    assert settings.research_source_label.text() == "Public source URLs (optional)"
    for control in (settings.appearance_heading, settings.cmb_theme_mode_chip, settings.cmb_ui_language_chip):
        assert appearance_page.isAncestorOf(control)

    footer = settings.btn_save.parentWidget()
    assert footer.objectName() == "settingsFooter"
    assert settings.btn_reset_defaults.parentWidget() is footer
    assert settings.btn_cancel.parentWidget() is footer
    assert settings.btn_save.parentWidget() is footer
    assert settings.btn_reset_defaults.text() == "Reset to Defaults"
    assert settings.btn_cancel.text()
    assert settings.btn_save.text() == "Save"
    assert settings.frame.layout().indexOf(footer) >= 0
    for index in range(settings.settings_tabs.count()):
        settings.settings_tabs.setCurrentIndex(index)
        qtbot.wait(5)
        assert settings.settings_pages.currentIndex() == index
        assert settings.settings_pages.currentWidget().isVisible()
        assert footer.isVisible()
        for page_index in range(settings.settings_pages.count()):
            if page_index != index:
                assert not settings.settings_pages.widget(page_index).isVisible()
    controller.close_app()
    assert controller._close_app_started
    controller.close_app()  # repeated shutdown must not touch deleted Qt objects


def test_settings_portrait_survives_compact_resize_and_theme_changes(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    controller.toggle_settings_window()
    settings = controller.settings_window
    settings.resize(780, 600)
    settings.show()
    qtbot.wait(20)

    assert settings.width() == 780
    assert settings.minimumSize().width() == 760
    assert settings.princess_portrait.isVisible()
    assert not settings.princess_portrait.grab().toImage().isNull()
    assert settings.grab().save(str(tmp_path / "settings-compact.png"))
    assert settings.backdrop_panel.styleSheet().find("background-image") == -1
    colors = {
        settings.princess_portrait.grab().toImage().pixelColor(x, y).rgba()
        for x in range(0, settings.princess_portrait.width(), 12)
        for y in range(0, settings.princess_portrait.height(), 12)
    }
    assert len(colors) > 16

    footer = settings.btn_save.parentWidget()
    for size, mode in (((1120, 760), "dark"), ((780, 600), "light"), ((1120, 760), "high_contrast")):
        settings.resize(*size)
        settings.update_theme(mode)
        qtbot.wait(10)
        assert settings.princess_portrait.isVisible() is (mode != "high_contrast")
        assert footer.isVisible()
        footer_corner = footer.mapTo(settings, footer.rect().bottomRight() - QPoint(1, 1))
        assert settings.rect().contains(footer_corner)
        if mode == "high_contrast":
            assert "background-image" not in settings.backdrop_panel.styleSheet()
        else:
            assert not settings.princess_portrait.grab().toImage().isNull()
            if size == (1120, 760):
                assert settings.grab().save(str(tmp_path / "settings-wide.png"))

    controller.close_app()


def test_capture_prompt_toggle_sync_save_and_minimum_layout(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    controller.toggle_settings_window()
    settings = controller.settings_window
    settings.show()
    settings.settings_tabs.setCurrentIndex(1)
    qtbot.wait(10)

    toggle = settings.screenshot_prompt_toggle
    body = settings.screenshot_prompt_body
    prompt = settings.input_screenshot_gemma_prompt
    assert not toggle.isChecked()
    assert not body.isVisible()
    assert body.isAncestorOf(prompt)

    toggle.click()
    qtbot.wait(10)
    assert toggle.isChecked()
    assert body.isVisible()
    assert prompt.isVisible()

    existing_prompt = "Keep named spells and character titles unchanged."
    controller.screenshot_gemma_prompt = existing_prompt
    settings.sync_from_controller()
    assert body.isVisible()
    assert prompt.toPlainText() == existing_prompt

    footer = settings.btn_save.parentWidget()
    settings.resize(900, 620)
    qtbot.wait(20)
    assert settings.width() >= 900
    assert settings.height() >= 620
    assert settings.settings_tabs.isVisible()
    assert settings.settings_tabs.count() == 4
    assert footer.isVisible()
    assert all(
        settings.settings_tabs.rect().contains(settings.settings_tabs.tabRect(index))
        for index in range(settings.settings_tabs.count())
    )
    scroll_areas = settings.findChildren(QScrollArea)
    assert scroll_areas
    assert all(scroll.horizontalScrollBar().maximum() == 0 for scroll in scroll_areas)
    capture_page_scroll = settings.settings_pages.widget(1)
    capture_page_scroll.ensureWidgetVisible(prompt)
    capture_page_scroll.verticalScrollBar().setValue(capture_page_scroll.verticalScrollBar().maximum())
    qtbot.wait(10)
    mapped_prompt = prompt.rect().center()
    mapped_prompt = prompt.mapTo(capture_page_scroll.viewport(), mapped_prompt)
    assert capture_page_scroll.viewport().rect().contains(mapped_prompt)

    saved_values = []
    controller.save_settings = lambda: saved_values.append(controller.screenshot_gemma_prompt) or True
    settings.btn_save.click()
    assert saved_values == [existing_prompt]
    controller.close_app()


def test_settings_language_tabs_and_high_contrast_disable_portrait(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    controller.toggle_settings_window()
    settings = controller.settings_window
    settings.show()

    controller.set_ui_language("zh-TW", persist=False, refresh=False)
    assert [settings.settings_tabs.tabText(index) for index in range(4)] == [
        "翻譯引擎",
        "擷取與顯示",
        "作品研究",
        "外觀",
    ]

    controller.set_ui_language("ja-JP", persist=False, refresh=False)
    assert controller.get_ui_language() == "ja"
    assert [settings.settings_tabs.tabText(index) for index in range(4)] == [
        "翻訳",
        "キャプチャと表示",
        "作品リサーチ",
        "外観",
    ]
    assert settings.cmb_ui_language_chip.currentData() == "ja"
    assert settings.translation_panel.lbl_translate.text() == "翻訳"

    settings.update_theme("high_contrast")
    assert not settings.princess_portrait.isVisible()
    assert "background:#121212;" in settings.backdrop_panel.styleSheet()
    assert "background-image" not in settings.backdrop_panel.styleSheet()
    high_contrast = resolve_theme("high_contrast")
    assert high_contrast.settings_shell_bg == "#121212"
    assert high_contrast.settings_card_bg == "#202020"
    assert high_contrast.settings_fallback_bg == "#121212"
    assert settings.settings_tabs.isEnabled()
    controller.close_app()


def test_settings_translation_entry_uses_one_gemma_key_and_fixed_luna_thinking(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    controller.toggle_settings_window()
    settings = controller.settings_window
    panel = settings.translation_panel
    qtbot.wait(10)

    assert panel.input_api_key is panel.input_google_api_key
    assert panel.input_api_key is panel.input_gemma_api_key
    assert not hasattr(panel, "input_google_api_key_secondary")
    assert tuple(panel.online_gemma_model_rows) == (
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
    )
    assert panel.lbl_online_gemma_models.text()
    assert "gemma-4-26b-a4b-it" in panel.lbl_online_gemma_models.text()
    assert "gemma-4-31b-it" in panel.lbl_online_gemma_models.text()
    provider_config = panel.get_provider_config()
    assert provider_config["online_gemma"]["models"] == (
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
    )
    assert "api_key" not in provider_config["online_gemma"]

    assert panel.lbl_luna_model.text() == "gpt-6-luna"
    assert panel.cmb_luna_reasoning.count() == 1
    assert panel.cmb_luna_reasoning.currentData() == "none"
    assert panel.cmb_luna_reasoning.isEnabled() is False
    reasoning_label = panel.lbl_luna_reasoning.text().lower()
    assert "fixed off" in reasoning_label or "固定關閉" in panel.lbl_luna_reasoning.text()
    assert provider_config["luna"]["reasoning_effort"] == "none"
    controller.close_app()


def test_translation_provider_controls_remain_reachable_in_translation_page(qtbot, monkeypatch):
    """Each selected provider remains reachable without showing duplicate settings."""
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    qtbot.addWidget(controller)
    controller.toggle_settings_window()
    settings = controller.settings_window
    settings.resize(1120, 760)
    settings.show()
    qtbot.wait(20)

    panel = settings.translation_panel
    scroll = panel.translation_scroll_area
    assert scroll.parentWidget() is panel.card_translate
    assert panel.online_provider_frame.height() > 0
    assert panel.luna_provider_frame.height() > 0
    assert all(not disclosure.body.isVisible() for disclosure in panel.provider_disclosures.values())
    for provider_id in ("local_gemma", "online_gemma", "luna"):
        panel._set_provider_choice(provider_id)
        header = panel.provider_headers[provider_id]
        scroll.ensureWidgetVisible(header)
        header.setFocus()
        qtbot.keyClick(header, Qt.Key_Return)
        qtbot.wait(10)
        assert panel.provider_disclosures[provider_id].body.isVisible()
        assert all(not disclosure.isVisible() for key, disclosure in panel.provider_disclosures.items() if key != provider_id)
    assert panel.translation_content.height() > scroll.viewport().height()
    assert scroll.verticalScrollBar().maximum() > 0

    footer = settings.btn_save.parentWidget()
    assert settings.settings_pages.widget(0).isAncestorOf(panel)
    assert footer.objectName() == "settingsFooter"
    assert settings.frame.layout().indexOf(footer) >= 0

    scroll.ensureWidgetVisible(panel.input_luna_api_key)
    qtbot.wait(10)
    center = panel.input_luna_api_key.rect().center()
    mapped = panel.input_luna_api_key.mapTo(scroll.viewport(), center)
    assert scroll.viewport().rect().contains(mapped)

    panel._set_provider_choice("local_gemma")
    panel.update_key_state(True)
    panel.provider_disclosures["local_gemma"].set_expanded(True)
    advanced_button = panel.btn_advanced_tuning
    scroll.ensureWidgetVisible(advanced_button)
    qtbot.wait(20)
    button_center = advanced_button.mapTo(scroll.viewport(), advanced_button.rect().center())
    assert scroll.viewport().rect().contains(button_center)
    advanced_button.click()
    qtbot.wait(10)
    assert panel.input_gemma_prompt.isVisible()
    scroll.ensureWidgetVisible(panel.input_gemma_prompt)
    qtbot.wait(10)
    prompt_center = panel.input_gemma_prompt.mapTo(scroll.viewport(), panel.input_gemma_prompt.rect().center())
    assert scroll.viewport().rect().contains(prompt_center)
    assert panel.tuning_frame.isHidden()
    for provider_id in ("online_gemma", "luna"):
        panel._set_provider_choice(provider_id)
        panel.update_key_state(True)
        assert advanced_button.isVisible()
        assert advanced_button.isEnabled()
        assert panel.input_gemma_prompt.isEnabled()
        scroll.ensureWidgetVisible(panel.input_gemma_prompt)
        qtbot.wait(10)
        prompt_center = panel.input_gemma_prompt.mapTo(scroll.viewport(), panel.input_gemma_prompt.rect().center())
        assert scroll.viewport().rect().contains(prompt_center)
    controller.close_app()


def test_raised_button_tokens_cover_settings_states_without_effects():
    """Raised settings controls stay tonal, theme-aware, and keyboard-visible."""
    token_names = (
        "button_primary_top",
        "button_primary_edge",
        "button_secondary_top",
        "button_secondary_edge",
        "button_segmented_top",
        "button_segmented_edge",
    )
    for mode in ("light", "dark", "high_contrast"):
        theme = resolve_theme(mode)
        assert all(theme.get(name) for name in token_names)
        for variant in ("primary", "secondary", "segmented"):
            style = theme.raised_button_qss(variant)
            assert style.count("{") == style.count("}")
            assert "border-top-color:" in style
            assert "border-bottom: 2px solid" in style
            assert "QPushButton:hover" in style
            assert "QPushButton:pressed" in style
            assert "padding-top: 7px" in style
            assert "QPushButton:focus {" in style
            assert "border: 2px solid" in style
            assert "QPushButton:disabled" in style
            assert "gradient" not in style.lower()
            assert "shadow" not in style.lower()

        segmented = theme.raised_button_qss("segmented")
        assert f"background-color: {theme.control_bg};" in segmented
        assert f"QPushButton:checked {{ background-color: {theme.control_checked};" in segmented
        assert segmented.index(f"background-color: {theme.control_bg};") < segmented.index(
            f"QPushButton:checked {{ background-color: {theme.control_checked};"
        )


def test_settings_top_surface_supports_shell_text():
    light = resolve_theme("light")
    dark = resolve_theme("dark")
    assert light.settings_top_bg != light.settings_nav_bg
    assert light.settings_top_bg == "rgba(242, 242, 247, 224)"
    assert dark.settings_top_bg == "rgba(28, 28, 30, 224)"


def test_dispatch_board_charge_bar_semantics():
    for mode in ("light", "dark", "high_contrast"):
        theme = resolve_theme(mode)
        normal = theme.get("charge_normal_fill")
        warning = theme.get("charge_warning_fill")
        danger = theme.get("charge_danger_fill")
        assert normal == theme.operational
        assert warning == theme.quota
        assert danger == theme.error
