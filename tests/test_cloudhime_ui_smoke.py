import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from CloudHime import Controller, OverlayWindow

def test_cloudhime_startup(qtbot, monkeypatch):
    # Mock hotkey registration to avoid interfering with the host OS during tests
    monkeypatch.setattr(Controller, "register_hotkey", lambda self, hwnd: None, raising=False)
    monkeypatch.setattr(Controller, "unregister_hotkey", lambda self, hwnd: None, raising=False)
    
    # Instantiate the overlay window first
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    
    # Instantiate the main window (Controller) with the overlay
    window = Controller(overlay)
    qtbot.addWidget(window)
    
    # Basic assertions to ensure the UI is created successfully
    assert overlay is not None
    assert window is not None
    
    # Show the window briefly
    overlay.show()
    window.show()
    assert window.isVisible()
    assert overlay.isVisible()
