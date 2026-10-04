"""Gemini-authored fixed UI text; technical output is passed through unchanged."""
from __future__ import annotations

import localization

MESSAGES = {
    'hotkey_conflict_body': {
        'en': 'Failed to register global hotkeys (Error {error}).\nPlease close applications using these keys and restart CloudHime (｡•́︿•̀｡)',
        'ja': 'グローバルホットキーの登録に失敗しました（エラー {error}）。\nキーを使用中の他アプリを終了後、CloudHime を再起動してください (｡•́︿•̀｡)',
        'zh-TW': '全域快速鍵註冊失敗（錯誤碼 {error}）。\n請關閉佔用熱鍵的程式後重新啟動 CloudHime (｡•́︿•̀｡)',
    },
    'hotkey_conflict_title': {
        'en': 'Hotkey Conflict',
        'ja': 'ホットキーの競合',
        'zh-TW': '快速鍵衝突',
    },
    'initial_translation_hint': {
        'en': 'Google Translate requires no key but needs internet; local Gemma requires no cloud key; online AI requires an API key (｡•̀ᴗ-)✧',
        'ja': 'Google 翻訳はキー不要ですがネット接続が必要、ローカル Gemma はクラウドキー不要、オンライン AI は API キーが必要です (｡•̀ᴗ-)✧',
        'zh-TW': 'Google 翻譯免 Key 但需網路，本機 Gemma 免雲端 Key，線上 AI 則需設定 API Key (｡•̀ᴗ-)✧',
    },
}

OCR_DETAILS = {
    'Built into Windows.': {
        'en': 'Built into Windows, ready to use! (｡•̀ᴗ-)✧',
        'ja': 'Windows 標準搭載で、すぐにお使いいただけます (｡•̀ᴗ-)✧',
        'zh-TW': 'Windows 系統內建，開箱即用 (｡•̀ᴗ-)✧',
    },
    'Downloads ONNX Runtime dependencies.': {
        'en': 'Downloads ONNX Runtime dependencies.',
        'ja': 'ONNX Runtime 関連の依存パッケージをダウンロードします。',
        'zh-TW': '會下載 ONNX Runtime 相關相依套件。',
    },
    'Downloads PyTorch dependencies.': {
        'en': 'Downloads PyTorch dependencies.',
        'ja': 'PyTorch 関連の依存パッケージをダウンロードします。',
        'zh-TW': '會下載 PyTorch 相關相依套件。',
    },
    'Install failed.': {
        'en': 'Install failed (｡•́︿•̀｡)',
        'ja': 'インストールに失敗しました (｡•́︿•̀｡)',
        'zh-TW': '安裝失敗 (｡•́︿•̀｡)',
    },
    'Needs easyocr / torch / torchvision': {
        'en': 'Needs easyocr / torch / torchvision',
        'ja': 'easyocr / torch / torchvision が必要',
        'zh-TW': '需要 easyocr / torch / torchvision',
    },
    'Needs rapidocr-onnxruntime': {
        'en': 'Needs rapidocr-onnxruntime',
        'ja': 'rapidocr-onnxruntime が必要です',
        'zh-TW': '需要 rapidocr-onnxruntime',
    },
    'Needs tesseract.exe': {
        'en': 'Needs tesseract.exe',
        'ja': 'tesseract.exe が必要',
        'zh-TW': '需要 tesseract.exe',
    },
    'Optional OCR backend installation is unavailable in packaged builds. Use Windows OCR or install the backend in source mode.': {
        'en': 'Optional OCR backend installation is unavailable in packaged builds. Please use Windows OCR or install dependencies in source mode (｡•́︿•̀｡)',
        'ja': 'パッケージ版では追加 OCR バックエンドの自動インストールに対応していません。Windows OCR をご利用いただくか、ソースコード環境にてインストールしてください (｡•́︿•̀｡)',
        'zh-TW': '打包版本暫不支援自動安裝選配 OCR 後端。請使用 Windows OCR，或在原始碼模式手動安裝後端套件 (｡•́︿•̀｡)',
    },
    'Ready': {
        'en': 'Ready',
        'ja': '準備完了',
        'zh-TW': '已就緒',
    },
    'Ready (CPU)': {
        'en': 'Ready (CPU)',
        'ja': '準備完了 (CPU)',
        'zh-TW': '已就緒 (CPU)',
    },
    'Ready (GPU)': {
        'en': 'Ready (GPU)',
        'ja': '準備完了 (GPU)',
        'zh-TW': '已就緒 (GPU)',
    },
    'Requires tesseract.exe.': {
        'en': 'Requires tesseract.exe.',
        'ja': 'tesseract.exe 実行ファイルが必要です。',
        'zh-TW': '需要 tesseract.exe 執行檔。',
    },
    'Requires the Tesseract executable.': {
        'en': 'Requires the installed Tesseract executable (tesseract.exe).',
        'ja': 'インストール済みの Tesseract 実行ファイル (tesseract.exe) が必要です。',
        'zh-TW': '需要已安裝的 Tesseract 可執行檔 (tesseract.exe)。',
    },
    'Tesseract runtime install completed.': {
        'en': 'Tesseract runtime installation completed! (｡•̀ᴗ-)✧',
        'ja': 'Tesseract 実行環境のインストールが完了しました！(｡•̀ᴗ-)✧',
        'zh-TW': 'Tesseract 執行環境安裝完成！(｡•̀ᴗ-)✧',
    },
    'Tesseract runtime is missing. Please install tesseract.exe separately.': {
        'en': 'Tesseract runtime was not found. Please install tesseract.exe separately (｡•́︿•̀｡)',
        'ja': 'Tesseract 実行環境が見つかりません。別途 tesseract.exe をインストールしてください (｡•́︿•̀｡)',
        'zh-TW': '未偵測到 Tesseract 執行環境，請先獨立安裝 tesseract.exe 喔 (｡•́︿•̀｡)',
    },
    'Unknown OCR backend.': {
        'en': 'Unknown OCR backend.',
        'ja': '不明な OCR バックエンドです。',
        'zh-TW': '未知的 OCR 後端。',
    },
    'Unknown backend': {
        'en': 'Unknown backend',
        'ja': '不明なバックエンド',
        'zh-TW': '未知的後端',
    },
    'Unsupported': {
        'en': 'Unsupported',
        'ja': '未対応',
        'zh-TW': '不支援',
    },
    'Windows OCR does not need installation.': {
        'en': 'Windows OCR is built-in and does not need installation (｡•̀ᴗ-)✧',
        'ja': 'Windows OCR は標準機能のためインストール不要です (｡•̀ᴗ-)✧',
        'zh-TW': 'Windows OCR 為系統內建，無需另行安裝 (｡•̀ᴗ-)✧',
    },
    '{backend} install completed.': {
        'en': '{backend} install completed! (｡•̀ᴗ-)✧',
        'ja': '{backend} のインストールが完了しました！(｡•̀ᴗ-)✧',
        'zh-TW': '{backend} 安裝完成！(｡•̀ᴗ-)✧',
    },
    '{backend} install failed.': {
        'en': '{backend} install failed (｡•́︿•̀｡)',
        'ja': '{backend} のインストールに失敗しました (｡•́︿•̀｡)',
        'zh-TW': '{backend} 安裝失敗 (｡•́︿•̀｡)',
    },
    '{requirement} Restart the app if tesseract was just installed.': {
        'en': '{requirement} Restart the app if tesseract was just installed (｡•̀ᴗ-)✧',
        'ja': '{requirement} Tesseract をインストールした直後の場合は、アプリを再起動してください (｡•̀ᴗ-)✧',
        'zh-TW': '{requirement} 若剛完成安裝 Tesseract，請重新啟動 CloudHime 喔 (｡•̀ᴗ-)✧',
    },
}


def _localized(entry, language, **params):
    text = entry[localization.normalize_ui_language(language)]
    return text.format(**params) if params else text


def get_copy(key, language="en", **params):
    return _localized(MESSAGES[key], language, **params)


def localize_ocr_detail(detail, language="en"):
    """Translate known fixed messages, retaining subprocess and exception diagnostics."""
    text = str(detail or "")
    if text in OCR_DETAILS:
        return _localized(OCR_DETAILS[text], language)
    lines = []
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        ending = line[len(content):]
        translated = None
        if content in OCR_DETAILS:
            translated = _localized(OCR_DETAILS[content], language)
        for suffix in (" install failed.", " install completed."):
            if content.endswith(suffix):
                backend = content[:-len(suffix)]
                if backend in {"Windows OCR", "Tesseract", "EasyOCR", "RapidOCR"}:
                    translated = _localized(OCR_DETAILS["{backend}" + suffix], language, backend=backend)
        restart_suffix = " Restart the app if tesseract was just installed."
        if content.endswith(restart_suffix):
            requirement = content[:-len(restart_suffix)]
            if requirement in OCR_DETAILS:
                translated = _localized(
                    OCR_DETAILS["{requirement}" + restart_suffix], language,
                    requirement=_localized(OCR_DETAILS[requirement], language),
                )
        lines.append((translated if translated is not None else content) + ending)
    return "".join(lines)
