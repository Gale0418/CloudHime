from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from frame_gate import FrameGate, FrameGateObservation


def test_identical_frame_is_observed_but_never_skips_ocr():
    gate = FrameGate()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    assert gate.observe(frame, context="panel").classification == "baseline"
    observed = gate.observe(frame.copy(), context="panel")
    assert observed.classification == "identical"
    assert observed.changed_pixel_ratio == observed.mean_absolute_delta == 0.0
    assert observed.skip_ocr is False


def test_one_pixel_and_tiny_noise_are_near_but_never_skip_ocr():
    gate, frame = FrameGate(), np.zeros((64, 64), dtype=np.uint8)
    gate.observe(frame, context="panel")
    one_pixel = frame.copy()
    one_pixel[0, 0] = 255
    assert gate.observe(one_pixel, context="panel").classification == "near"
    tiny_noise = one_pixel.copy()
    tiny_noise[1, 1] = 1
    observed = gate.observe(tiny_noise, context="panel")
    assert observed.classification == "near"
    assert observed.skip_ocr is False


def test_large_change_is_changed_and_never_skips_ocr():
    gate = FrameGate()
    gate.observe(np.zeros((64, 64, 3), dtype=np.uint8), context="panel")
    observed = gate.observe(np.full((64, 64, 3), 255, dtype=np.uint8), context="panel")
    assert observed.classification == "changed"
    assert observed.changed_pixel_ratio == 1.0
    assert observed.skip_ocr is False


def test_context_shape_and_dtype_changes_reset_baseline():
    gate, frame = FrameGate(), np.zeros((8, 8), dtype=np.uint8)
    assert gate.observe(frame, context="first").classification == "baseline"
    assert gate.observe(frame, context="second").classification == "baseline"
    assert gate.observe(np.zeros((9, 8), dtype=np.uint8), context="second").classification == "baseline"
    assert gate.observe(np.zeros((9, 8), dtype=np.float32), context="second").classification == "baseline"


def test_4k_frame_uses_a_bounded_immutable_sample():
    gate = FrameGate(max_sample_dimension=10_000)
    observed = gate.observe(np.zeros((2160, 3840, 3), dtype=np.uint8))
    assert observed.sampled_pixels == 64 * 64
    assert gate._baseline is not None
    assert gate._baseline.shape[:2] == (64, 64)
    assert gate._baseline.flags.writeable is False


def test_observation_is_immutable_and_basic_concurrent_calls_are_safe():
    gate = FrameGate()
    observation = gate.observe(np.zeros((4, 4), dtype=np.uint8))
    assert isinstance(observation, FrameGateObservation)
    with pytest.raises(FrozenInstanceError):
        observation.classification = "changed"
    frames = [np.full((32, 32), number, dtype=np.uint8) for number in range(16)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        observations = list(executor.map(gate.observe, frames))
    assert len(observations) == len(frames)
    assert all(item.skip_ocr is False for item in observations)

def test_complex_and_wide_integer_changes_are_never_collapsed_to_identical():
    complex_gate = FrameGate()
    complex_frame = np.full((2, 2), 1 + 0j, dtype=np.complex128)
    complex_gate.observe(complex_frame)
    complex_changed = complex_frame.copy()
    complex_changed[0, 0] = 1 + 1j
    complex_observation = complex_gate.observe(complex_changed)
    assert complex_observation.classification != "identical"
    assert complex_observation.changed_pixel_ratio > 0.0

    integer_gate = FrameGate()
    maximum = np.iinfo(np.uint64).max
    integer_frame = np.full((2, 2), maximum - 1, dtype=np.uint64)
    integer_gate.observe(integer_frame)
    integer_changed = integer_frame.copy()
    integer_changed[0, 0] = maximum
    integer_observation = integer_gate.observe(integer_changed)
    assert integer_observation.classification != "identical"
    assert integer_observation.changed_pixel_ratio > 0.0
