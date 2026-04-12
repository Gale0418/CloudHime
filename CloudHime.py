# ==========================================
# 🌟 雲朵翻譯姬 v3.0 - 螢幕 OCR 即時翻譯工具 (邏輯修正版) (｀・ω・´)ゞ
# ==========================================
# 核心引擎: Windows Media OCR (WinRT)
# 翻譯引擎: Google + Gemma (多模態支援)
# 架構優化: 移除多餘引用，清理過期的 Argos 備援邏輯
# ==========================================

import os
import sys
import asyncio
import base64
import ctypes
import ctypes.wintypes
import random
import re
import json
import time
import traceback
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
    print("⚠️ 未安裝 opencc。")

from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                               QPushButton, QFrame, QHBoxLayout, QButtonGroup,
                               QSlider, QLineEdit, QCheckBox, QComboBox,
                               QSpinBox, QSizePolicy, QSplitter, QScrollArea,
                               QGraphicsOpacityEffect,
                               QGridLayout)
from PySide6.QtCore import (Qt, QTimer, Signal, QThread, QObject, 
                            QAbstractNativeEventFilter, QEvent)
from PySide6.QtGui import QCursor, QFontMetrics, QIcon, QPixmap, QColor, QPainter, QFont, QBrush
from PySide6.QtCore import QRect, QPoint
from PySide6.QtGui import QPen

from themes import (
    ThemeRegistry,
    build_bubble_style,
    build_charge_bar_colors,
    build_controller_styles,
    build_selection_colors,
    build_settings_styles,
    resolve_theme,
)
# 防止高 DPI 縮放導致座標錯位
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

TRANSLATION_CACHE_LIMIT = 512
HUD_MEMORY_LIMIT = 160
HUD_OBSERVATION_LIMIT = 6
PREFERRED_TEXT_MEMORY_LIMIT = 256
API_KEY_ENV_VAR = "CLOUDHIME_GOOGLE_API_KEY"
AUTO_THRESHOLD_MIN = 50
AUTO_THRESHOLD_MAX = 250
AUTO_THRESHOLD_CANDIDATES = (50, 70, 90, 110, 130, 150, 170, 190, 220, 250)
AUTO_THRESHOLD_LOCAL_OFFSETS = (-10, 0, 10)
MAX_OCR_SCALE_FACTOR = 3.0
MIN_OCR_SCALE_FACTOR = 1.0
AI_IMAGE_MAX_WIDTH = 1536
AI_TOP_CONTEXT_RATIO = 0.22
NOISE_ONLY_PATTERN = re.compile(r'^[-_=.,|/\\:;~^]+$')
HAS_CJK_PATTERN = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
GOOGLE_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMMA_MODEL = "gemma-3-27b-it"
LEGACY_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "cloudhime_settings.json")
def get_user_settings_file():
    appdata_root = os.getenv("APPDATA") or os.path.expanduser("~")
    settings_dir = os.path.join(appdata_root, "CloudHime")
    try:
        os.makedirs(settings_dir, exist_ok=True)
    except Exception:
        pass
    return os.path.join(settings_dir, "cloudhime_settings.json")

SETTINGS_FILE = get_user_settings_file()
MIN_BUBBLE_FONT_PT = 8
MIN_BUBBLE_WIDTH = 96
MIN_BUBBLE_HEIGHT = 42
SUPPORTED_AI_MODELS = [
    ("Gemma 3 27B", "gemma-3-27b-it"),
    ("Gemma 4 31B", "gemma-4-31b-it"),
]
SUPPORTED_GEMMA_MODEL_NAMES = [model_name for _, model_name in SUPPORTED_AI_MODELS]
SCAN_MODE_FULLSCREEN = "fullscreen"
SCAN_MODE_REGION = "region"
REGION_RENDER_BUBBLE = "bubble"
REGION_RENDER_RELIEF = "relief"
RELIEF_SIDE_AUTO = "auto"
RELIEF_SIDE_TOP = "top"
RELIEF_SIDE_BOTTOM = "bottom"
RELIEF_SIDE_LEFT = "left"
RELIEF_SIDE_RIGHT = "right"
RELIEF_SIDE_OPTIONS = [
    ("自動", RELIEF_SIDE_AUTO),
    ("上方", RELIEF_SIDE_TOP),
    ("下方", RELIEF_SIDE_BOTTOM),
    ("左側", RELIEF_SIDE_LEFT),
    ("右側", RELIEF_SIDE_RIGHT),
]
GOOGLE_BATCH_SIZE = 12
SMART_FULLSCREEN_MAX_REGIONS = 3
SMART_FULLSCREEN_MIN_AREA_RATIO = 0.015
SMART_FULLSCREEN_MAX_AREA_RATIO = 0.82
AUTO_THRESHOLD_REFRESH_INTERVAL_MS = 60 * 1000
GEMMA_RATE_LIMIT_WINDOW_SEC = 60
GEMMA_RATE_LIMIT_MAX_CALLS = 15
RELIEF_BUBBLE_OPACITY = 40
RELIEF_MAX_GAP_PX = 500

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
    gemma_model_changed = Signal(str, str)

    def __init__(self):
        super().__init__()
        print("[OCR] Initializing OCR engine...")
        self.engine = None
        self.translators = {}
        self.last_combined_text = ""
        self.last_results = []
        self.last_provider = ""
        self.translation_cache = OrderedDict()
        self.hud_memory = OrderedDict()
        self.preferred_text_memory = OrderedDict()
        self.gemma_call_timestamps = {model_name: [] for model_name in SUPPORTED_GEMMA_MODEL_NAMES}
        self.google_api_key = ""
        self.gemma_model = DEFAULT_GEMMA_MODEL
        self.use_gemma_translation = False
        self.gemma_auto_switch_enabled = False
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

    def set_gemma_auto_switch_enabled(self, enabled):
        self.gemma_auto_switch_enabled = bool(enabled)

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

    def normalize_gemma_model(self, model_name):
        model_name = (model_name or "").strip()
        return model_name if model_name in SUPPORTED_GEMMA_MODEL_NAMES else DEFAULT_GEMMA_MODEL

    def get_gemma_model_call_limit(self, model_name):
        return GEMMA_RATE_LIMIT_MAX_CALLS

    def prune_gemma_call_timestamps(self, model_name=None):
        cutoff = time.monotonic() - GEMMA_RATE_LIMIT_WINDOW_SEC
        if model_name is None:
            for name in SUPPORTED_GEMMA_MODEL_NAMES:
                self.gemma_call_timestamps[name] = [ts for ts in self.gemma_call_timestamps.get(name, []) if ts >= cutoff]
            return
        model_name = self.normalize_gemma_model(model_name)
        self.gemma_call_timestamps[model_name] = [ts for ts in self.gemma_call_timestamps.get(model_name, []) if ts >= cutoff]

    def can_call_gemma(self, model_name=None):
        if not self.has_multimodal_ai():
            return False
        model_name = self.normalize_gemma_model(model_name or self.gemma_model)
        self.prune_gemma_call_timestamps(model_name)
        return len(self.gemma_call_timestamps.get(model_name, [])) < self.get_gemma_model_call_limit(model_name)

    def record_gemma_call(self, model_name=None):
        model_name = self.normalize_gemma_model(model_name or self.gemma_model)
        self.prune_gemma_call_timestamps(model_name)
        self.gemma_call_timestamps.setdefault(model_name, []).append(time.monotonic())

    def get_other_gemma_model(self, model_name=None):
        model_name = self.normalize_gemma_model(model_name or self.gemma_model)
        for candidate in SUPPORTED_GEMMA_MODEL_NAMES:
            if candidate != model_name:
                return candidate
        return model_name

    def resolve_gemma_model_for_call(self, preferred_model=None):
        preferred_model = self.normalize_gemma_model(preferred_model or self.gemma_model)
        if not self.has_multimodal_ai():
            return preferred_model
        if self.can_call_gemma(preferred_model):
            if preferred_model != self.gemma_model:
                old_model = self.gemma_model
                self.gemma_model = preferred_model
                self.gemma_model_changed.emit(old_model, preferred_model)
            return preferred_model
        if self.gemma_auto_switch_enabled:
            for candidate in SUPPORTED_GEMMA_MODEL_NAMES:
                if candidate == preferred_model:
                    continue
                if self.can_call_gemma(candidate):
                    old_model = self.gemma_model
                    self.gemma_model = candidate
                    self.gemma_model_changed.emit(old_model, candidate)
                    return candidate
        return preferred_model

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
        model_name = self.resolve_gemma_model_for_call(self.gemma_model)
        if not self.can_call_gemma(model_name):
            raise ValueError("gemma_rate_limited")

        cache_key = ("gemma", model_name, normalized_text)
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
            GOOGLE_API_ENDPOINT.format(model=model_name),
            data=json.dumps(req_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.google_api_key,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.record_gemma_call(model_name)

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
        model_name = self.resolve_gemma_model_for_call(self.gemma_model)
        if not self.can_call_gemma(model_name):
            raise ValueError("gemma_rate_limited")

        normalized_texts = tuple(normalize_ocr_text(text) for text in source_texts)
        cache_key = ("gemma-mm", model_name, normalized_texts)
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
            GOOGLE_API_ENDPOINT.format(model=model_name),
            data=json.dumps(req_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.google_api_key,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.record_gemma_call(model_name)

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
        batch_result, _ = self.translate_text_batch_with_provider(source_texts)
        return batch_result

    def translate_text_batch_with_provider(self, source_texts):
        normalized_texts = [normalize_ocr_text(text) for text in source_texts]
        if not normalized_texts or any(not text for text in normalized_texts):
            return [], ""
        if self.use_gemma_translation and self.google_api_key:
            combined_source = "\n".join(normalized_texts)
            try:
                translated = self.translate_text_gemma(combined_source)
                batch_result = self.split_translated_lines(translated, len(normalized_texts))
                if len(batch_result) == len(normalized_texts):
                    return batch_result, self.get_current_ai_provider()
            except (error.URLError, error.HTTPError, TimeoutError, ValueError):
                pass
        batch_result = self.translate_text_google_batch(normalized_texts)
        if len(batch_result) == len(normalized_texts):
            return batch_result, "google"
        return [], ""

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
        for start in range(0, len(source_texts), batch_size):
            batch = source_texts[start:start + batch_size]
            batch_result = []
            batch_provider = ""
            try:
                batch_result, batch_provider = self.translate_text_batch_with_provider(batch)
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

        def evaluate_thresholds(threshold_values, current_best_threshold, current_best_items, current_best_score):
            candidate_results = []
            regions = ocr_regions or [(0, 0, img.shape[1], img.shape[0])]
            orientations = orientation_candidates or [0]

            for threshold in threshold_values:
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
                if score > current_best_score:
                    current_best_score = score
                    current_best_threshold = threshold
                    current_best_items = filtered_items
            return candidate_results, current_best_threshold, current_best_items, current_best_score

        if candidate_thresholds:
            candidates = [int(value) for value in candidate_thresholds if value is not None]
        elif should_refresh_auto_threshold:
            candidates = list(AUTO_THRESHOLD_CANDIDATES)
        else:
            candidates = [base_threshold]
        candidates = sorted({max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, value)) for value in candidates})

        best_threshold = base_threshold
        best_items = []
        best_score = -1
        candidate_results, best_threshold, best_items, best_score = evaluate_thresholds(
            candidates,
            best_threshold,
            best_items,
            best_score,
        )

        if self.auto_threshold_enabled and should_refresh_auto_threshold:
            local_candidates = sorted({
                max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, best_threshold + offset))
                for offset in AUTO_THRESHOLD_LOCAL_OFFSETS
            })
            if len(local_candidates) > 1:
                self.status_msg.emit("🔎 局部微調閥值中...")
                local_results, best_threshold, best_items, best_score = evaluate_thresholds(
                    local_candidates,
                    best_threshold,
                    best_items,
                    best_score,
                )
                candidate_results.extend(local_results)

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
        self.status_msg.emit("🔍 自動調整清晰度中...")

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

        current_provider = self.get_current_ai_provider() if (self.use_gemma_translation and self.google_api_key) else "google"
        is_upgrade_needed = self.get_translation_provider_priority(current_provider) > self.get_translation_provider_priority(self.last_provider)

        # 🌟 邏輯修正：畫面靜止且無翻譯升級需求時才跳過
        if current_combined_text == self.last_combined_text and not is_upgrade_needed:
            self.status_msg.emit("♻️ 畫面靜止")
            self.finished.emit(self.last_results) 
            return

        self.last_combined_text = current_combined_text
        self.last_provider = current_provider
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
    def __init__(self, parent, text, x, y, w, h, is_dark_mode=False, render_mode=REGION_RENDER_BUBBLE,
                 relief_side=RELIEF_SIDE_AUTO, relief_font_pt=18, relief_opacity=40, relief_gap_px=10, region_rect=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.text_padding = 8
        self.source_rect = QRect(int(x), int(y), max(1, int(w)), max(1, int(h)))
        self.render_mode = render_mode if render_mode in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF) else REGION_RENDER_BUBBLE
        self.relief_side = relief_side if relief_side in {opt[1] for opt in RELIEF_SIDE_OPTIONS} else RELIEF_SIDE_AUTO
        self.relief_font_pt = max(MIN_BUBBLE_FONT_PT, int(relief_font_pt))
        self.relief_opacity = max(0, min(100, int(relief_opacity)))
        self.relief_gap_px = max(0, min(RELIEF_MAX_GAP_PX, int(relief_gap_px)))
        # 浮雕模式定位用的掃描框（若有，以整體掃描大框為 anchor）
        self.region_rect = QRect(int(region_rect[0]), int(region_rect[1]), max(1, int(region_rect[2])), max(1, int(region_rect[3]))) if region_rect else None
        self.setText(text)
        self.set_theme(is_dark_mode)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMargin(self.text_padding)
        self.setMouseTracking(True)
        if self.render_mode == REGION_RENDER_RELIEF:
            bubble_rect, best_size = self.compute_relief_layout(text, x, y, w, h)
        else:
            bubble_rect, best_size = self.compute_bubble_layout(text, x, y, w, h)
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setPointSizeF(best_size)
        font.setBold(True)
        self.setFont(font)
        self.setGeometry(bubble_rect)
        self.show()

    def set_theme(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.theme_mode = theme.key
        self.is_dark_mode = theme.key != "light"
        if self.render_mode == REGION_RENDER_RELIEF:
            self.setStyleSheet(theme.bubble_qss(relief=True))
            self.bubble_fill_color = theme.bubble_relief_fg
            self.bubble_outline_color = theme.bubble_relief_outline
            try:
                self.style().unpolish(self)
                self.style().polish(self)
            except Exception:
                pass
            self.update()
        else:
            self.setStyleSheet(theme.bubble_qss(relief=False))
            self.bubble_fill_color = theme.bubble_fg
            self.bubble_outline_color = theme.bubble_border
            try:
                self.style().unpolish(self)
                self.style().polish(self)
            except Exception:
                pass
        self.update()
        self.repaint()

    def fit_text_strictly(self, text, w, h, max_size=30):
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setBold(True)
        max_size = max(MIN_BUBBLE_FONT_PT, int(max_size))
        for size in range(max_size, MIN_BUBBLE_FONT_PT - 1, -1):
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

    def compute_bubble_layout(self, text, x, y, w, h, fixed_font_size=None):
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
        best_size = float(fixed_font_size) if fixed_font_size is not None else self.fit_text_strictly(text, base_w, base_h)
        best_score = (-1, -1, 0)
        source_center_x = x + w / 2
        source_center_y = y + h / 2

        for candidate_w in width_candidates:
            if fixed_font_size is None:
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
            else:
                font_size = float(fixed_font_size)
                required_h = self.measure_text_height(text, candidate_w, font_size) + self.text_padding * 2
                candidate_h = max(base_h, required_h)
                candidate_h = min(max_h, candidate_h)
                fits_fixed_font = self.measure_text_height(text, candidate_w, font_size) <= max(1, candidate_h - self.text_padding * 2)
                score = (
                    1 if fits_fixed_font else 0,
                    -abs(candidate_w - base_w),
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

    def compute_relief_layout(self, text, x, y, w, h):
        parent_rect = self.parent().rect()
        # 浮雕模式以氣泡位置為基準，位移 0 時要和氣泡模式完全一致
        base_rect, base_size = self.compute_bubble_layout(text, x, y, w, h, fixed_font_size=self.relief_font_pt)
        base_rect = QRect(base_rect)
        gap = max(0, int(self.relief_gap_px))
        font_size = float(self.relief_font_pt)

        if gap == 0:
            return base_rect, font_size

        if self.relief_side == RELIEF_SIDE_TOP:
            dx, dy = 0, -gap
        elif self.relief_side == RELIEF_SIDE_BOTTOM:
            dx, dy = 0, gap
        elif self.relief_side == RELIEF_SIDE_LEFT:
            dx, dy = -gap, 0
        elif self.relief_side == RELIEF_SIDE_RIGHT:
            dx, dy = gap, 0
        else:
            # 自動：優先維持貼近原位，再依空間選一個最自然的方向
            candidates = [(0, -gap), (0, gap), (-gap, 0), (gap, 0)]
            best_rect = QRect(base_rect)
            best_score = None
            for cand_dx, cand_dy in candidates:
                cand = QRect(base_rect)
                cand.translate(cand_dx, cand_dy)
                cand = QRect(
                    max(0, min(cand.x(), parent_rect.width() - cand.width())),
                    max(0, min(cand.y(), parent_rect.height() - cand.height())),
                    cand.width(),
                    cand.height(),
                )
                offscreen_penalty = 0
                if cand.left() <= 0 or cand.top() <= 0 or cand.right() >= parent_rect.right() or cand.bottom() >= parent_rect.bottom():
                    offscreen_penalty = 3000
                center_distance = abs(cand.center().x() - base_rect.center().x()) + abs(cand.center().y() - base_rect.center().y())
                score = (offscreen_penalty, center_distance)
                if best_score is None or score < best_score:
                    best_score = score
                    best_rect = cand
            return best_rect, font_size

        cand = QRect(base_rect)
        cand.translate(dx, dy)
        cand = QRect(
            max(0, min(cand.x(), parent_rect.width() - cand.width())),
            max(0, min(cand.y(), parent_rect.height() - cand.height())),
            cand.width(),
            cand.height(),
        )
        return cand, font_size

    def _rect_overlap_area(self, first, second):
        ix1 = max(first.left(), second.left())
        iy1 = max(first.top(), second.top())
        ix2 = min(first.right(), second.right())
        iy2 = min(first.bottom(), second.bottom())
        if ix2 <= ix1 or iy2 <= iy1:
            return 0
        return (ix2 - ix1) * (iy2 - iy1)

    def paintEvent(self, event):
        if self.render_mode != REGION_RENDER_RELIEF:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(self.text_padding, self.text_padding, -self.text_padding, -self.text_padding)
        font = self.font()
        painter.setFont(font)
        fill = QColor(getattr(self, "bubble_fill_color", "#FFFFFF"))
        outline = QColor(getattr(self, "bubble_outline_color", "rgba(0, 0, 0, 220)"))
        painter.setBrush(Qt.NoBrush)
        flags = Qt.AlignCenter | Qt.TextWordWrap
        offsets = [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]
        painter.setPen(outline)
        for dx, dy in offsets:
            painter.drawText(rect.translated(dx, dy), flags, self.text())
        painter.setPen(fill)
        painter.drawText(rect, flags, self.text())
        painter.end()

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
        self.theme_mode = "light"
        self.scan_mode = SCAN_MODE_FULLSCREEN
        self.render_mode = REGION_RENDER_BUBBLE
        self.relief_side = RELIEF_SIDE_AUTO
        self.relief_font_pt = 18
        self.relief_opacity = RELIEF_BUBBLE_OPACITY
        self.relief_gap_px = 10
        self.scan_region = None  # 浮雕模式定位用的掃描框
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x00000011)
        except Exception:
            pass
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.ghost_mode)
        self.timer.start(50)

    def set_theme_mode(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.theme_mode = theme.key
        self.is_dark = theme.key != "light"
        for b in self.bubbles:
            b.set_theme(theme.key)
            b.update()
        self.update()
        self.repaint()

    def set_render_context(self, scan_mode, render_mode, relief_side=None, relief_font_pt=None, relief_opacity=None, relief_gap_px=None, scan_region=None):
        self.scan_mode = scan_mode if scan_mode in (SCAN_MODE_FULLSCREEN, SCAN_MODE_REGION) else SCAN_MODE_FULLSCREEN
        self.render_mode = render_mode if render_mode in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF) else REGION_RENDER_BUBBLE
        if relief_side in {opt[1] for opt in RELIEF_SIDE_OPTIONS}:
            self.relief_side = relief_side
        if relief_font_pt is not None:
            self.relief_font_pt = max(MIN_BUBBLE_FONT_PT, int(relief_font_pt))
        if relief_opacity is not None:
            self.relief_opacity = max(0, min(100, int(relief_opacity)))
        if relief_gap_px is not None:
            self.relief_gap_px = max(0, min(RELIEF_MAX_GAP_PX, int(relief_gap_px)))
        self.scan_region = scan_region if (scan_region and len(scan_region) == 4) else None

    def update_bubbles(self, results):
        self.clear_all()
        for t, x, y, w, h in results:
            mode = self.render_mode if self.scan_mode == SCAN_MODE_REGION else REGION_RENDER_BUBBLE
            # 框選 + 浮雕模式：把掃描框傳入，讓翻譯貼在框的外側
            region_rect = self.scan_region if (mode == REGION_RENDER_RELIEF and self.scan_mode == SCAN_MODE_REGION and self.scan_region) else None
            self.bubbles.append(
                TransBubble(
                    self,
                    t,
                    x,
                    y,
                    w,
                    h,
                    self.theme_mode,
                    mode,
                    self.relief_side,
                    self.relief_font_pt,
                    self.relief_opacity,
                    self.relief_gap_px,
                    region_rect,
                )
            )
        self.arrange_bubbles()
        self.setVisible(True)
        self.raise_()

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
                offscreen_penalty = 0
                if cand.left() <= screen.left() or cand.right() >= screen.right() or cand.top() <= screen.top() or cand.bottom() >= screen.bottom():
                    offscreen_penalty = 5000
                if bubble.render_mode == REGION_RENDER_RELIEF:
                    anchor_distance = abs(cand.center().x() - original.center().x()) + abs(cand.center().y() - original.center().y())
                    score = (overlap + offscreen_penalty, anchor_distance, cand.width() * cand.height())
                else:
                    source_distance = abs(cand.center().x() - source.center().x()) + abs(cand.center().y() - source.center().y())
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
        self.theme_mode = "light"
        self.hide()

    def set_theme_mode(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.theme_mode = theme.key
        self.update()

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
        theme = resolve_theme(getattr(self, "theme_mode", "light"))
        overlay_bg = QColor(theme.bg)
        overlay_bg.setAlpha(90)
        painter.fillRect(self.rect(), overlay_bg)
        if not self.current_rect.isNull():
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(self.current_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(theme.accent), 2))
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
        self.theme_mode = "light"
        self.frame_opacity = 40
        self.hide()

    def set_theme_mode(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.theme_mode = theme.key
        self.is_dark = theme.key != "light"
        self.update()

    def set_frame_opacity(self, opacity):
        self.frame_opacity = max(0, min(100, int(opacity)))
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
        alpha = int(255 * max(0, min(100, self.frame_opacity)) / 100.0)
        theme = resolve_theme(getattr(self, "theme_mode", "dark" if self.is_dark else "light"))
        selection_colors = build_selection_colors(theme)
        border_color = QColor(selection_colors["border"])
        fill_color = QColor(selection_colors["fill"])
        border_color.setAlpha(alpha)
        fill_color.setAlpha(alpha)
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
        self.resize(800, 1000)
        self.setMinimumSize(800, 1000)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)

        self.frame = QFrame()
        root_layout.addWidget(self.frame)

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.header_panel = QFrame()
        header_layout = QVBoxLayout(self.header_panel)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(10)

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
        translate_layout.setContentsMargins(16, 16, 16, 16)
        translate_layout.setSpacing(12)
        self.lbl_translate = QLabel("翻譯")
        self.lbl_translate.setStyleSheet("font-weight: bold;")
        self.lbl_translate_hint = QLabel("Google 免設定；AI 模式才需要 API Key 與模型")
        self.lbl_translate_hint.setWordWrap(True)
        translate_layout.addWidget(self.lbl_translate)
        translate_layout.addWidget(self.lbl_translate_hint)

        self.lbl_translate_summary = QLabel("目前：Google 翻譯")
        self.lbl_translate_summary.setWordWrap(True)
        translate_layout.addWidget(self.lbl_translate_summary)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.lbl_translate_mode = QLabel("翻譯模式")
        mode_row.addWidget(self.lbl_translate_mode)
        mode_row.addStretch()
        self.translate_mode_group = QButtonGroup(self)
        self.translate_mode_group.setExclusive(True)
        self.btn_translate_google = QPushButton("Google 翻譯")
        self.btn_translate_google.setCheckable(True)
        self.btn_translate_google.setCursor(Qt.PointingHandCursor)
        self.btn_translate_google.clicked.connect(lambda: self.on_translate_mode_clicked(False))
        self.translate_mode_group.addButton(self.btn_translate_google)
        mode_row.addWidget(self.btn_translate_google)
        self.btn_translate_ai = QPushButton("Gemma AI 翻譯")
        self.btn_translate_ai.setCheckable(True)
        self.btn_translate_ai.setCursor(Qt.PointingHandCursor)
        self.btn_translate_ai.clicked.connect(lambda: self.on_translate_mode_clicked(True))
        self.translate_mode_group.addButton(self.btn_translate_ai)
        mode_row.addWidget(self.btn_translate_ai)
        translate_layout.addLayout(mode_row)

        self.advanced_translate_frame = QFrame()
        advanced_translate_layout = QVBoxLayout(self.advanced_translate_frame)
        advanced_translate_layout.setContentsMargins(14, 14, 14, 14)
        advanced_translate_layout.setSpacing(10)
        self.lbl_advanced_translate = QLabel("進階翻譯設定")
        self.lbl_advanced_hint = QLabel("只有 AI 模式會用到這些欄位")
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

        self.chk_auto_switch = QCheckBox("自動切換")
        self.chk_auto_switch.toggled.connect(self.on_auto_switch_toggled)
        advanced_translate_layout.addWidget(self.chk_auto_switch)
        translate_layout.addWidget(self.advanced_translate_frame)
        self.advanced_translate_frame.setVisible(False)

        self.card_ocr = QFrame()
        ocr_layout = QVBoxLayout(self.card_ocr)
        ocr_layout.setContentsMargins(16, 16, 16, 16)
        ocr_layout.setSpacing(10)
        self.lbl_ocr = QLabel("OCR")
        self.lbl_ocr.setStyleSheet("font-weight: bold;")
        self.lbl_ocr_hint = QLabel("閥值與字元清理會直接影響辨識品質")
        self.lbl_ocr_hint.setWordWrap(True)
        ocr_layout.addWidget(self.lbl_ocr)
        ocr_layout.addWidget(self.lbl_ocr_hint)

        self.auto_scan_panel = QFrame()
        auto_scan_layout = QVBoxLayout(self.auto_scan_panel)
        auto_scan_layout.setContentsMargins(14, 14, 14, 14)
        auto_scan_layout.setSpacing(10)
        self.lbl_auto_scan = QLabel("10 秒按鈕")
        self.lbl_auto_scan.setStyleSheet("font-weight: bold;")
        self.lbl_auto_scan_hint = QLabel("中心秒數與偏移幅度會同步到主畫面")
        self.lbl_auto_scan_hint.setWordWrap(True)
        auto_scan_layout.addWidget(self.lbl_auto_scan)
        auto_scan_layout.addWidget(self.lbl_auto_scan_hint)

        center_row = QHBoxLayout()
        self.lbl_random_scan_center = QLabel("中心秒數")
        center_row.addWidget(self.lbl_random_scan_center)
        center_row.addStretch()
        self.spin_random_scan_center = QSpinBox()
        self.spin_random_scan_center.setRange(3, 300)
        self.spin_random_scan_center.setSuffix(" 秒")
        self.spin_random_scan_center.valueChanged.connect(self.on_random_scan_settings_changed)
        center_row.addWidget(self.spin_random_scan_center)
        auto_scan_layout.addLayout(center_row)

        jitter_row = QHBoxLayout()
        self.lbl_random_scan_jitter = QLabel("偏移幅度")
        jitter_row.addWidget(self.lbl_random_scan_jitter)
        jitter_row.addStretch()
        self.spin_random_scan_jitter = QSpinBox()
        self.spin_random_scan_jitter.setRange(0, 100)
        self.spin_random_scan_jitter.setSuffix(" %")
        self.spin_random_scan_jitter.valueChanged.connect(self.on_random_scan_settings_changed)
        jitter_row.addWidget(self.spin_random_scan_jitter)
        auto_scan_layout.addLayout(jitter_row)

        self.lbl_random_scan_summary = QLabel("目前：10s 附近 · 約 8 ~ 12 秒")
        self.lbl_random_scan_summary.setWordWrap(True)
        auto_scan_layout.addWidget(self.lbl_random_scan_summary)
        ocr_layout.addWidget(self.auto_scan_panel)

        self.card_region_render = QFrame()
        region_render_layout = QVBoxLayout(self.card_region_render)
        region_render_layout.setContentsMargins(16, 16, 16, 16)
        region_render_layout.setSpacing(10)
        self.lbl_region_render = QLabel("框選顯示")
        self.lbl_region_render.setStyleSheet("font-weight: bold;")
        self.lbl_region_render_hint = QLabel("氣泡保留原本樣式，浮雕會貼近原文")
        self.lbl_region_render_hint.setWordWrap(True)
        region_render_layout.addWidget(self.lbl_region_render)
        region_render_layout.addWidget(self.lbl_region_render_hint)

        render_row = QHBoxLayout()
        self.lbl_region_render_mode = QLabel("顯示方式")
        render_row.addWidget(self.lbl_region_render_mode)
        render_row.addStretch()
        self.cmb_region_render_mode = QComboBox()
        self.cmb_region_render_mode.addItem("氣泡功能", REGION_RENDER_BUBBLE)
        self.cmb_region_render_mode.addItem("浮雕功能", REGION_RENDER_RELIEF)
        self.cmb_region_render_mode.currentIndexChanged.connect(self.on_region_render_mode_changed)
        render_row.addWidget(self.cmb_region_render_mode)
        region_render_layout.addLayout(render_row)

        self.lbl_region_render_summary = QLabel("目前：氣泡功能")
        self.lbl_region_render_summary.setWordWrap(True)
        region_render_layout.addWidget(self.lbl_region_render_summary)

        self.card_relief = QFrame()
        relief_layout = QVBoxLayout(self.card_relief)
        relief_layout.setContentsMargins(16, 16, 16, 16)
        relief_layout.setSpacing(10)
        self.lbl_relief = QLabel("浮雕細節")
        self.lbl_relief.setStyleSheet("font-weight: bold;")
        self.lbl_relief_hint = QLabel("只在浮雕模式啟用，位移 0 會對齊原位")
        self.lbl_relief_hint.setWordWrap(True)
        relief_layout.addWidget(self.lbl_relief)
        relief_layout.addWidget(self.lbl_relief_hint)

        side_row = QHBoxLayout()
        self.lbl_relief_side = QLabel("文字方向")
        side_row.addWidget(self.lbl_relief_side)
        side_row.addStretch()
        self.cmb_relief_side = QComboBox()
        for label, value in RELIEF_SIDE_OPTIONS:
            self.cmb_relief_side.addItem(label, value)
        self.cmb_relief_side.currentIndexChanged.connect(self.on_relief_setting_changed)
        side_row.addWidget(self.cmb_relief_side)
        relief_layout.addLayout(side_row)

        font_row = QHBoxLayout()
        self.lbl_relief_font = QLabel("文字大小")
        font_row.addWidget(self.lbl_relief_font)
        font_row.addStretch()
        self.spin_relief_font = QSpinBox()
        self.spin_relief_font.setRange(8, 48)
        self.spin_relief_font.setSuffix(" pt")
        self.spin_relief_font.valueChanged.connect(self.on_relief_setting_changed)
        font_row.addWidget(self.spin_relief_font)
        relief_layout.addLayout(font_row)

        gap_row = QHBoxLayout()
        self.lbl_relief_gap = QLabel("浮雕位移")
        gap_row.addWidget(self.lbl_relief_gap)
        self.slider_relief_gap = QSlider(Qt.Horizontal)
        self.slider_relief_gap.setRange(0, RELIEF_MAX_GAP_PX)
        self.slider_relief_gap.valueChanged.connect(self.on_relief_setting_changed)
        gap_row.addWidget(self.slider_relief_gap)
        self.lbl_relief_gap_value = QLabel("10 px")
        self.lbl_relief_gap_value.setFixedWidth(58)
        self.lbl_relief_gap_value.setAlignment(Qt.AlignCenter)
        gap_row.addWidget(self.lbl_relief_gap_value)
        relief_layout.addLayout(gap_row)

        opacity_row = QHBoxLayout()
        self.lbl_relief_opacity = QLabel("選區框透明度")
        opacity_row.addWidget(self.lbl_relief_opacity)
        self.slider_relief_opacity = QSlider(Qt.Horizontal)
        self.slider_relief_opacity.setRange(0, 100)
        self.slider_relief_opacity.valueChanged.connect(self.on_relief_setting_changed)
        opacity_row.addWidget(self.slider_relief_opacity)
        self.lbl_relief_opacity_value = QLabel("40%")
        self.lbl_relief_opacity_value.setFixedWidth(46)
        self.lbl_relief_opacity_value.setAlignment(Qt.AlignCenter)
        opacity_row.addWidget(self.lbl_relief_opacity_value)
        relief_layout.addLayout(opacity_row)

        self.lbl_relief_summary = QLabel("目前：自動 · 18 pt · 選區框透明度 40%")
        self.lbl_relief_summary.setWordWrap(True)
        relief_layout.addWidget(self.lbl_relief_summary)

        self.card_appearance = QFrame()
        appearance_layout = QVBoxLayout(self.card_appearance)
        appearance_layout.setContentsMargins(16, 16, 16, 16)
        appearance_layout.setSpacing(10)
        self.lbl_appearance = QLabel("外觀")
        self.lbl_appearance.setStyleSheet("font-weight: bold;")
        self.chk_dark_mode = QCheckBox("深色模式")
        self.chk_dark_mode.toggled.connect(self.controller.set_theme_mode)
        appearance_layout.addWidget(self.lbl_appearance)
        appearance_layout.addWidget(self.chk_dark_mode)

        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        left_panel = QWidget()
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_col = QVBoxLayout(left_panel)
        left_col.setSpacing(12)
        left_col.addWidget(self.card_ocr)
        left_col.addWidget(self.card_region_render)
        left_col.addWidget(self.card_relief)
        left_col.addStretch()

        right_panel = QWidget()
        right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_col = QVBoxLayout(right_panel)
        right_col.setSpacing(12)
        right_col.addWidget(self.card_translate)
        right_col.addWidget(self.card_appearance)
        right_col.addStretch()

        self.settings_splitter = QSplitter(Qt.Horizontal)
        self.settings_splitter.setChildrenCollapsible(False)
        self.settings_splitter.setHandleWidth(8)
        self.settings_splitter.addWidget(left_panel)
        self.settings_splitter.addWidget(right_panel)
        self.settings_splitter.setStretchFactor(0, 1)
        self.settings_splitter.setStretchFactor(1, 1)
        self.settings_splitter.setSizes([2, 1])
        content_row.addWidget(self.settings_splitter)
        layout.addLayout(content_row)
        layout.addStretch()
        self.left_panel = left_panel
        self.right_panel = right_panel
        self.auto_scan_panel.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.advanced_translate_frame.setStyleSheet("QFrame { background: transparent; border: none; }")

    def on_translate_mode_clicked(self, use_ai):
        self.set_translate_mode(use_ai)
        self.controller.btn_ai_mode.setChecked(use_ai)
        self.controller.toggle_ai_translation(use_ai)
        if use_ai and not self.controller.worker.google_api_key.strip():
            self.set_translate_mode(True)
            self.update_translate_summary()
        else:
            self.sync_from_controller()

    def on_api_key_text_changed(self, text):
        self.controller.on_api_key_changed(text)
        if text.strip() and self.btn_translate_ai.isChecked() and not self.controller.btn_ai_mode.isChecked():
            self.controller.btn_ai_mode.setChecked(True)
            self.controller.toggle_ai_translation(True)
        self.update_translate_summary()

    def on_ai_model_changed(self, index):
        self.controller.on_ai_model_changed(index)
        self.update_translate_summary()

    def on_auto_switch_toggled(self, checked):
        self.controller.set_gemma_auto_switch_mode(checked)
        self.update_translate_summary()

    def set_translate_mode(self, use_ai):
        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not use_ai)
        self.btn_translate_ai.setChecked(use_ai)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)
        self.set_translate_advanced_visible(True)
        self.update_key_state(use_ai)
        if use_ai and not self.input_api_key.text().strip():
            self.input_api_key.setFocus()
        self.update_translate_summary()

    def on_random_scan_settings_changed(self, *_):
        self.controller.on_random_scan_settings_changed(
            self.spin_random_scan_center.value(),
            self.spin_random_scan_jitter.value(),
        )
        self.update_random_scan_summary()

    def on_region_render_mode_changed(self, index):
        self.controller.on_region_render_mode_changed(self.cmb_region_render_mode.itemData(index))
        self.update_region_render_summary()

    def on_relief_setting_changed(self, *_):
        self.controller.on_region_relief_settings_changed(
            self.cmb_relief_side.itemData(self.cmb_relief_side.currentIndex()),
            self.spin_relief_font.value(),
            self.slider_relief_gap.value(),
            self.slider_relief_opacity.value(),
        )
        self.update_relief_summary()

    def set_translate_advanced_visible(self, visible):
        self.advanced_translate_frame.setVisible(visible)
        self.adjustSize()
        QTimer.singleShot(0, self._lock_settings_columns)

    def update_random_scan_summary(self):
        center = max(1, int(self.spin_random_scan_center.value()))
        jitter = max(0, int(self.spin_random_scan_jitter.value()))
        spread = max(0, int(round(center * jitter / 100.0)))
        low = max(1, center - spread)
        high = max(low, center + spread)
        self.lbl_random_scan_summary.setText(f"狀態：{center}s 附近 · 約 {low} ~ {high} 秒")

    def update_region_render_summary(self):
        mode = self.cmb_region_render_mode.itemData(self.cmb_region_render_mode.currentIndex())
        if mode == REGION_RENDER_RELIEF:
            self.lbl_region_render_summary.setText("狀態：浮雕功能 · 文字貼近原文")
            self.card_relief.setVisible(True)
        else:
            self.lbl_region_render_summary.setText("狀態：氣泡功能 · 保留原本泡泡")
            self.card_relief.setVisible(False)
        self.adjustSize()

    def update_relief_summary(self):
        side = self.cmb_relief_side.itemText(self.cmb_relief_side.currentIndex())
        font_pt = int(self.spin_relief_font.value())
        gap_px = int(self.slider_relief_gap.value())
        opacity = int(self.slider_relief_opacity.value())
        self.lbl_relief_gap_value.setText(f"{gap_px} px")
        self.lbl_relief_opacity_value.setText(f"{opacity}%")
        self.lbl_relief_summary.setText(f"狀態：{side} · {font_pt} pt · {gap_px}px · {opacity}%")

    def update_translate_summary(self):
        use_ai = self.btn_translate_ai.isChecked()
        model_name = self.cmb_ai_model.currentText() if self.cmb_ai_model.count() else "Gemma"
        if use_ai:
            auto_state = "自動切換 ON" if self.chk_auto_switch.isChecked() else "自動切換 OFF"
            self.lbl_translate_summary.setText(f"狀態：AI 翻譯 · {model_name} · {auto_state}")
        else:
            self.lbl_translate_summary.setText("狀態：Google 翻譯 · 免 API KEY")

    def sync_from_controller(self):
        self.chk_dark_mode.blockSignals(True)
        self.chk_dark_mode.setChecked(self.controller.is_dark_mode)
        self.chk_dark_mode.blockSignals(False)

        self.spin_random_scan_center.blockSignals(True)
        self.spin_random_scan_center.setValue(self.controller.random_scan_center_seconds)
        self.spin_random_scan_center.blockSignals(False)

        self.spin_random_scan_jitter.blockSignals(True)
        self.spin_random_scan_jitter.setValue(self.controller.random_scan_jitter_percent)
        self.spin_random_scan_jitter.blockSignals(False)

        self.cmb_region_render_mode.blockSignals(True)
        self.cmb_region_render_mode.setCurrentIndex(
            1 if self.controller.region_render_mode == REGION_RENDER_RELIEF else 0
        )
        self.cmb_region_render_mode.blockSignals(False)

        self.cmb_relief_side.blockSignals(True)
        self.cmb_relief_side.setCurrentIndex(max(0, self.cmb_relief_side.findData(self.controller.region_relief_side)))
        self.cmb_relief_side.blockSignals(False)

        self.spin_relief_font.blockSignals(True)
        self.spin_relief_font.setValue(self.controller.region_relief_font_pt)
        self.spin_relief_font.blockSignals(False)

        self.slider_relief_gap.blockSignals(True)
        self.slider_relief_gap.setValue(self.controller.region_relief_gap_px)
        self.slider_relief_gap.blockSignals(False)

        self.slider_relief_opacity.blockSignals(True)
        self.slider_relief_opacity.setValue(self.controller.region_frame_opacity)
        self.slider_relief_opacity.blockSignals(False)

        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(self.controller.worker.google_api_key)
        self.input_api_key.blockSignals(False)

        self.cmb_ai_model.blockSignals(True)
        self.cmb_ai_model.setCurrentIndex(self.controller.cmb_ai_model.currentIndex())
        self.cmb_ai_model.blockSignals(False)

        self.chk_auto_switch.blockSignals(True)
        self.chk_auto_switch.setChecked(self.controller.worker.gemma_auto_switch_enabled)
        self.chk_auto_switch.blockSignals(False)

        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not self.controller.btn_ai_mode.isChecked())
        self.btn_translate_ai.setChecked(self.controller.btn_ai_mode.isChecked())
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)
        self.set_translate_advanced_visible(self.controller.btn_ai_mode.isChecked())
        self.update_translate_summary()
        self.update_random_scan_summary()
        self.update_region_render_summary()
        self.update_relief_summary()
        QTimer.singleShot(0, self._lock_settings_columns)

    def _lock_settings_columns(self):
        if not hasattr(self, "settings_splitter"):
            return
        total_width = self.settings_splitter.width()
        if total_width <= 0:
            return
        handle_width = self.settings_splitter.handleWidth()
        available_width = max(0, total_width - handle_width)
        left_width = int(available_width * 0.60)
        right_width = available_width - left_width
        if hasattr(self, "left_panel") and hasattr(self, "right_panel"):
            self.left_panel.setMinimumWidth(left_width)
            self.left_panel.setMaximumWidth(left_width)
            self.right_panel.setMinimumWidth(right_width)
            self.right_panel.setMaximumWidth(right_width)
        self.settings_splitter.blockSignals(True)
        self.settings_splitter.setSizes([left_width, right_width])
        self.settings_splitter.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._lock_settings_columns()

    def update_theme(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.setStyleSheet(theme.base_qss())
        self.frame.setStyleSheet(theme.window_qss(radius=20, border_width=2))
        self.header_panel.setStyleSheet(theme.header_qss(radius=16))
        self.card_translate.setStyleSheet(theme.panel_qss("primary", radius=16))
        self.card_ocr.setStyleSheet(theme.panel_qss("subtle", radius=16))
        self.card_region_render.setStyleSheet(theme.panel_qss("subtle", radius=16))
        self.card_relief.setStyleSheet(theme.panel_qss("subtle", radius=16))
        self.card_appearance.setStyleSheet(theme.panel_qss("subtle", radius=16))
        self.advanced_translate_frame.setStyleSheet(f"QFrame {{ background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 12px; }}")
        self.lbl_title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {theme.text}; background: transparent; border: none;")
        self.lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_autosave.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_sync_state.setStyleSheet(f"color: {theme.text}; background-color: {theme.card_bg}; border: 1px solid {theme.border}; border-radius: 999px; padding: 4px 10px;")
        self.lbl_appearance.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text};")
        self.lbl_ocr.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text};")
        self.lbl_region_render.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text};")
        self.lbl_region_render_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_region_render_mode.setStyleSheet(f"color: {theme.text};")
        self.lbl_region_render_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_relief.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text};")
        self.lbl_relief_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_relief_side.setStyleSheet(f"color: {theme.text};")
        self.lbl_relief_font.setStyleSheet(f"color: {theme.text};")
        self.lbl_relief_gap.setStyleSheet(f"color: {theme.text};")
        self.lbl_relief_opacity.setStyleSheet(f"color: {theme.text};")
        self.lbl_relief_gap_value.setStyleSheet(f"color: {theme.accent}; font-weight: 700; background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 10px; padding: 4px 6px;")
        self.lbl_relief_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_relief_opacity_value.setStyleSheet(f"color: {theme.accent}; font-weight: 700; background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 10px; padding: 4px 6px;")
        self.lbl_translate.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text};")
        self.lbl_advanced_translate.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {theme.accent};")
        self.lbl_advanced_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_ocr_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_translate_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_random_scan_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_translate_summary.setStyleSheet(theme.pill_qss("accent"))
        self.btn_close.setStyleSheet(theme.button_qss("ghost"))

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

class SettingsWindowRevamp(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("設定頁面")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.old_pos = None
        self._drag_origin = None
        self._ai_requested = False
        self.setFixedSize(800, 1000)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(0)

        self.frame = QFrame()
        root.addWidget(self.frame)
        main = QVBoxLayout(self.frame)
        main.setContentsMargins(18, 18, 18, 18)
        main.setSpacing(14)

        self.header_panel = QFrame()
        header = QVBoxLayout(self.header_panel)
        header.setContentsMargins(18, 16, 18, 16)
        header.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self.lbl_title = QLabel("設定頁面")
        self.lbl_subtitle = QLabel("把常用設定分成固定五塊，少一點伸縮，多一點直接")
        self.lbl_title.setStyleSheet("font-size: 19px; font-weight: 800; background: transparent; border: none;")
        self.lbl_subtitle.setStyleSheet("font-size: 11px; background: transparent; border: none;")
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_subtitle)
        top_row.addLayout(title_box)
        top_row.addStretch()
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.hide)
        top_row.addWidget(self.btn_close)
        header.addLayout(top_row)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        self.lbl_autosave = QLabel("自動儲存中")
        self.lbl_sync_state = QLabel("即時同步")
        chip_row.addWidget(self.lbl_autosave)
        chip_row.addWidget(self.lbl_sync_state)
        chip_row.addStretch()
        self.cmb_theme_mode_chip = QComboBox()
        for theme in ThemeRegistry.available():
            self.cmb_theme_mode_chip.addItem(theme.label, theme.key)
        self.cmb_theme_mode_chip.setCursor(Qt.PointingHandCursor)
        self.cmb_theme_mode_chip.setMinimumWidth(132)
        self.cmb_theme_mode_chip.currentIndexChanged.connect(self.on_theme_mode_changed)
        chip_row.addWidget(self.cmb_theme_mode_chip)
        header.addLayout(chip_row)
        main.addWidget(self.header_panel)

        self.card_translate = QFrame()
        translate = QVBoxLayout(self.card_translate)
        translate.setContentsMargins(18, 18, 18, 18)
        translate.setSpacing(12)
        self.lbl_translate = QLabel("翻譯")
        self.lbl_translate_hint = QLabel("Google 免設定；AI 模式請看右側 KEY 區塊")
        self.lbl_translate_hint.setWordWrap(True)
        self.lbl_translate_summary = QLabel("狀態：Google 翻譯中")
        self.lbl_translate_summary.setWordWrap(True)
        translate.addWidget(self.lbl_translate)
        translate.addWidget(self.lbl_translate_hint)
        translate.addWidget(self.lbl_translate_summary)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.lbl_translate_mode = QLabel("翻譯模式")
        mode_row.addWidget(self.lbl_translate_mode)
        mode_row.addStretch()
        self.translate_mode_group = QButtonGroup(self)
        self.translate_mode_group.setExclusive(True)
        self.btn_translate_google = QPushButton("Google 翻譯")
        self.btn_translate_google.setCheckable(True)
        self.btn_translate_google.clicked.connect(lambda: self.on_translate_mode_clicked(False))
        self.translate_mode_group.addButton(self.btn_translate_google)
        mode_row.addWidget(self.btn_translate_google)
        self.btn_translate_ai = QPushButton("Gemma AI 翻譯")
        self.btn_translate_ai.setCheckable(True)
        self.btn_translate_ai.clicked.connect(lambda: self.on_translate_mode_clicked(True))
        self.translate_mode_group.addButton(self.btn_translate_ai)
        mode_row.addWidget(self.btn_translate_ai)
        translate.addLayout(mode_row)

        self.advanced_translate_frame = QFrame()
        adv = QVBoxLayout(self.advanced_translate_frame)
        adv.setContentsMargins(14, 14, 14, 14)
        adv.setSpacing(10)
        self.lbl_api_key = QLabel("Google API KEY")
        adv.addWidget(self.lbl_api_key)
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.input_api_key.setPlaceholderText("輸入 Google API KEY")
        self.input_api_key.textChanged.connect(self.on_api_key_text_changed)
        adv.addWidget(self.input_api_key)
        self.lbl_ai_model = QLabel("AI 模型")
        adv.addWidget(self.lbl_ai_model)
        self.cmb_ai_model = QComboBox()
        for label, model_name in SUPPORTED_AI_MODELS:
            self.cmb_ai_model.addItem(label, model_name)
        self.cmb_ai_model.currentIndexChanged.connect(self.on_ai_model_changed)
        adv.addWidget(self.cmb_ai_model)
        self.chk_auto_switch = QCheckBox("自動切換")
        self.chk_auto_switch.toggled.connect(self.on_auto_switch_toggled)
        adv.addWidget(self.chk_auto_switch)
        self.card_key = QFrame()
        key_layout = QVBoxLayout(self.card_key)
        key_layout.setContentsMargins(18, 18, 18, 18)
        key_layout.setSpacing(12)
        self.lbl_advanced_translate = QLabel("KEY")
        self.lbl_advanced_hint = QLabel("輸入 Google API KEY，AI 模式才會用到")
        self.lbl_advanced_hint.setWordWrap(True)
        key_layout.addWidget(self.lbl_advanced_translate)
        key_layout.addWidget(self.lbl_advanced_hint)
        key_layout.addWidget(self.advanced_translate_frame)

        self.card_ocr = QFrame()
        ocr = QVBoxLayout(self.card_ocr)
        ocr.setContentsMargins(18, 18, 18, 18)
        ocr.setSpacing(12)
        self.lbl_ocr = QLabel("掃描")
        self.lbl_ocr_hint = QLabel("中心秒數與偏移幅度會直接影響觸發節奏")
        self.lbl_ocr_hint.setWordWrap(True)
        ocr.addWidget(self.lbl_ocr)
        ocr.addWidget(self.lbl_ocr_hint)

        self.auto_scan_panel = QFrame()
        auto_scan = QVBoxLayout(self.auto_scan_panel)
        auto_scan.setContentsMargins(14, 14, 14, 14)
        auto_scan.setSpacing(10)
        self.lbl_auto_scan = QLabel("掃描設定")
        self.lbl_auto_scan_hint = QLabel("中心秒數與偏移幅度會同步到主畫面")
        self.lbl_auto_scan_hint.setWordWrap(True)
        auto_scan.addWidget(self.lbl_auto_scan)
        auto_scan.addWidget(self.lbl_auto_scan_hint)
        center_row = QHBoxLayout()
        center_row.setSpacing(8)
        self.lbl_random_scan_center = QLabel("中心秒數")
        center_row.addWidget(self.lbl_random_scan_center)
        center_row.addStretch()
        self.spin_random_scan_center = QSpinBox()
        self.spin_random_scan_center.setRange(3, 300)
        self.spin_random_scan_center.setSuffix(" 秒")
        self.spin_random_scan_center.valueChanged.connect(self.on_random_scan_settings_changed)
        center_row.addWidget(self.spin_random_scan_center)
        auto_scan.addLayout(center_row)
        jitter_row = QHBoxLayout()
        jitter_row.setSpacing(8)
        self.lbl_random_scan_jitter = QLabel("偏移幅度")
        jitter_row.addWidget(self.lbl_random_scan_jitter)
        jitter_row.addStretch()
        self.spin_random_scan_jitter = QSpinBox()
        self.spin_random_scan_jitter.setRange(0, 100)
        self.spin_random_scan_jitter.setSuffix(" %")
        self.spin_random_scan_jitter.valueChanged.connect(self.on_random_scan_settings_changed)
        jitter_row.addWidget(self.spin_random_scan_jitter)
        auto_scan.addLayout(jitter_row)
        self.lbl_random_scan_summary = QLabel("狀態：10s 附近 · 約 8 ~ 12 秒")
        self.lbl_random_scan_summary.setWordWrap(True)
        auto_scan.addWidget(self.lbl_random_scan_summary)
        ocr.addWidget(self.auto_scan_panel)

        self.card_region_render = QFrame()
        render = QVBoxLayout(self.card_region_render)
        render.setContentsMargins(18, 18, 18, 18)
        render.setSpacing(12)
        self.lbl_region_render = QLabel("模式")
        self.lbl_region_render_hint = QLabel("氣泡保留原本樣式，浮雕會貼近原文")
        self.lbl_region_render_hint.setWordWrap(True)
        render.addWidget(self.lbl_region_render)
        render.addWidget(self.lbl_region_render_hint)
        render_row = QHBoxLayout()
        render_row.setSpacing(8)
        self.lbl_region_render_mode = QLabel("顯示方式")
        render_row.addWidget(self.lbl_region_render_mode)
        render_row.addStretch()
        self.cmb_region_render_mode = QComboBox()
        self.cmb_region_render_mode.addItem("氣泡功能", REGION_RENDER_BUBBLE)
        self.cmb_region_render_mode.addItem("浮雕功能", REGION_RENDER_RELIEF)
        self.cmb_region_render_mode.currentIndexChanged.connect(self.on_region_render_mode_changed)
        render_row.addWidget(self.cmb_region_render_mode)
        render.addLayout(render_row)
        self.lbl_region_render_summary = QLabel("狀態：氣泡功能")
        self.lbl_region_render_summary.setWordWrap(True)
        render.addWidget(self.lbl_region_render_summary)

        self.card_relief = QFrame()
        relief = QVBoxLayout(self.card_relief)
        relief.setContentsMargins(18, 18, 18, 18)
        relief.setSpacing(12)
        self.lbl_relief = QLabel("浮雕細節")
        self.lbl_relief_hint = QLabel("只在浮雕模式啟用，位移 0 會對齊原位")
        self.lbl_relief_hint.setWordWrap(True)
        relief.addWidget(self.lbl_relief)
        relief.addWidget(self.lbl_relief_hint)
        side_row = QHBoxLayout()
        side_row.setSpacing(8)
        self.lbl_relief_side = QLabel("文字方向")
        side_row.addWidget(self.lbl_relief_side)
        side_row.addStretch()
        self.cmb_relief_side = QComboBox()
        for label, value in RELIEF_SIDE_OPTIONS:
            self.cmb_relief_side.addItem(label, value)
        self.cmb_relief_side.currentIndexChanged.connect(self.on_relief_setting_changed)
        side_row.addWidget(self.cmb_relief_side)
        relief.addLayout(side_row)
        font_row = QHBoxLayout()
        font_row.setSpacing(8)
        self.lbl_relief_font = QLabel("文字大小")
        font_row.addWidget(self.lbl_relief_font)
        font_row.addStretch()
        self.spin_relief_font = QSpinBox()
        self.spin_relief_font.setRange(8, 48)
        self.spin_relief_font.setSuffix(" pt")
        self.spin_relief_font.valueChanged.connect(self.on_relief_setting_changed)
        font_row.addWidget(self.spin_relief_font)
        relief.addLayout(font_row)
        gap_row = QHBoxLayout()
        gap_row.setSpacing(8)
        self.lbl_relief_gap = QLabel("浮雕位移")
        gap_row.addWidget(self.lbl_relief_gap)
        self.slider_relief_gap = QSlider(Qt.Horizontal)
        self.slider_relief_gap.setRange(0, RELIEF_MAX_GAP_PX)
        self.slider_relief_gap.valueChanged.connect(self.on_relief_setting_changed)
        gap_row.addWidget(self.slider_relief_gap)
        self.lbl_relief_gap_value = QLabel("10 px")
        self.lbl_relief_gap_value.setFixedWidth(58)
        self.lbl_relief_gap_value.setAlignment(Qt.AlignCenter)
        gap_row.addWidget(self.lbl_relief_gap_value)
        relief.addLayout(gap_row)
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(8)
        self.lbl_relief_opacity = QLabel("選區框透明度")
        opacity_row.addWidget(self.lbl_relief_opacity)
        self.slider_relief_opacity = QSlider(Qt.Horizontal)
        self.slider_relief_opacity.setRange(0, 100)
        self.slider_relief_opacity.valueChanged.connect(self.on_relief_setting_changed)
        opacity_row.addWidget(self.slider_relief_opacity)
        self.lbl_relief_opacity_value = QLabel("40%")
        self.lbl_relief_opacity_value.setFixedWidth(46)
        self.lbl_relief_opacity_value.setAlignment(Qt.AlignCenter)
        opacity_row.addWidget(self.lbl_relief_opacity_value)
        relief.addLayout(opacity_row)
        self.lbl_relief_summary = QLabel("狀態：自動 · 18 pt · 選區框透明度 40%")
        self.lbl_relief_summary.setWordWrap(True)
        relief.addWidget(self.lbl_relief_summary)
        body = QWidget()
        body_grid = QGridLayout(body)
        body_grid.setContentsMargins(0, 0, 0, 0)
        body_grid.setHorizontalSpacing(14)
        body_grid.setVerticalSpacing(14)
        body_grid.setColumnStretch(0, 1)
        body_grid.setColumnStretch(1, 1)
        body_grid.addWidget(self.card_translate, 0, 0, 1, 2)
        body_grid.addWidget(self.card_key, 1, 0)
        body_grid.addWidget(self.card_ocr, 1, 1)
        body_grid.addWidget(self.card_region_render, 2, 0)
        body_grid.addWidget(self.card_relief, 2, 1)
        main.addWidget(body)

        self._drag_widgets = [
            self,
            self.frame,
            self.header_panel,
            body,
            self.card_translate,
            self.card_key,
            self.card_ocr,
            self.auto_scan_panel,
            self.card_region_render,
            self.card_relief,
        ]
        for widget in self._drag_widgets:
            widget.installEventFilter(self)

        self.auto_scan_panel.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.advanced_translate_frame.setStyleSheet("QFrame { background: transparent; border: none; }")

    def on_translate_mode_clicked(self, use_ai):
        self.set_translate_mode(use_ai)
        has_key = bool(self.controller.worker.google_api_key.strip())
        if use_ai:
            if has_key:
                self._ai_requested = True
                self.controller.btn_ai_mode.setChecked(True)
                self.controller.toggle_ai_translation(True)
            else:
                self._ai_requested = True
                self.controller.btn_ai_mode.blockSignals(True)
                self.controller.btn_ai_mode.setChecked(False)
                self.controller.btn_ai_mode.blockSignals(False)
                self.update_key_state(True)
                self.input_api_key.setFocus()
        else:
            self._ai_requested = False
            self.controller.btn_ai_mode.setChecked(False)
            self.controller.toggle_ai_translation(False)

    def on_api_key_text_changed(self, text):
        self.controller.on_api_key_changed(text)
        if text.strip() and self.btn_translate_ai.isChecked() and not self.controller.btn_ai_mode.isChecked():
            self.controller.btn_ai_mode.setChecked(True)
            self.controller.toggle_ai_translation(True)
        self.update_translate_summary()

    def on_ai_model_changed(self, index):
        self.controller.on_ai_model_changed(index)
        self.update_translate_summary()

    def on_auto_switch_toggled(self, checked):
        self.controller.set_gemma_auto_switch_mode(checked)
        self.update_translate_summary()

    def set_translate_mode(self, use_ai):
        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not use_ai)
        self.btn_translate_ai.setChecked(use_ai)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)
        self.set_translate_advanced_visible(use_ai)
        self.update_key_state(use_ai or self._ai_requested)
        if use_ai and not self.input_api_key.text().strip():
            self.input_api_key.setFocus()
        self.update_translate_summary()

    def on_random_scan_settings_changed(self, *_):
        self.controller.on_random_scan_settings_changed(self.spin_random_scan_center.value(), self.spin_random_scan_jitter.value())
        self.update_random_scan_summary()

    def on_region_render_mode_changed(self, index):
        self.controller.on_region_render_mode_changed(self.cmb_region_render_mode.itemData(index))
        self.update_region_render_summary()

    def on_relief_setting_changed(self, *_):
        self.controller.on_region_relief_settings_changed(
            self.cmb_relief_side.itemData(self.cmb_relief_side.currentIndex()),
            self.spin_relief_font.value(),
            self.slider_relief_gap.value(),
            self.slider_relief_opacity.value(),
        )
        self.update_relief_summary()

    def on_theme_mode_changed(self, index):
        combo = self.sender()
        if combo is None or not hasattr(combo, "itemData"):
            return
        theme_mode = combo.itemData(index)
        if not theme_mode:
            return
        self.controller.set_theme_mode(theme_mode)

    def eventFilter(self, obj, event):
        if obj in getattr(self, "_drag_widgets", ()):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                local_pos = event.position().toPoint()
                child = obj.childAt(local_pos) if hasattr(obj, "childAt") else None
                interactive_types = (QPushButton, QLineEdit, QComboBox, QCheckBox, QSpinBox)
                while child is not None:
                    if isinstance(child, interactive_types):
                        return super().eventFilter(obj, event)
                    child = child.parentWidget()
                self._drag_origin = event.globalPosition().toPoint()
                event.accept()
                return True
            if event.type() == QEvent.MouseMove and self._drag_origin is not None and event.buttons() & Qt.LeftButton:
                delta = event.globalPosition().toPoint() - self._drag_origin
                self.move(self.x() + delta.x(), self.y() + delta.y())
                self._drag_origin = event.globalPosition().toPoint()
                event.accept()
                return True
            if event.type() == QEvent.MouseButtonRelease and self._drag_origin is not None:
                self._drag_origin = None
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def set_translate_advanced_visible(self, visible):
        self.advanced_translate_frame.setVisible(True)

    def update_random_scan_summary(self):
        center = max(1, int(self.spin_random_scan_center.value()))
        jitter = max(0, int(self.spin_random_scan_jitter.value()))
        spread = max(0, int(round(center * jitter / 100.0)))
        low = max(1, center - spread)
        high = max(low, center + spread)
        self.lbl_random_scan_summary.setText(f"目前：{center}s 附近 · 約 {low} ~ {high} 秒")

    def update_region_render_summary(self):
        mode = self.cmb_region_render_mode.itemData(self.cmb_region_render_mode.currentIndex())
        if mode == REGION_RENDER_RELIEF:
            self.lbl_region_render_summary.setText("目前：浮雕功能 · 文字貼近原文")
            self.update_relief_state(True)
        else:
            self.lbl_region_render_summary.setText("目前：氣泡功能 · 保留原本泡泡")
            self.update_relief_state(False)

    def update_relief_summary(self):
        side = self.cmb_relief_side.itemText(self.cmb_relief_side.currentIndex())
        font_pt = int(self.spin_relief_font.value())
        gap_px = int(self.slider_relief_gap.value())
        opacity = int(self.slider_relief_opacity.value())
        self.lbl_relief_gap_value.setText(f"{gap_px} px")
        self.lbl_relief_opacity_value.setText(f"{opacity}%")
        self.lbl_relief_summary.setText(f"目前：{side} · {font_pt} pt · {gap_px}px · {opacity}%")

    def update_translate_summary(self):
        use_ai = self.btn_translate_ai.isChecked()
        model_name = self.cmb_ai_model.currentText() if self.cmb_ai_model.count() else "Gemma"
        if use_ai:
            auto_state = "自動切換 ON" if self.chk_auto_switch.isChecked() else "自動切換 OFF"
            self.lbl_translate_summary.setText(f"目前：AI 翻譯 · {model_name} · {auto_state}")
        else:
            self.lbl_translate_summary.setText("目前：Google 翻譯 · 免 API KEY")

    def update_key_state(self, enabled):
        self.card_key.setEnabled(enabled)
        self.input_api_key.setEnabled(enabled)
        self.cmb_ai_model.setEnabled(enabled)
        self.chk_auto_switch.setEnabled(enabled)
        effect = None
        if not enabled:
            effect = QGraphicsOpacityEffect(self.card_key)
            effect.setOpacity(0.45)
        self.card_key.setGraphicsEffect(effect)

    def update_relief_state(self, enabled):
        self.card_relief.setEnabled(enabled)
        self.cmb_relief_side.setEnabled(enabled)
        self.spin_relief_font.setEnabled(enabled)
        self.slider_relief_gap.setEnabled(enabled)
        self.slider_relief_opacity.setEnabled(enabled)
        effect = None
        if not enabled:
            effect = QGraphicsOpacityEffect(self.card_relief)
            effect.setOpacity(0.45)
        self.card_relief.setGraphicsEffect(effect)

    def sync_from_controller(self):
        ai_requested = self.controller.btn_ai_mode.isChecked()
        if not ai_requested:
            self._ai_requested = False
        theme_mode = getattr(self.controller, "theme_mode", "dark" if self.controller.is_dark_mode else "light")
        self.spin_random_scan_center.blockSignals(True)
        self.spin_random_scan_center.setValue(self.controller.random_scan_center_seconds)
        self.spin_random_scan_center.blockSignals(False)
        self.spin_random_scan_jitter.blockSignals(True)
        self.spin_random_scan_jitter.setValue(self.controller.random_scan_jitter_percent)
        self.spin_random_scan_jitter.blockSignals(False)
        self.cmb_region_render_mode.blockSignals(True)
        self.cmb_region_render_mode.setCurrentIndex(1 if self.controller.region_render_mode == REGION_RENDER_RELIEF else 0)
        self.cmb_region_render_mode.blockSignals(False)
        self.cmb_relief_side.blockSignals(True)
        self.cmb_relief_side.setCurrentIndex(max(0, self.cmb_relief_side.findData(self.controller.region_relief_side)))
        self.cmb_relief_side.blockSignals(False)
        self.spin_relief_font.blockSignals(True)
        self.spin_relief_font.setValue(self.controller.region_relief_font_pt)
        self.spin_relief_font.blockSignals(False)
        self.slider_relief_gap.blockSignals(True)
        self.slider_relief_gap.setValue(self.controller.region_relief_gap_px)
        self.slider_relief_gap.blockSignals(False)
        self.slider_relief_opacity.blockSignals(True)
        self.slider_relief_opacity.setValue(self.controller.region_frame_opacity)
        self.slider_relief_opacity.blockSignals(False)
        self.input_api_key.blockSignals(True)
        self.input_api_key.setText(self.controller.worker.google_api_key)
        self.input_api_key.blockSignals(False)
        self.cmb_ai_model.blockSignals(True)
        self.cmb_ai_model.setCurrentIndex(self.controller.cmb_ai_model.currentIndex())
        self.cmb_ai_model.blockSignals(False)
        self.chk_auto_switch.blockSignals(True)
        self.chk_auto_switch.setChecked(self.controller.worker.gemma_auto_switch_enabled)
        self.chk_auto_switch.blockSignals(False)
        self.btn_translate_google.blockSignals(True)
        self.btn_translate_ai.blockSignals(True)
        self.btn_translate_google.setChecked(not ai_requested)
        self.btn_translate_ai.setChecked(ai_requested)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)
        self.set_translate_advanced_visible(True)
        self.update_key_state(ai_requested or self._ai_requested)
        self._sync_theme_mode(theme_mode)
        self.update_translate_summary()
        self.update_random_scan_summary()
        self.update_region_render_summary()
        self.update_relief_summary()

    def _sync_theme_mode(self, theme_mode):
        theme_mode = str(theme_mode or "light")
        for combo in (getattr(self, "cmb_theme_mode_chip", None),):
            if combo is None:
                continue
            combo.blockSignals(True)
            index = combo.findData(theme_mode)
            if index < 0:
                index = 0
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def update_theme(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.setStyleSheet(theme.base_qss())
        self.frame.setStyleSheet(theme.window_qss(radius=22, border_width=2))
        self.header_panel.setStyleSheet(theme.header_qss(radius=18))
        self.card_translate.setStyleSheet(theme.panel_qss("primary", radius=18))
        self.card_key.setStyleSheet(theme.panel_qss("subtle", radius=18))
        self.card_ocr.setStyleSheet(theme.panel_qss("subtle", radius=18))
        self.card_region_render.setStyleSheet(theme.panel_qss("subtle", radius=18))
        self.card_relief.setStyleSheet(theme.panel_qss("subtle", radius=18))
        self.advanced_translate_frame.setStyleSheet(theme.panel_qss("transparent"))
        self.auto_scan_panel.setStyleSheet(theme.panel_qss("transparent"))
        self.lbl_title.setStyleSheet(f"font-size: 19px; font-weight: 800; color: {theme.text}; background: transparent; border: none;")
        self.lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_autosave.setStyleSheet(theme.pill_qss("accent", size=11))
        self.lbl_sync_state.setStyleSheet(f"color: {theme.subtext}; font-size: 11px; font-weight: 700; background: transparent; border: none; padding: 0;")
        self.lbl_translate.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {theme.text};")
        self.lbl_translate_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_translate_mode.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_translate_summary.setStyleSheet(theme.pill_qss("accent", size=11))
        self.lbl_advanced_translate.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {theme.accent};")
        self.lbl_advanced_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_api_key.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_ai_model.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.chk_auto_switch.setStyleSheet(f"color: {theme.text}; padding-top: 2px;")
        self.lbl_ocr.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {theme.text};")
        self.lbl_ocr_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_auto_scan.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {theme.accent};")
        self.lbl_auto_scan_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_random_scan_summary.setStyleSheet(theme.pill_qss("accent", size=11))
        self.lbl_random_scan_center.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_random_scan_jitter.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_region_render.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {theme.text};")
        self.lbl_region_render_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_region_render_mode.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_region_render_summary.setStyleSheet(theme.pill_qss("accent", size=11))
        self.lbl_relief.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {theme.text};")
        self.lbl_relief_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_relief_side.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_relief_font.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_relief_gap.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_relief_opacity.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {theme.subtext};")
        self.lbl_relief_gap_value.setStyleSheet(f"color: {theme.accent}; font-weight: 700; background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 10px; padding: 4px 6px;")
        self.lbl_relief_opacity_value.setStyleSheet(f"color: {theme.accent}; font-weight: 700; background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 10px; padding: 4px 6px;")
        self.lbl_relief_summary.setStyleSheet(theme.pill_qss("accent", size=11))
        for combo in (
            self.cmb_theme_mode_chip,
            self.cmb_ai_model,
            self.cmb_region_render_mode,
            self.cmb_relief_side,
        ):
            combo.setStyleSheet(theme.combo_qss(radius=6))
        self._sync_theme_mode(theme.key)
        self.update_key_state(self.btn_translate_ai.isChecked() or self._ai_requested)
        self.update_relief_state(self.cmb_region_render_mode.currentData() == REGION_RENDER_RELIEF)
        self.btn_close.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {subtext}; border: none; font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {accent_soft}; color: {text}; border-radius: 15px; }}"
        )

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
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
        self.theme_mode = "light"
        self.current_auto_interval = 0 
        self.countdown_seconds = 0
        self.random_scan_center_seconds = 10
        self.random_scan_jitter_percent = 20
        self.region_render_mode = REGION_RENDER_BUBBLE
        self.region_relief_side = RELIEF_SIDE_AUTO
        self.region_relief_font_pt = 18
        self.region_relief_gap_px = 10
        self.region_frame_opacity = 40
        self.was_minimized = False
        self.scan_mode = SCAN_MODE_FULLSCREEN
        self.selected_region = None
        self.last_scan_results = []
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
        self.lbl_title = QLabel("☁️雲朵翻譯姬 v3.0")
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

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("歡迎回來，雲朵已就緒 (*´▽`*)")
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
        self.btn_mode_region.clicked.connect(self.activate_region_translation)
        self.scan_mode_group.addButton(self.btn_mode_region)
        scan_mode_row.addWidget(self.btn_mode_full)
        scan_mode_row.addWidget(self.btn_mode_region)
        inner_layout.addLayout(scan_mode_row)

        btn_layout = QHBoxLayout()
        self.btn_now = CooldownButton("⚡ 立即 (~)")
        self.btn_now.setCursor(Qt.PointingHandCursor)
        self.btn_now.clicked.connect(self.on_immediate_click)
        self.auto_group = QButtonGroup(self)
        self.auto_group.setExclusive(True)
        self.btn_30 = QPushButton(self.get_random_scan_button_text())
        self.btn_30.setCheckable(True)
        self.btn_30.setCursor(Qt.PointingHandCursor)
        self.btn_30.clicked.connect(self.start_auto_scan)
        self.auto_group.addButton(self.btn_30)
        btn_layout.addWidget(self.btn_now)
        btn_layout.addWidget(self.btn_30)
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_scan)
        btn_layout.addWidget(self.btn_stop)
        inner_layout.addLayout(btn_layout)

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
        self.worker.gemma_model_changed.connect(self.on_worker_gemma_model_changed)
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
            "gemma_model": self.worker.gemma_model,
            "use_gemma_translation": self.worker.use_gemma_translation,
            "gemma_auto_switch_enabled": self.worker.gemma_auto_switch_enabled,
            "google_api_key": self.worker.google_api_key,
            "random_scan_center_seconds": int(self.random_scan_center_seconds),
            "random_scan_jitter_percent": int(self.random_scan_jitter_percent),
            "region_render_mode": self.region_render_mode,
            "region_relief_side": self.region_relief_side,
            "region_relief_font_pt": int(self.region_relief_font_pt),
            "region_relief_gap_px": int(self.region_relief_gap_px),
            "region_frame_opacity": int(self.region_frame_opacity),
            "region_relief_opacity": int(self.region_frame_opacity),
            "scan_mode": self.scan_mode,
            "selected_region": list(self.selected_region) if self.selected_region else None,
            "is_dark_mode": self.is_dark_mode,
            "theme_mode": self.theme_mode,
            "binary_threshold": int(self.worker.binary_threshold),
        }

    def save_settings(self):
        try:
            payload = self.get_settings_payload()
            with open(SETTINGS_FILE, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[Settings] save failed: {exc}")

    def load_settings(self):
        loaded_from_path = None
        for settings_path in (SETTINGS_FILE, LEGACY_SETTINGS_FILE):
            try:
                with open(settings_path, "r", encoding="utf-8") as fp:
                    self.settings_data = json.load(fp)
                loaded_from_path = settings_path
                break
            except Exception:
                continue
        if loaded_from_path is None:
            self.settings_data = {}

        settings = self.settings_data if isinstance(self.settings_data, dict) else {}

        threshold = int(settings.get("binary_threshold", self.worker.binary_threshold))
        threshold = max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, threshold))
        self.worker.binary_threshold = threshold
        self.update_threshold(threshold)

        self.worker.set_auto_threshold_enabled(True)

        center_seconds = int(settings.get("random_scan_center_seconds", self.random_scan_center_seconds))
        self.random_scan_center_seconds = max(3, min(300, center_seconds))

        jitter_percent = int(settings.get("random_scan_jitter_percent", self.random_scan_jitter_percent))
        self.random_scan_jitter_percent = max(0, min(100, jitter_percent))

        region_render_mode = str(settings.get("region_render_mode", REGION_RENDER_BUBBLE) or REGION_RENDER_BUBBLE)
        self.region_render_mode = region_render_mode if region_render_mode in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF) else REGION_RENDER_BUBBLE

        self.region_relief_side = str(settings.get("region_relief_side", RELIEF_SIDE_AUTO) or RELIEF_SIDE_AUTO)
        if self.region_relief_side not in {opt[1] for opt in RELIEF_SIDE_OPTIONS}:
            self.region_relief_side = RELIEF_SIDE_AUTO
        self.region_relief_font_pt = max(MIN_BUBBLE_FONT_PT, min(48, int(settings.get("region_relief_font_pt", self.region_relief_font_pt))))
        self.region_relief_gap_px = max(0, min(RELIEF_MAX_GAP_PX, int(settings.get("region_relief_gap_px", self.region_relief_gap_px))))
        self.region_frame_opacity = max(0, min(100, int(settings.get("region_frame_opacity", settings.get("region_relief_opacity", self.region_frame_opacity)))))

        env_api_key = str(os.getenv(API_KEY_ENV_VAR, "") or "").strip()
        legacy_api_key = str(settings.get("google_api_key", "") or "").strip()
        api_key = env_api_key or legacy_api_key
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

        saved_theme_mode = str(settings.get("theme_mode", "") or "").strip()
        if not saved_theme_mode:
            saved_theme_mode = "dark" if bool(settings.get("is_dark_mode", False)) else "light"
        saved_theme_mode = ThemeRegistry.normalize_mode(saved_theme_mode)
        self.set_theme_mode(saved_theme_mode)
        self.region_frame.set_theme_mode(saved_theme_mode)
        self.region_frame.set_frame_opacity(self.region_frame_opacity)

        saved_region = settings.get("selected_region")
        if isinstance(saved_region, list) and len(saved_region) == 4:
            try:
                self.selected_region = tuple(int(v) for v in saved_region)
                self.worker.set_scan_region(self.selected_region)
            except Exception:
                self.selected_region = None

        if loaded_from_path == LEGACY_SETTINGS_FILE or not os.path.exists(SETTINGS_FILE):
            self.save_settings()

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
        self.worker.set_gemma_auto_switch_enabled(bool(settings.get("gemma_auto_switch_enabled", False)))
        if self.settings_window is not None:
            self.settings_window.chk_auto_switch.blockSignals(True)
            self.settings_window.chk_auto_switch.setChecked(self.worker.gemma_auto_switch_enabled)
            self.settings_window.chk_auto_switch.blockSignals(False)
        self.update_random_scan_button_text()
        if use_gemma_translation and api_key:
            self.lbl_status.setText(f"AI模型: {self.cmb_ai_model.currentText()}")
        else:
            self.lbl_status.setText("歡迎回來，雲朵已就緒 (*´▽`*)")
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_side,
            self.region_relief_font_pt,
            RELIEF_BUBBLE_OPACITY,
            self.region_relief_gap_px,
            self.selected_region,
        )
        if legacy_api_key:
            self.save_settings()

    def update_threshold(self, val):
        self.worker.binary_threshold = val
        self.schedule_save_settings()

    def apply_auto_threshold(self, val):
        self.worker.binary_threshold = val
        self.schedule_save_settings()

    def on_random_scan_settings_changed(self, center_seconds, jitter_percent):
        self.random_scan_center_seconds = max(3, min(300, int(center_seconds)))
        self.random_scan_jitter_percent = max(0, min(100, int(jitter_percent)))
        self.update_random_scan_button_text()
        if self.current_auto_interval > 0 and self.current_auto_interval != 5000:
            self.update_countdown_label()
        if self.settings_window is not None:
            self.settings_window.update_random_scan_summary()
        self.schedule_save_settings()

    def get_random_scan_button_text(self):
        return f"🎲 {int(self.random_scan_center_seconds)}s~"

    def update_random_scan_button_text(self):
        self.btn_30.setText(self.get_random_scan_button_text())

    def get_random_scan_delay_ms(self):
        center_ms = max(1000, int(self.random_scan_center_seconds) * 1000)
        jitter_percent = max(0, int(self.random_scan_jitter_percent))
        spread_ms = int(round(center_ms * jitter_percent / 100.0))
        low = max(1000, center_ms - spread_ms)
        high = max(low, center_ms + spread_ms)
        return random.randint(low, high)

    def on_region_render_mode_changed(self, mode):
        mode = str(mode or REGION_RENDER_BUBBLE)
        if mode not in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF):
            mode = REGION_RENDER_BUBBLE
        self.region_render_mode = mode
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_side,
            self.region_relief_font_pt,
            RELIEF_BUBBLE_OPACITY,
            self.region_relief_gap_px,
            self.selected_region,
        )
        if self.settings_window is not None:
            self.settings_window.update_region_render_summary()
        self.schedule_save_settings()

    def on_region_relief_settings_changed(self, side, font_pt, gap_px, opacity):
        side = str(side or RELIEF_SIDE_AUTO)
        if side not in {opt[1] for opt in RELIEF_SIDE_OPTIONS}:
            side = RELIEF_SIDE_AUTO
        self.region_relief_side = side
        self.region_relief_font_pt = max(MIN_BUBBLE_FONT_PT, min(48, int(font_pt)))
        self.region_relief_gap_px = max(0, min(RELIEF_MAX_GAP_PX, int(gap_px)))
        self.region_frame_opacity = max(0, min(100, int(opacity)))
        self.region_frame.set_theme_mode(self.theme_mode)
        self.region_frame.set_frame_opacity(self.region_frame_opacity)
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_side,
            self.region_relief_font_pt,
            RELIEF_BUBBLE_OPACITY,
            self.region_relief_gap_px,
            self.selected_region,
        )
        self.refresh_overlay_from_last_results()
        self.schedule_save_settings()

    def set_auto_threshold_mode(self, enabled):
        self.worker.set_auto_threshold_enabled(True)

    def set_gemma_auto_switch_mode(self, enabled):
        self.worker.set_gemma_auto_switch_enabled(enabled)
        if self.settings_window is not None and self.settings_window.chk_auto_switch.isChecked() != enabled:
            self.settings_window.chk_auto_switch.blockSignals(True)
            self.settings_window.chk_auto_switch.setChecked(enabled)
            self.settings_window.chk_auto_switch.blockSignals(False)
        self.schedule_save_settings()

    def on_worker_gemma_model_changed(self, old_model, new_model):
        old_model = str(old_model or "")
        new_model = str(new_model or "")
        model_index = self.cmb_ai_model.findData(new_model)
        if model_index < 0:
            model_index = 0
        if self.cmb_ai_model.currentIndex() != model_index:
            self.cmb_ai_model.blockSignals(True)
            self.cmb_ai_model.setCurrentIndex(model_index)
            self.cmb_ai_model.blockSignals(False)
        if self.settings_window is not None and self.settings_window.cmb_ai_model.currentIndex() != model_index:
            self.settings_window.cmb_ai_model.blockSignals(True)
            self.settings_window.cmb_ai_model.setCurrentIndex(model_index)
            self.settings_window.cmb_ai_model.blockSignals(False)
            self.settings_window.update_translate_summary()
        if self.btn_ai_mode.isChecked():
            old_index = self.cmb_ai_model.findData(old_model)
            old_label = self.cmb_ai_model.itemText(old_index) if old_index >= 0 else old_model
            new_label = self.cmb_ai_model.itemText(model_index) if model_index >= 0 else new_model
            self.lbl_status.setText(f"AI模型自動切換：{old_label} -> {new_label}")
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
                self.settings_window.set_translate_mode(False)
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
            self.schedule_save_settings()
            return
        self.worker.set_gemma_enabled(checked)
        if self.settings_window is not None:
            self.settings_window.set_translate_mode(checked)
        if checked:
            self.lbl_status.setText(f"AI模型: {self.cmb_ai_model.currentText()}")
        self.schedule_save_settings()

    def set_scan_mode(self, scan_mode):
        self.scan_mode = scan_mode
        self.worker.set_scan_mode(scan_mode)
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_side,
            self.region_relief_font_pt,
            RELIEF_BUBBLE_OPACITY,
            self.region_relief_gap_px,
            self.selected_region,
        )
        if scan_mode == SCAN_MODE_FULLSCREEN:
            self.region_frame.clear_region()
        elif self.selected_region:
            self.region_frame.set_theme_mode(self.theme_mode)
            self.region_frame.set_frame_opacity(self.region_frame_opacity)
            self.region_frame.show_region(self.selected_region)
        else:
            self.region_frame.clear_region()
        self.refresh_overlay_from_last_results()
        self.schedule_save_settings()

    def activate_region_translation(self):
        self.begin_region_selection()

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
            self.selected_region = None
            self.worker.set_scan_region(None)
            self.btn_mode_full.setChecked(True)
            self.set_scan_mode(SCAN_MODE_FULLSCREEN)
            return
        self.selected_region = rect
        self.worker.set_scan_region(rect)
        self.btn_mode_region.setChecked(True)
        self.set_scan_mode(SCAN_MODE_REGION)
        x, y, w, h = rect
        self.lbl_status.setText(f"框選區域已設定：{w}x{h}")
        self.refresh_overlay_from_last_results()
        self.schedule_save_settings()

    def on_region_frame_changed(self, rect):
        if not rect:
            return
        self.selected_region = rect
        self.worker.set_scan_region(rect)
        if self.scan_mode == SCAN_MODE_REGION:
            self.region_frame.set_theme_mode(self.theme_mode)
            self.region_frame.set_frame_opacity(self.region_frame_opacity)
            self.region_frame.show_region(rect)
        self.refresh_overlay_from_last_results()
        self.schedule_save_settings()

    def refresh_overlay_from_last_results(self):
        if not self.last_scan_results:
            return
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_side,
            self.region_relief_font_pt,
            RELIEF_BUBBLE_OPACITY,
            self.region_relief_gap_px,
            self.selected_region,
        )
        self.overlay.update_bubbles(self.last_scan_results)
        self.overlay.raise_()

    def toggle_settings_window(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindowRevamp(self)
        if self.settings_window.isVisible():
            self.settings_window.hide()
        else:
            self.settings_window.show()
            self.settings_window.resize(800, 1000)
            try:
                screen = QApplication.primaryScreen().availableGeometry()
                x = screen.left() + max(0, (screen.width() - self.settings_window.width()) // 2)
                y = screen.top() + max(0, (screen.height() - self.settings_window.height()) // 2)
                self.settings_window.move(x, y)
            except Exception:
                pass
            try:
                self.settings_window.sync_from_controller()
                self.settings_window.update_theme(self.theme_mode)
            except Exception as exc:
                self.log_ui_error("settings_window_sync", exc)
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            QTimer.singleShot(0, self.settings_window.raise_)
            QTimer.singleShot(0, self.settings_window.activateWindow)

    def log_ui_error(self, context, exc):
        try:
            log_path = os.path.join(os.path.dirname(__file__), "cloudhime_ui_errors.log")
            with open(log_path, "a", encoding="utf-8") as fp:
                fp.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}: {exc}\n")
                fp.write(traceback.format_exc())
                fp.write("\n")
        except Exception:
            pass

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
        self.worker.last_auto_threshold_refresh_ms = 0.0
        self.trigger_scan_sequence()
        self.btn_now.setEnabled(False)
        self.btn_now.setText("⚡ 充電中 0%")
        self.btn_now.set_cooldown_progress(0)
        self.cooldown_end_time = time.monotonic() + (self.cooldown_total_ms / 1000.0)
        self.cooldown_progress_timer.start()
        self.cooldown_timer.start(self.cooldown_total_ms)
        self.lbl_status.setText("⚡ 冷卻充電中...")

    def reset_immediate_btn(self):
        self.cooldown_progress_timer.stop()
        self.btn_now.set_cooldown_progress(0)
        self.cooldown_end_time = 0.0
        self.btn_now.setEnabled(True)
        self.btn_now.setText("⚡ 立即 (~)")
        self.lbl_status.setText("✅ 已就緒")

    def update_cooldown_progress(self):
        if self.cooldown_end_time <= 0:
            self.cooldown_progress_timer.stop()
            return
        remaining = max(0.0, self.cooldown_end_time - time.monotonic())
        progress = int(round((1.0 - (remaining / (self.cooldown_total_ms / 1000.0))) * 100))
        progress = max(0, min(100, progress))
        self.btn_now.set_cooldown_progress(progress)
        self.btn_now.setText(f"⚡ 充電中 {progress}%")
        self.lbl_status.setText("⚡ 冷卻充電中...")

    def start_auto_scan(self, checked=False, base_interval=None):
        if self.scan_mode == SCAN_MODE_REGION and not self.selected_region:
            self.lbl_status.setText("請先設定框選區域")
            self.begin_region_selection()
            return
        if base_interval is None:
            base_interval = max(1000, int(self.random_scan_center_seconds) * 1000)
        self.current_auto_interval = base_interval
        self.lbl_status.setText(f"{self.get_random_scan_button_text()}自動掃描中")
        self.schedule_next_scan()

    def schedule_next_scan(self):
        if self.current_auto_interval == 0:
            return
        if self.current_auto_interval == 5000:
            delay = 5000
        else:
            delay = self.get_random_scan_delay_ms()
        self.auto_timer.start(delay)
        self.countdown_seconds = delay // 1000
        self.update_countdown_label()
        self.display_timer.start()

    def update_countdown_label(self):
        if self.current_auto_interval == 0: 
            self.display_timer.stop()
            return
        self.countdown_seconds -= 1
        if self.countdown_seconds < 0:
            self.display_timer.stop()

    def on_scan_complete(self, results):
        self.last_scan_results = list(results) if results else []
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_side,
            self.region_relief_font_pt,
            RELIEF_BUBBLE_OPACITY,
            self.region_relief_gap_px,
            self.selected_region,
        )
        self.overlay.update_bubbles(results)
        self.overlay.raise_()
        if self.current_auto_interval > 0:
            self.schedule_next_scan()

    def stop_scan(self):
        self.current_auto_interval = 0
        self.auto_timer.stop()
        self.display_timer.stop()
        self.auto_group.setExclusive(False)
        self.btn_30.setChecked(False)
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
            selected_model = self.worker.normalize_gemma_model(self.worker.gemma_model)
            current_index = self.cmb_ai_model.findData(selected_model)
            current_label = self.cmb_ai_model.itemText(current_index) if current_index >= 0 else selected_model
            used = len(self.worker.gemma_call_timestamps.get(selected_model, []))
            limit = self.worker.get_gemma_model_call_limit(selected_model)
            progress = int(round((used / limit) * 100)) if limit else 0
            progress = max(0, min(100, progress))
            backup_model = self.worker.get_other_gemma_model(selected_model)
            backup_index = self.cmb_ai_model.findData(backup_model)
            backup_label = self.cmb_ai_model.itemText(backup_index) if backup_index >= 0 else backup_model
            backup_used = len(self.worker.gemma_call_timestamps.get(backup_model, []))
            backup_limit = self.worker.get_gemma_model_call_limit(backup_model)
            backup_ready = self.worker.gemma_auto_switch_enabled and used >= limit and backup_used < backup_limit
            theme = resolve_theme(self.theme_mode)
            if used >= limit and backup_ready:
                colors = build_charge_bar_colors(theme, "warning")
                self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
                self.charge_bar.set_progress(100, f"{current_label} {used}/{limit} -> {backup_label} {backup_used}/{backup_limit}")
                self.lbl_status.setText(f"{current_label} 已滿，下一次會自動切到 {backup_label}")
                return
            if used >= limit:
                colors = build_charge_bar_colors(theme, "danger")
                self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
                self.charge_bar.set_progress(100, f"{current_label} {used}/{limit}")
                self.lbl_status.setText(f"{current_label} 已滿 {limit}/{limit}，先改用 Google")
                return
            if used >= 10:
                colors = build_charge_bar_colors(theme, "warning")
            else:
                colors = build_charge_bar_colors(theme, "normal")
            self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
            self.charge_bar.set_progress(progress, f"{current_label} {used}/{limit}")
        else:
            colors = build_charge_bar_colors(resolve_theme(self.theme_mode), "off")
            self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
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
        self.set_theme_mode("dark" if not self.is_dark_mode else "light")

    def set_theme_mode(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.theme_mode = theme.key
        self.is_dark_mode = theme.key != "light"
        self.update_frame_style()
        self.selection_overlay.set_theme_mode(theme.key)
        self.overlay.set_theme_mode(theme.key)
        self.region_frame.set_theme_mode(theme.key)
        if self.settings_window is not None:
            self.settings_window.update_theme(theme.key)
        self.refresh_overlay_from_last_results()
        self.schedule_save_settings()

    def update_frame_style(self):
        theme = resolve_theme(self.theme_mode)
        self.frame.setStyleSheet(theme.window_qss(radius=15, border_width=2))
        self.lbl_title.setStyleSheet(f"color: {theme.text}; font-weight: bold; background: transparent; border: none;")
        self.lbl_status.setStyleSheet(f"color: {theme.text}; background-color: {theme.card_bg}; border: 1px solid {theme.border}; border-radius: 4px;")
        self.input_api_key.setStyleSheet(f"background-color: {theme.card_bg}; color: {theme.text}; border: 1px solid {theme.border}; border-radius: 6px; padding: 6px;")
        self.cmb_ai_model.setStyleSheet(theme.combo_qss(radius=6))

        self.btn_now.set_theme_colors(
            theme.control_bg,
            theme.text,
            theme.border,
            theme.control_hover,
            theme.control_checked,
            theme.control_disabled_bg,
            theme.control_disabled_fg,
        )

        auto_btn_style = theme.button_qss("toggle")
        self.btn_30.setStyleSheet(auto_btn_style)
        self.btn_ai_mode.setStyleSheet(auto_btn_style)
        self.btn_mode_full.setStyleSheet(auto_btn_style)
        self.btn_mode_region.setStyleSheet(auto_btn_style)

        self.btn_stop.setStyleSheet(theme.button_qss("toggle"))
        self.btn_theme.setText("⚙")
        self.btn_theme.setStyleSheet(f"QPushButton {{ background-color: transparent; color: {theme.accent}; border: none; font-size: 18px; }} QPushButton:hover {{ background-color: {theme.accent_soft}; border-radius: 15px; }}")
        if self.settings_window is not None:
            self.settings_window.update_theme(theme.key)
            self.settings_window.sync_from_controller()
        self.region_frame.set_theme_mode(theme.key)

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
