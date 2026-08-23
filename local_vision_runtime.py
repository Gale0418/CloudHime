"""
local_vision_runtime.py
------------------------
Task 2：LocalVisionRuntime 生命週期管理。

職責（唯一）：
- 驗證 VisionAssets 三個檔案存在。
- 配置 OS loopback port。
- 以隱藏視窗啟動 llama-server.exe（Windows CREATE_NO_WINDOW）。
- 輪詢健康端點，發出 missing / starting / ready / failed / stopped 狀態。
- GPU 明確回報 CUDA/VRAM 錯誤時只允許單次 CPU fallback（-ngl 0）。
- 截斷 stderr 到最多 2000 字元供 UI 顯示。
- stop() 只回收本 instance 持有的 process handle，不依名稱掃殺。

# FIX 清單（Task 2 修正輪）：
# [FIX-1] stderr 以 daemon thread 非阻塞讀取，health loop 不直接 next(proc.stderr)。
# [FIX-2] VisionRuntimeState 改為 frozen=True。
# [FIX-3] _try_spawn 失敗後 cleanup 該次 process，再允許 CPU retry 或 return failed。
# [FIX-4] health urlopen response 以 try/finally 確保 close()。

所有 I/O（subprocess、HTTP、port、sleep）以 constructor injection 傳入，
使測試可完全以 fake 取代，不啟動任何真實模型。
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import deque
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from local_vision_assets import (
    ASSET_MINIMUM_BYTES,
    ASSET_SHA256,
    VisionAssetError,
    VisionAssets,
    verify_asset,
)
from local_runtime_profiles import (
    LocalRuntimeProfile,
    VISION_RUNTIME_PROFILE,
    resolve_runtime_profile,
)


# ──────────────────────────────────────────────────────────────────────────────
# 常數
# ──────────────────────────────────────────────────────────────────────────────

_HEALTH_SLEEP_SEC = 0.5          # 每次健康輪詢的間隔（測試注入 no-op sleep）
_DEFAULT_HEALTH_RETRIES = 480    # 240 秒，容納慢速磁碟的模型冷讀取
_STDERR_MAX_CHARS = 2_000        # stderr detail 截斷上限
_CLEANUP_WAIT_TIMEOUT = 5.0      # _cleanup_process 等待 process 結束的秒數
_STDERR_JOIN_TIMEOUT = 1.0       # 等待 daemon stderr 讀取完成的秒數

_PROGRESS_MARKERS = (
    ("load_model: loading model", "loading_model", 20),
    ("load_tensors", "loading_tensors", 45),
    ("load_model: initializing", "initializing", 70),
    ("warming up", "warming_up", 85),
    ("model loaded", "model_loaded", 95),
)

# CUDA/VRAM 錯誤關鍵字（小寫比對）
_CUDA_ERROR_KEYWORDS = (
    "cuda out of memory",
    "cuda error",
    "out of memory",
    "vram",
    "failed to load model",
    "ggml_cuda_init",
    "gpu initialization failed",
    "no cuda-capable device",
    "cuda driver version is insufficient",
    "failed to initialize cuda",
    "could not initialize cuda",
    "cuda initialization failed",
    "cuda unavailable",
)



def _cancel_requested(cancel_event) -> bool:
    """以 fail-closed 方式讀取外部取消訊號，避免取消物件異常時啟動模型。"""
    if cancel_event is None:
        return False
    checker = getattr(cancel_event, "is_set", None)
    if not callable(checker):
        return True
    try:
        return bool(checker())
    except Exception:
        return True

# ──────────────────────────────────────────────────────────────────────────────
# 狀態資料類別 [FIX-2] frozen=True
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VisionRuntimeState:
    """RuntimeState 傳遞給 UI 的不可變快照。

    Attributes
    ----------
    name:   ``stopped`` | ``missing`` | ``starting`` | ``ready`` | ``failed``
    detail: 人類可讀的錯誤代碼或 stderr 截段（不含大段日誌）。
    base_url: ready 時為 ``http://127.0.0.1:<port>/v1``，其他時候為 ``""``。
    mode:   ``"gpu"`` | ``"cpu"`` | ``""``
    """

    name: str
    detail: str
    base_url: str
    mode: str
    gpu_offload_layers: int = 0
    gpu_total_layers: int = 0
    gpu_backend_confirmed: bool = False
    gpu_process_confirmed: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# 預置狀態
# ──────────────────────────────────────────────────────────────────────────────

_STOPPED = VisionRuntimeState(name="stopped", detail="", base_url="", mode="")


# ──────────────────────────────────────────────────────────────────────────────
# LocalVisionRuntime
# ──────────────────────────────────────────────────────────────────────────────


class LocalVisionRuntime:
    """管理 llama-server.exe 子程序的生命週期。

    Parameters
    ----------
    assets:
        由 ``resolve_vision_assets()`` 產生的資產路徑容器。
    popen_factory:
        簽名相容 ``subprocess.Popen`` 的 callable，用於依賴注入。
    urlopen:
        簽名相容 ``urllib.request.urlopen`` 的 callable（健康檢查用）。
    gpu_process_probe:
        回報指定 process PID 是否被 NVIDIA driver 列為 GPU process；測試可注入。
    port_allocator:
        無參數 callable，回傳可用的整數 port。
    sleep:
        簽名相容 ``time.sleep`` 的 callable，用於健康輪詢間隔。
    health_retries:
        健康輪詢最大次數（預設 480 次，每次間隔 0.5s → 約 240 秒）。
    """

    def __init__(
        self,
        assets: VisionAssets,
        *,
        profile: LocalRuntimeProfile | str = VISION_RUNTIME_PROFILE,
        popen_factory: Callable = subprocess.Popen,
        urlopen: Optional[Callable] = None,
        port_allocator: Optional[Callable[[], int]] = None,
        sleep: Optional[Callable[[float], None]] = None,
        monotonic: Optional[Callable[[], float]] = None,
        health_retries: int = _DEFAULT_HEALTH_RETRIES,
        context_size: int = 4096,
        gpu_layers: int = 999,
        asset_minimum_bytes: dict[str, int] | None = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        gpu_process_probe: Optional[Callable[[int], bool]] = None,
    ) -> None:
        self._assets = assets
        self._profile = resolve_runtime_profile(profile)
        self._popen_factory = popen_factory
        self._urlopen = urlopen or _default_urlopen()
        self._port_allocator = port_allocator or _default_port_allocator()
        self._sleep = sleep or time.sleep
        self._monotonic = monotonic or time.monotonic
        self._health_retries = health_retries
        self._context_size = max(512, int(context_size))
        self._gpu_layers = max(0, int(gpu_layers))
        self._progress_callback = progress_callback
        self._gpu_process_probe = gpu_process_probe or _default_gpu_process_probe
        self._last_progress = 0
        # 可注入資產大小最小值（測試用小數值，生產用正式大小）
        self._asset_minimum_bytes: dict[str, int] = (
            asset_minimum_bytes if asset_minimum_bytes is not None else ASSET_MINIMUM_BYTES
        )

        self._state: VisionRuntimeState = _STOPPED
        self._process = None   # FakeProcess or Popen；有啟動程序時非 None
        self._port: Optional[int] = None
        self._start_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._cancel_event = threading.Event()

    # ── 公開介面 ──────────────────────────────────────────────────────────────

    @property
    def owned_process(self):
        """回傳本 instance 建立的 process handle（供測試驗證）。"""
        return self._process

    @property
    def profile_name(self) -> str:
        return self._profile.name

    def set_profile(self, profile: LocalRuntimeProfile | str) -> None:
        """設定下一次啟動的 text/vision profile；執行中必須先 stop。"""
        resolved = resolve_runtime_profile(profile)
        with self._start_lock:
            if self._state.name in ("ready", "starting"):
                raise RuntimeError("runtime_profile_requires_stop")
            self._profile = resolved

    def start(
        self,
        profile: LocalRuntimeProfile | str | None = None,
        *,
        cancel_event=None,
    ) -> VisionRuntimeState:
        """啟動 vision runtime（idempotent：已 ready/starting 時直接回傳現有狀態）。

        狀態機：stopped → missing | starting → ready | failed
        """
        with self._start_lock:
            if _cancel_requested(cancel_event):
                self._stop_owned_process()
                return _STOPPED
            requested_profile = (
                resolve_runtime_profile(profile)
                if profile is not None
                else self._profile
            )
            if self._state.name in ("ready", "starting"):
                if requested_profile.name == self._profile.name:
                    return self._state
                self._stop_owned_process()
            self._profile = requested_profile
            self._cancel_event.clear()
            self._state = VisionRuntimeState(name="starting", detail="", base_url="", mode="")

            self._last_progress = 0
            self._report_progress("checking_assets", 5)

            # 1. 資產驗證
            if _cancel_requested(cancel_event):
                self._stop_owned_process()
                return _STOPPED
            missing_detail = self._check_assets()
            if missing_detail:
                self._state = VisionRuntimeState(
                    name="missing", detail=missing_detail, base_url="", mode=""
                )
                return self._state

            # 2. Port 分配：port_allocator 失敗則回傳 failed，不揋出
            try:
                port = self._port_allocator()
            except Exception as exc:
                self._state = VisionRuntimeState(
                    name="failed",
                    detail=f"port_unavailable: {exc}",
                    base_url="",
                    mode="",
                )
                return self._state
            self._port = port
            if _cancel_requested(cancel_event):
                self._stop_owned_process()
                return _STOPPED
            self._report_progress("starting_server", 10)
            initial_mode = "gpu" if self._gpu_layers > 0 else "cpu"
            state = self._try_spawn(
                port,
                gpu_layers=self._gpu_layers,
                mode=initial_mode,
                cancel_event=cancel_event,
            )
            if (
                self._cancel_event.is_set()
                or _cancel_requested(cancel_event)
                or state.name == "stopped"
            ):
                self._stop_owned_process()
                return self._state
            if state.name == "ready":
                with self._state_lock:
                    cancelled = self._cancel_event.is_set() or _cancel_requested(cancel_event)
                    if not cancelled:
                        self._state = state
                        return self._state
                self._stop_owned_process()
                return self._state

            # 3. GPU 啟動失敗時才允許單次 CPU fallback。
            # [FIX-3] GPU proc 已在 _try_spawn 內 cleanup，此處直接 spawn CPU
            if initial_mode == "gpu" and _is_cuda_error(state.detail):
                cpu_state = self._try_spawn(
                    port,
                    gpu_layers=0,
                    mode="cpu",
                    cancel_event=cancel_event,
                )
                with self._state_lock:
                    cancelled = self._cancel_event.is_set() or _cancel_requested(cancel_event)
                    if not cancelled:
                        self._state = cpu_state
                        return self._state
                self._stop_owned_process()
                return self._state

            with self._state_lock:
                cancelled = self._cancel_event.is_set() or _cancel_requested(cancel_event)
                if not cancelled:
                    self._state = state
                    return self._state
            self._stop_owned_process()
            return self._state

    def set_gpu_layers(self, gpu_layers: int) -> None:
        """設定下一次啟動使用的 GPU layer 數；不會自行啟動或停止 process。"""
        self._gpu_layers = max(0, int(gpu_layers))

    def stop(self) -> VisionRuntimeState:
        """終止本 instance 持有的 process；不影響任何其他程序。"""
        self._stop_owned_process()
        return self._state

    def _stop_owned_process(self) -> None:
        with self._state_lock:
            self._cancel_event.set()
            proc = self._process
            self._process = None
            self._state = _STOPPED
        if proc is not None:
            self._cleanup_process(proc)

    # ── 內部：spawn 單次嘗試 ─────────────────────────────────────────────────

    def _try_spawn(
        self,
        port: int,
        *,
        gpu_layers: int,
        mode: str,
        cancel_event=None,
    ) -> VisionRuntimeState:
        """建立一個 process 並等待健康檢查。

        [FIX-3] 若健康檢查失敗，在回傳前 terminate/wait/kill 該 process，
        確保不殘留任何廢棄 handle。
        """
        if self._cancel_event.is_set() or _cancel_requested(cancel_event):
            return _STOPPED
        assets = self._assets
        args = [
            str(assets.server_path),
            "--host", "127.0.0.1",
            "--port", str(port),
            "--no-webui",
            "-m", str(assets.model_path),
        ]
        if self._profile.requires_projector:
            args.extend(["--mmproj", str(assets.projector_path)])
        args.extend([
            # Keep OS memory mapping enabled; disabling it can stall large Gemma 3 projector loads on Windows.
            # Keep model layers on GPU but avoid WDDM operator offload stalls under VRAM pressure.
            "--no-op-offload",
            # CloudHime serializes translations, so extra server slots only waste KV memory.
            "--parallel", "1",
            "-c", str(self._context_size),
            "-ngl", str(gpu_layers),
        ])
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        try:
            proc = self._popen_factory(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except Exception as exc:
            return VisionRuntimeState(
                name="failed",
                detail=f"process_start_failed: {exc}"[:_STDERR_MAX_CHARS],
                base_url="",
                mode=mode,
            )

        self._process = proc
        if self._cancel_event.is_set() or _cancel_requested(cancel_event):
            self._cleanup_process(proc)
            self._process = None
            return _STOPPED
        state = self._wait_healthy(proc, port, mode, cancel_event=cancel_event)

        # [FIX-3] 失敗時清理 process，確保不殘留
        if state.name != "ready" and self._process is proc:
            self._cleanup_process(proc)
            self._process = None

        return state

    # ── 內部：健康輪詢 ────────────────────────────────────────────────────────

    def _wait_healthy(self, proc, port: int, mode: str, *, cancel_event=None) -> VisionRuntimeState:
        """輪詢 /health 端點；process 提早退出則立即 failed。

        [FIX-1] stderr 由 daemon thread 消化，health loop 絕不在 caller thread
        呼叫 next(proc.stderr)，避免真實 PIPE 的永久阻塞（deadlock）。
        [FIX-4] urlopen response 以 try/finally 確保 close()。
        """
        health_url = f"http://127.0.0.1:{port}/health"
        stderr_lines = deque(maxlen=256)
        stderr_lock = threading.Lock()
        gpu_offload_layers = 0
        gpu_total_layers = 0

        def _snapshot_stderr() -> str:
            with stderr_lock:
                return "".join(stderr_lines)[:_STDERR_MAX_CHARS]

        def _snapshot_gpu_offload() -> tuple[int, int]:
            with stderr_lock:
                return gpu_offload_layers, gpu_total_layers

        # [FIX-1] daemon thread：非阻塞消化 stderr
        def _drain() -> None:
            nonlocal gpu_offload_layers, gpu_total_layers
            try:
                for line in proc.stderr:  # type: ignore[union-attr]
                    gpu_offload = _find_gpu_offload_layers(line)
                    with stderr_lock:
                        stderr_lines.append(line)
                        if gpu_offload is not None:
                            gpu_offload_layers, gpu_total_layers = gpu_offload
                    self._report_line_progress(line)
            except Exception:
                pass

        drain_thread = threading.Thread(target=_drain, daemon=True)
        drain_thread.start()

        deadline = self._monotonic() + (self._health_retries * _HEALTH_SLEEP_SEC)
        for _ in range(self._health_retries):
            if self._cancel_event.is_set() or _cancel_requested(cancel_event):
                return _STOPPED

            remaining = deadline - self._monotonic()
            if remaining <= 0:
                break

            # 先確認 process 是否提早退出
            if proc.poll() is not None:
                drain_thread.join(timeout=_STDERR_JOIN_TIMEOUT)
                stderr_text = _snapshot_stderr()
                return VisionRuntimeState(
                    name="failed",
                    detail=f"process_exited: {stderr_text}",
                    base_url="",
                    mode=mode,
                )

            # 將 HTTP timeout 限制在總暖身 deadline 內，避免每次 2 秒累加超出預算。
            resp = None
            try:
                resp = self._urlopen(health_url, timeout=min(2.0, remaining))
                if self._cancel_event.is_set() or _cancel_requested(cancel_event):
                    return _STOPPED
                base_url = f"http://127.0.0.1:{port}/v1"
                self._report_progress("ready", 100)
                gpu_offload_layers, gpu_total_layers = _snapshot_gpu_offload()
                gpu_process_confirmed = False
                process_pid = getattr(proc, "pid", None)
                if mode == "gpu" and isinstance(process_pid, int) and process_pid > 0:
                    try:
                        gpu_process_confirmed = bool(self._gpu_process_probe(process_pid))
                    except Exception:
                        gpu_process_confirmed = False
                gpu_backend_confirmed = (
                    mode == "gpu"
                    and (
                        (gpu_offload_layers > 0 and gpu_total_layers >= gpu_offload_layers)
                        or gpu_process_confirmed
                    )
                )
                return VisionRuntimeState(
                    name="ready",
                    detail="",
                    base_url=base_url,
                    mode=mode,
                    gpu_offload_layers=gpu_offload_layers,
                    gpu_total_layers=gpu_total_layers,
                    gpu_backend_confirmed=gpu_backend_confirmed,
                    gpu_process_confirmed=gpu_process_confirmed,
                )
            except Exception:
                pass
            finally:
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:
                        pass

            remaining = deadline - self._monotonic()
            if remaining <= 0:
                break
            self._sleep(min(_HEALTH_SLEEP_SEC, remaining))

        # 全部嘗試耗盡 → health_timeout
        if self._cancel_event.is_set() or _cancel_requested(cancel_event):
            return _STOPPED
        drain_thread.join(timeout=_STDERR_JOIN_TIMEOUT)
        stderr_text = _snapshot_stderr()
        return VisionRuntimeState(
            name="failed",
            detail=f"health_timeout: {stderr_text}",
            base_url="",
            mode=mode,
        )

    # ── 內部：資產驗證 ────────────────────────────────────────────────────────

    def _report_progress(self, phase: str, progress: int) -> None:
        value = max(self._last_progress, min(100, int(progress)))
        if value == self._last_progress and value not in {0, 100}:
            return
        self._last_progress = value
        callback = self._progress_callback
        if callback is None:
            return
        try:
            callback(phase, value)
        except Exception:
            pass

    def _report_line_progress(self, line: str) -> None:
        normalized = str(line or "").lower()
        for marker, phase, progress in _PROGRESS_MARKERS:
            if marker in normalized:
                self._report_progress(phase, progress)
                return

    def _check_assets(self) -> str:
        """回傳空字串表示 OK；否則回傳第一個錯誤的 detail。

        使用 verify_asset（已包含存在性與大小驗證）取代單純 path.exists()。
        """
        a = self._assets
        field_map = [
            ("server_path", a.server_path, "runtime_missing"),
            ("model_path", a.model_path, "model_missing"),
        ]
        if self._profile.requires_projector:
            field_map.append(("projector_path", a.projector_path, "projector_missing"))
        for field, path, missing_code in field_map:
            min_bytes = self._asset_minimum_bytes.get(field, 0)
            try:
                expected_sha = ASSET_SHA256[field] if self._assets.managed else None
                verify_asset(path, expected_sha, minimum_bytes=min_bytes)
            except VisionAssetError as exc:
                if exc.code == "asset_missing":
                    return f"{missing_code}: {path.name}"
                return f"{exc.code}: {path.name} ({exc.detail})"
        return ""

    # ── 內部：process 清理 ────────────────────────────────────────────────────

    def _cleanup_process(self, proc) -> None:
        """Terminate + wait；超時或 terminate 失敗後 force-kill。"""
        if proc is None:
            return
        try:
            proc.terminate()
        except Exception:
            # Windows process handles can reject terminate during teardown;
            # still make a best-effort kill before returning.
            try:
                proc.kill()
            except Exception:
                pass
            return
        try:
            proc.wait(timeout=_CLEANUP_WAIT_TIMEOUT)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ──────────────────────────────────────────────────────────────────────────────
# 內部工具
# ──────────────────────────────────────────────────────────────────────────────


_GPU_OFFLOAD_RE = re.compile(
    r"offloaded\s+(\d+)\s*/\s*(\d+)\s+layers\s+to\s+gpu",
    flags=re.IGNORECASE,
)


def _default_gpu_process_probe(pid: int) -> bool:
    """以 NVIDIA driver 的 process snapshot 補足新版 server 缺少的 offload marker。"""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    for line in result.stdout.splitlines():
        token = line.split(",", 1)[0].strip()
        if token.isdigit() and int(token) == pid:
            return True
    return False


def _find_gpu_offload_layers(stderr_text: str) -> tuple[int, int] | None:
    """回傳最後一筆 llama.cpp GPU offload marker；無 marker 則為 None。"""
    matches = _GPU_OFFLOAD_RE.findall(str(stderr_text or ""))
    if not matches:
        return None
    offloaded, total = matches[-1]
    return int(offloaded), int(total)


def _parse_gpu_offload_layers(stderr_snapshot: str) -> tuple[int, int]:
    """解析 llama.cpp stderr 文字；保留無 marker 時的 (0, 0) 相容行為。"""
    return _find_gpu_offload_layers(stderr_snapshot) or (0, 0)

def _is_cuda_error(detail: str) -> bool:
    """判斷 detail 是否含有 CUDA/VRAM 啟動失敗的關鍵字（小寫比對）。"""
    lower = detail.lower()
    return any(kw in lower for kw in _CUDA_ERROR_KEYWORDS)


def _default_urlopen() -> Callable:
    """生產環境預設使用 urllib.request.urlopen。"""
    from urllib.request import urlopen as _urlopen
    return _urlopen


def _default_port_allocator() -> Callable[[], int]:
    """以 OS 自動配置空閒 loopback port。"""
    import socket

    def _alloc() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    return _alloc
