"""Adversarial numeric/FFI/diagnostic contracts; no model, Qt or network."""
import ctypes

import numpy as np
import pytest

import native_frame_metrics as native
from scan_pipeline import ScanOutcome, ScanStage, ScanTrace, ScanTraceEvent


def event(**kwargs):
    return ScanTraceEvent(ScanStage.CAPTURE, ScanOutcome.SUCCESS, **kwargs)


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_nonfinite_count_cannot_crash_diagnostics(value):
    assert event(item_count=value).item_count == 0


def test_unrepresentable_elapsed_cannot_crash_diagnostics():
    assert event(elapsed_ms=10**1000).elapsed_ms == 0.0


class HostileDetail:
    def __eq__(self, _):
        raise AssertionError("diagnostics must not invoke object equality")

    def __str__(self):
        raise AssertionError("diagnostics must not stringify arbitrary payloads")


@pytest.mark.parametrize("field", ["detail", "provider", "fallback_reason"])
def test_nontext_payload_is_redacted_without_coercion(field):
    assert getattr(event(**{field: HostileDetail()}), field) == "redacted"


@pytest.mark.parametrize("field", ["detail", "provider", "fallback_reason"])
def test_oversized_diagnostic_input_is_rejected_before_regex(field):
    assert getattr(event(**{field: "capture_" + "x" * 100_000}), field) == "redacted"


@pytest.mark.parametrize("value", [None, float("inf"), float("nan"), "bad"])
def test_invalid_dropped_count_does_not_crash_trace(value):
    assert ScanTrace(dropped_events=value).dropped_events == 0


def test_trace_retains_tail_and_validates_even_discarded_input():
    trace = ScanTrace((event(detail=f"capture_{i}") for i in range(1000)), 5)
    assert len(trace.events) == 64
    assert trace.events[0].detail == "capture_936"
    assert trace.dropped_events == 941
    with pytest.raises(TypeError):
        ScanTrace([object()] + list(trace.events))


@pytest.mark.parametrize("changed,delta", [(0, 1), (1, 0), (2, 1), (1, 256)])
def test_inconsistent_native_totals_fall_back(monkeypatch, changed, delta):
    monkeypatch.setenv(native.ENV_ENABLE, "1")

    def kernel(left, right, pixels, channels, out_changed, out_delta):
        ctypes.cast(out_changed, ctypes.POINTER(ctypes.c_uint64))[0] = changed
        ctypes.cast(out_delta, ctypes.POINTER(ctypes.c_uint64))[0] = delta
        return 0

    monkeypatch.setattr(native, "_load_native", lambda: (object(), kernel))
    a = np.zeros((2, 2), dtype=np.uint8)
    assert native.try_native_metrics(a, a) is None


def test_audit_regressions_are_registered_exactly_once():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    inventory = json.loads((root / "ci/test_groups.json").read_text(encoding="utf-8"))
    paths = [p for group in inventory["groups"] for p in group["test_files"]]
    for name in ("test_audit_boundaries.py", "test_responses_hardening.py",
                 "test_runtime_hardening.py", "test_asset_stream_hardening.py"):
        assert paths.count("tests/" + name) == 1


def test_normal_trace_reuses_its_already_immutable_tuple():
    events = (event(), event())
    assert ScanTrace(events).events is events
