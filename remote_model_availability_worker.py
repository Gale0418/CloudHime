"""Qt worker for explicit, non-blocking remote model availability checks."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot

from remote_model_discovery import (
    DISCOVERY_STATUS_UNVERIFIED,
    ModelDiscoveryResult,
    discover_remote_models,
)


class RemoteModelAvailabilityWorker(QObject):
    """Run one discovery call outside the GUI thread.

    The worker receives only immutable request data. It never reads widgets,
    settings objects, or provider instances.
    """

    finished = Signal(int, object)

    def __init__(
        self,
        *,
        snapshot_path: str | None = None,
        timeout_seconds: int = 5,
        discover: Callable[..., ModelDiscoveryResult] = discover_remote_models,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.snapshot_path = snapshot_path
        self.timeout_seconds = max(1, int(timeout_seconds))
        self._discover = discover

    @Slot(str, int)
    def refresh(self, api_key: str, generation: int) -> None:
        try:
            result = self._discover(
                str(api_key or ""),
                snapshot_path=self.snapshot_path,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception:
            result = ModelDiscoveryResult(
                status=DISCOVERY_STATUS_UNVERIFIED,
                error_code="worker_failed",
            )
        self.finished.emit(int(generation), result)
