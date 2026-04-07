# ==========================================
# 🌟 雲朵翻譯姬 v2.3 - 螢幕 OCR 即時翻譯工具 (邏輯修正版) (｀・ω・´)ゞ
# ==========================================
# 核心引擎: Windows Media OCR (WinRT)
# 翻譯引擎: Google (主) + Argos (備援)
# 架構優化: 移除多餘引用，修正 Google 無法覆蓋 Argos 的邏輯 Bug
# ==========================================

import os
import sys
import asyncio
import base64
import ctypes
import ctypes.wintypes
import random
import threading
import re
import json
import time
from collections import OrderedDict
from urllib import request, error
import numpy as np
import cv2
import mss

# Windows API 相關
import win32con 

# Windows Runtime API
try:
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
except ImportError:
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

# 翻譯套件
from deep_translator import GoogleTranslator

# 繁簡轉換
try:
    from opencc import OpenCC
    OPENCC_AVAILABLE = True
except ImportError:
    OPENCC_AVAILABLE = False
    print("⚠️ 未安裝 opencc，Argos 翻譯將維持簡體。")

from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                               QPushButton, QFrame, QHBoxLayout, QButtonGroup, 
                               QSlider, QLineEdit, QCheckBox, QComboBox, QProgressBar)
from PySide6.QtCore import (Qt, QTimer, Signal, QThread, QObject, 
                            QAbstractNativeEventFilter) # 刪除了 QEvent
from PySide6.QtGui import QCursor, QFontMetrics, QIcon, QPixmap, QColor, QPainter, QFont, QBrush
from PySide6.QtCore import QRect, QPoint
from PySide6.QtGui import QPen

# 防止高 DPI 縮放導致座標錯位
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

TRANSLATION_CACHE_LIMIT = 512
HUD_MEMORY_LIMIT = 160
HUD_OBSERVATION_LIMIT = 6
PREFERRED_TEXT_MEMORY_LIMIT = 256
AUTO_THRESHOLD_MIN = 50
AUTO_THRESHOLD_MAX = 250
AUTO_THRESHOLD_STEPS = 10
MAX_OCR_SCALE_FACTOR = 3.0
MIN_OCR_SCALE_FACTOR = 1.0
AI_IMAGE_MAX_WIDTH = 1536
AI_TOP_CONTEXT_RATIO = 0.22
NOISE_ONLY_PATTERN = re.compile(r'^[-_=.,|/\\:;~^]+$')
HAS_CJK_PATTERN = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
GOOGLE_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMMA_MODEL = "gemma-3-27b-it"
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "cloudhime_settings.json")
MIN_BUBBLE_FONT_PT = 8
MIN_BUBBLE_WIDTH = 96
MIN_BUBBLE_HEIGHT = 42
SUPPORTED_AI_MODELS = [
    ("Gemma 3 27B", "gemma-3-27b-it"),
    ("Gemma 4 31B", "gemma-4-31b-it"),
]
SCAN_MODE_FULLSCREEN = "fullscreen"
SCAN_MODE_REGION = "region"
GOOGLE_BATCH_SIZE = 12
SMART_FULLSCREEN_MAX_REGIONS = 3
SMART_FULLSCREEN_MIN_AREA_RATIO = 0.015
SMART_FULLSCREEN_MAX_AREA_RATIO = 0.82
AUTO_THRESHOLD_REFRESH_INTERVAL_MS = 10 * 60 * 1000
GEMMA_RATE_LIMIT_WINDOW_SEC = 60
GEMMA_RATE_LIMIT_MAX_CALLS = 15

# ==========================================
# 🛡️ 核心：Windows 原生熱鍵過濾器
# ==========================================
class GlobalHotKeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.hotkey_id = 101  # 自定義 ID
        self.is_registered = False

    def register_hotkey(self, hwnd):
        if self.is_registered:
            return
        
        # 使用 0xC0 代表 `~` 鍵
        VK_OEM_3 = 0xC0 
        
        # MOD_NOREPEAT (0x4000) 防止長按連發
        success = ctypes.windll.user32.RegisterHotKey(
            int(hwnd), 
            self.hotkey_id, 
            0x4000, # 無修飾鍵
            VK_OEM_3 
        )
        
        if success:
            print(f"[Hotkey] Registered [~] successfully (HWND: {hwnd})")
            self.is_registered = True
        else:
            err = ctypes.GetLastError()
            print(f"[Hotkey] Registration failed (Error: {err})")

    def unregister_hotkey(self, hwnd):
        if self.is_registered:
            ctypes.windll.user32.UnregisterHotKey(int(hwnd), self.hotkey_id)
            print("[Hotkey] Unregistered.")
            print("🛑 快捷鍵已解除註冊")

    def nativeEventFilter(self, eventType, message):
        # 攔截 Windows 系統消息
        if eventType == b"windows_generic_MSG":
            # 這裡直接用 ctypes.wintypes，不需要額外 import wintypes
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == win32con.WM_HOTKEY:
                if msg.wParam == self.hotkey_id:
                    self.callback() # 觸發回呼
                    return True, 0
        return False, 0

# ==========================================
# 🧹 工具函式
# ==========================================
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
    items.sort(key=lambda k: k['y'])
    lines = []
    current_line = [items[0]]
    for i in range(1, len(items)):
        curr = items[i]
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
                    x2 = cand['x'] + cand['w']
                    y2 = max(y2, cand['y'] + cand['h'])
                    y1 = min(y1, cand['y'])
                    next_idx += 1
                else:
                    break
            merged.append({'text': normalize_ocr_text(text), 'x': x1, 'y': y1, 'w': x2-x1, 'h': y2-y1})
            idx = next_idx
    return merged

# ==========================================
# 🤖 OCR 與翻譯工作執行緒
# ==========================================
class OCRWorker(QObject):
    finished = Signal(list)
    status_msg = Signal(str)
    hide_ui = Signal()
    show_ui = Signal()
    threshold_suggested = Signal(int)

    def __init__(self):
        super().__init__()
        print("[OCR] Initializing OCR engine...")
        self.engine = None
        self.translators = {}
        self.last_combined_text = ""
        self.last_results = []
        self.translation_cache = OrderedDict()
        self.hud_memory = OrderedDict()
        self.preferred_text_memory = OrderedDict()
        self.gemma_call_timestamps = []
        self.google_api_key = ""
        self.gemma_model = DEFAULT_GEMMA_MODEL
        self.use_gemma_translation = False
        self.scan_mode = SCAN_MODE_FULLSCREEN
        self.scan_region = None
        self.auto_threshold_enabled = True
        self.last_auto_threshold_refresh_ms = 0.0
        
        # 狀態標記
        
        self.binary_threshold = 100 
        self.cc = OpenCC('s2t') if OPENCC_AVAILABLE else None
        
        self.init_windows_ocr()

    def init_windows_ocr(self):
        try:
            lang = Language("ja-JP")
            if not OcrEngine.is_language_supported(lang):
                self.engine = OcrEngine.try_create_from_user_profile_languages()
            else:
                self.engine = OcrEngine.try_create_from_language(lang)
            if self.engine:
                print("[OCR] Windows OCR engine started.")
        except Exception as e:
            print(f"[OCR] Initialization failed: {e}")

    async def _run_ocr_async(self, img_np):
        try:
            success, encoded_image = cv2.imencode('.png', img_np)
            if not success:
                return None
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream.get_output_stream_at(0))
            writer.write_bytes(encoded_image.tobytes())
            await writer.store_async()
            await writer.flush_async()
            decoder = await BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async()
            return await self.engine.recognize_async(software_bitmap)
        except Exception:
            return None

    def convert_to_trad(self, text):
        return self.cc.convert(text) if self.cc else text

    def set_google_api_key(self, api_key):
        self.google_api_key = (api_key or "").strip()

    def set_gemma_enabled(self, enabled):
        self.use_gemma_translation = bool(enabled)

    def set_gemma_model(self, model_name):
        model_name = (model_name or "").strip()
        self.gemma_model = model_name or DEFAULT_GEMMA_MODEL

    def set_scan_mode(self, scan_mode):
        self.scan_mode = scan_mode if scan_mode in (SCAN_MODE_FULLSCREEN, SCAN_MODE_REGION) else SCAN_MODE_FULLSCREEN

    def set_scan_region(self, rect):
        self.scan_region = rect if rect and rect[2] > 0 and rect[3] > 0 else None

    def set_auto_threshold_enabled(self, enabled):
        self.auto_threshold_enabled = bool(enabled)
        if not self.auto_threshold_enabled:
            self.last_auto_threshold_refresh_ms = 0.0

    def has_multimodal_ai(self):
        return self.use_gemma_translation and bool(self.google_api_key)

    def prune_gemma_call_timestamps(self):
        cutoff = time.monotonic() - GEMMA_RATE_LIMIT_WINDOW_SEC
        self.gemma_call_timestamps = [ts for ts in self.gemma_call_timestamps if ts >= cutoff]

    def can_call_gemma(self):
        if not self.has_multimodal_ai():
            return False
        self.prune_gemma_call_timestamps()
        return len(self.gemma_call_timestamps) < GEMMA_RATE_LIMIT_MAX_CALLS

    def record_gemma_call(self):
        self.prune_gemma_call_timestamps()
        self.gemma_call_timestamps.append(time.monotonic())

    def detect_source_language(self, text):
        if HAS_CJK_PATTERN.search(text):
            return 'ja'
        ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in text)
        if ascii_letters >= max(2, len(text.replace(" ", "")) * 0.4):
            return 'en'
        return 'auto'

    def get_google_translator(self, source_lang):
        translator = self.translators.get(source_lang)
        if translator is None:
            translator = GoogleTranslator(source=source_lang, target='zh-TW')
            self.translators[source_lang] = translator
        return translator

    def get_cached_translation(self, cache_key):
        cached = self.translation_cache.get(cache_key)
        if cached is not None:
            self.translation_cache.move_to_end(cache_key)
        return cached

    def remember_translation(self, cache_key, translated_text):
        self.translation_cache[cache_key] = translated_text
        self.translation_cache.move_to_end(cache_key)
        if len(self.translation_cache) > TRANSLATION_CACHE_LIMIT:
            self.translation_cache.popitem(last=False)

    def get_translation_provider_priority(self, provider):
        provider = (provider or "").strip().lower()
        if provider == "gemma-4":
            return 30
        if provider == "gemma-3":
            return 20
        if provider == "google":
            return 10
        return 0

    def get_current_ai_provider(self):
        model = (self.gemma_model or "").strip().lower()
        if "gemma-4" in model:
            return "gemma-4"
        if "gemma-3" in model:
            return "gemma-3"
        return "google"

    def should_replace_provider(self, old_provider, new_provider):
        return self.get_translation_provider_priority(new_provider) >= self.get_translation_provider_priority(old_provider)

    def get_preferred_text_entry(self, text):
        key = self.make_hud_memory_key(text)
        if not key:
            return None
        entry = self.preferred_text_memory.get(key)
        if entry is not None:
            self.preferred_text_memory.move_to_end(key)
        return entry

    def remember_preferred_text(self, text, translated_text, provider):
        key = self.make_hud_memory_key(text)
        if not key or not translated_text:
            return
        entry = self.preferred_text_memory.get(key)
        if entry is None:
            entry = {
                "source_text": normalize_ocr_text(text),
                "translated_text": translated_text.strip(),
                "provider": provider,
            }
        elif self.should_replace_provider(entry.get("provider", ""), provider):
            entry["source_text"] = normalize_ocr_text(text)
            entry["translated_text"] = translated_text.strip()
            entry["provider"] = provider
        self.preferred_text_memory[key] = entry
        self.preferred_text_memory.move_to_end(key)
        if len(self.preferred_text_memory) > PREFERRED_TEXT_MEMORY_LIMIT:
            self.preferred_text_memory.popitem(last=False)

    def make_hud_memory_key(self, text):
        normalized = normalize_ocr_text(text)
        if not normalized:
            return ""
        lowered = normalized.lower()
        lowered = re.sub(r'\d+', '#', lowered)
        lowered = re.sub(r'\s+', ' ', lowered).strip()
        return lowered

    def get_hud_memory(self, text):
        hud_key = self.make_hud_memory_key(text)
        if not hud_key:
            return None
        cached = self.hud_memory.get(hud_key)
        if cached is not None:
            self.hud_memory.move_to_end(hud_key)
        return cached

    def remember_hud_observation(self, text, rect, translated_text="", provider=""):
        hud_key = self.make_hud_memory_key(text)
        if not hud_key:
            return

        x, y, w, h = [int(v) for v in rect]
        entry = self.hud_memory.get(hud_key)
        if entry is None:
            entry = {
                "count": 0,
                "last_rect": (x, y, w, h),
                "recent_positions": [],
                "last_text": normalize_ocr_text(text),
                "translated_text": translated_text.strip() if translated_text else "",
                "provider": provider or "",
            }

        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_rect"] = (x, y, w, h)
        entry["last_text"] = normalize_ocr_text(text)
        if translated_text and self.should_replace_provider(entry.get("provider", ""), provider):
            entry["translated_text"] = translated_text.strip()
            entry["provider"] = provider or entry.get("provider", "")

        positions = list(entry.get("recent_positions") or [])
        positions.append((x, y, w, h))
        if len(positions) > HUD_OBSERVATION_LIMIT:
            positions = positions[-HUD_OBSERVATION_LIMIT:]
        entry["recent_positions"] = positions

        self.hud_memory[hud_key] = entry
        self.hud_memory.move_to_end(hud_key)
        if len(self.hud_memory) > HUD_MEMORY_LIMIT:
            self.hud_memory.popitem(last=False)

    def get_best_known_translation(self, text):
        preferred = self.get_preferred_text_entry(text)
        hud_entry = self.get_hud_memory(text)
        if preferred and hud_entry:
            if self.get_translation_provider_priority(preferred.get("provider", "")) >= self.get_translation_provider_priority(hud_entry.get("provider", "")):
                return preferred.get("translated_text", ""), preferred.get("provider", "")
            return hud_entry.get("translated_text", ""), hud_entry.get("provider", "")
        if preferred:
            return preferred.get("translated_text", ""), preferred.get("provider", "")
        if hud_entry:
            return hud_entry.get("translated_text", ""), hud_entry.get("provider", "")
        return "", ""

    def translate_text_google(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return ""
        source_lang = self.detect_source_language(normalized_text)
        cache_key = (source_lang, normalized_text)
        cached = self.get_cached_translation(cache_key)
        if cached is not None:
            return cached
        translator = self.get_google_translator(source_lang)
        translated = translator.translate(normalized_text).strip()
        self.remember_translation(cache_key, translated)
        return translated

    def translate_text_google_with_provider(self, text):
        return self.translate_text_google(text), "google"

    def translate_text_google_batch(self, source_texts):
        normalized_texts = [normalize_ocr_text(text) for text in source_texts]
        if not normalized_texts or any(not text for text in normalized_texts):
            return []

        translated = [None] * len(normalized_texts)
        index = 0
        while index < len(normalized_texts):
            source_lang = self.detect_source_language(normalized_texts[index])
            group_start = index
            group_texts = [normalized_texts[index]]
            index += 1
            while index < len(normalized_texts) and self.detect_source_language(normalized_texts[index]) == source_lang:
                group_texts.append(normalized_texts[index])
                index += 1

            cache_key = ("google-batch", source_lang, tuple(group_texts))
            batch_result = self.get_cached_translation(cache_key)
            if batch_result is None:
                translator = self.get_google_translator(source_lang)
                combined_source = "\n".join(group_texts)
                combined_translated = translator.translate(combined_source).strip()
                batch_result = self.split_translated_lines(combined_translated, len(group_texts))
                if len(batch_result) != len(group_texts):
                    return []
                self.remember_translation(cache_key, batch_result)
            for offset, line in enumerate(batch_result):
                translated[group_start + offset] = line
                single_cache_key = (source_lang, group_texts[offset])
                self.remember_translation(single_cache_key, line)

        return translated

    def build_gemma_prompt(self, text):
        return (
            "你是遊戲畫面即時翻譯助手。"
            "請把輸入內容翻成自然、流暢、口語化的繁體中文（台灣用語）。"
            "保留原本換行數與句子順序，不要加入說明、註解、前言，也不要輸出原文。"
            "若有英文專有名詞可保留，若是日文台詞請優先翻成自然對話。\n\n"
            f"原文：\n{text}"
        )

    def extract_gemma_text(self, payload):
        candidates = payload.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
            if text.strip():
                return text.strip()
        return ""

    def build_gemma_prompt_v2(self, text):
        return (
            "You are a game and manga translation assistant. "
            "Translate the input into natural Traditional Chinese used in Taiwan. "
            "Preserve the original line breaks and sentence order. "
            "Do not add explanations, notes, bullets, romanization, or the original text. "
            "If the source contains dialogue, keep it conversational and concise.\n\n"
            f"Source text:\n{text}"
        )

    def build_segmented_ocr_payload(self, source_texts):
        rows = []
        for index, text in enumerate(source_texts):
            rows.append(f"{index}\t{normalize_ocr_text(text)}")
        return "\n".join(rows)

    def build_gemma_multimodal_prompt(self, source_texts):
        indexed_ocr = self.build_segmented_ocr_payload(source_texts)
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

    def split_translated_lines(self, translated_text, expected_count):
        cleaned_text = self.clean_model_output(translated_text)
        if expected_count <= 1:
            return [cleaned_text]
        translated_lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
        if len(translated_lines) == expected_count:
            return translated_lines
        return []

    def clean_model_output(self, text):
        if not text:
            return ""
        text = text.strip().replace("```", "")
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

    def parse_segmented_translation_json(self, text, expected_count):
        if not text:
            return []
        candidate = text.strip().replace("```json", "").replace("```JSON", "").replace("```", "").strip()
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
            translation = self.clean_model_output(str(translation))
            if not translation:
                return []
            translated[index] = translation
            seen.add(index)

        if len(seen) != expected_count or any(not line for line in translated):
            return []
        return translated

    def encode_image_for_ai(self, img_np):
        if img_np is None or img_np.size == 0:
            return b""
        height, width = img_np.shape[:2]
        if width > AI_IMAGE_MAX_WIDTH:
            scale = AI_IMAGE_MAX_WIDTH / width
            img_np = cv2.resize(img_np, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        success, encoded = cv2.imencode(".png", img_np)
        return encoded.tobytes() if success else b""

    def build_ai_image_parts(self, img_np):
        parts = []
        full_png = self.encode_image_for_ai(img_np)
        if full_png:
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(full_png).decode("ascii")
                }
            })
        return parts

    def translate_text_gemma(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return ""
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        if not self.can_call_gemma():
            raise ValueError("gemma_rate_limited")

        cache_key = ("gemma", self.gemma_model, normalized_text)
        cached = self.get_cached_translation(cache_key)
        if cached is not None:
            return cached

        req_body = {
            "contents": [{
                "parts": [{
                    "text": self.build_gemma_prompt_v2(normalized_text)
                }]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.9,
                "topK": 32,
                "maxOutputTokens": 1024,
                "responseMimeType": "text/plain"
            }
        }
        req = request.Request(
            GOOGLE_API_ENDPOINT.format(model=self.gemma_model),
            data=json.dumps(req_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.google_api_key,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.record_gemma_call()

        translated = self.clean_model_output(self.extract_gemma_text(payload))
        if not translated:
            raise ValueError("empty_gemma_response")

        self.remember_translation(cache_key, translated)
        return translated

    def translate_multimodal_gemma(self, image_parts, source_texts):
        if not source_texts:
            return ""
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        if not image_parts:
            raise ValueError("missing_image_context")
        if not self.can_call_gemma():
            raise ValueError("gemma_rate_limited")

        normalized_texts = tuple(normalize_ocr_text(text) for text in source_texts)
        cache_key = ("gemma-mm", self.gemma_model, normalized_texts)
        cached = self.get_cached_translation(cache_key)
        if cached is not None:
            return cached

        req_body = {
            "contents": [{
                "parts": image_parts + [{
                    "text": self.build_gemma_multimodal_prompt(source_texts)
                }]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.9,
                "topK": 32,
                "maxOutputTokens": 2048,
                "responseMimeType": "text/plain"
            }
        }
        req = request.Request(
            GOOGLE_API_ENDPOINT.format(model=self.gemma_model),
            data=json.dumps(req_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.google_api_key,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.record_gemma_call()

        translated = self.extract_gemma_text(payload)
        if not translated:
            raise ValueError("empty_gemma_multimodal_response")

        self.remember_translation(cache_key, translated)
        return translated

    def translate_text_gemma_with_provider(self, text):
        return self.translate_text_gemma(text), self.get_current_ai_provider()

    def translate_text_preferred(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return ""
        if self.use_gemma_translation and self.google_api_key:
            try:
                return self.translate_text_gemma(normalized_text)
            except (error.URLError, error.HTTPError, TimeoutError, ValueError):
                pass
        return self.translate_text_google(normalized_text)

    def translate_text_preferred_with_provider(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return "", ""
        if self.use_gemma_translation and self.google_api_key:
            try:
                translated = self.translate_text_gemma(normalized_text)
                return translated, self.get_current_ai_provider()
            except (error.URLError, error.HTTPError, TimeoutError, ValueError):
                pass
        translated = self.translate_text_google(normalized_text)
        return translated, "google"

    def translate_text_batch(self, source_texts):
        normalized_texts = [normalize_ocr_text(text) for text in source_texts]
        if not normalized_texts or any(not text for text in normalized_texts):
            return []
        if self.use_gemma_translation and self.google_api_key:
            combined_source = "\n".join(normalized_texts)
            translated = self.translate_text_preferred(combined_source)
            return self.split_translated_lines(translated, len(normalized_texts))
        return self.translate_text_google_batch(normalized_texts)

    def translate_items_in_batches(self, source_texts, batch_size=8):
        translated = [None] * len(source_texts)
        for start in range(0, len(source_texts), batch_size):
            batch = source_texts[start:start + batch_size]
            batch_result = []
            try:
                batch_result = self.translate_text_batch(batch)
            except Exception:
                batch_result = []
            if len(batch_result) == len(batch):
                for offset, line in enumerate(batch_result):
                    translated[start + offset] = line
        return translated

    def translate_items_in_batches_with_providers(self, source_texts, batch_size=8):
        translated = [None] * len(source_texts)
        providers = [None] * len(source_texts)
        batch_provider = self.get_current_ai_provider() if (self.use_gemma_translation and self.google_api_key) else "google"
        for start in range(0, len(source_texts), batch_size):
            batch = source_texts[start:start + batch_size]
            batch_result = []
            try:
                batch_result = self.translate_text_batch(batch)
            except Exception:
                batch_result = []
            if len(batch_result) == len(batch):
                for offset, line in enumerate(batch_result):
                    translated[start + offset] = line
                    providers[start + offset] = batch_provider
        return translated, providers

    def translate_items_with_ai(self, source_texts, image_parts):
        if not source_texts:
            return []
        if self.has_multimodal_ai() and image_parts:
            translated = self.translate_multimodal_gemma(image_parts, source_texts)
            parsed = self.parse_segmented_translation_json(translated, len(source_texts))
            if parsed:
                return parsed
        return self.translate_items_in_batches(source_texts, batch_size=GOOGLE_BATCH_SIZE if not self.has_multimodal_ai() else 8)

    def translate_items_with_ai_and_providers(self, source_texts, image_parts):
        if not source_texts:
            return [], []
        if self.has_multimodal_ai() and image_parts:
            translated = self.translate_multimodal_gemma(image_parts, source_texts)
            parsed = self.parse_segmented_translation_json(translated, len(source_texts))
            if parsed:
                return parsed, [self.get_current_ai_provider()] * len(parsed)
        return self.translate_items_in_batches_with_providers(
            source_texts,
            batch_size=GOOGLE_BATCH_SIZE if not self.has_multimodal_ai() else 8,
        )

    def capture_scan_area(self):
        with mss.mss() as sct:
            if self.scan_mode == SCAN_MODE_REGION and self.scan_region:
                left, top, width, height = self.scan_region
                capture_rect = {
                    "left": max(0, int(left)),
                    "top": max(0, int(top)),
                    "width": max(1, int(width)),
                    "height": max(1, int(height)),
                }
            else:
                capture_rect = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]

            screenshot = sct.grab(capture_rect)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img, capture_rect["left"], capture_rect["top"]

    def clip_region_rect(self, x, y, w, h, img_w, img_h):
        x = max(0, int(x))
        y = max(0, int(y))
        w = max(1, int(w))
        h = max(1, int(h))
        if x >= img_w or y >= img_h:
            return None
        w = min(w, img_w - x)
        h = min(h, img_h - y)
        if w <= 0 or h <= 0:
            return None
        return (x, y, w, h)

    def expand_region_rect(self, rect, pad_x, pad_y, img_w, img_h):
        x, y, w, h = rect
        return self.clip_region_rect(x - pad_x, y - pad_y, w + pad_x * 2, h + pad_y * 2, img_w, img_h)

    def union_region_rect(self, first, second):
        x1 = min(first[0], second[0])
        y1 = min(first[1], second[1])
        x2 = max(first[0] + first[2], second[0] + second[2])
        y2 = max(first[1] + first[3], second[1] + second[3])
        return (x1, y1, x2 - x1, y2 - y1)

    def rect_overlap_ratio(self, first, second):
        ax1, ay1, aw, ah = first
        bx1, by1, bw, bh = second
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0
        inter = (ix2 - ix1) * (iy2 - iy1)
        min_area = max(1, min(aw * ah, bw * bh))
        return inter / min_area

    def should_merge_region_rects(self, first, second):
        if self.rect_overlap_ratio(first, second) >= 0.18:
            return True
        fx1, fy1, fw, fh = first
        sx1, sy1, sw, sh = second
        fx2, fy2 = fx1 + fw, fy1 + fh
        sx2, sy2 = sx1 + sw, sy1 + sh
        horizontal_gap = max(0, max(sx1 - fx2, fx1 - sx2))
        vertical_gap = max(0, max(sy1 - fy2, fy1 - sy2))
        avg_h = max(1, int((fh + sh) / 2))
        if horizontal_gap <= avg_h * 2 and vertical_gap <= avg_h:
            return True
        if vertical_gap <= avg_h * 2 and min(fw, sw) >= avg_h * 4:
            return True
        return False

    def detect_text_dense_regions(self, img):
        img_h, img_w = img.shape[:2]
        if img_h <= 0 or img_w <= 0:
            return []

        scale = 1.0
        work = img
        max_side = max(img_w, img_h)
        if max_side > 1440:
            scale = 1440.0 / max_side
            work = cv2.resize(img, (int(img_w * scale), int(img_h * scale)), interpolation=cv2.INTER_AREA)

        work_h, work_w = work.shape[:2]
        gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        gradient = cv2.convertScaleAbs(cv2.addWeighted(cv2.convertScaleAbs(grad_x), 0.7, cv2.convertScaleAbs(grad_y), 0.3, 0))
        _, binary = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel_w = max(12, int(work_w * 0.018))
        kernel_h = max(3, int(work_h * 0.008))
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, kernel_h))
        morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel, iterations=2)
        morph = cv2.dilate(morph, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, kernel_w // 3), max(2, kernel_h))), iterations=1)

        contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []

        min_area = max(600, int(work_w * work_h * 0.0022))
        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < min_area:
                continue
            if w < max(40, int(work_w * 0.08)) or h < max(16, int(work_h * 0.025)):
                continue
            if h > int(work_h * 0.55):
                continue

            roi = morph[y:y + h, x:x + w]
            density = cv2.countNonZero(roi) / max(1, area)
            if density < 0.045:
                continue

            area_ratio = area / max(1, work_w * work_h)
            if area_ratio > 0.88:
                continue

            center_y_ratio = (y + h / 2) / max(1, work_h)
            edge_penalty = 0.0
            if center_y_ratio < 0.10 or center_y_ratio > 0.93:
                edge_penalty += 8.0
            if x < work_w * 0.04 or (x + w) > work_w * 0.96:
                edge_penalty += 4.0

            wide_bonus = 10.0 if (w / max(1, h)) >= 3.0 else 0.0
            dialogue_bonus = 8.0 if center_y_ratio >= 0.58 and w >= work_w * 0.28 else 0.0
            score = (density * 140.0) + (area_ratio * 100.0) + wide_bonus + dialogue_bonus - edge_penalty

            rect = (
                int(x / scale),
                int(y / scale),
                max(1, int(w / scale)),
                max(1, int(h / scale)),
            )
            pad_x = max(10, int(rect[2] * 0.06))
            pad_y = max(8, int(rect[3] * 0.20))
            expanded = self.expand_region_rect(rect, pad_x, pad_y, img_w, img_h)
            if expanded:
                regions.append({"rect": expanded, "score": score})

        if not regions:
            return []

        regions.sort(key=lambda item: item["score"], reverse=True)
        merged_regions = []
        for region in regions:
            rect = region["rect"]
            score = region["score"]
            merged = False
            for existing in merged_regions:
                if self.should_merge_region_rects(existing["rect"], rect):
                    existing["rect"] = self.union_region_rect(existing["rect"], rect)
                    existing["score"] = max(existing["score"], score) + min(existing["score"], score) * 0.35
                    merged = True
                    break
            if not merged:
                merged_regions.append({"rect": rect, "score": score})

        refined = []
        full_area = img_w * img_h
        for region in merged_regions:
            rect = self.expand_region_rect(region["rect"], 6, 6, img_w, img_h)
            if not rect:
                continue
            area_ratio = (rect[2] * rect[3]) / max(1, full_area)
            if area_ratio < SMART_FULLSCREEN_MIN_AREA_RATIO:
                continue
            refined.append({"rect": rect, "score": region["score"], "area_ratio": area_ratio})

        if not refined:
            return []

        refined.sort(key=lambda item: (item["score"], item["rect"][2] * item["rect"][3]), reverse=True)
        top_regions = refined[:SMART_FULLSCREEN_MAX_REGIONS]
        total_area_ratio = sum(item["area_ratio"] for item in top_regions)
        if total_area_ratio < SMART_FULLSCREEN_MIN_AREA_RATIO or total_area_ratio > SMART_FULLSCREEN_MAX_AREA_RATIO:
            return []
        return [item["rect"] for item in top_regions]

    def detect_manga_page_region(self, img):
        img_h, img_w = img.shape[:2]
        if img_h <= 0 or img_w <= 0:
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_area = img_w * img_h
        top_ignores = [120, 100, 80, 60, 40, 0]
        candidates = []

        for top_ignore in top_ignores:
            if top_ignore >= img_h - 20:
                continue
            roi = gray[top_ignore:, :]
            if roi.size == 0:
                continue
            blur = cv2.GaussianBlur(roi, (5, 5), 0)

            # 漫畫頁通常是整塊偏白的頁面，先找大面積亮區，比抓細文字更穩
            _, white_mask = cv2.threshold(blur, 220, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
            white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            white_mask = cv2.dilate(white_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)), iterations=1)

            contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h
                if area < img_area * 0.05:
                    continue
                if area > img_area * 0.90:
                    continue
                aspect = w / max(1, h)
                if aspect < 0.25 or aspect > 1.25:
                    continue

                crop = roi[y:y + h, x:x + w]
                if crop.size == 0:
                    continue
                bright_ratio = float(np.mean(crop > 180))
                if bright_ratio < 0.60:
                    continue

                page_score = (area / max(1, img_area)) * 120.0 + bright_ratio * 80.0
                candidates.append({
                    "rect": (x, y + top_ignore, w, h),
                    "score": page_score,
                })

        if not candidates:
            return None

        candidates.sort(key=lambda item: item["score"], reverse=True)
        x, y, w, h = candidates[0]["rect"]
        pad_x = max(8, int(w * 0.015))
        pad_y = max(8, int(h * 0.015))
        x = max(0, x - pad_x)
        y = max(0, y - pad_y)
        w = min(img_w - x, w + pad_x * 2)
        h = min(img_h - y, h + pad_y * 2)
        return (x, y, w, h)

    def split_region_into_tiles(self, rect, cols=2, rows=3, overlap=0.12):
        x, y, w, h = [int(v) for v in rect]
        if w <= 0 or h <= 0:
            return []
        cols = max(1, int(cols))
        rows = max(1, int(rows))
        overlap = max(0.0, min(0.4, float(overlap)))
        tile_w = max(1, int(w / cols))
        tile_h = max(1, int(h / rows))
        pad_x = max(0, int(tile_w * overlap))
        pad_y = max(0, int(tile_h * overlap))
        tiles = []
        for row in range(rows):
            for col in range(cols):
                left = x + col * tile_w - pad_x
                top = y + row * tile_h - pad_y
                right = x + (col + 1) * tile_w + pad_x
                bottom = y + (row + 1) * tile_h + pad_y
                tiles.append((left, top, right - left, bottom - top))
        return tiles

    def get_ocr_regions(self, img):
        img_h, img_w = img.shape[:2]
        full_rect = (0, 0, img_w, img_h)
        if self.scan_mode != SCAN_MODE_FULLSCREEN:
            return [full_rect]
        manga_page = self.detect_manga_page_region(img)
        if manga_page:
            return [manga_page]
        regions = self.detect_text_dense_regions(img)
        return regions or [full_rect]

    def build_ocr_image(self, img, threshold, scale_factor=3.0):
        h, w = img.shape[:2]
        img_scaled = cv2.resize(img, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img_scaled, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        img_final = cv2.bitwise_not(binary)
        img_for_ocr = cv2.cvtColor(img_final, cv2.COLOR_GRAY2BGR)
        return img_for_ocr, scale_factor

    def rotate_crop_for_ocr(self, img, orientation):
        if orientation == 90:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        if orientation == 270:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return img

    def remap_items_from_orientation(self, items, orientation, crop_w, crop_h, offset_x, offset_y):
        if orientation == 0:
            return items

        remapped = []
        for item in items:
            x = int(item['x'])
            y = int(item['y'])
            w = int(item['w'])
            h = int(item['h'])
            if orientation == 90:
                remapped.append({
                    'text': item['text'],
                    'x': offset_x + y,
                    'y': offset_y + max(0, crop_h - (x + w)),
                    'w': h,
                    'h': w,
                })
            elif orientation == 270:
                remapped.append({
                    'text': item['text'],
                    'x': offset_x + max(0, crop_w - (y + h)),
                    'y': offset_y + x,
                    'w': h,
                    'h': w,
                })
        return remapped

    def extract_raw_items(self, ocr_result, scale_factor, offset_x, offset_y):
        raw_items = []
        if not ocr_result:
            return raw_items
        for line in ocr_result.lines:
            line_text = line.text
            words = line.words
            if not words or not line_text.strip():
                continue
            x_min = min([w.bounding_rect.x for w in words])
            y_min = min([w.bounding_rect.y for w in words])
            x_max = max([w.bounding_rect.x + w.bounding_rect.width for w in words])
            y_max = max([w.bounding_rect.y + w.bounding_rect.height for w in words])
            raw_items.append({
                'text': line_text,
                'x': int(x_min / scale_factor) + offset_x,
                'y': int(y_min / scale_factor) + offset_y,
                'w': int((x_max - x_min) / scale_factor),
                'h': int((y_max - y_min) / scale_factor),
            })
        return raw_items

    def score_ocr_items(self, raw_items):
        if not raw_items:
            return -1, []
        merged_items = merge_horizontal_lines(raw_items)
        filtered_items = [item for item in merged_items if is_valid_content(item['text'])]
        if not filtered_items:
            return 0, []
        total_chars = sum(len(normalize_ocr_text(item['text'])) for item in filtered_items)
        cjk_lines = sum(1 for item in filtered_items if HAS_CJK_PATTERN.search(item['text']))
        tiny_lines = sum(1 for item in filtered_items if len(item['text'].strip()) <= 1)
        score = (len(filtered_items) * 8) + total_chars + (cjk_lines * 3) - (tiny_lines * 6)
        return score, filtered_items

    def summarize_threshold_candidate(self, items, max_items=8, max_chars=240):
        if not items:
            return ""
        snippets = []
        current_chars = 0
        for item in items[:max_items]:
            text = normalize_ocr_text(item.get('text', ''))
            if not text:
                continue
            snippets.append(text)
            current_chars += len(text)
            if current_chars >= max_chars:
                break
        summary = "\n".join(snippets).strip()
        return summary[:max_chars].strip()

    def build_threshold_judge_prompt(self, candidates):
        rows = []
        for candidate in candidates:
            preview = candidate.get("preview", "").strip() or "(empty)"
            rows.append(
                f"threshold={candidate['threshold']}\n"
                f"local_score={candidate['score']}\n"
                f"text:\n{preview}"
            )
        joined = "\n\n---\n\n".join(rows)
        return (
            "You are evaluating OCR threshold candidates for a live translation tool.\n"
            "Pick the threshold whose OCR text is most likely to represent complete, natural, readable sentences.\n"
            "Prefer: fewer broken fragments, fewer random UI scraps, better sentence continuity, and cleaner wording.\n"
            "Do not prefer a candidate just because it has more total text.\n"
            "Return JSON only in this exact format:\n"
            "{\"best_threshold\":110}\n\n"
            f"Candidates:\n{joined}"
        )

    def choose_threshold_with_llm(self, candidates):
        if not self.google_api_key:
            return None
        shortlist = []
        for candidate in candidates:
            preview = self.summarize_threshold_candidate(candidate.get("items", []))
            if not preview:
                continue
            shortlist.append({
                "threshold": int(candidate["threshold"]),
                "score": int(candidate["score"]),
                "preview": preview,
            })
        if len(shortlist) < 2:
            return None

        cache_key = (
            "threshold-judge",
            self.gemma_model,
            tuple((item["threshold"], item["score"], item["preview"]) for item in shortlist),
        )
        cached = self.get_cached_translation(cache_key)
        if isinstance(cached, int):
            return cached

        req_body = {
            "contents": [{
                "parts": [{
                    "text": self.build_threshold_judge_prompt(shortlist)
                }]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.8,
                "topK": 16,
                "maxOutputTokens": 128,
                "responseMimeType": "text/plain"
            }
        }
        req = request.Request(
            GOOGLE_API_ENDPOINT.format(model=self.gemma_model),
            data=json.dumps(req_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.google_api_key,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))

        raw_text = self.extract_gemma_text(payload)
        if not raw_text:
            return None
        try:
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            parsed = json.loads(raw_text[start:end + 1])
            best_threshold = int(parsed.get("best_threshold"))
        except Exception:
            return None

        valid_thresholds = {item["threshold"] for item in shortlist}
        if best_threshold not in valid_thresholds:
            return None
        self.remember_translation(cache_key, best_threshold)
        return best_threshold

    def run_ocr_with_best_threshold(self, img, offset_x, offset_y, ocr_regions=None, candidate_thresholds=None, orientation_candidates=None):
        base_threshold = int(self.binary_threshold)
        now_ms = time.monotonic() * 1000.0
        should_refresh_auto_threshold = (
            self.auto_threshold_enabled
            and (
                self.last_auto_threshold_refresh_ms <= 0.0
                or (now_ms - self.last_auto_threshold_refresh_ms) >= AUTO_THRESHOLD_REFRESH_INTERVAL_MS
            )
        )

        if candidate_thresholds:
            candidates = [int(value) for value in candidate_thresholds if value is not None]
        elif should_refresh_auto_threshold:
            step_denominator = max(1, AUTO_THRESHOLD_STEPS - 1)
            candidates = [
                AUTO_THRESHOLD_MIN + round((AUTO_THRESHOLD_MAX - AUTO_THRESHOLD_MIN) * index / step_denominator)
                for index in range(AUTO_THRESHOLD_STEPS)
            ]
        else:
            candidates = [base_threshold]
        candidates = sorted({max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, value)) for value in candidates})

        best_threshold = base_threshold
        best_items = []
        best_score = -1
        candidate_results = []
        regions = ocr_regions or [(0, 0, img.shape[1], img.shape[0])]
        orientations = orientation_candidates or [0]

        for threshold in candidates:
            raw_items = []
            for region_x, region_y, region_w, region_h in regions:
                crop = img[region_y:region_y + region_h, region_x:region_x + region_w]
                if crop.size == 0:
                    continue
                crop_best_items = []
                crop_best_score = -1
                crop_w, crop_h = crop.shape[1], crop.shape[0]
                for orientation in orientations:
                    rotated_crop = self.rotate_crop_for_ocr(crop, orientation)
                    img_for_ocr, scale_factor = self.build_ocr_image(rotated_crop, threshold)
                    try:
                        ocr_result = asyncio.run(self._run_ocr_async(img_for_ocr))
                    except Exception:
                        ocr_result = None
                    region_items = self.extract_raw_items(
                        ocr_result,
                        scale_factor,
                        offset_x + region_x,
                        offset_y + region_y,
                    )
                    region_items = self.remap_items_from_orientation(
                        region_items,
                        orientation,
                        crop_w,
                        crop_h,
                        offset_x + region_x,
                        offset_y + region_y,
                    )
                    score, filtered_items = self.score_ocr_items(region_items)
                    if score > crop_best_score:
                        crop_best_score = score
                        crop_best_items = filtered_items
                raw_items.extend(crop_best_items)
            score, filtered_items = self.score_ocr_items(raw_items)
            candidate_results.append({
                "threshold": threshold,
                "score": score,
                "items": filtered_items,
            })
            if score > best_score:
                best_score = score
                best_threshold = threshold
                best_items = filtered_items

        if self.auto_threshold_enabled and self.google_api_key:
            top_candidates = sorted(candidate_results, key=lambda item: item["score"], reverse=True)[:3]
            if len(top_candidates) >= 2:
                self.status_msg.emit("🧠 句子完整度複判中...")
                try:
                    llm_threshold = self.choose_threshold_with_llm(top_candidates)
                except Exception:
                    llm_threshold = None
            else:
                llm_threshold = None
            if llm_threshold is not None:
                for candidate in top_candidates:
                    if candidate["threshold"] == llm_threshold:
                        best_threshold = candidate["threshold"]
                        best_items = candidate["items"]
                        best_score = candidate["score"]
                        break

        if best_threshold != self.binary_threshold:
            self.binary_threshold = best_threshold
            self.threshold_suggested.emit(best_threshold)
        if should_refresh_auto_threshold:
            self.last_auto_threshold_refresh_ms = now_ms
        return best_threshold, best_items

    def collapse_region_items(self, items):
        if not items:
            return []
        text_parts = [normalize_ocr_text(item['text']) for item in items if normalize_ocr_text(item['text'])]
        if not text_parts:
            return []
        x1 = min(item['x'] for item in items)
        y1 = min(item['y'] for item in items)
        x2 = max(item['x'] + item['w'] for item in items)
        y2 = max(item['y'] + item['h'] for item in items)
        return [{
            'text': "\n".join(text_parts),
            'x': x1,
            'y': y1,
            'w': x2 - x1,
            'h': y2 - y1,
        }]

    def run_scan_once(self):
        if not self.engine:
            self.status_msg.emit("❌ 缺少日文套件")
            self.finished.emit([])
            self.show_ui.emit()
            return

        self.hide_ui.emit()
        try:
            img, offset_x, offset_y = self.capture_scan_area()
            ai_image_parts = self.build_ai_image_parts(img)
        except Exception:
            self.finished.emit([])
            self.show_ui.emit()
            return

        ocr_regions = None
        ocr_orientations = [0]
        page_region = None
        if self.scan_mode == SCAN_MODE_FULLSCREEN:
            self.status_msg.emit("🧭 智慧裁切分析中...")
            try:
                page_region = self.detect_manga_page_region(img)
                if page_region:
                    ocr_regions = [page_region]
                    ocr_orientations = [0, 90, 270]
                else:
                    ocr_regions = self.get_ocr_regions(img)
            except Exception:
                ocr_regions = None
                ocr_orientations = [0]
        elif self.scan_mode == SCAN_MODE_REGION:
            # 框選模式先尊重原始方向，英文/一般網頁多半就是 0 度。
            # 真的抓不到再走後面的旋轉重試，避免平白多花時間。
            ocr_orientations = [0]
        self.status_msg.emit("🔍 自動調整清晰度中..." if self.auto_threshold_enabled else f"🔍 辨識中 (閥值:{self.binary_threshold})...")

        try:
            used_threshold, filtered_items = self.run_ocr_with_best_threshold(img, offset_x, offset_y, ocr_regions, None, ocr_orientations)
        except Exception:
            self.status_msg.emit("❌ 辨識錯誤")
            self.finished.emit([])
            self.show_ui.emit()
            return

        if self.scan_mode == SCAN_MODE_FULLSCREEN and len(filtered_items) <= 1:
            if page_region and (not ocr_regions or len(ocr_regions) == 1):
                tile_regions = self.split_region_into_tiles(page_region, cols=2, rows=3, overlap=0.10)
                if tile_regions:
                    self.status_msg.emit("📚 漫畫頁切片重試中...")
                    try:
                        fallback_thresholds = sorted({
                            max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, used_threshold - 10)),
                            max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, used_threshold)),
                            max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, used_threshold + 10)),
                        })
                        used_threshold, filtered_items = self.run_ocr_with_best_threshold(
                            img,
                            offset_x,
                            offset_y,
                            tile_regions,
                            fallback_thresholds,
                            ocr_orientations,
                        )
                    except Exception:
                        filtered_items = []

        if (
            self.scan_mode == SCAN_MODE_FULLSCREEN
            and ocr_regions
            and len(ocr_regions) > 1
            and len(filtered_items) <= 1
        ):
            self.status_msg.emit("🧭 智慧裁切結果太少，改用全畫面重試...")
            try:
                used_threshold, filtered_items = self.run_ocr_with_best_threshold(
                    img,
                    offset_x,
                    offset_y,
                    [(0, 0, img.shape[1], img.shape[0])],
                )
            except Exception:
                filtered_items = []

        if not filtered_items:
            if self.scan_mode == SCAN_MODE_REGION:
                self.status_msg.emit("框選區域沒有掃到字，正在改用旋轉重試...")
                try:
                    retry_thresholds = sorted({
                        max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, used_threshold - 10)),
                        max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, used_threshold)),
                        max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, used_threshold + 10)),
                    })
                    tile_regions = self.split_region_into_tiles((0, 0, img.shape[1], img.shape[0]), cols=2, rows=2, overlap=0.12)
                    retry_regions = tile_regions if tile_regions else [(0, 0, img.shape[1], img.shape[0])]
                    used_threshold, filtered_items = self.run_ocr_with_best_threshold(
                        img,
                        offset_x,
                        offset_y,
                        retry_regions,
                        retry_thresholds,
                        [0, 90, 270],
                    )
                except Exception:
                    filtered_items = []
            if not filtered_items and self.scan_mode == SCAN_MODE_REGION:
                self.status_msg.emit("框選區域沒有掃到文字，請框大一點或換個角度。")
            self.handle_empty()
            return

        self.show_ui.emit()

        merged_items = filtered_items
        if self.scan_mode == SCAN_MODE_REGION and self.scan_region and len(merged_items) > 1:
            y_centers = [item['y'] + item['h'] / 2 for item in merged_items]
            heights = [max(1, item['h']) for item in merged_items]
            vertical_spread = max(y_centers) - min(y_centers)
            avg_height = sum(heights) / len(heights)
            # 只有真的很像單行內容時才合併，避免把多行 console / 日誌整坨壓成一個泡泡。
            if vertical_spread <= avg_height * 0.9 and len(merged_items) <= 3:
                merged_items = self.collapse_region_items(merged_items)
        if self.auto_threshold_enabled:
            self.status_msg.emit(f"✨ 已選最佳閥值 {used_threshold}")
        current_combined_text = "\n".join(item['text'] for item in merged_items)

        # 🌟 判斷當前是否使用 Argos
        current_use_argos = False
        
        # 🌟 邏輯修正：畫面靜止判定
        # 只有在「文字沒變」且「翻譯品質沒有升級需求」時才跳過
        # 如果上一次是 Argos (爛)，這一次是 Google (好)，必須強制執行，不能跳過
        is_upgrade_needed = False

        if current_combined_text == self.last_combined_text:
            self.status_msg.emit("♻️ 畫面靜止")
            self.finished.emit(self.last_results) 
            return

        self.last_combined_text = current_combined_text
        final_results = []

        try:
            self.status_msg.emit("🧠 AI 大圖翻譯..." if self.has_multimodal_ai() else "🌐 Google...")
            source_texts = [item['text'] for item in merged_items]
            translated_list = []
            provider_list = []
            try:
                translated_list, provider_list = self.translate_items_with_ai_and_providers(source_texts, ai_image_parts)
            except Exception:
                translated_list = []
                provider_list = []

            if len(translated_list) != len(merged_items):
                translated_list = [None] * len(merged_items)
            if len(provider_list) != len(merged_items):
                provider_list = [None] * len(merged_items)

            missing_indexes = [index for index, text in enumerate(translated_list) if not text]
            if missing_indexes:
                prefix = "AI" if self.has_multimodal_ai() else "Google"
                icon = "🧠" if prefix == "AI" else "🌐"
                self.status_msg.emit(f"{icon} {prefix} 批次補翻 {len(missing_indexes)} 段...")
                batch_source = [source_texts[index] for index in missing_indexes]
                batch_result, batch_providers = self.translate_items_in_batches_with_providers(batch_source, batch_size=8)
                for offset, translated in enumerate(batch_result):
                    if translated:
                        translated_list[missing_indexes[offset]] = translated
                        provider_list[missing_indexes[offset]] = batch_providers[offset]

            for i, item in enumerate(merged_items):
                trans_text = translated_list[i]
                provider = provider_list[i]
                known_text, known_provider = self.get_best_known_translation(item['text'])
                if known_text and not self.should_replace_provider(known_provider, provider):
                    trans_text = known_text
                    provider = known_provider
                if not trans_text:
                    prefix = "AI" if self.has_multimodal_ai() else "Google"
                    icon = "🧠" if prefix == "AI" else "🌐"
                    self.status_msg.emit(f"{icon} {prefix} {i+1}/{len(merged_items)}")
                    try:
                        trans_text, provider = self.translate_text_preferred_with_provider(item['text'])
                    except Exception:
                        trans_text = item['text']
                        provider = ""

                trans_text = trans_text.strip()
                cache_key = (
                    self.detect_source_language(merged_items[i]['text']),
                    normalize_ocr_text(merged_items[i]['text'])
                )
                self.remember_translation(cache_key, trans_text)
                self.remember_preferred_text(item['text'], trans_text, provider or "")
                self.remember_hud_observation(
                    item['text'],
                    (item['x'], item['y'], item['w'], item['h']),
                    trans_text,
                    provider or "",
                )
                final_results.append((trans_text, item['x'], item['y'], item['w'], item['h']))

            self.last_results = final_results
            self.status_msg.emit("✅ 翻譯完成")
            self.finished.emit(final_results)

        except Exception as e:
            print(f"Error: {e}")
            self.status_msg.emit("⚠️ 翻譯失敗")
            fallback = [(item['text'], item['x'], item['y'], item['w'], item['h']) for item in merged_items]
            self.last_results = fallback
            self.finished.emit(fallback)

    def handle_empty(self):
        if self.last_combined_text != "":
            self.status_msg.emit("💤 畫面無文字")
            self.last_combined_text = ""
            self.last_results = []
        self.finished.emit([])
        self.show_ui.emit()

# ==========================================
# 💬 氣泡與覆蓋層
# ==========================================
class TransBubble(QLabel):
    def __init__(self, parent, text, x, y, w, h, is_dark_mode=False):
        super().__init__(parent)
        self.text_padding = 8
        self.source_rect = QRect(int(x), int(y), max(1, int(w)), max(1, int(h)))
        self.setText(text)
        self.set_theme(is_dark_mode)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMargin(self.text_padding)
        bubble_rect, best_size = self.compute_bubble_layout(text, x, y, w, h)
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setPointSizeF(best_size)
        font.setBold(True)
        self.setFont(font)
        self.setGeometry(bubble_rect)
        self.show()

    def set_theme(self, is_dark):
        if is_dark:
            self.setStyleSheet("background-color: rgba(35,35,35,245); color: #FFFFFF; font-weight: bold; border-radius: 12px; border: 1px solid #555; padding: 2px;")
        else:
            self.setStyleSheet("background-color: rgba(255,255,255,245); color: #000; font-weight: bold; border-radius: 12px; border: 1px solid #DDD; padding: 2px;")

    def fit_text_strictly(self, text, w, h):
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setBold(True)
        for size in range(30, MIN_BUBBLE_FONT_PT - 1, -1):
            font.setPointSizeF(float(size))
            if QFontMetrics(font).boundingRect(0, 0, max(1, w - self.text_padding * 2), 0, Qt.TextWordWrap, text).height() <= max(1, h - self.text_padding * 2):
                return float(size)
        return float(MIN_BUBBLE_FONT_PT)

    def measure_text_height(self, text, w, point_size):
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setBold(True)
        font.setPointSizeF(float(point_size))
        return QFontMetrics(font).boundingRect(
            0,
            0,
            max(1, w - self.text_padding * 2),
            0,
            Qt.TextWordWrap,
            text,
        ).height()

    def compute_bubble_layout(self, text, x, y, w, h):
        parent_rect = self.parent().rect()
        base_w = max(MIN_BUBBLE_WIDTH, w + 10)
        base_h = max(MIN_BUBBLE_HEIGHT, h + 10)
        max_w = min(max(base_w, int(parent_rect.width() * 0.55)), max(base_w, 460))
        max_h = min(max(base_h, int(parent_rect.height() * 0.32)), max(base_h, 320))

        width_candidates = []
        for scale in (1.0, 1.2, 1.45, 1.75, 2.1, 2.5, 3.0):
            width_candidates.append(min(max_w, int(base_w * scale)))
        width_candidates.append(max_w)
        width_candidates = sorted(set(width_candidates))

        best_rect = QRect(x - 1, y - 1, base_w, base_h)
        best_size = self.fit_text_strictly(text, base_w, base_h)
        best_score = (-1, -1, 0)
        source_center_x = x + w / 2
        source_center_y = y + h / 2

        for candidate_w in width_candidates:
            min_font_h = self.measure_text_height(text, candidate_w, MIN_BUBBLE_FONT_PT)
            candidate_h = max(base_h, min_font_h + self.text_padding * 2)
            candidate_h = min(max_h, candidate_h)
            font_size = self.fit_text_strictly(text, candidate_w, candidate_h)
            fits_min_font = self.measure_text_height(text, candidate_w, MIN_BUBBLE_FONT_PT) <= max(1, candidate_h - self.text_padding * 2)
            score = (
                1 if fits_min_font else 0,
                font_size,
                -(candidate_w * candidate_h),
            )
            if score > best_score:
                left = int(round(source_center_x - candidate_w / 2))
                top = int(round(source_center_y - candidate_h / 2))
                left = max(0, min(left, parent_rect.width() - candidate_w))
                top = max(0, min(top, parent_rect.height() - candidate_h))
                best_rect = QRect(left, top, candidate_w, candidate_h)
                best_size = font_size
                best_score = score

        return best_rect, best_size

class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        self.bubbles = []
        self.is_dark = False
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x00000011)
        except Exception:
            pass
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.ghost_mode)
        self.timer.start(50)

    def set_theme_mode(self, is_dark):
        self.is_dark = is_dark
        for b in self.bubbles:
            b.set_theme(is_dark)

    def update_bubbles(self, results):
        self.clear_all()
        for t, x, y, w, h in results:
            self.bubbles.append(TransBubble(self, t, x, y, w, h, self.is_dark))
        self.arrange_bubbles()
        self.setVisible(True)

    def clear_all(self):
        for b in self.bubbles:
            b.deleteLater()
        self.bubbles = []

    def _rect_overlap_area(self, first, second):
        ix1 = max(first.left(), second.left())
        iy1 = max(first.top(), second.top())
        ix2 = min(first.right(), second.right())
        iy2 = min(first.bottom(), second.bottom())
        if ix2 <= ix1 or iy2 <= iy1:
            return 0
        return (ix2 - ix1) * (iy2 - iy1)

    def _clamp_rect_to_screen(self, rect):
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(rect.x(), screen.right() - rect.width() + 1))
        y = max(screen.top(), min(rect.y(), screen.bottom() - rect.height() + 1))
        return QRect(x, y, rect.width(), rect.height())

    def arrange_bubbles(self):
        if not self.bubbles:
            return

        screen = QApplication.primaryScreen().availableGeometry()
        gap = 10
        placed = []
        bubbles = sorted(self.bubbles, key=lambda b: (b.source_rect.y(), b.source_rect.x()))

        for bubble in bubbles:
            original = QRect(bubble.geometry())
            source = QRect(bubble.source_rect)
            max_shift = max(160, min(screen.width(), screen.height()) // 4)
            step = max(18, min(original.height(), original.width()) // 3)
            offsets = [(0, 0)]
            for delta in range(step, max_shift + 1, step):
                offsets.extend([
                    (0, -delta),
                    (0, delta),
                    (delta, 0),
                    (-delta, 0),
                    (delta, -delta),
                    (-delta, -delta),
                    (delta, delta),
                    (-delta, delta),
                ])

            best_rect = QRect(original)
            best_score = None
            for dx, dy in offsets:
                cand = QRect(original)
                cand.translate(dx, dy)
                cand = self._clamp_rect_to_screen(cand)
                overlap = sum(self._rect_overlap_area(cand, placed_rect.adjusted(-gap, -gap, gap, gap)) for placed_rect in placed)
                source_distance = abs(cand.center().x() - source.center().x()) + abs(cand.center().y() - source.center().y())
                offscreen_penalty = 0
                if cand.left() <= screen.left() or cand.right() >= screen.right() or cand.top() <= screen.top() or cand.bottom() >= screen.bottom():
                    offscreen_penalty = 5000
                score = (overlap + offscreen_penalty, source_distance, cand.width() * cand.height())
                if best_score is None or score < best_score:
                    best_score = score
                    best_rect = cand

            bubble.setGeometry(best_rect)
            placed.append(best_rect)

    def ghost_mode(self):
        if not self.isVisible():
            return
        pos = self.mapFromGlobal(QCursor.pos())
        for b in self.bubbles:
            b.setVisible(not b.geometry().adjusted(-20,-20,20,20).contains(pos))

class SelectionOverlay(QWidget):
    selection_made = Signal(object)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowFullScreen)
        self.start_point = None
        self.current_rect = QRect()
        self.is_selecting = False
        self.hide()

    def begin_selection(self):
        self.start_point = None
        self.current_rect = QRect()
        self.is_selecting = False
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 18, 28, 90))
        if not self.current_rect.isNull():
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(self.current_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#4FC3F7"), 2))
            painter.drawRect(self.current_rect)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.position().toPoint()
            self.current_rect = QRect(self.start_point, self.start_point)
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting and self.start_point is not None:
            current = event.position().toPoint()
            self.current_rect = QRect(self.start_point, current).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            rect = self.current_rect.normalized()
            self.hide()
            if rect.width() < 20 or rect.height() < 20:
                self.selection_made.emit(None)
            else:
                self.selection_made.emit((rect.x(), rect.y(), rect.width(), rect.height()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.selection_made.emit(None)
        else:
            super().keyPressEvent(event)

class RegionSelectionFrame(QWidget):
    region_changed = Signal(object)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.margin = 10
        self.min_size = 60
        self.region_rect = None
        self.drag_mode = None
        self.drag_start_global = None
        self.drag_start_rect = None
        self.is_dark = False
        self.hide()

    def set_theme_mode(self, is_dark):
        self.is_dark = bool(is_dark)
        self.update()

    def show_region(self, rect):
        if not rect:
            self.hide()
            self.region_rect = None
            return
        x, y, w, h = [int(v) for v in rect]
        self.region_rect = QRect(x, y, max(self.min_size, w), max(self.min_size, h))
        self._sync_geometry_from_region()
        self.show()
        self.raise_()

    def clear_region(self):
        self.region_rect = None
        self.hide()

    def _sync_geometry_from_region(self):
        if self.region_rect is None:
            return
        outer = self.region_rect.adjusted(-self.margin, -self.margin, self.margin, self.margin)
        self.setGeometry(outer)
        self.update()

    def paintEvent(self, event):
        if self.region_rect is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        border_color = QColor("#55C7F3") if self.is_dark else QColor("#4FC3F7")
        fill_color = QColor(85, 199, 243, 36) if self.is_dark else QColor(79, 195, 247, 30)
        inner = QRect(self.margin, self.margin, self.width() - self.margin * 2, self.height() - self.margin * 2)
        painter.fillRect(inner, fill_color)
        pen = QPen(border_color, 3)
        painter.setPen(pen)
        painter.drawRoundedRect(inner, 8, 8)

        handle_size = 8
        painter.setBrush(border_color)
        painter.setPen(Qt.NoPen)
        for point in self._handle_points(inner):
            painter.drawEllipse(point, handle_size // 2, handle_size // 2)
        painter.end()

    def _handle_points(self, inner):
        return [
            QPoint(inner.left(), inner.top()),
            QPoint(inner.center().x(), inner.top()),
            QPoint(inner.right(), inner.top()),
            QPoint(inner.right(), inner.center().y()),
            QPoint(inner.right(), inner.bottom()),
            QPoint(inner.center().x(), inner.bottom()),
            QPoint(inner.left(), inner.bottom()),
            QPoint(inner.left(), inner.center().y()),
        ]

    def _hit_test(self, pos):
        if self.region_rect is None:
            return None
        inner = QRect(self.margin, self.margin, self.width() - self.margin * 2, self.height() - self.margin * 2)
        edge = 12
        left = abs(pos.x() - inner.left()) <= edge
        right = abs(pos.x() - inner.right()) <= edge
        top = abs(pos.y() - inner.top()) <= edge
        bottom = abs(pos.y() - inner.bottom()) <= edge
        if top and left:
            return "top_left"
        if top and right:
            return "top_right"
        if bottom and left:
            return "bottom_left"
        if bottom and right:
            return "bottom_right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        if left:
            return "left"
        if right:
            return "right"
        return "move"

    def _cursor_for_mode(self, mode):
        mapping = {
            "top_left": Qt.SizeFDiagCursor,
            "bottom_right": Qt.SizeFDiagCursor,
            "top_right": Qt.SizeBDiagCursor,
            "bottom_left": Qt.SizeBDiagCursor,
            "left": Qt.SizeHorCursor,
            "right": Qt.SizeHorCursor,
            "top": Qt.SizeVerCursor,
            "bottom": Qt.SizeVerCursor,
            "move": Qt.SizeAllCursor,
        }
        return mapping.get(mode, Qt.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.region_rect is not None:
            self.drag_mode = self._hit_test(event.position().toPoint())
            self.drag_start_global = event.globalPosition().toPoint()
            self.drag_start_rect = QRect(self.region_rect)
            self.setCursor(self._cursor_for_mode(self.drag_mode))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self.drag_mode and self.drag_start_rect is not None:
            delta = event.globalPosition().toPoint() - self.drag_start_global
            rect = QRect(self.drag_start_rect)
            if self.drag_mode == "move":
                rect.translate(delta)
            else:
                if "left" in self.drag_mode:
                    rect.setLeft(rect.left() + delta.x())
                if "right" in self.drag_mode:
                    rect.setRight(rect.right() + delta.x())
                if "top" in self.drag_mode:
                    rect.setTop(rect.top() + delta.y())
                if "bottom" in self.drag_mode:
                    rect.setBottom(rect.bottom() + delta.y())
                if rect.width() < self.min_size:
                    if "left" in self.drag_mode:
                        rect.setLeft(rect.right() - self.min_size)
                    else:
                        rect.setRight(rect.left() + self.min_size)
                if rect.height() < self.min_size:
                    if "top" in self.drag_mode:
                        rect.setTop(rect.bottom() - self.min_size)
                    else:
                        rect.setBottom(rect.top() + self.min_size)
            self.region_rect = rect.normalized()
            self._sync_geometry_from_region()
            self.region_changed.emit((self.region_rect.x(), self.region_rect.y(), self.region_rect.width(), self.region_rect.height()))
            event.accept()
            return

        self.setCursor(self._cursor_for_mode(self._hit_test(pos)))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_mode = None
        self.drag_start_global = None
        self.drag_start_rect = None
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

class CooldownButton(QPushButton):
    def __init__(self, text=""):
        super().__init__(text)
        self.cooldown_progress = 0
        self.base_bg = QColor("#E0F7FA")
        self.base_fg = QColor("#444444")
        self.border_color = QColor("#87CEEB")
        self.hover_bg = QColor("#B2EBF2")
        self.fill_color = QColor("#4FC3F7")
        self.disabled_bg = QColor("#888888")
        self.disabled_fg = QColor("#CCCCCC")

    def set_theme_colors(self, base_bg, base_fg, border_color, hover_bg, fill_color, disabled_bg, disabled_fg):
        self.base_bg = QColor(base_bg)
        self.base_fg = QColor(base_fg)
        self.border_color = QColor(border_color)
        self.hover_bg = QColor(hover_bg)
        self.fill_color = QColor(fill_color)
        self.disabled_bg = QColor(disabled_bg)
        self.disabled_fg = QColor(disabled_fg)
        self.update()

    def set_cooldown_progress(self, progress):
        self.cooldown_progress = max(0, min(100, int(progress)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        bg = self.base_bg if self.isEnabled() else self.disabled_bg
        fg = self.base_fg if self.isEnabled() else self.disabled_fg
        if self.underMouse() and self.isEnabled():
            bg = self.hover_bg

        painter.setPen(QPen(self.border_color, 2))
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 8, 8)

        if self.cooldown_progress > 0:
            fill_rect = QRect(rect)
            fill_rect.setWidth(max(1, int(rect.width() * (self.cooldown_progress / 100.0))))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(self.fill_color))
            painter.drawRoundedRect(fill_rect, 8, 8)

        painter.setPen(fg)
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignCenter, self.text())
        painter.end()


class StatusChargeBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.progress = 0
        self.label = ""
        self.base_bg = QColor("#E8F8FB")
        self.border_color = QColor("#7FC8E8")
        self.fill_color = QColor("#4FC3F7")
        self.text_color = QColor("#3A5C72")
        self.setFixedHeight(18)

    def set_theme_colors(self, base_bg, border_color, fill_color, text_color):
        self.base_bg = QColor(base_bg)
        self.border_color = QColor(border_color)
        self.fill_color = QColor(fill_color)
        self.text_color = QColor(text_color)
        self.update()

    def set_progress(self, progress, label=""):
        self.progress = max(0, min(100, int(progress)))
        self.label = label or self.label
        self.update()

    def set_label(self, label):
        self.label = label
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(self.border_color, 1))
        painter.setBrush(self.base_bg)
        painter.drawRoundedRect(rect, 8, 8)

        fill_rect = QRect(rect.left(), rect.top(), int(rect.width() * self.progress / 100), rect.height())
        if fill_rect.width() > 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.fill_color)
            painter.drawRoundedRect(fill_rect, 8, 8)

        painter.setPen(self.text_color)
        painter.drawText(rect, Qt.AlignCenter, self.label or f"{self.progress}%")
        painter.end()

class SettingsWindow(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("設定頁面")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.old_pos = None
        self.resize(392, 470)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        self.frame = QFrame()
        root_layout.addWidget(self.frame)

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.header_panel = QFrame()
        header_layout = QVBoxLayout(self.header_panel)
        header_layout.setContentsMargins(14, 14, 14, 14)
        header_layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(2)
        self.lbl_title = QLabel("設定頁面")
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: 800; background: transparent; border: none;")
        self.lbl_subtitle = QLabel("把常用項目收整，少一點雜訊，多一點順手")
        self.lbl_subtitle.setStyleSheet("font-size: 11px; background: transparent; border: none;")
        header_text_layout.addWidget(self.lbl_title)
        header_text_layout.addWidget(self.lbl_subtitle)
        header_row.addLayout(header_text_layout)
        header_row.addStretch()
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.hide)
        header_row.addWidget(self.btn_close)
        header_layout.addLayout(header_row)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self.lbl_autosave = QLabel("自動儲存")
        self.lbl_sync_state = QLabel("已同步到主程式")
        badge_row.addWidget(self.lbl_autosave)
        badge_row.addWidget(self.lbl_sync_state)
        badge_row.addStretch()
        header_layout.addLayout(badge_row)
        layout.addWidget(self.header_panel)

        self.card_translate = QFrame()
        translate_layout = QVBoxLayout(self.card_translate)
        translate_layout.setContentsMargins(14, 14, 14, 14)
        translate_layout.setSpacing(10)
        self.lbl_translate = QLabel("翻譯")
        self.lbl_translate.setStyleSheet("font-weight: bold;")
        self.lbl_translate_hint = QLabel("Google 可以直接用，AI 模式才需要 API Key 和模型")
        self.lbl_translate_hint.setWordWrap(True)
        translate_layout.addWidget(self.lbl_translate)
        translate_layout.addWidget(self.lbl_translate_hint)

        self.lbl_translate_summary = QLabel("目前：Google 翻譯")
        translate_layout.addWidget(self.lbl_translate_summary)

        mode_row = QHBoxLayout()
        self.lbl_translate_mode = QLabel("翻譯模式")
        mode_row.addWidget(self.lbl_translate_mode)
        mode_row.addStretch()
        self.cmb_translate_mode = QComboBox()
        self.cmb_translate_mode.addItem("Google 翻譯", False)
        self.cmb_translate_mode.addItem("Gemma AI 翻譯", True)
        self.cmb_translate_mode.currentIndexChanged.connect(self.on_translate_mode_changed)
        mode_row.addWidget(self.cmb_translate_mode)
        translate_layout.addLayout(mode_row)

        self.advanced_translate_frame = QFrame()
        advanced_translate_layout = QVBoxLayout(self.advanced_translate_frame)
        advanced_translate_layout.setContentsMargins(12, 12, 12, 12)
        advanced_translate_layout.setSpacing(8)
        self.lbl_advanced_translate = QLabel("進階翻譯設定")
        self.lbl_advanced_hint = QLabel("AI 模式才會用到這些設定")
        self.lbl_advanced_hint.setWordWrap(True)
        advanced_translate_layout.addWidget(self.lbl_advanced_translate)
        advanced_translate_layout.addWidget(self.lbl_advanced_hint)

        self.lbl_api_key = QLabel("Google API KEY")
        advanced_translate_layout.addWidget(self.lbl_api_key)
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.input_api_key.setPlaceholderText("輸入 Google API KEY")
        self.input_api_key.textChanged.connect(self.on_api_key_text_changed)
        advanced_translate_layout.addWidget(self.input_api_key)

        self.lbl_ai_model = QLabel("AI 模型")
        advanced_translate_layout.addWidget(self.lbl_ai_model)
        self.cmb_ai_model = QComboBox()
        for label, model_name in SUPPORTED_AI_MODELS:
            self.cmb_ai_model.addItem(label, model_name)
        self.cmb_ai_model.currentIndexChanged.connect(self.on_ai_model_changed)
        advanced_translate_layout.addWidget(self.cmb_ai_model)
        translate_layout.addWidget(self.advanced_translate_frame)
        layout.addWidget(self.card_translate)
        self.advanced_translate_frame.setVisible(False)

        self.card_ocr = QFrame()
        ocr_layout = QVBoxLayout(self.card_ocr)
        ocr_layout.setContentsMargins(12, 12, 12, 12)
        ocr_layout.setSpacing(8)
        self.lbl_ocr = QLabel("OCR")
        self.lbl_ocr.setStyleSheet("font-weight: bold;")
        self.lbl_ocr_hint = QLabel("自動閥值與字元清理都會影響辨識品質")
        self.lbl_ocr_hint.setWordWrap(True)
        ocr_layout.addWidget(self.lbl_ocr)
        ocr_layout.addWidget(self.lbl_ocr_hint)
        self.chk_auto_threshold = QCheckBox("自動挑最佳閥值")
        self.chk_auto_threshold.toggled.connect(self.controller.set_auto_threshold_mode)
        ocr_layout.addWidget(self.chk_auto_threshold)

        threshold_row = QHBoxLayout()
        self.slider_threshold = QSlider(Qt.Horizontal)
        self.slider_threshold.setRange(50, 240)
        self.slider_threshold.valueChanged.connect(self.controller.update_threshold)
        threshold_row.addWidget(self.slider_threshold)
        self.lbl_threshold = QLabel("100")
        self.lbl_threshold.setAlignment(Qt.AlignCenter)
        self.lbl_threshold.setFixedWidth(44)
        threshold_row.addWidget(self.lbl_threshold)
        ocr_layout.addLayout(threshold_row)
        layout.addWidget(self.card_ocr)

        self.card_appearance = QFrame()
        appearance_layout = QVBoxLayout(self.card_appearance)
        appearance_layout.setContentsMargins(12, 12, 12, 12)
        appearance_layout.setSpacing(8)
        self.lbl_appearance = QLabel("外觀")
        self.lbl_appearance.setStyleSheet("font-weight: bold;")
        self.chk_dark_mode = QCheckBox("深色模式")
        self.chk_dark_mode.toggled.connect(self.controller.set_theme_mode)
        appearance_layout.addWidget(self.lbl_appearance)
        appearance_layout.addWidget(self.chk_dark_mode)
        layout.addWidget(self.card_appearance)

        layout.addStretch()

    def on_translate_mode_changed(self, index):
        use_ai = bool(self.cmb_translate_mode.itemData(index))
        self.controller.btn_ai_mode.setChecked(use_ai)
        self.controller.toggle_ai_translation(use_ai)
        self.set_translate_advanced_visible(use_ai)
        self.update_translate_summary()

    def on_api_key_text_changed(self, text):
        self.controller.on_api_key_changed(text)
        self.update_translate_summary()

    def on_ai_model_changed(self, index):
        self.controller.on_ai_model_changed(index)
        self.update_translate_summary()

    def set_translate_advanced_visible(self, visible):
        self.advanced_translate_frame.setVisible(visible)

    def update_translate_summary(self):
        use_ai = bool(self.cmb_translate_mode.itemData(self.cmb_translate_mode.currentIndex()))
        model_name = self.cmb_ai_model.currentText() if self.cmb_ai_model.count() else "Gemma"
        if use_ai:
            key_state = "已輸入 API KEY" if self.input_api_key.text().strip() else "尚未輸入 API KEY"
            self.lbl_translate_summary.setText(f"目前：AI 翻譯 · {model_name} · {key_state}")
        else:
            self.lbl_translate_summary.setText("目前：Google 翻譯 · 免 API KEY")

    def sync_from_controller(self):
        self.chk_dark_mode.blockSignals(True)
        self.chk_dark_mode.setChecked(self.controller.is_dark_mode)
        self.chk_dark_mode.blockSignals(False)

        self.slider_threshold.blockSignals(True)
        self.slider_threshold.setValue(self.controller.slider.value())
        self.slider_threshold.blockSignals(False)
        self.lbl_threshold.setText(str(self.controller.slider.value()))
        self.chk_auto_threshold.blockSignals(True)
        self.chk_auto_threshold.setChecked(self.controller.worker.auto_threshold_enabled)
        self.chk_auto_threshold.blockSignals(False)

        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(self.controller.worker.google_api_key)
        self.input_api_key.blockSignals(False)

        self.cmb_ai_model.blockSignals(True)
        self.cmb_ai_model.setCurrentIndex(self.controller.cmb_ai_model.currentIndex())
        self.cmb_ai_model.blockSignals(False)

        self.cmb_translate_mode.blockSignals(True)
        self.cmb_translate_mode.setCurrentIndex(1 if self.controller.btn_ai_mode.isChecked() else 0)
        self.cmb_translate_mode.blockSignals(False)
        self.set_translate_advanced_visible(self.controller.btn_ai_mode.isChecked())
        self.update_translate_summary()

    def update_theme(self, is_dark):
        if is_dark:
            bg = "rgba(34, 39, 46, 242)"
            card_bg = "rgba(56, 64, 74, 220)"
            text = "#EAF7FF"
            subtext = "#B7CCD9"
            border = "#5B6B78"
            accent = "#55C7F3"
            accent_soft = "rgba(85, 199, 243, 0.18)"
            input_bg = "#2F3942"
        else:
            bg = "rgba(240, 248, 255, 236)"
            card_bg = "rgba(255, 255, 255, 225)"
            text = "#39566B"
            subtext = "#6C8A9D"
            border = "#9DDCF2"
            accent = "#4FC3F7"
            accent_soft = "rgba(79, 195, 247, 0.16)"
            input_bg = "#FFFFFF"
        self.setStyleSheet(
            f"QWidget {{ color: {text}; }}"
            f"QFrame {{ border: none; }}"
            f"QLineEdit, QComboBox {{ background-color: {input_bg}; color: {text}; border: 1px solid {border}; border-radius: 10px; padding: 7px 10px; selection-background-color: {accent}; }}"
            f"QLineEdit:focus, QComboBox:focus {{ border: 2px solid {accent}; }}"
            f"QComboBox::drop-down {{ border: none; width: 22px; }}"
            f"QComboBox::down-arrow {{ image: none; }}"
            f"QCheckBox {{ color: {text}; spacing: 8px; }}"
            f"QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 9px; border: 1px solid {border}; background: {input_bg}; }}"
            f"QCheckBox::indicator:checked {{ background: {accent}; border: 1px solid {accent}; }}"
            f"QSlider::groove:horizontal {{ height: 8px; border-radius: 4px; background: {accent_soft}; }}"
            f"QSlider::handle:horizontal {{ width: 18px; margin: -5px 0; border-radius: 9px; background: {accent}; border: 2px solid white; }}"
        )
        self.frame.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 2px solid {border}; border-radius: 20px; }}")
        header_style = f"QFrame {{ background-color: {accent_soft}; border: 1px solid {border}; border-radius: 16px; }}"
        subtle_card_style = f"QFrame {{ background-color: {card_bg}; border: 1px solid {border}; border-radius: 16px; }}"
        primary_card_style = f"QFrame {{ background-color: {card_bg}; border: 1.5px solid {accent}; border-radius: 16px; }}"
        self.header_panel.setStyleSheet(header_style)
        self.card_translate.setStyleSheet(primary_card_style)
        self.card_ocr.setStyleSheet(subtle_card_style)
        self.card_appearance.setStyleSheet(subtle_card_style)
        self.advanced_translate_frame.setStyleSheet(f"QFrame {{ background-color: {accent_soft}; border: 1px solid {border}; border-radius: 12px; }}")
        self.lbl_title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {text}; background: transparent; border: none;")
        self.lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {subtext}; background: transparent; border: none;")
        self.lbl_autosave.setStyleSheet(f"color: {accent}; font-weight: 600; background-color: {accent_soft}; border: 1px solid {border}; border-radius: 999px; padding: 4px 10px;")
        self.lbl_sync_state.setStyleSheet(f"color: {text}; background-color: {card_bg}; border: 1px solid {border}; border-radius: 999px; padding: 4px 10px;")
        self.lbl_appearance.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {text};")
        self.lbl_ocr.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {text};")
        self.lbl_translate.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {text};")
        self.lbl_advanced_translate.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {accent};")
        self.lbl_advanced_hint.setStyleSheet(f"color: {subtext};")
        self.lbl_ocr_hint.setStyleSheet(f"color: {subtext};")
        self.lbl_translate_hint.setStyleSheet(f"color: {subtext};")
        self.lbl_translate_summary.setStyleSheet(f"color: {accent}; font-weight: 600; background-color: {accent_soft}; border: 1px solid {border}; border-radius: 999px; padding: 4px 10px;")
        self.lbl_threshold.setStyleSheet(f"color: {accent}; font-weight: bold; background-color: {accent_soft}; border: 1px solid {border}; border-radius: 10px; padding: 6px;")
        self.btn_close.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {subtext}; border: none; font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {accent_soft}; color: {text}; border-radius: 14px; }}"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.old_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        super().mouseReleaseEvent(event)

# ==========================================
# 設定與同步
# ==========================================
class Controller(QWidget):

    request_scan = Signal()

    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.selection_overlay = SelectionOverlay()
        self.selection_overlay.selection_made.connect(self.on_region_selected)
        self.region_frame = RegionSelectionFrame()
        self.region_frame.region_changed.connect(self.on_region_frame_changed)
        self.settings_window = None
        self.is_dark_mode = False
        self.current_auto_interval = 0 
        self.countdown_seconds = 0
        self.was_minimized = False
        self.scan_mode = SCAN_MODE_FULLSCREEN
        self.selected_region = None
        self.settings_data = {}
        self.cooldown_total_ms = 5000
        self.cooldown_end_time = 0.0
        
        self.setWindowTitle("雲朵翻譯姬")
        self.resize(320, 180) 
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.set_cloud_icon()

        self.setup_ui()
        self.setup_worker()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_settings)
        self.load_settings()
        
        self.hotkey_filter = GlobalHotKeyFilter(self.on_hotkey_pressed)
        QApplication.instance().installNativeEventFilter(self.hotkey_filter)
        QTimer.singleShot(500, self.enable_hotkey)

        self.old_pos = None

    def set_cloud_icon(self):
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        font = QFont("Segoe UI Emoji", int(size * 0.7))
        font.setStyleStrategy(QFont.PreferAntialias)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF")) 
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "☁️")
        painter.end()
        self.setWindowIcon(QIcon(pixmap))

    def setup_ui(self):
        self.frame = QFrame()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.frame)
        inner_layout = QVBoxLayout(self.frame)
        inner_layout.setContentsMargins(10, 10, 10, 10)
        inner_layout.setSpacing(6)
        
        title_bar = QHBoxLayout()
        self.lbl_title = QLabel("☁️雲朵翻譯姬 v2.3")
        self.lbl_title.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        
        self.btn_min = QPushButton("－")
        self.btn_min.setFixedSize(24,24)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_min.setStyleSheet("background:transparent; color:#888; border:none; font-weight:900;")
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(24,24)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.close_app)
        self.btn_close.setStyleSheet("background:transparent; color:#888; border:none; font-weight:900;")
        
        title_bar.addWidget(self.lbl_title)
        title_bar.addStretch()
        title_bar.addWidget(self.btn_min) 
        title_bar.addWidget(self.btn_close)
        inner_layout.addLayout(title_bar)

        self.threshold_row_widget = QWidget()
        slider_layout = QHBoxLayout(self.threshold_row_widget)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_thresh = QLabel("閥值: 100")
        self.lbl_thresh.setStyleSheet("font-size: 10px; color: #666;")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 240) 
        self.slider.setValue(100)     
        self.slider.valueChanged.connect(self.update_threshold)
        self.lbl_thresh_dark = QLabel("🌑")
        self.lbl_thresh_light = QLabel("🌕")
        slider_layout.addWidget(self.lbl_thresh_dark)
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.lbl_thresh_light)
        slider_layout.addWidget(self.lbl_thresh)
        inner_layout.addWidget(self.threshold_row_widget)
        self.threshold_row_widget.hide()

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("準備就緒 (｀・ω・´)")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setFixedHeight(30)
        self.charge_bar = StatusChargeBar()
        self.btn_theme = QPushButton("💡")
        self.btn_theme.setFixedSize(30, 30)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_settings_window)
        status_row.addWidget(self.lbl_status)
        status_row.addWidget(self.btn_theme)
        inner_layout.addLayout(status_row)
        inner_layout.addWidget(self.charge_bar)

        ai_key_row = QHBoxLayout()
        self.input_api_key = QLineEdit()
        self.input_api_key.setPlaceholderText("Google API KEY")
        self.input_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.input_api_key.textChanged.connect(self.on_api_key_changed)
        ai_key_row.addWidget(self.input_api_key)
        inner_layout.addLayout(ai_key_row)
        self.input_api_key.hide()

        ai_mode_row = QHBoxLayout()
        self.cmb_ai_model = QComboBox()
        for label, model_name in SUPPORTED_AI_MODELS:
            self.cmb_ai_model.addItem(label, model_name)
        self.cmb_ai_model.currentIndexChanged.connect(self.on_ai_model_changed)
        self.btn_ai_mode = QPushButton("準確AI翻譯")
        self.btn_ai_mode.setCheckable(True)
        self.btn_ai_mode.setCursor(Qt.PointingHandCursor)
        self.btn_ai_mode.clicked.connect(self.toggle_ai_translation)
        ai_mode_row.addWidget(self.cmb_ai_model)
        ai_mode_row.addWidget(self.btn_ai_mode)
        inner_layout.addLayout(ai_mode_row)
        self.cmb_ai_model.hide()
        self.btn_ai_mode.hide()

        scan_mode_row = QHBoxLayout()
        self.scan_mode_group = QButtonGroup(self)
        self.scan_mode_group.setExclusive(True)
        self.btn_mode_full = QPushButton("全螢幕翻譯")
        self.btn_mode_full.setCheckable(True)
        self.btn_mode_full.setChecked(True)
        self.btn_mode_full.clicked.connect(lambda: self.set_scan_mode(SCAN_MODE_FULLSCREEN))
        self.scan_mode_group.addButton(self.btn_mode_full)
        self.btn_mode_region = QPushButton("框選翻譯")
        self.btn_mode_region.setCheckable(True)
        self.btn_mode_region.clicked.connect(lambda: self.set_scan_mode(SCAN_MODE_REGION))
        self.scan_mode_group.addButton(self.btn_mode_region)
        scan_mode_row.addWidget(self.btn_mode_full)
        scan_mode_row.addWidget(self.btn_mode_region)
        inner_layout.addLayout(scan_mode_row)

        region_row = QHBoxLayout()
        self.btn_pick_region = QPushButton("設定框選區域")
        self.btn_pick_region.setCursor(Qt.PointingHandCursor)
        self.btn_pick_region.clicked.connect(self.begin_region_selection)
        self.lbl_region = QLabel("目前: 全螢幕")
        region_row.addWidget(self.btn_pick_region)
        region_row.addWidget(self.lbl_region)
        inner_layout.addLayout(region_row)

        btn_layout = QHBoxLayout()
        self.btn_now = CooldownButton("⚡ 立即 (~)")
        self.btn_now.setCursor(Qt.PointingHandCursor)
        self.btn_now.clicked.connect(self.on_immediate_click)
        self.auto_group = QButtonGroup(self)
        self.auto_group.setExclusive(True)
        self.btn_30 = QPushButton("🎲 10s~")
        self.btn_30.setCheckable(True)
        self.btn_30.setCursor(Qt.PointingHandCursor)
        self.btn_30.clicked.connect(lambda: self.start_auto_scan(10000))
        self.auto_group.addButton(self.btn_30)
        self.btn_60 = QPushButton("⭐ 30s~")
        self.btn_60.setCheckable(True)
        self.btn_60.setCursor(Qt.PointingHandCursor)
        self.btn_60.clicked.connect(lambda: self.start_auto_scan(30000))
        self.auto_group.addButton(self.btn_60)
        btn_layout.addWidget(self.btn_now)
        btn_layout.addWidget(self.btn_30)
        btn_layout.addWidget(self.btn_60)
        inner_layout.addLayout(btn_layout)

        stop_layout = QHBoxLayout()
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_scan)
        stop_layout.addWidget(self.btn_stop)
        inner_layout.addLayout(stop_layout)

        self.update_frame_style()

    def setup_worker(self):
        self.ocr_thread = QThread()
        self.worker = OCRWorker()
        self.worker.set_scan_mode(self.scan_mode)
        self.worker.moveToThread(self.ocr_thread)
        self.request_scan.connect(self.worker.run_scan_once)
        self.worker.finished.connect(self.on_scan_complete)
        self.worker.status_msg.connect(self.update_status)
        self.worker.hide_ui.connect(self.hide_ui_for_scan)
        self.worker.show_ui.connect(self.show_ui_after_scan)
        self.worker.threshold_suggested.connect(self.apply_auto_threshold)
        self.ocr_thread.start()
        
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self.trigger_scan_sequence)
        
        self.display_timer = QTimer(self)
        self.display_timer.setInterval(1000)
        self.display_timer.timeout.connect(self.update_countdown_label)
        
        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self.reset_immediate_btn)
        self.cooldown_progress_timer = QTimer(self)
        self.cooldown_progress_timer.setInterval(80)
        self.cooldown_progress_timer.timeout.connect(self.update_cooldown_progress)
        self.gemma_rate_timer = QTimer(self)
        self.gemma_rate_timer.setInterval(1000)
        self.gemma_rate_timer.timeout.connect(self.update_gemma_rate_indicator)
        self.gemma_rate_timer.start()

    def enable_hotkey(self):
        self.hotkey_filter.register_hotkey(self.winId())

    def schedule_save_settings(self):
        if hasattr(self, "save_timer"):
            self.save_timer.start(250)

    def get_settings_payload(self):
        return {
            "google_api_key": self.worker.google_api_key,
            "gemma_model": self.worker.gemma_model,
            "use_gemma_translation": self.worker.use_gemma_translation,
            "scan_mode": self.scan_mode,
            "selected_region": list(self.selected_region) if self.selected_region else None,
            "is_dark_mode": self.is_dark_mode,
            "binary_threshold": int(self.worker.binary_threshold),
            "auto_threshold_enabled": bool(self.worker.auto_threshold_enabled),
        }

    def save_settings(self):
        try:
            payload = self.get_settings_payload()
            with open(SETTINGS_FILE, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_settings(self):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as fp:
                self.settings_data = json.load(fp)
        except Exception:
            self.settings_data = {}

        settings = self.settings_data if isinstance(self.settings_data, dict) else {}

        threshold = int(settings.get("binary_threshold", self.slider.value()))
        threshold = max(50, min(240, threshold))
        self.slider.blockSignals(True)
        self.slider.setValue(threshold)
        self.slider.blockSignals(False)
        self.update_threshold(threshold)

        auto_threshold_enabled = bool(settings.get("auto_threshold_enabled", True))
        self.worker.set_auto_threshold_enabled(auto_threshold_enabled)

        api_key = str(settings.get("google_api_key", "") or "")
        if api_key:
            self.on_api_key_changed(api_key)

        model_name = str(settings.get("gemma_model", DEFAULT_GEMMA_MODEL) or DEFAULT_GEMMA_MODEL)
        model_index = self.cmb_ai_model.findData(model_name)
        if model_index < 0:
            model_index = 0
        self.cmb_ai_model.blockSignals(True)
        self.cmb_ai_model.setCurrentIndex(model_index)
        self.cmb_ai_model.blockSignals(False)
        self.on_ai_model_changed(model_index)

        self.set_theme_mode(bool(settings.get("is_dark_mode", False)))

        saved_region = settings.get("selected_region")
        if isinstance(saved_region, list) and len(saved_region) == 4:
            try:
                self.selected_region = tuple(int(v) for v in saved_region)
                self.worker.set_scan_region(self.selected_region)
            except Exception:
                self.selected_region = None

        saved_scan_mode = settings.get("scan_mode", SCAN_MODE_FULLSCREEN)
        if saved_scan_mode == SCAN_MODE_REGION and self.selected_region:
            self.btn_mode_region.setChecked(True)
            self.set_scan_mode(SCAN_MODE_REGION)
        else:
            self.btn_mode_full.setChecked(True)
            self.set_scan_mode(SCAN_MODE_FULLSCREEN)

        use_gemma_translation = bool(settings.get("use_gemma_translation", False))
        self.btn_ai_mode.setChecked(use_gemma_translation)
        self.toggle_ai_translation(use_gemma_translation)

    def update_threshold(self, val):
        self.lbl_thresh.setText(f"閥值: {val}")
        self.worker.binary_threshold = val

        if self.settings_window is not None:
            self.settings_window.lbl_threshold.setText(str(val))
        self.schedule_save_settings()

    def apply_auto_threshold(self, val):
        self.slider.blockSignals(True)
        self.slider.setValue(val)
        self.slider.blockSignals(False)
        self.lbl_thresh.setText(f"閥值: {val}")
        self.worker.binary_threshold = val
        if self.settings_window is not None:
            self.settings_window.slider_threshold.blockSignals(True)
            self.settings_window.slider_threshold.setValue(val)
            self.settings_window.slider_threshold.blockSignals(False)
            self.settings_window.lbl_threshold.setText(str(val))

    def set_auto_threshold_mode(self, enabled):
        self.worker.set_auto_threshold_enabled(enabled)
        if self.settings_window is not None and self.settings_window.chk_auto_threshold.isChecked() != enabled:
            self.settings_window.chk_auto_threshold.blockSignals(True)
            self.settings_window.chk_auto_threshold.setChecked(enabled)
            self.settings_window.chk_auto_threshold.blockSignals(False)
        self.schedule_save_settings()

    def on_api_key_changed(self, text):
        self.worker.set_google_api_key(text)
        if self.input_api_key.text() != text:
            self.input_api_key.blockSignals(True)
            self.input_api_key.setText(text)
            self.input_api_key.blockSignals(False)
        if self.btn_ai_mode.isChecked() and not text.strip():
            self.btn_ai_mode.setChecked(False)
            self.worker.set_gemma_enabled(False)
            if self.settings_window is not None:
                self.settings_window.cmb_translate_mode.blockSignals(True)
                self.settings_window.cmb_translate_mode.setCurrentIndex(0)
                self.settings_window.cmb_translate_mode.blockSignals(False)
        if self.settings_window is not None and self.settings_window.input_api_key.text() != text:
            self.settings_window.input_api_key.blockSignals(True)
            self.settings_window.input_api_key.setText(text)
            self.settings_window.input_api_key.blockSignals(False)
        self.schedule_save_settings()

    def on_ai_model_changed(self, index):
        model_name = self.cmb_ai_model.itemData(index)
        self.worker.set_gemma_model(model_name)
        if self.settings_window is not None and self.settings_window.cmb_ai_model.currentIndex() != index:
            self.settings_window.cmb_ai_model.blockSignals(True)
            self.settings_window.cmb_ai_model.setCurrentIndex(index)
            self.settings_window.cmb_ai_model.blockSignals(False)
        self.schedule_save_settings()

    def toggle_ai_translation(self, checked):
        has_key = bool(self.worker.google_api_key.strip())
        if checked and not has_key:
            self.lbl_status.setText("請先輸入 Google API KEY")
            self.btn_ai_mode.setChecked(False)
            self.worker.set_gemma_enabled(False)
            if self.settings_window is not None:
                self.settings_window.cmb_translate_mode.blockSignals(True)
                self.settings_window.cmb_translate_mode.setCurrentIndex(0)
                self.settings_window.cmb_translate_mode.blockSignals(False)
            self.schedule_save_settings()
            return
        self.worker.set_gemma_enabled(checked)
        if self.settings_window is not None:
            self.settings_window.cmb_translate_mode.blockSignals(True)
            self.settings_window.cmb_translate_mode.setCurrentIndex(1 if checked else 0)
            self.settings_window.cmb_translate_mode.blockSignals(False)
        if checked:
            self.lbl_status.setText(f"AI模型: {self.cmb_ai_model.currentText()}")
        self.schedule_save_settings()

    def set_scan_mode(self, scan_mode):
        self.scan_mode = scan_mode
        self.worker.set_scan_mode(scan_mode)
        if scan_mode == SCAN_MODE_FULLSCREEN:
            self.lbl_region.setText("目前: 全螢幕")
            self.region_frame.clear_region()
        elif self.selected_region:
            x, y, w, h = self.selected_region
            self.lbl_region.setText(f"區域: {w}x{h} @ {x},{y}")
            self.region_frame.set_theme_mode(self.is_dark_mode)
            self.region_frame.show_region(self.selected_region)
        else:
            self.lbl_region.setText("區域: 尚未設定")
            self.region_frame.clear_region()
        self.schedule_save_settings()

    def begin_region_selection(self):
        self.stop_scan()
        self.hide()
        self.overlay.hide()
        self.region_frame.hide()
        self.selection_overlay.begin_selection()

    def on_region_selected(self, rect):
        self.show()
        self.raise_()
        self.activateWindow()
        if not rect:
            self.lbl_status.setText("已取消框選")
            self.set_scan_mode(self.scan_mode)
            return
        self.selected_region = rect
        self.worker.set_scan_region(rect)
        self.btn_mode_region.setChecked(True)
        self.set_scan_mode(SCAN_MODE_REGION)
        x, y, w, h = rect
        self.lbl_status.setText(f"已設定框選區域 {w}x{h}")
        self.schedule_save_settings()

    def on_region_frame_changed(self, rect):
        if not rect:
            return
        self.selected_region = rect
        self.worker.set_scan_region(rect)
        if self.scan_mode == SCAN_MODE_REGION:
            x, y, w, h = rect
            self.lbl_region.setText(f"區域: {w}x{h} @ {x},{y}")
        self.schedule_save_settings()

    def toggle_settings_window(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
        self.settings_window.sync_from_controller()
        self.settings_window.update_theme(self.is_dark_mode)
        if self.settings_window.isVisible():
            self.settings_window.hide()
        else:
            self.settings_window.show()
            self.settings_window.raise_()
            self.settings_window.activateWindow()

    def on_hotkey_pressed(self):
        QTimer.singleShot(0, self.on_immediate_click)

    def on_immediate_click(self):
        if self.cooldown_timer.isActive():
            print("❄️ 冷卻中...請稍後")
            return
        if self.scan_mode == SCAN_MODE_REGION and not self.selected_region:
            self.lbl_status.setText("請先設定框選區域")
            self.begin_region_selection()
            return
        self.display_timer.stop()
        self.lbl_status.setText("⚡ 立即掃描中...")
        self.trigger_scan_sequence()
        self.btn_now.setEnabled(False)
        self.btn_now.setText("⚡ 充電中 0%")
        self.btn_now.set_cooldown_progress(0)
        self.cooldown_end_time = time.monotonic() + (self.cooldown_total_ms / 1000.0)
        self.cooldown_progress_timer.start()
        self.cooldown_timer.start(self.cooldown_total_ms)

    def reset_immediate_btn(self):
        self.cooldown_progress_timer.stop()
        self.btn_now.set_cooldown_progress(0)
        self.cooldown_end_time = 0.0
        self.btn_now.setEnabled(True)
        self.btn_now.setText("⚡ 立即 (~)")

    def update_cooldown_progress(self):
        if self.cooldown_end_time <= 0:
            self.cooldown_progress_timer.stop()
            return
        remaining = max(0.0, self.cooldown_end_time - time.monotonic())
        progress = int(round((1.0 - (remaining / (self.cooldown_total_ms / 1000.0))) * 100))
        progress = max(0, min(100, progress))
        self.btn_now.set_cooldown_progress(progress)
        self.btn_now.setText(f"⚡ 充電中 {progress}%")

    def start_auto_scan(self, base_interval):
        if self.scan_mode == SCAN_MODE_REGION and not self.selected_region:
            self.lbl_status.setText("請先設定框選區域")
            self.begin_region_selection()
            return
        self.current_auto_interval = base_interval
        self.schedule_next_scan()

    def schedule_next_scan(self):
        if self.current_auto_interval == 0:
            return
        if self.current_auto_interval == 5000:
            delay = 5000
        elif self.current_auto_interval == 10000:
            delay = random.randint(8000, 14000)
        elif self.current_auto_interval == 30000:
            delay = random.randint(25000, 40000)
        else:
            delay = random.randint(50000, 80000)
        self.auto_timer.start(delay)
        self.countdown_seconds = delay // 1000
        self.update_countdown_label()
        self.display_timer.start()

    def update_countdown_label(self):
        if self.current_auto_interval == 0: 
            self.display_timer.stop()
            return
        if self.current_auto_interval == 5000:
            prefix = "⚡ 冷卻"
        elif self.current_auto_interval == 10000:
            prefix = "🎲 10s~"
        elif self.current_auto_interval == 30000:
            prefix = "⭐ 30s~"
        else:
            prefix = "⏳ 隨機"
        self.lbl_status.setText(f"{prefix}倒數: {self.countdown_seconds}s")
        self.countdown_seconds -= 1
        if self.countdown_seconds < 0:
            self.display_timer.stop()

    def on_scan_complete(self, results):
        self.overlay.update_bubbles(results)
        if self.current_auto_interval > 0:
            self.schedule_next_scan()

    def stop_scan(self):
        self.current_auto_interval = 0
        self.auto_timer.stop()
        self.display_timer.stop()
        self.auto_group.setExclusive(False)
        self.btn_30.setChecked(False)
        self.btn_60.setChecked(False)
        self.auto_group.setExclusive(True)
        self.lbl_status.setText("⏸ 自動已停止")
        self.overlay.clear_all()

    def trigger_scan_sequence(self):
        self.display_timer.stop()
        self.overlay.setVisible(False)
        QTimer.singleShot(50, self._emit_scan_signal)

    def _emit_scan_signal(self):
        self.request_scan.emit()

    def update_status(self, msg):
        if self.display_timer.isActive() and "完成" not in msg:
            return
        self.lbl_status.setText(msg)
        self.update_gemma_rate_indicator()

    def update_gemma_rate_indicator(self):
        if not hasattr(self, "charge_bar") or not hasattr(self, "worker"):
            return
        self.worker.prune_gemma_call_timestamps()
        if self.worker.has_multimodal_ai():
            used = len(self.worker.gemma_call_timestamps)
            progress = int(round((used / GEMMA_RATE_LIMIT_MAX_CALLS) * 100))
            progress = max(0, min(100, progress))
            if used >= GEMMA_RATE_LIMIT_MAX_CALLS:
                self.charge_bar.set_theme_colors("#FDE8E8", "#E57373", "#E53935", "#8B1E1E")
                self.charge_bar.set_progress(100, f"Gemma {used}/15")
                self.lbl_status.setText("Gemma 已滿 15/15，先改用 Google")
                return
            if used >= 10:
                self.charge_bar.set_theme_colors("#FFF4D6", "#E6B800", "#F4C542", "#7A5A00")
            else:
                self.charge_bar.set_theme_colors("#E8F8FB", "#7FC8E8", "#4FC3F7", "#3A5C72")
            self.charge_bar.set_progress(progress, f"Gemma {used}/15")
        else:
            self.charge_bar.set_theme_colors("#F2F5F7", "#D7E0E8", "#B7C7D8", "#6B7C8A")
            self.charge_bar.set_progress(0, "Google")

    def hide_ui_for_scan(self):
        self.overlay.setVisible(False)
        if self.isMinimized():
            self.was_minimized = True
        else:
            self.was_minimized = False
            self.setVisible(False) 

    def show_ui_after_scan(self):
        self.overlay.setVisible(True)
        if not self.was_minimized:
            self.setVisible(True)
            self.showNormal() 

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.update_frame_style()
        self.overlay.set_theme_mode(self.is_dark_mode)

    def set_theme_mode(self, is_dark):
        self.is_dark_mode = bool(is_dark)
        self.update_frame_style()
        self.overlay.set_theme_mode(self.is_dark_mode)
        self.region_frame.set_theme_mode(self.is_dark_mode)
        if self.settings_window is not None:
            self.settings_window.update_theme(self.is_dark_mode)
        self.schedule_save_settings()

    def update_frame_style(self):
        if self.is_dark_mode:
            bg, border, text, btn_bg = "rgba(45,45,45,240)", "#555", "#E0E0E0", "#424242"
            status_bg, status_bd = "#3A3A3A", "#555"
            btn_fg, btn_hover, btn_chk = "#E0E0E0", "#505050", "#00ACC1"
            bulb_bg, bulb_fg = "transparent", "#FFEB3B"
        else:
            bg, border, text, btn_bg = "rgba(240,248,255,230)", "#87CEEB", "#444", "#E0F7FA"
            status_bg, status_bd = "white", "#87CEEB"
            btn_fg, btn_hover, btn_chk = "#444", "#B2EBF2", "#4FC3F7"
            bulb_bg, bulb_fg = "transparent", "#555"

        self.frame.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 15px; border: 2px solid {border}; }}")
        self.lbl_title.setStyleSheet(f"color: {text}; font-weight: bold; background: transparent; border: none;")
        self.lbl_status.setStyleSheet(f"color: {text}; background-color: {status_bg}; border: 1px solid {status_bd}; border-radius: 4px;")
        self.lbl_thresh.setStyleSheet(f"color: {text}; font-size: 10px;")
        self.lbl_region.setStyleSheet(f"color: {text}; font-size: 10px;")
        self.input_api_key.setStyleSheet(f"background-color: {status_bg}; color: {text}; border: 1px solid {status_bd}; border-radius: 6px; padding: 6px;")
        self.cmb_ai_model.setStyleSheet(f"background-color: {btn_bg}; color: {text}; border: 1px solid {border}; border-radius: 6px; padding: 4px;")

        self.btn_now.set_theme_colors(
            btn_bg,
            btn_fg,
            border,
            btn_hover,
            btn_chk,
            "#888888",
            "#CCCCCC",
        )

        auto_btn_style = f"""
            QPushButton {{ background-color: {btn_bg}; color: {btn_fg}; border-radius: 8px; padding: 8px; font-weight: bold; border: none; }}
            QPushButton:hover:!checked {{ background-color: {btn_hover}; }}
            QPushButton:checked {{ background-color: {btn_chk}; color: white; }}
        """
        self.btn_30.setStyleSheet(auto_btn_style)
        self.btn_60.setStyleSheet(auto_btn_style)
        self.btn_ai_mode.setStyleSheet(auto_btn_style)
        self.btn_mode_full.setStyleSheet(auto_btn_style)
        self.btn_mode_region.setStyleSheet(auto_btn_style)
        self.btn_pick_region.setStyleSheet(auto_btn_style)
        
        self.btn_stop.setStyleSheet("QPushButton {{ background-color: #D32F2F; color: white; border-radius: 10px; padding: 5px; border: none; }} QPushButton:hover {{ background-color: #E57373; }}")
        self.btn_theme.setText("⚙")
        self.btn_theme.setStyleSheet(f"QPushButton {{ background-color: {bulb_bg}; color: {bulb_fg}; border: none; font-size: 18px; }} QPushButton:hover {{ background-color: rgba(128,128,128,0.2); border-radius: 15px; }}")
        if self.settings_window is not None:
            self.settings_window.update_theme(self.is_dark_mode)
            self.settings_window.sync_from_controller()
        self.region_frame.set_theme_mode(self.is_dark_mode)

    def close_app(self):
        self.save_settings()
        if hasattr(self, 'hotkey_filter'):
            self.hotkey_filter.unregister_hotkey(self.winId())
        self.auto_timer.stop()
        self.display_timer.stop()
        self.cooldown_timer.stop()
        self.cooldown_progress_timer.stop()
        self.ocr_thread.quit()
        self.ocr_thread.wait()
        if self.settings_window is not None:
            self.settings_window.close()
        self.region_frame.close()
        self.selection_overlay.close()
        self.overlay.close()
        self.close()
        QApplication.instance().quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x()+delta.x(), self.y()+delta.y())
            self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self.old_pos = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    overlay = OverlayWindow()
    overlay.show()
    ctrl = Controller(overlay)
    ctrl.show()
    sys.exit(app.exec())
