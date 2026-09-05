"""Process-policy unit tests. Asset verification is an explicit injected stub.

Load the real runtime source under an isolated name, so no model downloader or
Qt/coordinator is imported. Existing asset/integration suites remain separate.
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import threading
from types import ModuleType, SimpleNamespace

import pytest

SECRET = "test-owned-session-key"


@pytest.fixture
def runtime_module(monkeypatch):
    assets = ModuleType("local_vision_assets")
    assets.ASSET_MINIMUM_BYTES = {}
    assets.ASSET_SHA256 = {}
    assets.VisionAssetError = RuntimeError
    assets.VisionAssets = SimpleNamespace
    assets.verify_asset = lambda *a, **kw: None
    name = "_cloudhime_runtime_policy_unit"
    path = Path(__file__).resolve().parents[1] / "local_vision_runtime.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    with monkeypatch.context() as scoped:
        scoped.setitem(sys.modules, "local_vision_assets", assets)
        spec.loader.exec_module(module)
    return module


class Process:
    def __init__(self, code=None, text=""):
        self.code = code
        self.stderr = io.StringIO(text)
        self.calls = []

    def poll(self):
        return self.code

    def terminate(self):
        self.calls.append("terminate")
        self.code = -15

    def kill(self):
        self.calls.append("kill")
        self.code = -9

    def wait(self, timeout=None):
        self.calls.append("wait")
        return self.code


def make_runtime(module, processes, **options):
    calls = []
    queue = iter(processes)

    def spawn(args, **kwargs):
        calls.append((args, kwargs))
        return next(queue)

    assets = SimpleNamespace(server_path=Path("server"), model_path=Path("model"),
                             projector_path=Path("projector"), managed=False)
    defaults = dict(popen_factory=spawn, urlopen=lambda *a, **k: SimpleNamespace(close=lambda: None),
                    port_allocator=lambda: 41001, sleep=lambda _: None,
                    health_retries=2, gpu_layers=0, api_key_factory=lambda: SECRET)
    defaults.update(options)
    return module.LocalVisionRuntime(assets, **defaults), calls


def test_key_never_enters_argv_and_inherited_runtime_switches_are_removed(runtime_module, monkeypatch):
    monkeypatch.setenv("LLAMA_ARG_AGENT", "1")
    monkeypatch.setenv("LLAMA_ARG_API_KEY_FILE", "/unexpected/keys")
    monkeypatch.setenv("LLAMA_API_KEY", "inherited-secret")
    process = Process()
    runtime, calls = make_runtime(runtime_module, [process])
    try:
        assert runtime.start().name == "ready"
        argv, kwargs = calls[0]
        assert SECRET not in repr(argv) and "--api-key" not in argv
        assert kwargs["env"]["LLAMA_API_KEY"] == SECRET
        assert "LLAMA_ARG_AGENT" not in kwargs["env"]
        assert "LLAMA_ARG_API_KEY_FILE" not in kwargs["env"]
        assert runtime.api_key == SECRET
    finally:
        runtime.stop()


@pytest.mark.parametrize("key", ["bad,key", "bad\nkey", "x" * 257])
def test_invalid_launch_key_is_rejected_before_spawn(runtime_module, key):
    runtime, calls = make_runtime(runtime_module, [Process()], api_key_factory=lambda: key)
    try:
        assert runtime.start().name == "failed"
        assert calls == []
        assert runtime.api_key == ""
    finally:
        runtime.stop()


def test_dead_ready_process_is_restarted(runtime_module):
    first, second = Process(), Process()
    runtime, calls = make_runtime(runtime_module, [first, second])
    try:
        assert runtime.start().name == "ready"
        assert runtime.start().name == "ready" and len(calls) == 1
        first.code = 1
        assert runtime.start().name == "ready"
        assert runtime.owned_process is second and len(calls) == 2
    finally:
        runtime.stop()


def test_cleanup_waits_after_timeout_kill(runtime_module):
    class Stubborn(Process):
        def wait(self, timeout=None):
            self.calls.append("wait")
            if "kill" not in self.calls:
                raise subprocess.TimeoutExpired("test", timeout)
            return -9
    process = Stubborn()
    runtime, _ = make_runtime(runtime_module, [])
    runtime._cleanup_process(process)
    assert process.calls == ["terminate", "wait", "kill", "wait"]
    assert not process.stderr.closed  # only the reader may close its pipe


def test_terminate_error_still_kills_and_reaps(runtime_module):
    class RefusesTerminate(Process):
        def terminate(self):
            self.calls.append("terminate")
            raise OSError("test denied")
    process = RefusesTerminate()
    runtime, _ = make_runtime(runtime_module, [])
    runtime._cleanup_process(process)
    assert process.calls == ["terminate", "kill", "wait"]
    assert not process.stderr.closed  # only the reader may close its pipe


def test_generic_model_failure_is_not_a_gpu_memory_failure(runtime_module):
    process = Process(1, "ggml_cuda_init: found GPU\nfailed to load model: invalid GGUF header\n")
    runtime, calls = make_runtime(runtime_module, [process], gpu_layers=999)
    assert runtime.start().name == "failed"
    assert len(calls) == 1


def test_cuda_memory_failure_still_gets_one_cpu_retry(runtime_module):
    first, second = Process(1, "CUDA out of memory\n"), Process()
    runtime, calls = make_runtime(runtime_module, [first, second], gpu_layers=999)
    try:
        state = runtime.start()
        assert state.name == "ready" and state.mode == "cpu"
        assert len(calls) == 2
        assert calls[1][0][-1] == "0"
    finally:
        runtime.stop()


def test_cancelled_start_never_spawns(runtime_module):
    cancelled = threading.Event()
    cancelled.set()
    runtime, calls = make_runtime(runtime_module, [Process()])
    assert runtime.start(cancel_event=cancelled).name == "stopped"
    assert calls == []


def test_redaction_uses_launch_key_not_mutable_runtime_field(runtime_module):
    runtime, _ = make_runtime(runtime_module, [])
    def spawn(*args, **kwargs):
        runtime.stop()
        raise OSError("launch rejected " + SECRET)
    runtime._popen_factory = spawn
    state = runtime._try_spawn(41001, gpu_layers=0, mode="cpu")
    assert SECRET not in state.detail


def test_stderr_reads_are_bounded_and_normal_errors_are_retained(runtime_module):
    class BoundedOnly(io.StringIO):
        def __iter__(self):
            raise AssertionError("unbounded line iteration")
        def readline(self, size=-1):
            assert 0 < size <= 4097
            return super().readline(size)
    process = Process(1)
    process.stderr = BoundedOnly("ordinary startup error " + SECRET + "\n")
    runtime, _ = make_runtime(runtime_module, [process])
    state = runtime.start()
    assert "ordinary startup error" in state.detail
    assert SECRET not in state.detail


def test_starting_snapshot_is_idempotent_without_a_published_process(runtime_module):
    runtime, calls = make_runtime(runtime_module, [])
    starting = runtime_module.VisionRuntimeState("starting", "loading", "", "gpu")
    runtime._state = starting
    assert runtime.start() is starting
    assert calls == []


def test_cleanup_never_closes_a_pipe_owned_by_another_thread(runtime_module):
    class ReaderOwnedPipe:
        def close(self):
            pytest.fail("cleanup thread must not wait for the stderr read lock")
    process = Process()
    process.stderr = ReaderOwnedPipe()
    runtime, _ = make_runtime(runtime_module, [])
    runtime._cleanup_process(process)
    assert process.calls == ["terminate", "wait"]
