"""Keep native UI side effects isolated without importing Qt in core tests."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from ci.corpus_policy import missing_files_for_test


def _wait_for_controller_shutdown(controllers, timeout_ms=15000):
    deadline = time.monotonic() + timeout_ms / 1000.0
    while any(not getattr(controller, "_close_app_finished", False) for controller in controllers):
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            pytest.fail("Controller shutdown did not drain before UI fixture teardown")
        # The production timer is preconnected; driving its slot directly lets
        # background QThreads finish without processing unrelated DeferredDelete
        # events for QtBot-owned widgets during their QObject teardown.
        for controller in controllers:
            if not getattr(controller, "_close_app_finished", False):
                controller._poll_app_shutdown_threads()
        time.sleep(min(0.01, remaining_ms / 1000.0))
    return True


def _allow_test_controller_shutdown(controller):
    # Assertions about save vetoes have already run by fixture teardown. Let
    # the harness close the window so its QThreads cannot outlive QtBot widgets.
    controller._persist_pending_api_key = lambda: True
    controller._persist_pending_openai_api_key = lambda: True
    controller.save_settings = lambda: True


def _is_fully_initialized_controller(controller, ui):
    return (
        isinstance(controller, ui.Controller)
        and hasattr(controller, "worker")
        and hasattr(controller, "ocr_thread")
        and callable(getattr(controller, "_persist_pending_api_key", None))
    )


def _drain_open_controller_shutdowns():
    widgets = sys.modules.get("PySide6.QtWidgets")
    ui = sys.modules.get("cloudhime_ui")
    if widgets is None or ui is None:
        return
    app = widgets.QApplication.instance()
    if app is None:
        return
    controllers = [
        widget for widget in app.topLevelWidgets()
        if _is_fully_initialized_controller(widget, ui)
    ]
    for controller in controllers:
        try:
            _allow_test_controller_shutdown(controller)
            controller.close_app()
        except (RuntimeError, AttributeError):
            continue
    pending = [
        controller for controller in controllers
        if not getattr(controller, "_close_app_finished", False)
    ]
    if not pending:
        return
    if any(not getattr(controller, "_close_app_started", False) for controller in pending):
        pytest.fail("Controller shutdown was vetoed during UI fixture teardown")

    _wait_for_controller_shutdown(pending)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_teardown(item):
    # Let controller and QtBot fixture finalizers run first; afterwards drain
    # all native QThreads before processing their queued widget deletions.
    yield
    _drain_open_controller_shutdowns()
    widgets = sys.modules.get("PySide6.QtWidgets")
    if widgets is not None and widgets.QApplication.instance() is not None:
        from PySide6.QtCore import QCoreApplication, QEvent

        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture(scope="session")
def _qt_session_safety():
    # Session lifetime is intentional: Controller queues a 500 ms callback.
    patches = pytest.MonkeyPatch()
    protected = set()
    yield patches, protected
    patches.undo()


@pytest.fixture(autouse=True)
def _disable_native_hotkey_side_effects_for_tests(request, _qt_session_safety):
    """Only UI users load UI code; delayed callbacks retain session guards."""
    ui = sys.modules.get("cloudhime_ui")
    if ui is None and {"qtbot", "qapp"}.intersection(request.fixturenames):
        import cloudhime_ui as ui
    if ui is None:
        return
    patches, protected = _qt_session_safety
    identity = (ui.GlobalHotKeyFilter, ui.QMessageBox)
    if identity in protected:
        return
    patches.setattr(ui.GlobalHotKeyFilter, "register_hotkey", lambda self, hwnd: None)
    patches.setattr(ui.GlobalHotKeyFilter, "unregister_hotkey", lambda self, hwnd: None)
    patches.setattr(ui.QMessageBox, "warning", staticmethod(
        lambda *args, **kwargs: ui.QMessageBox.StandardButton.NoButton
    ))
    protected.add(identity)


@pytest.fixture(autouse=True)
def _cleanup_controller_threads_after_ui_test(request):
    """Do not import Qt merely to clean up a test that never used it."""
    # Keep qtbot alive through controller shutdown and native thread joins.
    qtbot = request.getfixturevalue("qtbot") if "qtbot" in request.fixturenames else None
    yield
    widgets = sys.modules.get("PySide6.QtWidgets")
    ui = sys.modules.get("cloudhime_ui")
    if widgets is None or ui is None:
        return
    app = widgets.QApplication.instance()
    if app is None:
        return
    for widget in list(app.topLevelWidgets()):
        if _is_fully_initialized_controller(widget, ui):
            try:
                _allow_test_controller_shutdown(widget)
                widget.close_app()
            except (RuntimeError, AttributeError):
                # qtbot may already have deleted the native object.
                continue
    pending = []
    for widget in list(app.topLevelWidgets()):
        if _is_fully_initialized_controller(widget, ui) and not getattr(widget, "_close_app_finished", False):
            pending.append(widget)
    if pending:
        if any(not getattr(widget, "_close_app_started", False) for widget in pending):
            pytest.fail("Controller shutdown was vetoed during UI fixture teardown")
        _wait_for_controller_shutdown(pending, timeout_ms=10000)


def pytest_addoption(parser):
    parser.addoption(
        "--require-external-corpora", action="store_true", default=False,
        help="Fail collection instead of skipping unavailable external-image tests.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "external_corpus: requires separately provisioned image evidence",
    )


def pytest_collection_modifyitems(config, items):
    root = Path(__file__).resolve().parents[1]
    unavailable = []
    for item in items:
        try:
            relative = item.path.resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        name = getattr(item, "originalname", None) or item.name
        node = relative + "::" + name
        missing = missing_files_for_test(root, node)
        if not missing:
            continue
        reason = "External corpus unavailable (not quality evidence): " + ", ".join(missing[:3])
        if len(missing) > 3:
            reason += f" (+{len(missing) - 3} more)"
        unavailable.append(node + ": " + reason)
        item.add_marker(pytest.mark.external_corpus)
        if not config.getoption("--require-external-corpora"):
            item.add_marker(pytest.mark.skip(reason=reason))
    if unavailable and config.getoption("--require-external-corpora"):
        raise pytest.UsageError("Required external corpus is missing:\n" + "\n".join(unavailable))
