from __future__ import annotations

import ctypes
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import native_frame_metrics as native

_REAL_LOAD = native._load_native


@pytest.fixture(autouse=True)
def clear_loader_cache():
    _REAL_LOAD.cache_clear()
    yield
    _REAL_LOAD.cache_clear()


def numpy_metrics(a, b):
    changed = a != b
    if a.ndim > 2:
        changed = np.any(changed, axis=tuple(range(2, a.ndim)))
    return float(np.mean(changed)), float(np.mean(np.abs(a.astype(float) - b.astype(float))))


def test_native_is_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv(native.ENV_ENABLE, raising=False)
    monkeypatch.setattr(native, "_load_native", lambda: pytest.fail("unexpected DLL load"))
    a = np.zeros((2, 2), dtype=np.uint8)
    assert native.try_native_metrics(a, a) is None


def test_missing_library_falls_back(monkeypatch):
    monkeypatch.setenv(native.ENV_ENABLE, "1")
    monkeypatch.setattr(native, "_load_native", lambda: None)
    a = np.zeros((2, 2), dtype=np.uint8)
    assert native.try_native_metrics(a, a) is None


@pytest.mark.parametrize("kind", ["dtype", "shape", "empty", "large"])
def test_unsupported_input_never_enters_ffi(monkeypatch, kind):
    monkeypatch.setenv(native.ENV_ENABLE, "1")
    monkeypatch.setattr(native, "_load_native", lambda: pytest.fail("unexpected DLL load"))
    a = np.zeros((2, 2), dtype=np.uint8)
    b = a
    if kind == "dtype":
        b = a.astype(np.float32)
    elif kind == "shape":
        b = a[:1]
    elif kind == "empty":
        a = b = np.zeros((2, 2, 0), dtype=np.uint8)
    else:
        monkeypatch.setattr(native, "MAX_NATIVE_BYTES", 3)
    assert native.try_native_metrics(a, b) is None


def test_ffi_uses_immutable_snapshots_with_correct_pixel_grouping(monkeypatch):
    monkeypatch.setenv(native.ENV_ENABLE, "1")
    a = np.zeros((2, 4, 3), dtype=np.uint8)[:, ::2]
    b = a.copy()
    b[0, 0] = [255, 1, 0]
    def kernel(left, right, pixels, channels, changed, delta):
        assert isinstance(left, bytes) and isinstance(right, bytes)
        assert (pixels, channels) == (4, 3)
        assert len(left) == len(right) == 12
        assert right[:3] == bytes([255, 1, 0])
        ctypes.cast(changed, ctypes.POINTER(ctypes.c_uint64))[0] = 1
        ctypes.cast(delta, ctypes.POINTER(ctypes.c_uint64))[0] = 256
        return 0
    monkeypatch.setattr(native, "_load_native", lambda: (object(), kernel))
    assert native.try_native_metrics(a, b) == numpy_metrics(a, b)


@pytest.mark.parametrize("status,changed,delta", [(1, 0, 0), (2, 0, 0), (0, 5, 0), (0, 0, 1021)])
def test_error_or_impossible_totals_fall_back(monkeypatch, status, changed, delta):
    monkeypatch.setenv(native.ENV_ENABLE, "1")
    def kernel(left, right, pixels, channels, out_changed, out_delta):
        ctypes.cast(out_changed, ctypes.POINTER(ctypes.c_uint64))[0] = changed
        ctypes.cast(out_delta, ctypes.POINTER(ctypes.c_uint64))[0] = delta
        return status
    monkeypatch.setattr(native, "_load_native", lambda: (object(), kernel))
    a = np.zeros((2, 2), dtype=np.uint8)
    assert native.try_native_metrics(a, a) is None


def test_loader_does_not_search_current_directory(tmp_path, monkeypatch):
    source = tmp_path / "trusted"
    source.mkdir()
    monkeypatch.setattr(native, "__file__", str(source / "native_frame_metrics.py"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "libcloudhime_native.so").write_bytes(b"not executable")
    monkeypatch.setattr(native.ctypes, "CDLL", lambda *a, **k: pytest.fail("untrusted load"))
    assert _REAL_LOAD() is None


def test_loader_rejects_symlink_escape(tmp_path, monkeypatch):
    source = tmp_path / "trusted"
    release = source / "native" / "target" / "release"
    release.mkdir(parents=True)
    external = tmp_path / "external.so"
    external.write_bytes(b"not executable")
    try:
        (release / "libcloudhime_native.so").symlink_to(external)
    except OSError:
        pytest.skip("Host does not allow test symlinks")
    monkeypatch.setattr(native.sys, "platform", "linux")
    monkeypatch.setattr(native, "__file__", str(source / "native_frame_metrics.py"))
    monkeypatch.setattr(native.ctypes, "CDLL", lambda *a, **k: pytest.fail("untrusted load"))
    assert _REAL_LOAD() is None


def test_loader_rejects_incompatible_abi(tmp_path, monkeypatch):
    source = tmp_path / "trusted"
    release = source / "native" / "target" / "release"
    release.mkdir(parents=True)
    (release / "libcloudhime_native.so").write_bytes(b"test fixture")
    class Version:
        def __call__(self):
            return native.ABI_VERSION + 1
    monkeypatch.setattr(native.sys, "platform", "linux")
    monkeypatch.setattr(native, "__file__", str(source / "native_frame_metrics.py"))
    monkeypatch.setattr(native.ctypes, "CDLL", lambda *a, **k: SimpleNamespace(cloudhime_abi_version=Version()))
    assert _REAL_LOAD() is None


@pytest.mark.skipif(os.environ.get(native.ENV_ENABLE) != "1", reason="Compiled Rust 1.98.1 gate requires explicit native opt-in")
def test_compiled_rust_matches_numpy_oracle():
    assert _REAL_LOAD() is not None, "Native opt-in requires a locally built, compatible Rust library"
    rng = np.random.default_rng(9105)
    for shape in [(1, 1), (64, 64), (31, 17, 3), (9, 11, 2, 4)]:
        for _ in range(20):
            a = rng.integers(0, 256, size=shape, dtype=np.uint8)
            b = rng.integers(0, 256, size=shape, dtype=np.uint8)
            assert native.try_native_metrics(a, b) == numpy_metrics(a, b)
            assert native.try_native_metrics(a, a) == (0.0, 0.0)
