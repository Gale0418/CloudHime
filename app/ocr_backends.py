from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class OCRBox:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class OCRWord:
    text: str
    box: OCRBox
    confidence: float | None = None


@dataclass(frozen=True)
class OCRLine:
    text: str
    box: OCRBox
    confidence: float | None = None
    words: Tuple[OCRWord, ...] = ()


@dataclass(frozen=True)
class OCRResult:
    backend_name: str
    lines: Tuple[OCRLine, ...] = ()
    error: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.lines


class OCRBackend:
    name = "unknown"

    def available(self) -> bool:
        return False

    def recognize(self, image: np.ndarray) -> OCRResult:
        raise NotImplementedError


class OCRBackendFailure(RuntimeError):
    """A bounded signal that all configured OCR attempts failed."""

    def __init__(self, detail: str, *, error_code: str = "ocr_backend_failed"):
        self.detail = str(detail or "ocr_backend_initialization_failed")[:192]
        self.error_code = str(error_code or "ocr_backend_failed")[:64]
        super().__init__(self.error_code)


def _to_int_box(x: float, y: float, w: float, h: float) -> OCRBox:
    return OCRBox(int(x), int(y), max(1, int(w)), max(1, int(h)))


def _box_from_points(points: Sequence[Sequence[float]]) -> OCRBox:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    return _to_int_box(x1, y1, x2 - x1, y2 - y1)


def _ensure_bgr(image: np.ndarray) -> np.ndarray:
    if image is None:
        return image
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image


class WindowsOCRBackend(OCRBackend):
    name = "windows"

    def __init__(self):
        self._available = False
        self._engine = None
        self._init_error = ""
        self._language = None
        self._mode = "winrt"
        self._recognize_lock = threading.Lock()
        try:
            try:
                from winsdk.windows.media.ocr import OcrEngine  # type: ignore
                from winsdk.windows.globalization import Language  # type: ignore
                from winsdk.windows.graphics.imaging import BitmapDecoder  # type: ignore
                from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter  # type: ignore
            except Exception:
                # Async completion and OCR line collections load these lazily.
                # Check them before advertising OCR as ready to avoid a hung await.
                import winrt.windows.foundation  # type: ignore  # noqa: F401
                import winrt.windows.foundation.collections  # type: ignore  # noqa: F401
                from winrt.windows.media.ocr import OcrEngine  # type: ignore
                from winrt.windows.globalization import Language  # type: ignore
                from winrt.windows.graphics.imaging import BitmapDecoder  # type: ignore
                from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter  # type: ignore

            self._OcrEngine = OcrEngine
            self._Language = Language
            self._BitmapDecoder = BitmapDecoder
            self._InMemoryRandomAccessStream = InMemoryRandomAccessStream
            self._DataWriter = DataWriter
            self._available = True
        except Exception:
            self._available = False

    def available(self) -> bool:
        return self._available

    def _run_coroutine_sync(self, coroutine):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)

        result: dict[str, object] = {}
        error: dict[str, BaseException] = {}

        def runner():
            try:
                result["value"] = asyncio.run(coroutine)
            except BaseException as exc:
                error["exc"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if error:
            raise error["exc"]
        return result.get("value")

    def _init_engine(self):
        if self._engine is not None:
            return self._engine
        if not self._available:
            return None
        last_error = ""

        def try_create(language):
            nonlocal last_error
            try:
                self._engine = self._OcrEngine.try_create_from_language(language)
            except Exception as exc:
                last_error = self._bounded_exception_detail(exc)
            return self._engine

        try:
            preferred_language = self._Language("ja-JP")
            if self._OcrEngine.is_language_supported(preferred_language):
                if try_create(preferred_language) is not None:
                    return self._engine
        except Exception as exc:
            last_error = self._bounded_exception_detail(exc)

        try:
            self._engine = self._OcrEngine.try_create_from_user_profile_languages()
        except Exception as exc:
            self._engine = None
            last_error = self._bounded_exception_detail(exc)
        if self._engine is not None:
            return self._engine

        try:
            available_languages = self._OcrEngine.available_recognizer_languages
            for available_language in available_languages:
                language_tag = str(getattr(available_language, "language_tag", "") or "").strip()
                if not language_tag or language_tag.casefold() == "ja-jp":
                    continue
                try:
                    language = self._Language(language_tag)
                except Exception as exc:
                    last_error = self._bounded_exception_detail(exc)
                    continue
                if try_create(language) is not None:
                    return self._engine
        except Exception as exc:
            last_error = self._bounded_exception_detail(exc)

        if last_error:
            self._init_error = f"windows_ocr_engine_init_failed: {last_error}"[:192]
        else:
            self._init_error = "windows_ocr_engine_unavailable"
        return self._engine

    @staticmethod
    def _bounded_exception_detail(exc: BaseException) -> str:
        try:
            message = " ".join(str(exc).split())
        except Exception:
            message = ""
        detail = f"{type(exc).__name__}: {message}" if message else type(exc).__name__
        return detail[:160]

    async def _recognize_async(self, image: np.ndarray):
        engine = self._init_engine()
        if engine is None:
            return OCRResult(
                self.name,
                (),
                error=self._init_error or "windows_ocr_engine_unavailable",
            )
        image = _ensure_bgr(image)
        success, encoded = cv2.imencode(".png", image)
        if not success:
            return None
        stream = self._InMemoryRandomAccessStream()
        writer = self._DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(encoded.tobytes())
        await writer.store_async()
        await writer.flush_async()
        decoder = await self._BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        return await engine.recognize_async(bitmap)

    def recognize(self, image: np.ndarray) -> OCRResult:
        with self._recognize_lock:
            return self._recognize_once(image)

    def _recognize_once(self, image: np.ndarray) -> OCRResult:
        try:
            ocr_result = self._run_coroutine_sync(self._recognize_async(image))
        except Exception as exc:
            return OCRResult(
                self.name,
                (),
                error=f"windows_ocr_recognition_failed: {self._bounded_exception_detail(exc)}"[:192],
            )
        if isinstance(ocr_result, OCRResult):
            return ocr_result
        if not ocr_result:
            return OCRResult(self.name, ())
        lines: list[OCRLine] = []
        for line in getattr(ocr_result, "lines", []):
            line_text = str(getattr(line, "text", "") or "").strip()
            if not line_text:
                continue
            words: list[OCRWord] = []
            line_box = None
            for word in getattr(line, "words", []):
                rect = getattr(word, "bounding_rect", None)
                if rect is None:
                    continue
                word_box = _to_int_box(rect.x, rect.y, rect.width, rect.height)
                if line_box is None:
                    line_box = word_box
                else:
                    x1 = min(line_box.x, word_box.x)
                    y1 = min(line_box.y, word_box.y)
                    x2 = max(line_box.x + line_box.w, word_box.x + word_box.w)
                    y2 = max(line_box.y + line_box.h, word_box.y + word_box.h)
                    line_box = _to_int_box(x1, y1, x2 - x1, y2 - y1)
                words.append(OCRWord(str(getattr(word, "text", "") or "").strip(), word_box, None))
            if line_box is None:
                rect = getattr(line, "bounding_rect", None)
                if rect is not None:
                    line_box = _to_int_box(rect.x, rect.y, rect.width, rect.height)
                else:
                    line_box = OCRBox(0, 0, 1, 1)
            lines.append(OCRLine(line_text, line_box, None, tuple(words)))
        return OCRResult(self.name, tuple(lines))


class TesseractBackend(OCRBackend):
    name = "tesseract"

    def __init__(self):
        self._available = False
        self._pytesseract = None
        self._output_type = None
        self._version_probe_lock = threading.Lock()
        self._version_probe_complete = False
        self._version_available = False
        try:
            import pytesseract  # type: ignore
            from pytesseract import Output  # type: ignore

            self._pytesseract = pytesseract
            self._output_type = Output
            self._available = True
        except Exception:
            self._available = False

    def available(self) -> bool:
        if not self._available:
            return False
        with self._version_probe_lock:
            if self._version_probe_complete:
                return self._version_available
            try:
                _ = self._pytesseract.get_tesseract_version()
                self._version_available = True
            except Exception:
                self._version_available = False
            self._version_probe_complete = True
            return self._version_available

    def recognize(self, image: np.ndarray) -> OCRResult:
        if not self.available():
            return OCRResult(self.name, ())
        image = _ensure_bgr(image)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        try:
            data = self._pytesseract.image_to_data(rgb, output_type=self._output_type.DICT, lang="chi_tra+jpn+eng")
        except Exception as exc:
            return OCRResult(self.name, (), error=str(exc))
        lines: list[OCRLine] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = str(data["text"][i]).strip()
            if not text:
                continue
            conf_raw = data.get("conf", ["-1"])[i]
            try:
                confidence = float(conf_raw)
            except Exception:
                confidence = None
            x = int(data["left"][i])
            y = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])
            box = OCRBox(x, y, max(1, w), max(1, h))
            lines.append(OCRLine(text, box, confidence, (OCRWord(text, box, confidence),)))
        return OCRResult(self.name, tuple(lines))


class EasyOCRBackend(OCRBackend):
    name = "easyocr"

    def __init__(self):
        self._available = False
        self._reader = None
        self._gpu_enabled = False
        self._import_error = None
        self._init_error = None
        try:
            import easyocr  # type: ignore

            self._easyocr = easyocr
            self._available = True
        except Exception as exc:
            self._import_error = exc
            print(f"[OCR] EasyOCR unavailable: {exc}")
            self._available = False

    def available(self) -> bool:
        return self._available

    def _can_use_gpu(self) -> bool:
        try:
            import importlib
            torch = importlib.import_module("torch")
            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _get_reader(self):
        if self._reader is not None:
            return self._reader
        if not self._available:
            return None
        gpu_enabled = self._can_use_gpu()
        self._gpu_enabled = gpu_enabled
        last_error = None
        for langs in (["ch_tra", "en"], ["ja", "en"], ["ch_sim", "en"]):
            try:
                self._reader = self._easyocr.Reader(langs, gpu=gpu_enabled, verbose=False)
                mode = "GPU" if gpu_enabled else "CPU"
                print(f"[OCR] EasyOCR reader initialized ({mode})")
                break
            except Exception as exc:
                last_error = exc
                self._reader = None
                if gpu_enabled:
                    try:
                        self._reader = self._easyocr.Reader(langs, gpu=False, verbose=False)
                        self._gpu_enabled = False
                        print("[OCR] EasyOCR reader initialized (CPU fallback)")
                        break
                    except Exception as exc:
                        last_error = exc
                        self._reader = None
        self._init_error = last_error
        return self._reader

    def recognize(self, image: np.ndarray) -> OCRResult:
        reader = self._get_reader()
        if reader is None:
            message = str(self._init_error or self._import_error or "easyocr_unavailable")
            return OCRResult(self.name, (), error=message)
        image = _ensure_bgr(image)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        try:
            items = reader.readtext(rgb, detail=1, paragraph=False)
        except Exception as exc:
            return OCRResult(self.name, (), error=str(exc))
        lines: list[OCRLine] = []
        for item in items or []:
            if not item or len(item) < 2:
                continue
            box_points = item[0]
            text = str(item[1]).strip()
            if not text:
                continue
            confidence = None
            if len(item) >= 3:
                try:
                    confidence = float(item[2])
                except Exception:
                    confidence = None
            box = _box_from_points(box_points)
            lines.append(OCRLine(text, box, confidence, (OCRWord(text, box, confidence),)))
        return OCRResult(self.name, tuple(lines))


class RapidOCRBackend(OCRBackend):
    name = "rapidocr"

    def __init__(self):
        self._available = False
        self._ocr = None
        self._init_error = None
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore

            self._RapidOCR = RapidOCR
            self._available = True
        except Exception:
            try:
                from rapidocr import RapidOCR  # type: ignore

                self._RapidOCR = RapidOCR
                self._available = True
            except Exception:
                self._available = False

    def available(self) -> bool:
        return self._available

    def _get_ocr(self):
        if self._ocr is not None:
            return self._ocr
        if not self._available:
            return None
        try:
            self._ocr = self._RapidOCR()
        except Exception as exc:
            self._init_error = exc
            self._ocr = None
        return self._ocr

    def recognize(self, image: np.ndarray) -> OCRResult:
        ocr = self._get_ocr()
        if ocr is None:
            message = str(self._init_error or "rapidocr_unavailable")
            return OCRResult(self.name, (), error=message)
        image = _ensure_bgr(image)
        try:
            items = ocr(image)
        except Exception as exc:
            return OCRResult(self.name, (), error=str(exc))
        if isinstance(items, tuple) and len(items) >= 1:
            items = items[0]
        lines: list[OCRLine] = []
        for item in items or []:
            if not item or len(item) < 2:
                continue
            box_points = item[0]
            text = str(item[1]).strip()
            if not text:
                continue
            confidence = None
            if len(item) >= 3:
                try:
                    confidence = float(item[2])
                except Exception:
                    confidence = None
            box = _box_from_points(box_points)
            lines.append(OCRLine(text, box, confidence, (OCRWord(text, box, confidence),)))
        return OCRResult(self.name, tuple(lines))


BACKEND_CLASSES = {
    "windows": WindowsOCRBackend,
    "tesseract": TesseractBackend,
    "easyocr": EasyOCRBackend,
    "rapidocr": RapidOCRBackend,
}


def normalize_backend_name(name: str) -> str:
    return str(name or "").strip().lower()


def default_backend_order() -> List[str]:
    return ["windows"]


def resolve_preferred_backends(preferred: Optional[Sequence[str]] = None) -> List[str]:
    requested = [normalize_backend_name(name) for name in (preferred or []) if normalize_backend_name(name)]
    if not requested:
        requested = default_backend_order()
    order: List[str] = []
    for name in requested:
        if name in BACKEND_CLASSES and name not in order:
            order.append(name)
    return order


def discover_backends(preferred: Optional[Sequence[str]] = None) -> List[OCRBackend]:
    backends: List[OCRBackend] = []
    for name in resolve_preferred_backends(preferred):
        backend_cls = BACKEND_CLASSES.get(name)
        if backend_cls is None:
            continue
        backend = backend_cls()
        if backend.available():
            backends.append(backend)
    return backends
