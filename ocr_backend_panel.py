from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout

from ocr_backend_catalog import BACKEND_SPECS, optional_backend_names, summarize_backend_chain
from ocr_backend_installer import detect_backend_state, install_backend_packages
import translation_helpers as translation_tools
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
        self._backend_state_cache = {}
        self._build_ui()
        self.sync_from_controller()

    def _build_ui(self):
        self.setObjectName("ocrBackendSettingsPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self.lbl_title = QLabel("")
        self.lbl_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        outer.addWidget(self.lbl_title)

        self.segment_container = QFrame()
        self.segment_container.setObjectName("ocrBackendSegment")
        segment = QHBoxLayout(self.segment_container)
        segment.setContentsMargins(2, 2, 2, 2)
        segment.setSpacing(4)

        for index, backend_name in enumerate(optional_backend_names()):
            spec = BACKEND_SPECS[backend_name]
            button = QPushButton(spec.label)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, name=backend_name: self.on_backend_toggled(name, checked))
            button.setMinimumHeight(42)
            self._backend_buttons[backend_name] = button
            segment.addWidget(button)
        outer.addWidget(self.segment_container)
        self.refresh_localized_texts()

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
        if getattr(self.controller, "google_ocr_enabled", False):
            chain_text = f"{chain_text} + GoogleOCR"
        self.setToolTip(chain_text)

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

    def _cache_backend_state(self, backend_name):
        try:
            self._backend_state_cache[backend_name] = detect_backend_state(backend_name)
        except Exception:
            self._backend_state_cache.pop(backend_name, None)
        return self._backend_state_cache.get(backend_name)

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

        state = self._cache_backend_state(backend_name)
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
        state = self._cache_backend_state(backend_name)
        if state is None:
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
        self.refresh_localized_texts()
        chain = set(self._backend_chain())
        for backend_name in optional_backend_names():
            button = self._backend_buttons[backend_name]
            state = self._backend_state_cache.get(backend_name)
            checked = backend_name in chain
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)
            if self._busy_backend == backend_name:
                button.setText(f"{BACKEND_SPECS[backend_name].label}...")
            else:
                button.setText(BACKEND_SPECS[backend_name].label)
            detail = state.detail if state is not None and state.detail else BACKEND_SPECS[backend_name].install_note
            button.setToolTip(detail)
            button.setEnabled(True if self._busy_backend != backend_name else False)
        self._refresh_summary()

    def update_theme(self, theme_mode):
        theme = resolve_theme(theme_mode)
        self.refresh_localized_texts()
        self.lbl_title.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {theme.subtext};")
        self.segment_container.setStyleSheet(theme.panel_qss("subtle", radius=11))
        button_style = theme.button_qss(radius=8)
        for backend_name in optional_backend_names():
            button = self._backend_buttons.get(backend_name)
            if button is not None:
                button.setStyleSheet(button_style)
        self._refresh_summary()

    def refresh_localized_texts(self):
        lang = translation_tools.get_ui_language(self.controller)
        self.lbl_title.setText(translation_tools.ui_text(lang, "ocr_backend_title"))
        for backend_name in optional_backend_names():
            button = self._backend_buttons.get(backend_name)
            if button is not None:
                button.setText(BACKEND_SPECS[backend_name].label)
