from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout

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
        expected_background = "bg_dark.jpg" if mode != "light" else "bg_light.jpg"
        assert f"background-color: {theme.shell_bg};" in backdrop_style
        assert "background-image: url(" in backdrop_style
        assert expected_background in backdrop_style
        assert "background-position: center;" in backdrop_style
        assert "background-repeat: no-repeat;" in backdrop_style
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
        assert QColor(theme.settings_top_bg).isValid()
        assert QColor(theme.settings_top_bg).alpha() == 255
        assert settings.btn_close.text() == "✕"
        assert settings.top_panel.objectName() == "settingsTopPanel"
        assert settings.shell_panel.objectName() == "settingsShellPanel"

        expected_card_bg = (
            "rgba(18, 31, 46, 168)" if mode != "light" else "rgba(255, 255, 255, 214)"
        )
        expected_borders = (
            ("#3D8DFF", "#41B96F", "#8D5CF6")
            if mode != "light"
            else ("#5AA7F7", "#50B86F", "#8D65D8")
        )
        cards = (
            (settings.card_translate, expected_borders[0]),
            (settings.card_ocr, expected_borders[1]),
            (settings.card_region_render, expected_borders[2]),
            (settings.card_relief, expected_borders[2]),
        )
        for card, border in cards:
            style = card.styleSheet()
            assert f"background-color: {expected_card_bg};" in style
            assert f"border: 1px solid {border};" in style
            assert "border-left" not in style.lower()
            assert "border-right" not in style.lower()

        assert settings.lbl_random_scan_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_auto_threshold_refresh_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_region_render_summary.styleSheet() == theme.pill_qss("accent")
        assert settings.lbl_relief_summary.styleSheet() == theme.pill_qss("accent")

    window.close_app()


def test_settings_window_keeps_legacy_three_column_shell_and_footer(qtbot, monkeypatch):
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

    body = settings.translation_panel.parentWidget()
    assert body is settings.card_ocr.parentWidget()
    assert body is settings.card_region_render.parentWidget()
    assert body is settings.card_relief.parentWidget()
    body_grid = body.layout()
    assert isinstance(body_grid, QGridLayout)
    assert body_grid.columnCount() == 3
    expected_positions = {
        settings.translation_panel: (0, 0, 2, 1),
        settings.card_ocr: (0, 1, 2, 1),
        settings.card_region_render: (0, 2, 1, 1),
        settings.card_relief: (1, 2, 1, 1),
    }
    for widget, expected in expected_positions.items():
        index = body_grid.indexOf(widget)
        assert index >= 0
        row, column, row_span, column_span = body_grid.getItemPosition(index)
        assert (row, column, row_span, column_span) == expected

    footer = settings.btn_save.parentWidget()
    assert footer.objectName() == "settingsFooter"
    assert settings.btn_reset_defaults.parentWidget() is footer
    assert settings.btn_cancel.parentWidget() is footer
    assert settings.btn_save.parentWidget() is footer
    assert settings.btn_reset_defaults.text().startswith("↻")
    assert settings.btn_cancel.text()
    assert settings.btn_save.text().startswith("✓")
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

    assert panel.lbl_luna_model.text() == "gpt-5.6-luna"
    assert panel.cmb_luna_reasoning.count() == 1
    assert panel.cmb_luna_reasoning.currentData() == "none"
    assert panel.cmb_luna_reasoning.isEnabled() is False
    reasoning_label = panel.lbl_luna_reasoning.text().lower()
    assert "fixed off" in reasoning_label or "固定關閉" in panel.lbl_luna_reasoning.text()
    assert provider_config["luna"]["reasoning_effort"] == "none"
    controller.close_app()


def test_translation_provider_controls_remain_reachable_in_legacy_shell(qtbot, monkeypatch):
    """The legacy 1422x800 shell scrolls only the Translation card contents."""
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
    settings.resize(1422, 800)
    settings.show()
    qtbot.wait(20)

    panel = settings.translation_panel
    scroll = panel.translation_scroll_area
    assert scroll.parentWidget() is panel.card_translate
    assert panel.online_provider_frame.height() > 0
    assert panel.luna_provider_frame.height() > 0
    assert all(not disclosure.body.isVisible() for disclosure in panel.provider_disclosures.values())
    qtbot.mouseClick(panel.provider_headers["online_gemma"], Qt.LeftButton)
    panel.provider_headers["luna"].setFocus()
    qtbot.keyClick(panel.provider_headers["luna"], Qt.Key_Space)
    panel.provider_headers["local_gemma"].setFocus()
    qtbot.keyClick(panel.provider_headers["local_gemma"], Qt.Key_Return)
    qtbot.wait(10)
    assert all(disclosure.body.isVisible() for disclosure in panel.provider_disclosures.values())
    assert panel.translation_content.height() > scroll.viewport().height()
    assert scroll.verticalScrollBar().maximum() > 0

    body_host = settings.body_host
    body = panel.parentWidget()
    assert body_host.objectName() == "settingsBodyHost"
    assert body.parentWidget() is body_host
    assert body_host.layout().indexOf(body) >= 0
    for size in ((1422, 800), (1400, 780)):
        settings.resize(*size)
        qtbot.wait(10)
        widths = (
            settings.translation_panel.width(),
            settings.card_ocr.width(),
            settings.card_region_render.width(),
        )
        assert body.width() <= 1040
        assert body.width() >= 928
        assert body.geometry().left() == 0
        assert body_host.width() - body.width() >= 280
        assert all(300 <= width <= 360 for width in widths)
        assert max(widths) - min(widths) <= 20
    footer = settings.btn_save.parentWidget()
    assert footer.width() >= body_host.width() - 2

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
    assert QColor(light.settings_top_bg).alpha() == 255
    assert dark.settings_top_bg


def test_dispatch_board_charge_bar_semantics():
    for mode in ("light", "dark", "high_contrast"):
        theme = resolve_theme(mode)
        normal = theme.get("charge_normal_fill")
        warning = theme.get("charge_warning_fill")
        danger = theme.get("charge_danger_fill")
        assert normal == theme.operational
        assert warning == theme.quota
        assert danger == theme.error
