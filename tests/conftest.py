"""Keep native UI side effects isolated without importing Qt in core tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ci.corpus_policy import missing_files_for_test


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
def _cleanup_controller_threads_after_ui_test():
    """Do not import Qt merely to clean up a test that never used it."""
    yield
    widgets = sys.modules.get("PySide6.QtWidgets")
    ui = sys.modules.get("cloudhime_ui")
    if widgets is None or ui is None:
        return
    app = widgets.QApplication.instance()
    if app is None:
        return
    for widget in list(app.topLevelWidgets()):
        if isinstance(widget, ui.Controller):
            try:
                widget.close_app()
            except (RuntimeError, AttributeError):
                # qtbot may already have deleted the native object.
                continue
    app.processEvents()


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
