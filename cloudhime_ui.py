# ==========================================
# 🌟 雲朵翻譯姬 v3.0 - 螢幕 OCR 即時翻譯工具 (邏輯修正版) (｀・ω・´)ゞ
# ==========================================
# 核心引擎: Windows OCR 優先、可選 OCR 後端
# 翻譯引擎: Google + Gemma (多模態支援)
# 架構優化: 移除多餘引用，清理過期的 Argos 備援邏輯
# ==========================================

import os
import sys
from cloudhime_logging import logger
import ctypes
import ctypes.wintypes
import hashlib
import difflib
import random
import re
import json
import time
import traceback
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import request, error
import numpy as np
import cv2
import mss

# Windows API 相關
import win32con 

# 繁簡轉換
try:
    from opencc import OpenCC
    OPENCC_AVAILABLE = True
except ImportError:
    OPENCC_AVAILABLE = False
    logger.error("⚠️ 未安裝 opencc。")

from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,QApplication, QWidget, QLabel, QVBoxLayout, QMessageBox, QFileDialog,
                               QPushButton, QFrame, QHBoxLayout, QButtonGroup,
                               QSlider, QLineEdit, QCheckBox, QComboBox, QPlainTextEdit,
                               QSpinBox, QSizePolicy, QSplitter, QScrollArea,
                               QGraphicsOpacityEffect,
                               QGridLayout)
from PySide6.QtCore import (Qt, QTimer, Signal, QThread, QObject, 
                            QAbstractNativeEventFilter, QEvent)
from PySide6.QtGui import QCursor, QFontMetrics, QIcon, QPixmap, QColor, QPainter, QFont, QBrush, QFontDatabase
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
from ocr_backends import discover_backends
from ocr_quality import (
    score_ocr_items as quality_score_ocr_items,
    summarize_threshold_candidate as quality_summarize_threshold_candidate,
)
from ocr_backend_installer import detect_backend_state
from ocr_refinement import (
    normalize_translation_compare_text,
    should_fallback_to_text_translation,
    is_suspiciously_short_translation,
    score_ocr_candidate_text,
    choose_better_ocr_candidate,
    merge_google_lines_into_items
)
import translation_helpers as translation_tools
import localization
from translation_registry import TranslationProviderRegistry, TranslationProviderRegistryConfig
from translation_providers import GemmaTranslationProvider, GoogleTranslationProvider, LocalGemmaProvider
from settings_store import (
    appdata_companion_path,
    create_settings_paths,
    extract_backend_chain,
    load_settings_data,
    normalize_settings_payload,
    resolve_relief_offsets,
    resolve_region_opacity,
    resolve_ui_language,
    save_settings_data,
    should_migrate_to_appdata,
)
from ocr_backend_panel import OcrBackendSettingsPanel
from translation_settings_panel import TranslationSettingsPanel
# 防止高 DPI 縮放導致座標錯位
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
STARTUP_T0 = time.perf_counter()

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
SETTINGS_PATHS = create_settings_paths(os.path.dirname(__file__))
APPDATA_ENV_PATH = appdata_companion_path(SETTINGS_PATHS, ".env")
LEGACY_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
UI_ERROR_LOG_PATH = appdata_companion_path(SETTINGS_PATHS, "cloudhime_ui_errors.log")


def _read_api_key_from_env_files(env_paths) -> str:
    for env_path in env_paths:
        try:
            if not os.path.exists(env_path):
                continue
            with open(env_path, "r", encoding="utf-8") as env_file:
                for line in env_file:
                    if line.startswith(f"{API_KEY_ENV_VAR}="):
                        api_key = line.strip().split("=", 1)[1].strip()
                        if api_key:
                            return api_key
                        break
        except (OSError, UnicodeError) as exc:
            logger.warning("Failed to read API key file %s: %s", env_path, exc)
            continue
    return ""


MIN_BUBBLE_FONT_PT = 8
MIN_BUBBLE_WIDTH = 96
MIN_BUBBLE_HEIGHT = 42
SUPPORTED_AI_MODELS = [
    ("Gemma 3 1B", "gemma-3-1b-it"),
    ("Gemma 3 27B", "gemma-3-27b-it"),
    ("Gemma 4 31B", "gemma-4-31b-it"),
    ("Gemini 2.5 Pro", "gemini-2.5-pro"),
    ("TranslateGemma (Local)", "translategemma-4b-it-local"),
]
SUPPORTED_GEMMA_MODEL_NAMES = [model_name for _, model_name in SUPPORTED_AI_MODELS]
SCAN_MODE_FULLSCREEN = "fullscreen"
SCAN_MODE_REGION = "region"
REGION_RENDER_BUBBLE = "bubble"
REGION_RENDER_RELIEF = "relief"
REGION_RENDER_SCREENSHOT = "screenshot"

GOOGLE_BATCH_SIZE = 12
SMART_FULLSCREEN_MAX_REGIONS = 3
SMART_FULLSCREEN_MIN_AREA_RATIO = 0.015
SMART_FULLSCREEN_MAX_AREA_RATIO = 0.82
DEFAULT_AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES = 10
AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MIN = 1
AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MAX = 60
GEMMA_RATE_LIMIT_WINDOW_SEC = 60
GEMMA_RATE_LIMIT_MAX_CALLS = 15
RELIEF_BUBBLE_OPACITY = 40
RELIEF_MAX_OFFSET_PX = 500


def startup_log(stage, detail=""):
    elapsed_ms = (time.perf_counter() - STARTUP_T0) * 1000.0
    message = f"[Startup][{elapsed_ms:8.1f} ms] {stage}"
    if detail:
        message += f" | {detail}"
    logger.info(message)

# ==========================================
# 🛡️ 核心：Windows 原生熱鍵過濾器
# ==========================================
from cloudhime_core import is_valid_content, needs_cjk_tight_join, merge_horizontal_lines
from cloudhime_workers import OCRWorker

class GlobalHotKeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.hotkey_id = 101  # 自定義 ID
        self.is_registered = False
        self.registered_vk = None
        self.registered_label = None

    def register_hotkey(self, hwnd):
        if self.is_registered:
            return

        user32 = ctypes.windll.user32
        modifiers_no_repeat = 0x4000
        vk_candidates = [
            (0xC0, "~"),
            (0x78, "F9"),
            (0x77, "F8"),
        ]

        for vk, label in vk_candidates:
            success = user32.RegisterHotKey(
                int(hwnd),
                self.hotkey_id,
                modifiers_no_repeat,
                vk,
            )
            if success:
                self.is_registered = True
                self.registered_vk = vk
                self.registered_label = label
                logger.info(f"[Hotkey] Registered [{label}] successfully (HWND: {hwnd})")
                return

        for vk, label in vk_candidates:
            success = user32.RegisterHotKey(
                int(hwnd),
                self.hotkey_id,
                0,
                vk,
            )
            if success:
                self.is_registered = True
                self.registered_vk = vk
                self.registered_label = label
                logger.info(f"[Hotkey] Registered [{label}] without MOD_NOREPEAT (HWND: {hwnd})")
                return

        err = ctypes.GetLastError()
        logger.error(f"[Hotkey] Registration failed after fallbacks (Error: {err})")
        QMessageBox.warning(None, "熱鍵衝突", f"熱鍵註冊失敗 (Error: {err})\n可能與其他程式衝突！請關閉佔用該熱鍵的程式後重新啟動。")

    def unregister_hotkey(self, hwnd):
        if self.is_registered:
            ctypes.windll.user32.UnregisterHotKey(int(hwnd), self.hotkey_id)
            logger.info("[Hotkey] Unregistered.")
            logger.info("🛑 快捷鍵已解除註冊")
        self.is_registered = False
        self.registered_vk = None
        self.registered_label = None

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
# ==========================================
# 💬 氣泡與覆蓋層
# ==========================================
class TransBubble(QLabel):
    def __init__(self, parent, text, x, y, w, h, is_dark_mode=False, render_mode=REGION_RENDER_BUBBLE,
                 relief_offset_x=0, relief_offset_y=0, relief_font_pt=18, relief_opacity=40, region_rect=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.text_padding = 0
        self.source_rect = QRect(int(x), int(y), max(1, int(w)), max(1, int(h)))
        self.render_mode = render_mode if render_mode in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF, REGION_RENDER_SCREENSHOT) else REGION_RENDER_BUBBLE
        self.relief_offset_x = max(-RELIEF_MAX_OFFSET_PX, min(RELIEF_MAX_OFFSET_PX, int(relief_offset_x)))
        self.relief_offset_y = max(-RELIEF_MAX_OFFSET_PX, min(RELIEF_MAX_OFFSET_PX, int(relief_offset_y)))
        self.relief_font_pt = max(MIN_BUBBLE_FONT_PT, int(relief_font_pt))
        self.relief_opacity = max(0, min(100, int(relief_opacity)))
        # 浮雕模式定位用的掃描框（若有，以整體掃描大框為 anchor）
        self.region_rect = QRect(int(region_rect[0]), int(region_rect[1]), max(1, int(region_rect[2])), max(1, int(region_rect[3]))) if region_rect else None
        self.setText(text)
        self.set_theme(is_dark_mode)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(self.render_mode != REGION_RENDER_RELIEF)
        self.setMargin(self.text_padding)
        self.setMouseTracking(True)
        if self.render_mode == REGION_RENDER_RELIEF:
            bubble_rect, best_size = self.compute_relief_layout(text, x, y, w, h)
        elif self.render_mode == REGION_RENDER_SCREENSHOT:
            bubble_rect, best_size = self.compute_screenshot_layout(text, x, y, w, h)
        else:
            bubble_rect, best_size = self.compute_bubble_layout(text, x, y, w, h, tight=True)
        self.setFont(self._get_bubble_font(best_size))
        self.setGeometry(bubble_rect)
        self.show()

    def _get_bubble_font(self, size=None):
        parent = self.parentWidget()
        font = QFont(parent.font() if parent is not None else QApplication.font())
        font.setBold(True)
        if size is not None:
            font.setPointSizeF(float(size))
        return font

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
        font = self._get_bubble_font()
        # 扣掉 Padding，確保文字有足夠的內縮空間不會被截斷
        text_w = max(1, w - self.text_padding * 2)
        text_h = max(1, h - self.text_padding * 2)
        
        # Google Lens 風格：從氣泡高度推算起始字型大小 (1px ≈ 0.75pt)
        start_size = max(MIN_BUBBLE_FONT_PT, min(int(text_h * 0.75), 72))
        for size in range(start_size, MIN_BUBBLE_FONT_PT - 1, -1):
            font.setPointSizeF(float(size))
            if QFontMetrics(font).boundingRect(0, 0, text_w, 0, Qt.TextWordWrap, text).height() <= text_h:
                return float(size)
        return float(MIN_BUBBLE_FONT_PT)

    def measure_text_height(self, text, w, point_size):
        font = self._get_bubble_font(point_size)
        return QFontMetrics(font).boundingRect(
            0,
            0,
            max(1, w - self.text_padding * 2),
            0,
            Qt.TextWordWrap,
            text,
        ).height()

    def compute_bubble_layout(self, text, x, y, w, h, fixed_font_size=None, tight=False):
        parent_rect = self.parent().rect()
        extra_w = 2 if tight else 10
        extra_h = 2 if tight else 10
        base_w = max(MIN_BUBBLE_WIDTH, w + extra_w)
        base_h = max(MIN_BUBBLE_HEIGHT, h + extra_h)
        max_w_limit = 360 if tight else 460
        max_h_limit = 260 if tight else 320
        max_w = min(max(base_w, int(parent_rect.width() * (0.45 if tight else 0.55))), max(base_w, max_w_limit))
        max_h = min(max(base_h, int(parent_rect.height() * (0.25 if tight else 0.32))), max(base_h, max_h_limit))

        width_candidates = []
        width_scales = (1.0, 1.1, 1.25, 1.45, 1.75, 2.1) if tight else (1.0, 1.2, 1.45, 1.75, 2.1, 2.5, 3.0)
        for scale in width_scales:
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
        font_size = float(self.relief_font_pt)

        # 單行量測：用實際字型寬度決定氣泡大小，不換行
        font = self._get_bubble_font(font_size)
        fm = QFontMetrics(font)
        bubble_w = fm.horizontalAdvance(text) + self.text_padding * 2
        bubble_h = fm.height() + self.text_padding * 2
        bubble_w = max(bubble_w, max(MIN_BUBBLE_WIDTH, w))
        bubble_h = max(bubble_h, max(MIN_BUBBLE_HEIGHT, h))

        source_center_x = x + w / 2
        source_center_y = y + h / 2
        left = int(round(source_center_x - bubble_w / 2))
        top = int(round(source_center_y - bubble_h / 2))
        left = max(0, min(left, parent_rect.width() - bubble_w))
        top = max(0, min(top, parent_rect.height() - bubble_h))
        cand = QRect(left, top, bubble_w, bubble_h)
        cand.translate(self.relief_offset_x, self.relief_offset_y)
        cand = QRect(
            max(0, min(cand.x(), parent_rect.width() - cand.width())),
            max(0, min(cand.y(), parent_rect.height() - cand.height())),
            cand.width(),
            cand.height(),
        )
        return cand, font_size

    def compute_screenshot_layout(self, text, x, y, w, h):
        parent_rect = self.parent().rect()
        anchor = self.region_rect if self.region_rect is not None else QRect(int(x), int(y), max(1, int(w)), max(1, int(h)))
        base_rect, base_size = self.compute_bubble_layout(text, x, y, w, h)
        base_rect = QRect(base_rect)
        gap = max(14, min(RELIEF_MAX_OFFSET_PX, max(14, int(min(anchor.width(), anchor.height()) * 0.1))))

        candidates: list[QRect] = []
        centered_y = int(round(anchor.center().y() - base_rect.height() / 2))
        centered_x = int(round(anchor.center().x() - base_rect.width() / 2))
        candidates.append(QRect(anchor.right() + gap, centered_y, base_rect.width(), base_rect.height()))
        candidates.append(QRect(anchor.left() - gap - base_rect.width(), centered_y, base_rect.width(), base_rect.height()))
        candidates.append(QRect(centered_x, anchor.top() - gap - base_rect.height(), base_rect.width(), base_rect.height()))
        candidates.append(QRect(centered_x, anchor.bottom() + gap, base_rect.width(), base_rect.height()))

        best_rect = QRect(base_rect)
        best_score = None
        for cand in candidates:
            cand = QRect(
                max(0, min(cand.x(), parent_rect.width() - cand.width())),
                max(0, min(cand.y(), parent_rect.height() - cand.height())),
                cand.width(),
                cand.height(),
            )
            overlap = self._rect_overlap_area(cand, anchor)
            offscreen_penalty = 0
            if cand.left() <= 0 or cand.top() <= 0 or cand.right() >= parent_rect.right() or cand.bottom() >= parent_rect.bottom():
                offscreen_penalty = 2500
            distance = abs(cand.center().x() - anchor.center().x()) + abs(cand.center().y() - anchor.center().y())
            score = (overlap + offscreen_penalty, distance)
            if best_score is None or score < best_score:
                best_score = score
                best_rect = cand

        return best_rect, base_size

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
        self.relief_offset_x = 0
        self.relief_offset_y = 0
        self.relief_font_pt = 18
        self.relief_opacity = RELIEF_BUBBLE_OPACITY
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

    def set_render_context(self, scan_mode, render_mode, relief_offset_x=None, relief_offset_y=None, relief_font_pt=None, relief_opacity=None, scan_region=None):
        self.scan_mode = scan_mode if scan_mode in (SCAN_MODE_FULLSCREEN, SCAN_MODE_REGION) else SCAN_MODE_FULLSCREEN
        self.render_mode = render_mode if render_mode in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF, REGION_RENDER_SCREENSHOT) else REGION_RENDER_BUBBLE
        if relief_offset_x is not None:
            self.relief_offset_x = max(-RELIEF_MAX_OFFSET_PX, min(RELIEF_MAX_OFFSET_PX, int(relief_offset_x)))
        if relief_offset_y is not None:
            self.relief_offset_y = max(-RELIEF_MAX_OFFSET_PX, min(RELIEF_MAX_OFFSET_PX, int(relief_offset_y)))
        if relief_font_pt is not None:
            self.relief_font_pt = max(MIN_BUBBLE_FONT_PT, int(relief_font_pt))
        if relief_opacity is not None:
            self.relief_opacity = max(0, min(100, int(relief_opacity)))
        self.scan_region = scan_region if (scan_region and len(scan_region) == 4) else None

    def update_bubbles(self, results):
        self.clear_all()
        for t, x, y, w, h in results:
            mode = self.render_mode if self.scan_mode == SCAN_MODE_REGION else REGION_RENDER_BUBBLE
            # 框選 + 浮雕 / 截圖模式：把掃描框傳入，讓翻譯貼在框的外側
            region_rect = self.scan_region if (mode in (REGION_RENDER_RELIEF, REGION_RENDER_SCREENSHOT) and self.scan_mode == SCAN_MODE_REGION and self.scan_region) else None
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
                    self.relief_offset_x,
                    self.relief_offset_y,
                    self.relief_font_pt,
                    self.relief_opacity,
                    region_rect,
                )
            )
        if any(b.render_mode == REGION_RENDER_SCREENSHOT for b in self.bubbles):
            self.arrange_bubbles()
        self.setVisible(True)
        self.raise_()

    def clear_all(self):
        for b in self.bubbles:
            b.deleteLater()
        self.bubbles = []

    def update_translation_stream(self, index, partial_text, provider, x, y, w, h):
        if not self.isVisible():
            self.show()
            self.raise_()
        
        mode = self.render_mode if self.scan_mode == SCAN_MODE_REGION else 0 # fallback
        region_rect = self.scan_region if getattr(self, "scan_region", None) else None

        while len(self.bubbles) <= index:
            self.bubbles.append(TransBubble(self, "", x, y, w, h, self.theme_mode, mode, self.relief_offset_x, self.relief_offset_y, self.relief_font_pt, self.relief_opacity, region_rect))
            
        bubble = self.bubbles[index]
        bubble.setText(str(partial_text))
        bubble.source_rect = QRect(int(x), int(y), max(1, int(w)), max(1, int(h)))
        
        if mode == REGION_RENDER_RELIEF: # RELIEF
            if hasattr(bubble, 'compute_relief_layout'):
                bubble_rect, best_size = bubble.compute_relief_layout(partial_text, x, y, w, h)
            else:
                bubble_rect, best_size = bubble.compute_bubble_layout(partial_text, x, y, w, h, tight=True)
        elif mode == REGION_RENDER_SCREENSHOT: # SCREENSHOT
            if hasattr(bubble, 'compute_screenshot_layout'):
                bubble_rect, best_size = bubble.compute_screenshot_layout(partial_text, x, y, w, h)
            else:
                bubble_rect, best_size = bubble.compute_bubble_layout(partial_text, x, y, w, h, tight=True)
        else:
            bubble_rect, best_size = bubble.compute_bubble_layout(partial_text, x, y, w, h, tight=True)
            
        font = bubble.font()
        font.setPointSizeF(best_size)
        bubble.setFont(font)
        bubble.setGeometry(bubble_rect)
        bubble.repaint()

    def update_bubble_text_only(self, results):
        """串流更新：只更新現有氣泡的文字，不重建（打字機效果用）"""
        if not self.bubbles or not results:
            return
        for i, (t, x, y, w, h) in enumerate(results):
            if i < len(self.bubbles):
                bubble = self.bubbles[i]
                bubble.setText(str(t))
                bubble.repaint()
            else:
                # 氣泡數量不足時，補建新氣泡
                mode = self.render_mode if self.scan_mode == SCAN_MODE_REGION else REGION_RENDER_BUBBLE
                region_rect = self.scan_region if (mode in (REGION_RENDER_RELIEF, REGION_RENDER_SCREENSHOT) and self.scan_mode == SCAN_MODE_REGION and self.scan_region) else None
                self.bubbles.append(TransBubble(self, t, x, y, w, h, self.theme_mode, mode, self.relief_offset_x, self.relief_offset_y, self.relief_font_pt, self.relief_opacity, region_rect))

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
        if all(b.render_mode == REGION_RENDER_SCREENSHOT for b in self.bubbles):
            return
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
        self.region_pass_through = False
        self.hide()

    def set_region_pass_through(self, pass_through):
        self.region_pass_through = bool(pass_through)
        flags = self.windowFlags()
        if self.region_pass_through:
            flags |= Qt.WindowTransparentForInput
        else:
            flags &= ~Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        if self.isVisible():
            self.show()

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

    def _parse_color(self, c_str):
        c_str = str(c_str).strip()
        if c_str.startswith("rgba("):
            try:
                parts = c_str.replace("rgba(", "").replace(")", "").split(",")
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                a = int(float(parts[3])) if len(parts) > 3 else 255
                return QColor(r, g, b, a)
            except:
                pass
        return QColor(c_str)

    def set_theme_colors(self, base_bg, base_fg, border_color, hover_bg, fill_color, disabled_bg, disabled_fg):
        self.base_bg = self._parse_color(base_bg)
        self.base_fg = self._parse_color(base_fg)
        self.border_color = self._parse_color(border_color)
        self.hover_bg = self._parse_color(hover_bg)
        self.fill_color = self._parse_color(fill_color)
        self.disabled_bg = self._parse_color(disabled_bg)
        self.disabled_fg = self._parse_color(disabled_fg)
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
        self.indeterminate = False
        self.indeterminate_offset = 0
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._update_animation)
        self.setFixedHeight(18)

    def _update_animation(self):
        self.indeterminate_offset = (self.indeterminate_offset + 5) % 100
        self.update()

    def set_indeterminate(self, is_indeterminate, label=""):
        self.indeterminate = is_indeterminate
        if label:
            self.label = label
        if self.indeterminate:
            if not self._animation_timer.isActive():
                self._animation_timer.start(30)
        else:
            self._animation_timer.stop()
        self.update()

    def _parse_color(self, c_str):
        c_str = str(c_str).strip()
        if c_str.startswith("rgba("):
            try:
                parts = c_str.replace("rgba(", "").replace(")", "").split(",")
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                a = int(float(parts[3])) if len(parts) > 3 else 255
                return QColor(r, g, b, a)
            except:
                pass
        return QColor(c_str)

    def set_theme_colors(self, base_bg, border_color, fill_color, text_color):
        self.base_bg = self._parse_color(base_bg)
        self.border_color = self._parse_color(border_color)
        self.fill_color = self._parse_color(fill_color)
        self.text_color = self._parse_color(text_color)
        self.update()

    def set_progress(self, progress, label=""):
        if getattr(self, "indeterminate", False):
            self.set_indeterminate(False)
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

        if getattr(self, "indeterminate", False):
            bar_width = int(rect.width() * 0.3)
            import math
            pos = (math.sin(self.indeterminate_offset / 100.0 * math.pi * 2) + 1) / 2.0
            x = rect.left() + int((rect.width() - bar_width) * pos)
            fill_rect = QRect(x, rect.top(), bar_width, rect.height())
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.fill_color)
            painter.drawRoundedRect(fill_rect, 8, 8)
        else:
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
        self.setWindowTitle(translation_tools.ui_text(self.controller, "settings_title"))
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
        self.spin_random_scan_center.setRange(1, 300)
        self.spin_random_scan_center.setSuffix(" 秒")
        self.spin_random_scan_center.valueChanged.connect(self.on_random_scan_settings_changed)
        center_row.addWidget(self.spin_random_scan_center)
        auto_scan_layout.addLayout(center_row)
        self.slider_random_scan_center = QSlider(Qt.Horizontal)
        self.slider_random_scan_center.setRange(1, 300)
        self.slider_random_scan_center.setTickPosition(QSlider.TicksBelow)
        self.slider_random_scan_center.setTickInterval(60)
        self.slider_random_scan_center.valueChanged.connect(self.spin_random_scan_center.setValue)
        auto_scan_layout.addWidget(self.slider_random_scan_center)

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
        self.slider_random_scan_jitter = QSlider(Qt.Horizontal)
        self.slider_random_scan_jitter.setRange(0, 100)
        self.slider_random_scan_jitter.setTickPosition(QSlider.TicksBelow)
        self.slider_random_scan_jitter.setTickInterval(25)
        self.slider_random_scan_jitter.valueChanged.connect(self.spin_random_scan_jitter.setValue)
        auto_scan_layout.addWidget(self.slider_random_scan_jitter)

        threshold_row = QHBoxLayout()
        self.lbl_auto_threshold_refresh = QLabel("閥值刷新")
        threshold_row.addWidget(self.lbl_auto_threshold_refresh)
        threshold_row.addStretch()
        self.spin_auto_threshold_refresh_minutes = QSpinBox()
        self.spin_auto_threshold_refresh_minutes.setRange(
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MIN,
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MAX,
        )
        self.spin_auto_threshold_refresh_minutes.setSuffix(" 分鐘")
        self.spin_auto_threshold_refresh_minutes.valueChanged.connect(self.on_auto_threshold_refresh_changed)
        threshold_row.addWidget(self.spin_auto_threshold_refresh_minutes)
        auto_scan_layout.addLayout(threshold_row)
        self.slider_auto_threshold_refresh = QSlider(Qt.Horizontal)
        self.slider_auto_threshold_refresh.setRange(
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MIN,
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MAX,
        )
        self.slider_auto_threshold_refresh.setTickPosition(QSlider.TicksBelow)
        self.slider_auto_threshold_refresh.setTickInterval(5)
        self.slider_auto_threshold_refresh.valueChanged.connect(self.spin_auto_threshold_refresh_minutes.setValue)
        auto_scan_layout.addWidget(self.slider_auto_threshold_refresh)

        self.lbl_random_scan_summary = QLabel("目前：10s 附近 · 約 8 ~ 12 秒")
        self.lbl_random_scan_summary.setWordWrap(True)
        auto_scan_layout.addWidget(self.lbl_random_scan_summary)
        self.lbl_auto_threshold_refresh_summary = QLabel("狀態：每 10 分鐘重新評估一次閥值")
        self.lbl_auto_threshold_refresh_summary.setWordWrap(True)
        auto_scan_layout.addWidget(self.lbl_auto_threshold_refresh_summary)
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
        self.cmb_region_render_mode.addItem("截圖模式", REGION_RENDER_SCREENSHOT)
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
        self.lbl_relief_hint = QLabel("只在浮雕模式啟用，X 與 Y 為 0 會對齊原位")
        self.lbl_relief_hint.setWordWrap(True)
        relief_layout.addWidget(self.lbl_relief)
        relief_layout.addWidget(self.lbl_relief_hint)

        offset_x_row = QHBoxLayout()
        self.lbl_relief_offset_x = QLabel("X 軸位移")
        offset_x_row.addWidget(self.lbl_relief_offset_x)
        self.slider_relief_offset_x = QSlider(Qt.Horizontal)
        self.slider_relief_offset_x.setRange(-RELIEF_MAX_OFFSET_PX, RELIEF_MAX_OFFSET_PX)
        self.slider_relief_offset_x.valueChanged.connect(self.on_relief_setting_changed)
        offset_x_row.addWidget(self.slider_relief_offset_x)
        self.lbl_relief_offset_x_value = QLabel("+0 px")
        self.lbl_relief_offset_x_value.setFixedWidth(58)
        self.lbl_relief_offset_x_value.setAlignment(Qt.AlignCenter)
        offset_x_row.addWidget(self.lbl_relief_offset_x_value)
        relief_layout.addLayout(offset_x_row)

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

        offset_y_row = QHBoxLayout()
        self.lbl_relief_offset_y = QLabel("Y 軸位移")
        offset_y_row.addWidget(self.lbl_relief_offset_y)
        self.slider_relief_offset_y = QSlider(Qt.Horizontal)
        self.slider_relief_offset_y.setRange(-RELIEF_MAX_OFFSET_PX, RELIEF_MAX_OFFSET_PX)
        self.slider_relief_offset_y.valueChanged.connect(self.on_relief_setting_changed)
        offset_y_row.addWidget(self.slider_relief_offset_y)
        self.lbl_relief_offset_y_value = QLabel("+0 px")
        self.lbl_relief_offset_y_value.setFixedWidth(58)
        self.lbl_relief_offset_y_value.setAlignment(Qt.AlignCenter)
        offset_y_row.addWidget(self.lbl_relief_offset_y_value)
        relief_layout.addLayout(offset_y_row)

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
        self._ai_requested = bool(use_ai)
        self.controller.toggle_ai_translation(use_ai)
        self.sync_from_controller()

    def on_api_key_text_changed(self, text):
        self.controller.on_api_key_changed(text)
        if text.strip() and self._ai_requested and not getattr(self.controller.worker, "use_gemma_translation", False):
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

    def on_auto_threshold_refresh_changed(self, *_):
        self.controller.set_auto_threshold_refresh_minutes(self.spin_auto_threshold_refresh_minutes.value())
        self.update_auto_threshold_refresh_summary()

    def on_region_render_mode_clicked(self, mode):
        self.controller.on_region_render_mode_changed(mode)
        self.update_region_render_summary()

    def on_relief_setting_changed(self, *_):
        self.controller.on_region_relief_settings_changed(
            self.slider_relief_offset_x.value(),
            self.slider_relief_offset_y.value(),
            self.spin_relief_font.value(),
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

    def update_auto_threshold_refresh_summary(self):
        minutes = max(1, int(self.spin_auto_threshold_refresh_minutes.value()))
        self.lbl_auto_threshold_refresh_summary.setText(f"狀態：每 {minutes} 分鐘重新評估一次閥值")

    def update_region_render_summary(self):
        mode = self.cmb_region_render_mode.itemData(self.cmb_region_render_mode.currentIndex())
        if mode == REGION_RENDER_RELIEF:
            self.lbl_region_render_summary.setText("狀態：浮雕功能 · 文字貼近原文")
            self.card_relief.setVisible(True)
        elif mode == REGION_RENDER_SCREENSHOT:
            self.lbl_region_render_summary.setText("狀態：截圖模式 · 整塊區域一起理解")
            self.card_relief.setVisible(False)
        else:
            self.lbl_region_render_summary.setText("狀態：氣泡功能 · 保留原本泡泡")
            self.card_relief.setVisible(False)
        self.adjustSize()

    def update_relief_summary(self):
        font_pt = int(self.spin_relief_font.value())
        offset_x = int(self.slider_relief_offset_x.value())
        offset_y = int(self.slider_relief_offset_y.value())
        opacity = int(self.slider_relief_opacity.value())
        self.lbl_relief_offset_x_value.setText(f"{offset_x:+d} px")
        self.lbl_relief_offset_y_value.setText(f"{offset_y:+d} px")
        self.lbl_relief_opacity_value.setText(f"{opacity}%")
        self.lbl_relief_summary.setText(f"狀態：{font_pt} pt · X {offset_x:+d}px · Y {offset_y:+d}px · {opacity}%")
    def update_translate_summary(self):
        use_ai = self.btn_translate_ai.isChecked()
        model_name = self.cmb_ai_model.currentText() if self.cmb_ai_model.count() else "Gemma"
        if use_ai:
            auto_state = "自動切換 ON" if self.chk_auto_switch.isChecked() else "自動切換 OFF"
            self.lbl_translate_summary.setText(f"狀態：AI 翻譯 · {model_name} · {auto_state}")
        else:
            self.lbl_translate_summary.setText("狀態：Google 翻譯 · 免 API KEY")

    def update_key_state(self, enabled):
        self.input_api_key.setEnabled(enabled)
        self.cmb_ai_model.setEnabled(enabled)
        self.chk_auto_switch.setEnabled(enabled)

    def sync_from_controller(self):
        self.chk_dark_mode.blockSignals(True)
        self.chk_dark_mode.setChecked(self.controller.is_dark_mode)
        self.chk_dark_mode.blockSignals(False)

        self.spin_random_scan_center.blockSignals(True)
        self.spin_random_scan_center.setValue(self.controller.random_scan_center_seconds)
        self.spin_random_scan_center.blockSignals(False)
        self.slider_random_scan_center.blockSignals(True)
        self.slider_random_scan_center.setValue(self.controller.random_scan_center_seconds)
        self.slider_random_scan_center.blockSignals(False)

        self.spin_random_scan_jitter.blockSignals(True)
        self.spin_random_scan_jitter.setValue(self.controller.random_scan_jitter_percent)
        self.spin_random_scan_jitter.blockSignals(False)
        self.slider_random_scan_jitter.blockSignals(True)
        self.slider_random_scan_jitter.setValue(self.controller.random_scan_jitter_percent)
        self.slider_random_scan_jitter.blockSignals(False)

        self.spin_auto_threshold_refresh_minutes.blockSignals(True)
        self.spin_auto_threshold_refresh_minutes.setValue(self.controller.auto_threshold_refresh_minutes)
        self.spin_auto_threshold_refresh_minutes.blockSignals(False)
        self.slider_auto_threshold_refresh.blockSignals(True)
        self.slider_auto_threshold_refresh.setValue(self.controller.auto_threshold_refresh_minutes)
        self.slider_auto_threshold_refresh.blockSignals(False)

        self.cmb_region_render_mode.blockSignals(True)
        if self.controller.region_render_mode == REGION_RENDER_RELIEF:
            render_index = 1
        elif self.controller.region_render_mode == REGION_RENDER_SCREENSHOT:
            render_index = 2
        else:
            render_index = 0
        self.cmb_region_render_mode.setCurrentIndex(render_index)
        self.cmb_region_render_mode.blockSignals(False)

        self.slider_relief_offset_x.blockSignals(True)
        self.slider_relief_offset_x.setValue(self.controller.region_relief_offset_x)
        self.slider_relief_offset_x.blockSignals(False)

        self.spin_relief_font.blockSignals(True)
        self.spin_relief_font.setValue(self.controller.region_relief_font_pt)
        self.spin_relief_font.blockSignals(False)

        self.slider_relief_offset_y.blockSignals(True)
        self.slider_relief_offset_y.setValue(self.controller.region_relief_offset_y)
        self.slider_relief_offset_y.blockSignals(False)

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
        ai_enabled = bool(getattr(self.controller.worker, "use_gemma_translation", False))
        if ai_enabled:
            self._ai_requested = True
        self.btn_translate_google.setChecked(not ai_enabled)
        self.btn_translate_ai.setChecked(ai_enabled)
        self.btn_translate_google.blockSignals(False)
        self.btn_translate_ai.blockSignals(False)
        self.set_translate_advanced_visible(bool(ai_enabled or self._ai_requested))
        self.update_translate_summary()
        self.update_random_scan_summary()
        self.update_auto_threshold_refresh_summary()
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
        import os
        is_dark = theme.key != "light"
        bg_image = "assets/bg_dark.jpg" if is_dark else "assets/bg_light.jpg"
        bg_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), bg_image)).replace("\\", "/")
        base_style = theme.window_qss(radius=20, border_width=2).strip().rstrip('}')
        style_with_bg = base_style + f" background-image: url({bg_image_path}); background-position: center; background-repeat: no-repeat; }}"
        self.frame.setStyleSheet(style_with_bg)
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
        self.lbl_relief_offset_x.setStyleSheet(f"color: {theme.text};")
        self.lbl_relief_font.setStyleSheet(f"color: {theme.text};")
        self.lbl_relief_offset_y.setStyleSheet(f"color: {theme.text};")
        self.lbl_relief_opacity.setStyleSheet(f"color: {theme.text};")
        self.lbl_relief_offset_y_value.setStyleSheet(f"color: {theme.accent}; font-weight: 700; background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 10px; padding: 4px 6px;")
        self.lbl_relief_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_relief_opacity_value.setStyleSheet(f"color: {theme.accent}; font-weight: 700; background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 10px; padding: 4px 6px;")
        self.lbl_translate.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {theme.text};")
        self.lbl_advanced_translate.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {theme.accent};")
        self.lbl_advanced_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_ocr_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_translate_hint.setStyleSheet(f"color: {theme.subtext};")
        self.lbl_random_scan_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_auto_threshold_refresh.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_auto_threshold_refresh_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_translate_summary.setStyleSheet(theme.pill_qss("accent"))
        spinbox_style = (
            f"QSpinBox {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 8px; padding: 3px 8px; }} "
            f"QSpinBox:focus {{ border: 2px solid {theme.accent}; }} "
            "QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }"
        )
        self.spin_auto_threshold_refresh_minutes.setStyleSheet(spinbox_style)
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
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("settingsWindowRevamp")
        self.old_pos = None
        self._ai_requested = False
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMinimumSize(1400, 780)
        self.resize(1422, 800)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        self.backdrop_panel = QFrame()
        self.backdrop_panel.setObjectName("settingsBackdropPanel")
        self.backdrop_panel.setAttribute(Qt.WA_StyledBackground, True)
        
        # Apple-style subtle drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 10)
        self.backdrop_panel.setGraphicsEffect(shadow)
        backdrop = QVBoxLayout(self.backdrop_panel)
        backdrop.setContentsMargins(0, 0, 0, 0)
        backdrop.setSpacing(12)

        self.top_panel = QWidget()
        self.top_panel.setObjectName("settingsTopPanel")
        self.top_panel.setAttribute(Qt.WA_StyledBackground, True)
        top = QVBoxLayout(self.top_panel)
        top.setContentsMargins(22, 18, 22, 8)
        top.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.btn_export_history = QPushButton("匯出翻譯歷史")
        self.btn_export_history.setObjectName("settingsNavBtn")
        self.btn_export_history.clicked.connect(self.export_history)
        top_row.addWidget(self.btn_export_history)
        self.lbl_brand_icon = QLabel("☁️")
        self.lbl_brand_icon.setFixedSize(40, 40)
        self.lbl_brand_icon.setAlignment(Qt.AlignCenter)
        top_row.addWidget(self.lbl_brand_icon)
        title_box = QHBoxLayout()
        title_box.setSpacing(18)
        self.lbl_page_title = QLabel("")
        self.lbl_page_subtitle = QLabel("")
        self.lbl_page_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.lbl_page_subtitle.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        title_box.addWidget(self.lbl_page_title)
        title_box.addWidget(self.lbl_page_subtitle)
        top_row.addLayout(title_box)
        top_row.addStretch()
        self.btn_close = QPushButton("✕")
        self.btn_close.setText("✕")
        self.btn_close.setFixedSize(36, 36)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.hide)
        top_row.addWidget(self.btn_close)
        top.addLayout(top_row)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(10)
        self.ocr_backend_panel = OcrBackendSettingsPanel(self.controller, self)
        self.ocr_backend_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ocr_backend_panel.setVisible(False)
        theme_chip = QWidget()
        theme_chip_layout = QHBoxLayout(theme_chip)
        theme_chip_layout.setContentsMargins(0, 0, 0, 0)
        theme_chip_layout.setSpacing(4)
        self.lbl_theme_mode = QLabel("🎨")
        self.lbl_theme_mode.setFixedWidth(24)
        self.lbl_theme_mode.setAlignment(Qt.AlignCenter)
        theme_chip_layout.addWidget(self.lbl_theme_mode)
        self.cmb_theme_mode_chip = QComboBox()
        self.cmb_theme_mode_chip.setCursor(Qt.PointingHandCursor)
        self.cmb_theme_mode_chip.setMinimumWidth(150)
        self.cmb_theme_mode_chip.currentIndexChanged.connect(self.on_theme_mode_changed)
        theme_chip_layout.addWidget(self.cmb_theme_mode_chip)
        chip_row.addWidget(theme_chip)

        language_chip = QWidget()
        language_chip_layout = QHBoxLayout(language_chip)
        language_chip_layout.setContentsMargins(0, 0, 0, 0)
        language_chip_layout.setSpacing(4)
        self.lbl_ui_language = QLabel("🌐")
        self.lbl_ui_language.setFixedWidth(24)
        self.lbl_ui_language.setAlignment(Qt.AlignCenter)
        language_chip_layout.addWidget(self.lbl_ui_language)
        self.cmb_ui_language_chip = QComboBox()
        self.cmb_ui_language_chip.setCursor(Qt.PointingHandCursor)
        self.cmb_ui_language_chip.setMinimumWidth(170)
        self.cmb_ui_language_chip.currentIndexChanged.connect(self.on_ui_language_changed)
        language_chip_layout.addWidget(self.cmb_ui_language_chip)
        chip_row.addWidget(language_chip)
        chip_row.addStretch()
        top.addLayout(chip_row)

        self.shell_panel = QFrame()
        self.shell_panel.setObjectName("settingsShellPanel")
        shell = QVBoxLayout(self.shell_panel)
        shell.setContentsMargins(22, 8, 22, 0)
        shell.setSpacing(0)

        self.frame = QFrame()
        shell.addWidget(self.frame)
        main = QVBoxLayout(self.frame)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        backdrop.addWidget(self.top_panel)
        backdrop.addWidget(self.shell_panel)
        root.addWidget(self.backdrop_panel)

        self.translation_panel = TranslationSettingsPanel(self.controller, SUPPORTED_AI_MODELS, self)
        self.translation_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.card_translate = self.translation_panel.card_translate
        self.lbl_translate = self.translation_panel.lbl_translate
        self.lbl_translate_hint = self.translation_panel.lbl_translate_hint
        self.lbl_translate_summary = self.translation_panel.lbl_translate_summary
        self.lbl_translate_mode = self.translation_panel.lbl_translate_mode
        self.btn_translate_google = self.translation_panel.btn_translate_google
        self.btn_translate_ai = self.translation_panel.btn_translate_ai
        self.lbl_api_key = self.translation_panel.lbl_api_key
        self.input_api_key = self.translation_panel.input_api_key
        self.lbl_ai_model = self.translation_panel.lbl_ai_model
        self.cmb_ai_model = self.translation_panel.cmb_ai_model
        self.lbl_gemma_prompt = self.translation_panel.lbl_gemma_prompt
        self.input_gemma_prompt = self.translation_panel.input_gemma_prompt
        self.chk_auto_switch = self.translation_panel.chk_auto_switch

        self.card_ocr = QFrame()
        ocr = QVBoxLayout(self.card_ocr)
        ocr.setContentsMargins(18, 10, 18, 10)
        ocr.setSpacing(4)
        ocr.setAlignment(Qt.AlignTop)
        self.lbl_ocr = QLabel("自動掃描")
        self.lbl_ocr_hint = QLabel("你可以隨意修改自動掃描的秒數以及偏移幅度")
        self.lbl_ocr_hint.setWordWrap(True)
        self.lbl_ocr_hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_ocr.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_ocr.setStyleSheet("background: transparent; border: none;")
        ocr.addWidget(self.lbl_ocr)
        ocr.addWidget(self.lbl_ocr_hint)
        ocr.addWidget(self.ocr_backend_panel)
        self.ocr_backend_panel.setVisible(True)
        
        self.chk_region_pass_through = QCheckBox("允許滑鼠穿透框選區 (點擊背景遊戲)")
        self.chk_region_pass_through.setChecked(getattr(self.controller, "region_pass_through", False))
        self.chk_region_pass_through.toggled.connect(self.controller.on_region_pass_through_changed)
        ocr.addWidget(self.chk_region_pass_through)

        self.auto_scan_panel = QWidget()
        self.lbl_auto_scan = QLabel("掃描設定")
        self.lbl_auto_scan_hint = QLabel("中心秒數與偏移幅度會同步到主畫面")
        ocr.addWidget(self.lbl_auto_scan)
        ocr.addWidget(self.lbl_auto_scan_hint)
        center_row = QHBoxLayout()
        center_row.setSpacing(8)
        self.lbl_random_scan_center = QLabel("中心秒數")
        center_row.addWidget(self.lbl_random_scan_center)
        center_row.addStretch()
        self.spin_random_scan_center = QSpinBox()
        self.spin_random_scan_center.setRange(1, 300)
        self.spin_random_scan_center.setSuffix(" 秒")
        self.spin_random_scan_center.valueChanged.connect(self.on_random_scan_settings_changed)
        center_row.addWidget(self.spin_random_scan_center)
        ocr.addLayout(center_row)
        self.slider_random_scan_center = QSlider(Qt.Horizontal)
        self.slider_random_scan_center.setRange(1, 300)
        self.slider_random_scan_center.setTickPosition(QSlider.TicksBelow)
        self.slider_random_scan_center.setTickInterval(60)
        self.slider_random_scan_center.valueChanged.connect(self.spin_random_scan_center.setValue)
        ocr.addWidget(self.slider_random_scan_center)
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
        ocr.addLayout(jitter_row)
        self.slider_random_scan_jitter = QSlider(Qt.Horizontal)
        self.slider_random_scan_jitter.setRange(0, 100)
        self.slider_random_scan_jitter.setTickPosition(QSlider.TicksBelow)
        self.slider_random_scan_jitter.setTickInterval(25)
        self.slider_random_scan_jitter.valueChanged.connect(self.spin_random_scan_jitter.setValue)
        ocr.addWidget(self.slider_random_scan_jitter)
        self.lbl_random_scan_summary = QLabel("狀態：10s 附近 · 約 8 ~ 12 秒")
        self.lbl_random_scan_summary.setWordWrap(False)
        self.lbl_random_scan_summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ocr.addWidget(self.lbl_random_scan_summary)
        threshold_row = QHBoxLayout()
        threshold_row.setSpacing(8)
        self.lbl_auto_threshold_refresh = QLabel("閥值刷新")
        threshold_row.addWidget(self.lbl_auto_threshold_refresh)
        threshold_row.addStretch()
        self.spin_auto_threshold_refresh_minutes = QSpinBox()
        self.spin_auto_threshold_refresh_minutes.setRange(
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MIN,
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MAX,
        )
        self.spin_auto_threshold_refresh_minutes.setSuffix(" 分鐘")
        self.spin_auto_threshold_refresh_minutes.valueChanged.connect(self.on_auto_threshold_refresh_changed)
        threshold_row.addWidget(self.spin_auto_threshold_refresh_minutes)
        ocr.addLayout(threshold_row)
        self.slider_auto_threshold_refresh = QSlider(Qt.Horizontal)
        self.slider_auto_threshold_refresh.setRange(
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MIN,
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MAX,
        )
        self.slider_auto_threshold_refresh.setTickPosition(QSlider.TicksBelow)
        self.slider_auto_threshold_refresh.setTickInterval(5)
        self.slider_auto_threshold_refresh.valueChanged.connect(self.spin_auto_threshold_refresh_minutes.setValue)
        ocr.addWidget(self.slider_auto_threshold_refresh)
        self.lbl_auto_threshold_refresh_summary = QLabel("狀態：每 10 分鐘重新評估一次閥值")
        self.lbl_auto_threshold_refresh_summary.setWordWrap(True)
        ocr.addWidget(self.lbl_auto_threshold_refresh_summary)

        self.card_region_render = QFrame()
        render = QVBoxLayout(self.card_region_render)
        render.setContentsMargins(18, 10, 18, 10)
        render.setSpacing(4)
        render.setAlignment(Qt.AlignTop)
        self.lbl_region_render = QLabel("文字模式")
        self.lbl_region_render_hint = QLabel("在框選模式下才會啟用，一共有三種文字顯示方式可以切換")
        self.lbl_region_render_hint.setWordWrap(True)
        self.lbl_region_render_hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_region_render.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_region_render.setStyleSheet("background: transparent; border: none;")
        render.addWidget(self.lbl_region_render)
        render.addWidget(self.lbl_region_render_hint)
        render_row = QHBoxLayout()
        render_row.setSpacing(8)
        self.lbl_region_render_mode = QLabel("顯示方式")
        self.lbl_region_render_mode.setStyleSheet("background: transparent; border: none; padding: 0px;")
        render_row.addWidget(self.lbl_region_render_mode)
        render_row.addStretch()
        self.render_mode_group = QButtonGroup(self)
        self.render_mode_group.setExclusive(True)
        self.btn_render_bubble = QPushButton("氣泡模式")
        self.btn_render_bubble.setCheckable(True)
        self.btn_render_bubble.setCursor(Qt.PointingHandCursor)
        self.btn_render_bubble.clicked.connect(lambda: self.on_region_render_mode_clicked(REGION_RENDER_BUBBLE))
        self.render_mode_group.addButton(self.btn_render_bubble)
        render_row.addWidget(self.btn_render_bubble)
        self.btn_render_relief = QPushButton("浮雕模式")
        self.btn_render_relief.setCheckable(True)
        self.btn_render_relief.setCursor(Qt.PointingHandCursor)
        self.btn_render_relief.clicked.connect(lambda: self.on_region_render_mode_clicked(REGION_RENDER_RELIEF))
        self.render_mode_group.addButton(self.btn_render_relief)
        render_row.addWidget(self.btn_render_relief)
        self.btn_render_screenshot = QPushButton("截圖模式")
        self.btn_render_screenshot.setCheckable(True)
        self.btn_render_screenshot.setCursor(Qt.PointingHandCursor)
        self.btn_render_screenshot.clicked.connect(lambda: self.on_region_render_mode_clicked(REGION_RENDER_SCREENSHOT))
        self.render_mode_group.addButton(self.btn_render_screenshot)
        render_row.addWidget(self.btn_render_screenshot)
        render.addLayout(render_row)
        self.lbl_region_render_summary = QLabel("狀態：氣泡模式")
        self.lbl_region_render_summary.setWordWrap(False)
        self.lbl_region_render_summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        render.addWidget(self.lbl_region_render_summary)

        self.input_screenshot_gemma_prompt = QPlainTextEdit()
        self.input_screenshot_gemma_prompt.setPlaceholderText("此為截圖模式專用的系統提示詞（選填）。\n如果不填，將使用預設的截圖翻譯指令。")
        self.input_screenshot_gemma_prompt.setTabChangesFocus(True)
        self.input_screenshot_gemma_prompt.setMinimumHeight(122)
        self.input_screenshot_gemma_prompt.textChanged.connect(self.controller.on_screenshot_gemma_prompt_changed)
        self.input_screenshot_gemma_prompt.setVisible(True)
        render.addWidget(self.input_screenshot_gemma_prompt)

        self.card_relief = QFrame()
        relief = QVBoxLayout(self.card_relief)
        relief.setContentsMargins(18, 10, 18, 10)
        relief.setSpacing(8)
        relief.setAlignment(Qt.AlignTop)
        self.lbl_relief = QLabel("浮雕細節")
        self.lbl_relief_hint = QLabel("只在浮雕模式才啟用，X 與 Y 為 0 會對齊原位")
        self.lbl_relief_hint.setWordWrap(True)
        self.lbl_relief_hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_relief.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_relief.setStyleSheet("background: transparent; border: none;")
        relief.addWidget(self.lbl_relief)
        relief.addWidget(self.lbl_relief_hint)

        offset_x_row = QHBoxLayout()
        self.lbl_relief_offset_x = QLabel("X 軸位移")
        self.lbl_relief_offset_x.setStyleSheet("background: transparent; border: none; padding: 0px;")
        offset_x_row.addWidget(self.lbl_relief_offset_x)
        self.lbl_relief_offset_x_value = QLabel("+0 px")
        offset_x_row.addWidget(self.lbl_relief_offset_x_value)
        offset_x_row.addStretch()
        self.slider_relief_offset_x = QSlider(Qt.Horizontal)
        self.slider_relief_offset_x.setRange(-RELIEF_MAX_OFFSET_PX, RELIEF_MAX_OFFSET_PX)
        self.slider_relief_offset_x.setFixedWidth(130)
        self.slider_relief_offset_x.valueChanged.connect(self.on_relief_setting_changed)
        offset_x_row.addWidget(self.slider_relief_offset_x)
        relief.addLayout(offset_x_row)

        font_row = QHBoxLayout()
        self.lbl_relief_font = QLabel("文字大小")
        self.lbl_relief_font.setStyleSheet("background: transparent; border: none; padding: 0px;")
        font_row.addWidget(self.lbl_relief_font)
        font_row.addStretch()
        self.spin_relief_font = QSpinBox()
        self.spin_relief_font.setRange(8, 48)
        self.spin_relief_font.valueChanged.connect(self.on_relief_setting_changed)
        font_row.addWidget(self.spin_relief_font)
        relief.addLayout(font_row)

        offset_y_row = QHBoxLayout()
        self.lbl_relief_offset_y = QLabel("Y 軸位移")
        self.lbl_relief_offset_y.setStyleSheet("background: transparent; border: none; padding: 0px;")
        offset_y_row.addWidget(self.lbl_relief_offset_y)
        self.lbl_relief_offset_y_value = QLabel("+0 px")
        offset_y_row.addWidget(self.lbl_relief_offset_y_value)
        offset_y_row.addStretch()
        self.slider_relief_offset_y = QSlider(Qt.Horizontal)
        self.slider_relief_offset_y.setRange(-RELIEF_MAX_OFFSET_PX, RELIEF_MAX_OFFSET_PX)
        self.slider_relief_offset_y.setFixedWidth(130)
        self.slider_relief_offset_y.valueChanged.connect(self.on_relief_setting_changed)
        offset_y_row.addWidget(self.slider_relief_offset_y)
        relief.addLayout(offset_y_row)

        opacity_row = QHBoxLayout()
        self.lbl_relief_opacity = QLabel("邊框透明度")
        self.lbl_relief_opacity.setStyleSheet("background: transparent; border: none; padding: 0px;")
        opacity_row.addWidget(self.lbl_relief_opacity)
        self.lbl_relief_opacity_value = QLabel("40%")
        opacity_row.addWidget(self.lbl_relief_opacity_value)
        opacity_row.addStretch()
        self.slider_relief_opacity = QSlider(Qt.Horizontal)
        self.slider_relief_opacity.setRange(0, 100)
        self.slider_relief_opacity.setFixedWidth(130)
        self.slider_relief_opacity.valueChanged.connect(self.on_relief_setting_changed)
        opacity_row.addWidget(self.slider_relief_opacity)
        relief.addLayout(opacity_row)
        self.lbl_relief_summary = QLabel("狀態：自動 · 18 pt · 選區框透明度 40%")
        self.lbl_relief_summary.setWordWrap(False)
        self.lbl_relief_summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        relief.addWidget(self.lbl_relief_summary)
        body = QWidget()
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        body_grid = QGridLayout(body)
        body_grid.setContentsMargins(0, 0, 0, 0)
        body_grid.setHorizontalSpacing(14)
        body_grid.setVerticalSpacing(14)
        body_grid.setColumnStretch(0, 1)
        body_grid.setColumnStretch(1, 1)
        body_grid.setColumnStretch(2, 1)
        body_grid.setColumnStretch(3, 1)
        body_grid.setRowStretch(0, 1)
        body_grid.setRowStretch(1, 1)

        self.card_translate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.card_ocr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.card_region_render.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.card_relief.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        body_grid.addWidget(self.translation_panel, 0, 0, 2, 1)
        body_grid.addWidget(self.card_ocr, 0, 1, 2, 1)
        body_grid.addWidget(self.card_region_render, 0, 2)
        body_grid.addWidget(self.card_relief, 1, 2)
        main.addWidget(body)

        footer = QWidget()
        footer.setObjectName("settingsFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 16, 0, 0)
        footer_layout.setSpacing(10)
        footer_layout.addStretch()
        self.btn_reset_defaults = QPushButton("↻")
        self.btn_reset_defaults.setCursor(Qt.PointingHandCursor)
        self.btn_reset_defaults.setMinimumWidth(170)
        self.btn_cancel = QPushButton("")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setMinimumWidth(110)
        self.btn_cancel.clicked.connect(self.hide)
        self.btn_save = QPushButton("✓")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setMinimumWidth(120)
        self.btn_save.clicked.connect(self.on_save_clicked)
        footer_layout.addWidget(self.btn_reset_defaults)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)
        main.addWidget(footer)

        self.auto_scan_panel.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.refresh_localized_texts()

    def on_translate_mode_clicked(self, use_ai):
        self.translation_panel.on_translate_mode_clicked(use_ai)

    def on_api_key_text_changed(self, text):
        self.translation_panel.on_api_key_text_changed(text)

    def on_ai_model_changed(self, index):
        self.translation_panel.on_ai_model_changed(index)

    def on_auto_switch_toggled(self, checked):
        self.translation_panel.on_auto_switch_toggled(checked)

    def on_gemma_prompt_changed(self):
        if hasattr(self.translation_panel, "on_gemma_prompt_changed"):
            self.translation_panel.on_gemma_prompt_changed()

    def set_translate_mode(self, use_ai):
        self.translation_panel.set_translate_mode(use_ai)

    def set_translate_advanced_visible(self, visible):
        self.translation_panel.set_translate_advanced_visible(visible)

    def on_random_scan_settings_changed(self, *_):
        self.controller.on_random_scan_settings_changed(self.spin_random_scan_center.value(), self.spin_random_scan_jitter.value())
        self.update_random_scan_summary()

    def on_auto_threshold_refresh_changed(self, *_):
        self.controller.set_auto_threshold_refresh_minutes(self.spin_auto_threshold_refresh_minutes.value())
        self.update_auto_threshold_refresh_summary()

    def on_region_render_mode_clicked(self, mode):
        self.controller.on_region_render_mode_changed(mode)
        self.update_region_render_summary()

    def on_relief_setting_changed(self, *_):
        self.controller.on_region_relief_settings_changed(
            self.slider_relief_offset_x.value(),
            self.slider_relief_offset_y.value(),
            self.spin_relief_font.value(),
            self.slider_relief_opacity.value(),
        )
        self.update_relief_summary()

    def _current_ui_language(self):
        return translation_tools.get_ui_language(self.controller)

    def _sync_theme_mode_combo(self):
        current_theme = getattr(self.controller, "theme_mode", "dark" if self.controller.is_dark_mode else "light")
        lang = self._current_ui_language()
        self.cmb_theme_mode_chip.blockSignals(True)
        self.cmb_theme_mode_chip.clear()
        for theme in ThemeRegistry.available():
            self.cmb_theme_mode_chip.addItem(translation_tools.theme_label(theme.key, lang), theme.key)
        index = self.cmb_theme_mode_chip.findData(current_theme)
        if index < 0:
            index = 0
        self.cmb_theme_mode_chip.setCurrentIndex(index)
        self.cmb_theme_mode_chip.blockSignals(False)

    def _sync_ui_language_combo(self):
        current_language = self._current_ui_language()
        self.cmb_ui_language_chip.blockSignals(True)
        self.cmb_ui_language_chip.clear()
        for label, code in translation_tools.ui_language_options(current_language):
            self.cmb_ui_language_chip.addItem(label, code)
        index = self.cmb_ui_language_chip.findData(current_language)
        if index < 0:
            index = 0
        self.cmb_ui_language_chip.setCurrentIndex(index)
        self.cmb_ui_language_chip.blockSignals(False)

    def refresh_localized_texts(self):
        lang = self._current_ui_language()
        self.setWindowTitle(translation_tools.ui_text(lang, "settings_title"))
        self.lbl_page_title.setText("CloudHime")
        self.lbl_page_subtitle.setText(translation_tools.ui_text(lang, "settings_subtitle"))
        self.btn_close.setToolTip(translation_tools.ui_text(lang, "settings_close"))
        self.btn_close.setText("✕")
        self.lbl_theme_mode.setText("🎨")
        self.lbl_theme_mode.setToolTip(translation_tools.ui_text(lang, "settings_theme_mode"))
        self.lbl_ui_language.setText("🌐")
        self.lbl_ui_language.setToolTip(translation_tools.ui_text(lang, "settings_ui_language"))
        self.btn_reset_defaults.setText(f"↻  {translation_tools.ui_text(lang, 'settings_reset_defaults')}")
        self.btn_cancel.setText(translation_tools.ui_text(lang, "settings_cancel"))
        self.btn_save.setText(f"✓  {translation_tools.ui_text(lang, 'settings_save')}")
        self.spin_random_scan_center.setSuffix(" sec" if lang == "en" else " 秒")
        self.spin_auto_threshold_refresh_minutes.setSuffix(" min" if lang == "en" else " 分鐘")
        self.lbl_ocr.setText(translation_tools.ui_text(lang, "settings_ocr_title"))
        self.lbl_ocr_hint.setText(translation_tools.ui_text(lang, "settings_ocr_hint"))
        self.chk_region_pass_through.setText(translation_tools.ui_text(lang, "settings_pass_through"))
        self.lbl_auto_scan.setText(translation_tools.ui_text(lang, "settings_auto_scan_title"))
        self.lbl_auto_scan_hint.setText(translation_tools.ui_text(lang, "settings_auto_scan_hint"))
        self.lbl_random_scan_center.setText(translation_tools.ui_text(lang, "settings_random_scan_center"))
        self.lbl_random_scan_jitter.setText(translation_tools.ui_text(lang, "settings_random_scan_jitter"))
        self.lbl_auto_threshold_refresh.setText(translation_tools.ui_text(lang, "settings_threshold_refresh"))
        self.lbl_region_render.setText(translation_tools.ui_text(lang, "settings_region_render_title"))
        self.lbl_region_render_hint.setText(translation_tools.ui_text(lang, "settings_region_render_hint"))
        self.lbl_region_render_mode.setText(translation_tools.ui_text(lang, "settings_region_render_mode"))
        self.btn_render_bubble.setText(translation_tools.ui_text(lang, "settings_render_bubble"))
        self.btn_render_relief.setText(translation_tools.ui_text(lang, "settings_render_relief"))
        self.btn_render_screenshot.setText(translation_tools.ui_text(lang, "settings_render_screenshot"))
        self.input_screenshot_gemma_prompt.setPlaceholderText(
            translation_tools.ui_text(lang, "settings_screenshot_prompt_placeholder")
        )
        self.lbl_relief.setText(translation_tools.ui_text(lang, "settings_relief_title"))
        self.lbl_relief_hint.setText(translation_tools.ui_text(lang, "settings_relief_hint"))
        self.lbl_relief_offset_x.setText(translation_tools.ui_text(lang, "settings_relief_offset_x"))
        self.lbl_relief_font.setText(translation_tools.ui_text(lang, "settings_relief_font"))
        self.lbl_relief_offset_y.setText(translation_tools.ui_text(lang, "settings_relief_offset_y"))
        self.lbl_relief_opacity.setText(translation_tools.ui_text(lang, "settings_relief_opacity"))
        self._sync_theme_mode_combo()
        self._sync_ui_language_combo()
        self.update_random_scan_summary()
        self.update_auto_threshold_refresh_summary()
        self.update_region_render_summary()
        self.update_relief_summary()

    def on_theme_mode_changed(self, index):
        combo = self.sender()
        if combo is None or not hasattr(combo, "itemData"):
            return
        theme_mode = combo.itemData(index)
        if not theme_mode:
            return
        self.controller.set_theme_mode(theme_mode)

    def on_ui_language_changed(self, index):
        combo = self.sender()
        if combo is None or not hasattr(combo, "itemData"):
            return
        language_code = combo.itemData(index)
        if not language_code:
            return
        if hasattr(self.controller, "set_ui_language"):
            self.controller.set_ui_language(language_code)
        else:
            self.controller.ui_language = localization.normalize_ui_language(language_code)
            self.refresh_localized_texts()

    def on_save_clicked(self):
        if hasattr(self.controller, "save_settings"):
            self.controller.save_settings()
        self.hide()

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)

    def set_translate_advanced_visible(self, visible):
        self.translation_panel.set_translate_advanced_visible(visible)

    def update_random_scan_summary(self):
        lang = self._current_ui_language()
        center = max(1, int(self.spin_random_scan_center.value()))
        jitter = max(0, int(self.spin_random_scan_jitter.value()))
        spread = max(0, int(round(center * jitter / 100.0)))
        low = max(1, center - spread)
        high = max(low, center + spread)
        self.lbl_random_scan_summary.setText(
            translation_tools.ui_text(lang, "settings_random_scan_summary").format(
                center=center,
                low=low,
                high=high,
            )
        )

    def update_auto_threshold_refresh_summary(self):
        lang = self._current_ui_language()
        minutes = max(1, int(self.spin_auto_threshold_refresh_minutes.value()))
        self.lbl_auto_threshold_refresh_summary.setText(
            translation_tools.ui_text(lang, "settings_auto_threshold_refresh_summary").format(minutes=minutes)
        )

    def update_region_render_summary(self):
        lang = self._current_ui_language()
        mode = self.controller.region_render_mode
        if mode == REGION_RENDER_RELIEF:
            self.lbl_region_render_summary.setText(
                translation_tools.ui_text(lang, "settings_region_render_summary_relief")
            )
            self.update_relief_state(True)
            self.input_screenshot_gemma_prompt.setVisible(True)
        elif mode == REGION_RENDER_SCREENSHOT:
            self.lbl_region_render_summary.setText(
                translation_tools.ui_text(lang, "settings_region_render_summary_screenshot")
            )
            self.update_relief_state(False)
            self.input_screenshot_gemma_prompt.setVisible(True)
        else:
            self.lbl_region_render_summary.setText(
                translation_tools.ui_text(lang, "settings_region_render_summary_bubble")
            )
            self.update_relief_state(False)
            self.input_screenshot_gemma_prompt.setVisible(True)

    def update_relief_summary(self):
        lang = self._current_ui_language()
        font_pt = int(self.spin_relief_font.value())
        offset_x = int(self.slider_relief_offset_x.value())
        offset_y = int(self.slider_relief_offset_y.value())
        opacity = int(self.slider_relief_opacity.value())
        self.lbl_relief_offset_x_value.setText(f"{offset_x:+d} px")
        self.lbl_relief_offset_y_value.setText(f"{offset_y:+d} px")
        self.lbl_relief_opacity_value.setText(f"{opacity}%")
        self.lbl_relief_summary.setText(
            translation_tools.ui_text(lang, "settings_relief_summary").format(
                font_pt=font_pt,
                offset_x=offset_x,
                offset_y=offset_y,
                opacity=opacity,
            )
        )

    def update_translate_summary(self):
        self.translation_panel.update_translate_summary()

    def update_key_state(self, enabled):
        self.translation_panel.update_key_state(enabled)

    def update_relief_state(self, enabled):
        self.card_relief.setEnabled(enabled)
        self.slider_relief_offset_x.setEnabled(enabled)
        self.spin_relief_font.setEnabled(enabled)
        self.slider_relief_offset_y.setEnabled(enabled)
        self.slider_relief_opacity.setEnabled(enabled)
        effect = None
        if not enabled:
            effect = QGraphicsOpacityEffect(self.card_relief)
            effect.setOpacity(0.45)
        self.card_relief.setGraphicsEffect(effect)

    def sync_from_controller(self):
        theme_mode = getattr(self.controller, "theme_mode", "dark" if self.controller.is_dark_mode else "light")
        self.refresh_localized_texts()
        ocr_backend_panel = getattr(self, "ocr_backend_panel", None)
        if ocr_backend_panel is not None:
            ocr_backend_panel.sync_from_controller()
        self.spin_random_scan_center.blockSignals(True)
        self.spin_random_scan_center.setValue(self.controller.random_scan_center_seconds)
        self.spin_random_scan_center.blockSignals(False)
        self.spin_random_scan_jitter.blockSignals(True)
        self.spin_random_scan_jitter.setValue(self.controller.random_scan_jitter_percent)
        self.spin_random_scan_jitter.blockSignals(False)
        self.spin_auto_threshold_refresh_minutes.blockSignals(True)
        self.spin_auto_threshold_refresh_minutes.setValue(self.controller.auto_threshold_refresh_minutes)
        self.spin_auto_threshold_refresh_minutes.blockSignals(False)
        self.slider_relief_offset_x.blockSignals(True)
        self.slider_relief_offset_x.setValue(self.controller.region_relief_offset_x)
        self.slider_relief_offset_x.blockSignals(False)
        self.spin_relief_font.blockSignals(True)
        self.spin_relief_font.setValue(self.controller.region_relief_font_pt)
        self.spin_relief_font.blockSignals(False)
        self.slider_relief_offset_y.blockSignals(True)
        self.slider_relief_offset_y.setValue(self.controller.region_relief_offset_y)
        self.slider_relief_offset_y.blockSignals(False)
        self.slider_relief_opacity.blockSignals(True)
        self.slider_relief_opacity.setValue(self.controller.region_frame_opacity)
        self.slider_relief_opacity.blockSignals(False)
        self.input_screenshot_gemma_prompt.blockSignals(True)
        screenshot_prompt = (
            getattr(self.controller, "screenshot_gemma_prompt", "")
            or self.controller.get_default_screenshot_gemma_prompt()
        )
        self.input_screenshot_gemma_prompt.setPlainText(screenshot_prompt)
        self.input_screenshot_gemma_prompt.blockSignals(False)
        translation_panel = getattr(self, "translation_panel", None)
        if translation_panel is not None:
            translation_panel.sync_from_controller()
        self._sync_theme_mode(theme_mode)
        self._sync_render_mode()
        self.update_random_scan_summary()
        self.update_auto_threshold_refresh_summary()
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

    def _sync_render_mode(self):
        mode = getattr(self.controller, "region_render_mode", REGION_RENDER_BUBBLE)
        for button, button_mode in (
            (self.btn_render_bubble, REGION_RENDER_BUBBLE),
            (self.btn_render_relief, REGION_RENDER_RELIEF),
            (self.btn_render_screenshot, REGION_RENDER_SCREENSHOT),
        ):
            button.blockSignals(True)
            button.setChecked(mode == button_mode)
            button.blockSignals(False)

    def update_theme(self, theme_mode):
        theme = resolve_theme(theme_mode)
        is_dark = theme.key != "light"
        card_bg = "rgba(18, 31, 46, 168)" if is_dark else "rgba(255, 255, 255, 214)"
        translation_border = "#3D8DFF" if is_dark else "#5AA7F7"
        ocr_border = "#41B96F" if is_dark else "#50B86F"
        render_border = "#8D5CF6" if is_dark else "#8D65D8"
        self.refresh_localized_texts()
        self.setStyleSheet(
            theme.base_qss()
            + f"\nQWidget#settingsWindowRevamp {{ background: transparent; }}"
        )
        import os
        bg_image = "assets/bg_dark.jpg" if is_dark else "assets/bg_light.jpg"
        bg_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), bg_image)).replace("\\", "/")
        self.backdrop_panel.setStyleSheet(
            f"QFrame#settingsBackdropPanel {{ background-color: {theme.shell_bg}; border: 2px solid {theme.shell_border}; border-radius: 20px; "
            f"background-image: url('assets/{'bg_dark.jpg' if is_dark else 'bg_light.jpg'}'); background-position: center; background-repeat: no-repeat; }}"
        )
        self.top_panel.setStyleSheet(
            f"QWidget#settingsTopPanel {{ background: transparent; border: none; }}"
        )
        self.shell_panel.setStyleSheet(
            f"QFrame#settingsShellPanel {{ background: transparent; border: none; }}"
        )
        self.frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.ocr_backend_panel.update_theme(theme_mode)
        self.card_translate.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border: 1px solid {translation_border}; border-radius: 14px; }}")
        self.card_ocr.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border: 1px solid {ocr_border}; border-radius: 14px; }}")
        self.card_region_render.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border: 1px solid {render_border}; border-radius: 14px; }}")
        self.card_relief.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border: 1px solid {render_border}; border-radius: 14px; }}")
        self.auto_scan_panel.setStyleSheet(theme.panel_qss("transparent"))
        self.lbl_brand_icon.setStyleSheet(f"font-size: 24px; background-color: {theme.accent_soft}; border: 1px solid {theme.border}; border-radius: 20px;")
        self.lbl_page_title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {theme.text}; background: transparent; border: none;")
        self.lbl_page_subtitle.setStyleSheet(f"font-size: 14px; color: {theme.subtext}; background: transparent; border: none;")
        self.btn_close.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {theme.subtext}; border: none; font-size: 16px; font-weight: 900; }}"
            f"QPushButton:hover {{ background-color: {theme.accent_soft}; color: {theme.text}; border-radius: 15px; }}"
        )
        self.lbl_ocr.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {ocr_border}; background: transparent; border: none;")
        self.lbl_ocr_hint.setStyleSheet(f"font-size: 11px; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_auto_scan.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {theme.text}; background: transparent; border: none;")
        self.lbl_auto_scan_hint.setStyleSheet(f"font-size: 11px; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_auto_threshold_refresh.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_random_scan_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_auto_threshold_refresh_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_random_scan_center.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_random_scan_jitter.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_region_render.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {render_border}; background: transparent; border: none;")
        self.lbl_region_render_hint.setStyleSheet(f"font-size: 11px; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_region_render_mode.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_region_render_summary.setStyleSheet(theme.pill_qss("accent"))
        self.lbl_relief.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {render_border}; background: transparent; border: none;")
        self.lbl_relief_hint.setStyleSheet(f"font-size: 11px; color: {theme.subtext}; background: transparent; border: none;")
        self.lbl_relief_offset_x.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_relief_font.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_relief_offset_y.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_relief_opacity.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.subtext}; background: transparent; border: none; padding: 0px;")
        self.lbl_relief_offset_y_value.setStyleSheet(f"color: {theme.accent}; font-weight: 600; background: transparent; border: none; padding: 0px;")
        self.lbl_relief_opacity_value.setStyleSheet(f"color: {theme.accent}; font-weight: 600; background: transparent; border: none; padding: 0px;")
        spinbox_style = (
            f"QSpinBox {{ background-color: {theme.input_bg}; color: {theme.text}; border: 1px solid {theme.border}; "
            f"border-radius: 8px; padding: 3px 8px; }} "
            f"QSpinBox:focus {{ border: 2px solid {theme.accent}; }} "
            "QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }"
        )
        slider_style = (
            f"QSlider::groove:horizontal {{ height: 8px; border-radius: 4px; background: {theme.accent_soft}; }} "
            f"QSlider::handle:horizontal {{ width: 18px; margin: -5px 0; border-radius: 9px; background: {theme.accent}; border: 2px solid white; }}"
        )
        self.spin_random_scan_center.setStyleSheet(spinbox_style)
        self.spin_random_scan_jitter.setStyleSheet(spinbox_style)
        self.spin_auto_threshold_refresh_minutes.setStyleSheet(spinbox_style)
        self.slider_random_scan_center.setStyleSheet(slider_style)
        self.slider_random_scan_jitter.setStyleSheet(slider_style)
        self.slider_auto_threshold_refresh.setStyleSheet(slider_style)
        self.spin_relief_font.setStyleSheet(spinbox_style)
        self.slider_relief_offset_y.setStyleSheet(slider_style)
        self.slider_relief_opacity.setStyleSheet(slider_style)
        self.lbl_relief_summary.setStyleSheet(theme.pill_qss("accent"))
        self.cmb_theme_mode_chip.setStyleSheet(theme.combo_qss(radius=6))
        self.cmb_ui_language_chip.setStyleSheet(theme.combo_qss(radius=6))
        self.slider_relief_offset_x.setStyleSheet(slider_style)
        render_button_style = (
            f"QPushButton {{ color: {theme.text}; background-color: transparent; border: 1px solid {theme.border}; "
            f"border-radius: 10px; padding: 6px 10px; }}"
            f"QPushButton:checked {{ background-color: {theme.accent}; color: #FFFFFF; border-color: {theme.accent}; }}"
        )
        self.btn_render_bubble.setStyleSheet(render_button_style)
        self.btn_render_relief.setStyleSheet(render_button_style)
        self.btn_render_screenshot.setStyleSheet(render_button_style)
        self._sync_theme_mode(theme.key)
        self._sync_render_mode()
        self.translation_panel.update_theme(theme_mode)
        self.card_translate.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border: 1px solid {translation_border}; border-radius: 14px; }}")
        self.lbl_translate.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {translation_border}; background: transparent; border: none;")
        footer_button_style = (
            f"QPushButton {{ color: {theme.text}; background-color: {theme.input_bg}; border: 1px solid {theme.border}; "
            "border-radius: 8px; padding: 10px 16px; font-size: 13px; font-weight: 700; }}"
            f"QPushButton:hover {{ border-color: {theme.accent}; background-color: {theme.accent_soft}; }}"
        )
        self.btn_reset_defaults.setStyleSheet(footer_button_style)
        self.btn_cancel.setStyleSheet(footer_button_style)
        self.btn_save.setStyleSheet(
            f"QPushButton {{ color: #FFFFFF; background-color: {theme.accent}; border: 1px solid {theme.accent}; "
            "border-radius: 8px; padding: 10px 18px; font-size: 13px; font-weight: 800; }}"
            f"QPushButton:hover {{ background-color: {theme.control_checked}; }}"
        )
        self.update_relief_state(self.controller.region_render_mode == REGION_RENDER_RELIEF)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

# ==========================================
# 設定與同步
# ==========================================
    def export_history(self):
        try:
            import json
            cache = getattr(self.controller.worker, 'translation_cache', {})
            if not cache:
                QMessageBox.information(self, "提示", "目前沒有翻譯歷史紀錄。")
                return
            path, _ = QFileDialog.getSaveFileName(self, "匯出翻譯歷史", "cloudhime_history.json", "JSON Files (*.json)")
            if path:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", f"翻譯歷史已匯出至 {path}")
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"匯出失敗: {e}")

class Controller(QWidget):

    DEFAULT_GEMMA_PROMPT = translation_tools.DEFAULT_SYSTEM_PROMPT
    DEFAULT_SCREENSHOT_GEMMA_PROMPT = translation_tools.DEFAULT_SCREENSHOT_SYSTEM_PROMPT

    request_scan = Signal()

    def __init__(self, overlay):
        super().__init__()
        controller_t0 = time.perf_counter()
        last_mark = controller_t0

        def mark(stage, detail=""):
            nonlocal last_mark
            now = time.perf_counter()
            elapsed_ms = (now - last_mark) * 1000.0
            total_ms = (now - controller_t0) * 1000.0
            suffix = f"{detail} | " if detail else ""
            startup_log(f"Controller.{stage}", f"{suffix}+{elapsed_ms:.1f} ms / {total_ms:.1f} ms total")
            last_mark = now

        mark("__init__ start")
        self.overlay = overlay
        self.selection_overlay = SelectionOverlay()
        self.selection_overlay.selection_made.connect(self.on_region_selected)
        self.region_frame = RegionSelectionFrame()
        self.region_frame.region_changed.connect(self.on_region_frame_changed)
        self.settings_window = None
        self.google_ocr_enabled = False
        self.is_dark_mode = False
        self.theme_mode = "light"
        self.current_auto_interval = 0 
        self.countdown_seconds = 0
        self.random_scan_center_seconds = 10
        self.random_scan_jitter_percent = 20
        self.auto_threshold_refresh_minutes = DEFAULT_AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES
        self.region_render_mode = REGION_RENDER_BUBBLE
        self.region_relief_offset_x = 0
        self.region_relief_offset_y = 0
        self.region_relief_font_pt = 18
        self.region_frame_opacity = 40
        self.region_pass_through = False
        self.gemma_prompt = ""
        self.local_multimodal_enabled = False
        self.local_multimodal_base_url = "http://127.0.0.1:8080/v1"
        self.local_multimodal_model = "gemma-3-4b-it"
        self.local_multimodal_timeout_seconds = 20
        self.japanese_ocr_rescue_enabled = False
        self.was_minimized = False
        self.scan_mode = SCAN_MODE_FULLSCREEN
        self.selected_region = None
        self.last_scan_results = []
        self.settings_data = {}
        self.ui_language = localization.DEFAULT_UI_LANGUAGE
        self.cooldown_total_ms = 5000
        self.cooldown_end_time = 0.0
        self.scan_in_progress = False
        
        self.setWindowTitle("雲朵翻譯姬")
        self.resize(320, 180) 
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.set_cloud_icon()
        mark("ui shell ready")

        self.setup_ui()
        mark("setup_ui done")
        self.setup_worker()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_settings)
        self.gemma_prompt_timer = QTimer(self)
        self.gemma_prompt_timer.setSingleShot(True)
        self.gemma_prompt_timer.timeout.connect(self._apply_pending_gemma_prompt)
        self.screenshot_gemma_prompt_timer = QTimer(self)
        self.screenshot_gemma_prompt_timer.setSingleShot(True)
        self.screenshot_gemma_prompt_timer.timeout.connect(self._apply_pending_screenshot_gemma_prompt)
        self.load_settings()
        
        self.hotkey_filter = GlobalHotKeyFilter(self.on_hotkey_pressed)
        QApplication.instance().installNativeEventFilter(self.hotkey_filter)
        QTimer.singleShot(500, self.enable_hotkey)

        self.old_pos = None
        mark("__init__ end")

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
        self.lbl_status.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setMinimumHeight(30)
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
        self.refresh_main_ui_texts()

    def setup_worker(self):
        worker_t0 = time.perf_counter()
        startup_log("Controller.setup_worker start")
        self.ocr_thread = QThread()
        self.worker = OCRWorker()
        self.worker.set_scan_mode(self.scan_mode)
        self.worker.moveToThread(self.ocr_thread)
        self.request_scan.connect(self.worker.run_scan_once)
        self.worker.finished.connect(self.on_scan_complete)
        self.worker.streaming_update.connect(self.on_streaming_update)
        self.worker.translation_stream_update.connect(self.on_translation_stream_update)
        self.worker.status_msg.connect(self.update_status)
        self.worker.hide_ui.connect(self.hide_ui_for_scan)
        self.worker.show_ui.connect(self.show_ui_after_scan)
        self.worker.threshold_suggested.connect(self.apply_auto_threshold)
        self.worker.gemma_model_changed.connect(self.on_worker_gemma_model_changed)
        self.worker.local_model_status.connect(self.on_local_model_status)
        self.worker.local_vision_status.connect(self.on_local_vision_status)
        self.worker.japanese_rescue_status.connect(self.on_japanese_rescue_status)
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
        startup_log(
            "Controller.setup_worker done",
            f"+{(time.perf_counter() - worker_t0) * 1000.0:.1f} ms",
        )

    def enable_hotkey(self):
        self.hotkey_filter.register_hotkey(self.winId())
        self.refresh_hotkey_button_text()
        # 讓主視窗在截圖時隱形 (WDA_EXCLUDEFROMCAPTURE = 0x11)
        # 如此一來掃描時就不需要再 hide/show 視窗，消除閃爍
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x00000011)
        except Exception:
            pass

    def get_hotkey_button_text(self):
        label = getattr(self.hotkey_filter, "registered_label", None) or "~"
        return f"⚡ {self._tr('controller.button.now', fallback='Translate Now')} ({label})"

    def refresh_hotkey_button_text(self):
        if hasattr(self, "btn_now"):
            self.btn_now.setText(self.get_hotkey_button_text())

    def schedule_save_settings(self):
        if hasattr(self, "save_timer"):
            self.save_timer.start(250)

    def _tr(self, key, fallback=None, **params):
        return localization.tr(key, self.ui_language, fallback=fallback, **params)

    def _set_status_text(self, key, fallback=None, **params):
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText(self._tr(key, fallback=fallback, **params))

    def get_ui_language(self):
        return localization.normalize_ui_language(self.ui_language)

    def set_ui_language(self, language, *, persist=True, refresh=True):
        normalized = localization.normalize_ui_language(language)
        changed = normalized != getattr(self, "ui_language", localization.DEFAULT_UI_LANGUAGE)
        self.ui_language = normalized
        if hasattr(self, "worker") and hasattr(self.worker, "set_translation_target_lang"):
            self.worker.set_translation_target_lang(localization.get_translation_target_lang(normalized))
        if refresh and hasattr(self, "lbl_title"):
            self.refresh_main_ui_texts()
        if self.settings_window is not None:
            self.settings_window.refresh_localized_texts()
            if refresh:
                self.settings_window.sync_from_controller()
        if persist and changed:
            self.schedule_save_settings()

    def refresh_main_ui_texts(self):
        if hasattr(self, "setWindowTitle"):
            self.setWindowTitle(self._tr("controller.window_title", fallback="CloudHime"))
        if hasattr(self, "lbl_title"):
            self.lbl_title.setText(self._tr("controller.title", fallback="CloudHime v3.0"))
        if hasattr(self, "input_api_key"):
            self.input_api_key.setPlaceholderText(
                self._tr("controller.placeholder.google_api_key", fallback="Google API KEY")
            )
        if hasattr(self, "btn_ai_mode"):
            self.btn_ai_mode.setText(self._tr("controller.button.ai_translation", fallback="AI 翻譯"))
        if hasattr(self, "btn_mode_full"):
            self.btn_mode_full.setText(self._tr("controller.button.fullscreen", fallback="全螢幕翻譯"))
        if hasattr(self, "btn_mode_region"):
            self.btn_mode_region.setText(self._tr("controller.button.region", fallback="區域翻譯"))
        if hasattr(self, "btn_stop"):
            self.btn_stop.setText(self._tr("controller.button.stop", fallback="停止"))
        if hasattr(self, "btn_theme"):
            self.btn_theme.setToolTip(self._tr("controller.tooltip.settings", fallback="設定"))
        if hasattr(self, "btn_30"):
            self.btn_30.setText(
                f"{self._tr('controller.button.random_scan_prefix', fallback='隨機')} {int(self.random_scan_center_seconds)}s~"
            )
        if hasattr(self, "btn_now"):
            self.btn_now.setText(self._tr("controller.button.now", fallback="立即翻譯"))

    def get_settings_payload(self):
        payload = {
            "gemma_model": self.worker.gemma_model,
            "gemma_prompt": self.gemma_prompt,
            "local_gemma_temperature": float(
                getattr(self, "local_gemma_temperature", 0.2)
            ),
            "local_gemma_repeat_penalty": float(
                getattr(self, "local_gemma_repeat_penalty", 1.15)
            ),
            "screenshot_gemma_prompt": self.screenshot_gemma_prompt,
            "use_gemma_translation": self.worker.use_gemma_translation,
            "auto_threshold_enabled": self.worker.auto_threshold_enabled,
            "auto_threshold_refresh_minutes": int(self.auto_threshold_refresh_minutes),
            "google_ocr_enabled": self.google_ocr_enabled,
            "gemma_auto_switch_enabled": self.worker.gemma_auto_switch_enabled,
            "local_multimodal_enabled": bool(getattr(self.worker, "local_multimodal_enabled", getattr(self, "local_multimodal_enabled", False))),
            "local_multimodal_base_url": str(getattr(self.worker, "local_multimodal_base_url", getattr(self, "local_multimodal_base_url", "http://127.0.0.1:8080/v1")) or "http://127.0.0.1:8080/v1"),
            "local_multimodal_model": str(getattr(self.worker, "local_multimodal_model", getattr(self, "local_multimodal_model", "gemma-3-4b-it")) or "gemma-3-4b-it"),
            "local_multimodal_timeout_seconds": int(getattr(self.worker, "local_multimodal_timeout_seconds", getattr(self, "local_multimodal_timeout_seconds", 20))),
            "japanese_ocr_rescue_enabled": bool(getattr(self, "japanese_ocr_rescue_enabled", False)),
            "ocr_backend_chain": list(self.worker.ocr_backend_chain) if getattr(self.worker, "ocr_backend_chain", None) else None,
            "random_scan_center_seconds": int(self.random_scan_center_seconds),
            "random_scan_jitter_percent": int(self.random_scan_jitter_percent),
            "region_pass_through": getattr(self, "region_pass_through", False),
            "region_render_mode": self.region_render_mode,
            "region_relief_offset_x": int(self.region_relief_offset_x),
            "region_relief_offset_y": int(self.region_relief_offset_y),
            "region_relief_font_pt": int(self.region_relief_font_pt),
            "scan_mode": self.scan_mode,
            "selected_region": list(self.selected_region) if self.selected_region else None,
            "is_dark_mode": self.is_dark_mode,
            "theme_mode": self.theme_mode,
            "binary_threshold": int(self.worker.binary_threshold),
            "ui_language": self.get_ui_language(),
        }
        return normalize_settings_payload(payload, int(self.region_frame_opacity), self.get_ui_language())

    def save_settings(self):
        try:
            payload = self.get_settings_payload()
            save_settings_data(SETTINGS_PATHS, payload)
        except Exception as exc:
            logger.error(f"[Settings] save failed: {exc}")
            try:
                log_path = UI_ERROR_LOG_PATH
                with open(log_path, "a", encoding="utf-8") as fp:
                    fp.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] save_settings failed: {exc}\n")
                    fp.write(traceback.format_exc())
                    fp.write("\n")
            except Exception:
                pass
            return False
        return True

    def load_settings(self):
        load_t0 = time.perf_counter()
        startup_log("Controller.load_settings start")
        settings, loaded_from_path = load_settings_data(SETTINGS_PATHS)
        self.settings_data = settings
        self.worker.begin_translation_registry_batch()
        self.set_ui_language(resolve_ui_language(settings, self.ui_language), persist=False, refresh=True)

        def safe_int(value, fallback, lower=None, upper=None):
            try:
                numeric = int(value)
            except Exception:
                numeric = int(fallback)
            if lower is not None:
                numeric = max(lower, numeric)
            if upper is not None:
                numeric = min(upper, numeric)
            return numeric

        def safe_choice(value, fallback, *allowed):
            candidate = str(value or "").strip()
            return candidate if candidate in allowed else fallback

        try:
            threshold = safe_int(settings.get("binary_threshold", self.worker.binary_threshold), self.worker.binary_threshold, AUTO_THRESHOLD_MIN, AUTO_THRESHOLD_MAX)
            self.worker.binary_threshold = threshold
            self.update_threshold(threshold)

            self.worker.set_auto_threshold_enabled(bool(settings.get("auto_threshold_enabled", self.worker.auto_threshold_enabled)))
            auto_threshold_minutes = safe_int(
                settings.get("auto_threshold_refresh_minutes", self.auto_threshold_refresh_minutes),
                self.auto_threshold_refresh_minutes,
                AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MIN,
                AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MAX,
            )
            self.set_auto_threshold_refresh_minutes(auto_threshold_minutes, persist=False)
            backend_chain = extract_backend_chain(settings)
            if backend_chain is None:
                backend_chain = ["windows"]
            backend_chain = self.worker.normalize_ocr_backend_chain(backend_chain)
            if "windows" not in backend_chain:
                backend_chain.insert(0, "windows")
            try:
                self.worker.reload_ocr_backends(backend_chain)
            except Exception:
                self.worker.reload_ocr_backends(None)
            startup_log(
                "Controller.load_settings backends",
                f"chain={','.join(backend_chain) if backend_chain else 'none'}",
            )

            center_seconds = safe_int(settings.get("random_scan_center_seconds", self.random_scan_center_seconds), self.random_scan_center_seconds, 1, 300)
            self.random_scan_center_seconds = center_seconds

            jitter_percent = safe_int(settings.get("random_scan_jitter_percent", self.random_scan_jitter_percent), self.random_scan_jitter_percent, 0, 100)
            self.random_scan_jitter_percent = jitter_percent

            self.region_render_mode = safe_choice(
                settings.get("region_render_mode", REGION_RENDER_BUBBLE),
                REGION_RENDER_BUBBLE,
                REGION_RENDER_BUBBLE,
                REGION_RENDER_RELIEF,
                REGION_RENDER_SCREENSHOT,
            )
            self.worker.set_region_render_mode(self.region_render_mode)

            self.region_relief_offset_x, self.region_relief_offset_y = resolve_relief_offsets(settings)
            self.region_relief_font_pt = safe_int(settings.get("region_relief_font_pt", self.region_relief_font_pt), self.region_relief_font_pt, MIN_BUBBLE_FONT_PT, 48)
            self.region_frame_opacity = resolve_region_opacity(settings, self.region_frame_opacity)

            env_api_key = str(os.getenv(API_KEY_ENV_VAR, "") or "").strip()
            
            # Read the AppData copy first, with the install-adjacent file kept as a migration fallback.
            if not env_api_key:
                env_api_key = _read_api_key_from_env_files(
                    (APPDATA_ENV_PATH, LEGACY_ENV_PATH)
                )

            legacy_api_key = str(settings.get("google_api_key", "") or "").strip()
            api_key = env_api_key or legacy_api_key
            self.worker.set_google_api_key(api_key)
            if self.input_api_key.text() != api_key:
                self.input_api_key.blockSignals(True)
                self.input_api_key.setText(api_key)
                self.input_api_key.blockSignals(False)

            model_name = safe_choice(settings.get("gemma_model", DEFAULT_GEMMA_MODEL), DEFAULT_GEMMA_MODEL, *SUPPORTED_GEMMA_MODEL_NAMES)
            model_index = self.cmb_ai_model.findData(model_name)
            if model_index < 0:
                model_index = 0
            self.cmb_ai_model.blockSignals(True)
            self.cmb_ai_model.setCurrentIndex(model_index)
            self.cmb_ai_model.blockSignals(False)
            self.worker.set_gemma_model(self.cmb_ai_model.itemData(model_index))
            if self.settings_window is not None and self.settings_window.cmb_ai_model.currentIndex() != model_index:
                self.settings_window.cmb_ai_model.blockSignals(True)
                self.settings_window.cmb_ai_model.setCurrentIndex(model_index)
                self.settings_window.cmb_ai_model.blockSignals(False)
                self.settings_window.update_translate_summary()

            self.gemma_prompt = str(settings.get("gemma_prompt", "") or "").strip() or self.get_default_gemma_prompt()
            self.worker.set_gemma_prompt(self.gemma_prompt)

            self.screenshot_gemma_prompt = (
                str(settings.get("screenshot_gemma_prompt", "") or "").strip()
                or self.get_default_screenshot_gemma_prompt()
            )
            self.worker.set_screenshot_gemma_prompt(self.screenshot_gemma_prompt)
            if self.settings_window is not None and self.settings_window.input_screenshot_gemma_prompt.toPlainText() != self.screenshot_gemma_prompt:
                self.settings_window.input_screenshot_gemma_prompt.blockSignals(True)
                self.settings_window.input_screenshot_gemma_prompt.setPlainText(self.screenshot_gemma_prompt)
                self.settings_window.input_screenshot_gemma_prompt.blockSignals(False)
            if self.settings_window is not None and self.settings_window.input_gemma_prompt.toPlainText() != self.gemma_prompt:
                self.settings_window.input_gemma_prompt.blockSignals(True)
                self.settings_window.input_gemma_prompt.setPlainText(self.gemma_prompt)
                self.settings_window.input_gemma_prompt.blockSignals(False)

            self.local_gemma_temperature = float(settings.get("local_gemma_temperature", 0.2))
            self.local_gemma_repeat_penalty = float(settings.get("local_gemma_repeat_penalty", 1.15))
            self.worker.set_local_gemma_params(self.local_gemma_temperature, self.local_gemma_repeat_penalty)

            self.local_multimodal_enabled = bool(settings.get("local_multimodal_enabled", False))
            self.local_multimodal_base_url = str(settings.get("local_multimodal_base_url", "http://127.0.0.1:8080/v1") or "http://127.0.0.1:8080/v1").rstrip("/")
            self.local_multimodal_model = str(settings.get("local_multimodal_model", "gemma-3-4b-it") or "gemma-3-4b-it").strip()
            self.local_multimodal_timeout_seconds = safe_int(settings.get("local_multimodal_timeout_seconds", 20), 20, 1, 300)
            self.worker.set_local_multimodal_config(
                enabled=self.local_multimodal_enabled,
                base_url=self.local_multimodal_base_url,
                model_name=self.local_multimodal_model,
                timeout_seconds=self.local_multimodal_timeout_seconds,
            )
            self.japanese_ocr_rescue_enabled = bool(settings.get("japanese_ocr_rescue_enabled", False))
            self.worker.set_japanese_rescue_enabled(
                self.japanese_ocr_rescue_enabled and self.local_multimodal_enabled
            )

            saved_theme_mode = str(settings.get("theme_mode", "") or "").strip()
            if not saved_theme_mode:
                saved_theme_mode = "dark" if bool(settings.get("is_dark_mode", False)) else "light"
            saved_theme_mode = ThemeRegistry.normalize_mode(saved_theme_mode)
            self.set_theme_mode(saved_theme_mode)
            self.region_frame.set_theme_mode(saved_theme_mode)
            self.region_frame.set_frame_opacity(self.region_frame_opacity)
            self.region_pass_through = bool(settings.get("region_pass_through", False))
            self.region_frame.set_region_pass_through(self.region_pass_through)
            if self.settings_window is not None:
                self.settings_window.chk_region_pass_through.blockSignals(True)
                self.settings_window.chk_region_pass_through.setChecked(self.region_pass_through)
                self.settings_window.chk_region_pass_through.blockSignals(False)

            saved_region = settings.get("selected_region")
            if isinstance(saved_region, list) and len(saved_region) == 4:
                try:
                    self.selected_region = tuple(int(v) for v in saved_region)
                    self.worker.set_scan_region(self.selected_region)
                except Exception:
                    self.selected_region = None

            saved_scan_mode = safe_choice(settings.get("scan_mode", SCAN_MODE_FULLSCREEN), SCAN_MODE_FULLSCREEN, SCAN_MODE_FULLSCREEN, SCAN_MODE_REGION)
            if saved_scan_mode == SCAN_MODE_REGION and self.selected_region:
                self.btn_mode_region.setChecked(True)
                self.set_scan_mode(SCAN_MODE_REGION)
            else:
                self.btn_mode_full.setChecked(True)
                self.set_scan_mode(SCAN_MODE_FULLSCREEN)

            use_gemma_translation = bool(settings.get("use_gemma_translation", False))
            self.btn_ai_mode.setChecked(use_gemma_translation)
            self.worker.set_gemma_enabled(use_gemma_translation)
            if self.settings_window is not None:
                self.settings_window.set_translate_mode(use_gemma_translation)
            self.google_ocr_enabled = bool(settings.get("google_ocr_enabled", False))
            self.worker.google_ocr_enabled = self.google_ocr_enabled
            if self.settings_window is not None:
                self.settings_window.ocr_backend_panel.sync_from_controller()
            self.worker.set_gemma_auto_switch_enabled(bool(settings.get("gemma_auto_switch_enabled", False)))
            if self.settings_window is not None:
                self.settings_window.chk_auto_switch.blockSignals(True)
                self.settings_window.chk_auto_switch.setChecked(self.worker.gemma_auto_switch_enabled)
                self.settings_window.chk_auto_switch.blockSignals(False)
            self.update_random_scan_button_text()
            if use_gemma_translation and api_key:
                self._set_status_text(
                    "controller.status.ai_model_ready",
                    fallback="AI model: {model}",
                    model=self.cmb_ai_model.currentText(),
                )
            else:
                self._set_status_text("controller.status.ready", fallback="Ready and waiting (*´▽`*)")
            self.overlay.set_render_context(
                self.scan_mode,
                self.region_render_mode,
                self.region_relief_offset_x,
                self.region_relief_offset_y,
                self.region_relief_font_pt,
                self.region_frame_opacity,
                self.selected_region,
            )
            self.refresh_main_ui_texts()
            if should_migrate_to_appdata(SETTINGS_PATHS, loaded_from_path):
                self.save_settings()
            if legacy_api_key:
                self.save_settings()
        finally:
            self.worker.end_translation_registry_batch()
            startup_log(
                "Controller.load_settings done",
                f"+{(time.perf_counter() - load_t0) * 1000.0:.1f} ms",
            )

    def update_threshold(self, val):
        self.worker.binary_threshold = val
        self.schedule_save_settings()

    def apply_auto_threshold(self, val):
        self.worker.binary_threshold = val
        self.schedule_save_settings()

    def on_random_scan_settings_changed(self, center_seconds, jitter_percent):
        self.random_scan_center_seconds = max(1, min(300, int(center_seconds)))
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

    def on_region_pass_through_changed(self, checked):
        self.region_pass_through = checked
        if hasattr(self, 'region_frame'):
            self.region_frame.set_region_pass_through(checked)
        self.schedule_save_settings()

    def on_region_render_mode_changed(self, mode):
        mode = str(mode or REGION_RENDER_BUBBLE)
        if mode not in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF, REGION_RENDER_SCREENSHOT):
            mode = REGION_RENDER_BUBBLE
        self.region_render_mode = mode
        self.worker.set_region_render_mode(mode)
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_offset_x,
            self.region_relief_offset_y,
            self.region_relief_font_pt,
            self.region_frame_opacity,
            self.selected_region,
        )
        if self.settings_window is not None:
            self.settings_window.update_region_render_summary()
        self.update_mode_status_text()
        self.schedule_save_settings()

    def update_mode_status_text(self):
        if self.scan_mode == SCAN_MODE_FULLSCREEN:
            self._set_status_text("controller.mode.fullscreen", fallback="🖥 Mode: Full screen")
            return

        if self.region_render_mode == REGION_RENDER_RELIEF:
            self._set_status_text("controller.mode.relief", fallback="🧩 Mode: Relief")
        elif self.region_render_mode == REGION_RENDER_SCREENSHOT:
            self._set_status_text("controller.mode.screenshot", fallback="🖼 Mode: Screenshot")
        else:
            self._set_status_text("controller.mode.bubble", fallback="💬 Mode: Bubble")

    def on_region_relief_settings_changed(self, offset_x, offset_y, font_pt, opacity):
        self.region_relief_offset_x = max(-RELIEF_MAX_OFFSET_PX, min(RELIEF_MAX_OFFSET_PX, int(offset_x)))
        self.region_relief_offset_y = max(-RELIEF_MAX_OFFSET_PX, min(RELIEF_MAX_OFFSET_PX, int(offset_y)))
        self.region_relief_font_pt = max(MIN_BUBBLE_FONT_PT, min(48, int(font_pt)))
        self.region_frame_opacity = max(0, min(100, int(opacity)))
        self.region_frame.set_theme_mode(self.theme_mode)
        self.region_frame.set_frame_opacity(self.region_frame_opacity)
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_offset_x,
            self.region_relief_offset_y,
            self.region_relief_font_pt,
            self.region_frame_opacity,
            self.selected_region,
        )
        self.refresh_overlay_from_last_results()
        self.schedule_save_settings()
    def set_auto_threshold_mode(self, enabled):
        self.worker.set_auto_threshold_enabled(enabled)
        self.schedule_save_settings()

    def set_auto_threshold_refresh_minutes(self, minutes, persist=True):
        minutes = max(
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MIN,
            min(AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MAX, int(minutes)),
        )
        self.auto_threshold_refresh_minutes = minutes
        self.worker.set_auto_threshold_refresh_interval_minutes(minutes)
        if persist:
            self.schedule_save_settings()

    def set_gemma_auto_switch_mode(self, enabled):
        self.worker.set_gemma_auto_switch_enabled(enabled)
        if self.settings_window is not None and self.settings_window.chk_auto_switch.isChecked() != enabled:
            self.settings_window.chk_auto_switch.blockSignals(True)
            self.settings_window.chk_auto_switch.setChecked(enabled)
            self.settings_window.chk_auto_switch.blockSignals(False)
        if self.settings_window is not None:
            self.settings_window.update_translate_summary()
        self.schedule_save_settings()
        self.save_settings()

    def get_ocr_backend_chain(self):
        chain = list(getattr(self.worker, "ocr_backend_chain", []) or [])
        if "windows" not in chain:
            chain.insert(0, "windows")
        return chain

    def set_ocr_backend_chain(self, chain):
        normalized = self.worker.normalize_ocr_backend_chain(chain)
        if not normalized:
            normalized = ["windows"]
        self.worker.reload_ocr_backends(normalized)
        self.save_settings()

    def set_ocr_backend_enabled(self, backend_name, enabled):
        backend_name = str(backend_name or "").strip().lower()
        if not backend_name:
            return
        if backend_name == "windows":
            enabled = True
        chain = self.get_ocr_backend_chain()
        if enabled:
            if backend_name not in chain:
                chain.append(backend_name)
        else:
            chain = [item for item in chain if item != backend_name]
        if not chain:
            chain = ["windows"]
        self.set_ocr_backend_chain(chain)

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
        elif self.settings_window is not None:
            self.settings_window.update_translate_summary()
        if getattr(self.worker, "use_gemma_translation", False):
            old_index = self.cmb_ai_model.findData(old_model)
            old_label = self.cmb_ai_model.itemText(old_index) if old_index >= 0 else old_model
            new_label = self.cmb_ai_model.itemText(model_index) if model_index >= 0 else new_model
            self.lbl_status.setText(f"AI模型自動切換：{old_label} -> {new_label}")
        self.schedule_save_settings()

    def on_api_key_changed(self, text):
        self.worker.set_google_api_key(text)
        
        # Store user secrets beside settings, never in the read-only package directory.
        env_path = APPDATA_ENV_PATH
        try:
            os.makedirs(os.path.dirname(env_path), exist_ok=True)
            env_vars = {}
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            env_vars[k] = v
            env_vars[API_KEY_ENV_VAR] = text.strip()
            with open(env_path, "w", encoding="utf-8") as f:
                for k, v in env_vars.items():
                    f.write(f"{k}={v}\n")
        except Exception as e:
            logger.error(f"Failed to save API key to AppData: {e}")

        if self.input_api_key.text() != text:
            self.input_api_key.blockSignals(True)
            self.input_api_key.setText(text)
            self.input_api_key.blockSignals(False)
        if getattr(self.worker, "use_gemma_translation", False) and not text.strip():
            self.toggle_ai_translation(False)
        if self.settings_window is not None and self.settings_window.input_api_key.text() != text:
            self.settings_window.input_api_key.blockSignals(True)
            self.settings_window.input_api_key.setText(text)
            self.settings_window.input_api_key.blockSignals(False)
        if self.settings_window is not None and hasattr(self.settings_window, "ocr_backend_panel"):
            self.settings_window.ocr_backend_panel.sync_from_controller()
        self.schedule_save_settings()

    def on_ai_model_changed(self, index):
        model_name = self.cmb_ai_model.itemData(index)
        self.worker.set_gemma_model(model_name)
        if self.cmb_ai_model.currentIndex() != index:
            self.cmb_ai_model.blockSignals(True)
            self.cmb_ai_model.setCurrentIndex(index)
            self.cmb_ai_model.blockSignals(False)
        if self.settings_window is not None and self.settings_window.cmb_ai_model.currentIndex() != index:
            self.settings_window.cmb_ai_model.blockSignals(True)
            self.settings_window.cmb_ai_model.setCurrentIndex(index)
            self.settings_window.cmb_ai_model.blockSignals(False)
        if self.settings_window is not None:
            self.settings_window.update_translate_summary()
        self.schedule_save_settings()

    def on_gemma_prompt_changed(self, text):
        self.gemma_prompt = (text or "").strip()
        self._pending_gemma_prompt = self.gemma_prompt
        if hasattr(self, "gemma_prompt_timer"):
            self.gemma_prompt_timer.start(350)

    def on_local_gemma_temp_changed(self, value):
        self.local_gemma_temperature = value
        self.worker.set_local_gemma_params(self.local_gemma_temperature, getattr(self, "local_gemma_repeat_penalty", 1.15))
        self.schedule_save_settings()

    def on_local_gemma_repeat_changed(self, value):
        self.local_gemma_repeat_penalty = value
        self.worker.set_local_gemma_params(getattr(self, "local_gemma_temperature", 0.2), self.local_gemma_repeat_penalty)
        self.schedule_save_settings()

    def get_default_gemma_prompt(self):
        return self.DEFAULT_GEMMA_PROMPT

    def get_default_screenshot_gemma_prompt(self):
        return self.DEFAULT_SCREENSHOT_GEMMA_PROMPT

    def set_google_ocr_enabled(self, enabled):
        self.google_ocr_enabled = bool(enabled)
        if hasattr(self, "worker"):
            self.worker.google_ocr_enabled = self.google_ocr_enabled
        self.schedule_save_settings()

    def _score_ocr_candidate_text(self, text):
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

    def _choose_better_ocr_candidate(self, local_text, google_text):
        local_norm = normalize_ocr_text(local_text)
        google_norm = normalize_ocr_text(google_text)
        if not local_norm:
            return google_norm
        if not google_norm:
            return local_norm
        if local_norm == google_norm:
            return local_norm
        local_score = self._score_ocr_candidate_text(local_norm)
        google_score = self._score_ocr_candidate_text(google_norm)
        if google_score >= local_score + 1:
            return google_norm
        if len(google_norm) > len(local_norm) and google_score >= local_score:
            return google_norm
        return local_norm

    def _apply_pending_gemma_prompt(self):
        self.worker.set_gemma_prompt(self._pending_gemma_prompt)
        self.schedule_save_settings()

    def _apply_pending_screenshot_gemma_prompt(self):
        self.worker.set_screenshot_gemma_prompt(self._pending_screenshot_gemma_prompt)
        self.schedule_save_settings()

    def on_screenshot_gemma_prompt_changed(self):
        if not self.settings_window:
            return
        self.screenshot_gemma_prompt = self.settings_window.input_screenshot_gemma_prompt.toPlainText().strip()
        self._pending_screenshot_gemma_prompt = self.screenshot_gemma_prompt
        self.screenshot_gemma_prompt_timer.start(1000)

    def _push_local_multimodal_config(self):
        self.worker.set_local_multimodal_config(
            enabled=self.local_multimodal_enabled,
            base_url=self.local_multimodal_base_url,
            model_name=self.local_multimodal_model,
            timeout_seconds=self.local_multimodal_timeout_seconds,
        )
        rescue_setter = getattr(self.worker, "set_japanese_rescue_enabled", None)
        if callable(rescue_setter):
            rescue_setter(
                bool(getattr(self, "japanese_ocr_rescue_enabled", False))
                and self.local_multimodal_enabled
            )
        self.schedule_save_settings()

    def on_local_multimodal_enabled_changed(self, enabled):
        self.local_multimodal_enabled = bool(enabled)
        self._push_local_multimodal_config()

    def on_japanese_ocr_rescue_enabled_changed(self, enabled):
        self.japanese_ocr_rescue_enabled = bool(enabled)
        rescue_setter = getattr(self.worker, "set_japanese_rescue_enabled", None)
        if callable(rescue_setter):
            rescue_setter(
                bool(getattr(self, "japanese_ocr_rescue_enabled", False))
                and self.local_multimodal_enabled
            )
        self.schedule_save_settings()

    def on_local_multimodal_base_url_changed(self, base_url):
        self.local_multimodal_base_url = str(base_url or "").strip().rstrip("/")
        self._push_local_multimodal_config()

    def on_local_multimodal_model_changed(self, model_name):
        self.local_multimodal_model = str(model_name or "").strip()
        self._push_local_multimodal_config()

    def on_local_multimodal_timeout_changed(self, timeout_seconds):
        self.local_multimodal_timeout_seconds = max(1, min(300, int(timeout_seconds)))
        self._push_local_multimodal_config()

    def toggle_ai_translation(self, checked):
        desired_enabled = bool(checked)
        has_key = bool(self.worker.google_api_key.strip())
        is_local_model = (getattr(self.worker, "gemma_model", "") or "").strip() in {"translategemma-4b-it-local", "gemma-3-4b-it-local"}
        if desired_enabled and not (has_key or is_local_model):
            self.lbl_status.setText("請先輸入 Google API KEY，或切換到本地模型")
            desired_enabled = False
        self.worker.set_gemma_enabled(desired_enabled)
        if self.btn_ai_mode.isChecked() != desired_enabled:
            self.btn_ai_mode.blockSignals(True)
            self.btn_ai_mode.setChecked(desired_enabled)
            self.btn_ai_mode.blockSignals(False)
        if self.settings_window is not None:
            self.settings_window.set_translate_mode(desired_enabled)
            if hasattr(self.settings_window, "ocr_backend_panel"):
                self.settings_window.ocr_backend_panel.sync_from_controller()
        if desired_enabled:
            self.lbl_status.setText(f"AI模型: {self.cmb_ai_model.currentText()}")
        self.schedule_save_settings()

    def set_scan_mode(self, scan_mode):
        self.scan_mode = scan_mode
        self.worker.set_scan_mode(scan_mode)
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_offset_x,
            self.region_relief_offset_y,
            self.region_relief_font_pt,
            self.region_frame_opacity,
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
        self.update_mode_status_text()
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
        self._set_status_text(
            "controller.status.region_ready",
            fallback="Scan region set: {size}",
            size=f"{w}x{h}",
        )
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
            self.region_relief_offset_x,
            self.region_relief_offset_y,
            self.region_relief_font_pt,
            self.region_frame_opacity,
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
            self.settings_window.resize(1180, 740)
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
            log_path = UI_ERROR_LOG_PATH
            with open(log_path, "a", encoding="utf-8") as fp:
                fp.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}: {exc}\n")
                fp.write(traceback.format_exc())
                fp.write("\n")
        except Exception:
            pass

    def log_ai_debug(self, message):
        from cloudhime_logging import log_ai_debug
        log_ai_debug(message)

    def log_translation_debug(self, message):
        from cloudhime_logging import log_translation_debug
        log_translation_debug(message)

    def on_hotkey_pressed(self):
        QTimer.singleShot(0, self.on_immediate_click)

    def on_immediate_click(self):
        if self.cooldown_timer.isActive():
            logger.info("[Hotkey] Cooldown active, please wait")
            return
        if self.scan_mode == SCAN_MODE_REGION and not self.selected_region:
            self._set_status_text("controller.status.need_region", fallback="Please set a scan region first")
            self.begin_region_selection()
            return
        self.display_timer.stop()
        self._set_status_text("controller.status.immediate_scanning", fallback="⚡ Scanning now...")
        self.worker.last_auto_threshold_refresh_ms = 0.0
        self.trigger_scan_sequence()
        self.btn_now.setEnabled(False)
        self.btn_now.setText(self._tr("controller.status.cold_down", fallback="⚡ Cooling down..."))
        self.btn_now.set_cooldown_progress(0)
        self.cooldown_end_time = time.monotonic() + (self.cooldown_total_ms / 1000.0)
        self.cooldown_progress_timer.start()
        self.cooldown_timer.start(self.cooldown_total_ms)
        self._set_status_text("controller.status.cold_down", fallback="⚡ Cooling down...")

    def reset_immediate_btn(self):
        self.cooldown_progress_timer.stop()
        self.btn_now.set_cooldown_progress(0)
        self.cooldown_end_time = 0.0
        self.btn_now.setEnabled(True)
        self.refresh_hotkey_button_text()
        status_text = self.lbl_status.text()
        if not self.scan_in_progress:
            # 截圖模式的完成訊息要保留，不要被冷卻結束直接蓋掉
            if any(token in status_text for token in ("截圖", "翻譯", "完成")):
                return
            self.update_mode_status_text()
        elif "截圖" in status_text or "Screenshot" in status_text:
            self._set_status_text("controller.status.capture_running", fallback="🖼 Screenshot translation running...")

    def update_cooldown_progress(self):
        if self.cooldown_end_time <= 0:
            self.cooldown_progress_timer.stop()
            return
        remaining = max(0.0, self.cooldown_end_time - time.monotonic())
        progress = int(round((1.0 - (remaining / (self.cooldown_total_ms / 1000.0))) * 100))
        progress = max(0, min(100, progress))
        self.btn_now.set_cooldown_progress(progress)
        self.btn_now.setText(f"⚡ {progress}%")
        self._set_status_text("controller.status.cold_down", fallback="⚡ Cooling down...")

    def start_auto_scan(self, checked=False, base_interval=None):
        if self.scan_mode == SCAN_MODE_REGION and not self.selected_region:
            self._set_status_text("controller.status.need_region", fallback="Please set a scan region first")
            self.begin_region_selection()
            return
        if base_interval is None:
            base_interval = max(1000, int(self.random_scan_center_seconds) * 1000)
        self.current_auto_interval = base_interval
        self._set_status_text(
            "controller.status.auto_scanning",
            fallback="{prefix} auto-scanning",
            prefix=self.get_random_scan_button_text(),
        )
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

    def on_translation_stream_update(self, index, partial_text, provider, x, y, w, h):
        if getattr(self, "overlay", None):
            self.overlay.update_translation_stream(index, partial_text, provider, x, y, w, h)

    def on_streaming_update(self, partial_results):
        """接收串流翻譯的中間結果，即時更新氣泡文字（打字機效果）"""
        if not partial_results:
            return
        if not self.overlay.bubbles:
            # 還沒建立氣泡時，先用 update_bubbles 建立框架
            self.overlay.set_render_context(
                self.scan_mode, self.region_render_mode, self.region_relief_offset_x,
                self.region_relief_offset_y, self.region_relief_font_pt, self.region_frame_opacity,
                self.selected_region,
            )
            self.overlay.update_bubbles(partial_results)
            self.overlay.raise_()
        else:
            self.overlay.update_bubble_text_only(partial_results)

    def on_scan_complete(self, results):
        self.scan_in_progress = False
        self.last_scan_results = list(results) if results else []
        self.overlay.set_render_context(
            self.scan_mode,
            self.region_render_mode,
            self.region_relief_offset_x,
            self.region_relief_offset_y,
            self.region_relief_font_pt,
            self.region_frame_opacity,
            self.selected_region,
        )
        display_results = list(results) if results else []
        if self.scan_mode == SCAN_MODE_REGION and self.region_render_mode == REGION_RENDER_SCREENSHOT and display_results:
            combined_text = "\n".join(str(text).strip() for text, *_ in display_results if str(text).strip())
            if combined_text:
                if self.selected_region:
                    anchor = self.selected_region
                else:
                    first = display_results[0]
                    anchor = (int(first[1]), int(first[2]), max(1, int(first[3])), max(1, int(first[4])))
                display_results = [(combined_text, int(anchor[0]), int(anchor[1]), max(1, int(anchor[2])), max(1, int(anchor[3])))]
        self.overlay.update_bubbles(display_results)
        self.overlay.raise_()
        if self.current_auto_interval > 0:
            self.schedule_next_scan()

    def stop_scan(self):
        self.scan_in_progress = False
        self.current_auto_interval = 0
        self.auto_timer.stop()
        self.display_timer.stop()
        self.auto_group.setExclusive(False)
        self.btn_30.setChecked(False)
        self.auto_group.setExclusive(True)
        self._set_status_text("controller.status.auto_stopped", fallback="⏸ Auto stopped")
        self.overlay.clear_all()

    def trigger_scan_sequence(self):
        self.scan_in_progress = True
        self.display_timer.stop()
        # 截圖隱身術已啟用，不需要在掃描時隱藏 UI，保留舊字幕達成無縫更新
        QTimer.singleShot(50, self._emit_scan_signal)

    def _emit_scan_signal(self):
        self.request_scan.emit()

    def update_status(self, msg):
        if self.display_timer.isActive() and not any(token in msg for token in ("完成", "翻譯", "失敗", "錯誤", "需要", "就緒")):
            return
        self.lbl_status.setToolTip(msg)
        self.lbl_status.setStatusTip(msg)
        self.lbl_status.setText(msg)
        self.update_gemma_rate_indicator()

    def update_gemma_rate_indicator(self):
        if not hasattr(self, "charge_bar") or not hasattr(self, "worker"):
            return
        self.worker.prune_gemma_call_timestamps()
        if self.worker.has_multimodal_ai():
            selected_model = self.worker.normalize_gemma_model(self.worker.gemma_model)
            if self.worker.can_call_gemma(selected_model):
                self.worker.active_gemma_model = selected_model
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
                self._set_status_text(
                    "controller.status.ai_model_full_switch",
                    fallback="{current} is full; next run will switch to {backup}",
                    current=current_label,
                    backup=backup_label,
                )
                return
            if used >= limit:
                colors = build_charge_bar_colors(theme, "danger")
                self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
                self.charge_bar.set_progress(100, f"{current_label} {used}/{limit}")
                self._set_status_text(
                    "controller.status.ai_model_full_google",
                    fallback="{current} is full {limit}/{limit}; using Google for now",
                    current=current_label,
                    limit=limit,
                )
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
        # 由於部分環境下截圖 API 仍可能無視 DisplayAffinity 拍到氣泡，
        # 在這裡做毫秒級的瞬間隱藏，截完圖立刻恢復。
        self.overlay.hide()
        QApplication.processEvents()

    def show_ui_after_scan(self):
        self.overlay.show()
        QApplication.processEvents()

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

    def on_local_model_status(self, state, detail=""):
        state = str(state or "failed")
        detail = str(detail or "")
        self.local_model_state = state
        self.local_model_detail = detail
        theme = resolve_theme(self.theme_mode)

        if state == "loading":
            colors = build_charge_bar_colors(theme, "normal")
            self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
            label = "Local Gemma3 載入中"
            self.charge_bar.set_indeterminate(True, label)
            self.lbl_status.setText("正在讀取內嵌模型並初始化 GPU...")
            return
        if state == "ready":
            colors = build_charge_bar_colors(theme, "normal")
            self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
            self.charge_bar.set_progress(100, "Local Gemma3 已就緒")
            self.lbl_status.setText("內嵌 Local Gemma3 已就緒")
            return

        colors = build_charge_bar_colors(theme, "danger")
        self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
        self.charge_bar.set_progress(0, "Local Gemma3 載入失敗")
        self.lbl_status.setText(f"內嵌模型載入失敗：{detail}" if detail else "內嵌模型載入失敗")

    def on_local_vision_status(self, state, detail=""):
        state = str(state or "failed")
        detail = str(detail or "")
        self.local_vision_state = state
        self.local_vision_detail = detail
        theme = resolve_theme(self.theme_mode)
        english = self.get_ui_language() == "en"

        if state == "progress":
            try:
                progress_text, phase = detail.split("|", 1)
                progress = max(0, min(100, int(progress_text)))
            except (TypeError, ValueError):
                progress, phase = 0, "starting_server"
            phase_labels = {
                "checking_disk": "Checking disk space" if english else "檢查磁碟空間",
                "checking_assets": "Checking model files" if english else "檢查模型檔案",
                "downloading": "Downloading Gemma model" if english else "下載 Gemma 模型",
                "verifying": "Verifying model files" if english else "驗證模型檔案",
                "starting_server": "Starting embedded server" if english else "啟動內嵌伺服器",
                "loading_model": "Reading Gemma model" if english else "讀取 Gemma 模型",
                "loading_tensors": "Loading model weights" if english else "載入模型權重",
                "initializing": "Initializing GPU and context" if english else "初始化 GPU 與上下文",
                "warming_up": "Warming up model" if english else "執行模型暖身",
                "model_loaded": "Model loaded, checking service" if english else "模型已載入，確認服務",
                "ready": "Model warm-up complete" if english else "模型暖身完成",
            }
            label = phase_labels.get(
                phase,
                "Loading Gemma Vision" if english else "載入 Gemma Vision",
            )
            colors = build_charge_bar_colors(theme, "normal")
            self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
            self.charge_bar.set_progress(progress, f"{label} {progress}%")
            suffix = "..." if progress < 100 else ""
            self.lbl_status.setText(f"{label}{suffix} ({progress}%)" if progress < 100 else label)
            return

        if state == "progress":
            try:
                progress_text, phase = detail.split("|", 1)
                progress = max(0, min(100, int(progress_text)))
            except (TypeError, ValueError):
                progress, phase = 0, "starting_server"
            phase_labels = {
                "checking_assets": "檢查模型檔案",
                "starting_server": "啟動內嵌伺服器",
                "loading_model": "讀取 Gemma 模型",
                "loading_tensors": "載入模型權重",
                "initializing": "初始化 GPU 與上下文",
                "warming_up": "執行模型暖身",
                "model_loaded": "模型已載入，確認服務",
                "ready": "模型暖身完成",
            }
            label = phase_labels.get(phase, "載入 Gemma Vision")
            colors = build_charge_bar_colors(theme, "normal")
            self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
            self.charge_bar.set_progress(progress, f"{label} {progress}%")
            self.lbl_status.setText(f"{label}... ({progress}%)" if progress < 100 else label)
            return

        if state == "starting":
            colors = build_charge_bar_colors(theme, "normal")
            self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
            label = "Loading Gemma Vision" if english else "Gemma Vision 載入中"
            self.charge_bar.set_indeterminate(True, label)
            self.lbl_status.setText(
                "Preparing the embedded multimodal engine..."
                if english else "正在準備內嵌多模態引擎..."
            )
            return
        if state == "ready":
            colors = build_charge_bar_colors(theme, "normal")
            self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])
            self.charge_bar.set_progress(100, "Gemma Vision ready" if english else "Gemma Vision 已就緒")
            self.lbl_status.setText(
                "Embedded Gemma Vision is ready"
                if english else "內嵌 Gemma Vision 已就緒"
            )
            return

        colors = build_charge_bar_colors(theme, "danger")
        self.charge_bar.set_theme_colors(colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"])

        if state == "missing":
            bar_text = "Vision model missing" if english else "缺少 Vision 模型"
            status_text = "Embedded multimodal model files were not found" if english else "找不到內嵌多模態模型檔案"
        elif state == "stopped":
            bar_text = "Vision stopped" if english else "Vision 已停止"
            status_text = "Embedded multimodal server stopped" if english else "內嵌多模態伺服器已停止"
        else:
            bar_text = "Gemma Vision failed" if english else "Gemma Vision 啟動失敗"
            status_text = "Embedded multimodal startup failed" if english else "內嵌多模態啟動失敗"

        if detail:
            status_text += (f": {detail}" if english else f"：{detail}")

        self.charge_bar.set_progress(0, bar_text)
        self.lbl_status.setText(status_text)
    def on_japanese_rescue_status(self, state, detail=""):
        state = str(state or "failed")
        detail = str(detail or "")
        if state == "disabled":
            return
        english = self.get_ui_language() == "en"
        labels = {
            "downloading": "Downloading Japanese OCR model" if english else "下載日文 OCR 模型",
            "warming_up": "Warming up Japanese OCR" if english else "暖身日文 OCR",
            "ready": "Japanese OCR ready" if english else "日文 OCR 已就緒",
            "preparing": "Preparing Japanese OCR" if english else "準備日文 OCR",
            "failed": "Japanese OCR failed" if english else "日文 OCR 啟動失敗",
        }
        theme = resolve_theme(self.theme_mode)
        colors = build_charge_bar_colors(theme, "danger" if state == "failed" else "normal")
        self.charge_bar.set_theme_colors(
            colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"]
        )
        if state == "progress":
            try:
                progress_text, phase = detail.split("|", 1)
                progress = max(0, min(100, int(progress_text)))
            except (TypeError, ValueError):
                progress, phase = 0, "downloading"
            label = labels.get(phase, labels["preparing"])
            self.charge_bar.set_progress(progress, f"{label} {progress}%")
            self.lbl_status.setText(f"{label}... ({progress}%)" if progress < 100 else label)
        elif state == "starting":
            self.charge_bar.set_indeterminate(True, labels["preparing"])
            self.lbl_status.setText(
                "Preparing Japanese game subtitle OCR in the background..."
                if english else "正在背景準備日文遊戲字幕 OCR..."
            )
        elif state == "ready":
            self.charge_bar.set_progress(100, labels["ready"])
            self.lbl_status.setText(
                "Accurate Japanese game subtitle OCR is ready"
                if english else "日文遊戲字幕精準 OCR 已就緒"
            )
        else:
            self.charge_bar.set_progress(0, labels["failed"])
            separator = ": " if english else "："
            self.lbl_status.setText(
                f"{labels['failed']}{separator}{detail}" if detail else labels["failed"]
            )

    def on_japanese_rescue_status(self, state, detail=""):
        state = str(state or "failed")
        detail = str(detail or "")
        if state == "disabled":
            return
        english = self.get_ui_language() == "en"
        labels = {
            "downloading": "Downloading Japanese OCR model" if english else "下載日文 OCR 模型",
            "warming_up": "Warming up Japanese OCR" if english else "暖身日文 OCR",
            "ready": "Japanese OCR ready" if english else "日文 OCR 已就緒",
            "preparing": "Preparing Japanese OCR" if english else "準備日文 OCR",
            "failed": "Japanese OCR failed" if english else "日文 OCR 啟動失敗",
        }
        theme = resolve_theme(self.theme_mode)
        colors = build_charge_bar_colors(theme, "danger" if state == "failed" else "normal")
        self.charge_bar.set_theme_colors(
            colors["base_bg"], colors["border_color"], colors["fill_color"], colors["text_color"]
        )
        if state == "progress":
            try:
                progress_text, phase = detail.split("|", 1)
                progress = max(0, min(100, int(progress_text)))
            except (TypeError, ValueError):
                progress, phase = 0, "downloading"
            label = labels.get(phase, labels["preparing"])
            self.charge_bar.set_progress(progress, f"{label} {progress}%")
            self.lbl_status.setText(f"{label}... ({progress}%)" if progress < 100 else label)
        elif state == "starting":
            self.charge_bar.set_indeterminate(True, labels["preparing"])
            self.lbl_status.setText(
                "Preparing Japanese game subtitle OCR in the background..."
                if english else "正在背景準備日文遊戲字幕 OCR..."
            )
        elif state == "ready":
            self.charge_bar.set_progress(100, labels["ready"])
            self.lbl_status.setText(
                "Accurate Japanese game subtitle OCR is ready"
                if english else "日文遊戲字幕精準 OCR 已就緒"
            )
        else:
            self.charge_bar.set_progress(0, labels["failed"])
            separator = ": " if english else "："
            self.lbl_status.setText(
                f"{labels['failed']}{separator}{detail}" if detail else labels["failed"]
            )

    def close_app(self):
        self.save_settings()
        if hasattr(self, 'worker'):
            self.worker.cleanup()
        if hasattr(self, 'hotkey_filter'):
            self.hotkey_filter.unregister_hotkey(self.winId())
            if QApplication.instance():
                QApplication.instance().removeNativeEventFilter(self.hotkey_filter)
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
        if hasattr(self.overlay, 'timer'):
            self.overlay.timer.stop()
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
