from __future__ import annotations

from typing import Any


DEFAULT_UI_LANGUAGE = "en"
SUPPORTED_UI_LANGUAGES = ("en", "zh-TW")

_LANGUAGE_ALIASES = {
    "zh": "zh-TW",
    "zh-hant": "zh-TW",
    "zh-tw": "zh-TW",
    "zh-hk": "zh-TW",
    "zh-mo": "zh-TW",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
}

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh-TW": {
        "settings_title": "設定頁面",
        "settings_subtitle": "集中管理翻譯、OCR、外觀與掃描行為。",
        "settings_close": "關閉",
        "settings_theme_mode": "顏色模式",
        "settings_ui_language": "UI 語言",
        "controller.window_title": "CloudHime",
        "controller.title": "CloudHime v3.0",
        "controller.placeholder.google_api_key": "Google API KEY",
        "controller.button.ai_translation": "AI 翻譯",
        "controller.button.fullscreen": "全螢幕翻譯",
        "controller.button.region": "區域翻譯",
        "controller.button.stop": "停止",
        "controller.button.random_scan_prefix": "隨機",
        "controller.button.now": "立即翻譯",
        "controller.tooltip.settings": "設定",
        "controller.status.ready": "待命中，等你喊我 (*´▽`*)",
        "controller.status.ai_model_ready": "AI 模型：{model}",
        "controller.status.auto_scanning": "{prefix} 自動掃描中",
        "controller.status.auto_stopped": "⏸ 自動已停止",
        "controller.status.immediate_scanning": "⚡ 立即掃描中...",
        "controller.status.need_api_key": "請先輸入 Google API KEY",
        "controller.status.need_region": "請先設定框選區域",
        "controller.status.region_ready": "框選區域已設定：{size}",
        "controller.status.capture_running": "🖼 截圖翻譯進行中...",
        "controller.status.cold_down": "⚡ 冷卻充電中...",
        "controller.status.ai_model_auto_switch": "AI模型自動切換：{old_label} -> {new_label}",
        "controller.status.ai_model_full_switch": "{current} 已滿，下一次會自動切到 {backup}",
        "controller.status.ai_model_full_google": "{current} 已滿 {limit}/{limit}，先改用 Google",
        "controller.mode.fullscreen": "🖥 目前模式：全螢幕",
        "controller.mode.relief": "🧩 目前模式：浮離",
        "controller.mode.screenshot": "🖼 目前模式：截圖",
        "controller.mode.bubble": "💬 目前模式：氣泡",
        "controller.mode.scan_fullscreen": "全螢幕翻譯",
        "controller.mode.scan_region": "框選翻譯",
    },
    "en": {
        "settings_title": "Settings",
        "settings_subtitle": "Manage translation, OCR, appearance, and scan behavior in one place.",
        "settings_close": "Close",
        "settings_theme_mode": "Theme",
        "settings_ui_language": "UI Language",
        "controller.window_title": "CloudHime",
        "controller.title": "CloudHime v3.0",
        "controller.placeholder.google_api_key": "Google API KEY",
        "controller.button.ai_translation": "AI Translate",
        "controller.button.fullscreen": "Full Screen",
        "controller.button.region": "Region",
        "controller.button.stop": "Stop",
        "controller.button.random_scan_prefix": "Random",
        "controller.button.now": "Translate Now",
        "controller.tooltip.settings": "Settings",
        "controller.status.ready": "Ready and waiting (*´▽`*)",
        "controller.status.ai_model_ready": "AI model: {model}",
        "controller.status.auto_scanning": "{prefix} auto-scanning",
        "controller.status.auto_stopped": "⏸ Auto stopped",
        "controller.status.immediate_scanning": "⚡ Scanning now...",
        "controller.status.need_api_key": "Please enter your Google API key first",
        "controller.status.need_region": "Please set a scan region first",
        "controller.status.region_ready": "Scan region set: {size}",
        "controller.status.capture_running": "🖼 Screenshot translation running...",
        "controller.status.cold_down": "⚡ Cooling down...",
        "controller.status.ai_model_auto_switch": "AI model auto switch: {old_label} -> {new_label}",
        "controller.status.ai_model_full_switch": "{current} is full; next run will switch to {backup}",
        "controller.status.ai_model_full_google": "{current} is full {limit}/{limit}; using Google for now",
        "controller.mode.fullscreen": "🖥 Mode: Full screen",
        "controller.mode.relief": "🧩 Mode: Relief",
        "controller.mode.screenshot": "🖼 Mode: Screenshot",
        "controller.mode.bubble": "💬 Mode: Bubble",
        "controller.mode.scan_fullscreen": "Full screen",
        "controller.mode.scan_region": "Region",
    },
}


def normalize_ui_language(language: Any, fallback: str = DEFAULT_UI_LANGUAGE) -> str:
    candidate = str(language or "").strip()
    if not candidate:
        return fallback
    normalized = _LANGUAGE_ALIASES.get(candidate.lower(), candidate)
    if normalized in SUPPORTED_UI_LANGUAGES:
        return normalized
    if normalized.lower().startswith("zh"):
        return "zh-TW"
    if normalized.lower().startswith("en"):
        return "en"
    return fallback


def get_translation_target_lang(ui_language: Any, fallback: str = DEFAULT_UI_LANGUAGE) -> str:
    return normalize_ui_language(ui_language, fallback=fallback)


def fallback_text(value: Any, fallback: Any = "") -> str:
    text = str(value or "").strip()
    if text:
        return text
    return str(fallback or "")


def tr(key: str, language: Any = DEFAULT_UI_LANGUAGE, fallback: str | None = None, **params: Any) -> str:
    normalized = normalize_ui_language(language)
    catalog = _TRANSLATIONS.get(normalized, {})
    default_catalog = _TRANSLATIONS.get(DEFAULT_UI_LANGUAGE, {})
    text = catalog.get(key) or default_catalog.get(key) or fallback or key
    if params:
        try:
            text = text.format(**params)
        except Exception:
            pass
    return text
