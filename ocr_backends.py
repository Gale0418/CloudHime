from __future__ import annotations

import asyncio
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
        self._language = None
        self._mode = "winrt"
        try:
            try:
                from winsdk.windows.media.ocr import OcrEngine  # type: ignore
                from winsdk.windows.globalization import Language  # type: ignore
                from winsdk.windows.graphics.imaging import BitmapDecoder  # type: ignore
                from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter  # type: ignore
            except Exception:
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
        return self._available and self._init_engine() is not None

    def _init_engine(self):
        if self._engine is not None:
            return self._engine
        if not self._available:
            return None
        lang = self._Language("ja-JP")
        try:
            if not self._OcrEngine.is_language_supported(lang):
                self._engine = self._OcrEngine.try_create_from_user_profile_languages()
            else:
                self._engine = self._OcrEngine.try_create_from_language(lang)
        except Exception:
            self._engine = None
        return self._engine

    async def _recognize_async(self, image: np.ndarray):
        engine = self._init_engine()
        if engine is None:
            return None
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
        try:
            ocr_result = asyncio.run(self._recognize_async(image))
        except Exception as exc:
            return OCRResult(self.name, (), error=str(exc))
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
        try:
            _ = self._pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

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
            import torch  # type: ignore

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
        for langs in (["ch_tra", "en"], ["ja", "en"], ["ch_sim", "en"]):
            try:
                self._reader = self._easyocr.Reader(langs, gpu=gpu_enabled, verbose=False)
                mode = "GPU" if gpu_enabled else "CPU"
                print(f"[OCR] EasyOCR reader initialized ({mode})")
                break
            except Exception:
                self._reader = None
                if gpu_enabled:
                    try:
                        self._reader = self._easyocr.Reader(langs, gpu=False, verbose=False)
                        self._gpu_enabled = False
                        print("[OCR] EasyOCR reader initialized (CPU fallback)")
                        break
                    except Exception:
                        self._reader = None
        return self._reader

    def recognize(self, image: np.ndarray) -> OCRResult:
        reader = self._get_reader()
        if reader is None:
            return OCRResult(self.name, ())
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
        except Exception:
            self._ocr = None
        return self._ocr

    def recognize(self, image: np.ndarray) -> OCRResult:
        ocr = self._get_ocr()
        if ocr is None:
            return OCRResult(self.name, ())
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
