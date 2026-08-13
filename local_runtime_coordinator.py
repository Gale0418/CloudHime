"""Application-scoped ownership for the single local llama-server runtime."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable

from local_vision_runtime import LocalVisionRuntime


def _asset_key(assets) -> tuple[str, ...]:
    return tuple(
        str(getattr(assets, field, ""))
        for field in ("server_path", "model_path", "projector_path")
    )


@dataclass
class _RuntimeEntry:
    runtime: object
    leases: int = 0
    stopped: bool = False


class LocalVisionRuntimeLease:
    """Reference-counted handle for one consumer of a shared runtime."""

    def __init__(self, coordinator, key, runtime):
        self._coordinator = coordinator
        self._key = key
        self.runtime = runtime
        self._released = False

    @property
    def released(self) -> bool:
        return self._released

    def stop(self):
        return self._coordinator.stop(self)

    def set_profile(self, profile):
        return self._coordinator.set_profile(self, profile)

    def set_gpu_layers(self, gpu_layers):
        return self._coordinator.set_gpu_layers(self, gpu_layers)

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._coordinator.release(self)


class LocalVisionRuntimeCoordinator:
    """Own one application-wide runtime and protect it with reference-counted leases.

    The coordinator is intentionally explicit and application-scoped. A caller that
    does not provide one keeps the old standalone ``LocalVisionRuntime`` behavior,
    while the GUI can pass one coordinator to every worker it creates.
    """

    def __init__(self, *, runtime_factory: Callable = LocalVisionRuntime):
        self._runtime_factory = runtime_factory
        self._lock = RLock()
        self._entries: dict[tuple[str, ...], _RuntimeEntry] = {}

    @property
    def active_lease_count(self) -> int:
        with self._lock:
            return sum(entry.leases for entry in self._entries.values())

    def acquire(self, assets, *, profile="vision", runtime_kwargs=None):
        key = _asset_key(assets)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                if self._entries:
                    raise RuntimeError("shared_runtime_asset_conflict")
                kwargs = dict(runtime_kwargs or {})
                kwargs["profile"] = profile
                runtime = self._runtime_factory(assets, **kwargs)
                entry = _RuntimeEntry(runtime=runtime, leases=0)
                self._entries[key] = entry
            elif entry.stopped:
                # A stopped entry must not be handed to a new consumer as if it were ready.
                raise RuntimeError("shared_runtime_stopped")
            elif getattr(entry.runtime, "profile_name", profile) != profile:
                raise RuntimeError("shared_runtime_profile_conflict")
            entry.leases += 1
            entry.stopped = False
            return LocalVisionRuntimeLease(self, key, entry.runtime)

    def _entry_for(self, lease) -> _RuntimeEntry:
        if lease._coordinator is not self or lease._released:
            raise RuntimeError("runtime_lease_invalid")
        entry = self._entries.get(lease._key)
        if entry is None:
            raise RuntimeError("runtime_lease_missing")
        return entry

    def stop(self, lease):
        with self._lock:
            entry = self._entry_for(lease)
            if entry.stopped:
                return getattr(entry.runtime, "state", getattr(entry.runtime, "_state", None))
            if entry.leases == 1:
                result = entry.runtime.stop()
                entry.stopped = True
                return result
            return getattr(entry.runtime, "state", getattr(entry.runtime, "_state", None))

    def set_profile(self, lease, profile):
        with self._lock:
            entry = self._entry_for(lease)
            current = getattr(entry.runtime, "profile_name", profile)
            if current == profile:
                return
            if entry.leases != 1:
                raise RuntimeError("shared_runtime_profile_conflict")
            entry.runtime.stop()
            entry.stopped = True
            entry.runtime.set_profile(profile)

    def set_gpu_layers(self, lease, gpu_layers):
        with self._lock:
            entry = self._entry_for(lease)
            if entry.leases != 1:
                raise RuntimeError("shared_runtime_gpu_config_conflict")
            return entry.runtime.set_gpu_layers(gpu_layers)

    def release(self, lease) -> None:
        with self._lock:
            entry = self._entries.get(lease._key)
            if entry is None:
                return
            entry.leases = max(0, entry.leases - 1)
            if entry.leases:
                return
            try:
                if not entry.stopped:
                    entry.runtime.stop()
            finally:
                self._entries.pop(lease._key, None)