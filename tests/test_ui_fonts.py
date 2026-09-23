from pathlib import Path

from PySide6.QtWidgets import QApplication

from ui_fonts import apply_ui_font


def test_bundled_ui_font_switches_between_taiwanese_and_japanese():
    app = QApplication.instance() or QApplication([])
    previous = app.font()
    try:
        assert apply_ui_font("zh-TW", app) == "GenSenRounded2 TW"
        assert apply_ui_font("en", app) == "GenSenRounded2 TW"
        assert apply_ui_font("ja", app) == "GenSenRounded2 JP"
        assert app.font().family() == "GenSenRounded2 JP"
    finally:
        app.setFont(previous)


def test_font_license_is_bundled_with_both_locale_faces():
    font_dir = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    assert (font_dir / "OFL.txt").is_file()
    assert (font_dir / "GenSenRounded2TW-R.otf").is_file()
    assert (font_dir / "GenSenRounded2JP-R.otf").is_file()
