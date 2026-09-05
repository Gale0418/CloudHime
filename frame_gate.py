"""Conservative, shadow-only consecutive-frame observation for OCR pipelines."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from threading import RLock
from typing import Any

import numpy as np

from frame_metrics import frame_metrics


@dataclass(frozen=True, slots=True)
class FrameGateObservation:
    """A non-authoritative observation. OCR is never skipped."""

    classification: str
    changed_pixel_ratio: float
    mean_absolute_delta: float
    sampled_pixels: int
    skip_ocr: bool = False


class FrameGate:
    """Bounded, thread-safe observer for consecutive frames in one context."""

    def __init__(self, max_sample_dimension: int = 64,
                 near_changed_pixel_ratio: float = 0.02,
                 near_mean_absolute_delta: float = 8.0) -> None:
        self._max_sample_dimension = self._dimension(max_sample_dimension)
        self._near_changed_pixel_ratio = self._ratio(near_changed_pixel_ratio)
        self._near_mean_absolute_delta = self._delta(near_mean_absolute_delta)
        self._lock = RLock()
        self._baseline: np.ndarray | None = None
        self._baseline_context: bytes | None = None
        self._baseline_shape: tuple[int, ...] | None = None
        self._baseline_dtype: np.dtype[Any] | None = None

    def observe(self, frame: np.ndarray, context: Any = None) -> FrameGateObservation:
        """Observe a frame; the returned decision is always ``skip_ocr=False``."""
        array = self._validate(frame)
        context_token = self._context_token(context)
        sampled = self._sample(array)
        shape, dtype = tuple(array.shape), array.dtype
        with self._lock:
            reset = (self._baseline is None or self._baseline_context != context_token
                     or self._baseline_shape != shape or self._baseline_dtype != dtype)
            result = (self._observation("baseline", 0.0, 0.0, sampled)
                      if reset else self._compare(self._baseline, sampled))
            # Advanced indexing in _sample already owns a detached snapshot.
            sampled.setflags(write=False)
            self._baseline = sampled
            self._baseline_context, self._baseline_shape, self._baseline_dtype = context_token, shape, dtype
            return result

    @staticmethod
    def _dimension(value: int) -> int:
        try:
            return max(1, min(64, int(value))) if not isinstance(value, bool) else 64
        except (TypeError, ValueError, OverflowError):
            return 64

    @staticmethod
    def _ratio(value: float) -> float:
        try:
            result = float(value)
            return min(1.0, max(0.0, result)) if np.isfinite(result) else 0.02
        except (TypeError, ValueError, OverflowError):
            return 0.02

    @staticmethod
    def _delta(value: float) -> float:
        try:
            result = float(value)
            return max(0.0, result) if np.isfinite(result) else 8.0
        except (TypeError, ValueError, OverflowError):
            return 8.0

    @staticmethod
    def _validate(frame: np.ndarray) -> np.ndarray:
        if not isinstance(frame, np.ndarray) or frame.ndim < 2:
            raise ValueError("frame must be a NumPy array with at least two dimensions")
        if frame.size == 0:
            raise ValueError("frame dimensions must be non-zero")
        if not (np.issubdtype(frame.dtype, np.number) or frame.dtype == np.bool_):
            raise ValueError("frame dtype must be numeric or boolean")
        return frame

    def _sample(self, frame: np.ndarray) -> np.ndarray:
        rows = np.linspace(0, frame.shape[0] - 1, min(frame.shape[0], self._max_sample_dimension), dtype=np.intp)
        columns = np.linspace(0, frame.shape[1] - 1, min(frame.shape[1], self._max_sample_dimension), dtype=np.intp)
        return np.ascontiguousarray(frame[rows[:, None], columns])

    def _compare(self, baseline: np.ndarray, current: np.ndarray) -> FrameGateObservation:
        ratio, mean = frame_metrics(baseline, current)
        classification = "identical" if ratio == 0.0 else (
            "near" if ratio <= self._near_changed_pixel_ratio and mean <= self._near_mean_absolute_delta else "changed")
        return self._observation(classification, ratio, mean, current)

    @staticmethod
    def _observation(classification: str, ratio: float, mean: float, sampled: np.ndarray) -> FrameGateObservation:
        return FrameGateObservation(classification, ratio, mean, int(sampled.shape[0] * sampled.shape[1]))

    @staticmethod
    def _context_token(context: Any) -> bytes:
        """Persist only a digest; never the supplied context text or bytes."""
        try:
            value = repr(context)
        except Exception:
            value = f"<{type(context).__module__}.{type(context).__qualname__}>"
        return blake2b(value.encode("utf-8", "backslashreplace"), digest_size=16).digest()
