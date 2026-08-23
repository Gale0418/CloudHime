"""Lazy CPU runtime for confidence-gated Japanese OCR rescue."""

from __future__ import annotations

from enum import Enum
import threading
from typing import Any, Callable

from japanese_ocr_assets import JapaneseOCRAssets, JapaneseOCRAssetError, ensure_japanese_ocr_assets
from japanese_ocr_rescue import MeikiCandidate, candidate_from_meiki_results


class JapaneseOCRRuntimeState(Enum):
    disabled = "disabled"
    starting = "starting"
    ready = "ready"
    failed = "failed"


_CONSTRUCTOR_LOCK = threading.Lock()


def _create_meiki_ocr(assets: JapaneseOCRAssets) -> Any:
    import meikiocr.ocr as module

    paths = {
        (module.DET_MODEL_REPO, module.DET_MODEL_NAME): str(assets.detection),
        (module.REC_MODEL_REPO, module.REC_MODEL_NAME): str(assets.horizontal),
        (module.REC_MODEL_REPO, module.VREC_MODEL_NAME): str(assets.vertical),
    }
    with _CONSTRUCTOR_LOCK:
        original = module._get_model_path
        module._get_model_path = lambda repo, filename: paths[(repo, filename)]
        try:
            return module.MeikiOCR(provider="CPUExecutionProvider")
        finally:
            module._get_model_path = original


class JapaneseOCRRuntime:
    def __init__(self, assets: JapaneseOCRAssets, progress_callback: Callable[[str, int], None] | None = None):
        self.assets = assets
        self.progress_callback = progress_callback
        self.state = JapaneseOCRRuntimeState.disabled
        self.last_error = ""
        self._ocr = None
        self._lock = threading.Lock()
        self._generation = 0
        self._cancel = threading.Event()

    def _report(
        self,
        phase: str,
        progress: int,
        *,
        cancel_event: threading.Event | None = None,
        generation: int | None = None,
    ) -> None:
        token = cancel_event or self._cancel
        if token.is_set() or (
            generation is not None and generation != self._generation
        ):
            raise JapaneseOCRAssetError("japanese OCR setup cancelled")
        if self.progress_callback:
            self.progress_callback(phase, progress)

    def start(self) -> bool:
        with self._lock:
            if self.state is JapaneseOCRRuntimeState.ready:
                return True
            if self.state is JapaneseOCRRuntimeState.starting:
                return False
            self._generation += 1
            generation = self._generation
            cancel_event = threading.Event()
            self._cancel = cancel_event
            self.state = JapaneseOCRRuntimeState.starting
            self.last_error = ""

        def report(phase: str, progress: int) -> None:
            self._report(
                phase,
                progress,
                cancel_event=cancel_event,
                generation=generation,
            )

        try:
            ensure_japanese_ocr_assets(
                self.assets,
                progress_callback=report,
                cancel_event=cancel_event,
            )
            report("warming_up", 85)
            ocr = _create_meiki_ocr(self.assets)

            import numpy as np

            ocr.run_ocr(np.zeros((64, 256, 3), dtype=np.uint8))
            ocr.run_recognition([np.zeros((32, 256, 3), dtype=np.uint8)])
            ocr.run_recognition([np.zeros((256, 32, 3), dtype=np.uint8)])
            report("ready", 100)
            with self._lock:
                if cancel_event.is_set() or generation != self._generation:
                    return False
                self._ocr = ocr
                self.state = JapaneseOCRRuntimeState.ready
            return True
        except Exception as exc:
            with self._lock:
                if cancel_event.is_set() or generation != self._generation:
                    return False
                self._ocr = None
                self.last_error = f"{type(exc).__name__}: {exc}"
                self.state = JapaneseOCRRuntimeState.failed
            return False

    def disable(self) -> None:
        with self._lock:
            self._generation += 1
            self._cancel.set()
            self._ocr = None
            self.state = JapaneseOCRRuntimeState.disabled
            self.last_error = ""

    def run(self, image: Any) -> MeikiCandidate:
        with self._lock:
            if self.state is not JapaneseOCRRuntimeState.ready or self._ocr is None:
                raise RuntimeError("japanese OCR runtime is not ready")
            return candidate_from_meiki_results(self._ocr.run_ocr(image))