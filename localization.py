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
        "settings_title": "設定",
        "settings_subtitle": "管理翻譯、OCR、外觀和掃描行為。",
        "settings_close": "關閉",
        "settings_theme_mode": "主題",
        "settings_ui_language": "介面語言",
        "controller.window_title": "CloudHime",
        "controller.title": "☁️ CloudHime v3.0",
        "controller.placeholder.google_api_key": "Google API KEY",
        "controller.button.ai_translation": "AI 翻譯",
        "controller.button.fullscreen": "全螢幕",
        "controller.button.region": "區域",
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
        "controller.status.ai_model_auto_switch": "AI 模型自動切換：{old_label} -> {new_label}",
        "controller.status.ai_model_full_switch": "{current} 已滿，下一次會自動切到 {backup}",
        "controller.status.ai_model_full_google": "{current} 已滿 {limit}/{limit}，先改用 Google",
        "controller.mode.fullscreen": "🖥 模式：全螢幕",
        "controller.mode.relief": "🧩 模式：浮雕",
        "controller.mode.screenshot": "🖼 模式：截圖",
        "controller.mode.bubble": "💬 模式：氣泡",
        "controller.mode.scan_fullscreen": "全螢幕",
        "controller.mode.scan_region": "區域",
        "worker.status.threshold_tuning": "🔎 局部微調閥值中...",
        "worker.status.sentence_recheck": "🧠 句子完整度複判中...",
        "worker.status.no_ocr_backend": "❌ 缺少可用 OCR 後端",
        "worker.status.capture_failed": "❌ 擷取螢幕失敗：{error}",
        "worker.status.screenshot_requires_ai": "❌ 截圖模式需要 Gemma AI 與 Google API KEY",
        "worker.status.screenshot_translating": "🖼 截圖模式翻譯中...",
        "worker.status.screenshot_failed": "❌ 截圖翻譯失敗：{error}",
        "worker.status.screen_static": "♻️ 畫面靜止",
        "worker.status.screenshot_done": "✅ 截圖翻譯完成",
        "worker.status.smart_crop": "🧭 智慧裁切分析中...",
        "worker.status.scanning_translating": "🔍 掃描與翻譯中...",
        "worker.status.recognition_error": "❌ 辨識錯誤",
        "worker.status.crop_retry_full": "🧭 智慧裁切結果太少，改用全畫面重試...",
        "worker.status.crop_retry_rotate": "框選區域沒有掃到字，正在改用旋轉重試...",
        "worker.status.crop_retry_zoom": "框選區域沒有掃到文字，請框大一點或換個角度。",
        "worker.status.comic_retry": "📚 漫畫頁切片重試中...",
        "worker.status.best_threshold": "✨ 已選最佳閥值 {threshold}",
        "worker.status.ai_big_translation": "🧠 AI 大圖翻譯...",
        "worker.status.google_translation": "🌐 Google 翻譯中...",
        "worker.status.batch_translate": "{icon} {prefix} 批次補翻 {count} 段...",
        "worker.status.segment_progress": "{icon} {prefix} {current}/{total}",
        "worker.status.translation_done": "✅ 翻譯完成",
        "worker.status.translation_failed": "⚠️ 翻譯失敗",
        "worker.status.no_text": "沒有偵測到文字",
    },
    "en": {
        "settings_title": "Settings",
        "settings_subtitle": "Manage translation, OCR, appearance, and scan behavior in one place.",
        "settings_close": "Close",
        "settings_theme_mode": "Theme",
        "settings_ui_language": "UI Language",
        "controller.window_title": "CloudHime",
        "controller.title": "☁️ CloudHime v3.0",
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
        "worker.status.threshold_tuning": "🔎 Fine-tuning threshold...",
        "worker.status.sentence_recheck": "🧠 Rechecking sentence completeness...",
        "worker.status.no_ocr_backend": "❌ No available OCR backend",
        "worker.status.capture_failed": "❌ Screenshot capture failed: {error}",
        "worker.status.screenshot_requires_ai": "❌ Screenshot mode requires Gemma AI and a Google API key",
        "worker.status.screenshot_translating": "🖼 Screenshot translation running...",
        "worker.status.screenshot_failed": "❌ Screenshot translation failed: {error}",
        "worker.status.screen_static": "♻️ Frame static",
        "worker.status.screenshot_done": "✅ Screenshot translation complete",
        "worker.status.smart_crop": "🧭 Smart crop analyzing...",
        "worker.status.scanning_translating": "🔍 Scanning and translating...",
        "worker.status.recognition_error": "❌ Recognition error",
        "worker.status.crop_retry_full": "🧭 Too few smart-crop results; retrying full screen...",
        "worker.status.crop_retry_rotate": "No text found in the selected area; retrying with rotation...",
        "worker.status.crop_retry_zoom": "No text found in the selected area. Try a larger region or a different angle.",
        "worker.status.comic_retry": "📚 Retrying comic-page slicing...",
        "worker.status.best_threshold": "✨ Best threshold selected: {threshold}",
        "worker.status.ai_big_translation": "🧠 AI large-image translation...",
        "worker.status.google_translation": "🌐 Google translating...",
        "worker.status.batch_translate": "{icon} {prefix} Backfilling {count} segments...",
        "worker.status.segment_progress": "{icon} {prefix} {current}/{total}",
        "worker.status.translation_done": "✅ Translation complete",
        "worker.status.translation_failed": "⚠️ Translation failed",
        "worker.status.no_text": "No text detected",
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
    normalized = normalize_ui_language(ui_language, fallback=fallback)
    # 如果UI是英文，翻譯目標設為英文
    if normalized == "en":
        return "en"
    # 如果UI是中文，翻譯目標設為繁體中文
    elif normalized == "zh-TW":
        return "zh-TW"
    # 其他情況使用預設
    return normalized


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
