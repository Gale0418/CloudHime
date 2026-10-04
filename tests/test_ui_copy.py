import pytest

from ui_copy import get_copy, localize_ocr_detail


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "Built into Windows"),
        ("zh-TW", "Windows 系統內建"),
        ("ja", "Windows 標準搭載"),
    ],
)
def test_known_ocr_detail_is_localized(language, expected):
    localized = localize_ocr_detail("Built into Windows.", language)

    assert expected in localized
    assert "Windows OCR" not in localized


@pytest.mark.parametrize(
    ("language", "completed", "failed", "restart"),
    [
        ("en", "completed", "failed", "Restart the app"),
        ("zh-TW", "安裝完成", "安裝失敗", "重新啟動"),
        ("ja", "インストールが完了", "インストールに失敗", "再起動"),
    ],
)
def test_ocr_backend_templates_keep_brand_and_restart_guidance(language, completed, failed, restart):
    success = localize_ocr_detail("Tesseract install completed.", language)
    failure = localize_ocr_detail("Tesseract install failed.", language)
    restart_detail = localize_ocr_detail(
        "Requires the Tesseract executable. Restart the app if tesseract was just installed.",
        language,
    )

    assert "Tesseract" in success
    assert completed in success
    assert "Tesseract" in failure
    assert failed in failure
    assert "Tesseract" in restart_detail
    assert restart in restart_detail


@pytest.mark.parametrize(
    ("language", "error", "close_apps", "restart"),
    [
        ("en", "Error 5", "close applications", "restart CloudHime"),
        ("zh-TW", "錯誤碼 5", "關閉佔用熱鍵的程式", "重新啟動 CloudHime"),
        ("ja", "エラー 5", "他アプリ", "CloudHime を再起動"),
    ],
)
def test_hotkey_conflict_explains_error_and_safe_recovery(language, error, close_apps, restart):
    message = get_copy("hotkey_conflict_body", language, error=5)

    assert error in message
    assert close_apps in message
    assert restart in message


def test_unknown_multiline_ocr_diagnostic_is_preserved_exactly():
    diagnostic = "Synthetic backend failure: CODE_42\n  detail: keep spacing\n"

    assert localize_ocr_detail(diagnostic, "ja") == diagnostic
