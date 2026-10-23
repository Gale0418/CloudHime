from PySide6.QtCore import QObject, QThread, Qt, Signal

from remote_model_discovery import (
    DISCOVERY_STATUS_NO_KEY,
    DISCOVERY_STATUS_VERIFIED,
    ModelDiscoveryResult,
)
from remote_model_availability_worker import RemoteModelAvailabilityWorker


def test_worker_emits_generation_and_result_once(qtbot):
    calls = []

    def discover(api_key, **kwargs):
        calls.append((api_key, kwargs))
        return ModelDiscoveryResult(
            status=DISCOVERY_STATUS_VERIFIED,
            available_model_ids=("gemma-4-31b-it",),
            verified=True,
        )

    worker = RemoteModelAvailabilityWorker(discover=discover)
    thread = QThread()
    worker.moveToThread(thread)
    thread.start()
    try:
        received = []
        worker.finished.connect(lambda generation, result: received.append((generation, result)))
        worker.refresh("secret-key", 7)
        qtbot.waitUntil(lambda: len(received) == 1)
        assert received[0][0] == 7
        assert received[0][1].status == DISCOVERY_STATUS_VERIFIED
        assert calls == [(
            "secret-key",
            {"snapshot_path": None, "timeout_seconds": 5},
        )]
    finally:
        thread.quit()
        assert thread.wait(2000)


def test_worker_converts_unexpected_exception_to_safe_result(qtbot):
    def discover(api_key, **kwargs):
        raise RuntimeError(f"leaked key={api_key}")

    worker = RemoteModelAvailabilityWorker(discover=discover)
    received = []
    worker.finished.connect(lambda generation, result: received.append((generation, result)))

    worker.refresh("secret-key", 11)

    assert len(received) == 1
    generation, result = received[0]
    assert generation == 11
    assert result.status != DISCOVERY_STATUS_VERIFIED
    assert result.error_code == "worker_failed"
    assert "secret-key" not in repr(result)


def test_worker_passes_empty_key_without_network(monkeypatch, qtbot):
    calls = []

    def discover(*args, **kwargs):
        calls.append((args, kwargs))
        return ModelDiscoveryResult(status=DISCOVERY_STATUS_NO_KEY, error_code="no_key")

    worker = RemoteModelAvailabilityWorker(discover=discover)
    received = []
    worker.finished.connect(lambda generation, result: received.append((generation, result)))

    worker.refresh("", 3)

    assert calls == [(("",), {"snapshot_path": None, "timeout_seconds": 5})]
    assert received[0][1].status == DISCOVERY_STATUS_NO_KEY


class _RequestEmitter(QObject):
    request = Signal(str, int)


def test_worker_slot_runs_in_its_qthread(qtbot):
    in_worker_thread = []
    worker = None

    def discover(api_key, **kwargs):
        in_worker_thread.append(worker.thread() == QThread.currentThread())
        return ModelDiscoveryResult(status=DISCOVERY_STATUS_VERIFIED, verified=True)

    worker = RemoteModelAvailabilityWorker(discover=discover)
    thread = QThread()
    emitter = _RequestEmitter()
    worker.moveToThread(thread)
    emitter.request.connect(worker.refresh, Qt.QueuedConnection)
    received = []
    worker.finished.connect(lambda generation, result: received.append((generation, result)))
    thread.start()
    try:
        emitter.request.emit("secret-key", 13)
        qtbot.waitUntil(lambda: len(received) == 1)
        assert received[0][0] == 13
        assert in_worker_thread == [True]
    finally:
        thread.quit()
        assert thread.wait(2000)
