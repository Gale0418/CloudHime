from concurrent.futures import ThreadPoolExecutor
import builtins
import threading
import time
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from ocr_backends import (
    OCRResult,
    TesseractBackend,
    WindowsOCRBackend,
    discover_backends,
)


@pytest.mark.parametrize(
    "missing_module",
    ["winrt.windows.foundation", "winrt.windows.foundation.collections"],
)
def test_windows_ocr_backend_fails_fast_without_winrt_async_modules(
    monkeypatch, missing_module
):
    real_import = builtins.__import__
    module_attributes = {
        "winrt.windows.media.ocr": {"OcrEngine": object},
        "winrt.windows.globalization": {"Language": object},
        "winrt.windows.graphics.imaging": {"BitmapDecoder": object},
        "winrt.windows.storage.streams": {
            "InMemoryRandomAccessStream": object,
            "DataWriter": object,
        },
    }
    fake_modules = {}
    for name, attributes in module_attributes.items():
        module = ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        fake_modules[name] = module
    fake_modules["winrt.windows.foundation"] = ModuleType(
        "winrt.windows.foundation"
    )
    fake_modules["winrt.windows.foundation.collections"] = ModuleType(
        "winrt.windows.foundation.collections"
    )

    def isolated_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("winsdk."):
            raise ModuleNotFoundError("winsdk fallback unavailable", name=name)
        if name == missing_module:
            raise ModuleNotFoundError("simulated missing WinRT module", name=name)
        if name in fake_modules:
            return fake_modules[name]
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", isolated_import)
    async_starts = []

    def fail_if_async_starts(coroutine):
        async_starts.append(coroutine)
        coroutine.close()
        pytest.fail("WinRT async must not start when a required module is absent")

    monkeypatch.setattr("ocr_backends.asyncio.run", fail_if_async_starts)

    backend = WindowsOCRBackend()

    assert backend.available() is False
    assert discover_backends(["windows"]) == []
    assert async_starts == []


def test_windows_ocr_backend_serializes_engine_access(monkeypatch):
    backend = WindowsOCRBackend()
    active = 0
    max_active = 0
    state_lock = threading.Lock()

    def fake_recognize(_image):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with state_lock:
            active -= 1
        return OCRResult("windows", ())

    monkeypatch.setattr(backend, "_recognize_once", fake_recognize)
    image = np.zeros((8, 8, 3), dtype=np.uint8)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(backend.recognize, [image] * 4))

    assert len(results) == 4
    assert max_active == 1


def test_windows_ocr_backend_uses_available_language_after_profile_fallback(monkeypatch):
    backend = WindowsOCRBackend()
    language_attempts = []
    engine = object()

    class FakeOcrEngine:
        available_recognizer_languages = [SimpleNamespace(language_tag="en-US")]

        @staticmethod
        def is_language_supported(language):
            return language == "ja-JP"

        @staticmethod
        def try_create_from_language(language):
            language_attempts.append(language)
            return engine if language == "en-US" else None

        @staticmethod
        def try_create_from_user_profile_languages():
            return None

    backend._available = True
    backend._Language = lambda language_tag: language_tag
    backend._OcrEngine = FakeOcrEngine

    assert backend.available() is True
    assert backend._init_engine() is engine
    assert language_attempts == ["ja-JP", "en-US"]


def test_windows_ocr_backend_retries_when_language_support_becomes_available():
    backend = WindowsOCRBackend()
    engine = object()

    class FakeOcrEngine:
        available_recognizer_languages = []

        @staticmethod
        def is_language_supported(_language):
            return False

        @staticmethod
        def try_create_from_language(_language):
            return engine

        @staticmethod
        def try_create_from_user_profile_languages():
            return None

    backend._available = True
    backend._Language = lambda language_tag: language_tag
    backend._OcrEngine = FakeOcrEngine

    assert backend._init_engine() is None
    FakeOcrEngine.available_recognizer_languages = [SimpleNamespace(language_tag="en-US")]
    assert backend._init_engine() is engine


def test_windows_ocr_backend_reports_when_no_language_engine_can_be_created():
    backend = WindowsOCRBackend()

    class FakeOcrEngine:
        available_recognizer_languages = [SimpleNamespace(language_tag="en-US")]

        @staticmethod
        def is_language_supported(_language):
            return False

        @staticmethod
        def try_create_from_language(_language):
            return None

        @staticmethod
        def try_create_from_user_profile_languages():
            return None

    backend._available = True
    backend._Language = lambda language_tag: language_tag
    backend._OcrEngine = FakeOcrEngine
    result = backend.recognize(np.zeros((8, 8, 3), dtype=np.uint8))

    assert backend.available() is True
    assert result.lines == ()
    assert result.error == "windows_ocr_engine_unavailable"


def test_windows_ocr_backend_bounds_engine_initialization_exception():
    backend = WindowsOCRBackend()

    class FakeOcrEngine:
        available_recognizer_languages = []

        @staticmethod
        def is_language_supported(_language):
            raise RuntimeError("simulated engine failure " + "x" * 500)

        @staticmethod
        def try_create_from_user_profile_languages():
            return None

    backend._available = True
    backend._Language = lambda language_tag: language_tag
    backend._OcrEngine = FakeOcrEngine
    result = backend.recognize(np.zeros((8, 8, 3), dtype=np.uint8))

    assert result.error.startswith("windows_ocr_engine_init_failed: RuntimeError:")
    assert len(result.error) <= 192


def test_windows_ocr_backend_keeps_real_empty_recognition_as_empty(monkeypatch):
    backend = WindowsOCRBackend()

    async def empty_result(_image):
        return SimpleNamespace(lines=[])

    monkeypatch.setattr(backend, "_recognize_async", empty_result)
    result = backend.recognize(np.zeros((8, 8, 3), dtype=np.uint8))

    assert result.lines == ()
    assert result.error == ""


def test_tesseract_backend_caches_version_probe_for_available_and_recognize(monkeypatch):
    backend = TesseractBackend()
    probes = []
    recognitions = []

    def get_version():
        probes.append(True)
        return "5.3.0"

    def image_to_data(_image, *, output_type, lang):
        recognitions.append((output_type, lang))
        return {"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []}

    backend._available = True
    backend._pytesseract = SimpleNamespace(
        get_tesseract_version=get_version,
        image_to_data=image_to_data,
    )
    backend._output_type = SimpleNamespace(DICT="dict")

    assert backend.available() is True
    assert backend.available() is True
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    assert backend.recognize(image).error == ""
    assert backend.recognize(image).error == ""

    assert len(probes) == 1
    assert len(recognitions) == 2


def test_tesseract_backend_keeps_disabled_backend_unavailable(monkeypatch):
    backend = TesseractBackend()
    backend._available = False
    backend._pytesseract = SimpleNamespace(
        get_tesseract_version=lambda: pytest.fail("disabled backend must not probe")
    )

    assert backend.available() is False
