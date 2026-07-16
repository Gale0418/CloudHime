import re

NOISE_ONLY_PATTERN = re.compile(r'^[-_=.,|/\\:;~^]+$')
HAS_CJK_PATTERN = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')

def is_valid_content(text):
    if not text:
        return False
    text = text.strip()
    if len(text) == 0:
        return False
    if NOISE_ONLY_PATTERN.match(text):
        return False
    has_cjk = HAS_CJK_PATTERN.search(text)
    if len(text) < 2 and not has_cjk and not text.isdigit():
        return False
    if text.lower() in ['ii', 'll', 'rr', '...']:
        return False
    return True

def needs_cjk_tight_join(left_text, right_text):
    if not left_text or not right_text:
        return False
    left_char = left_text[-1]
    right_char = right_text[0]
    return bool(HAS_CJK_PATTERN.search(left_char) or HAS_CJK_PATTERN.search(right_char) or left_char in "「『（([" or right_char in "」』），。！？：；、)]")

def normalize_ocr_text(text):
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r'(?<=[\u3040-\u30ff\u4e00-\u9fff])\s+(?=[\u3040-\u30ff\u4e00-\u9fff])', '', text)
    text = re.sub(r'\s+([，。！？：；、」』）])', r'\1', text)
    text = re.sub(r'([「『（])\s+', r'\1', text)
    return text

def merge_horizontal_lines(items):
    if not items:
        return []
    
    # FIX: 建立複本，避免原地改動呼叫端傳入的 items (純函式)
    items_copy = list(items)
    items_copy.sort(key=lambda k: k['y'])
    
    lines = []
    current_line = [items_copy[0]]
    for i in range(1, len(items_copy)):
        curr = items_copy[i]
        prev = current_line[-1]
        prev_cy = prev['y'] + prev['h'] / 2
        curr_cy = curr['y'] + curr['h'] / 2
        if abs(prev_cy - curr_cy) < (min(prev['h'], curr['h']) * 0.5):
            current_line.append(curr)
        else:
            lines.append(current_line)
            current_line = [curr]
    lines.append(current_line)
    
    merged = []
    for line in lines:
        line.sort(key=lambda k: k['x'])
        idx = 0
        while idx < len(line):
            base = line[idx]
            text = base['text']
            x1, y1 = base['x'], base['y']
            x2, y2 = base['x']+base['w'], base['y']+base['h']
            next_idx = idx + 1
            while next_idx < len(line):
                cand = line[next_idx]
                if cand['x'] - x2 < (base['h'] * 2.0):
                    joiner = "" if needs_cjk_tight_join(text, cand['text']) else " "
                    text += joiner + cand['text']
                    x2 = max(x2, cand['x'] + cand['w'])
                    y2 = max(y2, cand['y'] + cand['h'])
                    y1 = min(y1, cand['y'])
                    next_idx += 1
                else:
                    break
            merged.append({'text': normalize_ocr_text(text), 'x': x1, 'y': y1, 'w': x2-x1, 'h': y2-y1})
            idx = next_idx
    return merged
