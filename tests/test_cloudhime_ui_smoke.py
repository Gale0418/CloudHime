from CloudHime import Controller, OverlayWindow


def test_cloudhime_startup(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.GlobalHotKeyFilter.unregister_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None), raising=False)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True, raising=False)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args, **kwargs: None, raising=False)

    overlay = OverlayWindow()
    qtbot.addWidget(overlay)

    window = Controller(overlay)
    qtbot.addWidget(window)

    assert overlay is not None
    assert window is not None

    overlay.show()
    window.show()
    assert window.isVisible()
    assert overlay.isVisible()

    window.close_app()
    qtbot.waitUntil(lambda: not window.isVisible() and not overlay.isVisible(), timeout=2000)
