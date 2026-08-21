from __future__ import annotations

import difflib
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


def normalize_ocr_confidence(value: Any) -> float | None:
    """Normalize backend confidence values to the inclusive 0..1 range."""
    return _normalize_confidence(value)


def weighted_ocr_confidence(items: list[dict[str, Any]]) -> float | None:
    weighted_total = 0.0
    total_weight = 0
    for item in items or []:
        confidence = _normalize_confidence(item.get("confidence"))
        if confidence is None:
            continue
        weight = max(1, len(normalize_ocr_text(item.get("text", ""))))
        weighted_total += confidence * weight
        total_weight += weight
    if total_weight == 0:
        return None
    return weighted_total / total_weight


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


def should_try_bounded_ocr_rescue(
    items: list[dict[str, Any]],
    *,
    low_confidence_threshold: float = 0.45,
) -> bool:
    """Request the bounded rescue only for empty or explicitly low-confidence OCR."""
    if not items:
        return True
    confidence = weighted_ocr_confidence(items)
    return confidence is not None and confidence < low_confidence_threshold


def select_bounded_ocr_rescue_items(
    baseline_items: list[dict[str, Any]],
    candidate_items: list[dict[str, Any]],
    *,
    minimum_candidate_confidence: float = 0.60,
    minimum_confidence_gain: float = 0.15,
) -> list[dict[str, Any]]:
    """Adopt a nonempty rescue only when confidence and local score both improve."""
    baseline = list(baseline_items or [])
    candidate = list(candidate_items or [])
    if not candidate:
        return baseline
    if not baseline:
        return candidate

    baseline_confidence = weighted_ocr_confidence(baseline)
    candidate_confidence = weighted_ocr_confidence(candidate)
    if baseline_confidence is None or candidate_confidence is None:
        return baseline
    if candidate_confidence < minimum_candidate_confidence:
        return baseline
    if candidate_confidence < baseline_confidence + minimum_confidence_gain:
        return baseline

    baseline_score, _ = score_ocr_items(baseline, allow_relaxed=True)
    candidate_score, filtered_candidate = score_ocr_items(candidate, allow_relaxed=True)
    if not filtered_candidate or candidate_score <= baseline_score:
        return baseline
    return filtered_candidate


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


def are_ocr_texts_consistent(text1: str, text2: str) -> bool:
    """Check whether two OCR text candidates are consistent.

    Short strings (< 4 chars) require exact match or substring inclusion
    where the length difference is small (len ratio >= 0.4).
    Longer strings (>= 4 chars) allow inclusion or fuzzy ratio >= 0.6.
    """
    t1 = normalize_ocr_text(text1)
    t2 = normalize_ocr_text(text2)
    if not t1 or not t2:
        return False
    if t1 == t2:
        return True

    len1 = len(t1)
    len2 = len(t2)
    min_len = min(len1, len2)
    max_len = max(len1, len2)

    if min_len / max_len < 0.4:
        return False

    if min_len < 4:
        return t1 in t2 or t2 in t1

    if t1 in t2 or t2 in t1:
        return True

    return difflib.SequenceMatcher(None, t1, t2).ratio() >= 0.6


def evaluate_ocr_hint_consensus(
    variant_outputs: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Evaluate consensus among OCR preprocessing variant outputs.

    variant_outputs format:
    [
        {
            "name": "color_scaled",
            "is_primary": True,
            "score": score_int,
            "items": filtered_items_list,
            "summary": summary_str,
        },
        ...
    ]

    Returns (hint_text, winning_items).
    Returns ("", []) if consensus fails or inputs are invalid.
    """
    valid_variants = [
        v
        for v in variant_outputs
        if v
        and v.get("summary")
        and is_valid_content(v.get("summary"))
        and v.get("items")
    ]
    if len(valid_variants) < 2:
        return "", []

    n = len(valid_variants)
    consensus_indices = set()
    for i in range(n):
        for j in range(i + 1, n):
            v1 = valid_variants[i]
            v2 = valid_variants[j]
            if are_ocr_texts_consistent(v1["summary"], v2["summary"]):
                if v1.get("is_primary") or v2.get("is_primary"):
                    consensus_indices.add(i)
                    consensus_indices.add(j)

    if not consensus_indices:
        return "", []

    matching_variants = [valid_variants[i] for i in sorted(consensus_indices)]

    primary_matches = [v for v in matching_variants if v.get("is_primary")]
    candidates_to_pick = primary_matches if primary_matches else matching_variants

    winning_variant = max(
        candidates_to_pick,
        key=lambda v: (v.get("score", 0), len(v.get("summary", ""))),
    )
    items = winning_variant.get("items", [])
    hint = summarize_threshold_candidate(items, max_items=6, max_chars=180).strip()

    if not is_valid_content(hint):
        return "", []

    if len(hint) < 4 and not (
        HAS_CJK_PATTERN.search(hint) or hint.isdigit()
    ):
        return "", []

    return hint[:400], items
