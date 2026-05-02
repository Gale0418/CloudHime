from __future__ import annotations

import base64
import json
import re
from collections import OrderedDict
from typing import Any, Sequence

import cv2
import numpy as np
from deep_translator import GoogleTranslator

from ocr_quality import HAS_CJK_PATTERN, normalize_ocr_text

GOOGLE_TARGET_LANG = "zh-TW"
DEFAULT_AI_IMAGE_MAX_WIDTH = 1536
UI_LANGUAGE_ORDER = ("en", "zh-TW")
UI_LANGUAGE_ALIASES = {
    "zh": "zh-TW",
    "zh-tw": "zh-TW",
    "zh_tw": "zh-TW",
    "tw": "zh-TW",
    "en-us": "en",
    "en-gb": "en",
    "english": "en",
}


def normalize_target_lang(target_lang: Any, fallback: str = GOOGLE_TARGET_LANG) -> str:
    candidate = str(target_lang or "").strip()
    if not candidate:
        candidate = fallback
    normalized = UI_LANGUAGE_ALIASES.get(candidate.lower(), candidate)
    if normalized in UI_LANGUAGE_ORDER:
        return normalized
    if normalized.lower().startswith("zh"):
        return "zh-TW"
    if normalized.lower().startswith("en"):
        return "en"
    return fallback


def target_lang_instruction(target_lang: Any) -> str:
    normalized = normalize_target_lang(target_lang)
    if normalized == "en":
        return "natural English"
    return "natural Traditional Chinese used in Taiwan"


def target_lang_system_prompt(target_lang: Any) -> str:
    target = target_lang_instruction(target_lang)
    return (
        "You are a professional translator for games, manga, and applications. "
        f"Your task is to translate text into {target}. "
        "CRITICAL RULES: 1) Output ONLY the translated text 2) No explanations or analysis "
        "3) No original text or romanization 4) Preserve line breaks 5) Keep natural style"
    )


def source_lang_instruction(source_lang: Any) -> str:
    candidate = str(source_lang or "").strip().lower().replace("_", "-")
    if candidate.startswith("ja"):
        return "Japanese"
    if candidate.startswith("en"):
        return "English"
    if candidate.startswith("zh"):
        return "Traditional Chinese"
    if candidate == "auto":
        return "the source language"
    return str(source_lang or "the source language")
UI_TEXTS = {
    "settings_title": {
        "zh-TW": "設定頁面",
        "en": "Settings",
    },
    "settings_subtitle": {
        "zh-TW": "翻譯 / OCR 設定",
        "en": "Translation / OCR Settings",
    },
    "settings_ocr_title": {
        "zh-TW": "OCR",
        "en": "OCR",
    },
    "settings_ocr_hint": {
        "zh-TW": "管理 OCR 後端、滑鼠穿透與掃描節奏。",
        "en": "Manage OCR backends, passthrough, and scan timing.",
    },
    "settings_pass_through": {
        "zh-TW": "滑鼠穿透框選區",
        "en": "Mouse passthrough",
    },
    "settings_auto_scan_title": {
        "zh-TW": "自動掃描",
        "en": "Auto-scan",
    },
    "settings_auto_scan_hint": {
        "zh-TW": "中心秒數與偏移幅度會同步到主畫面",
        "en": "The interval and jitter are synced to the main window.",
    },
    "settings_random_scan_center": {
        "zh-TW": "中心秒數",
        "en": "Center seconds",
    },
    "settings_random_scan_jitter": {
        "zh-TW": "偏移幅度",
        "en": "Jitter range",
    },
    "settings_threshold_refresh": {
        "zh-TW": "閥值刷新",
        "en": "Threshold refresh",
    },
    "settings_region_render_title": {
        "zh-TW": "渲染設定",
        "en": "Rendering",
    },
    "settings_region_render_hint": {
        "zh-TW": "在框選模式下才會啟用，一共有三種文字顯示方式可以切換",
        "en": "Only applies in region mode. You can switch between three text display styles.",
    },
    "settings_region_render_mode": {
        "zh-TW": "顯示方式",
        "en": "Display mode",
    },
    "settings_render_bubble": {
        "zh-TW": "氣泡模式",
        "en": "Bubble",
    },
    "settings_render_relief": {
        "zh-TW": "浮離模式",
        "en": "Relief",
    },
    "settings_render_screenshot": {
        "zh-TW": "截圖模式",
        "en": "Screenshot",
    },
    "settings_screenshot_prompt_placeholder": {
        "zh-TW": "這裡放截圖模式專用提示詞；留空就會使用預設提示詞。",
        "en": "Optional prompt for screenshot mode. Leave blank to use the default prompt.",
    },
    "settings_relief_title": {
        "zh-TW": "浮離細節",
        "en": "Relief details",
    },
    "settings_relief_hint": {
        "zh-TW": "只在浮離模式才啟用，位移 0 會對齊原位",
        "en": "Only available in Relief mode; a gap of 0 keeps text aligned with the source.",
    },
    "settings_relief_side": {
        "zh-TW": "文字方向",
        "en": "Text side",
    },
    "settings_relief_font": {
        "zh-TW": "文字大小",
        "en": "Font size",
    },
    "settings_relief_gap": {
        "zh-TW": "浮離位移",
        "en": "Offset",
    },
    "settings_relief_opacity": {
        "zh-TW": "選區框透明度",
        "en": "Region opacity",
    },
    "settings_random_scan_summary": {
        "zh-TW": "目前：{center}s 附近 · 約 {low} ~ {high} 秒",
        "en": "Current: around {center}s · about {low} ~ {high} seconds",
    },
    "settings_auto_threshold_refresh_summary": {
        "zh-TW": "目前：每 {minutes} 分鐘重新評估一次閥值",
        "en": "Current: re-evaluate threshold every {minutes} minutes",
    },
    "settings_region_render_summary_bubble": {
        "zh-TW": "目前：氣泡模式 · 保留原本泡泡",
        "en": "Current: Bubble mode · keep the original bubble style",
    },
    "settings_region_render_summary_relief": {
        "zh-TW": "目前：浮離模式 · 文字貼近原文",
        "en": "Current: Relief mode · keep text close to the source",
    },
    "settings_region_render_summary_screenshot": {
        "zh-TW": "目前：截圖模式 · 整塊區域一起理解",
        "en": "Current: Screenshot mode · interpret the whole region together",
    },
    "settings_relief_summary": {
        "zh-TW": "目前：{side} · {font_pt} pt · {gap_px}px · {opacity}%",
        "en": "Current: {side} · {font_pt} pt · {gap_px}px · {opacity}%",
    },
    "settings_relief_side_auto": {
        "zh-TW": "自動",
        "en": "Auto",
    },
    "settings_relief_side_top": {
        "zh-TW": "上方",
        "en": "Top",
    },
    "settings_relief_side_bottom": {
        "zh-TW": "下方",
        "en": "Bottom",
    },
    "settings_relief_side_left": {
        "zh-TW": "左側",
        "en": "Left",
    },
    "settings_relief_side_right": {
        "zh-TW": "右側",
        "en": "Right",
    },
    "settings_appearance": {
        "zh-TW": "外觀",
        "en": "Appearance",
    },
    "settings_dark_mode": {
        "zh-TW": "深色模式",
        "en": "Dark mode",
    },
    "settings_close": {
        "zh-TW": "關閉",
        "en": "Close",
    },
    "settings_reset_defaults": {
        "zh-TW": "重設預設值",
        "en": "Reset to Defaults",
    },
    "settings_cancel": {
        "zh-TW": "取消",
        "en": "Cancel",
    },
    "settings_save": {
        "zh-TW": "儲存",
        "en": "Save",
    },
    "settings_autosave": {
        "zh-TW": "自動儲存",
        "en": "Autosave",
    },
    "settings_synced": {
        "zh-TW": "已同步",
        "en": "Synced",
    },
    "settings_theme_mode": {
        "zh-TW": "顏色模式",
        "en": "Theme",
    },
    "settings_ui_language": {
        "zh-TW": "UI 語言",
        "en": "UI Language",
    },
    "translation_panel_title": {
        "zh-TW": "翻譯功能",
        "en": "Translation",
    },
    "translation_panel_hint": {
        "zh-TW": "Google 翻譯可直接使用；AI 模式才需要 API Key 與模型。",
        "en": "Google translation works out of the box; AI mode needs an API key and model.",
    },
    "translation_mode_google": {
        "zh-TW": "Google 翻譯",
        "en": "Google Translate",
    },
    "translation_mode_ai": {
        "zh-TW": "Gemma AI 翻譯",
        "en": "Gemma AI",
    },
    "translation_api_key": {
        "zh-TW": "Google API KEY",
        "en": "Google API Key",
    },
    "translation_api_key_placeholder": {
        "zh-TW": "輸入 API KEY",
        "en": "Enter API key",
    },
    "translation_ai_model": {
        "zh-TW": "AI 模型",
        "en": "AI Model",
    },
    "translation_gemma_prompt": {
        "zh-TW": "Gemma Prompt",
        "en": "Gemma Prompt",
    },
    "translation_gemma_prompt_placeholder": {
        "zh-TW": "輸入自訂 Gemma 提示詞...",
        "en": "Enter a custom Gemma prompt...",
    },
    "translation_auto_switch": {
        "zh-TW": "自動切換",
        "en": "Auto switch",
    },
    "ocr_backend_title": {
        "zh-TW": "OCR",
        "en": "OCR",
    },
    "ocr_backend_windows": {
        "zh-TW": "Windows OCR",
        "en": "Windows OCR",
    },
    "ocr_backend_google": {
        "zh-TW": "Google OCR",
        "en": "Google OCR",
    },
    "ocr_backend_google_tooltip_ai": {
        "zh-TW": "翻譯前會先用 Gemma 截圖 OCR 協助辨識。",
        "en": "Uses Gemma screenshot OCR assistance before translation.",
    },
    "ocr_backend_google_tooltip_basic": {
        "zh-TW": "需要 Gemma AI 與 Google API KEY 才能使用。",
        "en": "Requires Gemma AI and a Google API key.",
    },
    "ui_language_zh_tw": {
        "zh-TW": "繁體中文",
        "en": "Traditional Chinese",
    },
    "ui_language_en": {
        "zh-TW": "英文",
        "en": "English",
    },
}
THEME_TEXTS = {
    "light": {
        "zh-TW": "淺色模式",
        "en": "Light",
    },
    "dark": {
        "zh-TW": "深色模式",
        "en": "Dark",
    },
    "high_contrast": {
        "zh-TW": "高對比模式",
        "en": "High Contrast",
    },
}


def get_ui_language(source: Any = None, fallback: str = "en") -> str:
    if source is None:
        candidate = fallback
    elif isinstance(source, str):
        candidate = source
    elif hasattr(source, "get_ui_language"):
        try:
            candidate = source.get_ui_language()
        except Exception:
            candidate = None
    else:
        candidate = (
            getattr(source, "ui_language", None)
            or getattr(source, "ui_locale", None)
            or getattr(source, "language", None)
        )
    normalized = str(candidate or fallback).strip()
    lowered = normalized.lower().replace("_", "-")
    normalized = UI_LANGUAGE_ALIASES.get(lowered, normalized)
    if normalized not in UI_LANGUAGE_ORDER:
        if lowered.startswith("en"):
            normalized = "en"
        elif lowered.startswith("zh"):
            normalized = "zh-TW"
        else:
            normalized = fallback if fallback in UI_LANGUAGE_ORDER else "zh-TW"
    return normalized


def ui_text(source: Any, key: str, default: str = "") -> str:
    lang = get_ui_language(source)
    entry = UI_TEXTS.get(key)
    if not entry:
        return default or key
    return entry.get(lang) or entry.get("zh-TW") or entry.get("en") or default or key


def theme_label(theme_key: Any, source: Any = None) -> str:
    lang = get_ui_language(source)
    normalized = str(theme_key or "").strip().lower()
    if normalized in {"system", "default", "light_mode"}:
        normalized = "light"
    entry = THEME_TEXTS.get(normalized)
    if not entry:
        return normalized or "light"
    return entry.get(lang) or entry.get("zh-TW") or entry.get("en") or normalized


def ui_language_label(language_code: Any, source: Any = None) -> str:
    lang = get_ui_language(source)
    normalized = get_ui_language(language_code)
    key = f"ui_language_{normalized.replace('-', '_').lower()}"
    return ui_text(lang, key, default=normalized)


def ui_language_options(source: Any = None) -> list[tuple[str, str]]:
    return [(ui_language_label(code, source), code) for code in UI_LANGUAGE_ORDER]


def relief_side_options(source: Any = None) -> list[tuple[str, str]]:
    return [
        (ui_text(source, "settings_relief_side_auto"), "auto"),
        (ui_text(source, "settings_relief_side_top"), "top"),
        (ui_text(source, "settings_relief_side_bottom"), "bottom"),
        (ui_text(source, "settings_relief_side_left"), "left"),
        (ui_text(source, "settings_relief_side_right"), "right"),
    ]


def detect_source_language(text: Any) -> str:
    text = str(text or "")
    if HAS_CJK_PATTERN.search(text):
        return "ja"
    ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in text)
    if ascii_letters >= max(2, len(text.replace(" ", "")) * 0.4):
        return "en"
    return "auto"


def convert_to_trad(text: Any, cc: Any | None = None) -> Any:
    return cc.convert(text) if cc else text


def get_google_translator(
    translators: dict[str, GoogleTranslator],
    source_lang: str,
    target_lang: str = GOOGLE_TARGET_LANG,
) -> GoogleTranslator:
    cache_key = f"{source_lang}->{target_lang}"
    translator = translators.get(cache_key)
    if translator is None:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translators[cache_key] = translator
    return translator


def get_cached_translation(cache: OrderedDict[Any, Any], cache_key: Any) -> Any:
    cached = cache.get(cache_key)
    if cached is not None:
        cache.move_to_end(cache_key)
    return cached


def remember_translation(
    cache: OrderedDict[Any, Any],
    cache_key: Any,
    translated_text: Any,
    cache_limit: int = 512,
) -> None:
    cache[cache_key] = translated_text
    cache.move_to_end(cache_key)
    if len(cache) > cache_limit:
        cache.popitem(last=False)


def translate_text_google(
    text: Any,
    translators: dict[str, GoogleTranslator],
    translation_cache: OrderedDict[Any, Any],
    *,
    target_lang: str = GOOGLE_TARGET_LANG,
    cache_limit: int = 512,
) -> str:
    normalized_text = normalize_ocr_text(text)
    if not normalized_text:
        return ""
    source_lang = detect_source_language(normalized_text)
    cache_key = (source_lang, target_lang, normalized_text)
    cached = get_cached_translation(translation_cache, cache_key)
    if cached is not None:
        return cached
    translator = get_google_translator(translators, source_lang, target_lang=target_lang)
    translated = translator.translate(normalized_text).strip()
    remember_translation(translation_cache, cache_key, translated, cache_limit=cache_limit)
    return translated


def translate_text_google_batch(
    source_texts: Sequence[Any],
    translators: dict[str, GoogleTranslator],
    translation_cache: OrderedDict[Any, Any],
    *,
    target_lang: str = GOOGLE_TARGET_LANG,
    cache_limit: int = 512,
) -> list[str]:
    normalized_texts = [normalize_ocr_text(text) for text in source_texts]
    if not normalized_texts or any(not text for text in normalized_texts):
        return []

    translated: list[str | None] = [None] * len(normalized_texts)
    index = 0
    while index < len(normalized_texts):
        source_lang = detect_source_language(normalized_texts[index])
        group_start = index
        group_texts = [normalized_texts[index]]
        index += 1
        while index < len(normalized_texts) and detect_source_language(normalized_texts[index]) == source_lang:
            group_texts.append(normalized_texts[index])
            index += 1

        cache_key = ("google-batch", source_lang, target_lang, tuple(group_texts))
        batch_result = get_cached_translation(translation_cache, cache_key)
        if batch_result is None:
            translator = get_google_translator(translators, source_lang, target_lang=target_lang)
            combined_source = "\n".join(group_texts)
            combined_translated = translator.translate(combined_source).strip()
            batch_result = split_translated_lines(combined_translated, len(group_texts))
            if len(batch_result) != len(group_texts):
                return []
            remember_translation(translation_cache, cache_key, batch_result, cache_limit=cache_limit)
        for offset, line in enumerate(batch_result):
            translated[group_start + offset] = line
            single_cache_key = (source_lang, target_lang, group_texts[offset])
            remember_translation(translation_cache, single_cache_key, line, cache_limit=cache_limit)

    return [line or "" for line in translated]


def build_gemma_prompt(text: Any, target_lang: str = GOOGLE_TARGET_LANG, model_name: str = "gemma-3-27b-it") -> str:
    target = target_lang_instruction(target_lang)
    
    # 為1B模型使用簡化prompt
    if model_name == "gemma-3-1b-it":
        return (
            f"Translate to {target}:\n"
            f"{text}\n\n"
            "Translation:"
        )
    
    # 為4B模型使用嚴格限制prompt
    if model_name == "gemma-4-31b-it":
        return (
            "RULES: Translate ONLY. NO analysis. NO explanations. NO notes.\n"
            f"Task: Translate to {target}.\n"
            "Output ONLY the translation text.\n\n"
            f"Text: {text}\n\n"
            "Translation:"
        )
    
    # 標準prompt（適用於27B和其他模型）
    return (
        "You are a professional translator specializing in games, manga, and UI text.\n"
        f"Task: Translate the following text into {target}.\n"
        "Requirements:\n"
        "1. Translate ONLY the text content, no analysis or explanations\n"
        "2. Preserve original line breaks and formatting\n"
        "3. Keep natural, fluent style appropriate for the context\n"
        "4. Do NOT add: explanations, notes, bullet points, romanization, or original text\n"
        "5. For dialogue: keep conversational tone\n"
        "6. For UI text: keep concise and clear\n"
        "7. Output ONLY the translated text\n\n"
        f"Text to translate:\n{text}\n\n"
        "Translation:"
    )


def extract_gemma_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if text.strip():
            return text.strip()
    return ""


def build_gemma_prompt_v2(text: Any, target_lang: str = GOOGLE_TARGET_LANG) -> str:
    target = target_lang_instruction(target_lang)
    return (
        "You are a game and manga translation assistant. "
        f"Translate the input into {target}. "
        "Preserve the original line breaks and sentence order. "
        "Do not add explanations, notes, bullets, romanization, or the original text. "
        "If the source contains dialogue, keep it conversational and concise.\n\n"
        f"Source text:\n{text}"
    )


def build_segmented_ocr_payload(source_texts: Sequence[Any]) -> str:
    rows = []
    for index, text in enumerate(source_texts):
        rows.append(f"{index}\t{normalize_ocr_text(text)}")
    return "\n".join(rows)


def build_gemma_multimodal_prompt(source_texts: Sequence[Any], target_lang: str = GOOGLE_TARGET_LANG) -> str:
    indexed_ocr = build_segmented_ocr_payload(source_texts)
    target = target_lang_instruction(target_lang)
    source_lang = source_lang_instruction(detect_source_language("\n".join(str(text or "") for text in source_texts)))
    return (
        "You are a professional translator specializing in game UI, manga, and application screenshots.\n"
        "Task: Translate the visual content from the screenshot into accurate, natural text.\n"
        "Instructions:\n"
        "1. Examine the screenshot visually and cross-reference with OCR text\n"
        "2. Correct any OCR errors based on what you see in the image\n"
        "3. Translate ONLY the visible text content\n"
        "4. Preserve original formatting, line breaks, and layout\n"
        "5. Do NOT add explanations, notes, analysis, or original text\n"
        "6. Keep the style natural and context-appropriate\n"
        "7. Output ONLY the translated text in the same index format\n\n"
        f"Source language: {source_lang}\n"
        f"Target language: {target}\n\n"
        "OCR extracted text (may contain errors):\n"
        f"{indexed_ocr}\n\n"
        "Translate and output in the same format:"
    )


def build_gemma_screenshot_prompt(source_text_hint: Any = None, target_lang: str = GOOGLE_TARGET_LANG) -> str:
    return build_screenshot_prompt_with_override(source_text_hint, custom_prompt='', target_lang=target_lang)


def split_translated_lines(translated_text: Any, expected_count: int) -> list[str]:
    cleaned_text = clean_model_output(translated_text)
    if expected_count <= 1:
        return [cleaned_text]
    translated_lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    if len(translated_lines) == expected_count:
        return translated_lines
    return []


def clean_model_output(text: Any) -> str:
    if not text:
        return ""
    text = str(text).strip().replace("```", "")
    
    # 移除markdown格式標記
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # 移除粗體
    text = re.sub(r"\*(.*?)\*", r"\1", text)     # 移除斜體
    
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[*\-\s\d\.]+", "", line)
        if re.match(r"^(Input|Task|OCR text|Source text|Translation|Text|Output)\s*[:：]", line, re.IGNORECASE):
            continue
        line = re.sub(r"^(Translation|Output|Text)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
        lines.append(line)

    if not lines:
        return ""

    # 單行處理
    if len(lines) == 1:
        line = lines[0]
        line = re.sub(r"\s*\([^)]*(romanization|pinyin|direct translation|meaning|note|explanation)[^)]*\)", "", line, flags=re.IGNORECASE)
        line = line.strip(" \"'*")
        return line

    # 多行處理 - 尋找包含翻譯內容的行
    translation_lines = []
    for line in lines:
        # 跳過明顯的標籤行
        if re.match(r"^(Note|Explanation|Context|Analysis|Original|Source|Here's the translation)", line, re.IGNORECASE):
            continue
        
        # 清理行
        cleaned = line.strip(" \"'*")
        if cleaned and len(cleaned) > 1:
            translation_lines.append(cleaned)

    # 如果有多行，嘗試組合或選擇最佳行
    if translation_lines:
        # 優先選擇包含中文的行
        chinese_lines = [line for line in translation_lines if HAS_CJK_PATTERN.search(line)]
        if chinese_lines:
            # 如果有多行中文，檢查是否應該組合
            if len(chinese_lines) > 1:
                # 檢查是否為不完整的片段（如只有emoji或標點符號）
                meaningful_lines = [line for line in chinese_lines if len(line.strip()) > 2]
                if meaningful_lines:
                    return "\n".join(meaningful_lines)
            return max(chinese_lines, key=len)
        else:
            # 如果沒有中文，返回最長的行
            return max(translation_lines, key=len)
    
    # 後備方案：返回最後一行
    return lines[-1].strip()


def clean_model_output_multiline(text: Any) -> str:
    if not text:
        return ""
    text = str(text).strip().replace("```", "")
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[*\-\s]+", "", line)
        if re.match(r"^(Input|Task|OCR text|Source text|Translation)\s*[:：]", line, re.IGNORECASE):
            continue
        line = re.sub(r"^(Translation|Output)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
        line = line.strip(" \"'")
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def extract_screenshot_translation(text: Any) -> str:
    if not text:
        return ""
    candidate = str(text).strip().replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            payload = json.loads(candidate[start:end + 1])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            for key in ("translation", "text", "result", "output"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return clean_model_output_multiline(value).strip()
    cleaned = clean_model_output_multiline(candidate)
    if not cleaned:
        return ""
    filtered: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if re.match(r"^(text|translation|output|meaning|context|right column|left column|furigana|romanization)\s*[:：]", lowered):
            continue
        if lowered in {"text:", "translation:", "output:"}:
            continue
        if re.search(r"[A-Za-z]{4,}", stripped) and not HAS_CJK_PATTERN.search(stripped):
            continue
        filtered.append(stripped)
    if filtered:
        return "\n".join(filtered).strip()
    return ""


def parse_segmented_translation_json(text: Any, expected_count: int) -> list[str]:
    if not text:
        return []
    candidate = str(text).strip().replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return []
    candidate = candidate[start:end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return []

    segments = payload.get("segments")
    if not isinstance(segments, list):
        return []

    translated = [""] * expected_count
    seen = set()
    for item in segments:
        if not isinstance(item, dict):
            return []
        index = item.get("index")
        translation = item.get("translation", "")
        if not isinstance(index, int) or not (0 <= index < expected_count):
            return []
        if index in seen:
            return []
        translation = clean_model_output(str(translation))
        if not translation:
            return []
        translated[index] = translation
        seen.add(index)

    if len(seen) != expected_count or any(not line for line in translated):
        return []
    return translated


DEFAULT_SCREENSHOT_SYSTEM_PROMPT = (
    "You are a professional translator specializing in screenshots, UI, and visual content. "
    "Task: Translate all visible text in the image accurately and naturally. "
    "Requirements: 1) Translate ONLY the text content 2) Preserve formatting and layout 3) "
    "Do NOT add explanations, notes, or analysis 4) Keep natural, fluent style 5) Output ONLY translation"
)


def build_gemma_screenshot_prompt_v3(
    source_text_hint: Any = None,
    retry_note: str | None = None,
    target_lang: str = GOOGLE_TARGET_LANG,
) -> str:
    return build_screenshot_prompt_with_override(
        source_text_hint,
        retry_note,
        custom_prompt="",
        target_lang=target_lang,
    )


def build_screenshot_prompt_with_override(
    source_text_hint: Any = None,
    retry_note: str | None = None,
    custom_prompt: str = "",
    target_lang: str = GOOGLE_TARGET_LANG,
) -> str:
    hint_block = ""
    if source_text_hint:
        hint_text = clean_model_output_multiline(str(source_text_hint)).strip()
        if hint_text:
            source_lang = source_lang_instruction(detect_source_language(hint_text))
            hint_block = (
                f"\nSource language hint: {source_lang}.\n"
                "\nOCR hint (may be imperfect, trust the image more):\n"
                f"{hint_text[:1200]}\n"
            )

    retry_block = ""
    if retry_note:
        retry_block = (
            "\nPrevious answer was too literal or contained analysis.\n"
            f"Rewrite it as {target_lang_instruction(target_lang)} only: {retry_note.strip()}\n"
        )

    default_system = target_lang_system_prompt(target_lang)
    custom = custom_prompt.strip() if custom_prompt and custom_prompt.strip() else ""
    system = default_system
    if custom:
        system = (
            f"{default_system}\n"
            f"User instructions (highest priority):\n{custom}"
        )

    return (
        f"{system}\n"
        f"{hint_block}"
        f"{retry_block}"
    )


def build_gemma_screenshot_prompt_v2(
    retry_note: str | None = None,
    target_lang: str = GOOGLE_TARGET_LANG,
) -> str:
    target = target_lang_instruction(target_lang)
    retry_block = ""
    if retry_note:
        retry_block = (
            "\nPrevious answer was invalid because it contained non-translation text.\n"
            f"Do not repeat this mistake: {retry_note.strip()}\n"
        )
    return (
        "You are a Japanese screenshot translation engine for manga pages, game UI, and dialogue screenshots.\n"
        f"Translate the screenshot into {target}.\n"
        "Focus only on the actual translation, not dictionary notes or analysis.\n"
        "Return exactly one JSON object and nothing else:\n"
        "{\"translation\":\"...\"}\n"
        "Rules:\n"
        "- The translation value must contain only the translated text.\n"
        "- Do not include romanization, pinyin, furigana, meaning, context, notes, labels, or explanations.\n"
        "- Do not repeat the source text.\n"
        "- Do not add markdown, code fences, bullets, or extra keys.\n"
        "- Preserve line breaks inside the translation string when they help readability.\n"
        "- For spatial or context words, choose the most natural phrasing for the scene.\n"
        "- If you produce anything other than the translation, the answer is invalid.\n"
        "If you cannot comply, output {\"translation\":\"\"}."
        f"{retry_block}"
    )


def clean_screenshot_translation_output(text: Any) -> str:
    """
    截圖翻譯輸出清理：極度寬鬆，只移除明顯的標籤
    """
    if not text:
        return ""
    
    candidate = str(text).strip().replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    
    # 嘗試解析JSON格式
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            payload = json.loads(candidate[start:end + 1])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            for key in ("translation", "text", "result", "output"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    # 如果不是JSON，直接返回清理後的文本
    # 只移除明顯的標籤行，保留所有其他內容
    lines = []
    for raw_line in candidate.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        
        lower = line.lower()
        # 只移除明顯的標籤行
        if re.match(r"^(text|translation|output|meaning|context|right column|left column|furigana|romanization)\s*[:：]", lower):
            continue
        if re.match(r"^[A-Za-z\s]+:\s*$", line):
            continue
            
        # 保留所有其他內容，包括英文、日文、符號等
        lines.append(line)
    
    result = "\n".join(lines).strip()
    return result if result else candidate  # 如果清理後為空，返回原始內容


def is_valid_screenshot_translation(text: Any) -> bool:
    """
    截圖翻譯驗證：接受所有非空的有效輸出
    因為截圖模式有專用prompt，應該信任AI模型的輸出
    """
    if not text:
        return False
    
    normalized = str(text).strip()
    if not normalized:
        return False
    
    # 只要不是純空白，就認為有效
    # emoji、符號、數字、任何字符都接受
    return len(normalized) >= 1


def encode_image_for_ai(img_np: Any, max_width: int = DEFAULT_AI_IMAGE_MAX_WIDTH) -> bytes:
    if img_np is None or img_np.size == 0:
        return b""
    height, width = img_np.shape[:2]
    if width > max_width:
        scale = max_width / width
        img_np = cv2.resize(img_np, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    success, encoded = cv2.imencode(".png", img_np)
    return encoded.tobytes() if success else b""


DEFAULT_SYSTEM_PROMPT = target_lang_system_prompt(GOOGLE_TARGET_LANG)


def build_gemma_prompt_conservative(text: Any, target_lang: str = GOOGLE_TARGET_LANG) -> str:
    return (
        f"{target_lang_system_prompt(target_lang)}\n\n"
        f"Source text:\n{text}"
    )


def build_gemma_prompt_with_override(
    text: Any,
    custom_prompt: str = "",
    target_lang: str = GOOGLE_TARGET_LANG,
    model_name: str = "gemma-3-27b-it",
) -> str:
    """Return the model-specific prompt with user override if provided."""
    custom = custom_prompt.strip() if custom_prompt and custom_prompt.strip() else ""
    
    # 獲取模型特定的預設prompt
    base_prompt = build_gemma_prompt(text, target_lang, model_name)
    
    # 如果沒有自訂prompt，直接返回模型特定prompt
    if not custom:
        return base_prompt
    
    # 如果有自訂prompt，將其添加到模型特定prompt前面
    # 但需要確保不會重複內容
    return (
        f"User instructions (highest priority):\n{custom}\n\n"
        f"System instructions:\n{base_prompt}"
    )


def build_ai_image_parts(img_np: Any, max_width: int = DEFAULT_AI_IMAGE_MAX_WIDTH) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    full_png = encode_image_for_ai(img_np, max_width=max_width)
    if full_png:
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": base64.b64encode(full_png).decode("ascii"),
            }
        })
    return parts


def get_translation_provider_priority(provider: Any) -> int:
    provider = (provider or "").strip().lower()
    if provider == "gemma-4":
        return 30
    if provider == "gemma-3":
        return 20
    if provider == "google":
        return 10
    return 0


def should_replace_provider(old_provider: Any, new_provider: Any) -> bool:
    return get_translation_provider_priority(new_provider) >= get_translation_provider_priority(old_provider)





