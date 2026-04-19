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
    translator = translators.get(source_lang)
    if translator is None:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translators[source_lang] = translator
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
    cache_key = (source_lang, normalized_text)
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

        cache_key = ("google-batch", source_lang, tuple(group_texts))
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
            single_cache_key = (source_lang, group_texts[offset])
            remember_translation(translation_cache, single_cache_key, line, cache_limit=cache_limit)

    return [line or "" for line in translated]


def build_gemma_prompt(text: Any) -> str:
    return (
        "你是遊戲畫面即時翻譯助手。"
        "請把輸入內容翻成自然、流暢、口語化的繁體中文（台灣用語）。"
        "保留原本換行數與句子順序，不要加入說明、註解、前言，也不要輸出原文。"
        "若有英文專有名詞可保留，若是日文台詞請優先翻成自然對話。\n\n"
        f"原文：\n{text}"
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


def build_gemma_prompt_v2(text: Any) -> str:
    return (
        "You are a game and manga translation assistant. "
        "Translate the input into natural Traditional Chinese used in Taiwan. "
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


def build_gemma_multimodal_prompt(source_texts: Sequence[Any]) -> str:
    indexed_ocr = build_segmented_ocr_payload(source_texts)
    return (
        "You are a multimodal UI, game, and manga translation assistant.\n"
        "You will receive one screenshot and OCR lines extracted from that same screenshot.\n"
        "Use the screenshot to understand context, UI meaning, title, speaker tone, and ambiguous words.\n"
        "Translate every OCR line into natural Traditional Chinese used in Taiwan.\n"
        "Keep one output item for every input item.\n"
        "Do not skip items. Do not merge items. Do not explain anything.\n"
        "Return JSON only in this exact shape:\n"
        "{\"segments\":[{\"index\":0,\"translation\":\"...\"}]}\n"
        "Rules:\n"
        "- index must match the input index exactly\n"
        "- translation must contain only the translated text\n"
        "- no markdown, no code fence, no comments\n\n"
        f"OCR lines:\n{indexed_ocr}"
    )


def build_gemma_screenshot_prompt(source_text_hint: Any = None) -> str:
    return (
        "You are a Japanese screenshot translation engine for manga pages, game UI, and dialogue screenshots.\n"
        "Translate the screenshot into natural Traditional Chinese used in Taiwan.\n"
        "Return exactly one JSON object and nothing else:\n"
        "{\"translation\":\"...\"}\n"
        "Rules:\n"
        "- The translation value must contain only the translated Chinese text.\n"
        "- Do not include romanization, pinyin, furigana, meaning, context, notes, labels, or explanations.\n"
        "- Do not repeat the source text.\n"
        "- Do not add markdown, code fences, bullets, or extra keys.\n"
        "- Preserve line breaks inside the translation string when they help readability.\n"
        "- For spatial or context words such as \"手前\" and \"奥\", choose the most natural Taiwanese phrasing for the scene.\n"
        "- If the screenshot already contains Traditional Chinese, lightly normalize it only if needed.\n"
        "If you cannot comply, output {\"translation\":\"\"}."
    )


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
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[*\-•]\s*", "", line)
        if re.match(r"^(Input|Task|OCR text|Source text|Translation)\s*[:：]", line, re.IGNORECASE):
            continue
        line = re.sub(r"^(Translation|Output)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
        lines.append(line)

    if not lines:
        return ""

    if len(lines) == 1:
        line = lines[0]
        line = re.sub(r"\s*\([^)]*(romanization|pinyin|direct translation)[^)]*\)", "", line, flags=re.IGNORECASE)
        return line.strip(" \"'")

    candidates = []
    for line in lines:
        quoted = re.findall(r'[\"“「]([\u3040-\u30ff\u4e00-\u9fff][^\"”」]*)[\"”」]', line)
        if quoted:
            candidates.extend(item.strip() for item in quoted if item.strip())
            continue

        if re.search(r"(translated as|translation)", line, re.IGNORECASE):
            parts = re.split(r"[:：]", line, maxsplit=1)
            if len(parts) == 2 and HAS_CJK_PATTERN.search(parts[1]):
                candidates.append(parts[1].strip(" \"'"))
                continue

        stripped = line.strip(" \"'")
        if HAS_CJK_PATTERN.search(stripped):
            candidates.append(stripped)

    if candidates:
        candidates.sort(key=lambda item: (len(item), item))
        return candidates[0]

    preferred = [line for line in lines if not re.match(r"^(Input|Task|Context|Constraints|Original)", line, re.IGNORECASE)]
    return "\n".join(preferred or lines).strip()


def clean_model_output_multiline(text: Any) -> str:
    if not text:
        return ""
    text = str(text).strip().replace("```", "")
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[*\-•\s]+", "", line)
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


def build_gemma_screenshot_prompt_v2(retry_note: str | None = None) -> str:
    retry_block = ""
    if retry_note:
        retry_block = (
            "\nPrevious answer was invalid because it contained non-translation text.\n"
            f"Do not repeat this mistake: {retry_note.strip()}\n"
        )
    return (
        "You are a Japanese screenshot translation engine for manga pages, game UI, and dialogue screenshots.\n"
        "Translate the screenshot into natural Traditional Chinese used in Taiwan.\n"
        "Focus only on the actual Chinese translation, not dictionary notes or analysis.\n"
        "Return exactly one JSON object and nothing else:\n"
        "{\"translation\":\"...\"}\n"
        "Rules:\n"
        "- The translation value must contain only the translated Chinese text.\n"
        "- Do not include romanization, pinyin, furigana, meaning, context, notes, labels, or explanations.\n"
        "- Do not repeat the source text.\n"
        "- Do not add markdown, code fences, bullets, or extra keys.\n"
        "- Preserve line breaks inside the translation string when they help readability.\n"
        "- For spatial or context words such as \"手前\" and \"奥\", choose the most natural Taiwanese phrasing for the scene.\n"
        "- If the screenshot already contains Traditional Chinese, lightly normalize it only if needed.\n"
        "- If you produce anything other than the translation, the answer is invalid.\n"
        "If you cannot comply, output {\"translation\":\"\"}."
        f"{retry_block}"
    )


def clean_screenshot_translation_output(text: Any) -> str:
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

    lines = []
    for raw_line in candidate.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if re.match(r"^(text|translation|output|meaning|context|right column|left column|furigana|romanization)\s*[:：]?", lower):
            continue
        if re.match(r"^[A-Za-z\s]+:\s*$", line):
            continue
        if re.search(r"[\u3040-\u30ff]", line):
            continue
        if re.search(r"[A-Za-z]{4,}", line) and not HAS_CJK_PATTERN.search(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def is_valid_screenshot_translation(text: Any) -> bool:
    if not text:
        return False
    normalized = str(text).strip()
    if not normalized:
        return False
    if re.search(r"[\u3040-\u30ff]", normalized):
        return False
    if re.search(r"[A-Za-z]", normalized):
        return False
    if not HAS_CJK_PATTERN.search(normalized):
        return False
    compact = re.sub(r"[\s\W_]+", "", normalized)
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", compact))
    return cjk_count >= 2 or len(compact) <= 2


def encode_image_for_ai(img_np: Any, max_width: int = DEFAULT_AI_IMAGE_MAX_WIDTH) -> bytes:
    if img_np is None or img_np.size == 0:
        return b""
    height, width = img_np.shape[:2]
    if width > max_width:
        scale = max_width / width
        img_np = cv2.resize(img_np, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    success, encoded = cv2.imencode(".png", img_np)
    return encoded.tobytes() if success else b""


def build_gemma_prompt_conservative(text: Any) -> str:
    return (
        "你是遊戲畫面即時翻譯助手。\n"
        "請把輸入內容翻成自然、流暢、口語化的繁體中文（台灣用語）。\n"
        "保留原本換行數與句子順序，不要加入說明、註解、前言，也不要輸出原文。\n"
        "若有英文專有名詞可保留，若是日文台詞請優先翻成自然對話。\n"
        "OCR 內容可能有破損、缺字或斷行，請優先維持原意並做適度修補；若無法確定，請保守翻譯，不要硬猜。\n\n"
        f"原文：\n{text}"
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
