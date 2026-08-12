import threading
from concurrent.futures import Future
from types import SimpleNamespace

from cloudhime_workers import OCRWorker


class FakeProcess:
    def __init__(self, pid=4242, return_code=None):
        self.pid = pid
        self.return_code = return_code

    def poll(self):
        return self.return_code


class FakeProvider:
    def __init__(self):
        self.base_url = ""
        self.model_name = ""
        self._runtime_ready = False
        self.runtime_updates = []

    def update_runtime(self, base_url, model_name, ready):
        self.base_url = (base_url or "").rstrip("/")
        self.model_name = model_name
        self._runtime_ready = bool(ready and self.base_url and model_name)
        self.runtime_updates.append((base_url, model_name, ready))


class InlineExecutor:
    def __init__(self):
        self.submissions = 0

    def submit(self, callback):
        self.submissions += 1
        future = Future()
        try:
            future.set_result(callback())
        except Exception as exc:
            future.set_exception(exc)
        return future


class PendingExecutor:
    def __init__(self):
        self.submissions = []

    def submit(self, callback):
        future = Future()
        self.submissions.append((callback, future))
        return future


class FakeOwnedRuntime:
    def __init__(self, *, state, start_state=None, process=None):
        self._state = state
        self._start_state = start_state or state
        self._process = process if process is not None else FakeProcess()
        self.start_calls = 0

    @property
    def owned_process(self):
        return self._process

    @property
    def profile_name(self):
        return "vision"

    def start(self, *, cancel_event=None):
        self.start_calls += 1
        if cancel_event is not None and cancel_event.is_set():
            self._state = state("stopped")
            return self._state
        self._state = self._start_state
        return self._state


def state(name, *, base_url="", mode="", detail="", gpu_offload_layers=0, gpu_total_layers=0, gpu_backend_confirmed=False):
    return SimpleNamespace(name=name, base_url=base_url, mode=mode, detail=detail, gpu_offload_layers=gpu_offload_layers, gpu_total_layers=gpu_total_layers, gpu_backend_confirmed=gpu_backend_confirmed)


def make_worker(runtime, executor=None):
    statuses = []
    worker = OCRWorker.__new__(OCRWorker)
    worker.use_gemma_translation = True
    worker.local_vision_runtime = runtime
    worker.local_multimodal_provider = FakeProvider()
    worker.local_multimodal_model = "gemma-3-4b-it"
    worker._local_vision_executor = executor or InlineExecutor()
    worker._local_vision_load_future = None
    worker._local_vision_cancel_event = threading.Event()
    worker._local_vision_assets = None
    worker._local_runtime_profile = "vision"
    worker.local_multimodal_enabled = True
    worker._local_text_runtime_required = False
    worker.local_vision_status = SimpleNamespace(emit=lambda *args: statuses.append(args))
    worker._refresh_translation_registry = lambda: None
    worker.statuses = statuses
    return worker


def test_ensure_uses_formal_start_path_and_syncs_owned_cpu_runtime_provider():
    endpoint = "http://127.0.0.1:48123/v1"
    runtime = FakeOwnedRuntime(
        state=state("stopped"),
        start_state=state("ready", base_url=endpoint, mode="cpu", gpu_offload_layers=12, gpu_total_layers=43),
    )
    worker = make_worker(runtime)

    assert worker.ensure_local_runtime_ready(0.1) is True
    assert runtime.start_calls == 1
    assert worker._local_vision_executor.submissions == 1
    assert worker.local_vision_runtime is runtime
    assert worker.statuses == [("starting", ""), ("ready", "")]
    assert worker.local_multimodal_provider.runtime_updates == [
        (endpoint, "gemma-3-4b-it", True)
    ]
    assert worker.local_multimodal_provider.base_url == endpoint
    assert worker.local_multimodal_provider._runtime_ready is True
    assert worker._local_vision_load_future is None
    assert worker.local_runtime_evidence() == {
        "ready": True,
        "profile": "vision",
        "mode": "cpu",
        "gpu_offload_layers": 12,
        "gpu_total_layers": 43,
        "gpu_backend_confirmed": False,
        "base_url": endpoint,
        "owned_process": True,
        "owned_process_handle": runtime.owned_process,
        "pid": 4242,
        "server_path": "",
    }


def test_local_runtime_evidence_confirms_only_gpu_with_positive_valid_offload():
    endpoint = "http://127.0.0.1:48126/v1"
    runtime = FakeOwnedRuntime(
        state=state(
            "ready",
            base_url=endpoint,
            mode="gpu",
            gpu_offload_layers=12,
            gpu_total_layers=43,
        )
    )
    worker = make_worker(runtime)

    assert worker.local_runtime_evidence()["gpu_backend_confirmed"] is True

    runtime._state = state(
        "ready",
        base_url=endpoint,
        mode="gpu",
        gpu_offload_layers=0,
        gpu_total_layers=43,
    )
    evidence = worker.local_runtime_evidence()
    assert evidence["gpu_offload_layers"] == 0
    assert evidence["gpu_total_layers"] == 43
    assert evidence["gpu_backend_confirmed"] is False

def test_ensure_reuses_pending_future_then_failed_callback_clears_lifecycle():
    runtime = FakeOwnedRuntime(state=state("starting"))
    executor = PendingExecutor()
    worker = make_worker(runtime, executor)

    assert worker.ensure_local_runtime_ready(0) is False
    assert len(executor.submissions) == 1
    assert runtime.start_calls == 0
    pending = worker._local_vision_load_future

    assert worker.ensure_local_runtime_ready(0) is False
    assert len(executor.submissions) == 1
    assert worker._local_vision_load_future is pending

    pending.set_exception(RuntimeError("private runtime failure"))
    assert worker._local_vision_load_future is None
    assert worker.local_multimodal_provider.runtime_updates[-1] == ("", "", False)
    assert worker.statuses[-1][0] == "failed"


def test_ensure_recycles_completed_failed_future_through_same_runtime():
    endpoint = "http://127.0.0.1:48124/v1"
    runtime = FakeOwnedRuntime(
        state=state("failed"),
        start_state=state("ready", base_url=endpoint, mode="gpu"),
    )
    worker = make_worker(runtime)
    stale = Future()
    stale.set_exception(RuntimeError("old failure"))
    worker._local_vision_load_future = stale

    assert worker.ensure_local_runtime_ready(0.1) is True
    assert runtime.start_calls == 1
    assert worker.local_vision_runtime is runtime
    assert worker.local_multimodal_provider.base_url == endpoint
    assert worker._local_vision_load_future is None


def test_ready_evidence_requires_a_live_owned_process():
    endpoint = "http://127.0.0.1:48125/v1"
    runtime = FakeOwnedRuntime(
        state=state("ready", base_url=endpoint, mode="gpu"),
        process=FakeProcess(return_code=7),
    )
    worker = make_worker(runtime)

    assert worker.ensure_local_runtime_ready(0.1) is False
    assert worker.local_runtime_evidence() == {
        "ready": False,
        "profile": "vision",
        "mode": "",
        "gpu_offload_layers": 0,
        "gpu_total_layers": 0,
        "gpu_backend_confirmed": False,
        "base_url": "",
        "owned_process": True,
        "owned_process_handle": runtime.owned_process,
        "pid": 4242,
        "server_path": "",
    }


def test_local_runtime_evidence_rejects_external_ollama_endpoint():
    runtime = FakeOwnedRuntime(
        state=state("ready", base_url="http://ollama.example:11434/v1", mode="gpu")
    )
    worker = make_worker(runtime)

    assert worker.ensure_local_runtime_ready(0.1) is False
    assert runtime.start_calls == 0
    assert worker.local_runtime_evidence() == {
        "ready": False,
        "profile": "vision",
        "mode": "",
        "gpu_offload_layers": 0,
        "gpu_total_layers": 0,
        "gpu_backend_confirmed": False,
        "base_url": "",
        "owned_process": True,
        "owned_process_handle": runtime.owned_process,
        "pid": 4242,
        "server_path": "",
    }
