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

from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
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

from cloudhime_ui import Controller, OverlayWindow

if __name__ == "__main__":
    startup_log("main start")
    app = QApplication(sys.argv)
    
    # Apply Apple-style typography globally
    font = QFont("Helvetica Neue", 10)
    font.setStyleHint(QFont.SansSerif)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    startup_log("QApplication created")
    loaded_font = None
    for font_path in (
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msjhbd.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\mingliu.ttc",
    ):
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
            if families:
                loaded_font = families[0]
                app.setFont(QFont(loaded_font, 10))
                break
    if loaded_font is None:
        app.setFont(QFont("Microsoft JhengHei UI", 10))
    startup_log("font ready", loaded_font or "Microsoft JhengHei UI")
    
    overlay = OverlayWindow()
    startup_log("OverlayWindow created")
    overlay.show()
    startup_log("OverlayWindow shown")
    ctrl = Controller(overlay)
    startup_log("Controller created")
    ctrl.show()
    startup_log("Controller shown")
    sys.exit(app.exec())
