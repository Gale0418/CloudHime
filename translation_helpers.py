from __future__ import annotations

import base64
import json
import re
from typing import Any, Sequence

import cv2
import numpy as np

from ocr_quality import normalize_ocr_text

AI_IMAGE_MAX_WIDTH = 1536
HAS_CJK_PATTERN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def detect_source_language(text: Any) -> str:
    normalized_text = normalize_ocr_text(text)
    if not normalized_text:
        return "auto"
    if HAS_CJK_PATTERN.search(normalized_text):
        return "ja"
    ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in normalized_text)
    if ascii_letters >= max(2, len(normalized_text.replace(" ", "")) * 0.4):
        return "en"
    return "auto"


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


def build_gemma_prompt(text: Any) -> str:
    return (
        "你是遊戲畫面即時翻譯助手。"
        "請把輸入內容翻成自然、流暢、口語化的繁體中文（台灣用語）。"
        "保留原本換行數與句子順序，不要加入說明、註解、前言，也不要輸出原文。"
        "若有英文專有名詞可保留，若是日文台詞請優先翻成自然對話。\n\n"
        f"原文：\n{normalize_ocr_text(text)}"
    )


def build_gemma_prompt_v2(text: Any) -> str:
    normalized_text = normalize_ocr_text(text)
    return (
        "You are a game and manga translation assistant. "
        "Translate the input into natural Traditional Chinese used in Taiwan. "
        "Preserve the original line breaks and sentence order. "
        "Do not add explanations, notes, bullets, romanization, or the original text. "
        "If the source contains dialogue, keep it conversational and concise.\n\n"
        f"Source text:\n{normalized_text}"
    )


def build_segmented_ocr_payload(source_texts: Sequence[Any]) -> str:
    rows: list[str] = []
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


def clean_model_output(text: Any) -> str:
    if not text:
        return ""
    text = str(text).strip().replace("```", "")
    lines: list[str] = []
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

    candidates: list[str] = []
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


def split_translated_lines(translated_text: Any, expected_count: int) -> list[str]:
    cleaned_text = clean_model_output(translated_text)
    if expected_count <= 1:
        return [cleaned_text]
    translated_lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    if len(translated_lines) == expected_count:
        return translated_lines
    return []


def extract_gemma_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if text.strip():
            return text.strip()
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


def encode_image_for_ai(img_np: np.ndarray | None) -> bytes:
    if img_np is None or img_np.size == 0:
        return b""
    height, width = img_np.shape[:2]
    if width > AI_IMAGE_MAX_WIDTH:
        scale = AI_IMAGE_MAX_WIDTH / width
        img_np = cv2.resize(img_np, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    success, encoded = cv2.imencode(".png", img_np)
    return encoded.tobytes() if success else b""


def build_ai_image_parts(img_np: np.ndarray | None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    full_png = encode_image_for_ai(img_np)
    if full_png:
        parts.append(
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(full_png).decode("ascii"),
                }
            }
        )
    return parts
