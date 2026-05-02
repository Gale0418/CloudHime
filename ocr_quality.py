from __future__ import annotations

import re
from typing import Any

NOISE_ONLY_PATTERN = re.compile(r"^[-_=.,|/\\:;~^]+$")
HAS_CJK_PATTERN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def _normalize_confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence > 1.0:
        confidence = confidence / 100.0 if confidence > 1.5 else 1.0
    return max(0.0, min(confidence, 1.0))


def _score_text_fragment(text: str, confidence: Any) -> int:
    normalized_text = normalize_ocr_text(text)
    if not normalized_text:
        return 0
    text_len = len(normalized_text)
    confidence_value = _normalize_confidence(confidence)
    if confidence_value is None:
        confidence_value = 0.5
    confidence_bonus = round(confidence_value * 8)
    short_penalty = max(0, 6 - text_len) * 2
    noise_chars = sum(
        1
        for char in normalized_text
        if not (char.isalnum() or HAS_CJK_PATTERN.search(char) or char.isspace())
    )
    noise_penalty = round((noise_chars / max(1, text_len)) * 6)
    cjk_bonus = 3 if HAS_CJK_PATTERN.search(normalized_text) else 0
    return text_len + confidence_bonus + cjk_bonus - short_penalty - noise_penalty


def normalize_ocr_text(text: Any) -> str:
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"(?<=[\u3040-\u30ff\u4e00-\u9fff])\s+(?=[\u3040-\u30ff\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([，。！？：；、」』）])", r"\1", text)
    text = re.sub(r"([「『（])\s+", r"\1", text)
    return text


def is_valid_content(text: Any) -> bool:
    if not text:
        return False
    text = str(text).strip()
    if len(text) == 0:
        return False
    if NOISE_ONLY_PATTERN.match(text):
        return False
    has_cjk = HAS_CJK_PATTERN.search(text)
    if len(text) < 2 and not has_cjk and not text.isdigit():
        return False
    if text.lower() in {"ii", "ll", "rr", "..."}:
        return False
    return True


def needs_cjk_tight_join(left_text: str, right_text: str) -> bool:
    if not left_text or not right_text:
        return False
    left_char = left_text[-1]
    right_char = right_text[0]
    return bool(
        HAS_CJK_PATTERN.search(left_char)
        or HAS_CJK_PATTERN.search(right_char)
        or left_char in "「『（(["
        or right_char in "」』），。！？：；、)]"
    )


def merge_horizontal_lines(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return []
    items = sorted(items, key=lambda item: item["y"])
    lines: list[list[dict[str, Any]]] = []
    current_line = [items[0]]
    for curr in items[1:]:
        prev = current_line[-1]
        prev_cy = prev["y"] + prev["h"] / 2
        curr_cy = curr["y"] + curr["h"] / 2
        if abs(prev_cy - curr_cy) < (min(prev["h"], curr["h"]) * 0.5):
            current_line.append(curr)
        else:
            lines.append(current_line)
            current_line = [curr]
    lines.append(current_line)

    merged: list[dict[str, Any]] = []
    for line in lines:
        line = sorted(line, key=lambda item: item["x"])
        idx = 0
        while idx < len(line):
            base = line[idx]
            text = base["text"]
            x1, y1 = base["x"], base["y"]
            x2, y2 = base["x"] + base["w"], base["y"] + base["h"]
            confidence_sum = 0.0
            confidence_weight = 0.0
            base_confidence = _normalize_confidence(base.get("confidence"))
            if base_confidence is not None:
                base_weight = max(1.0, float(len(normalize_ocr_text(base["text"])) or 1))
                confidence_sum += base_confidence * base_weight
                confidence_weight += base_weight
            next_idx = idx + 1
            while next_idx < len(line):
                cand = line[next_idx]
                if cand["x"] - x2 < (base["h"] * 2.0):
                    joiner = "" if needs_cjk_tight_join(text, cand["text"]) else " "
                    text += joiner + cand["text"]
                    x2 = cand["x"] + cand["w"]
                    y2 = max(y2, cand["y"] + cand["h"])
                    y1 = min(y1, cand["y"])
                    cand_confidence = _normalize_confidence(cand.get("confidence"))
                    if cand_confidence is not None:
                        cand_weight = max(1.0, float(len(normalize_ocr_text(cand["text"])) or 1))
                        confidence_sum += cand_confidence * cand_weight
                        confidence_weight += cand_weight
                    next_idx += 1
                else:
                    break
            merged_confidence = confidence_sum / confidence_weight if confidence_weight else None
            merged.append(
                {
                    "text": normalize_ocr_text(text),
                    "x": x1,
                    "y": y1,
                    "w": x2 - x1,
                    "h": y2 - y1,
                    "confidence": merged_confidence,
                }
            )
            idx = next_idx
    return merged


def score_ocr_items(raw_items: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    if not raw_items:
        return -1, []
    merged_items = merge_horizontal_lines(raw_items)
    filtered_items = [item for item in merged_items if is_valid_content(item["text"])]
    if not filtered_items:
        return 0, []
    score = sum(
        _score_text_fragment(item["text"], item.get("confidence"))
        for item in filtered_items
    )
    return score, filtered_items


def summarize_threshold_candidate(items: list[dict[str, Any]], max_items: int = 8, max_chars: int = 240) -> str:
    if not items:
        return ""
    snippets: list[str] = []
    current_chars = 0
    for item in items[:max_items]:
        text = normalize_ocr_text(item.get("text", ""))
        if not text:
            continue
        snippets.append(text)
        current_chars += len(text)
        if current_chars >= max_chars:
            break
    summary = "\n".join(snippets).strip()
    return summary[:max_chars].strip()
