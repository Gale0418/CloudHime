"""Exercise the release boundary, including Windows names and future add-ons."""
from pathlib import Path
import importlib.util

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qt_bundle_policy", ROOT / "packaging/qt_bundle_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


@pytest.mark.parametrize("name", ["Qt6VirtualKeyboard.dll", "qtvirtualkeyboardplugin.dll", "Qt6Qml.dll", "Qt6Quick.dll", "qpdf.dll"])
def test_hook_collected_addons_are_excluded(name):
    assert policy.is_unused_qt_binary(("PySide6\\plugins\\" + name, "source", "BINARY"))


def test_widgets_dependencies_and_windows_ime_remain_available(tmp_path):
    for name in (*policy.REVIEWED_QT_LIBRARIES, "qwindows.dll", "QtGui.pyd", "qjpeg.dll"):
        assert not policy.is_unused_qt_binary(("PySide6/" + name, "source", "BINARY"))
        (tmp_path / name).write_bytes(b"fixture")
    assert policy.verify_qt_bundle(tmp_path) == []


@pytest.mark.parametrize("name", ["QT6VIRTUALKEYBOARD.DLL", "qtvirtualkeyboardplugin.dll", "Qt6Charts.dll", "Qt6FutureAddon.dll"])
def test_dist_rejects_stale_and_new_unreviewed_addons(tmp_path, name):
    nested = tmp_path / "_internal/PySide6/plugins"
    nested.mkdir(parents=True)
    (nested / name).write_bytes(b"fixture")
    assert policy.verify_qt_bundle(tmp_path) == ["_internal/PySide6/plugins/" + name]


def test_missing_dist_is_not_a_pass(tmp_path):
    with pytest.raises(ValueError):
        policy.verify_qt_bundle(tmp_path / "missing")
