from __future__ import annotations

import re
from typing import Any

NOISE_ONLY_PATTERN = re.compile(r"^[-_=.,|/\\:;~^]+$")
HAS_CJK_PATTERN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
HORIZONTAL_SPACE_PATTERN = re.compile(r"[^\S\r\n]+")
CLOSING_PUNCTUATION = "，。！？：；、﹐﹒﹔﹕﹖﹗)]}〉》」』】〕］〉〉,.!?;:"
OPENING_PUNCTUATION = "「『（【〔［〈《([{"


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
    """Normalize OCR spacing while preserving meaningful Latin word spacing/newlines."""
    if not text:
        return ""
    normalized = str(text).strip()
    normalized = HORIZONTAL_SPACE_PATTERN.sub(" ", normalized)
    normalized = re.sub(
        r"(?<=[\u3040-\u30ff\u4e00-\u9fff])[^\S\r\n]+(?=[\u3040-\u30ff\u4e00-\u9fff])",
        "",
        normalized,
    )
    closing = re.escape(CLOSING_PUNCTUATION)
    opening = re.escape(OPENING_PUNCTUATION)
    normalized = re.sub(rf"[^\S\r\n]+([{closing}])", r"\1", normalized)
    normalized = re.sub(rf"([{opening}])[^\S\r\n]+", r"\1", normalized)
    normalized = re.sub(
        rf"(?<=[\u3040-\u30ff\u4e00-\u9fff])([{closing}])[^\S\r\n]+(?=[\u3040-\u30ff\u4e00-\u9fff])",
        r"\1",
        normalized,
    )
    return normalized


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
        or left_char in OPENING_PUNCTUATION
        or right_char in CLOSING_PUNCTUATION + ")]"
    )


def _vertical_overlap_ratio(first: dict[str, Any], second: dict[str, Any]) -> float:
    first_top = float(first["y"])
    first_bottom = first_top + float(first["h"])
    second_top = float(second["y"])
    second_bottom = second_top + float(second["h"])
    overlap = max(0.0, min(first_bottom, second_bottom) - max(first_top, second_top))
    return overlap / max(1.0, min(float(first["h"]), float(second["h"])))


def _same_horizontal_line(anchor: dict[str, Any], candidate: dict[str, Any]) -> bool:
    anchor_height = float(anchor["h"])
    candidate_height = float(candidate["h"])
    anchor_center = float(anchor["y"]) + anchor_height / 2.0
    candidate_center = float(candidate["y"]) + candidate_height / 2.0
    center_delta = abs(anchor_center - candidate_center)
    min_height = min(anchor_height, candidate_height)
    return center_delta < min_height * 0.5 or _vertical_overlap_ratio(anchor, candidate) >= 0.8


def _group_horizontal_lines(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group items against a stable, largest-height anchor to avoid chain merges."""
    lines: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda value: (value["y"], value["x"])):
        matching_lines = [
            line
            for line in lines
            if all(_same_horizontal_line(member, item) for member in line["items"])
        ]
        if not matching_lines:
            lines.append({"anchor": item, "items": [item]})
            continue
        line = min(
            matching_lines,
            key=lambda value: abs(
                (float(value["anchor"]["y"]) + float(value["anchor"]["h"]) / 2.0)
                - (float(item["y"]) + float(item["h"]) / 2.0)
            ),
        )
        line["items"].append(item)
        if float(item["h"]) > float(line["anchor"]["h"]):
            line["anchor"] = item
    return [line["items"] for line in lines]


def merge_horizontal_lines(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge horizontal OCR items without mutating input, preserving bbox/confidence."""
    if not items:
        return []

    merged: list[dict[str, Any]] = []
    for line in _group_horizontal_lines(items):
        ordered_line = sorted(line, key=lambda item: (item["x"], item["y"]))
        line_height = max(float(item["h"]) for item in ordered_line)
        idx = 0
        while idx < len(ordered_line):
            base = ordered_line[idx]
            text = base["text"]
            x1, y1 = base["x"], base["y"]
            x2 = base["x"] + base["w"]
            y2 = base["y"] + base["h"]
            confidence_sum = 0.0
            confidence_weight = 0.0

            def add_confidence(item: dict[str, Any]) -> None:
                nonlocal confidence_sum, confidence_weight
                normalized_text = normalize_ocr_text(item.get("text", ""))
                confidence = _normalize_confidence(item.get("confidence"))
                if not normalized_text or confidence is None:
                    return
                weight = float(len(normalized_text))
                confidence_sum += confidence * weight
                confidence_weight += weight

            add_confidence(base)
            next_idx = idx + 1
            while next_idx < len(ordered_line):
                candidate = ordered_line[next_idx]
                if candidate["x"] - x2 < line_height * 2.0:
                    joiner = "" if needs_cjk_tight_join(text, candidate["text"]) else " "
                    text += joiner + candidate["text"]
                    x2 = max(x2, candidate["x"] + candidate["w"])
                    y2 = max(y2, candidate["y"] + candidate["h"])
                    y1 = min(y1, candidate["y"])
                    add_confidence(candidate)
                    next_idx += 1
                else:
                    break
            merged.append(
                {
                    "text": normalize_ocr_text(text),
                    "x": x1,
                    "y": y1,
                    "w": x2 - x1,
                    "h": y2 - y1,
                    "confidence": confidence_sum / confidence_weight if confidence_weight else None,
                }
            )
            idx = next_idx
    return merged


def score_ocr_items(
    raw_items: list[dict[str, Any]],
    *,
    allow_relaxed: bool = False,
) -> tuple[int, list[dict[str, Any]]]:
    if not raw_items:
        return -1, []
    merged_items = merge_horizontal_lines(raw_items)
    filtered_items = [item for item in merged_items if is_valid_content(item["text"])]
    if allow_relaxed:
        filtered_items = [
            item
            for item in merged_items
            if normalize_ocr_text(item.get("text", ""))
            and not NOISE_ONLY_PATTERN.fullmatch(normalize_ocr_text(item.get("text", "")))
        ]
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
