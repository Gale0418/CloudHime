from concurrent.futures import ThreadPoolExecutor
import threading
import time

import numpy as np

from ocr_backends import OCRResult, WindowsOCRBackend


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
