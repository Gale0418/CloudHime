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

    settings.update_theme("dark")
    dark = resolve_theme("dark")
    assert settings.card_translate.styleSheet() == "QFrame { background-color: rgba(18, 31, 46, 168); border: 1px solid #3D8DFF; border-radius: 14px; }"
    assert settings.lbl_random_scan_summary.styleSheet() == dark.pill_qss("accent")
    assert settings.lbl_auto_threshold_refresh_summary.styleSheet() == dark.pill_qss("accent")
    assert settings.lbl_region_render_summary.styleSheet() == dark.pill_qss("accent")
    assert settings.lbl_relief_summary.styleSheet() == dark.pill_qss("accent")

    settings.update_theme("light")
    assert settings.card_translate.styleSheet() == "QFrame { background-color: rgba(255, 255, 255, 214); border: 1px solid #5AA7F7; border-radius: 14px; }"

    window.close_app()
