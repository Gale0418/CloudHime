import re
import difflib
from ocr_text_processing import normalize_ocr_text

def normalize_translation_compare_text(text):
    normalized = normalize_ocr_text(text)
    if not normalized:
        return ""
    normalized = re.sub(r"[\s\(\)（）\[\]【】「」『』《》<>“”\"'、，。！？!?…：;；\-—~]+", "", normalized)
    return normalized.lower()

def should_fallback_to_text_translation(source_text_hint, translated_text):
    if re.search(r"[\u3040-\u30ff]", str(translated_text or "")):
        return True
    source_norm = normalize_translation_compare_text(source_text_hint)
    translated_norm = normalize_translation_compare_text(translated_text)
    if not source_norm or not translated_norm:
        return False
    if source_norm == translated_norm:
        return True
    similarity = difflib.SequenceMatcher(None, source_norm, translated_norm).ratio()
    return similarity >= 0.82

def is_suspiciously_short_translation(source_text_hint, translated_text):
    source_norm = normalize_translation_compare_text(source_text_hint)
    translated_norm = normalize_translation_compare_text(translated_text)
    if len(source_norm) < 8 or len(translated_norm) < 2:
        return False
    return len(translated_norm) <= max(4, int(len(source_norm) * 0.35))

def score_ocr_candidate_text(text):
    normalized = normalize_ocr_text(text)
    if not normalized:
        return -10_000
    kana_count = len(re.findall(r"[\u3040-\u30ff]", normalized))
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    ascii_count = sum(ch.isascii() and ch.isalpha() for ch in normalized)
    digit_count = sum(ch.isdigit() for ch in normalized)
    punct_count = sum(ch in "。、，,.!?！？:：;；()[]{}<>/\\|~`" for ch in normalized)
    noise_count = sum(ch in "=_-*" for ch in normalized)
    basic_punct = set("。、，,.!?！？:：;；()（）[]【】{}<>/\\|~`'\"-—・…")
    weird_count = sum(
        1
        for ch in normalized
        if not (ch.isascii() and ch.isalnum())
        and not re.match(r"[\u3040-\u30ff\u4e00-\u9fff]", ch)
        and ch not in basic_punct
        and not ch.isspace()
    )
    return (
        (len(normalized) * 2)
        + (cjk_count * 3)
        + (kana_count * 2)
        + ascii_count
        + digit_count
        - (punct_count * 2)
        - (noise_count * 3)
        - (weird_count * 4)
    )

def choose_better_ocr_candidate(local_text, google_text):
    local_norm = normalize_ocr_text(local_text)
    google_norm = normalize_ocr_text(google_text)
    if not google_norm:
        return local_norm
    if not local_norm:
        return google_norm
    return google_norm

def merge_google_lines_into_items(google_lines, items):
    if not google_lines:
        return list(items)
    local_items = [dict(item) for item in items if normalize_ocr_text(item.get("text", ""))]
    if not local_items:
        return list(items)
    local_items.sort(key=lambda item: (int(item.get("y", 0)), int(item.get("x", 0))))
    if len(google_lines) >= len(local_items):
        if len(google_lines) == len(local_items):
            refined_items = []
            for local_item, google_text in zip(local_items, google_lines):
                refined_item = dict(local_item)
                refined_item["text"] = choose_better_ocr_candidate(local_item.get("text", ""), google_text)
                refined_items.append(refined_item)
            return refined_items
        return list(local_items)
    group_count = max(1, len(google_lines))
    base_size = len(local_items) // group_count
    remainder = len(local_items) % group_count
    group_sizes = [base_size + (1 if index >= group_count - remainder else 0) for index in range(group_count)]
    refined_items = []
    cursor = 0
    for index, group_size in enumerate(group_sizes):
        chunk = local_items[cursor:cursor + group_size]
        cursor += group_size
        if not chunk:
            continue
        x1 = min(int(item.get("x", 0)) for item in chunk)
        y1 = min(int(item.get("y", 0)) for item in chunk)
        x2 = max(int(item.get("x", 0)) + int(item.get("w", 1)) for item in chunk)
        y2 = max(int(item.get("y", 0)) + int(item.get("h", 1)) for item in chunk)
        local_group_text = normalize_ocr_text(
            " ".join(
                normalize_ocr_text(item.get("text", ""))
                for item in chunk
                if normalize_ocr_text(item.get("text", ""))
            )
        )
        refined_items.append({
            "text": choose_better_ocr_candidate(local_group_text, google_lines[min(index, len(google_lines) - 1)]),
            "x": x1,
            "y": y1,
            "w": max(1, x2 - x1),
            "h": max(1, y2 - y1),
        })
    return refined_items
