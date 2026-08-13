# ==========================================
# 🌟 雲朵翻譯姬 v3.0 - 螢幕 OCR 即時翻譯工具 (邏輯修正版) (｀・ω・´)ゞ
# ==========================================
# 核心引擎: Windows OCR 優先、可選 OCR 後端
# 翻譯引擎: Google + Gemma (多模態支援)
# 架構優化: 移除多餘引用，清理過期的 Argos 備援邏輯
# ==========================================

import os
from copy import deepcopy
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
import math
import time
import threading
import traceback
from collections import Counter, OrderedDict, deque
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
    as_completed,
    wait,
)
from urllib import request, error
from urllib.parse import urlsplit
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
from frame_gate import FrameGate
from scan_pipeline import (
    ScanErrorCode,
    ScanOutcome,
    ScanRequestToken,
    ScanStage,
    ScanTrace,
    ScanTraceEvent,
)
from knowledge_retrieval import pack_revision_token
import localization
from model_catalog import (
    LOCAL_MODEL_IDS,
    WORKER_DEFAULT_MODEL,
    WORKER_MODEL_CHOICES,
    REMOTE_TRANSLATION_MODEL_IDS,
    WORKER_MODEL_IDS,
    get_model_spec,
)
from translation_registry import TranslationProviderRegistry, TranslationProviderRegistryConfig
from translation_providers import (
    GemmaTranslationProvider,
    GoogleTranslationProvider,
    LocalMultimodalProvider,
    LocalRequestCancelled,
    classify_region_vision_failure,
)
from translation_contracts import TranslationResult
from translation_orchestrator import TranslationOrchestrator
from local_vision_runtime import LocalVisionRuntime
from local_runtime_profiles import resolve_runtime_profile
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
LOCAL_VISION_REDUCED_IMAGE_MAX_WIDTH = 1280
LOCAL_VISION_TINY_TEXT_HEIGHT = 20
AI_TOP_CONTEXT_RATIO = 0.22
NOISE_ONLY_PATTERN = re.compile(r'^[-_=.,|/\\:;~^]+$')
HAS_CJK_PATTERN = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
GOOGLE_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMMA_MODEL = WORKER_DEFAULT_MODEL
LOCAL_GEMMA_MODEL_ID = "gemma-3-4b-it-local"
SETTINGS_PATHS = create_settings_paths(os.path.dirname(__file__))
MIN_BUBBLE_FONT_PT = 8
MIN_BUBBLE_WIDTH = 96
MIN_BUBBLE_HEIGHT = 42
SUPPORTED_AI_MODELS = list(WORKER_MODEL_CHOICES)
SUPPORTED_GEMMA_MODEL_NAMES = WORKER_MODEL_IDS
SUPPORTED_REMOTE_MODEL_NAMES = REMOTE_TRANSLATION_MODEL_IDS
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
MANGA_GRID_RECOVERY_ENV = "CLOUDHIME_MANGA_GRID_RECOVERY"
MANGA_GRID_RECOVERY_MAX_ITEMS = 6
MANGA_GRID_RECOVERY_SCORE_MARGIN = 3
FULLSCREEN_OCR_DOWNSCALE_TRIGGER = 2400
FULLSCREEN_OCR_MAX_DIM = 4096
FULLSCREEN_OCR_MIN_SCALE = 1.5
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


def resolve_local_vision_image_max_width(img_np, hints=None, max_width=None):
    """Choose a conservative local-Vision image width without upscaling."""
    try:
        width = max(0, int(img_np.shape[1]))
    except (AttributeError, IndexError, TypeError, ValueError):
        return AI_IMAGE_MAX_WIDTH
    if max_width is not None:
        try:
            requested = int(max_width)
        except (TypeError, ValueError):
            requested = AI_IMAGE_MAX_WIDTH
        return min(width, max(1, requested))
    if width <= LOCAL_VISION_REDUCED_IMAGE_MAX_WIDTH:
        return width
    for hint in hints or ():
        try:
            if int(hint.get("h", 0)) <= LOCAL_VISION_TINY_TEXT_HEIGHT:
                return min(width, AI_IMAGE_MAX_WIDTH)
        except (AttributeError, TypeError, ValueError):
            return min(width, AI_IMAGE_MAX_WIDTH)
    return min(width, LOCAL_VISION_REDUCED_IMAGE_MAX_WIDTH)

# ==========================================
# 🛡️ 核心：Windows 原生熱鍵過濾器
# ==========================================
from cloudhime_core import is_valid_content, needs_cjk_tight_join, merge_horizontal_lines
from ocr_text_processing import normalize_ocr_text

class OCRWorker(QObject):
    finished = Signal(list)
    scan_finished = Signal(int, list)
    streaming_update = Signal(list)  # [(partial_text, x, y, w, h)] 打字機效果用
    translation_stream_update = Signal(int, str, str, int, int, int, int)  # (index, partial_text, provider, x, y, w, h) 串流翻譯用
    scan_translation_stream_update = Signal(int, int, str, str, int, int, int, int)
    status_msg = Signal(str)
    scan_status_msg = Signal(int, str)
    hide_ui = Signal()
    show_ui = Signal()
    threshold_suggested = Signal(int)
    gemma_model_changed = Signal(str, str)
    local_model_status = Signal(str, str)
    local_vision_status = Signal(str, str)
    japanese_rescue_status = Signal(str, str)

    def __init__(self, local_runtime_coordinator=None):
        super().__init__()
        startup_log("OCRWorker.__init__ start")
        self._local_runtime_coordinator = local_runtime_coordinator
        self._local_vision_runtime_lease = None
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
        self.frame_gate = FrameGate()
        self.last_scan_trace = ScanTrace()
        self._scan_request_lock = threading.RLock()
        self._scan_generation = 0
        self._scan_request_sequence = 0
        self._pending_scan_requests = deque()
        self._active_scan_request = None
        self.active_knowledge_pack = None
        self.knowledge_revision_token = "knowledge-pack:none"
        self.gemma_call_timestamps = {model_name: [] for model_name in SUPPORTED_REMOTE_MODEL_NAMES}
        self._translation_registry_batch_depth = 0
        self._translation_registry_batch_dirty = False
        self._pending_gemma_prompt = ""
        self._last_local_vision_request_metrics = {}
        self.translation_target_lang = localization.get_translation_target_lang(localization.DEFAULT_UI_LANGUAGE)
        self.google_translation_provider = GoogleTranslationProvider(target_lang=self.translation_target_lang)
        self.gemma_translation_provider = GemmaTranslationProvider(
            google_api_key="",
            gemma_model=DEFAULT_GEMMA_MODEL,
            gemma_prompt="",
            target_lang=self.translation_target_lang,
            auto_switch_enabled=False,
            supported_models=SUPPORTED_REMOTE_MODEL_NAMES,
        )
        app_root = Path(__file__).resolve().parent
        self._local_vision_assets = resolve_preferred_vision_assets(app_root)
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
        self.local_multimodal_cpu_only = False
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
        self.translation_registry_error_code = ""
        
        # 狀態標記
        
        self.binary_threshold = 100 
        self.last_scanned_img = None
        self.last_scanned_offset = (0, 0)
        self._bg_threshold_running = False  # 防止重複提交背景任務
        self._bg_threshold_executor = ThreadPoolExecutor(max_workers=1)
        self._local_vision_executor = ThreadPoolExecutor(max_workers=1)
        self._local_vision_load_future = None
        self._local_vision_reconfigure_future = None
        self._local_vision_reconfigure_generation = 0
        self._local_vision_reconfigure_waiting_for_load = False
        self._local_vision_cancel_event = threading.Event()
        self._local_vision_lifecycle_lock = threading.RLock()
        self._local_vision_lifecycle_generation = 0
        self._japanese_rescue_executor = ThreadPoolExecutor(max_workers=1)
        self._japanese_rescue_load_future = None
        self.japanese_rescue_runtime = JapaneseOCRRuntime(
            resolve_japanese_ocr_assets(),
            progress_callback=lambda phase, progress: OCRWorker._emit_japanese_rescue_status(
                self, "progress", f"{progress}|{phase}"
            ),
        )
        
        try:
            runtime_kwargs = {
                "gpu_layers": 0 if self.local_multimodal_cpu_only else 999,
                "progress_callback": lambda phase, progress: OCRWorker._emit_local_vision_status(
                    self, "progress", f"{progress}|{phase}"
                ),
            }
            if self._local_runtime_coordinator is not None:
                self._local_vision_runtime_lease = self._local_runtime_coordinator.acquire(
                    self._local_vision_assets,
                    profile="vision",
                    runtime_kwargs=runtime_kwargs,
                )
                self.local_vision_runtime = self._local_vision_runtime_lease.runtime
            else:
                self.local_vision_runtime = LocalVisionRuntime(
                    self._local_vision_assets,
                    profile="vision",
                    **runtime_kwargs,
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

    def set_scan_generation(self, generation):
        normalized = max(0, int(generation))
        with self._scan_request_lock:
            self._scan_generation = max(self._scan_generation, normalized)
        return self._scan_generation

    def enqueue_scan_request(self, generation):
        normalized = max(0, int(generation))
        with self._scan_request_lock:
            self._scan_generation = max(self._scan_generation, normalized)
            self._scan_request_sequence += 1
            request = ScanRequestToken(
                generation=normalized,
                request_id=self._scan_request_sequence,
                enqueued_at_ms=time.monotonic() * 1000.0,
            )
            self._pending_scan_requests.append(request)
            return request

    def _take_scan_request(self):
        with self._scan_request_lock:
            if self._pending_scan_requests:
                return self._pending_scan_requests.popleft()
            self._scan_request_sequence += 1
            return ScanRequestToken(
                generation=self._scan_generation,
                request_id=self._scan_request_sequence,
                enqueued_at_ms=time.monotonic() * 1000.0,
            )

    def _active_scan_is_current(self):
        request = self._active_scan_request
        if request is None:
            return True
        with self._scan_request_lock:
            return request.generation == self._scan_generation

    def _abort_stale_scan(self, stage):
        if self._active_scan_is_current():
            return False
        if not self.last_scan_trace.events or (
            self.last_scan_trace.events[-1].outcome is not ScanOutcome.CANCELLED
        ):
            self._record_scan_event(
                stage,
                ScanOutcome.CANCELLED,
                error_code=ScanErrorCode.SCAN_CANCELLED,
                detail="pipeline_cancelled",
            )
        return True

    def _reset_scan_trace(self):
        self.last_scan_trace = ScanTrace()
        self._last_local_vision_request_metrics = {}

    def _capture_local_vision_request_metrics(self, provider):
        getter = getattr(provider, "get_last_request_metrics", None)
        if not callable(getter):
            self._last_local_vision_request_metrics = {}
            return
        try:
            raw = getter()
        except Exception:
            self._last_local_vision_request_metrics = {}
            return
        if not isinstance(raw, dict):
            self._last_local_vision_request_metrics = {}
            return
        metrics = {}
        for key in (
            "prompt_tokens", "completion_tokens", "total_tokens",
            "prompt_n", "predicted_n", "prompt_ms", "predicted_ms",
        ):
            value = raw.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not math.isfinite(float(value)) or value < 0:
                continue
            metrics[key] = value
        self._last_local_vision_request_metrics = metrics

    def _record_scan_event(
        self,
        stage,
        outcome,
        *,
        started_at=None,
        error_code=ScanErrorCode.NONE,
        detail="",
        provider="",
        fallback_reason="",
        exception=None,
        item_count=0,
    ):
        elapsed_ms = 0.0
        if started_at is not None:
            elapsed_ms = max(0.0, (time.perf_counter() - started_at) * 1000.0)
        self.last_scan_trace = self.last_scan_trace.append(
            ScanTraceEvent(
                stage=stage,
                outcome=outcome,
                error_code=error_code,
                detail=detail,
                provider=provider,
                fallback_reason=fallback_reason,
                exception=exception,
                elapsed_ms=elapsed_ms,
                item_count=item_count,
            )
        )

    def _observe_frame_gate(self, image, context):
        started_at = time.perf_counter()
        try:
            observation = self.frame_gate.observe(image, context)
            detail = f"frame_cache_shadow_{observation.classification}"
            item_count = observation.sampled_pixels
        except Exception:
            detail = "frame_cache_shadow_failed"
            item_count = 0
        return detail, item_count, started_at

    def _record_render_dispatch(self, results):
        self._record_scan_event(
            ScanStage.RENDER_DISPATCH,
            ScanOutcome.SUCCESS,
            detail="render_dispatch_completed",
            item_count=len(results),
        )

    def _emit_scan_finished(self, results):
        if self._abort_stale_scan(ScanStage.RENDER_DISPATCH):
            return False
        self._record_render_dispatch(results)
        request = self._active_scan_request
        generation = request.generation if request is not None else self._scan_generation
        self.finished.emit(results)
        self.scan_finished.emit(generation, results)
        return True

    def _emit_scan_status(self, message):
        request = self._active_scan_request
        generation = request.generation if request is not None else self._scan_generation
        self.status_msg.emit(message)
        self.scan_status_msg.emit(generation, message)

    def _emit_scan_translation_stream_update(
        self, index, partial_text, provider, x, y, w, h
    ):
        if self._abort_stale_scan(ScanStage.TRANSLATION):
            return False
        request = self._active_scan_request
        generation = request.generation if request is not None else self._scan_generation
        self.translation_stream_update.emit(
            index, partial_text, provider, x, y, w, h
        )
        self.scan_translation_stream_update.emit(
            generation, index, partial_text, provider, x, y, w, h
        )
        return True

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
            selected_local_model = config.gemma_model in LOCAL_MODEL_IDS
            embedded_runtime = getattr(self, "local_vision_runtime", None)
            runtime_state = getattr(embedded_runtime, "_state", None)
            has_embedded_runtime = embedded_runtime is not None
            runtime_ready = OCRWorker._owned_local_runtime_ready(
                self, embedded_runtime, runtime_state
            )
            local_text_runtime_required = bool(config.gemma_enabled and selected_local_model)
            self._local_text_runtime_required = local_text_runtime_required
            desired_profile = (
                "vision"
                if config.gemma_enabled and config.local_multimodal_enabled
                else "text"
                if local_text_runtime_required
                else None
            )
            self._local_runtime_profile = (
                desired_profile if has_embedded_runtime else None
            )

            self.local_multimodal_provider.target_lang = config.target_lang
            self.local_multimodal_provider.enabled = bool(
                config.local_multimodal_enabled or local_text_runtime_required
            )
            self.local_multimodal_provider.timeout_seconds = config.local_multimodal_timeout_seconds
            self.local_multimodal_provider.update_generation_config(
                temperature=config.local_gemma_temperature,
                repeat_penalty=config.local_gemma_repeat_penalty,
            )
            if has_embedded_runtime:
                runtime_profile = getattr(embedded_runtime, "profile_name", "vision")
                if (
                    runtime_ready
                    and runtime_state is not None
                    and runtime_state.name == "ready"
                    and desired_profile == runtime_profile
                ):
                    self.local_multimodal_provider.update_runtime(
                        runtime_state.base_url,
                        config.local_multimodal_model,
                        ready=True,
                    )
                else:
                    self.local_multimodal_provider.update_runtime("", "", ready=False)
            else:
                # A configured endpoint is not proof that this app owns a live server.
                self.local_multimodal_provider.update_runtime("", "", ready=False)

            if selected_local_model:
                active_gemma = self.local_multimodal_provider
            else:
                active_gemma = self.gemma_translation_provider
                active_gemma.name = "gemma"
            self.translation_registry = TranslationProviderRegistry([
                active_gemma,
                self.google_translation_provider,
                self.local_multimodal_provider,
            ])
            if selected_local_model:
                self.translation_registry.register("gemma", self.local_multimodal_provider)
            self.translation_registry_error_code = ""
            if has_embedded_runtime and desired_profile is None:
                OCRWorker._stop_local_vision_runtime(self)
                self.local_multimodal_provider.update_runtime("", "", ready=False)
            elif desired_profile is not None:
                self.request_local_vision_start()
        except Exception as exc:
            self.translation_registry_error_code = "translation_registry_refresh_failed"
            logger.error(f"[TranslationRegistry] {self.translation_registry_error_code} type={type(exc).__name__}")

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
        if getattr(self, "_local_runtime_profile", None) == "text":
            status, *details = args
            if status in {"starting", "progress"}:
                status = "loading"
            OCRWorker._emit_local_model_status(self, status, *details)
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

    def _prepare_and_start_local_vision(self, *, start_generation=None):
        runtime = self.local_vision_runtime
        cancel_event = getattr(self, "_local_vision_cancel_event", None)
        start_is_stale = (
            start_generation is not None
            and start_generation != getattr(self, "_local_vision_lifecycle_generation", start_generation)
        )
        if start_is_stale or (cancel_event is not None and cancel_event.is_set()):
            return OCRWorker._stop_local_vision_runtime(self)
        profile_name = getattr(self, "_local_runtime_profile", None)
        if profile_name is None:
            if getattr(self, "local_multimodal_enabled", False):
                profile_name = "vision"
            elif getattr(self, "_local_text_runtime_required", False):
                profile_name = "text"
        profile = resolve_runtime_profile(profile_name) if profile_name else None

        if profile is not None:
            runtime_owner = getattr(self, "_local_vision_runtime_lease", None) or runtime
            set_profile = getattr(runtime_owner, "set_profile", None)
            current_profile = getattr(runtime, "profile_name", profile.name)
            if callable(set_profile) and current_profile != profile.name:
                try:
                    set_profile(profile.name)
                except RuntimeError as exc:
                    if str(exc) != "runtime_profile_requires_stop":
                        raise
                    OCRWorker._stop_local_vision_runtime(self)
                    set_profile(profile.name)

        assets = getattr(self, "_local_vision_assets", None)
        if assets is not None:
            progress_callback = lambda phase, progress: OCRWorker._emit_local_vision_status(
                self, "progress", f"{progress}|{phase}"
            )
            if profile is not None and profile.name == "text":
                ensure_vision_model_assets(
                    assets,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                    required_fields=profile.required_asset_fields,
                )
            else:
                ensure_vision_model_assets(
                    assets,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                )
        start_is_stale = (
            start_generation is not None
            and start_generation != getattr(self, "_local_vision_lifecycle_generation", start_generation)
        )
        if start_is_stale or (cancel_event is not None and cancel_event.is_set()):
            return OCRWorker._stop_local_vision_runtime(self)
        if cancel_event is None:
            return runtime.start()
        return runtime.start(cancel_event=cancel_event)

    def _owned_local_runtime_ready(self, runtime, state):
        if runtime is None or state is None or getattr(state, "name", "") != "ready":
            return False
        try:
            process = runtime.owned_process
            process_running = process is not None and process.poll() is None
        except Exception:
            return False
        if not process_running:
            return False
        base_url = getattr(state, "base_url", "")
        if not isinstance(base_url, str):
            return False
        try:
            parsed = urlsplit(base_url)
            return (
                parsed.scheme == "http"
                and parsed.hostname == "127.0.0.1"
                and parsed.port is not None
                and parsed.path == "/v1"
                and not parsed.username
                and not parsed.password
                and not parsed.query
                and not parsed.fragment
            )
        except (TypeError, ValueError):
            return False

    def _local_runtime_provider_synced(self, state):
        provider = getattr(self, "local_multimodal_provider", None)
        if provider is None or state is None:
            return False
        runtime_endpoint = getattr(state, "base_url", "").rstrip("/")
        expected_model = getattr(self, "local_multimodal_model", "gemma-3-4b-it")
        return (
            bool(getattr(provider, "_runtime_ready", False))
            and getattr(provider, "base_url", "").rstrip("/") == runtime_endpoint
            and getattr(provider, "model_name", "") == expected_model
        )

    def _wait_for_local_vision_callback(self, future, deadline):
        while getattr(self, "_local_vision_load_future", None) is future:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.005, remaining))
        return True

    def ensure_local_runtime_ready(self, timeout_seconds):
        """啟動或等待本 worker 持有的 loopback LocalVisionRuntime。"""
        try:
            timeout = float(timeout_seconds)
        except (TypeError, ValueError):
            return False
        if timeout < 0:
            return False

        deadline = time.monotonic() + timeout
        runtime = getattr(self, "local_vision_runtime", None)
        state = getattr(runtime, "_state", None) if runtime is not None else None
        if (
            OCRWorker._owned_local_runtime_ready(self, runtime, state)
            and OCRWorker._local_runtime_provider_synced(self, state)
        ):
            return True

        try:
            self.request_local_vision_start()
        except Exception:
            return False

        future = getattr(self, "_local_vision_load_future", None)
        if future is not None:
            try:
                future.result(timeout=max(0.0, deadline - time.monotonic()))
            except FutureTimeoutError:
                return False
            except Exception:
                OCRWorker._wait_for_local_vision_callback(self, future, deadline)
                return False
            if not OCRWorker._wait_for_local_vision_callback(self, future, deadline):
                return False

        state = getattr(runtime, "_state", None) if runtime is not None else None
        return (
            OCRWorker._owned_local_runtime_ready(self, runtime, state)
            and OCRWorker._local_runtime_provider_synced(self, state)
        )

    def local_runtime_evidence(self):
        """回傳不含內容或密鑰的本 worker 本機 runtime 證據。"""
        runtime = getattr(self, "local_vision_runtime", None)
        state = getattr(runtime, "_state", None) if runtime is not None else None
        try:
            process = runtime.owned_process if runtime is not None else None
        except Exception:
            process = None
        assets = getattr(self, "_local_vision_assets", None)
        if assets is None and runtime is not None:
            assets = getattr(runtime, "_assets", None)
        server_path = getattr(assets, "server_path", None)
        profile = getattr(runtime, "profile_name", "") if runtime is not None else ""
        ready = OCRWorker._owned_local_runtime_ready(self, runtime, state)
        gpu_offload_layers = 0
        gpu_total_layers = 0
        gpu_process_confirmed = False
        if ready:
            try:
                gpu_offload_layers = max(0, int(getattr(state, "gpu_offload_layers", 0)))
                gpu_total_layers = max(0, int(getattr(state, "gpu_total_layers", 0)))
                gpu_process_confirmed = getattr(state, "gpu_process_confirmed", False) is True
            except (TypeError, ValueError):
                gpu_offload_layers = 0
                gpu_total_layers = 0
                gpu_process_confirmed = False
        mode = getattr(state, "mode", "") if ready else ""
        has_process_probe_evidence = hasattr(state, "gpu_process_confirmed")
        state_backend_confirmed = getattr(state, "gpu_backend_confirmed", None)
        if not has_process_probe_evidence or state_backend_confirmed is None:
            gpu_backend_confirmed = (
                mode == "gpu"
                and gpu_offload_layers > 0
                and gpu_total_layers >= gpu_offload_layers
            )
        else:
            gpu_backend_confirmed = (
                mode == "gpu"
                and state_backend_confirmed is True
                and (
                    gpu_process_confirmed
                    or (gpu_offload_layers > 0 and gpu_total_layers >= gpu_offload_layers)
                )
            )
        evidence = {
            "ready": ready,
            "profile": profile if profile in {"text", "vision"} else "",
            "mode": mode,
            "gpu_offload_layers": gpu_offload_layers,
            "gpu_total_layers": gpu_total_layers,
            "gpu_backend_confirmed": gpu_backend_confirmed,
            "base_url": getattr(state, "base_url", "") if ready else "",
            "owned_process": process is not None,
            "owned_process_handle": process,
            "pid": getattr(process, "pid", None) if process is not None else None,
            "server_path": str(server_path) if server_path is not None else "",
        }
        if has_process_probe_evidence:
            evidence["gpu_process_confirmed"] = gpu_process_confirmed
        return evidence

    def request_local_vision_start(self):
        runtime = getattr(self, "local_vision_runtime", None)
        profile_name = getattr(self, "_local_runtime_profile", None)
        if profile_name is None:
            if getattr(self, "local_multimodal_enabled", False):
                profile_name = "vision"
            elif getattr(self, "_local_text_runtime_required", False):
                profile_name = "text"

        if not self.use_gemma_translation or profile_name is None:
            if runtime is not None and profile_name is None:
                OCRWorker._stop_local_vision_runtime(self)
                self.local_multimodal_provider.update_runtime("", "", False)
            return
        if runtime is None:
            OCRWorker._emit_local_vision_status(self, "failed", "runtime_missing")
            return

        state = getattr(runtime, "_state", None)
        current_profile = getattr(runtime, "profile_name", profile_name)
        if state is not None and state.name == "ready":
            if not OCRWorker._owned_local_runtime_ready(self, runtime, state):
                self.local_multimodal_provider.update_runtime("", "", ready=False)
                OCRWorker._emit_local_vision_status(self, "failed", "runtime_ownership_invalid")
                return
            if current_profile != profile_name:
                OCRWorker._schedule_local_vision_reconfigure(self)
                return
            self.local_multimodal_provider.update_runtime(
                state.base_url,
                getattr(self, "local_multimodal_model", "gemma-3-4b-it"),
                ready=True,
            )
            OCRWorker._emit_local_vision_status(self, state.name, state.detail)
            return

        lifecycle_lock = getattr(self, "_local_vision_lifecycle_lock", None)
        if lifecycle_lock is None:
            lifecycle_lock = threading.RLock()
            self._local_vision_lifecycle_lock = lifecycle_lock

        executor = getattr(self, "_local_vision_executor", getattr(self, "vision_executor", None))
        if executor is None:
            OCRWorker._emit_local_vision_status(self, "failed", "vision_executor_missing")
            return
        try:
            with lifecycle_lock:
                pending_future = getattr(self, "_local_vision_load_future", None)
                if pending_future is not None and not pending_future.done():
                    return
                OCRWorker._emit_local_vision_status(self, "starting", "")
                cancel_event = getattr(self, "_local_vision_cancel_event", None)
                start_generation = getattr(self, "_local_vision_lifecycle_generation", 0)
                if cancel_event is not None:
                    cancel_event.clear()
                if (
                    start_generation != getattr(
                        self, "_local_vision_lifecycle_generation", start_generation
                    )
                    or (cancel_event is not None and cancel_event.is_set())
                ):
                    return
                future = executor.submit(
                    lambda: OCRWorker._prepare_and_start_local_vision(
                        self, start_generation=start_generation
                    )
                )
                self._local_vision_load_generation = start_generation
                try:
                    future._cloudhime_local_vision_generation = start_generation
                except Exception:
                    pass
                self._local_vision_load_future = future
        except Exception as exc:
            self._local_vision_load_future = None
            self.local_multimodal_provider.update_runtime("", "", False)
            OCRWorker._emit_local_vision_status(self, "failed", f"{type(exc).__name__}: {exc}")
            return
        future.add_done_callback(
            lambda completed: OCRWorker._on_local_vision_load_done(self, completed)
        )

    def _restore_configured_text_provider(self):
        registry = getattr(self, "translation_registry", None)
        if registry is None:
            return
        provider_name = "local_multimodal_provider" if self._is_local_model_active() else "gemma_translation_provider"
        provider = getattr(self, provider_name, None)
        if provider is not None:
            registry.register("gemma", provider)
    def _on_local_vision_load_done(self, future):
        try:
            state = future.result()
        except Exception as exc:
            self.local_multimodal_provider.update_runtime("", "", False)
            OCRWorker._emit_local_vision_status(
                self,
                "failed",
                f"{type(exc).__name__}: {exc}",
            )
        else:
            load_generation = getattr(
                future,
                "_cloudhime_local_vision_generation",
                getattr(self, "_local_vision_load_generation", None),
            )
            current_generation = getattr(
                self, "_local_vision_lifecycle_generation", load_generation
            )
            if load_generation is not None and current_generation != load_generation:
                if getattr(self, "_local_vision_load_future", None) is not future:
                    return
                if getattr(state, "name", "") == "ready":
                    OCRWorker._stop_local_vision_runtime(self)
                self.local_multimodal_provider.update_runtime("", "", False)
                OCRWorker._emit_local_vision_status(self, "stopped", "stale_start")
                return
            ready = state.name == "ready" and OCRWorker._owned_local_runtime_ready(
                self, getattr(self, "local_vision_runtime", None), state
            )
            detail = state.detail
            if state.name == "ready" and not ready:
                detail = "runtime_ownership_invalid"
            self.local_multimodal_provider.update_runtime(
                state.base_url if ready else "",
                getattr(self, "local_multimodal_model", "gemma-3-4b-it") if ready else "",
                ready=ready,
            )
            if ready:
                self._refresh_translation_registry()
            OCRWorker._emit_local_vision_status(self, state.name if ready else "failed", detail)
        finally:
            if getattr(self, "_local_vision_load_future", None) is future:
                self._local_vision_load_future = None
                self._local_vision_load_generation = None
    request_local_vision_load = request_local_vision_start

    def _invalidate_local_vision_start(self):
        lifecycle_lock = getattr(self, "_local_vision_lifecycle_lock", None)
        if lifecycle_lock is None:
            lifecycle_lock = threading.RLock()
            self._local_vision_lifecycle_lock = lifecycle_lock
        with lifecycle_lock:
            self._local_vision_lifecycle_generation = (
                getattr(self, "_local_vision_lifecycle_generation", 0) + 1
            )
            cancel_event = getattr(self, "_local_vision_cancel_event", None)
            if cancel_event is not None:
                cancel_event.set()
    def _stop_local_vision_runtime(self):
        """Stop only the runtime owned by this worker, safely and observably."""
        lease = getattr(self, "_local_vision_runtime_lease", None)
        runtime = getattr(self, "local_vision_runtime", None)
        stopper = (
            getattr(lease, "stop", None)
            if lease is not None
            else getattr(runtime, "stop", None)
        )
        if not callable(stopper):
            return None
        try:
            return stopper()
        except Exception as exc:
            logger.error(f"[LocalVisionRuntime] stop failed type={type(exc).__name__}")
            return None

    def shutdown_local_vision_runtime(self):
        lifecycle_lock = getattr(self, "_local_vision_lifecycle_lock", None)
        if lifecycle_lock is None:
            lifecycle_lock = threading.RLock()
            self._local_vision_lifecycle_lock = lifecycle_lock
        with lifecycle_lock:
            self._local_vision_lifecycle_generation = (
                getattr(self, "_local_vision_lifecycle_generation", 0) + 1
            )
            cancel_event = getattr(self, "_local_vision_cancel_event", None)
            if cancel_event is not None:
                cancel_event.set()
            runtime = getattr(self, "local_vision_runtime", None)
            if runtime is not None:
                OCRWorker._stop_local_vision_runtime(self)

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

    def set_knowledge_pack(self, pack):
        """Set the active pack snapshot and invalidate all translation/image memories."""
        if pack is None:
            normalized = None
            revision_token = "knowledge-pack:none"
        else:
            normalized = deepcopy(dict(pack))
            revision_token = pack_revision_token(normalized)
        if revision_token == getattr(self, "knowledge_revision_token", "knowledge-pack:none"):
            return
        for provider in (
            getattr(self, "gemma_translation_provider", None),
            getattr(self, "local_multimodal_provider", None),
        ):
            setter = getattr(provider, "set_knowledge_pack", None)
            if setter is not None:
                setter(normalized)
        self.active_knowledge_pack = normalized
        self.knowledge_revision_token = revision_token
        self._clear_translation_memories()

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
            getattr(self, "knowledge_revision_token", "knowledge-pack:none"),
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
        if normalized == "local_multimodal":
            return normalized
        if normalized == "gemma":
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
            OCRWorker._invalidate_local_vision_start(self)
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

    def _reconfigure_local_vision_runtime(self):
        runtime = getattr(self, "local_vision_runtime", None)
        if runtime is None:
            return
        OCRWorker._stop_local_vision_runtime(self)
        runtime_owner = getattr(self, "_local_vision_runtime_lease", None) or runtime
        setter = getattr(runtime_owner, "set_gpu_layers", None)
        if callable(setter):
            setter(0 if bool(getattr(self, "local_multimodal_cpu_only", False)) else 999)
        profile_name = getattr(self, "_local_runtime_profile", None)
        if profile_name is not None:
            profile_setter = getattr(runtime_owner, "set_profile", None)
            if callable(profile_setter):
                profile_setter(profile_name)

    def _submit_local_vision_reconfigure(self, generation):
        executor = getattr(self, "_local_vision_executor", getattr(self, "vision_executor", None))
        if executor is None:
            OCRWorker._emit_local_vision_status(self, "failed", "vision_executor_missing")
            return
        try:
            future = executor.submit(
                lambda: OCRWorker._reconfigure_local_vision_runtime(self)
            )
        except Exception as exc:
            self._local_vision_reconfigure_future = None
            OCRWorker._emit_local_vision_status(self, "failed", f"{type(exc).__name__}: {exc}")
            return

        self._local_vision_reconfigure_future = future
        future.add_done_callback(
            lambda completed: OCRWorker._on_local_vision_reconfigure_done(
                self, completed, generation
            )
        )

    def _on_local_vision_load_finished_for_reconfigure(self, _future):
        if not getattr(self, "_local_vision_reconfigure_waiting_for_load", False):
            return
        self._local_vision_reconfigure_waiting_for_load = False
        OCRWorker._schedule_local_vision_reconfigure(self)

    def _schedule_local_vision_reconfigure(self):
        generation = getattr(self, "_local_vision_reconfigure_generation", 0) + 1
        self._local_vision_reconfigure_generation = generation

        pending = getattr(self, "_local_vision_reconfigure_future", None)
        if pending is not None and not pending.done():
            return

        pending_load = getattr(self, "_local_vision_load_future", None)
        if pending_load is not None and not pending_load.done():
            if not getattr(self, "_local_vision_reconfigure_waiting_for_load", False):
                self._local_vision_reconfigure_waiting_for_load = True
                pending_load.add_done_callback(
                    lambda completed: OCRWorker._on_local_vision_load_finished_for_reconfigure(
                        self, completed
                    )
                )
            return

        self._local_vision_reconfigure_waiting_for_load = False
        OCRWorker._submit_local_vision_reconfigure(self, generation)

    def _on_local_vision_reconfigure_done(self, future, generation):
        if self._local_vision_reconfigure_future is future:
            self._local_vision_reconfigure_future = None
        try:
            future.result()
        except Exception as exc:
            if generation != getattr(self, "_local_vision_reconfigure_generation", generation):
                OCRWorker._schedule_local_vision_reconfigure(self)
            else:
                OCRWorker._emit_local_vision_status(
                    self, "failed", f"{type(exc).__name__}: {exc}"
                )
            return

        if generation != getattr(self, "_local_vision_reconfigure_generation", generation):
            OCRWorker._schedule_local_vision_reconfigure(self)
            return
        if self.use_gemma_translation and (
            getattr(self, "_local_runtime_profile", None) is not None
            or getattr(self, "local_multimodal_enabled", False)
            or getattr(self, "_local_text_runtime_required", False)
        ):
            self.request_local_vision_start()

    def set_local_multimodal_config(self, *, enabled, base_url, model_name, timeout_seconds, cpu_only=None):
        self.local_multimodal_enabled = bool(enabled)
        if not self.local_multimodal_enabled:
            OCRWorker._invalidate_local_vision_start(self)
        self.local_multimodal_base_url = (base_url or "").rstrip("/")
        self.local_multimodal_model = (model_name or "").strip()
        self.local_multimodal_timeout_seconds = max(1, int(timeout_seconds))
        previous_cpu_only = bool(getattr(self, "local_multimodal_cpu_only", False))
        self.local_multimodal_cpu_only = (
            previous_cpu_only if cpu_only is None else bool(cpu_only)
        )
        runtime = getattr(self, "local_vision_runtime", None)
        if runtime is not None and previous_cpu_only != self.local_multimodal_cpu_only:
            OCRWorker._schedule_local_vision_reconfigure(self)
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

        previous_temperature = float(getattr(self, "local_gemma_temperature", 0.2))
        previous_repeat_penalty = float(getattr(self, "local_gemma_repeat_penalty", 1.15))
        changed = (
            temperature != previous_temperature
            or repeat_penalty != previous_repeat_penalty
        )
        self.local_gemma_temperature = temperature
        self.local_gemma_repeat_penalty = repeat_penalty
        if changed:
            self._clear_translation_memories()
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
        model = (
            getattr(self, "active_gemma_model", self.gemma_model)
            or self.gemma_model
            or ""
        ).strip()
        spec = get_model_spec(model)
        return bool(
            self.use_gemma_translation
            and self.google_api_key
            and spec is not None
            and spec.locality == "remote"
            and spec.multimodal
        )

    def has_local_multimodal_ai(self):
        provider = getattr(self, "local_multimodal_provider", None)
        available = getattr(provider, "available", None)
        return (
            self.use_gemma_translation
            and bool(getattr(self, "local_multimodal_enabled", False))
            and bool(getattr(self, "local_multimodal_model", ""))
            and callable(available)
            and bool(available())
        )

    def has_any_multimodal_ai(self):
        return self.has_remote_multimodal_ai() or self.has_local_multimodal_ai()

    def has_multimodal_ai(self):
        return self.has_any_multimodal_ai()

    def has_ai_text_provider(self):
        return self.use_gemma_translation and self._get_translation_provider("gemma") is not None

    def _is_local_model_active(self):
        model = getattr(self, "active_gemma_model", self.gemma_model) or self.gemma_model
        return model in LOCAL_MODEL_IDS

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
            for name in SUPPORTED_REMOTE_MODEL_NAMES:
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
        for candidate in SUPPORTED_REMOTE_MODEL_NAMES:
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
            for candidate in SUPPORTED_REMOTE_MODEL_NAMES:
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


    def invalidate_scan_requests(self):
        """Invalidate active and queued scans before provider/runtime teardown."""
        with self._scan_request_lock:
            self._scan_generation += 1
            self._pending_scan_requests.clear()
            return self._scan_generation

    def cleanup(self):
        invalidate = getattr(self, "invalidate_scan_requests", None)
        if callable(invalidate):
            invalidate()
        if hasattr(self, '_bg_threshold_executor'):
            self._bg_threshold_executor.shutdown(wait=True)
        if hasattr(self, 'japanese_rescue_runtime'):
            self.japanese_rescue_runtime.disable()
        if hasattr(self, '_japanese_rescue_executor'):
            self._japanese_rescue_executor.shutdown(wait=True)
        local_provider = getattr(self, "local_multimodal_provider", None)
        if local_provider is not None:
            try:
                local_provider.close()
            except Exception:
                pass
        self.shutdown_local_vision_runtime()
        runtime_lease = getattr(self, "_local_vision_runtime_lease", None)
        if runtime_lease is not None:
            try:
                runtime_lease.release()
            except Exception as exc:
                logger.error(f"[LocalVisionRuntime] lease release failed type={type(exc).__name__}")
            self._local_vision_runtime_lease = None
            self.local_vision_runtime = None
        local_vision_executor = getattr(self, "_local_vision_executor", None)
        if local_vision_executor is not None:
            try:
                local_vision_executor.shutdown(wait=True, cancel_futures=True)
            except TypeError:
                # Python-compatible test doubles or older executors may not expose cancel_futures.
                try:
                    local_vision_executor.shutdown(wait=True)
                except Exception:
                    pass
            except Exception:
                pass

    def get_translation_provider_priority(self, provider):
        return translation_tools.get_translation_provider_priority(provider)

    def get_current_ai_provider(self):
        model = (
            getattr(self, "active_gemma_model", self.gemma_model)
            or self.gemma_model
            or ""
        ).strip()
        if self._is_local_model_active():
            return "local_multimodal"
        spec = get_model_spec(model)
        return spec.provider if spec is not None else "google"

    def sync_gemma_call_timestamps_from_provider(self, provider):
        timestamps = getattr(provider, "_call_timestamps", None)
        if not isinstance(timestamps, dict):
            return
        self.gemma_call_timestamps = {
            model_name: list(timestamps.get(model_name, []))
            for model_name in SUPPORTED_REMOTE_MODEL_NAMES
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

    def _translate_text_google_result(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return TranslationResult(text="", provider="google")
        provider = self._get_translation_provider("google")
        if provider is not None:
            return provider.translate(normalized_text)
        translated = translation_tools.translate_text_google(
            normalized_text,
            self.translators,
            self.translation_cache,
            target_lang=self.translation_target_lang,
            cache_limit=TRANSLATION_CACHE_LIMIT,
        )
        return TranslationResult(text=translated, provider="google")

    def translate_text_google(self, text):
        return self._translate_text_google_result(text).text

    def translate_text_google_with_provider(self, text):
        result = self._translate_text_google_result(text)
        return result.text, result.provider

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

    def build_ai_image_parts(self, img_np, max_width=AI_IMAGE_MAX_WIDTH):
        return translation_tools.build_ai_image_parts(img_np, max_width=max_width)

    def build_local_vision_image_parts(self, img_np, hints=None):
        max_width = resolve_local_vision_image_max_width(
            img_np,
            hints,
            max_width=getattr(self, "_local_vision_image_max_width", None),
        )
        return self.build_ai_image_parts(img_np, max_width=max_width)

    def _collect_screenshot_hint_items(self, ocr_result, min_confidence=0.35):
        raw_items = []
        for line in getattr(ocr_result, "lines", []) or []:
            text = normalize_ocr_text(getattr(line, "text", "") or "")
            if not text:
                continue
            if any(
                marker in text
                for marker in (
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

    def _translate_text_gemma_result(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return TranslationResult(text="", provider="gemma")
        provider = self._get_translation_provider("gemma")
        if provider is not None:
            result = provider.translate(normalized_text)
            reported_model = str(getattr(result, "model", None) or "").strip()
            if reported_model in SUPPORTED_GEMMA_MODEL_NAMES:
                self.active_gemma_model = reported_model
            elif not self._is_local_model_active():
                self.active_gemma_model = self.normalize_gemma_model(self.gemma_model)
            self.sync_gemma_call_timestamps_from_provider(provider)
            return TranslationResult(
                text=self.convert_to_trad(result.text),
                provider=getattr(result, "provider", None) or getattr(provider, "name", "gemma"),
                model=result.model,
                raw_text=getattr(result, "raw_text", None),
                from_cache=getattr(result, "from_cache", False),
                requested_provider=getattr(result, "requested_provider", None),
                fallback_reason=getattr(result, "fallback_reason", None),
            )
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
            return TranslationResult(text=cached, provider="gemma", model=model_name, from_cache=True)
        req_body = {
            "contents": [{"parts": [{"text": effective_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.9,
                "topK": 32,
                "maxOutputTokens": 1024,
                "responseMimeType": "text/plain",
            },
        }
        req = request.Request(
            GOOGLE_API_ENDPOINT.format(model=model_name),
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.google_api_key},
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
        return TranslationResult(text=translated, provider="gemma", model=model_name)

    def translate_text_gemma(self, text):
        return self._translate_text_gemma_result(text).text

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

    def _remember_screenshot_translation_result(self, result):
        normalized = TranslationResult(
            text=self.convert_to_trad(result.text),
            provider=getattr(result, "provider", None) or self.get_current_ai_provider(),
            model=getattr(result, "model", None),
            raw_text=getattr(result, "raw_text", None),
            from_cache=getattr(result, "from_cache", False),
            requested_provider=getattr(result, "requested_provider", None),
            fallback_reason=getattr(result, "fallback_reason", None),
        )
        self._last_screenshot_translation_result = normalized
        self._last_screenshot_translation_provider = normalized.provider
        return normalized.text

    def translate_screenshot_gemma(self, image_parts, source_text_hint=""):
        if not image_parts:
            raise ValueError("missing_image_context")
        self._last_screenshot_translation_provider = ""
        self._last_screenshot_translation_result = None
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
            primary_provider = getattr(result, "provider", None) or provider_name or self.get_current_ai_provider()
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
                    return self._remember_screenshot_translation_result(
                        TranslationResult(
                            text=fallback,
                            provider=fallback_provider or primary_provider,
                            model=getattr(result, "model", None),
                            requested_provider=(
                                getattr(result, "requested_provider", None)
                                or primary_provider
                            ),
                            fallback_reason=(
                                getattr(result, "fallback_reason", None)
                                or fallback_reason
                            ),
                        )
                    )
            return self._remember_screenshot_translation_result(
                TranslationResult(
                    text=translated,
                    provider=primary_provider,
                    model=getattr(result, "model", None),
                    raw_text=getattr(result, "raw_text", None),
                    from_cache=getattr(result, "from_cache", False),
                    requested_provider=getattr(result, "requested_provider", None),
                    fallback_reason=getattr(result, "fallback_reason", None),
                )
            )
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
                return self._remember_screenshot_translation_result(
                    TranslationResult(
                        text=fallback,
                        provider="google",
                        model=model_name,
                        requested_provider=self.get_current_ai_provider(),
                        fallback_reason=fallback_reason,
                    )
                )
            try:
                fallback = self.translate_text_gemma(source_text_hint)
            except Exception:
                fallback = ""
            if self._is_usable_text_fallback(source_text_hint, fallback):
                provider_name = self.get_current_ai_provider()
                return self._remember_screenshot_translation_result(
                    TranslationResult(
                        text=fallback,
                        provider=provider_name,
                        model=model_name,
                        requested_provider=provider_name,
                        fallback_reason=fallback_reason,
                    )
                )
        return self._remember_screenshot_translation_result(
            TranslationResult(
                text=translated,
                provider=self.get_current_ai_provider(),
                model=model_name,
            )
        )

    def translate_text_gemma_with_provider(self, text):
        result = self._translate_text_gemma_result(text)
        return result.text, result.provider

    def _translation_route_cancelled(self):
        active_request = getattr(self, "_active_scan_request", None)
        if active_request is None:
            return False
        return not self._active_scan_is_current()

    def _translate_text_preferred_result(self, text):
        normalized_text = normalize_ocr_text(text)
        if not normalized_text:
            return TranslationResult(text="", provider="")
        if not self.has_ai_text_provider():
            return self._translate_text_google_result(normalized_text)

        requested_provider = self.get_current_ai_provider()
        instance_overrides = getattr(self, "__dict__", {})
        ai_override = instance_overrides.get("translate_text_gemma")
        google_override = instance_overrides.get("translate_text_google")

        def primary():
            if callable(ai_override):
                return TranslationResult(
                    text=ai_override(normalized_text),
                    provider=requested_provider,
                )
            return self._translate_text_gemma_result(normalized_text)

        def fallback():
            if callable(google_override):
                return TranslationResult(
                    text=google_override(normalized_text),
                    provider="google",
                )
            return self._translate_text_google_result(normalized_text)

        orchestrator = TranslationOrchestrator(
            fallback_exceptions=(error.URLError, error.HTTPError, TimeoutError, ValueError)
        )
        return orchestrator.execute(
            requested_provider=requested_provider,
            primary=primary,
            fallback_provider="google",
            fallback=fallback,
            fallback_reason="provider_error",
            cancelled=self._translation_route_cancelled,
        )

    def translate_text_preferred(self, text):
        return self._translate_text_preferred_result(text).text

    def translate_text_preferred_with_provider(self, text):
        result = self._translate_text_preferred_result(text)
        return result.text, result.provider

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
                translated, provider = self.translate_text_gemma_with_provider(combined_source)
                batch_result = self.split_translated_lines(translated, len(normalized_texts))
                if len(batch_result) == len(normalized_texts):
                    return batch_result, provider
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
            try:
                translated = self.translate_multimodal_gemma(image_parts, source_texts)
                parsed = self.parse_segmented_translation_json(translated, len(source_texts))
                if parsed:
                    if self._has_degenerate_multimodal_segments(source_texts, parsed):
                        raise ValueError("degenerate_multimodal_translation")
                    repaired, _providers = self._repair_suspicious_multimodal_segments(source_texts, parsed)
                    return repaired
            except Exception as exc:
                logger.info(
                    f"[Multimodal translation] text fallback: {type(exc).__name__}"
                )
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

    @staticmethod
    def _has_degenerate_multimodal_segments(source_texts, translated_texts):
        if len(translated_texts) < 4 or len(source_texts) != len(translated_texts):
            return False

        normalized_sources = [
            re.sub(r"\s+", "", str(text or ""))
            for text in source_texts
        ]
        if len(set(normalized_sources)) < max(2, len(normalized_sources) // 2):
            return False

        normalized_translations = [
            re.sub(r"\s+", "", str(text or ""))
            for text in translated_texts
        ]
        if not all(normalized_translations):
            return False

        counts = Counter(normalized_translations)
        dominant_translation, dominant_count = counts.most_common(1)[0]
        if (
            dominant_count * 4 < len(normalized_translations) * 3
            or len(counts) > max(2, len(normalized_translations) // 2)
        ):
            return False

        long_source_count = sum(len(source) >= 8 for source in normalized_sources)
        return long_source_count >= max(2, len(normalized_sources) // 2)

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
            try:
                translated = self.translate_multimodal_gemma(image_parts, source_texts)
                parsed = self.parse_segmented_translation_json(
                    translated,
                    len(source_texts),
                )
                if parsed and self._has_degenerate_multimodal_segments(
                    source_texts,
                    parsed,
                ):
                    raise ValueError("degenerate_multimodal_translation")
            except Exception as exc:
                logger.info(
                    f"[Multimodal translation] text fallback: {type(exc).__name__}"
                )
            else:
                if parsed:
                    return self._repair_suspicious_multimodal_segments(
                        source_texts,
                        parsed,
                    )
        if len(source_texts) == 1 and merged_items is not None:
            provider_name = self.get_current_ai_provider() if self.has_ai_text_provider() else "google"
            provider_obj = self._get_translation_provider(provider_name)
            if hasattr(provider_obj, "translate_stream"):
                try:
                    accumulated = ""
                    item = merged_items[0]
                    for chunk in provider_obj.translate_stream(source_texts[0]):
                        if self._abort_stale_scan(ScanStage.TRANSLATION):
                            break
                        accumulated += chunk
                        self._emit_scan_translation_stream_update(
                            0,
                            accumulated,
                            provider_name,
                            int(item['x']),
                            int(item['y']),
                            int(item['w']),
                            int(item['h']),
                        )
                    return [accumulated], [provider_name]
                except Exception as exc:
                    logger.error(f"Streaming translation failed: {type(exc).__name__}")
                    pass

        return self.translate_items_in_batches_with_providers(
            source_texts,
            batch_size=GOOGLE_BATCH_SIZE if not self.has_any_multimodal_ai() else 8,
        )

    def translate_local_manga_crop_batches(self, source_texts, merged_items, batches):
        """Translate local crop batches and map each result back to its source index."""
        translated = [None] * len(source_texts or [])
        providers = [None] * len(source_texts or [])
        written_indexes = set()
        for batch in batches or []:
            try:
                item_indexes = list(batch.get("item_indexes") or [])
                image_parts = batch.get("image_parts")
                if (
                    not item_indexes
                    or len(set(item_indexes)) != len(item_indexes)
                    or not image_parts
                    or any(
                        not isinstance(index, int)
                        or index < 0
                        or index >= len(source_texts)
                        or index >= len(merged_items)
                        for index in item_indexes
                    )
                    or any(index in written_indexes for index in item_indexes)
                ):
                    continue
                batch_texts = [source_texts[index] for index in item_indexes]
                batch_items = [merged_items[index] for index in item_indexes]
                result = self.translate_items_with_ai_and_providers(
                    batch_texts,
                    image_parts,
                    batch_items,
                )
                if not isinstance(result, (list, tuple)) or len(result) != 2:
                    continue
                batch_translated, batch_providers = result
                if (
                    len(batch_translated) != len(item_indexes)
                    or len(batch_providers) != len(item_indexes)
                ):
                    continue
                for index, text, provider in zip(item_indexes, batch_translated, batch_providers):
                    translated[index] = text
                    providers[index] = provider
                written_indexes.update(item_indexes)
            except Exception as exc:
                logger.info(f"[Manga crop translation] region fallback: {type(exc).__name__}")
        return translated, providers

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
        if len(lines) >= 8:
            counts = {line: lines.count(line) for line in set(lines)}
            if max(counts.values(), default=0) >= 4 and (len(counts) / len(lines)) < 0.45:
                return True

        compact = re.sub(r"\s+", "", str(text or ""))
        if len(compact) < 8:
            return False
        character_counts = [compact.count(char) for char in set(compact)]
        if max(character_counts, default=0) >= max(6, int(len(compact) * 0.65)):
            return True
        max_unit = min(32, len(compact) // 4)
        for unit_size in range(1, max_unit + 1):
            if len(compact) % unit_size:
                continue
            repeats = len(compact) // unit_size
            if repeats < 4:
                continue
            unit = compact[:unit_size]
            if unit * repeats == compact:
                return True
        return False

    def should_rescue_manga_ocr(self, img, page_region, items):
        if self.is_unreliable_manga_ocr(items):
            return True
        if not page_region or not items or not self.has_cjk_manga_text(items):
            return False

        try:
            page_area = max(1, int(page_region[2]) * int(page_region[3]))
        except (TypeError, ValueError, IndexError):
            return False

        normalized = []
        for item in items:
            text = normalize_ocr_text(item.get("text", ""))
            try:
                width = int(item.get("w", 0))
                height = int(item.get("h", 0))
            except (TypeError, ValueError):
                continue
            if text and width > 0 and height > 0:
                normalized.append((text, width * height))
        if not normalized:
            return False

        compact_text = "".join(text for text, _area in normalized)
        if self.is_degenerate_manga_transcription("\n".join(text for text, _area in normalized)):
            return True

        def cjk_ratio(value):
            characters = [char for char in value if not char.isspace()]
            if not characters:
                return 0.0
            return sum(bool(re.match(r"[぀-ヿ㐀-䶿一-鿿]", char)) for char in characters) / len(characters)

        if any(len(text) >= 6 and cjk_ratio(text) >= 0.65 for text, _area in normalized):
            return False

        if len(normalized) == 1:
            text, area = normalized[0]
            return (
                len(compact_text) < 8
                and bool(re.search(r"[^\w぀-ヿ㐀-䶿一-鿿]", compact_text))
                and area / page_area <= 0.03
            )

        total_area_ratio = sum(area for _text, area in normalized) / page_area
        tiny_count = sum(
            area / page_area <= MANGA_ADAPTIVE_MIN_AREA_RATIO
            for _text, area in normalized
        )
        return (
            len(normalized) >= 3
            and tiny_count >= (len(normalized) + 1) // 2
            and total_area_ratio <= 0.01
        )

    def rescue_unreliable_manga_items(
        self,
        img,
        page_region,
        items,
        offset_x,
        offset_y,
        image_parts=None,
    ):
        if not self.should_rescue_manga_ocr(img, page_region, items):
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

    def build_local_manga_crop_regions(
        self,
        items,
        img_w,
        img_h,
        offset_x=0,
        offset_y=0,
    ):
        """Group nearby OCR items into at most four bounded local-vision crops."""
        page_area = max(1, int(img_w) * int(img_h))
        candidates = []
        for item in items or []:
            try:
                x = int(item.get("x", 0)) - int(offset_x)
                y = int(item.get("y", 0)) - int(offset_y)
                width = int(item.get("w", 0))
                height = int(item.get("h", 0))
            except (TypeError, ValueError):
                return []
            if width <= 0 or height <= 0:
                return []
            raw = self.clip_region_rect(x, y, width, height, int(img_w), int(img_h))
            if raw is None:
                return []
            raw_ratio = (raw[2] * raw[3]) / page_area
            if raw_ratio > MANGA_ADAPTIVE_MAX_AREA_RATIO:
                return []
            expanded = self.expand_region_rect(
                raw,
                max(10, int(raw[2] * 0.10)),
                max(10, int(raw[3] * 0.10)),
                int(img_w), int(img_h),
            )
            if expanded is None:
                return []
            region = expanded
            if (region[2] * region[3]) / page_area > MANGA_ADAPTIVE_MAX_AREA_RATIO:
                region = raw
            candidates.append(region)

        if not candidates:
            return []

        selected = []
        for region in candidates:
            if any(self.rect_overlap_ratio(region, old) >= 0.75 for old in selected):
                continue
            selected.append(region)

        max_gap = max(24, min(320, max(int(img_w), int(img_h)) * 0.24))
        while len(selected) > MANGA_ADAPTIVE_MAX_REGIONS:
            best = None
            for first_index in range(len(selected)):
                first = selected[first_index]
                for second_index in range(first_index + 1, len(selected)):
                    second = selected[second_index]
                    union = self.union_region_rect(first, second)
                    union_ratio = (union[2] * union[3]) / page_area
                    if union_ratio > MANGA_ADAPTIVE_MAX_AREA_RATIO:
                        continue
                    fx2 = first[0] + first[2]
                    fy2 = first[1] + first[3]
                    sx2 = second[0] + second[2]
                    sy2 = second[1] + second[3]
                    horizontal_gap = max(0, max(second[0] - fx2, first[0] - sx2))
                    vertical_gap = max(0, max(second[1] - fy2, first[1] - sy2))
                    gap = horizontal_gap + vertical_gap
                    if gap > max_gap and self.rect_overlap_ratio(first, second) < 0.18:
                        continue
                    score = (gap, union[2] * union[3])
                    if best is None or score < best[0]:
                        best = (score, first_index, second_index, union)
            if best is None:
                return []
            _score, first_index, second_index, union = best
            selected = [
                region
                for index, region in enumerate(selected)
                if index not in {first_index, second_index}
            ]
            selected.append(union)

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

    def try_manga_grid_recovery(
        self,
        img,
        page_region,
        items,
        threshold,
        orientation_candidates,
        offset_x=0,
        offset_y=0,
    ):
        """Optionally retry sparse manga pages with bounded overlapping tiles."""
        baseline = list(items or [])
        enabled = os.environ.get(MANGA_GRID_RECOVERY_ENV, "").strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return threshold, baseline
        if (
            not page_region
            or not (2 <= len(baseline) <= MANGA_GRID_RECOVERY_MAX_ITEMS)
            or not self.has_cjk_manga_text(baseline)
        ):
            return threshold, baseline

        tile_regions = self.split_region_into_tiles(
            page_region,
            cols=2,
            rows=3,
            overlap=0.10,
        )
        if not tile_regions:
            return threshold, baseline

        try:
            base_threshold = int(threshold)
        except (TypeError, ValueError):
            base_threshold = int(self.binary_threshold)
        retry_thresholds = sorted({
            max(AUTO_THRESHOLD_MIN, min(AUTO_THRESHOLD_MAX, base_threshold + delta))
            for delta in (-10, 0, 10)
        })
        try:
            candidate_threshold, candidate = self.run_ocr_with_best_threshold(
                img,
                offset_x,
                offset_y,
                tile_regions,
                retry_thresholds,
                orientation_candidates,
            )
        except Exception as exc:
            logger.info(f"[Manga grid recovery] fallback: {type(exc).__name__}")
            return threshold, baseline

        candidate = list(candidate or [])
        if len(candidate) < 2 or not self.has_cjk_manga_text(candidate):
            return threshold, baseline
        baseline_score, _ = self.score_ocr_items(baseline)
        candidate_score, _ = self.score_ocr_items(candidate)
        if candidate_score < baseline_score + MANGA_GRID_RECOVERY_SCORE_MARGIN:
            return threshold, baseline
        return candidate_threshold, candidate

    def build_local_manga_crop_batches(
        self,
        img,
        page_region,
        items,
        offset_x=0,
        offset_y=0,
    ):
        """Build region-aware local-vision batches without changing OCR geometry."""
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
        if available is not None and not callable(available) and not available:
            return None

        items = list(items or [])
        img_h, img_w = img.shape[:2]
        regions = self.build_local_manga_crop_regions(
            items,
            img_w,
            img_h,
            offset_x,
            offset_y,
        )
        if not regions:
            return None

        region_indexes = []
        covered_indexes = set()
        for region in regions:
            indexes = [
                index
                for index, item in enumerate(items)
                if index not in covered_indexes
                and self.item_center_in_region(item, region, offset_x, offset_y)
            ]
            if indexes:
                region_indexes.append((region, indexes))
                covered_indexes.update(indexes)
        if len(covered_indexes) != len(items):
            return None

        batches = []
        for region, item_indexes in region_indexes:
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
            if not isinstance(crop_parts, (list, tuple)) or not crop_parts:
                return None
            batches.append(
                {
                    "region": clipped,
                    "item_indexes": list(item_indexes),
                    "image_parts": list(crop_parts),
                }
            )
        return batches or None

    def build_local_manga_crop_context(
        self,
        img,
        page_region,
        items,
        offset_x=0,
        offset_y=0,
    ):
        """Build the legacy flattened local-vision context from region batches."""
        batches = self.build_local_manga_crop_batches(
            img,
            page_region,
            items,
            offset_x,
            offset_y,
        )
        if not batches:
            return None
        parts = []
        for batch in batches:
            parts.extend(batch.get("image_parts") or [])
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

    def get_ocr_scale_factor(self, width, height):
        scale_factor = 3.0
        max_side = max(int(width), int(height))
        if self.scan_mode == SCAN_MODE_REGION:
            max_dim = 1000
            min_scale = 1.5
        elif max_side > FULLSCREEN_OCR_DOWNSCALE_TRIGGER:
            max_dim = FULLSCREEN_OCR_MAX_DIM
            min_scale = FULLSCREEN_OCR_MIN_SCALE
        else:
            return scale_factor

        scaled_width = width * scale_factor
        scaled_height = height * scale_factor
        if max(scaled_width, scaled_height) <= max_dim:
            return scale_factor
        return max(
            min_scale,
            min(max_dim / max(1, width), max_dim / max(1, height)),
        )

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
                    scale_factor = self.get_ocr_scale_factor(rot_w, rot_h)
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
                        wait=(deadline is None or getattr(self, "drain_deadline_futures", False)),
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
                if not silent: self._emit_scan_status("🔎 局部微調閥值中...")
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
                if not silent: self._emit_scan_status("🧠 句子完整度複判中...")
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
            logger.info(
                "[Japanese rescue] outcome=%s first_similarity=%.3f second_similarity=%.3f",
                "adopted" if decision.adopted else "rejected",
                decision.first_similarity,
                decision.second_similarity,
            )
            return decision.selected_text
        except Exception as exc:
            logger.warning(f"[Japanese rescue] fallback to baseline: {type(exc).__name__}: {exc}")
            return first_text

    def run_scan_once(self):
        self._reset_scan_trace()
        self._active_scan_request = self._take_scan_request()
        if self._abort_stale_scan(ScanStage.FRAME_CACHE):
            return
        is_screenshot_mode = self.scan_mode == SCAN_MODE_REGION and self.region_render_mode == REGION_RENDER_SCREENSHOT
        is_relief_mode = self.scan_mode == SCAN_MODE_REGION and self.region_render_mode == REGION_RENDER_RELIEF
        is_region_vision_mode = (
            self.scan_mode == SCAN_MODE_REGION
            and self.region_render_mode in (REGION_RENDER_BUBBLE, REGION_RENDER_RELIEF)
            and self.has_any_multimodal_ai()
        )
        _t0 = time.perf_counter()
        def _log(label):
            if is_relief_mode:
                elapsed = (time.perf_counter() - _t0) * 1000
                logger.info(f"[浮雕計時] {label}: +{elapsed:.1f}ms (累計)")
        ai_image_parts = None
        region_vision_failed = False
        ocr_trace_recorded = False
        if not is_screenshot_mode and not is_region_vision_mode and not self.ocr_backends:
            self._record_scan_event(
                ScanStage.OCR,
                ScanOutcome.FAILURE,
                error_code=ScanErrorCode.OCR_FAILED,
                detail="ocr_backend_unavailable",
            )
            self._emit_scan_status("❌ 缺少可用 OCR 後端")
            self._emit_scan_finished([])
            self.show_ui.emit()
            return

        self.hide_ui.emit()
        _log("開始 - hide_ui")
        # 挑戰肉眼極限：只等 30 毫秒（約 2 個畫面影格）
        time.sleep(0.03)
        capture_started = time.perf_counter()
        try:
            img, offset_x, offset_y = self.capture_scan_area()
            self.last_scanned_img = img.copy()
            self.last_scanned_offset = (offset_x, offset_y)
            self._record_scan_event(
                ScanStage.CAPTURE,
                ScanOutcome.SUCCESS,
                started_at=capture_started,
                detail="capture_completed",
            )
            _log("① 截圖完成")
        except Exception as exc:
            self._record_scan_event(
                ScanStage.CAPTURE,
                ScanOutcome.FAILURE,
                started_at=capture_started,
                error_code=ScanErrorCode.CAPTURE_FAILED,
                detail="capture_failed",
                exception=exc,
            )
            self._emit_scan_status(f"\u274c 擷取螢幕失敗：{type(exc).__name__}")
            self._emit_scan_finished([])
            return
        finally:
            # 截完圖立刻讓舊字幕回來，達成無縫翻譯效果
            self.show_ui.emit()

        if self._abort_stale_scan(ScanStage.CAPTURE):
            return
        exact_context = self._exact_image_cache_context(offset_x, offset_y)
        shadow_detail, sampled_pixels, shadow_started = self._observe_frame_gate(
            img, exact_context
        )
        cached_image_result = self.exact_image_cache.get(img, exact_context)
        if cached_image_result is not None:
            selected_provider = self._current_cache_provider()
            is_upgrade_needed = (
                self.get_translation_provider_priority(selected_provider)
                > self.get_translation_provider_priority(cached_image_result.provider)
            )
            if not is_upgrade_needed:
                cached_results = list(cached_image_result.results)
                if self._abort_stale_scan(ScanStage.FRAME_CACHE):
                    return
                self._record_scan_event(
                    ScanStage.FRAME_CACHE,
                    ScanOutcome.HIT,
                    detail="frame_cache_hit",
                    provider=cached_image_result.provider,
                    item_count=len(cached_results),
                )
                self.last_combined_text = cached_image_result.state_token
                self.last_provider = cached_image_result.provider
                self.last_results = cached_results
                self._emit_scan_status("♻️ 完全相同畫面（快取）")
                if not is_screenshot_mode:
                    self.trigger_background_threshold_refresh(img, offset_x, offset_y, self.scan_mode)
                self._emit_scan_finished(cached_results)
                return
            self._record_scan_event(
                ScanStage.FRAME_CACHE,
                ScanOutcome.MISS,
                started_at=shadow_started,
                detail=shadow_detail,
                provider=cached_image_result.provider,
                fallback_reason="cache_provider_upgrade",
                item_count=sampled_pixels,
            )
        else:
            self._record_scan_event(
                ScanStage.FRAME_CACHE,
                ScanOutcome.MISS,
                started_at=shadow_started,
                detail=shadow_detail,
                item_count=sampled_pixels,
            )

        # 截圖後立刻預取 Google OCR（與本地 OCR 並列進行）
        # 注意：多模態 AI 翻譯已包含看圖能力，可代替 Google OCR refine，故不重複呼叫
        _google_ocr_future = None
        _google_executor = None
        _google_executor_shutdown = False

        def _shutdown_google_ocr_executor(wait=False):
            nonlocal _google_executor, _google_executor_shutdown
            if _google_executor is None or _google_executor_shutdown:
                return
            executor = _google_executor
            _google_executor = None
            _google_executor_shutdown = True
            try:
                executor.shutdown(wait=wait)
            except Exception:
                pass

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
                    _google_ocr_future.add_done_callback(
                        lambda _completed: _shutdown_google_ocr_executor(wait=False)
                    )
                    _log("① 截圖完成 (Google OCR 預取已啟動)")
            except Exception:
                _shutdown_google_ocr_executor(wait=False)
                _google_ocr_future = None

        if is_screenshot_mode:
            translation_started = time.perf_counter()
            requested_screenshot_provider = self._canonical_cache_provider(
                self.get_current_ai_provider()
                if self.has_any_multimodal_ai() or self.has_ai_text_provider()
                else "google"
            )
            screenshot_text_hint = self.build_screenshot_text_hint(img)
            if self.has_any_multimodal_ai():
                screenshot_text_hint = self.rescue_japanese_text(
                    img,
                    screenshot_text_hint,
                    ai_image_parts,
                )
            if not self.has_any_multimodal_ai():
                if not screenshot_text_hint:
                    self._record_scan_event(
                        ScanStage.TRANSLATION,
                        ScanOutcome.FAILURE,
                        started_at=translation_started,
                        error_code=ScanErrorCode.TRANSLATION_FAILED,
                        detail="translation_input_unavailable",
                    )
                    self._emit_scan_status("❌ 截圖模式需要 Gemma AI 與 Google API KEY")
                    self._emit_scan_finished([])
                    self.show_ui.emit()
                    return
                self._emit_scan_status("🖼 截圖模式改走文字翻譯...")
                try:
                    translated_text, current_provider = self.translate_text_preferred_with_provider(screenshot_text_hint)
                except Exception as exc:
                    self._record_scan_event(
                        ScanStage.TRANSLATION,
                        ScanOutcome.FAILURE,
                        started_at=translation_started,
                        error_code=ScanErrorCode.TRANSLATION_FAILED,
                        detail="translation_failed",
                        exception=exc,
                    )
                    self._emit_scan_status(f"❌ 截圖翻譯失敗：{type(exc).__name__}")
                    self._emit_scan_finished([])
                    self.show_ui.emit()
                    return
            else:
                ai_image_parts = self.build_ai_image_parts(img)
                self._emit_scan_status("🖼 截圖模式翻譯中...")
                try:
                    translated_text = self.translate_screenshot_gemma(ai_image_parts, screenshot_text_hint).strip()
                    current_provider = (
                        getattr(self, "_last_screenshot_translation_provider", "")
                        or self.get_current_ai_provider()
                    )
                except Exception as exc:
                    self.log_ai_debug(f"MULTIMODAL FAILED: {type(exc).__name__}")
                    if screenshot_text_hint:
                        self._emit_scan_status("🖼 截圖模式失敗，改走文字翻譯...")
                        try:
                            translated_text, current_provider = self.translate_text_preferred_with_provider(screenshot_text_hint)
                        except Exception as fallback_exc:
                            self._record_scan_event(
                                ScanStage.TRANSLATION,
                                ScanOutcome.FAILURE,
                                started_at=translation_started,
                                error_code=ScanErrorCode.TRANSLATION_FAILED,
                                detail="translation_fallback_failed",
                                exception=fallback_exc,
                            )
                            self._emit_scan_status(f"❌ 截圖翻譯失敗：{type(exc).__name__}")
                            self._emit_scan_finished([])
                            self.show_ui.emit()
                            return
                    else:
                        self._record_scan_event(
                            ScanStage.TRANSLATION,
                            ScanOutcome.FAILURE,
                            started_at=translation_started,
                            error_code=ScanErrorCode.TRANSLATION_FAILED,
                            detail="translation_failed",
                            exception=exc,
                        )
                        self._emit_scan_status(f"❌ 截圖翻譯失敗：{type(exc).__name__}")
                        self._emit_scan_finished([])
                        self.show_ui.emit()
                        return

            if self._abort_stale_scan(ScanStage.TRANSLATION):
                return
            if not translated_text:
                self._record_scan_event(
                    ScanStage.TRANSLATION,
                    ScanOutcome.NO_TEXT,
                    started_at=translation_started,
                    detail="translation_empty",
                )
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
            screenshot_result = getattr(self, "_last_screenshot_translation_result", None)
            route_fallback_reason = (
                getattr(screenshot_result, "fallback_reason", None) or ""
            )
            route_requested_provider = self._canonical_cache_provider(
                getattr(screenshot_result, "requested_provider", None)
                or requested_screenshot_provider
            )
            screenshot_outcome = (
                ScanOutcome.FALLBACK
                if route_fallback_reason
                or (
                    route_requested_provider
                    and current_provider != route_requested_provider
                )
                else ScanOutcome.SUCCESS
            )
            self._record_scan_event(
                ScanStage.TRANSLATION,
                screenshot_outcome,
                started_at=translation_started,
                detail="translation_completed",
                provider=current_provider,
                fallback_reason=(
                    "translation_provider_fallback"
                    if screenshot_outcome is ScanOutcome.FALLBACK
                    else ""
                ),
                item_count=len(final_results),
            )
            self._emit_scan_status("✅ 截圖翻譯完成")
            self._emit_scan_finished(final_results)
            self.show_ui.emit()
            return

        ocr_regions = None
        ocr_orientations = [0]
        page_region = None
        if self.scan_mode == SCAN_MODE_FULLSCREEN:
            self._emit_scan_status("🧭 智慧裁切分析中...")
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
        
        self._emit_scan_status("🔍 掃描與翻譯中...")
        _log("② 開始 OCR")

        ocr_started = time.perf_counter()
        if not self.ocr_backends and is_region_vision_mode:
            used_threshold, filtered_items = 0, []
        else:
            try:
                used_threshold, filtered_items = self.run_ocr_with_best_threshold(img, offset_x, offset_y, ocr_regions, None, ocr_orientations)
                _log(f"③ OCR 完成 (找到 {len(filtered_items)} 段)")
                if self._abort_stale_scan(ScanStage.OCR):
                    return
            except Exception as exc:
                self._record_scan_event(
                    ScanStage.OCR,
                    ScanOutcome.FAILURE,
                    started_at=ocr_started,
                    error_code=ScanErrorCode.OCR_FAILED,
                    detail="ocr_optional_failed" if is_region_vision_mode else "ocr_failed",
                    exception=exc,
                )
                if is_region_vision_mode:
                    used_threshold, filtered_items = 0, []
                else:
                    self._emit_scan_status("❌ 辨識錯誤")
                    self._emit_scan_finished([])
                    self.show_ui.emit()
                    return

        if (
            self.scan_mode == SCAN_MODE_FULLSCREEN
            and ocr_regions
            and len(ocr_regions) > 1
            and len(filtered_items) <= 1
        ):
            self._emit_scan_status("🧭 智慧裁切結果太少，改用全畫面重試...")
            try:
                used_threshold, filtered_items = self.run_ocr_with_best_threshold(
                    img,
                    offset_x,
                    offset_y,
                    [(0, 0, img.shape[1], img.shape[0])],
                )
            except Exception:
                filtered_items = []

        if self._abort_stale_scan(ScanStage.OCR):
            return

        if not filtered_items:
            if self.scan_mode == SCAN_MODE_REGION and not is_region_vision_mode:
                self._emit_scan_status("框選區域沒有掃到字，正在改用旋轉重試...")
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
            if (
                not filtered_items
                and self.scan_mode == SCAN_MODE_REGION
                and not is_region_vision_mode
            ):
                self._emit_scan_status("框選區域沒有掃到文字，請框大一點或換個角度。")

        if self._abort_stale_scan(ScanStage.OCR):
            return

        if is_region_vision_mode:
            self._record_scan_event(
                ScanStage.OCR,
                ScanOutcome.SUCCESS if filtered_items else ScanOutcome.NO_TEXT,
                started_at=ocr_started,
                detail=(
                    "ocr_optional_geometry"
                    if filtered_items
                    else "ocr_optional_unavailable"
                ),
                item_count=len(filtered_items),
            )
            ocr_trace_recorded = True
            vision_started = time.perf_counter()
            vision_hints = [
                {
                    "id": region_id,
                    "x": int(item["x"]) - int(offset_x),
                    "y": int(item["y"]) - int(offset_y),
                    "w": int(item["w"]),
                    "h": int(item["h"]),
                    "text": str(item.get("text") or ""),
                }
                for region_id, item in enumerate(filtered_items)
            ]
            if not vision_hints:
                vision_hints = [
                    {
                        "id": 0,
                        "x": 0,
                        "y": 0,
                        "w": int(img.shape[1]),
                        "h": int(img.shape[0]),
                        "text": "",
                    }
                ]

            provider_name = self.resolve_multimodal_provider_name()
            if self._abort_stale_scan(ScanStage.TRANSLATION):
                return
            provider = self._get_translation_provider(provider_name) if provider_name else None
            try:
                if provider is None or not hasattr(provider, "interpret_regions"):
                    raise ValueError("region_vision_unavailable")
                if provider_name == "local_multimodal":
                    ai_image_parts = self.build_local_vision_image_parts(img, vision_hints)
                else:
                    ai_image_parts = self.build_ai_image_parts(img)
                interpret_kwargs = {
                    "image_width": int(img.shape[1]),
                    "image_height": int(img.shape[0]),
                    "target_lang": self.translation_target_lang,
                }
                if isinstance(provider, LocalMultimodalProvider):
                    interpret_kwargs["cancel_predicate"] = lambda: not self._active_scan_is_current()
                try:
                    vision_results = provider.interpret_regions(
                        ai_image_parts,
                        vision_hints,
                        **interpret_kwargs,
                    )
                finally:
                    self._capture_local_vision_request_metrics(provider)
                self.sync_gemma_call_timestamps_from_provider(provider)
                if self._abort_stale_scan(ScanStage.TRANSLATION):
                    return
                by_id = {result.id: result for result in vision_results}
                expected_ids = {hint["id"] for hint in vision_hints}
                if set(by_id) != expected_ids:
                    raise ValueError("incomplete_region_vision_response")
                final_results, source_texts = [], []
                current_provider = self._canonical_cache_provider(provider_name)
                for hint in vision_hints:
                    result = by_id.get(hint["id"])
                    if result is None:
                        continue
                    source_text = result.source_text.strip()
                    translated_text = result.translation.strip()
                    if not source_text or not translated_text:
                        continue
                    output_rect = (
                        int(hint["x"] + offset_x),
                        int(hint["y"] + offset_y),
                        int(hint["w"]),
                        int(hint["h"]),
                    )
                    cache_key = (
                        self.detect_source_language(source_text),
                        normalize_ocr_text(source_text),
                    )
                    self.remember_translation(cache_key, translated_text)
                    self.remember_preferred_text(source_text, translated_text, current_provider)
                    self.remember_hud_observation(source_text, output_rect, translated_text, current_provider)
                    source_texts.append(source_text)
                    final_results.append((translated_text, *output_rect))
                if not final_results:
                    raise ValueError("empty_region_vision_response")
            except LocalRequestCancelled:
                if self._abort_stale_scan(ScanStage.TRANSLATION):
                    return
                raise
            except Exception as exc:
                region_vision_failed = True
                self._record_scan_event(
                    ScanStage.TRANSLATION,
                    ScanOutcome.FAILURE,
                    started_at=vision_started,
                    error_code=ScanErrorCode.TRANSLATION_FAILED,
                    detail="translation_region_vision_failed",
                    fallback_reason=(
                        "translation_region_vision_"
                        + classify_region_vision_failure(exc)
                    ),
                    exception=exc,
                )
                if not filtered_items:
                    self.last_results = []
                    self._emit_scan_status("⚠️ 區域 Vision 翻譯失敗")
                    self._emit_scan_finished([])
                    self.show_ui.emit()
                    return
            else:
                current_combined_text = "\n".join(source_texts)
                self.last_combined_text = current_combined_text
                self.last_provider = current_provider
                self.last_results = final_results
                self.exact_image_cache.put(
                    img,
                    self._exact_image_cache_context(offset_x, offset_y),
                    final_results,
                    current_provider,
                    current_combined_text,
                )
                self._record_scan_event(
                    ScanStage.TRANSLATION,
                    ScanOutcome.SUCCESS,
                    started_at=vision_started,
                    detail="translation_region_vision_completed",
                    provider=current_provider,
                    item_count=len(final_results),
                )
                self._emit_scan_status("✅ 區域 Vision 翻譯完成")
                self.trigger_background_threshold_refresh(img, offset_x, offset_y, self.scan_mode)
                self._emit_scan_finished(final_results)
                return

        manga_tile_retry_used = False
        if self.scan_mode == SCAN_MODE_FULLSCREEN and len(filtered_items) <= 1 and page_region:
            tile_regions = self.split_region_into_tiles(page_region, cols=2, rows=3, overlap=0.10)
            if tile_regions:
                manga_tile_retry_used = True
                self._emit_scan_status("📚 漫畫頁切片重試中...")
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

        if (not manga_tile_retry_used and self.scan_mode == SCAN_MODE_FULLSCREEN and page_region):
            used_threshold, filtered_items = self.try_manga_grid_recovery(
                img,
                page_region,
                filtered_items,
                used_threshold,
                ocr_orientations,
                offset_x,
                offset_y,
            )
        if self._abort_stale_scan(ScanStage.OCR):
            return
        if (
            self.scan_mode == SCAN_MODE_FULLSCREEN
            and page_region
            and len(filtered_items) >= 2
            and self.has_cjk_manga_text(filtered_items)
        ):
            self._emit_scan_status("📖 漫畫文字精修中...")
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

        if self._abort_stale_scan(ScanStage.OCR):
            return

        if (
            self.scan_mode == SCAN_MODE_FULLSCREEN
            and page_region
            and (
                detected_page_region is not None
                or self.has_cjk_manga_text(filtered_items)
            )
            and self.has_any_multimodal_ai()
            and self.should_rescue_manga_ocr(img, page_region, filtered_items)
        ):
            self._emit_scan_status("📖 漫畫文字辨識補救中...")
            filtered_items, ai_image_parts = self.rescue_unreliable_manga_items(
                img,
                page_region,
                filtered_items,
                offset_x,
                offset_y,
                ai_image_parts,
            )

        if self._abort_stale_scan(ScanStage.OCR):
            return

        if not filtered_items:
            self._record_scan_event(
                ScanStage.OCR,
                ScanOutcome.NO_TEXT,
                started_at=ocr_started,
                detail="no_text",
            )
            self.handle_empty()
            return

        if not ocr_trace_recorded:
            self._record_scan_event(
                ScanStage.OCR,
                ScanOutcome.SUCCESS,
                started_at=ocr_started,
                detail="ocr_completed",
                item_count=len(filtered_items),
            )
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
            self._emit_scan_status(f"✨ 已選最佳閥值 {used_threshold}")
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

        if self._abort_stale_scan(ScanStage.OCR):
            return

        translation_started = time.perf_counter()
        try:
            self._emit_scan_status("🧠 AI 大圖翻譯..." if self.has_any_multimodal_ai() else "🌐 Google...")
            if _use_google_ocr_refine:
                if _google_ocr_future is not None:
                    _log("⑤ 等待 Google OCR 預取結果...")
                    try:
                        _google_result = _google_ocr_future.result(timeout=30)
                        _log("⑥ Google OCR 精煉完成 (已預取)")
                        if _google_result is not None:
                            _google_lines = [normalize_ocr_text(line) for line in str(_google_result.text or "").splitlines() if normalize_ocr_text(line)]
                            merged_items = merge_google_lines_into_items(_google_lines, merged_items)
                    except FutureTimeoutError:
                        _google_ocr_future.cancel()
                    except Exception:
                        pass
                    finally:
                        _shutdown_google_ocr_executor(wait=False)
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
            used_local_crop_batches = False
            try:
                if ai_image_parts is None and self.scan_mode == SCAN_MODE_FULLSCREEN:
                    try:
                        crop_batches = self.build_local_manga_crop_batches(
                            img,
                            page_region,
                            merged_items,
                            offset_x,
                            offset_y,
                        )
                    except Exception as exc:
                        crop_batches = None
                        logger.info(
                            f"[Manga crop context] full-page fallback: "
                            f"{type(exc).__name__}"
                        )
                    if crop_batches:
                        try:
                            translated_list, provider_list = self.translate_local_manga_crop_batches(
                                source_texts,
                                merged_items,
                                crop_batches,
                            )
                            used_local_crop_batches = any(
                                bool(text) for text in translated_list
                            )
                            _log(
                                f"⑦-pre 漫畫局部多模態 batches 完成 "
                                f"({len(crop_batches)} regions)"
                            )
                        except Exception as exc:
                            logger.info(
                                f"[Manga crop translation] full-page fallback: "
                                f"{type(exc).__name__}"
                            )
                if not used_local_crop_batches:
                    if ai_image_parts is None and self.has_any_multimodal_ai():
                        _log("⑦-pre 開始 build_ai_image_parts (多模態翻譯)")
                        ai_image_parts = self.build_ai_image_parts(img)
                        _log("⑦ build_ai_image_parts 完成")
                    _log("⑧ 開始 translate_items_with_ai_and_providers")
                    translated_list, provider_list = self.translate_items_with_ai_and_providers(source_texts, ai_image_parts, merged_items)
                _log(f"⑨ 翻譯完成 (共 {len(translated_list)} 段)")
            except Exception as exc:
                self.log_ai_debug(f"MULTIMODAL BATCH FAILED: {type(exc).__name__}")
                translated_list = []
                provider_list = []

            if self._abort_stale_scan(ScanStage.TRANSLATION):
                return
            if len(translated_list) != len(merged_items):
                translated_list = [None] * len(merged_items)
            if len(provider_list) != len(merged_items):
                provider_list = [None] * len(merged_items)

            missing_indexes = [index for index, text in enumerate(translated_list) if not text]
            if missing_indexes:
                prefix = "AI" if self.has_any_multimodal_ai() else "Google"
                icon = "🧠" if prefix == "AI" else "🌐"
                self._emit_scan_status(f"{icon} {prefix} 批次補翻 {len(missing_indexes)} 段...")
                batch_source = [source_texts[index] for index in missing_indexes]
                batch_result, batch_providers = self.translate_items_in_batches_with_providers(batch_source, batch_size=8)
                for offset, translated in enumerate(batch_result):
                    if translated:
                        translated_list[missing_indexes[offset]] = translated
                        provider_list[missing_indexes[offset]] = batch_providers[offset]

            for i, item in enumerate(merged_items):
                if self._abort_stale_scan(ScanStage.TRANSLATION):
                    return
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
                    self._emit_scan_status(f"{icon} {prefix} {i+1}/{len(merged_items)}")
                    try:
                        trans_text, provider = self.translate_text_preferred_with_provider(source_text)
                    except Exception:
                        trans_text = source_text
                        provider = ""

                if self._abort_stale_scan(ScanStage.TRANSLATION):
                    return
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
            trace_providers = [provider for provider in final_providers if provider]
            unique_trace_providers = list(dict.fromkeys(trace_providers))
            trace_provider = (
                unique_trace_providers[0]
                if len(unique_trace_providers) == 1
                else "mixed" if unique_trace_providers else ""
            )
            requested_provider = self._canonical_cache_provider(current_provider)
            if len(trace_providers) != len(final_results):
                trace_outcome = ScanOutcome.FALLBACK
                trace_reason = "translation_source_fallback"
            elif requested_provider and any(
                provider != requested_provider for provider in trace_providers
            ):
                trace_outcome = ScanOutcome.FALLBACK
                trace_reason = "translation_provider_fallback"
            elif region_vision_failed:
                trace_outcome = ScanOutcome.FALLBACK
                trace_reason = "translation_region_vision_failed"
            else:
                trace_outcome = ScanOutcome.SUCCESS
                trace_reason = ""
            self._record_scan_event(
                ScanStage.TRANSLATION,
                trace_outcome,
                started_at=translation_started,
                detail="translation_completed",
                provider=trace_provider,
                fallback_reason=trace_reason,
                item_count=len(final_results),
            )
            _log(f"⑩ 全部完成！共 {len(final_results)} 筆結果")
            self._emit_scan_status("✅ 翻譯完成")
            self.trigger_background_threshold_refresh(img, offset_x, offset_y, self.scan_mode)
            self._emit_scan_finished(final_results)

        except Exception as e:
            self._record_scan_event(
                ScanStage.TRANSLATION,
                ScanOutcome.FAILURE,
                started_at=translation_started,
                error_code=ScanErrorCode.TRANSLATION_FAILED,
                detail="translation_failed",
                exception=e,
            )
            logger.error(f"Error: {e}")
            self._emit_scan_status("⚠️ 翻譯失敗")
            fallback = [(item['text'], item['x'], item['y'], item['w'], item['h']) for item in merged_items]
            self.last_results = fallback
            self._emit_scan_finished(fallback)

    def handle_empty(self, message="💤 畫面無文字"):
        if self.last_combined_text != "":
            self._emit_scan_status(message)
            self.last_combined_text = ""
            self.last_results = []
        self._emit_scan_finished([])
        self.show_ui.emit()
