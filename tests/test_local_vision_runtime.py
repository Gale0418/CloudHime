"""
tests/test_local_vision_runtime.py
------------------------------------
Task 2：LocalVisionRuntime 生命週期 – TDD 單元測試。

所有 subprocess、socket、HTTP 均以 fake 注入；不啟動任何真實模型。
覆蓋範圍：
  - missing assets（server / model / projector）
  - loopback dynamic port command construction
  - Windows CREATE_NO_WINDOW hidden process flag
  - health check: ready / timeout / early exit
  - start idempotency（already starting / already ready）
  - CUDA/VRAM failure → 單次 CPU mode retry
  - second failure → failed state（不無限重試）
  - stop terminate then kill only owned process
  - stderr truncated to 2000 chars in detail
  [FIX] health loop must NOT block on stderr (daemon thread required)
  [FIX] VisionRuntimeState must be frozen=True
  [FIX] failed _try_spawn must cleanup process before CPU retry
  [FIX] health_timeout must not leave residual process
  [FIX] health urlopen response must be closed
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import threading
from pathlib import Path
from typing import Iterator, List, Optional

import pytest

import local_vision_runtime as runtime_module
from local_vision_assets import VisionAssets
from local_vision_runtime import LocalVisionRuntime, VisionRuntimeState


# ──────────────────────────────────────────────────────────────────────────────
# Fake 基礎設施
# ──────────────────────────────────────────────────────────────────────────────


def _make_assets(tmp_path: Path, *, create_files: bool = True) -> VisionAssets:
    """建立含真實路徑的 VisionAssets（預設建立空檔以通過存在性檢查）。"""
    server = tmp_path / "runtime" / "llama-server.exe"
    model = tmp_path / "models" / "gemma-3-4b-it.Q4_K_M.gguf"
    projector = tmp_path / "models" / "mmproj-model-f16.gguf"
    if create_files:
        server.parent.mkdir(parents=True, exist_ok=True)
        model.parent.mkdir(parents=True, exist_ok=True)
        server.write_bytes(b"x" * 1024)
        model.write_bytes(b"x" * 1024)
        projector.write_bytes(b"x" * 1024)
    return VisionAssets(server_path=server, model_path=model, projector_path=projector)


class FakeProcess:
    """模擬 subprocess.Popen 回傳物件。"""

    def __init__(
        self,
        *,
        returncode: Optional[int] = None,  # None → still running
        stderr_lines: List[str] | None = None,
        stderr_obj=None,  # 覆寫 stderr iterator（供 BlockingStderr 注入）
    ) -> None:
        self._returncode = returncode
        if stderr_obj is not None:
            self._stderr_obj = stderr_obj
        else:
            self._stderr_obj: Iterator[str] = iter(stderr_lines or [])
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0
        self.args: list[str] = []  # 由 FakePopen 填入

    def poll(self) -> Optional[int]:
        return self._returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self._returncode = -15  # SIGTERM

    def kill(self) -> None:
        self.kill_calls += 1
        self._returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        return self._returncode or 0

    # stderr as iterator（line-by-line）
    @property
    def stderr(self):
        return self._stderr_obj


class ExitedProcess(FakeProcess):
    """代表已提前退出（returncode 非 None）的 process。"""

    def __init__(self, stderr_text: str = "") -> None:
        super().__init__(
            returncode=1,
            stderr_lines=[stderr_text] if stderr_text else [],
        )


class RunningProcess(FakeProcess):
    """代表健康運行中（returncode = None）的 process。"""

    def __init__(self, stderr_obj=None) -> None:
        super().__init__(returncode=None, stderr_obj=stderr_obj)


class BlockingStderr:
    """
    模擬真實 subprocess PIPE：若從 *caller thread*（呼叫 start() 的執行緒）直接
    呼叫 __next__，就記錄下來。在測試結束後可斷言 called_from_caller_thread == False。

    真正的 PIPE 在這種情況下會永久阻塞（deadlock）；這個 fake 為了測試不阻塞，
    直接拋出 StopIteration，但仍記錄呼叫來源。
    """

    def __init__(self, caller_thread_ident: int) -> None:
        self._caller_ident = caller_thread_ident
        self.called_from_caller_thread: bool = False
        self.read_started = threading.Event()

    def __iter__(self):
        return self

    def __next__(self) -> str:
        self.read_started.set()
        if threading.current_thread().ident == self._caller_ident:
            self.called_from_caller_thread = True
        raise StopIteration



class FakePopen:
    """記錄每次呼叫的 popen_factory。"""

    def __init__(self, processes: List[FakeProcess]) -> None:
        self._processes = iter(processes)
        self.calls: List[List[str]] = []
        self.kwargs_list: List[dict] = []
        self.call_count = 0

    def __call__(self, args, **kwargs) -> FakeProcess:
        self.calls.append(list(args))
        self.kwargs_list.append(kwargs)
        self.call_count += 1
        proc = next(self._processes)
        proc.args = list(args)
        return proc


class TrackingFakePopen(FakePopen):
    """記錄事件順序的 FakePopen 子類別，用於驗證 spawn 與 cleanup 的相對時序。"""

    def __init__(self, processes: List[FakeProcess], events: List[str]) -> None:
        super().__init__(processes)
        self._events = events

    def __call__(self, args, **kwargs) -> FakeProcess:
        self._events.append(f"spawn_{self.call_count + 1}")
        return super().__call__(args, **kwargs)


def _make_health_urlopen(responses: List[bool]):
    """
    製造假的 urlopen callable。
    True  → 回傳 200 OK（健康）
    False → 拋出 OSError（尚未就緒）
    """
    it = iter(responses)

    def _urlopen(url, timeout=None):
        ok = next(it, False)
        if ok:
            return _FakeHTTPResponse()
        raise OSError("connection refused")

    return _urlopen


class _FakeHTTPResponse:
    status = 200

    def read(self):
        return b'{"status":"ok"}'

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def _port_allocator(port: int):
    """固定回傳指定 port 的 port allocator。"""
    def _alloc() -> int:
        return port
    return _alloc


def _no_sleep(_: float) -> None:
    """測試用空 sleep，不實際等待。"""
    pass


# 測試用注入值：資產檔案最小 bytes（1 byte），避免測試檔需達 GB 小。
# 生產環境預設用 ASSET_MINIMUM_BYTES（正式大小）。
_TEST_MIN: dict[str, int] = {
    "server_path": 1,
    "model_path": 1,
    "projector_path": 1,
}


def _make_runtime(
    assets: VisionAssets,
    *,
    processes: List[FakeProcess] | None = None,
    health: List[bool] | None = None,
    port: int = 43123,
    health_retries: int = 3,
) -> LocalVisionRuntime:
    """便捷工廠，預設一個 RunningProcess + health=[True]；測試用小檔案限制。"""
    procs = processes if processes is not None else [RunningProcess()]
    popen = FakePopen(procs)
    urlopen = _make_health_urlopen(health if health is not None else [True])
    return LocalVisionRuntime(
        assets=assets,
        popen_factory=popen,
        urlopen=urlopen,
        port_allocator=_port_allocator(port),
        sleep=_no_sleep,
        health_retries=health_retries,
        asset_minimum_bytes=_TEST_MIN,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_assets(tmp_path):
    return _make_assets(tmp_path)


# ──────────────────────────────────────────────────────────────────────────────
# 1. 缺少資產 → missing 狀態
# ──────────────────────────────────────────────────────────────────────────────


def test_missing_server_returns_missing_state(tmp_path):
    """llama-server.exe 不存在 → state.name == 'missing'。"""
    assets = _make_assets(tmp_path, create_files=True)
    assets.server_path.unlink()
    runtime = _make_runtime(assets)
    state = runtime.start()
    assert state.name == "missing"
    assert "runtime_missing" in state.detail


def test_missing_model_returns_missing_state(tmp_path):
    """model GGUF 不存在 → state.name == 'missing'。"""
    assets = _make_assets(tmp_path, create_files=True)
    assets.model_path.unlink()
    runtime = _make_runtime(assets)
    state = runtime.start()
    assert state.name == "missing"
    assert "model_missing" in state.detail


def test_missing_projector_returns_missing_state(tmp_path):
    """mmproj GGUF 不存在 → state.name == 'missing'。"""
    assets = _make_assets(tmp_path, create_files=True)
    assets.projector_path.unlink()
    runtime = _make_runtime(assets)
    state = runtime.start()
    assert state.name == "missing"
    assert "projector_missing" in state.detail


# ──────────────────────────────────────────────────────────────────────────────
# 2. 命令列：loopback、動態 port、mmproj、model、ctx
# ──────────────────────────────────────────────────────────────────────────────


def test_start_uses_loopback_dynamic_port_and_mmproj(fake_assets):
    """啟動命令必須包含 loopback host、動態 port 和 --mmproj。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()

    assert state.name == "ready"
    assert state.base_url == "http://127.0.0.1:43123/v1"
    args = popen.calls[0]
    assert args[:4] == [str(fake_assets.server_path), "--host", "127.0.0.1", "--port"]
    assert args[4] == "43123"
    assert "--mmproj" in args
    idx = args.index("--mmproj")
    assert args[idx + 1] == str(fake_assets.projector_path)
    assert "--no-mmproj-offload" not in args
    assert "--no-op-offload" in args
    assert "--no-mmap" not in args
    parallel_idx = args.index("--parallel")
    assert args[parallel_idx + 1] == "1"


def test_default_health_budget_allows_slow_cold_start(fake_assets):
    health = [False] * 100 + [True]
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([RunningProcess()]),
        urlopen=_make_health_urlopen(health),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )

    assert runtime.start().name == "ready"


def test_stop_interrupts_slow_cold_start(fake_assets):
    entered_sleep = threading.Event()
    release_sleep = threading.Event()
    proc = RunningProcess()
    result = {}

    def blocking_sleep(_):
        entered_sleep.set()
        release_sleep.wait(timeout=2)

    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([proc]),
        urlopen=_make_health_urlopen([False] * 480),
        port_allocator=_port_allocator(43123),
        sleep=blocking_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    thread = threading.Thread(
        target=lambda: result.setdefault("state", runtime.start()),
        daemon=True,
    )
    thread.start()
    assert entered_sleep.wait(timeout=1)

    assert runtime.stop().name == "stopped"
    release_sleep.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert result["state"].name == "stopped"
    assert runtime.owned_process is None
    assert proc.terminate_calls == 1


def test_start_reports_monotonic_warmup_progress(fake_assets):
    updates = []
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
        progress_callback=lambda phase, progress: updates.append((phase, progress)),
    )

    state = runtime.start()

    assert state.name == "ready"
    assert updates[:2] == [("checking_assets", 5), ("starting_server", 10)]
    assert updates[-1] == ("ready", 100)

    runtime._last_progress = 10
    runtime._report_line_progress("load_tensors: loading weights")
    runtime._report_line_progress("load_model: initializing, n_slots = 1")
    runtime._report_line_progress("warming up the model")
    assert updates[-3:] == [
        ("loading_tensors", 45),
        ("initializing", 70),
        ("warming_up", 85),
    ]


def test_start_command_includes_model_path(fake_assets):
    """命令列必須含有 -m <model_path>。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    args = popen.calls[0]
    assert "-m" in args
    idx = args.index("-m")
    assert args[idx + 1] == str(fake_assets.model_path)


def test_start_command_includes_context_size(fake_assets):
    """命令列必須含有 -c 4096。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    args = popen.calls[0]
    assert "-c" in args
    idx = args.index("-c")
    assert args[idx + 1] == "4096"


def test_managed_model_hash_mismatch_blocks_start(fake_assets, monkeypatch):
    """受管模型即使大小正確，hash 不符也不得啟動 runtime。"""
    monkeypatch.setitem(runtime_module.ASSET_SHA256, "model_path", "0" * 64)
    monkeypatch.setitem(
        runtime_module.ASSET_SHA256,
        "projector_path",
        hashlib.sha256(fake_assets.projector_path.read_bytes()).hexdigest(),
    )
    managed_assets = VisionAssets(
        server_path=fake_assets.server_path,
        model_path=fake_assets.model_path,
        projector_path=fake_assets.projector_path,
        managed=True,
    )
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=managed_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )

    state = runtime.start()

    assert state.name == "missing"
    assert "asset_sha256_mismatch" in state.detail
    assert fake_assets.model_path.name in state.detail
    assert popen.call_count == 0

def test_start_gpu_mode_uses_ngl_999(fake_assets):
    """首次 GPU 啟動必須使用 -ngl 999。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.mode == "gpu"
    args = popen.calls[0]
    assert "-ngl" in args
    idx = args.index("-ngl")
    assert args[idx + 1] == "999"


def test_start_gpu_mode_accepts_ngl_override(fake_assets):
    """GPU smoke test 可指定部分 offload 的 layer 數量。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        gpu_layers=20,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()

    assert state.mode == "gpu"
    args = popen.calls[0]
    idx = args.index("-ngl")
    assert args[idx + 1] == "20"


def test_gpu_offload_parser_accepts_prefixed_case_insensitive_llama_cpp_marker():
    assert runtime_module._parse_gpu_offload_layers(
        'llama_model_load: Offloaded 40/43 layers to GPU\n'
    ) == (40, 43)


def test_gpu_offload_parser_reports_zero_or_missing_marker_as_unconfirmed():
    assert runtime_module._parse_gpu_offload_layers('offloaded 0/43 layers to GPU') == (0, 43)
    assert runtime_module._parse_gpu_offload_layers('health endpoint is ready') == (0, 0)


def test_gpu_health_ready_captures_llama_cpp_offload_evidence(fake_assets):
    proc = FakeProcess(
        returncode=None,
        stderr_lines=['prefix: offloaded 12/43 layers to GPU\n'],
    )
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([proc]),
        urlopen=_make_health_urlopen([False, True]),
        port_allocator=_port_allocator(43123),
        sleep=lambda _: threading.Event().wait(0.01),
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )

    state = runtime.start()

    assert state.name == 'ready'
    assert state.mode == 'gpu'
    assert state.gpu_offload_layers == 12
    assert state.gpu_total_layers == 43
    assert state.gpu_backend_confirmed is True


def test_gpu_health_ready_accepts_owned_process_probe_without_offload_marker(fake_assets):
    proc = RunningProcess()
    proc.pid = 4242
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([proc]),
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        health_retries=1,
        asset_minimum_bytes=_TEST_MIN,
        gpu_process_probe=lambda pid: pid == 4242,
    )

    state = runtime.start()

    assert state.name == "ready"
    assert state.mode == "gpu"
    assert state.gpu_offload_layers == 0
    assert state.gpu_process_confirmed is True
    assert state.gpu_backend_confirmed is True

def test_gpu_offload_evidence_survives_more_than_256_later_stderr_lines(fake_assets):
    marker = "load: offloaded 12/43 layers to GPU\n"
    noise = [f"noise-{index:04d}\n" for index in range(300)]
    proc = FakeProcess(returncode=None, stderr_lines=[marker, *noise])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([proc]),
        urlopen=_make_health_urlopen([False, True]),
        port_allocator=_port_allocator(43123),
        sleep=lambda _: threading.Event().wait(0.01),
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )

    state = runtime.start()

    assert state.gpu_offload_layers == 12
    assert state.gpu_total_layers == 43
    assert state.gpu_backend_confirmed is True
    assert state.detail == ""
    retained_runtime_state = {
        key: value for key, value in vars(runtime).items() if key != "_process"
    }
    assert marker.strip() not in repr(retained_runtime_state)
    assert noise[-1].strip() not in repr(retained_runtime_state)

def test_zero_gpu_layers_reports_cpu_mode(fake_assets):
    """-ngl 0 不得被標記成 GPU。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        gpu_layers=0,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()

    assert state.name == "ready"
    assert state.mode == "cpu"


# ──────────────────────────────────────────────────────────────────────────────
# 3. Windows 隱藏視窗 flag
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_process_uses_create_no_window(fake_assets):
    """Windows 平台必須設定 CREATE_NO_WINDOW。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    kwargs = popen.kwargs_list[0]
    assert kwargs.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW != 0


def test_process_uses_devnull_stdout_and_pipe_stderr(fake_assets):
    """stdout 必須是 DEVNULL，stderr 必須是 PIPE。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    kwargs = popen.kwargs_list[0]
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.PIPE


# ──────────────────────────────────────────────────────────────────────────────
# 4. 健康檢查：ready / timeout / early exit
# ──────────────────────────────────────────────────────────────────────────────


def test_health_check_returns_ready_on_first_success(fake_assets):
    """健康端點第一次成功 → state.name == 'ready'。"""
    runtime = _make_runtime(fake_assets, health=[True])
    state = runtime.start()
    assert state.name == "ready"


def test_health_check_retries_until_ready(fake_assets):
    """健康端點前兩次失敗第三次成功 → still ready。"""
    runtime = _make_runtime(fake_assets, health=[False, False, True], health_retries=5)
    state = runtime.start()
    assert state.name == "ready"


def test_health_timeout_respects_total_deadline(fake_assets):
    """HTTP timeout 不能讓總暖身時間超過 health_retries 的預算。"""
    observed_timeouts = []
    clock = {"now": 0.0}

    def monotonic():
        return clock["now"]

    def timed_urlopen(_url, timeout=None):
        observed_timeouts.append(timeout)
        clock["now"] += float(timeout or 0.0)
        raise OSError("connection refused")

    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([RunningProcess()]),
        urlopen=timed_urlopen,
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        monotonic=monotonic,
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )

    state = runtime.start()

    assert state.name == "failed"
    assert observed_timeouts == [pytest.approx(1.5)]

def test_health_timeout_returns_failed(fake_assets):
    """所有健康檢查嘗試均失敗 → state.name == 'failed'，detail 含 'health_timeout'。"""
    runtime = _make_runtime(fake_assets, health=[False, False, False], health_retries=3)
    state = runtime.start()
    assert state.name == "failed"
    assert "health_timeout" in state.detail


def test_process_early_exit_returns_failed(fake_assets):
    """process 在健康輪詢前提早退出 → state.name == 'failed'，detail 含 'process_exited'。"""
    runtime = _make_runtime(
        fake_assets,
        processes=[ExitedProcess("fatal error")],
        health=[False],
        health_retries=3,
    )
    state = runtime.start()
    assert state.name == "failed"
    assert "process_exited" in state.detail


# ──────────────────────────────────────────────────────────────────────────────
# 5. Start idempotency
# ──────────────────────────────────────────────────────────────────────────────


def test_start_is_idempotent_while_ready(fake_assets):
    """已 ready 時再次呼叫 start() 應回傳同一 base_url，且只 spawn 一次 process。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    first = runtime.start()
    second = runtime.start()
    assert first.base_url == second.base_url
    assert popen.call_count == 1


def test_start_is_idempotent_while_starting(fake_assets):
    """已有 starting snapshot 時，start() 不得重新配置 port 或 spawn。"""
    popen = FakePopen([])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([]),
        port_allocator=lambda: pytest.fail("starting state must not allocate a port"),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    starting = VisionRuntimeState(
        name="starting", detail="loading", base_url="", mode="gpu"
    )
    runtime._state = starting

    returned = runtime.start()

    assert returned is starting
    assert popen.call_count == 0


# ──────────────────────────────────────────────────────────────────────────────
# 6. CUDA/VRAM 失敗 → 只重試一次 CPU mode
# ──────────────────────────────────────────────────────────────────────────────


def test_common_cuda_initialization_errors_trigger_cpu_fallback(fake_assets):
    """常見 CUDA 初始化錯誤也必須進入單次 CPU fallback。"""
    cuda_proc = ExitedProcess("no CUDA-capable device is available")
    cpu_proc = RunningProcess()
    popen = FakePopen([cuda_proc, cpu_proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.name == "ready"
    assert state.mode == "cpu"
    assert popen.call_count == 2

def test_cuda_start_failure_retries_once_in_cpu_mode(fake_assets):
    """
    GPU 嘗試 stderr 含 CUDA 錯誤 → 只重試一次（CPU mode）。
    第二次成功 → state.name == 'ready'，state.mode == 'cpu'。
    """
    cuda_proc = ExitedProcess("CUDA out of memory")
    cpu_proc = RunningProcess()
    popen = FakePopen([cuda_proc, cpu_proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.name == "ready"
    assert state.mode == "cpu"
    assert popen.call_count == 2


def test_cpu_retry_uses_ngl_0(fake_assets):
    """CPU fallback 的命令列必須使用 -ngl 0。"""
    cuda_proc = ExitedProcess("CUDA error: out of memory")
    cpu_proc = RunningProcess()
    popen = FakePopen([cuda_proc, cpu_proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    # 第二次呼叫（CPU retry）
    assert popen.call_count == 2
    cpu_args = popen.calls[1]
    assert "-ngl" in cpu_args
    idx = cpu_args.index("-ngl")
    assert cpu_args[idx + 1] == "0"


def test_cuda_failure_then_cpu_also_fails_returns_failed(fake_assets):
    """GPU 失敗 → CPU 重試 → CPU 也失敗（health timeout） → state.name == 'failed'，不再重試。"""
    cuda_proc = ExitedProcess("CUDA out of memory")
    cpu_proc = RunningProcess()
    popen = FakePopen([cuda_proc, cpu_proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([False, False, False]),  # CPU health 也逾時
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.name == "failed"
    assert popen.call_count == 2  # GPU + CPU，不再第三次


# ──────────────────────────────────────────────────────────────────────────────
# 7. stop：terminate → kill only owned process
# ──────────────────────────────────────────────────────────────────────────────


def test_stop_terminates_only_owned_process(fake_assets):
    """stop() 必須呼叫 terminate()，且 terminate_calls == 1。"""
    proc = RunningProcess()
    popen = FakePopen([proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    owned = runtime.owned_process
    state = runtime.stop()
    assert state.name == "stopped"
    assert owned.terminate_calls == 1


def test_stop_kills_owned_process_when_terminate_times_out(fake_assets):
    """terminate() 逾時時，stop() 必須 kill 自己持有的 process。"""

    class UncooperativeProcess(RunningProcess):
        def wait(self, timeout=None):
            self.wait_calls += 1
            raise subprocess.TimeoutExpired(cmd="llama-server", timeout=timeout)

    proc = UncooperativeProcess()
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([proc]),
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()

    state = runtime.stop()

    assert state.name == "stopped"
    assert proc.terminate_calls == 1
    assert proc.wait_calls == 1
    assert proc.kill_calls == 1
    assert runtime.owned_process is None


def test_stop_without_start_returns_stopped(fake_assets):
    """未 start 就 stop() → 直接回傳 stopped，不拋出例外。"""
    runtime = _make_runtime(fake_assets)
    state = runtime.stop()
    assert state.name == "stopped"


def test_stop_does_not_affect_external_processes(fake_assets):
    """stop() 只操作自己的 process handle，不影響其他 process（不做名稱掃殺）。"""
    other_proc = RunningProcess()
    owned_proc = RunningProcess()
    popen = FakePopen([owned_proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    runtime.stop()
    # 外部 process 不應被觸碰
    assert other_proc.terminate_calls == 0
    assert other_proc.kill_calls == 0


def test_stop_returns_stopped_state(fake_assets):
    """stop() 回傳 VisionRuntimeState，name == 'stopped'。"""
    runtime = _make_runtime(fake_assets, health=[True])
    runtime.start()
    state = runtime.stop()
    assert isinstance(state, VisionRuntimeState)
    assert state.name == "stopped"


# ──────────────────────────────────────────────────────────────────────────────
# 8. stderr 截斷至 2000 字元
# ──────────────────────────────────────────────────────────────────────────────


def test_stderr_truncated_to_2000_chars_in_detail(fake_assets):
    """process 提早退出時，detail 中的 stderr 最多保留 2000 字元。"""
    long_stderr = "x" * 5000
    proc = ExitedProcess(long_stderr)
    popen = FakePopen([proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([False]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        health_retries=1,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.name == "failed"
    assert len(state.detail) <= 2000 + len("process_exited: ")  # 允許 detail 含 code 前綴


# ──────────────────────────────────────────────────────────────────────────────
# 9. VisionRuntimeState 基本結構
# ──────────────────────────────────────────────────────────────────────────────


def test_runtime_state_is_dataclass():
    """VisionRuntimeState 應為 dataclass，含 name/detail/base_url/mode 欄位。"""
    state = VisionRuntimeState(name="ready", detail="", base_url="http://127.0.0.1:43123/v1", mode="gpu")
    assert state.name == "ready"
    assert state.base_url == "http://127.0.0.1:43123/v1"
    assert state.mode == "gpu"


def test_runtime_state_new_evidence_fields_have_backward_compatible_defaults():
    state = VisionRuntimeState(name='ready', detail='', base_url='http://x', mode='gpu')

    assert state.gpu_offload_layers == 0
    assert state.gpu_total_layers == 0
    assert state.gpu_backend_confirmed is False

def test_ready_state_has_non_empty_base_url(fake_assets):
    """ready 狀態的 base_url 必須非空。"""
    runtime = _make_runtime(fake_assets, health=[True])
    state = runtime.start()
    assert state.name == "ready"
    assert state.base_url.startswith("http://127.0.0.1:")


# ──────────────────────────────────────────────────────────────────────────────
# [FIX] 10. Health loop 不可從 caller thread 直接 next(proc.stderr)
# ──────────────────────────────────────────────────────────────────────────────


def test_health_loop_does_not_block_on_stderr(fake_assets):
    """
    健康輪詢主迴圈絕對不能直接 next(proc.stderr)。
    真實 PIPE 在此情況下會永久阻塞（deadlock）。
    正確實作應透過 daemon reader thread 消化 stderr。

    RED 條件：目前實作在 _wait_healthy 的迴圈內呼叫 next(proc.stderr)，
              BlockingStderr 會記錄 called_from_caller_thread=True → 斷言失敗。
    """
    blocking = BlockingStderr(threading.current_thread().ident)
    proc = RunningProcess(stderr_obj=blocking)
    popen = FakePopen([proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.name == "ready"
    assert blocking.read_started.wait(timeout=1), "stderr reader thread never consumed the pipe"
    assert not blocking.called_from_caller_thread, (
        "Health loop called next(proc.stderr) from caller thread — "
        "this deadlocks on a real subprocess PIPE"
    )


# ──────────────────────────────────────────────────────────────────────────────
# [FIX] 11. VisionRuntimeState 必須 frozen=True
# ──────────────────────────────────────────────────────────────────────────────


def test_vision_runtime_state_is_frozen():
    """
    VisionRuntimeState 必須是 frozen dataclass；欄位不可被修改。

    RED 條件：目前實作缺少 frozen=True，賦值不會拋出例外。
    """
    state = VisionRuntimeState(name="ready", detail="", base_url="http://x", mode="gpu")
    with pytest.raises((AttributeError, TypeError)):
        state.name = "stopped"  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────────────
# [FIX] 12. GPU process 必須在 CPU spawn 前完成清理
# ──────────────────────────────────────────────────────────────────────────────


def test_gpu_process_cleaned_up_before_cpu_spawn(fake_assets):
    """
    CUDA 失敗後，必須先 terminate GPU process，才能 spawn CPU process。
    順序錯誤 → 舊 process 殘留，佔用 port 與 VRAM。

    RED 條件：目前 _try_spawn 失敗後直接 return，未 cleanup，
              events 中 'gpu_terminate' 在 'spawn_2' 之後（或不存在）。
    """
    events: List[str] = []

    class TrackingExited(ExitedProcess):
        def terminate(self):
            events.append("gpu_terminate")
            super().terminate()

        def wait(self, timeout=None):
            events.append("gpu_wait")
            return super().wait(timeout=timeout)

    gpu_proc = TrackingExited("CUDA out of memory")
    cpu_proc = RunningProcess()
    popen = TrackingFakePopen([gpu_proc, cpu_proc], events)
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.name == "ready"
    assert state.mode == "cpu"
    assert popen.call_count == 2
    assert "gpu_terminate" in events, f"GPU process was never terminated. Events: {events}"
    assert "spawn_2" in events
    gpu_t_idx = events.index("gpu_terminate")
    spawn2_idx = events.index("spawn_2")
    assert gpu_t_idx < spawn2_idx, (
        f"GPU terminate must precede CPU spawn. Events: {events}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# [FIX] 13. Health timeout 後不殘留 process
# ──────────────────────────────────────────────────────────────────────────────


def test_health_timeout_no_residual_process(fake_assets):
    """
    health_timeout 後，process 必須被 terminate；owned_process 必須為 None。

    RED 條件：目前 _wait_healthy timeout 後只 return failed，未 cleanup，
              proc.terminate_calls == 0，owned_process 仍持有 handle。
    """
    proc = RunningProcess()
    popen = FakePopen([proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([False, False, False]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.name == "failed"
    assert "health_timeout" in state.detail
    assert proc.terminate_calls >= 1, "health_timeout 後 process 必須被 terminate"
    assert runtime.owned_process is None, "health_timeout 後 owned_process 必須為 None"


# ──────────────────────────────────────────────────────────────────────────────
# [FIX] 14. 健康端點 response 必須被 close
# ──────────────────────────────────────────────────────────────────────────────


def test_health_response_is_closed(fake_assets):
    """
    urlopen 回傳的 response 必須在讀取後呼叫 close()（或以 context manager 使用）。
    否則在真實環境會洩漏 socket file descriptor。

    RED 條件：目前實作直接接受 urlopen 回傳值而不 close。
    """
    close_calls: List[bool] = []

    class TrackingResponse:
        status = 200

        def close(self):
            close_calls.append(True)

        def read(self):
            return b'{"status":"ok"}'

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    def tracking_urlopen(url, timeout=None):
        return TrackingResponse()

    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([RunningProcess()]),
        urlopen=tracking_urlopen,
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    assert len(close_calls) >= 1, "urlopen response 必須被 close（socket fd 洩漏）"


# ──────────────────────────────────────────────────────────────────────────────
# [FINAL FIX] 15. ASSET_MINIMUM_BYTES 可 import、_check_assets 驗證大小
# ──────────────────────────────────────────────────────────────────────────────


def test_check_assets_uses_verify_asset_for_size(tmp_path):
    """
    _check_assets 對存在但過小的檔案必須回傳 asset_too_small detail，
    而非 missing 狀態。

    RED 條件：目前 _check_assets 只用 path.exists()，不驗證大小，
              檢查過小檔案會返回空字串而非 asset_too_small。
    """
    assets = _make_assets(tmp_path)
    # server 小於 minimum（min=1000, actual=1 byte）
    assets.server_path.write_bytes(b"x")
    runtime = LocalVisionRuntime(
        assets=assets,
        popen_factory=FakePopen([RunningProcess()]),
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes={"server_path": 1000, "model_path": 1, "projector_path": 1},
    )
    state = runtime.start()
    assert state.name == "missing"
    assert "asset_too_small" in state.detail


# ──────────────────────────────────────────────────────────────────────────────
# [FINAL FIX] 16. port_allocator 失敗 → failed + port_unavailable
# ──────────────────────────────────────────────────────────────────────────────


def test_port_allocator_failure_returns_port_unavailable(fake_assets):
    """
    port_allocator 拋出例外時，start() 必須回傳 VisionRuntimeState，
    name='failed'，detail 以 'port_unavailable' 開頭，不可向上拋出。

    RED 條件：目前 start() 直接呼叫 port_allocator()，不有 try/except，
              例外會向上傳播而非回傳 failed state。
    """
    def failing_port() -> int:
        raise OSError("address already in use")

    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=FakePopen([]),
        urlopen=_make_health_urlopen([]),
        port_allocator=failing_port,
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )
    state = runtime.start()
    assert state.name == "failed"
    assert state.detail.startswith("port_unavailable"), (
        f"Expected detail starting with 'port_unavailable', got: {state.detail!r}"
    )

def test_gpu_health_timeout_does_not_double_wait_in_cpu_mode(fake_assets):
    """A generic loading timeout must fail once instead of repeating the full wait on CPU."""
    gpu_proc = FakeProcess(stderr_lines=["load_model: loading model"])
    popen = FakePopen([gpu_proc])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([False, False, False]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        health_retries=3,
        asset_minimum_bytes=_TEST_MIN,
    )

    state = runtime.start()

    assert state.name == "failed"
    assert state.mode == "gpu"
    assert "health_timeout" in state.detail
    assert popen.call_count == 1

def test_start_command_accepts_context_size_override(fake_assets):
    """診斷 smoke 可覆寫 context size，但正式預設仍由既有測試固定為 4096。"""
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=fake_assets,
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        context_size=2048,
        asset_minimum_bytes=_TEST_MIN,
    )
    runtime.start()
    args = popen.calls[0]
    idx = args.index("-c")
    assert args[idx + 1] == "2048"

def test_text_profile_omits_mmproj_and_allows_missing_projector(tmp_path):
    assets = _make_assets(tmp_path, create_files=True)
    assets.projector_path.unlink()
    popen = FakePopen([RunningProcess()])
    runtime = LocalVisionRuntime(
        assets=assets,
        profile="text",
        popen_factory=popen,
        urlopen=_make_health_urlopen([True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )

    state = runtime.start()

    assert state.name == "ready"
    assert "--mmproj" not in popen.calls[0]

def test_profile_switch_stops_old_process_before_starting_new_mode(tmp_path):
    assets = _make_assets(tmp_path, create_files=True)
    first = RunningProcess()
    second = RunningProcess()
    popen = FakePopen([first, second])
    runtime = LocalVisionRuntime(
        assets=assets,
        profile="text",
        popen_factory=popen,
        urlopen=_make_health_urlopen([True, True]),
        port_allocator=_port_allocator(43123),
        sleep=_no_sleep,
        asset_minimum_bytes=_TEST_MIN,
    )

    assert runtime.start().name == "ready"
    assert runtime.start(profile="vision").name == "ready"

    assert first.terminate_calls == 1
    assert popen.call_count == 2
    assert "--mmproj" not in popen.calls[0]
    assert "--mmproj" in popen.calls[1]
