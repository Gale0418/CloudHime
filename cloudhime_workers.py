# ==========================================
# 🌟 雲朵翻譯姬 v3.0 - 螢幕 OCR 即時翻譯工具 (邏輯修正版) (｀・ω・´)ゞ
# ==========================================
# 核心引擎: Windows OCR 優先、可選 OCR 後端
# 翻譯引擎: Google + Gemma (多模態支援)
# 架構優化: 移除多餘引用，清理過期的 Argos 備援邏輯
# ==========================================

import os
import sys
from pathlib import Path
from cloudhime_logging import logger
import ctypes
import ctypes.wintypes
import hashlib
import difflib
import random
import re
import json
import time
import threading
import traceback
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
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
    translation_fallback_reason,
    should_fallback_to_text_translation,
    is_suspiciously_short_translation,
    score_ocr_candidate_text,
    choose_better_ocr_candidate,
    merge_google_lines_into_items
)
import translation_helpers as translation_tools
from exact_image_cache import ExactImageCache
import localization
from translation_registry import TranslationProviderRegistry, TranslationProviderRegistryConfig
from translation_providers import GemmaTranslationProvider, GoogleTranslationProvider, LocalGemmaProvider, LocalMultimodalProvider
from local_vision_runtime import LocalVisionRuntime
from local_vision_assets import (
    ensure_vision_model_assets,
    resolve_preferred_vision_assets,
)
from japanese_ocr_assets import resolve_japanese_ocr_assets
from japanese_ocr_runtime import JapaneseOCRRuntime, JapaneseOCRRuntimeState
from japanese_ocr_rescue import (
    build_verification_hint,
    decide_rescue_text,
    is_usable_meiki_candidate,
    rescue_gate,
)
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
LOCAL_GEMMA_MODEL_ID = "gemma-3-4b-it-local"
SETTINGS_PATHS = create_settings_paths(os.path.dirname(__file__))
MIN_BUBBLE_FONT_PT = 8
MIN_BUBBLE_WIDTH = 96
MIN_BUBBLE_HEIGHT = 42
SUPPORTED_AI_MODELS = [
    ("Gemma 3 4B (Local)", LOCAL_GEMMA_MODEL_ID),
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
MANGA_ADAPTIVE_MAX_REGIONS = 4
MANGA_ADAPTIVE_MIN_AREA_RATIO = 0.001
MANGA_ADAPTIVE_MAX_AREA_RATIO = 0.30
MANGA_ADAPTIVE_SCORE_MARGIN = 5
MANGA_ADAPTIVE_MIN_TEXT_AGREEMENT = 0.20
MANGA_ADAPTIVE_MIN_COVERAGE = 0.80
MANGA_ADAPTIVE_MAX_MS = 600
MANGA_CROP_CONTEXT_ENV = "CLOUDHIME_MANGA_CROP_CONTEXT"
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
from ocr_text_processing import normalize_ocr_text

class OCRWorker(QObject):
    finished = Signal(list)
    streaming_update = Signal(list)  # [(partial_text, x, y, w, h)] 打字機效果用
    translation_stream_update = Signal(int, str, str, int, int, int, int)  # (index, partial_text, provider, x, y, w, h) 串流翻譯用
    status_msg = Signal(str)
    hide_ui = Signal()
    show_ui = Signal()
    threshold_suggested = Signal(int)
    gemma_model_changed = Signal(str, str)
    local_model_status = Signal(str, str)
    local_vision_status = Signal(str, str)
    japanese_rescue_status = Signal(str, str)

    def __init__(self):
        super().__init__()
        startup_log("OCRWorker.__init__ start")
        self.ocr_backend_chain = []
        self.ocr_backends = []
        self.translators = {}
        self.last_combined_text = ""
        self.last_results = []
        self.last_provider = ""
        self.translation_cache = OrderedDict()
        self.hud_memory = OrderedDict()
        self.preferred_text_memory = OrderedDict()
        self.exact_image_cache = ExactImageCache(max_entries=4, max_bytes=32 * 1024 * 1024)
        self.gemma_call_timestamps = {model_name: [] for model_name in SUPPORTED_GEMMA_MODEL_NAMES}
        self._translation_registry_batch_depth = 0
        self._translation_registry_batch_dirty = False
        self._pending_gemma_prompt = ""
        self.translation_target_lang = localization.get_translation_target_lang(localization.DEFAULT_UI_LANGUAGE)
        self.google_translation_provider = GoogleTranslationProvider(target_lang=self.translation_target_lang)
        self.gemma_translation_provider = GemmaTranslationProvider(
            google_api_key="",
            gemma_model=DEFAULT_GEMMA_MODEL,
            gemma_prompt="",
            target_lang=self.translation_target_lang,
            auto_switch_enabled=False,
            supported_models=SUPPORTED_GEMMA_MODEL_NAMES,
        )
        app_root = Path(__file__).resolve().parent
        self._local_vision_assets = resolve_preferred_vision_assets(app_root)
        self.local_gemma_provider = LocalGemmaProvider(
            model_path=str(self._local_vision_assets.model_path),
            gemma_prompt="",
            target_lang=self.translation_target_lang,
            enabled=False
        )
        self.local_multimodal_provider = LocalMultimodalProvider(
            base_url="http://127.0.0.1:8080/v1",
            model_name="gemma-3-4b-it",
            target_lang=self.translation_target_lang,
            enabled=False,
            timeout_seconds=20,
        )
        self.local_multimodal_enabled = False
        self.local_multimodal_base_url = "http://127.0.0.1:8080/v1"
        self.local_multimodal_model = "gemma-3-4b-it"
        self.local_multimodal_timeout_seconds = 20
        self.japanese_rescue_enabled = False
        self.google_api_key = ""
        self.gemma_model = DEFAULT_GEMMA_MODEL
        self.active_gemma_model = self.gemma_model
        self.gemma_prompt = ""
        self.screenshot_gemma_prompt = ""
        self._pending_screenshot_gemma_prompt = ""
        self.use_gemma_translation = False
        self.google_ocr_enabled = False
        self.gemma_auto_switch_enabled = False
        self.scan_mode = SCAN_MODE_FULLSCREEN
        self.region_render_mode = REGION_RENDER_BUBBLE
        self.scan_region = None
        self.auto_threshold_enabled = True
        self.auto_threshold_refresh_interval_ms = DEFAULT_AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES * 60 * 1000
        self.last_auto_threshold_refresh_ms = 0.0
        self.translation_registry = None
        
        # 狀態標記
        
        self.binary_threshold = 100 
        self.last_scanned_img = None
        self.last_scanned_offset = (0, 0)
        self._bg_threshold_running = False  # 防止重複提交背景任務
        self._bg_threshold_executor = ThreadPoolExecutor(max_workers=1)
        self._local_model_executor = ThreadPoolExecutor(max_workers=1)
        self._local_model_load_future = None
        self._local_model_cancel_event = threading.Event()
        self._local_vision_executor = ThreadPoolExecutor(max_workers=1)
        self._local_vision_load_future = None
        self._local_vision_cancel_event = threading.Event()
        self._japanese_rescue_executor = ThreadPoolExecutor(max_workers=1)
        self._japanese_rescue_load_future = None
        self.japanese_rescue_runtime = JapaneseOCRRuntime(
            resolve_japanese_ocr_assets(),
            progress_callback=lambda phase, progress: OCRWorker._emit_japanese_rescue_status(
                self, "progress", f"{progress}|{phase}"
            ),
        )
        
        try:
            self.local_vision_runtime = LocalVisionRuntime(
                self._local_vision_assets,
                progress_callback=lambda phase, progress: OCRWorker._emit_local_vision_status(
                    self, "progress", f"{progress}|{phase}"
                ),
            )
        except Exception as exc:
            logger.error(f"Failed to init LocalVisionRuntime: {exc}")
            self.local_vision_runtime = None
        
        self.cc = OpenCC('s2t') if OPENCC_AVAILABLE else None
        self._refresh_translation_registry()
        startup_log(
            "OCRWorker.__init__ done",
            f"backends={len(self.ocr_backends)} registry={'ready' if self.translation_registry else 'none'}",
        )

    def trigger_background_threshold_refresh(self, img, offset_x, offset_y, mode):
        # 這是掃描結束後呼叫的觸發器
        if not self.auto_threshold_enabled or self._bg_threshold_running:
            return
        
        now_ms = time.monotonic() * 1000.0
        if self.last_auto_threshold_refresh_ms > 0 and (now_ms - self.last_auto_threshold_refresh_ms) < self.auto_threshold_refresh_interval_ms:
            return

        self._bg_threshold_running = True
        candidates_count = len(AUTO_THRESHOLD_CANDIDATES)
        logger.info(f"[BG閥值] 🔍 觸發背景自動校正，測試 {candidates_count} 個候選閥值...")
        self._bg_threshold_executor.submit(self._run_background_threshold, img.copy(), offset_x, offset_y, mode)

    def _run_background_threshold(self, img, offset_x, offset_y, mode):
        t0 = time.perf_counter()
        try:
            best_threshold, best_items = self.run_ocr_with_best_threshold(img, offset_x, offset_y, silent=True, force_bg_refresh=True)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[BG閥值] ✅ 校正完成！最佳閥值={best_threshold}，找到 {len(best_items)} 段文字，耗時 {elapsed_ms:.0f}ms")
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error(f"[BG閥值] ❌ 校正失敗：{type(exc).__name__}: {exc}，耗時 {elapsed_ms:.0f}ms")
        finally:
            # 無論成功或失敗，一定要清掉 flag，否則背景永遠不會再觸發
            self._bg_threshold_running = False

    def normalize_ocr_backend_chain(self, chain):
        if chain is None:
            return []
        if isinstance(chain, str):
            raw_items = [item.strip() for item in chain.split(",")]
        elif isinstance(chain, (list, tuple)):
            raw_items = [str(item).strip() for item in chain]
        else:
            raw_items = [str(chain).strip()]
        cleaned = []
        for item in raw_items:
            item = item.lower()
            if not item:
                continue
            if item in {"winrt", "winsdk", "windows-ocr", "windows_ocr"}:
                item = "windows"
            if item in {"rapid-ocr"}:
                item = "rapidocr"
            if item in {"easy-ocr"}:
                item = "easyocr"
            if item not in {"windows", "tesseract", "easyocr", "rapidocr"}:
                continue
            if item not in cleaned:
                cleaned.append(item)
        return cleaned

    def reload_ocr_backends(self, backend_chain=None, log=True):
        chain = self.normalize_ocr_backend_chain(
            backend_chain if backend_chain is not None else self.ocr_backend_chain
        )
        if backend_chain is not None and chain == self.ocr_backend_chain and self.ocr_backends:
            if log:
                names = ", ".join(backend.name for backend in self.ocr_backends)
                logger.info(f"[OCR] Available backends: {names}")
            return
        self.ocr_backend_chain = chain
        self.ocr_backends = discover_backends(chain)
        if not log:
            return
        if self.ocr_backends:
            names = ", ".join(backend.name for backend in self.ocr_backends)
            logger.info(f"[OCR] Available backends: {names}")
        else:
            logger.info("[OCR] No OCR backends available.")

    def _build_translation_registry_config(self):
        return TranslationProviderRegistryConfig(
            google_api_key=self.google_api_key,
            gemma_model=self.gemma_model,
            gemma_prompt=self.gemma_prompt,
            screenshot_gemma_prompt=self.screenshot_gemma_prompt,
            gemma_enabled=self.use_gemma_translation,
            gemma_auto_switch_enabled=self.gemma_auto_switch_enabled,
            target_lang=self.translation_target_lang,
            local_gemma_temperature=getattr(self, "local_gemma_temperature", 0.2),
            local_gemma_repeat_penalty=getattr(self, "local_gemma_repeat_penalty", 1.15),
            local_multimodal_enabled=getattr(self, "local_multimodal_enabled", False),
            local_multimodal_base_url=getattr(self, "local_multimodal_base_url", "http://127.0.0.1:8080/v1"),
            local_multimodal_model=getattr(self, "local_multimodal_model", "gemma-3-4b-it"),
            local_multimodal_timeout_seconds=getattr(self, "local_multimodal_timeout_seconds", 20),
        )

    def _refresh_translation_registry(self):
        if self._translation_registry_batch_depth > 0:
            self._translation_registry_batch_dirty = True
            return
        try:
            config = self._build_translation_registry_config()
            self.google_translation_provider.set_target_lang(config.target_lang)
            
            # API Provider config
            self.gemma_translation_provider.update_config(
                google_api_key=config.google_api_key,
                gemma_model=config.gemma_model,
                gemma_prompt=config.gemma_prompt,
                screenshot_gemma_prompt=config.screenshot_gemma_prompt,
                target_lang=config.target_lang,
                gemma_enabled=config.gemma_enabled,
                auto_switch_enabled=config.gemma_auto_switch_enabled,
                supported_models=config.supported_models,
            )
            
            # Local Provider config
            self.local_gemma_provider.update_config(
                gemma_prompt=config.gemma_prompt,
                target_lang=config.target_lang,
                gemma_enabled=config.gemma_enabled,
                temperature=config.local_gemma_temperature,
                repeat_penalty=config.local_gemma_repeat_penalty
            )
            
            self.local_multimodal_provider.target_lang = config.target_lang
            self.local_multimodal_provider.enabled = config.local_multimodal_enabled
            self.local_multimodal_provider.timeout_seconds = config.local_multimodal_timeout_seconds
            embedded_runtime = getattr(self, "local_vision_runtime", None)
            runtime_state = getattr(embedded_runtime, "_state", None)
            has_embedded_runtime = embedded_runtime is not None
            
            if has_embedded_runtime:
                if runtime_state is None or runtime_state.name != "ready":
                    self.local_multimodal_provider.update_runtime("", "", ready=False)
                else:
                    self.local_multimodal_provider.model_name = config.local_multimodal_model
            else:
                self.local_multimodal_provider.update_runtime(
                    config.local_multimodal_base_url,
                    config.local_multimodal_model,
                    ready=config.local_multimodal_enabled,
                )
            
            uses_shared_local_runtime = (
                config.gemma_model in {LOCAL_GEMMA_MODEL_ID, "translategemma-4b-it-local"}
                and config.local_multimodal_enabled
                and has_embedded_runtime
                and (runtime_state is None or runtime_state.name != "failed")
            )
            active_gemma = self.local_gemma_provider if config.gemma_model in {LOCAL_GEMMA_MODEL_ID, "translategemma-4b-it-local"} else self.gemma_translation_provider
            active_gemma.name = "gemma"
            
            self.translation_registry = TranslationProviderRegistry([
                active_gemma,
                self.google_translation_provider,
                self.local_multimodal_provider,
            ])
            if uses_shared_local_runtime:
                self.translation_registry.register("gemma", self.local_multimodal_provider)
            self.request_local_model_load()
            self.request_local_vision_start()
        except Exception:
            self.translation_registry = None

    def _prepare_and_load_local_model(self):
        assets = getattr(self, "_local_vision_assets", None)
        if assets is not None:
            ensure_vision_model_assets(
                assets,
                progress_callback=lambda phase, progress: OCRWorker._emit_local_vision_status(
                    self, "progress", f"{progress}|{phase}"
                ),
                cancel_event=getattr(self, "_local_model_cancel_event", None),
            )
        return self.local_gemma_provider.load_model()
    def request_local_model_load(self):
        if not self.use_gemma_translation or not self._is_local_model_active():
            return
        vision_runtime = getattr(self, "local_vision_runtime", None)
        vision_state = getattr(vision_runtime, "_state", None)
        if (
            getattr(self, "local_multimodal_enabled", False)
            and vision_runtime is not None
            and (vision_state is None or vision_state.name != "failed")
        ):
            return
        if self.local_gemma_provider.available():
            OCRWorker._emit_local_model_status(self, "ready", "")
            return
        if self._local_model_load_future is not None and not self._local_model_load_future.done():
            return

        OCRWorker._emit_local_model_status(self, "loading", "")
        try:
            cancel_event = getattr(self, "_local_model_cancel_event", None)
            if cancel_event is not None:
                cancel_event.clear()
            future = self._local_model_executor.submit(
                lambda: OCRWorker._prepare_and_load_local_model(self)
            )
        except Exception as exc:
            self._local_model_load_future = None
            OCRWorker._emit_local_model_status(self, "failed", f"{type(exc).__name__}: {exc}")
            return
        self._local_model_load_future = future
        future.add_done_callback(
            lambda completed: OCRWorker._on_local_model_load_done(self, completed)
        )

    def _on_local_model_load_done(self, future):
        if self._local_model_load_future is not future:
            return
        self._local_model_load_future = None
        try:
            ready = bool(future.result())
        except Exception as exc:
            OCRWorker._emit_local_model_status(self, "failed", f"{type(exc).__name__}: {exc}")
            return
        if ready:
            OCRWorker._emit_local_model_status(self, "ready", "")
            return
        OCRWorker._emit_local_model_status(self, 
            "failed",
            getattr(self.local_gemma_provider, "last_load_error", "") or "local_model_unavailable",
        )

    def _emit_local_model_status(self, *args):
        try:
            signal = getattr(self, "local_model_status", None)
        except RuntimeError:
            return
        if signal is not None:
            signal.emit(*args)

    def _emit_local_vision_status(self, *args):
        try:
            signal = getattr(self, "local_vision_status", None)
        except RuntimeError:
            return
        if signal is not None:
            signal.emit(*args)

    def _emit_japanese_rescue_status(self, *args):
        try:
            signal = getattr(self, "japanese_rescue_status", None)
        except RuntimeError:
            return
        if signal is not None:
            signal.emit(*args)

    def request_japanese_rescue_start(self):
        if not self.japanese_rescue_enabled:
            return
        runtime = getattr(self, "japanese_rescue_runtime", None)
        if runtime is None:
            OCRWorker._emit_japanese_rescue_status(self, "failed", "runtime_missing")
            return
        if runtime.state is JapaneseOCRRuntimeState.ready:
            OCRWorker._emit_japanese_rescue_status(self, "ready", "")
            return
        pending = self._japanese_rescue_load_future
        if pending is not None and not pending.done():
            return
        OCRWorker._emit_japanese_rescue_status(self, "starting", "")
        try:
            future = self._japanese_rescue_executor.submit(runtime.start)
        except Exception as exc:
            self._japanese_rescue_load_future = None
            OCRWorker._emit_japanese_rescue_status(
                self, "failed", f"{type(exc).__name__}: {exc}"
            )
            return
        self._japanese_rescue_load_future = future
        future.add_done_callback(lambda completed: OCRWorker._on_japanese_rescue_start_done(self, completed))

    def _on_japanese_rescue_start_done(self, future):
        if self._japanese_rescue_load_future is not future:
            return
        self._japanese_rescue_load_future = None
        try:
            ready = bool(future.result())
        except Exception as exc:
            OCRWorker._emit_japanese_rescue_status(self, "failed", f"{type(exc).__name__}: {exc}")
            return
        runtime = self.japanese_rescue_runtime
        if ready:
            OCRWorker._emit_japanese_rescue_status(self, "ready", "")
        elif runtime.state is JapaneseOCRRuntimeState.disabled:
            OCRWorker._emit_japanese_rescue_status(self, "disabled", "")
        else:
            OCRWorker._emit_japanese_rescue_status(self, "failed", runtime.last_error)

    def _prepare_and_start_local_vision(self):
        assets = getattr(self, "_local_vision_assets", None)
        if assets is not None:
            ensure_vision_model_assets(
                assets,
                progress_callback=lambda phase, progress: OCRWorker._emit_local_vision_status(
                    self, "progress", f"{progress}|{phase}"
                ),
                cancel_event=getattr(self, "_local_vision_cancel_event", None),
            )
        return self.local_vision_runtime.start()
    def request_local_vision_start(self):
        if not self.use_gemma_translation or not self.local_multimodal_enabled:
            return
        if getattr(self, "local_vision_runtime", None) is None:
            OCRWorker._emit_local_vision_status(self, "failed", "runtime_missing")
            return
        
        state = getattr(self.local_vision_runtime, "_state", None)
        if state is not None and state.name == "ready":
            self.local_multimodal_provider.update_runtime(
                state.base_url,
                getattr(self, "local_multimodal_model", "gemma-3-4b-it"),
                ready=True,
            )
            OCRWorker._emit_local_vision_status(self, state.name, state.detail)
            return
            
        pending_future = getattr(self, "_local_vision_load_future", None)
        if pending_future is not None and not pending_future.done():
            return

        OCRWorker._emit_local_vision_status(self, "starting", "")
        executor = getattr(self, "_local_vision_executor", getattr(self, "vision_executor", None))
        if executor is None:
            OCRWorker._emit_local_vision_status(self, "failed", "vision_executor_missing")
            return
        try:
            cancel_event = getattr(self, "_local_vision_cancel_event", None)
            if cancel_event is not None:
                cancel_event.clear()
            future = executor.submit(
                lambda: OCRWorker._prepare_and_start_local_vision(self)
            )
        except Exception as exc:
            self._local_vision_load_future = None
            self.local_multimodal_provider.update_runtime("", "", False)
            OCRWorker._emit_local_vision_status(self, "failed", f"{type(exc).__name__}: {exc}")
            return

        self._local_vision_load_future = future
        future.add_done_callback(
            lambda completed: OCRWorker._on_local_vision_load_done(self, completed)
        )

    def _restore_configured_text_provider(self):
        registry = getattr(self, "translation_registry", None)
        if registry is None:
            return
        provider_name = (
            "local_gemma_provider"
            if self._is_local_model_active()
            else "gemma_translation_provider"
        )
        provider = getattr(self, provider_name, None)
        if provider is not None:
            registry.register("gemma", provider)
    def _on_local_vision_load_done(self, future):
        if self._local_vision_load_future is future:
            self._local_vision_load_future = None
        try:
            state = future.result()
        except Exception as exc:
            self.local_multimodal_provider.update_runtime("", "", False)
            OCRWorker._restore_configured_text_provider(self)

            OCRWorker._emit_local_vision_status(self, "failed", f"{type(exc).__name__}: {exc}")
            return
            
        self.local_multimodal_provider.update_runtime(
            state.base_url if state.name == "ready" else "",
            getattr(self, "local_multimodal_model", "gemma-3-4b-it") if state.name == "ready" else "",
            ready=state.name == "ready",
        )
        if state.name == "ready":
            self._refresh_translation_registry()
        else:
            OCRWorker._restore_configured_text_provider(self)
            self.request_local_model_load()
        OCRWorker._emit_local_vision_status(self, state.name, state.detail)

    request_local_vision_load = request_local_vision_start

    def shutdown_local_vision_runtime(self):
        cancel_event = getattr(self, "_local_vision_cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()
        runtime = getattr(self, "local_vision_runtime", None)
        if runtime is not None:
            runtime.stop()
        executor = getattr(self, "_local_vision_executor", getattr(self, "vision_executor", None))
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=False)

    def shutdown_local_model_loader(self):
        cancel_event = getattr(self, "_local_model_cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()
        executor = getattr(self, "_local_model_executor", None)
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=False)

    def _clear_translation_memories(self):
        """清除可能把舊語言、prompt 或影像結果帶回翻譯流程的 worker 記憶。"""
        for memory_name in (
            "translation_cache",
            "preferred_text_memory",
            "hud_memory",
            "exact_image_cache",
        ):
            memory = getattr(self, memory_name, None)
            if hasattr(memory, "clear"):
                memory.clear()
        self.last_combined_text = ""
        self.last_results = []
        self.last_provider = ""

    def _exact_image_cache_context(self, offset_x, offset_y):
        region = getattr(self, "scan_region", None)
        if region is None:
            region_key = None
        elif hasattr(region, "x") and callable(region.x):
            region_key = (region.x(), region.y(), region.width(), region.height())
        else:
            try:
                region_key = tuple(int(value) for value in region)
            except (TypeError, ValueError):
                region_key = repr(region)

        backend_names = tuple(
            str(getattr(backend, "name", type(backend).__name__))
            for backend in getattr(self, "ocr_backends", ())
        )
        threshold_value = int(getattr(self, "binary_threshold", 100))
        japanese_rescue_ready = (
            getattr(getattr(self, "japanese_rescue_runtime", None), "state", None)
            is JapaneseOCRRuntimeState.ready
        )

        return (
            "exact-image-v1",
            getattr(self, "scan_mode", SCAN_MODE_FULLSCREEN),
            getattr(self, "region_render_mode", REGION_RENDER_BUBBLE),
            region_key,
            int(offset_x),
            int(offset_y),
            getattr(self, "translation_target_lang", "zh-TW"),
            tuple(getattr(self, "ocr_backend_chain", ()) or ()),
            backend_names,
            threshold_value,
            bool(getattr(self, "auto_threshold_enabled", False)),
            bool(getattr(self, "google_ocr_enabled", False)),
            bool(getattr(self, "japanese_rescue_enabled", False)),
            japanese_rescue_ready,
            bool(getattr(self, "use_gemma_translation", False)),
            bool(getattr(self, "gemma_auto_switch_enabled", False)),
            getattr(self, "gemma_model", ""),
            getattr(self, "gemma_prompt", ""),
            getattr(self, "screenshot_gemma_prompt", ""),
            bool(getattr(self, "google_api_key", "")),
            bool(getattr(self, "local_multimodal_enabled", False)),
            getattr(self, "local_multimodal_base_url", ""),
            getattr(self, "local_multimodal_model", ""),
            float(getattr(self, "local_gemma_temperature", 0.2)),
            float(getattr(self, "local_gemma_repeat_penalty", 1.15)),
        )

    def _canonical_cache_provider(self, provider):
        normalized = str(provider or "").strip().lower()
        if normalized in {"gemma", "local_multimodal"}:
            return self.get_current_ai_provider()
        return normalized

    def _current_cache_provider(self):
        if self.has_any_multimodal_ai() or self.has_ai_text_provider():
            return self.get_current_ai_provider()
        return "google"

    def set_translation_target_lang(self, target_lang):
        normalized = localization.get_translation_target_lang(target_lang)
        if normalized == getattr(self, "translation_target_lang", localization.DEFAULT_UI_LANGUAGE):
            return
        self.translation_target_lang = normalized
        self._clear_translation_memories()
        self._refresh_translation_registry()

    def begin_translation_registry_batch(self):
        self._translation_registry_batch_depth += 1

    def end_translation_registry_batch(self):
        if self._translation_registry_batch_depth <= 0:
            self._translation_registry_batch_depth = 0
            return
        self._translation_registry_batch_depth -= 1
        if self._translation_registry_batch_depth == 0 and self._translation_registry_batch_dirty:
            self._translation_registry_batch_dirty = False
            self._refresh_translation_registry()

    def _get_translation_provider(self, provider_name):
        registry = self.translation_registry
        if registry is None:
            return None
        try:
            provider = registry.get(provider_name)
        except Exception:
            return None
        if provider is None or not provider.available():
            return None
        return provider

    def _recognize_with_backends(self, img_np):
        if not self.ocr_backends:
            return None
        best_result = None
        best_score = float("-inf")
        best_any_result = None
        best_any_score = float("-inf")
        for backend in self.ocr_backends:
            try:
                result = backend.recognize(img_np)
            except Exception:
                continue
            if not result or not result.lines:
                continue
            raw_items = self.extract_raw_items(result, 1.0, 0, 0)
            score, filtered_items = self.score_ocr_items(raw_items)
            if score > best_any_score:
                best_any_score = score
                best_any_result = result
            if score > best_score and filtered_items:
                best_score = score
                best_result = result
        return best_result or best_any_result

    def convert_to_trad(self, text):
        return translation_tools.convert_to_trad(text, self.cc)

    def set_google_api_key(self, api_key):
        self.google_api_key = (api_key or "").strip()
        self._refresh_translation_registry()

    def set_gemma_enabled(self, enabled):
        self.use_gemma_translation = bool(enabled)
        if not self.use_gemma_translation:
            for name in ("_local_model_cancel_event", "_local_vision_cancel_event"):
                cancel_event = getattr(self, name, None)
                if cancel_event is not None:
                    cancel_event.set()
        self._refresh_translation_registry()

    def set_gemma_auto_switch_enabled(self, enabled):
        self.gemma_auto_switch_enabled = bool(enabled)
        self._refresh_translation_registry()

    def set_gemma_model(self, model_name):
        model_name = (model_name or "").strip()
        self.gemma_model = model_name or DEFAULT_GEMMA_MODEL
        self.active_gemma_model = self.gemma_model
        self._refresh_translation_registry()

    def set_japanese_rescue_enabled(self, enabled):
        self.japanese_rescue_enabled = bool(enabled)
        if self.japanese_rescue_enabled:
            self.request_japanese_rescue_start()
        else:
            self.japanese_rescue_runtime.disable()
            OCRWorker._emit_japanese_rescue_status(self, "disabled", "")

    def set_local_multimodal_config(self, *, enabled, base_url, model_name, timeout_seconds):
        self.local_multimodal_enabled = bool(enabled)
        if not self.local_multimodal_enabled:
            cancel_event = getattr(self, "_local_vision_cancel_event", None)
            if cancel_event is not None:
                cancel_event.set()
        self.local_multimodal_base_url = (base_url or "").rstrip("/")
        self.local_multimodal_model = (model_name or "").strip()
        self.local_multimodal_timeout_seconds = max(1, int(timeout_seconds))
        self._refresh_translation_registry()


    def set_gemma_prompt(self, prompt):
        normalized = (prompt or "").strip()
        changed = normalized != getattr(self, "gemma_prompt", "")
        self.gemma_prompt = normalized
        if changed:
            self._clear_translation_memories()
        self._refresh_translation_registry()

    def set_screenshot_gemma_prompt(self, prompt):
        normalized = (prompt or "").strip()
        changed = normalized != getattr(self, "screenshot_gemma_prompt", "")
        self.screenshot_gemma_prompt = normalized
        if changed:
            self._clear_translation_memories()
        self._refresh_translation_registry()
    def set_local_gemma_params(self, temperature, repeat_penalty):
        try:
            temperature = float(temperature)
            repeat_penalty = float(repeat_penalty)
        except (TypeError, ValueError) as exc:
            raise TypeError("temperature and repeat_penalty must be numeric") from exc

        if not 0.0 <= temperature <= 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")
        if not 1.0 <= repeat_penalty <= 2.0:
            raise ValueError("repeat_penalty must be between 1.0 and 2.0")

        self.local_gemma_temperature = temperature
        self.local_gemma_repeat_penalty = repeat_penalty
        self._refresh_translation_registry()

    def set_scan_mode(self, scan_mode):
        self.scan_mode = scan_mode if scan_mode in (SCAN_MODE_FULLSCREEN, SCAN_MODE_REGION) else SCAN_MODE_FULLSCREEN

    def set_region_render_mode(self, render_mode):
        render_mode = str(render_mode or REGION_RENDER_BUBBLE)
        if render_mode not in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF, REGION_RENDER_SCREENSHOT):
            render_mode = REGION_RENDER_BUBBLE
        self.region_render_mode = render_mode

    def set_scan_region(self, rect):
        self.scan_region = rect if rect and rect[2] > 0 and rect[3] > 0 else None

    def set_binary_threshold(self, threshold):
        normalized = max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, int(threshold)))
        if normalized == getattr(self, "binary_threshold", normalized):
            self.binary_threshold = normalized
            return normalized
        self.binary_threshold = normalized
        cache = getattr(self, "exact_image_cache", None)
        if hasattr(cache, "clear"):
            cache.clear()
        return normalized

    def set_auto_threshold_enabled(self, enabled):
        self.auto_threshold_enabled = bool(enabled)
        if not self.auto_threshold_enabled:
            self.last_auto_threshold_refresh_ms = 0.0

    def set_auto_threshold_refresh_interval_minutes(self, minutes):
        minutes = max(
            AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MIN,
            min(AUTO_THRESHOLD_REFRESH_INTERVAL_MINUTES_MAX, int(minutes)),
        )
        self.auto_threshold_refresh_interval_ms = minutes * 60 * 1000

    def has_remote_multimodal_ai(self):
        return self.use_gemma_translation and bool(self.google_api_key) and not self._is_local_model_active()

    def has_local_multimodal_ai(self):
        return (
            self.use_gemma_translation
            and bool(getattr(self, "local_multimodal_enabled", False))
            and bool(getattr(self, "local_multimodal_model", ""))
        )

    def has_any_multimodal_ai(self):
        return self.has_remote_multimodal_ai() or self.has_local_multimodal_ai()

    def has_multimodal_ai(self):
        return self.has_any_multimodal_ai()

    def has_ai_text_provider(self):
        return self.use_gemma_translation and self._get_translation_provider("gemma") is not None

    def _is_local_model_active(self):
        model = getattr(self, "active_gemma_model", self.gemma_model) or self.gemma_model
        return model in {LOCAL_GEMMA_MODEL_ID, "translategemma-4b-it-local"}

    def resolve_multimodal_provider_name(self):
        if self.has_local_multimodal_ai():
            return "local_multimodal"
        if self.has_remote_multimodal_ai():
            return "gemma"
        return None

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
        if not self.has_remote_multimodal_ai():
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
        if not self.has_remote_multimodal_ai():
            self.active_gemma_model = preferred_model
            return preferred_model
        if self.can_call_gemma(preferred_model):
            self.active_gemma_model = preferred_model
            return preferred_model
        if self.gemma_auto_switch_enabled:
            for candidate in SUPPORTED_GEMMA_MODEL_NAMES:
                if candidate == preferred_model:
                    continue
                if self.can_call_gemma(candidate):
                    self.active_gemma_model = candidate
                    return candidate
        self.active_gemma_model = preferred_model
        return preferred_model

    def detect_source_language(self, text):
        return translation_tools.detect_source_language(text)

    def get_google_translator(self, source_lang):
        return translation_tools.get_google_translator(self.translators, source_lang)

    def get_cached_translation(self, cache_key):
        return translation_tools.get_cached_translation(self.translation_cache, cache_key)

    def remember_translation(self, cache_key, translated_text):
        translation_tools.remember_translation(self.translation_cache, cache_key, translated_text, TRANSLATION_CACHE_LIMIT)


    def cleanup(self):
        if hasattr(self, '_bg_threshold_executor'):
            self._bg_threshold_executor.shutdown(wait=True)
        if hasattr(self, 'japanese_rescue_runtime'):
            self.japanese_rescue_runtime.disable()
        if hasattr(self, '_japanese_rescue_executor'):
            self._japanese_rescue_executor.shutdown(wait=True)
        self.shutdown_local_vision_runtime()
        self.shutdown_local_model_loader()

    def get_translation_provider_priority(self, provider):
        return translation_tools.get_translation_provider_priority(provider)

    def get_current_ai_provider(self):
        model = (getattr(self, "active_gemma_model", self.gemma_model) or self.gemma_model or "").strip().lower()
        if self._is_local_model_active():
            return "gemma-3"
        if "gemma-4" in model:
            return "gemma-4"
        if "gemma-3" in model:
            return "gemma-3"
        return "google"

    def sync_gemma_call_timestamps_from_provider(self, provider):
        timestamps = getattr(provider, "_call_timestamps", None)
        if not isinstance(timestamps, dict):
            return
        self.gemma_call_timestamps = {
            model_name: list(timestamps.get(model_name, []))
            for model_name in SUPPORTED_GEMMA_MODEL_NAMES
        }

    def should_replace_provider(self, old_provider, new_provider):
        return translation_tools.should_replace_provider(old_provider, new_provider)

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
        provider = self._get_translation_provider("google")
        if provider is not None:
            normalized_text = normalize_ocr_text(text)
            if not normalized_text:
                return ""
            result = provider.translate(normalized_text)
            self.log_translation_debug(
                f"google single {'hit' if getattr(result, 'from_cache', False) else 'miss'} "
                f"source={normalized_text!r}"
            )
            return result.text
        return translation_tools.translate_text_google(
            text,
            self.translators,
            self.translation_cache,
            target_lang=self.translation_target_lang,
            cache_limit=TRANSLATION_CACHE_LIMIT,
        )

    def translate_text_google_with_provider(self, text):
        provider = self._get_translation_provider("google")
        if provider is not None:
            normalized_text = normalize_ocr_text(text)
            if not normalized_text:
                return "", provider.name
            result = provider.translate(normalized_text)
            return result.text, result.provider
        return self.translate_text_google(text), "google"

    def translate_text_google_batch(self, source_texts):
        provider = self._get_translation_provider("google")
        if provider is not None:
            normalized_texts = [normalize_ocr_text(text) for text in source_texts]
            if not normalized_texts or any(not text for text in normalized_texts):
                return []
            results = provider.translate_batch(normalized_texts)
            if len(results) != len(normalized_texts):
                return []
            cache_hits = sum(1 for item in results if getattr(item, "from_cache", False))
            self.log_translation_debug(
                f"google batch hits={cache_hits}/{len(results)} source_count={len(normalized_texts)}"
            )
            return [item.text for item in results]
        return translation_tools.translate_text_google_batch(
            source_texts,
            self.translators,
            self.translation_cache,
            target_lang=self.translation_target_lang,
            cache_limit=TRANSLATION_CACHE_LIMIT,
        )

    def build_gemma_prompt(self, text):
        return translation_tools.build_gemma_prompt(text)

    def build_gemma_text_prompt(self, text, model_name=None):
        target_lang = getattr(
            self,
            "translation_target_lang",
            localization.get_translation_target_lang(localization.DEFAULT_UI_LANGUAGE),
        )
        model_name = model_name or getattr(self, "gemma_model", DEFAULT_GEMMA_MODEL)
        return translation_tools.build_gemma_prompt_with_override(
            text,
            getattr(self, "gemma_prompt", ""),
            target_lang=target_lang,
            model_name=model_name,
        )

    def extract_gemma_text(self, payload):
        return translation_tools.extract_gemma_text(payload)

    def build_gemma_prompt_v2(self, text):
        return translation_tools.build_gemma_prompt_v2(text)

    def build_segmented_ocr_payload(self, source_texts):
        return translation_tools.build_segmented_ocr_payload(source_texts)

    def build_gemma_multimodal_prompt(self, source_texts):
        target_lang = getattr(
            self,
            "translation_target_lang",
            localization.get_translation_target_lang(localization.DEFAULT_UI_LANGUAGE),
        )
        base_prompt = translation_tools.build_gemma_multimodal_prompt(
            source_texts,
            target_lang=target_lang,
        )
        custom_prompt = getattr(self, "gemma_prompt", "").strip()
        if not custom_prompt:
            return base_prompt
        return f"{custom_prompt}\n\n{base_prompt}"

    def split_translated_lines(self, translated_text, expected_count):
        return translation_tools.split_translated_lines(translated_text, expected_count)

    def clean_model_output(self, text):
        return translation_tools.clean_model_output(text)

    def parse_segmented_translation_json(self, text, expected_count):
        return translation_tools.parse_segmented_translation_json(text, expected_count)

    def encode_image_for_ai(self, img_np):
        return translation_tools.encode_image_for_ai(img_np, max_width=AI_IMAGE_MAX_WIDTH)

    def build_ai_image_parts(self, img_np):
        return translation_tools.build_ai_image_parts(img_np, max_width=AI_IMAGE_MAX_WIDTH)

    def _collect_screenshot_hint_items(self, ocr_result, min_confidence=0.35):
        raw_items = []
        for line in getattr(ocr_result, "lines", []) or []:
            text = normalize_ocr_text(getattr(line, "text", "") or "")
            if not text:
                continue
            if any(
                marker in text
                for marker in (
                    "?????",
                    "??????",
                    "?????",
                    "????",
                    "??",
                    "??",
                    "Gemma",
                    "OCR",
                    "v3.0",
                    "5s",
                )
            ):
                continue
            confidence = getattr(line, "confidence", None)
            try:
                confidence = float(confidence) if confidence is not None else None
            except Exception:
                confidence = None
            if confidence is not None and confidence < min_confidence:
                continue
            box = getattr(line, "box", None)
            x = int(getattr(box, "x", 0) or 0)
            y = int(getattr(box, "y", 0) or 0)
            w = max(1, int(getattr(box, "w", 1) or 1))
            h = max(1, int(getattr(box, "h", 1) or 1))
            raw_items.append({
                "text": self.convert_to_trad(text),
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "confidence": confidence,
            })
        return raw_items

    def build_screenshot_text_hint(self, img_np):
        if not self.ocr_backends:
            return ""
        try:
            h, w = img_np.shape[:2]
            img_scaled = cv2.resize(img_np, (int(w * 2.0), int(h * 2.0)), interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(img_scaled, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
            _, binary = cv2.threshold(gray, self.binary_threshold, 255, cv2.THRESH_BINARY)
            _, clahe_binary = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            adaptive = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                11,
            )
            variants = [
                ("color_scaled", img_scaled),
                ("gray_scaled", cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)),
                ("binary_invert", cv2.cvtColor(cv2.bitwise_not(binary), cv2.COLOR_GRAY2BGR)),
                ("clahe_gray", cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR)),
                ("clahe_otsu_invert", cv2.cvtColor(cv2.bitwise_not(clahe_binary), cv2.COLOR_GRAY2BGR)),
                ("adaptive_invert", cv2.cvtColor(cv2.bitwise_not(adaptive), cv2.COLOR_GRAY2BGR)),
            ]
        except Exception:
            return ""

        best_items = []
        best_score = -1
        for _, variant_img in variants:
            try:
                ocr_result = self._recognize_with_backends(variant_img)
            except Exception:
                continue
            if not ocr_result or not getattr(ocr_result, "lines", None):
                continue
            raw_items = self._collect_screenshot_hint_items(ocr_result, min_confidence=0.35)
            if not raw_items:
                continue
            score, filtered_items = quality_score_ocr_items(raw_items)
            if score > best_score:
                best_score = score
                best_items = filtered_items
            if score >= 16 and filtered_items:
                best_items = filtered_items
                break
        if not best_items:
            return ""
        hint = quality_summarize_threshold_candidate(best_items, max_items=6, max_chars=180).strip()
        if len(hint) < 4:
            return ""
        return hint[:400]



    def log_ai_debug(self, message):
        from cloudhime_logging import log_ai_debug
        log_ai_debug(message)

    def log_translation_debug(self, message):
        from cloudhime_logging import log_translation_debug
        log_translation_debug(message)



    def refine_merged_items_with_google_ocr(self, items, image_parts):
        if not self.google_ocr_enabled or not self.google_api_key:
            return list(items)
        provider = self._get_translation_provider("gemma")
        if provider is None or not hasattr(provider, "transcribe_screenshot"):
            return list(items)
        try:
            source_hint = "\n".join(
                normalize_ocr_text(item.get("text", ""))
                for item in items
                if normalize_ocr_text(item.get("text", ""))
            )
            result = provider.transcribe_screenshot(image_parts, source_text_hint=source_hint)
            self.sync_gemma_call_timestamps_from_provider(provider)
            google_lines = [normalize_ocr_text(line) for line in str(result.text or "").splitlines() if normalize_ocr_text(line)]
        except Exception:
            return list(items)
        return merge_google_lines_into_items(google_lines, items)

    def translate_text_gemma(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return ""
        provider = self._get_translation_provider("gemma")
        if provider is not None:
            result = provider.translate(normalized_text)
            provider_model = self.normalize_gemma_model(result.model or self.gemma_model)
            self.active_gemma_model = provider_model
            self.sync_gemma_call_timestamps_from_provider(provider)
            return self.convert_to_trad(result.text)
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        model_name = self.resolve_gemma_model_for_call(self.gemma_model)
        if not self.can_call_gemma(model_name):
            raise ValueError("gemma_rate_limited")

        target_lang = getattr(
            self,
            "translation_target_lang",
            localization.get_translation_target_lang(localization.DEFAULT_UI_LANGUAGE),
        )
        effective_prompt = self.build_gemma_text_prompt(normalized_text, model_name)
        cache_key = ("gemma", model_name, normalized_text, target_lang, effective_prompt)
        cached = self.get_cached_translation(cache_key)
        if cached is not None:
            return cached

        req_body = {
            "contents": [{
                "parts": [{
                    "text": effective_prompt
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
        self.record_gemma_call(model_name)
        with request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        translated = self.clean_model_output(self.extract_gemma_text(payload))
        if not translated:
            raise ValueError("empty_gemma_response")

        translated = self.convert_to_trad(translated)
        self.remember_translation(cache_key, translated)
        return translated

    def translate_multimodal_gemma(self, image_parts, source_texts):
        if not source_texts:
            return ""
        provider_name = self.resolve_multimodal_provider_name()
        provider = self._get_translation_provider(provider_name) if provider_name else None
        if provider is not None:
            results = provider.translate_multimodal(
                source_texts,
                image_parts,
                target_lang=self.translation_target_lang,
            )
            if results:
                provider_model = self.normalize_gemma_model(results[0].model or self.gemma_model)
                self.active_gemma_model = provider_model
                self.sync_gemma_call_timestamps_from_provider(provider)
                translated_text = {
                    "segments": [
                        {"index": index, "translation": self.convert_to_trad(item.text)}
                        for index, item in enumerate(results)
                        if item.text
                    ]
                }
                return json.dumps(translated_text, ensure_ascii=False)
            raise ValueError("empty_gemma_multimodal_response")
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        if not image_parts:
            raise ValueError("missing_image_context")
        model_name = self.resolve_gemma_model_for_call(self.gemma_model)
        if not self.can_call_gemma(model_name):
            raise ValueError("gemma_rate_limited")

        normalized_texts = tuple(normalize_ocr_text(text) for text in source_texts)
        target_lang = getattr(
            self,
            "translation_target_lang",
            localization.get_translation_target_lang(localization.DEFAULT_UI_LANGUAGE),
        )
        effective_prompt = self.build_gemma_multimodal_prompt(source_texts)
        image_seed = json.dumps(image_parts, sort_keys=True, ensure_ascii=False)
        image_digest = hashlib.sha256(image_seed.encode("utf-8")).hexdigest()
        cache_key = ("gemma-mm", model_name, normalized_texts, image_digest, target_lang, effective_prompt)
        cached = self.get_cached_translation(cache_key)
        if cached is not None:
            return cached

        req_body = {
            "contents": [{
                "parts": image_parts + [{
                    "text": effective_prompt
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
        self.record_gemma_call(model_name)
        with request.urlopen(req, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))

        translated = self.convert_to_trad(self.extract_gemma_text(payload))
        if not translated:
            raise ValueError("empty_gemma_multimodal_response")

        self.remember_translation(cache_key, translated)
        return translated

    def translate_screenshot_gemma(self, image_parts, source_text_hint=""):
        if not image_parts:
            raise ValueError("missing_image_context")
        self._last_screenshot_translation_provider = ""
        self.log_ai_debug(
            "\n".join([
                "[screenshot start]",
                f"scan_mode={self.scan_mode}",
                f"region_render_mode={self.region_render_mode}",
                f"image_parts={len(image_parts)}",
                f"source_text_hint_len={len(source_text_hint or '')}",
            ])
        )
        provider_name = self.resolve_multimodal_provider_name()
        provider = self._get_translation_provider(provider_name) if provider_name else None
        if provider is not None:
            result = provider.translate_screenshot(
                image_parts,
                target_lang=self.translation_target_lang,
                source_text_hint=source_text_hint,
                debug_log=self.log_ai_debug,
            )
            provider_model = self.normalize_gemma_model(result.model or self.gemma_model)
            self.active_gemma_model = provider_model
            self.sync_gemma_call_timestamps_from_provider(provider)
            translated = self.convert_to_trad(result.text)
            fallback_reason = translation_fallback_reason(
                source_text_hint,
                translated,
                target_lang=self.translation_target_lang,
            )
            primary_provider = provider_name or self.get_current_ai_provider()
            if fallback_reason:
                self._log_translation_fallback_reason(
                    fallback_reason,
                    source_text_hint,
                    translated,
                    "screenshot_gemma_provider",
                )
                if fallback_reason == "empty":
                    raise ValueError("empty_gemma_screenshot_response")
                try:
                    fallback, fallback_provider = self.translate_text_preferred_with_provider(source_text_hint)
                except Exception:
                    fallback, fallback_provider = "", ""
                if self._is_usable_text_fallback(source_text_hint, fallback):
                    self._last_screenshot_translation_provider = fallback_provider or primary_provider
                    return fallback
            self._last_screenshot_translation_provider = primary_provider
            return translated
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        model_name = self.resolve_gemma_model_for_call(self.gemma_model)
        if not self.can_call_gemma(model_name):
            raise ValueError("gemma_rate_limited")

        translated = ""
        last_payload = None
        last_raw_text = ""
        for attempt_index in range(3):
            retry_note = None
            if attempt_index >= 1 and last_raw_text:
                retry_note = (
                    "Rewrite the previous answer as translation only. "
                    f"Previous answer was: {last_raw_text[:600]}"
                )
            prompt = translation_tools.build_gemma_screenshot_prompt_v2(
                retry_note, target_lang=self.translation_target_lang
            )
            req_body = {
                "contents": [{
                    "parts": [*image_parts, {"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.0 if attempt_index else 0.1,
                    "topP": 0.9,
                    "topK": 32,
                    "maxOutputTokens": 2048,
                    "responseMimeType": "application/json"
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
            self.record_gemma_call(model_name)
            with request.urlopen(req, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
            last_payload = payload
            last_raw_text = self.extract_gemma_text(payload)
            translated = self.convert_to_trad(
                translation_tools.clean_screenshot_translation_output(
                    last_raw_text, target_lang=self.translation_target_lang
                )
            )
            if translation_tools.is_valid_screenshot_translation(
                translated, target_lang=self.translation_target_lang
            ):
                break
            translated = ""
        if not translated:
            fallback_reason = translation_fallback_reason(
                source_text_hint,
                translated,
                target_lang=self.translation_target_lang,
            )
            if fallback_reason:
                self._log_translation_fallback_reason(
                    fallback_reason,
                    source_text_hint,
                    translated,
                    "screenshot_gemma_empty",
                )
            raise ValueError("empty_gemma_screenshot_response")
        fallback_reason = translation_fallback_reason(
            source_text_hint,
            translated,
            target_lang=self.translation_target_lang,
        )
        if fallback_reason:
            self._log_translation_fallback_reason(
                fallback_reason,
                source_text_hint,
                translated,
                "screenshot_gemma_google",
            )
            try:
                fallback = self.translate_text_google(source_text_hint)
            except Exception:
                fallback = ""
            if self._is_usable_text_fallback(source_text_hint, fallback):
                self._last_screenshot_translation_provider = "google"
                return fallback
            try:
                fallback = self.translate_text_gemma(source_text_hint)
            except Exception:
                fallback = ""
            if self._is_usable_text_fallback(source_text_hint, fallback):
                self._last_screenshot_translation_provider = self.get_current_ai_provider()
                return fallback
        self._last_screenshot_translation_provider = self.get_current_ai_provider()
        return translated

    def translate_text_gemma_with_provider(self, text):
        translated = self.translate_text_gemma(text)
        return translated, self.get_current_ai_provider()

    def translate_text_preferred(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return ""
        if self.has_ai_text_provider():
            try:
                return self.translate_text_gemma(normalized_text)
            except (error.URLError, error.HTTPError, TimeoutError, ValueError):
                pass
        return self.translate_text_google(normalized_text)

    def translate_text_preferred_with_provider(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return "", ""
        if self.has_ai_text_provider():
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
        if self.has_ai_text_provider():
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
        if self.has_any_multimodal_ai() and image_parts:
            translated = self.translate_multimodal_gemma(image_parts, source_texts)
            parsed = self.parse_segmented_translation_json(translated, len(source_texts))
            if parsed:
                repaired, _providers = self._repair_suspicious_multimodal_segments(source_texts, parsed)
                return repaired
        return self.translate_items_in_batches(source_texts, batch_size=GOOGLE_BATCH_SIZE if not self.has_any_multimodal_ai() else 8)

    def _is_usable_text_fallback(self, source_text, translated_text):
        return bool(str(translated_text or "").strip()) and not translation_fallback_reason(
            source_text,
            translated_text,
            target_lang=self.translation_target_lang,
        )

    def _log_translation_fallback_reason(self, reason, source_text, translated_text, route):
        debug_log = getattr(self, "log_ai_debug", None)
        if not callable(debug_log):
            return
        debug_log(
            " ".join(
                [
                    "[translation fallback]",
                    f"route={route}",
                    f"reason={reason}",
                    f"source_len={len(str(source_text or ''))}",
                    f"translated_len={len(str(translated_text or ''))}",
                ]
            )
        )

    def _repair_suspicious_multimodal_segments(self, source_texts, parsed):
        repaired = list(parsed)
        provider_name = self.get_current_ai_provider()
        providers = [provider_name] * len(repaired)
        for index, (source_text, translated_text) in enumerate(zip(source_texts, repaired)):
            fallback_reason = translation_fallback_reason(
                source_text,
                translated_text,
                target_lang=self.translation_target_lang,
            )
            if not fallback_reason:
                continue
            self._log_translation_fallback_reason(
                fallback_reason,
                source_text,
                translated_text,
                f"multimodal_segment_{index}",
            )
            try:
                fallback, fallback_provider = self.translate_text_preferred_with_provider(source_text)
            except Exception:
                continue
            if self._is_usable_text_fallback(source_text, fallback):
                repaired[index] = fallback
                providers[index] = fallback_provider or provider_name
        return repaired, providers

    def translate_items_with_ai_and_providers(self, source_texts, image_parts, merged_items=None):
        if not source_texts:
            return [], []
        if self.has_any_multimodal_ai() and image_parts:
            translated = self.translate_multimodal_gemma(image_parts, source_texts)
            parsed = self.parse_segmented_translation_json(translated, len(source_texts))
            if parsed:
                return self._repair_suspicious_multimodal_segments(source_texts, parsed)
        if len(source_texts) == 1 and merged_items is not None:
            provider_name = self.get_current_ai_provider() if self.has_ai_text_provider() else "google"
            provider_obj = self._get_translation_provider(provider_name)
            if hasattr(provider_obj, "translate_stream"):
                try:
                    accumulated = ""
                    item = merged_items[0]
                    for chunk in provider_obj.translate_stream(source_texts[0]):
                        accumulated += chunk
                        self.translation_stream_update.emit(0, accumulated, provider_name, int(item['x']), int(item['y']), int(item['w']), int(item['h']))
                    return [accumulated], [provider_name]
                except Exception as exc:
                    logger.error(f"Streaming translation failed: {exc}")
                    pass

        return self.translate_items_in_batches_with_providers(
            source_texts,
            batch_size=GOOGLE_BATCH_SIZE if not self.has_any_multimodal_ai() else 8,
        )

    def capture_scan_area(self):
        with mss.mss() as sct:
            virtual_monitor = sct.monitors[0] if sct.monitors else None
            if self.scan_mode == SCAN_MODE_REGION and self.scan_region:
                left, top, width, height = [int(v) for v in self.scan_region]
                if virtual_monitor:
                    virt_left = int(virtual_monitor.get("left", 0))
                    virt_top = int(virtual_monitor.get("top", 0))
                    virt_right = virt_left + int(virtual_monitor.get("width", 0))
                    virt_bottom = virt_top + int(virtual_monitor.get("height", 0))
                    left = max(virt_left, left)
                    top = max(virt_top, top)
                    right = min(virt_right, left + max(1, width))
                    bottom = min(virt_bottom, top + max(1, height))
                    width = max(1, right - left)
                    height = max(1, bottom - top)
                capture_rect = {
                    "left": left,
                    "top": top,
                    "width": max(1, width),
                    "height": max(1, height),
                }
            else:
                capture_rect = virtual_monitor or (sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0])

            try:
                screenshot = sct.grab(capture_rect)
            except Exception:
                if capture_rect is not virtual_monitor and virtual_monitor is not None:
                    screenshot = sct.grab(virtual_monitor)
                    capture_rect = virtual_monitor
                else:
                    raise
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

    def normalize_manga_page_region(self, img, detected_region):
        img_h, img_w = img.shape[:2]
        if img_h <= 0 or img_w <= 0:
            return detected_region
        aspect_ratio = img_w / max(1, img_h)
        image_is_page_shaped = (
            min(img_w, img_h) >= 700
            and 0.58 <= aspect_ratio <= 1.25
        )
        if not image_is_page_shaped:
            return detected_region

        full_region = (0, 0, img_w, img_h)
        if not detected_region:
            return full_region
        try:
            _x, _y, width, height = [int(value) for value in detected_region]
        except (TypeError, ValueError):
            return full_region
        detected_ratio = max(0, width) * max(0, height) / max(1, img_w * img_h)
        return full_region if detected_ratio < 0.45 else detected_region

    @staticmethod
    def is_unreliable_manga_ocr(items):
        texts = [
            normalize_ocr_text(item.get("text", ""))
            for item in (items or [])
            if normalize_ocr_text(item.get("text", ""))
        ]
        combined = "".join(texts)
        compact = "".join(char for char in combined if not char.isspace())
        if len(compact) < 4:
            return not bool(re.search(r"[぀-ヿ㐀-䶿一-鿿]", compact))
        noise_count = sum(
            1
            for char in compact
            if not (char.isalnum() or re.match(r"[぀-ヿ㐀-䶿一-鿿]", char))
        )
        if (noise_count / len(compact)) > 0.55:
            return True
        cjk_count = len(re.findall(r"[぀-ヿ㐀-䶿一-鿿]", compact))
        if len(compact) < 12:
            fragmented = len(texts) > 1 or any(" " in text for text in texts)
            return fragmented and (cjk_count / len(compact)) < 0.35
        return (cjk_count / len(compact)) < 0.18

    @staticmethod
    def has_cjk_manga_text(items):
        return any(
            re.search(r"[぀-ヿ㐀-䶿一-鿿]", normalize_ocr_text(item.get("text", "")))
            for item in (items or [])
        )

    @staticmethod
    def is_degenerate_manga_transcription(text):
        lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
        if len(lines) < 8:
            return False
        counts = {line: lines.count(line) for line in set(lines)}
        return max(counts.values(), default=0) >= 4 and (len(counts) / len(lines)) < 0.45

    def rescue_unreliable_manga_items(
        self,
        img,
        page_region,
        items,
        offset_x,
        offset_y,
        image_parts=None,
    ):
        if not self.is_unreliable_manga_ocr(items):
            return list(items or []), image_parts
        provider_name = self.resolve_multimodal_provider_name()
        provider = self._get_translation_provider(provider_name) if provider_name else None
        if provider is None or not hasattr(provider, "transcribe_screenshot"):
            return list(items or []), image_parts

        page_rect = self.clip_region_rect(
            *page_region,
            img.shape[1],
            img.shape[0],
        )
        if page_rect is None:
            return list(items or []), image_parts
        x, y, width, height = page_rect
        page_img = img[y:y + height, x:x + width]

        hint = self.build_screenshot_text_hint(page_img)
        if not hint:
            hint = "\n".join(
                normalize_ocr_text(item.get("text", ""))
                for item in (items or [])
                if normalize_ocr_text(item.get("text", ""))
            )
        full_rect = (0, 0, img.shape[1], img.shape[0])
        parts = (
            image_parts
            if image_parts and page_rect == full_rect
            else self.build_ai_image_parts(page_img)
        )
        try:
            result = provider.transcribe_screenshot(parts, source_text_hint=hint or None)
            transcription = str(getattr(result, "text", "") or "").strip()
        except Exception as exc:
            logger.info(f"[Manga rescue] transcription fallback: {type(exc).__name__}")
            return list(items or []), image_parts
        if (
            len(normalize_ocr_text(transcription)) < 4
            or self.is_degenerate_manga_transcription(transcription)
        ):
            return list(items or []), image_parts

        return [
            {
                "text": transcription,
                "x": int(offset_x) + x,
                "y": int(offset_y) + y,
                "w": width,
                "h": height,
                "confidence": None,
            }
        ], parts

    @staticmethod
    def item_center_in_region(item, region, offset_x=0, offset_y=0):
        try:
            center_x = int(item.get("x", 0)) - int(offset_x) + int(item.get("w", 0)) / 2
            center_y = int(item.get("y", 0)) - int(offset_y) + int(item.get("h", 0)) / 2
            x, y, width, height = [int(value) for value in region]
        except (TypeError, ValueError):
            return False
        return x <= center_x < x + width and y <= center_y < y + height

    def build_manga_adaptive_regions(self, items, img_w, img_h, offset_x=0, offset_y=0):
        page_area = max(1, int(img_w) * int(img_h))
        ranked = []
        for item in items or []:
            try:
                x = int(item.get("x", 0)) - int(offset_x)
                y = int(item.get("y", 0)) - int(offset_y)
                width = int(item.get("w", 0))
                height = int(item.get("h", 0))
            except (TypeError, ValueError):
                continue
            if width <= 0 or height <= 0:
                continue
            area_ratio = (width * height) / page_area
            if not (
                MANGA_ADAPTIVE_MIN_AREA_RATIO
                <= area_ratio
                <= MANGA_ADAPTIVE_MAX_AREA_RATIO
            ):
                continue
            pad_x = max(10, int(width * 0.10))
            pad_y = max(10, int(height * 0.10))
            expanded = self.expand_region_rect(
                (x, y, width, height),
                pad_x,
                pad_y,
                int(img_w),
                int(img_h),
            )
            if (
                expanded
                and (expanded[2] * expanded[3]) / page_area
                <= MANGA_ADAPTIVE_MAX_AREA_RATIO
            ):
                ranked.append((width * height, expanded))

        ranked.sort(key=lambda value: value[0], reverse=True)
        selected = []
        for _area, region in ranked:
            if any(self.rect_overlap_ratio(region, old) >= 0.75 for old in selected):
                continue
            selected.append(region)
            if len(selected) >= MANGA_ADAPTIVE_MAX_REGIONS:
                break
        return selected

    def refine_manga_ocr_items(
        self,
        img,
        items,
        threshold,
        offset_x=0,
        offset_y=0,
    ):
        baseline = list(items or [])
        refine_started = time.perf_counter()
        refine_deadline = refine_started + MANGA_ADAPTIVE_MAX_MS / 1000.0
        if len(baseline) < 2 or not self.has_cjk_manga_text(baseline):
            return baseline

        img_h, img_w = img.shape[:2]
        regions = self.build_manga_adaptive_regions(
            baseline,
            img_w,
            img_h,
            offset_x,
            offset_y,
        )
        if not regions:
            return baseline

        tall_regions = [
            region for region in regions
            if region[3] >= region[2] * 1.3
        ]
        horizontal_regions = [
            region for region in regions
            if region not in tall_regions
        ]
        try:
            selected_threshold = max(
                AUTO_THRESHOLD_MIN,
                min(AUTO_THRESHOLD_MAX, int(threshold)),
            )
        except (TypeError, ValueError):
            selected_threshold = int(self.binary_threshold)

        candidates = []
        for region_group, orientations in (
            (tall_regions, [90, 270]),
            (horizontal_regions, [0]),
        ):
            if not region_group:
                continue
            if time.perf_counter() >= refine_deadline:
                break
            _used_threshold, found = self.run_ocr_with_best_threshold(
                img,
                offset_x,
                offset_y,
                region_group,
                [selected_threshold],
                orientations,
                deadline=refine_deadline,
            )
            candidates.extend(found or [])

        def rectangle_coverage(base_item, candidate_item):
            try:
                bx = float(base_item.get("x", 0))
                by = float(base_item.get("y", 0))
                bw = float(base_item.get("w", 0))
                bh = float(base_item.get("h", 0))
                cx = float(candidate_item.get("x", 0))
                cy = float(candidate_item.get("y", 0))
                cw = float(candidate_item.get("w", 0))
                ch = float(candidate_item.get("h", 0))
            except (TypeError, ValueError):
                return 0.0
            base_area = bw * bh
            if base_area <= 0 or cw <= 0 or ch <= 0:
                return 0.0
            intersection = max(0.0, min(bx + bw, cx + cw) - max(bx, cx))
            intersection *= max(0.0, min(by + bh, cy + ch) - max(by, cy))
            return intersection / base_area

        replace_indexes = set()
        accepted = []
        accepted_keys = set()
        for region in regions:
            base_indexes = [
                index
                for index, item in enumerate(baseline)
                if self.item_center_in_region(item, region, offset_x, offset_y)
            ]
            base_local = [baseline[index] for index in base_indexes]
            candidate_local = [
                item
                for item in candidates
                if self.item_center_in_region(item, region, offset_x, offset_y)
            ]
            base_score, _filtered_base = self.score_ocr_items(base_local)
            candidate_score, filtered_candidate = self.score_ocr_items(candidate_local)
            if not base_local or not filtered_candidate:
                continue
            if any(
                not any(rectangle_coverage(base_item, candidate_item) >= MANGA_ADAPTIVE_MIN_COVERAGE for candidate_item in filtered_candidate)
                for base_item in base_local
            ):
                continue
            base_text = "".join(normalize_ocr_text(item.get("text", "")) for item in base_local)
            candidate_text = "".join(normalize_ocr_text(item.get("text", "")) for item in filtered_candidate)
            text_agreement = difflib.SequenceMatcher(None, base_text, candidate_text).ratio()
            if (
                candidate_score < base_score + MANGA_ADAPTIVE_SCORE_MARGIN
                or text_agreement < MANGA_ADAPTIVE_MIN_TEXT_AGREEMENT
            ):
                continue
            replace_indexes.update(base_indexes)
            for item in filtered_candidate:
                key = (
                    normalize_ocr_text(item.get("text", "")),
                    int(item.get("x", 0)),
                    int(item.get("y", 0)),
                    int(item.get("w", 0)),
                    int(item.get("h", 0)),
                )
                if key not in accepted_keys:
                    accepted_keys.add(key)
                    accepted.append(item)
        if not replace_indexes:
            return baseline
        adjusted = [
            item
            for index, item in enumerate(baseline)
            if index not in replace_indexes
        ]
        adjusted.extend(accepted)
        _score, filtered_adjusted = self.score_ocr_items(adjusted)
        return filtered_adjusted or baseline

    def build_local_manga_crop_context(
        self,
        img,
        page_region,
        items,
        offset_x=0,
        offset_y=0,
    ):
        """Build bounded local-vision context without changing OCR geometry."""
        enabled = os.environ.get(MANGA_CROP_CONTEXT_ENV, "").strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return None
        if (
            not page_region
            or len(items or []) < 2
            or not self.has_cjk_manga_text(items)
            or not self.has_local_multimodal_ai()
        ):
            return None

        provider = self._get_translation_provider("local_multimodal")
        if provider is None or not hasattr(provider, "transcribe_screenshot"):
            return None
        available = getattr(provider, "available", None)
        if callable(available) and not available():
            return None

        img_h, img_w = img.shape[:2]
        regions = self.build_manga_adaptive_regions(
            items,
            img_w,
            img_h,
            offset_x,
            offset_y,
        )
        if not regions or any(
            not any(self.item_center_in_region(item, region, offset_x, offset_y) for region in regions)
            for item in items
        ):
            return None

        parts = []
        for region in regions:
            clipped = self.clip_region_rect(
                *region,
                img_w,
                img_h,
            )
            if clipped is None:
                return None
            x, y, width, height = clipped
            crop = img[y:y + height, x:x + width]
            if crop.size == 0:
                return None
            try:
                crop_parts = self.build_ai_image_parts(crop)
            except Exception as exc:
                logger.info(f"[Manga crop context] fallback: {type(exc).__name__}")
                return None
            if not crop_parts:
                return None
            parts.extend(crop_parts)
        return parts or None

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
                cell_left = x + col * tile_w
                cell_top = y + row * tile_h
                cell_right = x + w if col == cols - 1 else x + (col + 1) * tile_w
                cell_bottom = y + h if row == rows - 1 else y + (row + 1) * tile_h
                left = max(x, cell_left - pad_x)
                top = max(y, cell_top - pad_y)
                right = min(x + w, cell_right + pad_x)
                bottom = min(y + h, cell_bottom + pad_y)
                tiles.append((left, top, right - left, bottom - top))
        return tiles

    def get_ocr_regions(self, img, page_region=None):
        img_h, img_w = img.shape[:2]
        full_rect = (0, 0, img_w, img_h)
        if self.scan_mode != SCAN_MODE_FULLSCREEN:
            return [full_rect]
        if page_region:
            return [page_region]
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
            x = int(item['x']) - offset_x
            y = int(item['y']) - offset_y
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

        def get_rect(obj):
            rect = getattr(obj, "bounding_rect", None)
            if rect is None:
                rect = getattr(obj, "box", None)
            if rect is None:
                return None
            x = int(getattr(rect, "x", 0))
            y = int(getattr(rect, "y", 0))
            w = int(getattr(rect, "width", getattr(rect, "w", 1)))
            h = int(getattr(rect, "height", getattr(rect, "h", 1)))
            return x, y, max(1, w), max(1, h)

        for line in getattr(ocr_result, "lines", []):
            line_text = normalize_ocr_text(getattr(line, "text", "") or "")
            if not line_text.strip():
                continue
            words = list(getattr(line, "words", []) or [])
            if words:
                rects = [get_rect(word) for word in words]
                rects = [rect for rect in rects if rect is not None]
                if not rects:
                    continue
                x_min = min(rect[0] for rect in rects)
                y_min = min(rect[1] for rect in rects)
                x_max = max(rect[0] + rect[2] for rect in rects)
                y_max = max(rect[1] + rect[3] for rect in rects)
            else:
                line_rect = get_rect(line)
                if line_rect is None:
                    continue
                x_min, y_min, w, h = line_rect
                x_max = x_min + w
                y_max = y_min + h
            raw_items.append({
                'text': line_text,
                'x': int(x_min / scale_factor) + offset_x,
                'y': int(y_min / scale_factor) + offset_y,
                'w': int((x_max - x_min) / scale_factor),
                'h': int((y_max - y_min) / scale_factor),
            })
        return raw_items

    def score_ocr_items(self, raw_items):
        return quality_score_ocr_items(raw_items, allow_relaxed=True)

    def summarize_threshold_candidate(self, items, max_items=8, max_chars=240):
        return quality_summarize_threshold_candidate(items, max_items=max_items, max_chars=max_chars)

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

    def run_ocr_with_best_threshold(self, img, offset_x, offset_y, ocr_regions=None, candidate_thresholds=None, orientation_candidates=None, silent=False, force_bg_refresh=False, deadline=None):
        base_threshold = int(self.binary_threshold)
        now_ms = time.monotonic() * 1000.0
        should_refresh_auto_threshold = force_bg_refresh

        def evaluate_thresholds(
            threshold_values,
            current_best_threshold,
            current_best_items,
            current_best_score,
            parallel=True,
        ):
            candidate_results = []
            regions = ocr_regions or [(0, 0, img.shape[1], img.shape[0])]
            orientations = orientation_candidates or [0]

            prepared_regions = []
            for region_x, region_y, region_w, region_h in regions:
                if deadline is not None and time.perf_counter() >= deadline:
                    break
                crop = img[region_y:region_y + region_h, region_x:region_x + region_w]
                if crop.size == 0:
                    continue
                crop_w, crop_h = crop.shape[1], crop.shape[0]
                prepared_orientations = []
                for orientation in orientations:
                    if deadline is not None and time.perf_counter() >= deadline:
                        break
                    rotated_crop = self.rotate_crop_for_ocr(crop, orientation)
                    if rotated_crop.size == 0:
                        continue
                    rot_h, rot_w = rotated_crop.shape[:2]
                    scale_factor = 3.0
                    # 框選模式：限制圖片最大邊長 1000px，避免大對話框 OCR 過慢
                    if self.scan_mode == SCAN_MODE_REGION:
                        max_dim = 1000
                        scaled_w = int(rot_w * scale_factor)
                        scaled_h = int(rot_h * scale_factor)
                        if scaled_w > max_dim or scaled_h > max_dim:
                            scale_factor = max(1.5, min(max_dim / rot_w, max_dim / rot_h))
                    img_scaled = cv2.resize(
                        rotated_crop,
                        (int(rot_w * scale_factor), int(rot_h * scale_factor)),
                        interpolation=cv2.INTER_CUBIC,
                    )
                    gray = cv2.cvtColor(img_scaled, cv2.COLOR_BGR2GRAY)
                    prepared_orientations.append(
                        {
                            "orientation": orientation,
                            "gray": gray,
                            "scale_factor": scale_factor,
                            "crop_w": crop_w,
                            "crop_h": crop_h,
                            "offset_x": offset_x + region_x,
                            "offset_y": offset_y + region_y,
                        }
                    )
                if prepared_orientations:
                    prepared_regions.append(prepared_orientations)

            # 並列 OCR：把所有（閥値, 區域索引, 方向）組合同時丟給 ThreadPoolExecutor
            def _run_one(task):
                if deadline is not None and time.perf_counter() >= deadline:
                    return None
                threshold, region_idx, prepared = task
                _, binary = cv2.threshold(prepared["gray"], threshold, 255, cv2.THRESH_BINARY)
                img_final = cv2.bitwise_not(binary)
                img_for_ocr = cv2.cvtColor(img_final, cv2.COLOR_GRAY2BGR)
                try:
                    ocr_result = self._recognize_with_backends(img_for_ocr)
                except Exception:
                    ocr_result = None
                region_items = self.extract_raw_items(
                    ocr_result,
                    prepared["scale_factor"],
                    prepared["offset_x"],
                    prepared["offset_y"],
                )
                region_items = self.remap_items_from_orientation(
                    region_items,
                    prepared["orientation"],
                    prepared["crop_w"],
                    prepared["crop_h"],
                    prepared["offset_x"],
                    prepared["offset_y"],
                )
                score, filtered_items = self.score_ocr_items(region_items)
                return threshold, region_idx, prepared["orientation"], score, filtered_items

            tasks = [
                (threshold, region_idx, prepared)
                for threshold in threshold_values
                for region_idx, prepared_orientations in enumerate(prepared_regions)
                for prepared in prepared_orientations
            ]

            # 收集並列結果： results_map[(threshold, region_idx)] = [(score, items), ...]
            results_map = {}
            if len(tasks) == 1:
                # 單任務直接跑，省略 ThreadPoolExecutor 開銷
                try:
                    result = _run_one(tasks[0])
                    if result is not None:
                        threshold, region_idx, orientation, score, filtered_items = result
                        results_map.setdefault((threshold, region_idx), []).append((orientation, score, filtered_items))
                except Exception:
                    pass
            elif parallel:
                max_workers = min(len(tasks), 8)
                executor = ThreadPoolExecutor(max_workers=max_workers)
                futures = []
                try:
                    futures = [executor.submit(_run_one, task) for task in tasks]
                    if deadline is None:
                        done, _pending = wait(futures)
                    else:
                        remaining = max(0.0, deadline - time.perf_counter())
                        done, _pending = wait(futures, timeout=remaining)
                    for future in done:
                        if deadline is not None and time.perf_counter() >= deadline:
                            continue
                        try:
                            result = future.result()
                            if result is None:
                                continue
                            threshold, region_idx, orientation, score, filtered_items = result
                            results_map.setdefault((threshold, region_idx), []).append((orientation, score, filtered_items))
                        except Exception:
                            pass
                finally:
                    executor.shutdown(
                        wait=deadline is None,
                        cancel_futures=deadline is not None,
                    )
            else:
                for task in tasks:
                    if deadline is not None and time.perf_counter() >= deadline:
                        break
                    try:
                        result = _run_one(task)
                        if result is not None:
                            threshold, region_idx, orientation, score, filtered_items = result
                            results_map.setdefault((threshold, region_idx), []).append((orientation, score, filtered_items))
                    except Exception:
                        pass

            # 依閥値排序組裝結果
            for threshold in threshold_values:
                raw_items = []
                for region_idx in range(len(prepared_regions)):
                    region_results = results_map.get((threshold, region_idx), [])
                    if region_results:
                        orientation_order = {
                            value: index for index, value in enumerate(orientations)
                        }
                        best_score_items = max(
                            region_results,
                            key=lambda result: (
                                bool(result[2]),
                                result[1],
                                -orientation_order.get(result[0], len(orientation_order)),
                            ),
                        )
                        raw_items.extend(best_score_items[2])
                score, filtered_items = self.score_ocr_items(raw_items)
                candidate_results.append({
                    "threshold": threshold,
                    "score": score,
                    "items": filtered_items,
                })
                if filtered_items and (not current_best_items or score > current_best_score):
                    current_best_score = score
                    current_best_threshold = threshold
                    current_best_items = filtered_items
            return candidate_results, current_best_threshold, current_best_items, current_best_score

        if candidate_thresholds:
            candidates = [int(value) for value in candidate_thresholds if value is not None]
        elif should_refresh_auto_threshold:
            # 因為已經在背景偷算了，我們不怕慢，直接恢復成完整的 AUTO_THRESHOLD_CANDIDATES
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
            parallel=not should_refresh_auto_threshold,
        )

        # Explore the threshold table only after the fast path returns no text.
        if not best_items and not candidate_thresholds and not should_refresh_auto_threshold:
            fallback_candidates = [value for value in AUTO_THRESHOLD_CANDIDATES if value not in candidates]
            if fallback_candidates:
                fallback_results, best_threshold, best_items, best_score = evaluate_thresholds(
                    fallback_candidates,
                    best_threshold,
                    best_items,
                    best_score,
                    parallel=False,
                )
                candidate_results.extend(fallback_results)

        # 框選模式 refresh 時跳過 local offset，省去額外 OCR 呼叫
        if self.auto_threshold_enabled and should_refresh_auto_threshold and self.scan_mode != SCAN_MODE_REGION:
            local_candidates = sorted({
                max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, best_threshold + offset))
                for offset in AUTO_THRESHOLD_LOCAL_OFFSETS
            })
            if len(local_candidates) > 1:
                if not silent: self.status_msg.emit("🔎 局部微調閥值中...")
                local_results, best_threshold, best_items, best_score = evaluate_thresholds(
                    local_candidates,
                    best_threshold,
                    best_items,
                    best_score,
                    parallel=not should_refresh_auto_threshold,
                )
                candidate_results.extend(local_results)

        if self.auto_threshold_enabled and self.google_api_key and should_refresh_auto_threshold:
            top_candidates = sorted(candidate_results, key=lambda item: item["score"], reverse=True)[:3]
            if len(top_candidates) >= 2:
                if not silent: self.status_msg.emit("🧠 句子完整度複判中...")
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
            self.set_binary_threshold(best_threshold)
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

    def rescue_japanese_text(self, img, first_text, image_parts=None):
        if not self.japanese_rescue_enabled or not first_text:
            return first_text
        runtime = getattr(self, "japanese_rescue_runtime", None)
        height, width = img.shape[:2]
        if (
            runtime is None
            or runtime.state is not JapaneseOCRRuntimeState.ready
            or not rescue_gate(first_text, image_width=width, image_height=height)
        ):
            return first_text
        try:
            candidate = runtime.run(img)
            if not is_usable_meiki_candidate(candidate, first_text):
                return first_text
            provider = self.local_multimodal_provider
            if not provider.available():
                return first_text
            parts = image_parts or self.build_ai_image_parts(img)
            second = provider.transcribe_screenshot(
                parts,
                source_text_hint=build_verification_hint(candidate),
            ).text
            decision = decide_rescue_text(first_text, second, candidate)
            if decision.adopted:
                logger.info(
                    "[Japanese rescue] adopted first=%.3f second=%.3f",
                    decision.first_similarity,
                    decision.second_similarity,
                )
            return decision.selected_text
        except Exception as exc:
            logger.warning(f"[Japanese rescue] fallback to baseline: {type(exc).__name__}: {exc}")
            return first_text

    def run_scan_once(self):
        is_screenshot_mode = self.scan_mode == SCAN_MODE_REGION and self.region_render_mode == REGION_RENDER_SCREENSHOT
        is_relief_mode = self.scan_mode == SCAN_MODE_REGION and self.region_render_mode == REGION_RENDER_RELIEF
        _t0 = time.perf_counter()
        def _log(label):
            if is_relief_mode:
                elapsed = (time.perf_counter() - _t0) * 1000
                logger.info(f"[浮雕計時] {label}: +{elapsed:.1f}ms (累計)")
        ai_image_parts = None
        if not is_screenshot_mode and not self.ocr_backends:
            self.status_msg.emit("❌ 缺少可用 OCR 後端")
            self.finished.emit([])
            self.show_ui.emit()
            return

        self.hide_ui.emit()
        _log("開始 - hide_ui")
        # 挑戰肉眼極限：只等 30 毫秒（約 2 個畫面影格）
        time.sleep(0.03)
        try:
            img, offset_x, offset_y = self.capture_scan_area()
            self.last_scanned_img = img.copy()
            self.last_scanned_offset = (offset_x, offset_y)
            _log("① 截圖完成")
        except Exception as exc:
            self.status_msg.emit(f"\u274c 擷取螢幕失敗：{type(exc).__name__}")
            self.finished.emit([])
            return
        finally:
            # 截完圖立刻讓舊字幕回來，達成無縫翻譯效果
            self.show_ui.emit()

        exact_context = self._exact_image_cache_context(offset_x, offset_y)
        cached_image_result = self.exact_image_cache.get(img, exact_context)
        if cached_image_result is not None:
            selected_provider = self._current_cache_provider()
            is_upgrade_needed = (
                self.get_translation_provider_priority(selected_provider)
                > self.get_translation_provider_priority(cached_image_result.provider)
            )
            if not is_upgrade_needed:
                cached_results = list(cached_image_result.results)
                self.last_combined_text = cached_image_result.state_token
                self.last_provider = cached_image_result.provider
                self.last_results = cached_results
                self.status_msg.emit("♻️ 完全相同畫面（快取）")
                if not is_screenshot_mode:
                    self.trigger_background_threshold_refresh(img, offset_x, offset_y, self.scan_mode)
                self.finished.emit(cached_results)
                return

        # 截圖後立刻預取 Google OCR（與本地 OCR 並列進行）
        # 注意：多模態 AI 翻譯已包含看圖能力，可代替 Google OCR refine，故不重複呼叫
        _google_ocr_future = None
        _prefetch_image_parts = None
        _use_google_ocr_refine = self.google_ocr_enabled and self.google_api_key and not self.has_any_multimodal_ai()
        if _use_google_ocr_refine and self.scan_mode == SCAN_MODE_REGION:
            try:
                _prefetch_image_parts = self.build_ai_image_parts(img)
                ai_image_parts = _prefetch_image_parts
                _provider_snap = self._get_translation_provider("gemma")
                if _provider_snap is not None and hasattr(_provider_snap, "transcribe_screenshot"):
                    _google_executor = ThreadPoolExecutor(max_workers=1)
                    def _bg_google_ocr(_prov=_provider_snap, _parts=_prefetch_image_parts):
                        try:
                            result = _prov.transcribe_screenshot(_parts)
                            self.sync_gemma_call_timestamps_from_provider(_prov)
                            return result
                        except Exception:
                            return None
                    _google_ocr_future = _google_executor.submit(_bg_google_ocr)
                    _log("① 截圖完成 (Google OCR 預取已啟動)")
            except Exception:
                _google_ocr_future = None

        if is_screenshot_mode:
            screenshot_text_hint = self.build_screenshot_text_hint(img)
            if self.has_any_multimodal_ai():
                screenshot_text_hint = self.rescue_japanese_text(
                    img,
                    screenshot_text_hint,
                    ai_image_parts,
                )
            if not self.has_any_multimodal_ai():
                if not screenshot_text_hint:
                    self.status_msg.emit("❌ 截圖模式需要 Gemma AI 與 Google API KEY")
                    self.finished.emit([])
                    self.show_ui.emit()
                    return
                self.status_msg.emit("🖼 截圖模式改走文字翻譯...")
                try:
                    translated_text, current_provider = self.translate_text_preferred_with_provider(screenshot_text_hint)
                except Exception as exc:
                    self.status_msg.emit(f"❌ 截圖翻譯失敗：{type(exc).__name__}: {exc}")
                    self.finished.emit([])
                    self.show_ui.emit()
                    return
            else:
                ai_image_parts = self.build_ai_image_parts(img)
                self.status_msg.emit("🖼 截圖模式翻譯中...")
                try:
                    translated_text = self.translate_screenshot_gemma(ai_image_parts, screenshot_text_hint).strip()
                    current_provider = (
                        getattr(self, "_last_screenshot_translation_provider", "")
                        or self.get_current_ai_provider()
                    )
                except Exception as exc:
                    self.log_ai_debug(f"MULTIMODAL FAILED: {exc}")
                    if screenshot_text_hint:
                        self.status_msg.emit("🖼 截圖模式失敗，改走文字翻譯...")
                        try:
                            translated_text, current_provider = self.translate_text_preferred_with_provider(screenshot_text_hint)
                        except Exception:
                            self.status_msg.emit(f"❌ 截圖翻譯失敗：{type(exc).__name__}: {exc}")
                            self.finished.emit([])
                            self.show_ui.emit()
                            return
                    else:
                        self.status_msg.emit(f"❌ 截圖翻譯失敗：{type(exc).__name__}: {exc}")
                        self.finished.emit([])
                        self.show_ui.emit()
                        return

            if not translated_text:
                self.handle_empty("⚠️ 截圖翻譯結果為空")
                self.show_ui.emit()
                return

            current_combined_text = "screenshot"
            self.last_combined_text = current_combined_text
            current_provider = self._canonical_cache_provider(current_provider)
            self.last_provider = current_provider
            final_results = [(translated_text, int(offset_x), int(offset_y), int(img.shape[1]), int(img.shape[0]))]
            if current_provider:
                exact_context = self._exact_image_cache_context(offset_x, offset_y)
                self.exact_image_cache.put(
                    img,
                    exact_context,
                    final_results,
                    current_provider,
                    current_combined_text,
                )
            self.last_results = final_results
            self.status_msg.emit("✅ 截圖翻譯完成")
            self.finished.emit(final_results)
            self.show_ui.emit()
            return

        ocr_regions = None
        ocr_orientations = [0]
        page_region = None
        if self.scan_mode == SCAN_MODE_FULLSCREEN:
            self.status_msg.emit("🧭 智慧裁切分析中...")
            try:
                detected_page_region = self.detect_manga_page_region(img)
                page_region = self.normalize_manga_page_region(img, detected_page_region)
                if page_region:
                    ocr_regions = [page_region]
                    ocr_orientations = [0, 90, 270]
                else:
                    ocr_regions = self.get_ocr_regions(img, page_region=page_region)
            except Exception:
                ocr_regions = None
                ocr_orientations = [0]
        elif self.scan_mode == SCAN_MODE_REGION:
            # 框選模式先尊重原始方向，英文/一般網頁多半就是 0 度。
            # 真的抓不到再走後面的旋轉重試，避免平白多花時間。
            ocr_orientations = [0]
        
        self.status_msg.emit("🔍 掃描與翻譯中...")
        _log("② 開始 OCR")

        try:
            used_threshold, filtered_items = self.run_ocr_with_best_threshold(img, offset_x, offset_y, ocr_regions, None, ocr_orientations)
            _log(f"③ OCR 完成 (找到 {len(filtered_items)} 段)")
        except Exception:
            self.status_msg.emit("❌ 辨識錯誤")
            self.finished.emit([])
            self.show_ui.emit()
            return

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

        if self.scan_mode == SCAN_MODE_FULLSCREEN and len(filtered_items) <= 1 and page_region:
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
            and page_region
            and len(filtered_items) >= 2
            and self.has_cjk_manga_text(filtered_items)
        ):
            self.status_msg.emit("📖 漫畫文字精修中...")
            refine_started = time.perf_counter()
            try:
                filtered_items = self.refine_manga_ocr_items(
                    img,
                    filtered_items,
                    used_threshold,
                    offset_x,
                    offset_y,
                )
                _log(
                    f"③-1 漫畫文字精修完成 "
                    f"({(time.perf_counter() - refine_started) * 1000.0:.0f}ms)"
                )
            except Exception as exc:
                logger.info(f"[Manga refine] fallback: {type(exc).__name__}")

        if (
            self.scan_mode == SCAN_MODE_FULLSCREEN
            and page_region
            and (
                detected_page_region is not None
                or self.has_cjk_manga_text(filtered_items)
            )
            and self.has_any_multimodal_ai()
            and self.is_unreliable_manga_ocr(filtered_items)
        ):
            self.status_msg.emit("📖 漫畫文字辨識補救中...")
            filtered_items, ai_image_parts = self.rescue_unreliable_manga_items(
                img,
                page_region,
                filtered_items,
                offset_x,
                offset_y,
                ai_image_parts,
            )

        if not filtered_items:
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
        if (
            self.scan_mode == SCAN_MODE_REGION
            and len(merged_items) == 1
            and self.has_any_multimodal_ai()
        ):
            rescued_text = self.rescue_japanese_text(img, current_combined_text, ai_image_parts)
            if rescued_text != current_combined_text:
                merged_items[0] = dict(merged_items[0], text=rescued_text)
                current_combined_text = rescued_text

        current_provider = self.get_current_ai_provider() if self.has_ai_text_provider() else "google"
        final_results = []
        final_providers = []

        try:
            self.status_msg.emit("🧠 AI 大圖翻譯..." if self.has_any_multimodal_ai() else "🌐 Google...")
            if _use_google_ocr_refine:
                if _google_ocr_future is not None:
                    _log("⑤ 等待 Google OCR 預取結果...")
                    try:
                        _google_result = _google_ocr_future.result()
                        _log("⑥ Google OCR 精煉完成 (已預取)")
                        if _google_result is not None:
                            _google_lines = [normalize_ocr_text(line) for line in str(_google_result.text or "").splitlines() if normalize_ocr_text(line)]
                            merged_items = merge_google_lines_into_items(_google_lines, merged_items)
                    except Exception:
                        pass
                else:
                    if ai_image_parts is None:
                        _log("④-pre 開始 build_ai_image_parts (Google OCR)")
                        ai_image_parts = self.build_ai_image_parts(img)
                        _log("④ build_ai_image_parts 完成 (Google OCR)")
                    _log("⑤ 開始 refine_merged_items_with_google_ocr")
                    merged_items = self.refine_merged_items_with_google_ocr(merged_items, ai_image_parts)
                    _log("⑥ Google OCR 精煉完成")
            elif self.google_ocr_enabled and self.has_any_multimodal_ai():
                _log("⑤ 多模態 AI 可用，跳過 Google OCR refine（由 AI 翻譯直接讀圖修正）")
            source_texts = [item['text'] for item in merged_items]
            current_combined_text = "\n".join(source_texts)
            self.last_combined_text = current_combined_text
            translated_list = []
            provider_list = []
            try:
                if ai_image_parts is None and self.scan_mode == SCAN_MODE_FULLSCREEN:
                    crop_context = self.build_local_manga_crop_context(
                        img,
                        page_region,
                        merged_items,
                        offset_x,
                        offset_y,
                    )
                    if crop_context:
                        ai_image_parts = crop_context
                        _log(f"⑦-pre 漫畫局部多模態 context 完成 ({len(crop_context)} parts)")
                if ai_image_parts is None and self.has_any_multimodal_ai():
                    _log("⑦-pre 開始 build_ai_image_parts (多模態翻譯)")
                    ai_image_parts = self.build_ai_image_parts(img)
                    _log("⑦ build_ai_image_parts 完成")
                _log("⑧ 開始 translate_items_with_ai_and_providers")
                translated_list, provider_list = self.translate_items_with_ai_and_providers(source_texts, ai_image_parts, merged_items)
                _log(f"⑨ 翻譯完成 (共 {len(translated_list)} 段)")
            except Exception as exc:
                self.log_ai_debug(f"MULTIMODAL BATCH FAILED: {exc}")
                translated_list = []
                provider_list = []

            if len(translated_list) != len(merged_items):
                translated_list = [None] * len(merged_items)
            if len(provider_list) != len(merged_items):
                provider_list = [None] * len(merged_items)

            missing_indexes = [index for index, text in enumerate(translated_list) if not text]
            if missing_indexes:
                prefix = "AI" if self.has_any_multimodal_ai() else "Google"
                icon = "🧠" if prefix == "AI" else "🌐"
                self.status_msg.emit(f"{icon} {prefix} 批次補翻 {len(missing_indexes)} 段...")
                batch_source = [source_texts[index] for index in missing_indexes]
                batch_result, batch_providers = self.translate_items_in_batches_with_providers(batch_source, batch_size=8)
                for offset, translated in enumerate(batch_result):
                    if translated:
                        translated_list[missing_indexes[offset]] = translated
                        provider_list[missing_indexes[offset]] = batch_providers[offset]

            for i, item in enumerate(merged_items):
                source_text = source_texts[i] if i < len(source_texts) else item['text']
                trans_text = translated_list[i]
                provider = provider_list[i]
                known_text, known_provider = self.get_best_known_translation(source_text)
                if known_text and not self.should_replace_provider(known_provider, provider):
                    trans_text = known_text
                    provider = known_provider
                if not trans_text:
                    prefix = "AI" if self.has_any_multimodal_ai() else "Google"
                    icon = "🧠" if prefix == "AI" else "🌐"
                    self.status_msg.emit(f"{icon} {prefix} {i+1}/{len(merged_items)}")
                    try:
                        trans_text, provider = self.translate_text_preferred_with_provider(source_text)
                    except Exception:
                        trans_text = source_text
                        provider = ""

                trans_text = trans_text.strip()
                cache_key = (
                    self.detect_source_language(source_text),
                    normalize_ocr_text(source_text)
                )
                self.remember_translation(cache_key, trans_text)
                self.remember_preferred_text(source_text, trans_text, provider or "")
                self.remember_hud_observation(
                    source_text,
                    (item['x'], item['y'], item['w'], item['h']),
                    trans_text,
                    provider or "",
                )
                final_results.append((trans_text, item['x'], item['y'], item['w'], item['h']))
                final_providers.append(self._canonical_cache_provider(provider))

            if final_results and all(final_providers):
                exact_context = self._exact_image_cache_context(offset_x, offset_y)
                cache_provider = min(
                    final_providers,
                    key=self.get_translation_provider_priority,
                )
                self.exact_image_cache.put(
                    img,
                    exact_context,
                    final_results,
                    cache_provider,
                    current_combined_text,
                )
                self.last_provider = cache_provider
            self.last_results = final_results
            _log(f"⑩ 全部完成！共 {len(final_results)} 筆結果")
            self.status_msg.emit("✅ 翻譯完成")
            self.trigger_background_threshold_refresh(img, offset_x, offset_y, self.scan_mode)
            self.finished.emit(final_results)

        except Exception as e:
            logger.error(f"Error: {e}")
            self.status_msg.emit("⚠️ 翻譯失敗")
            fallback = [(item['text'], item['x'], item['y'], item['w'], item['h']) for item in merged_items]
            self.last_results = fallback
            self.finished.emit(fallback)

    def handle_empty(self, message="💤 畫面無文字"):
        if self.last_combined_text != "":
            self.status_msg.emit(message)
            self.last_combined_text = ""
            self.last_results = []
        self.finished.emit([])
        self.show_ui.emit()




