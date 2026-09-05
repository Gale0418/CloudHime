"""Shared safeguards for Qt UI tests.

Controller schedules its global-hotkey registration 500 ms after construction.
Keeping these test doubles at session scope prevents a queued callback from
outliving a function-scoped monkeypatch and touching the host OS (or opening a
modal warning) after its originating test has finished.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _disable_native_hotkey_side_effects_for_tests():
    """Keep delayed Controller hotkey callbacks harmless during pytest."""
    import cloudhime_ui

    hotkey_filter = cloudhime_ui.GlobalHotKeyFilter
    original_register = hotkey_filter.register_hotkey
    original_unregister = hotkey_filter.unregister_hotkey
    original_warning = cloudhime_ui.QMessageBox.warning

    hotkey_filter.register_hotkey = lambda self, hwnd: None
    hotkey_filter.unregister_hotkey = lambda self, hwnd: None
    cloudhime_ui.QMessageBox.warning = staticmethod(
        lambda *args, **kwargs: cloudhime_ui.QMessageBox.StandardButton.NoButton
    )
    try:
        yield
    finally:
        hotkey_filter.register_hotkey = original_register
        hotkey_filter.unregister_hotkey = original_unregister
        cloudhime_ui.QMessageBox.warning = original_warning


@pytest.fixture(autouse=True)
def _cleanup_controller_threads_after_ui_test(monkeypatch):
    """Stop Controller-owned Qt threads even when qtbot only closes widgets."""
    yield

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return

    import cloudhime_ui

    for widget in list(app.topLevelWidgets()):
        if not isinstance(widget, cloudhime_ui.Controller):
            continue
        try:
            widget.close_app()
        except (RuntimeError, AttributeError):
            # The Qt object may already have been deleted by qtbot.
            continue
    app.processEvents()
