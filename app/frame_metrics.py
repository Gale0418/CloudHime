"""Pure frame-observation metrics, independent of Qt, OCR and providers."""
from __future__ import annotations

import numpy as np

from native_frame_metrics import try_native_metrics


def frame_metrics(baseline: np.ndarray, current: np.ndarray) -> tuple[float, float]:
    if (not isinstance(baseline, np.ndarray) or not isinstance(current, np.ndarray)
            or baseline.shape != current.shape or baseline.dtype != current.dtype
            or current.ndim < 2 or current.size == 0):
        raise ValueError("frames must have matching nonempty shapes and dtypes")
    if not (np.issubdtype(current.dtype, np.number) or current.dtype == np.bool_):
        raise ValueError("frames must be numeric or boolean")
    native = try_native_metrics(baseline, current)
    if native is not None:
        return native
    changed_values = current != baseline
    changed = (changed_values if current.ndim == 2 else
               np.any(changed_values, axis=tuple(range(2, current.ndim))))
    if current.dtype == np.uint8:
        # [-255, 255] fits int16. One temporary replaces three float64 arrays.
        delta = np.subtract(current, baseline, dtype=np.int16)
        np.abs(delta, out=delta)
    elif np.issubdtype(current.dtype, np.integer) and current.dtype.itemsize > 4:
        delta = np.abs(current.astype(object) - baseline.astype(object))
    elif current.dtype.itemsize > 8:
        delta = np.abs(current.astype(object) - baseline.astype(object))
    elif np.issubdtype(current.dtype, np.complexfloating):
        delta = np.abs(current.astype(np.complex128) - baseline.astype(np.complex128))
    else:
        delta = np.abs(current.astype(np.float64) - baseline.astype(np.float64))
    return float(np.mean(changed)), float(np.mean(delta))
