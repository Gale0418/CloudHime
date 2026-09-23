from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QScrollArea, QStackedWidget, QTabBar

from CloudHime import Controller, OverlayWindow
from themes import resolve_theme


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

    for mode in ("dark", "light", "high_contrast"):
        settings.update_theme(mode)
        theme = resolve_theme(mode)

        backdrop_style = settings.backdrop_panel.styleSheet()
        expected_surface = (
            "#121212" if mode == "high_contrast"
            else "#23263D" if mode == "dark"
            else "#F8F7FD"
        )
        assert f"background:{expected_surface};" in backdrop_style
        assert f"color: {theme.text};" in settings.lbl_page_title.styleSheet()
        assert f"color: {theme.subtext};" in settings.lbl_page_subtitle.styleSheet()
        export_style = settings.btn_export_history.styleSheet()
        assert f"background-color: {theme.input_bg};" in export_style
        assert f"border-color: {theme.accent};" in export_style
        assert "QPushButton:focus" in export_style
        assert "min-height: 32px" in export_style
        top_style = settings.top_panel.styleSheet()
        assert f"background-color: {theme.settings_top_bg};" in top_style
        assert "background: transparent" not in top_style
        if mode == "high_contrast":
            assert QColor(theme.settings_top_bg).isValid()
            assert QColor(theme.settings_top_bg).alpha() == 255
        else:
            expected_top_bg = (
                "rgba(28, 28, 30, 224)"
                if mode == "dark"
                else "rgba(242, 242, 247, 224)"
            )
            assert theme.settings_top_bg == expected_top_bg
        assert settings.btn_close.text() == "✕"
        assert settings.top_panel.objectName() == "settingsTopPanel"
        assert settings.shell_panel.objectName() == "settingsShellPanel"

        tab_style = settings.settings_tabs.styleSheet()
        assert f"color:{theme.text};" in tab_style
        assert "QTabBar::tab:selected" in tab_style
        assert "QTabBar::tab:focus" in tab_style
        assert settings.princess_portrait.isVisible() is (mode != "high_contrast")

        assert settings.lbl_random_scan_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_auto_threshold_refresh_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_region_render_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_relief_summary.styleSheet() == theme.pill_qss("accent")

    window.close_app()


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
    assert settings.minimumWidth() == 900
    assert settings.minimumHeight() == 620
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
