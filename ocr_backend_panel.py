from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy

from ocr_backend_catalog import BACKEND_SPECS, optional_backend_names, summarize_backend_chain
from ocr_backend_installer import detect_backend_state, install_backend_packages
from themes import resolve_theme


class _BackendInstallWorker(QObject):
    finished = Signal(str, bool, str)

    def __init__(self, backend_name):
        super().__init__()
        self.backend_name = backend_name

    def run(self):
        success, message = install_backend_packages(self.backend_name)
        self.finished.emit(self.backend_name, success, message)


class OcrBackendSettingsPanel(QFrame):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._busy_backend = None
        self._install_jobs = {}
        self._backend_buttons = {}
        self._build_ui()
        self.sync_from_controller()

    def _build_ui(self):
        self.setObjectName("ocrBackendSettingsPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self.lbl_title = QLabel("OCR")
        self.lbl_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        outer.addWidget(self.lbl_title)

        self.lbl_windows = QLabel("Windows OCR")
        self.lbl_windows.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)
        outer.addWidget(self.lbl_windows)

        for backend_name in optional_backend_names():
            spec = BACKEND_SPECS[backend_name]
            button = QPushButton(spec.label)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, name=backend_name: self.on_backend_toggled(name, checked))
            button.setMinimumHeight(28)
            self._backend_buttons[backend_name] = button
            outer.addWidget(button)

        outer.addStretch()

    def _backend_chain(self):
        chain = []
        if hasattr(self.controller, "get_ocr_backend_chain"):
            chain = list(self.controller.get_ocr_backend_chain() or [])
        elif getattr(self.controller, "worker", None) is not None:
            chain = list(getattr(self.controller.worker, "ocr_backend_chain", []) or [])
        if "windows" not in chain:
            chain.insert(0, "windows")
        return chain

    def _refresh_summary(self):
        chain_text = summarize_backend_chain(self._backend_chain())
        self.setToolTip(chain_text)
        self.lbl_windows.setToolTip(chain_text)

    def _set_controller_backend_enabled(self, backend_name, enabled):
        if hasattr(self.controller, "set_ocr_backend_enabled"):
            self.controller.set_ocr_backend_enabled(backend_name, enabled)
            return
        if not hasattr(self.controller, "set_ocr_backend_chain"):
            return
        chain = list(self._backend_chain())
        if backend_name == "windows":
            enabled = True
        if enabled:
            if backend_name not in chain:
                chain.append(backend_name)
        else:
            chain = [item for item in chain if item != backend_name]
        if not chain:
            chain = ["windows"]
        self.controller.set_ocr_backend_chain(chain)

    def _set_backend_busy(self, backend_name, busy):
        button = self._backend_buttons.get(backend_name)
        if button is None:
            return
        button.setEnabled(not busy)
        button.setText(f"{BACKEND_SPECS[backend_name].label}..." if busy else BACKEND_SPECS[backend_name].label)

    def on_backend_toggled(self, backend_name, checked):
        if backend_name == "windows":
            self.sync_from_controller()
            return
        if self._busy_backend is not None and self._busy_backend != backend_name:
            self.sync_from_controller()
            return
        if not checked:
            self._set_controller_backend_enabled(backend_name, False)
            self.sync_from_controller()
            return

        # 先立即反映成啟用，避免偵測或同步延遲讓 UI 看起來像沒吃到。
        self._set_controller_backend_enabled(backend_name, True)
        self.sync_from_controller()

        state = detect_backend_state(backend_name)
        if not state.available:
            self._start_backend_install(backend_name)

    def _start_backend_install(self, backend_name):
        if self._busy_backend is not None:
            return
        self._busy_backend = backend_name
        self._set_backend_busy(backend_name, True)

        thread = QThread(self)
        worker = _BackendInstallWorker(backend_name)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_install_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._install_jobs[backend_name] = (thread, worker)
        thread.start()

    def _on_install_finished(self, backend_name, success, message):
        self._install_jobs.pop(backend_name, None)
        self._busy_backend = None
        state = detect_backend_state(backend_name)
        if success and state.available:
            self._set_controller_backend_enabled(backend_name, True)
            self.sync_from_controller()
            return
        self._set_controller_backend_enabled(backend_name, False)
        self.sync_from_controller()
        title = BACKEND_SPECS[backend_name].label if backend_name in BACKEND_SPECS else "OCR"
        body = message or state.detail or "Install failed."
        if success and not state.available:
            QMessageBox.information(self, title, body)
        else:
            QMessageBox.warning(self, title, body)

    def sync_from_controller(self):
        chain = set(self._backend_chain())
        for backend_name in optional_backend_names():
            button = self._backend_buttons[backend_name]
            state = detect_backend_state(backend_name)
            checked = backend_name in chain
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)
            if self._busy_backend == backend_name:
                button.setText(f"{BACKEND_SPECS[backend_name].label}...")
            else:
                button.setText(BACKEND_SPECS[backend_name].label)
            button.setToolTip(state.detail if state.detail else BACKEND_SPECS[backend_name].install_note)
        self._refresh_summary()

    def update_theme(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.lbl_title.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {theme.subtext};")
        self.lbl_windows.setStyleSheet(
            f"color: {theme.accent}; background-color: {theme.accent_soft}; border: 1px solid {theme.border}; "
            f"border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 700;"
        )
        button_style = (
            f"QPushButton {{ color: {theme.text}; background-color: transparent; border: 1px solid {theme.border}; "
            f"border-radius: 10px; padding: 5px 10px; font-size: 11px; font-weight: 700; }}"
            f"QPushButton:checked {{ background-color: {theme.accent}; color: #FFFFFF; border-color: {theme.accent}; }}"
            f"QPushButton:disabled {{ color: {theme.subtext}; }}"
        )
        for backend_name in optional_backend_names():
            button = self._backend_buttons.get(backend_name)
            if button is not None:
                button.setStyleSheet(button_style)
        self._refresh_summary()
