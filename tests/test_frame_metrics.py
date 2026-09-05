from __future__ import annotations

import numpy as np
import pytest

from frame_gate import FrameGate
from frame_metrics import frame_metrics


def oracle(a, b):
    changed = a != b
    if a.ndim > 2:
        changed = np.any(changed, axis=tuple(range(2, a.ndim)))
    if (np.issubdtype(a.dtype, np.integer) and a.dtype.itemsize > 4) or a.dtype.itemsize > 8:
        delta = np.abs(b.astype(object) - a.astype(object))
    elif np.issubdtype(a.dtype, np.complexfloating):
        delta = np.abs(b.astype(np.complex128) - a.astype(np.complex128))
    else:
        delta = np.abs(b.astype(np.float64) - a.astype(np.float64))
    return float(np.mean(changed)), float(np.mean(delta))


@pytest.mark.parametrize("shape", [(1, 1), (64, 64), (17, 31, 3), (12, 13, 2, 4)])
@pytest.mark.parametrize("dtype", [np.uint8, np.int8, np.int16, np.int32, np.int64,
                                 np.uint64, np.float32, np.float64, np.complex64,
                                 np.complex128, np.bool_])
def test_matches_original_numpy_oracle(shape, dtype, monkeypatch):
    monkeypatch.delenv("CLOUDHIME_NATIVE_FRAME_METRICS", raising=False)
    rng = np.random.default_rng(9105)
    a = rng.integers(0, 100, size=shape).astype(dtype)
    b = rng.integers(0, 100, size=shape).astype(dtype)
    assert frame_metrics(a, b) == oracle(a, b)
    assert frame_metrics(a, a) == oracle(a, a)


def test_noncontiguous_channel_views_match_oracle():
    a = np.arange(120, dtype=np.uint8).reshape(10, 4, 3)[::2, ::2, ::-1]
    b = (a.copy() + 250).astype(np.uint8)
    assert frame_metrics(a, b) == oracle(a, b)


def test_wide_integer_extremes_do_not_overflow():
    a = np.array([[0, np.iinfo(np.uint64).max]], dtype=np.uint64)
    b = a[:, ::-1]
    assert frame_metrics(a, b) == oracle(a, b)


@pytest.mark.parametrize("shape", [(0, 2), (2, 0), (2, 2, 0)])
def test_empty_axes_are_rejected(shape):
    a = np.zeros(shape, dtype=np.uint8)
    with pytest.raises(ValueError):
        frame_metrics(a, a)
    with pytest.raises(ValueError):
        FrameGate().observe(a)


def test_mismatched_or_non_numeric_inputs_are_rejected():
    a = np.zeros((2, 2), dtype=np.uint8)
    for b in [a[:1], a.astype(float), [[0, 0], [0, 0]]]:
        with pytest.raises(ValueError):
            frame_metrics(a, b)
    with pytest.raises(ValueError):
        frame_metrics(np.array([["x"]]), np.array([["x"]]))


def test_baseline_is_detached_and_never_skips_ocr():
    gate = FrameGate()
    a = np.zeros((64, 64, 3), dtype=np.uint8)
    gate.observe(a)
    assert not np.shares_memory(gate._baseline, a)
    assert not gate._baseline.flags.writeable
    a[:] = 255
    observation = gate.observe(a)
    assert observation.changed_pixel_ratio == 1.0
    assert not observation.skip_ocr


def test_uint8_all_pairs_match_oracle_without_wraparound():
    values = np.arange(256, dtype=np.uint8)
    a = np.broadcast_to(values[:, None], (256, 256))
    b = np.broadcast_to(values[None, :], (256, 256))
    assert frame_metrics(a, b) == oracle(a, b)
