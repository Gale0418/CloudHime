"""Regression coverage for non-blocking UI shutdown ordering."""
import hashlib
import threading
import time

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, Signal, Slot, QThread, QTimer
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from cloudhime_ui import Controller, OverlayWindow
from knowledge_builder_worker import KnowledgeBuildWorker


_KNOWLEDGE_SOURCE_URL = "https://example.com/knowledge"
_KNOWLEDGE_SOURCE_ID = hashlib.sha256(_KNOWLEDGE_SOURCE_URL.encode("utf-8")).hexdigest()[:16]
_KNOWLEDGE_SOURCE_CONTENT = "A bounded trusted source."
_KNOWLEDGE_SOURCE_HASH = hashlib.sha256(_KNOWLEDGE_SOURCE_CONTENT.encode("utf-8")).hexdigest()


def _knowledge_draft():
    return {
        "schema_version": 1,
        "status": "draft",
        "title": "Work",
        "query": "Work",
        "created_at": "2026-08-03T04:00:00+00:00",
        "sources": [{
            "source_id": _KNOWLEDGE_SOURCE_ID,
            "url": _KNOWLEDGE_SOURCE_URL,
            "title": "Official source",
            "snippet": "A bounded snippet.",
            "status": "read",
            "fetched_at": "2026-08-03T04:00:00+00:00",
            "content": _KNOWLEDGE_SOURCE_CONTENT,
            "content_sha256": _KNOWLEDGE_SOURCE_HASH,
            "error": "",
        }],
        "entries": [],
        "review": {"owner_confirmed": False, "approver": None, "approved_at": None},
    }


class _BlockedSlot(QObject):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    @Slot()
    def run(self):
        self.entered.set()
        self.release.wait(3.0)
        self.moveToThread(QApplication.instance().thread())


class _QueuedCall(QObject):
    fire = Signal()


class _NativeJoinGateThread(QThread):
    def __init__(self):
        super().__init__()
        self.native_joined = False

    def wait(self, *args):
        return self.native_joined


def _make_controller(qtbot, monkeypatch, *, register_controller=True):
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None))
    monkeypatch.setattr("cloudhime_ui.SecretStore.get", lambda self: "")
    monkeypatch.setattr("cloudhime_ui.SecretStore.legacy_sources_disabled", lambda self: True)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args: None)
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
    if register_controller:
        qtbot.addWidget(controller)
    controller.show()
    return controller


def test_close_waits_for_ocr_slot_before_cleanup_and_keeps_gui_responsive(qtbot, monkeypatch):
    controller = _make_controller(qtbot, monkeypatch)
    blocker = _BlockedSlot()
    blocker.moveToThread(controller.ocr_thread)
    queued = _QueuedCall()
    queued.fire.connect(blocker.run, Qt.QueuedConnection)
    queued.fire.emit()
    qtbot.waitUntil(blocker.entered.is_set, timeout=2000)

    events = []
    original_cleanup = controller.worker.cleanup

    def tracked_cleanup():
        events.append(("cleanup", controller.ocr_thread.isRunning()))
        time.sleep(0.12)
        original_cleanup()

    controller.worker.cleanup = tracked_cleanup
    ticks = []
    heartbeat = QTimer(controller)
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
    heartbeat.start()

    start = time.monotonic()
    controller.close()  # native close path
    controller.close()  # repeated close while pending is harmless
    elapsed = time.monotonic() - start
    assert elapsed < 0.1
    assert controller.isVisible()
    assert controller._shutdown_pending
    assert controller.lbl_status.text() == controller._tr("controller.status.shutting_down")
    for button in (
        controller.btn_now,
        controller.btn_hotkey,
        controller.btn_30,
        controller.btn_stop,
        controller.btn_mode_full,
        controller.btn_mode_region,
    ):
        assert not button.isEnabled()
    assert events == []

    blocker.release.set()
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False), timeout=5000)
    heartbeat.stop()
    assert events == [("cleanup", False)]
    assert len(ticks) >= 2
    assert not controller.isVisible()


def test_stale_scan_result_is_not_rendered_while_shutdown_is_pending(qtbot, monkeypatch):
    controller = _make_controller(qtbot, monkeypatch)
    rendered = []
    controller.on_scan_complete = rendered.append
    generation = controller.scan_generation
    controller.close_app()
    assert controller._shutdown_pending
    controller.on_scan_complete_for_generation(generation, [["late result"]])
    assert rendered == []
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False), timeout=5000)


def test_delayed_hotkey_activation_is_cancelled_when_closing(qtbot, monkeypatch):
    registrations = []
    monkeypatch.setattr(
        "cloudhime_ui.GlobalHotKeyFilter.register_hotkey",
        lambda self, hwnd: registrations.append(hwnd),
    )
    monkeypatch.setattr(
        "cloudhime_ui.ctypes.windll.user32.SetWindowDisplayAffinity",
        lambda *args: None,
    )
    controller = _make_controller(qtbot, monkeypatch)
    controller.close_app()
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False), timeout=5000)
    qtbot.wait(600)
    assert registrations == []


def test_settings_window_is_destroyed_with_controller(qtbot, monkeypatch):
    controller = _make_controller(qtbot, monkeypatch, register_controller=False)
    controller.toggle_settings_window()
    settings = controller.settings_window
    assert settings.isWindow()
    settings.close()
    assert isValid(settings)  # Closing settings must still allow reopening it.
    controller.toggle_settings_window()
    assert controller.settings_window is settings
    controller.close_app()
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False), timeout=5000)
    controller.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert not isValid(controller)
    assert not isValid(settings)


def test_stopped_ocr_thread_still_waits_for_native_join(qtbot, monkeypatch):
    controller = _make_controller(qtbot, monkeypatch)
    ocr_thread = controller.ocr_thread
    native_wait = ocr_thread.wait
    monkeypatch.setattr(ocr_thread, "wait", lambda *_args: False)

    controller.close_app()
    qtbot.waitUntil(lambda: not ocr_thread.isRunning(), timeout=2000)
    qtbot.wait(30)
    assert not getattr(controller, "_shutdown_cleanup_started", False)
    assert not getattr(controller, "_close_app_finished", False)

    monkeypatch.setattr(ocr_thread, "wait", native_wait)
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False), timeout=5000)


def test_close_waits_for_stalled_remote_availability_slot(qtbot, monkeypatch):
    controller = _make_controller(qtbot, monkeypatch)
    blocker = _BlockedSlot()
    blocker.moveToThread(controller.remote_model_availability_thread)
    queued = _QueuedCall()
    queued.fire.connect(blocker.run, Qt.QueuedConnection)
    queued.fire.emit()
    qtbot.waitUntil(blocker.entered.is_set, timeout=2000)

    start = time.monotonic()
    controller.close_app()
    assert time.monotonic() - start < 0.1
    assert not getattr(controller, "_close_app_finished", False)
    assert controller.isVisible()

    blocker.release.set()
    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False), timeout=5000)
    assert not controller.remote_model_availability_thread


def test_finished_signals_do_not_release_shutdown_gates_before_native_join(qtbot):
    import cloudhime_ui

    # Use real Qt QThread objects whose wait(0) is deliberately delayed to
    # model the interval between QThread.finished and native TLS teardown.
    controller = Controller.__new__(Controller)
    QWidget.__init__(controller)
    controller._maybe_finish_app_shutdown = lambda: None

    cleanup_thread = _NativeJoinGateThread()
    controller._shutdown_cleanup_thread = cleanup_thread
    controller._shutdown_cleanup_finished = False
    cloudhime_ui._ACTIVE_SHUTDOWN_THREADS.add(cleanup_thread)
    controller._on_shutdown_cleanup_finished()
    assert not controller._shutdown_cleanup_finished
    assert cleanup_thread in cloudhime_ui._ACTIVE_SHUTDOWN_THREADS
    cleanup_thread.native_joined = True
    controller._on_shutdown_cleanup_finished()
    assert controller._shutdown_cleanup_finished
    assert cleanup_thread not in cloudhime_ui._ACTIVE_SHUTDOWN_THREADS

    remote_thread = _NativeJoinGateThread()
    controller._remote_model_shutdown_thread = remote_thread
    controller.remote_model_availability_thread = remote_thread
    controller.remote_model_availability_worker = object()
    controller._remote_model_shutdown_finished = False
    cloudhime_ui._ACTIVE_REMOTE_SHUTDOWN_THREADS.add(remote_thread)
    controller._on_remote_model_availability_shutdown_finished()
    assert not controller._remote_model_shutdown_finished
    assert remote_thread in cloudhime_ui._ACTIVE_REMOTE_SHUTDOWN_THREADS
    remote_thread.native_joined = True
    controller._on_remote_model_availability_shutdown_finished()
    assert controller._remote_model_shutdown_finished
    assert remote_thread not in cloudhime_ui._ACTIVE_REMOTE_SHUTDOWN_THREADS
    assert controller.remote_model_availability_thread is None
    controller.deleteLater()
    qtbot.wait(0)


def test_close_waits_for_cancelled_knowledge_worker_past_old_timeout(qtbot, monkeypatch):
    controller = _make_controller(qtbot, monkeypatch)
    entered = threading.Event()
    release = threading.Event()
    cancellation = []
    completed = []
    cancelled = []

    def blocked_research(cancel_event):
        cancellation.append(cancel_event)
        entered.set()
        release.wait()
        return _knowledge_draft()

    def unexpected_extraction(*_args):
        raise AssertionError("cancelled build must not extract")

    worker = KnowledgeBuildWorker(
        research_builder=blocked_research,
        extractor=unexpected_extraction,
        on_finished=completed.append,
        on_cancelled=cancelled.append,
    )
    controller.knowledge_build_worker = worker
    job_id = worker.start()
    assert entered.wait(2.0)

    ticks = []
    heartbeat = QTimer(controller)
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
    heartbeat.start()

    controller.close_app()
    assert controller._shutdown_pending
    assert controller.lbl_status.text() == controller._tr("controller.status.shutting_down")
    assert not getattr(controller, "_close_app_finished", False)
    assert worker.is_running()  # Research remains blocked until released.
    assert cancellation[0].is_set()
    constructor_calls = []

    def unexpected_service_constructor(**_kwargs):
        constructor_calls.append(True)
        raise AssertionError("shutdown must reject new knowledge builds")

    monkeypatch.setattr("cloudhime_ui.KnowledgeResearchService", unexpected_service_constructor)
    assert not controller.start_knowledge_research("must not start")
    assert constructor_calls == []

    try:
        # The previous 2s timeout let cleanup finish while this real worker
        # was still executing its research callback.
        qtbot.wait(2200)
        assert not getattr(controller, "_close_app_finished", False)
        assert not getattr(controller, "_shutdown_cleanup_finished", False)
        assert worker.is_running()
        assert completed == []
        assert len(ticks) >= 20
    finally:
        release.set()

    qtbot.waitUntil(lambda: getattr(controller, "_close_app_finished", False), timeout=5000)
    heartbeat.stop()
    worker.wait_for_all()
    assert completed == []
    assert cancelled == [job_id]
    assert not worker.is_running()
    assert not controller.start_knowledge_research("must not start")
    assert constructor_calls == []
