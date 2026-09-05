"""Opt-in, dependency-free ctypes boundary for the Rust frame kernel.

No PATH/current-directory loading, network access or automatic compilation.
The native path stays disabled until explicitly enabled after local validation.
"""
from __future__ import annotations

import ctypes
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

ABI_VERSION = 1
MAX_NATIVE_BYTES = 16 * 1024 * 1024
ENV_ENABLE = "CLOUDHIME_NATIVE_FRAME_METRICS"


@lru_cache(maxsize=1)
def _load_native():
    names = {"win32": "cloudhime_native.dll", "darwin": "libcloudhime_native.dylib", "linux": "libcloudhime_native.so"}
    name = names.get(sys.platform)
    if name is None:
        return None
    try:
        root = Path(__file__).resolve().parent
        library = (root / "native" / "target" / "release" / name).resolve()
        if not library.is_relative_to(root) or not library.is_file():
            return None
        # Restrict Windows dependency lookup to the DLL's directory and System32.
        options = {"winmode": 0x00000900} if sys.platform == "win32" else {}
        handle = ctypes.CDLL(str(library), **options)
        version = handle.cloudhime_abi_version
        version.argtypes = []
        version.restype = ctypes.c_uint32
        if version() != ABI_VERSION:
            return None
        kernel = handle.cloudhime_frame_metrics_u8
        kernel.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64),
        ]
        kernel.restype = ctypes.c_int32
        # Keep the CDLL alive for as long as its function pointer is used.
        return handle, kernel
    except (OSError, RuntimeError, AttributeError, TypeError):
        return None


def try_native_metrics(baseline: np.ndarray, current: np.ndarray) -> tuple[float, float] | None:
    """Return exact uint8 metrics, or None to preserve the NumPy path.

    Immutable bytes snapshots keep foreign reads safe while CDLL releases the
    GIL; merely marking a NumPy view readonly does not freeze writable aliases.
    Copies are bounded, made only for the explicit native opt-in, and never kept.
    """
    if os.environ.get(ENV_ENABLE) != "1":
        return None
    if (baseline.dtype != np.uint8 or current.dtype != np.uint8
            or baseline.shape != current.shape or current.ndim < 2
            or not current.size or current.nbytes > MAX_NATIVE_BYTES):
        return None
    loaded = _load_native()
    if loaded is None:
        return None
    pixels = int(current.shape[0]) * int(current.shape[1])
    channels = int(current.size) // pixels
    left, right = baseline.tobytes(order="C"), current.tobytes(order="C")
    changed, delta = ctypes.c_uint64(), ctypes.c_uint64()
    try:
        status = loaded[1](left, right, pixels, channels, ctypes.byref(changed), ctypes.byref(delta))
    except (OSError, ctypes.ArgumentError):
        return None
    # Every changed pixel contributes at least 1 and at most channels * 255.
    # Check the relationship as well as individual caps: (0, positive_delta)
    # must never become an "identical" observation after a broken ABI call.
    if (status != 0 or changed.value > pixels
            or not changed.value <= delta.value <= changed.value * channels * 255):
        return None
    return changed.value / pixels, delta.value / len(right)
