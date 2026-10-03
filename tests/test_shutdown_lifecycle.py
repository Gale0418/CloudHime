"""Regression coverage for non-blocking UI shutdown ordering."""
import threading
import time

from PySide6.QtCore import QObject, Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import QApplication

from cloudhime_ui import Controller, OverlayWindow


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


def _make_controller(qtbot, monkeypatch):
    monkeypatch.setattr("cloudhime_ui.load_settings_data", lambda paths: ({}, None))
    monkeypatch.setattr("cloudhime_ui.SecretStore.get", lambda self: "")
    monkeypatch.setattr("cloudhime_ui.SecretStore.legacy_sources_disabled", lambda self: True)
    monkeypatch.setattr(Controller, "save_settings", lambda self: True)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda *args: None)
    overlay = OverlayWindow()
    qtbot.addWidget(overlay)
    controller = Controller(overlay)
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
