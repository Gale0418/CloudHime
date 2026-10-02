from concurrent.futures import ThreadPoolExecutor
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from ocr_backends import OCRResult, TesseractBackend, WindowsOCRBackend


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
