"""Load the bundled UI fonts without installing them into Windows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


_FONT_FILES = {
    "zh-TW": "GenSenRounded2TW-R.otf",
    "en": "GenSenRounded2TW-R.otf",
    "ja": "GenSenRounded2JP-R.otf",
}


def _font_path(filename: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / "fonts" / filename


def apply_ui_font(language: str, app: QApplication | None = None) -> str:
    """Apply the locale's rounded face; return the actual selected family.

    Font registration belongs to each QApplication, so tests that recreate an app
    do not accidentally reuse stale Qt font IDs. Missing assets fall back to the
    operating system UI font and never prevent the app from opening.
    """
    app = app or QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication is required before loading UI fonts")

    registered = app.property("_cloudhime_registered_fonts") or {}
    if not isinstance(registered, dict):
        registered = {}
    filename = _FONT_FILES.get(language, _FONT_FILES["zh-TW"])
    family = registered.get(filename)
    if family is None:
        font_id = QFontDatabase.addApplicationFont(str(_font_path(filename)))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        family = families[0] if families else ""
        registered[filename] = family
        app.setProperty("_cloudhime_registered_fonts", registered)

    font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
    if family:
        font.setFamily(family)
    font.setPointSize(10)
    font.setStyleHint(QFont.SansSerif)
    font.setHintingPreference(QFont.PreferDefaultHinting)
    app.setFont(font)
    return font.family()
