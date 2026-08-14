import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_runtime_coordinator import LocalVisionRuntimeCoordinator


class FakeRuntime:
    def __init__(self, assets, *, profile='vision', **kwargs):
        self.assets = assets
        self.profile_name = profile
        self.stop_calls = 0
        self.state = SimpleNamespace(name='stopped')

    def stop(self):
        self.stop_calls += 1
        self.state = SimpleNamespace(name='stopped')
        return self.state

    def set_profile(self, profile):
        self.profile_name = profile


def _assets():
    return SimpleNamespace(
        server_path='runtime/llama-server.exe',
        model_path='models/gemma.gguf',
        projector_path='models/mmproj.gguf',
    )


def test_controller_wires_an_application_scoped_runtime_coordinator():
    source = (Path(__file__).resolve().parents[1] / "cloudhime_ui.py").read_text(encoding="utf-8")

    assert "self.local_runtime_coordinator = LocalVisionRuntimeCoordinator()" in source
    assert "OCRWorker(local_runtime_coordinator=self.local_runtime_coordinator)" in source


def test_shared_coordinator_reuses_one_runtime_and_refcounts_leases():
    created = []

    def factory(assets, **kwargs):
        runtime = FakeRuntime(assets, **kwargs)
        created.append(runtime)
        return runtime

    coordinator = LocalVisionRuntimeCoordinator(runtime_factory=factory)
    first = coordinator.acquire(_assets(), profile='vision')
    second = coordinator.acquire(_assets(), profile='vision')

    assert first.runtime is second.runtime
    assert created == [first.runtime]
    assert coordinator.active_lease_count == 2

    first.stop()
    assert first.runtime.stop_calls == 0
    first.release()
    assert first.runtime.stop_calls == 0
    assert coordinator.active_lease_count == 1

    second.release()
    assert first.runtime.stop_calls == 1
    assert coordinator.active_lease_count == 0


def test_shared_coordinator_does_not_double_stop_after_explicit_stop():
    coordinator = LocalVisionRuntimeCoordinator(runtime_factory=FakeRuntime)
    lease = coordinator.acquire(_assets(), profile='vision')

    lease.stop()
    lease.release()

    assert lease.runtime.stop_calls == 1
    assert coordinator.active_lease_count == 0


def test_shared_coordinator_stop_is_idempotent_for_one_lease():
    coordinator = LocalVisionRuntimeCoordinator(runtime_factory=FakeRuntime)
    lease = coordinator.acquire(_assets(), profile='vision')

    lease.stop()
    lease.stop()

    assert lease.runtime.stop_calls == 1
    lease.release()

def test_shared_coordinator_rejects_acquire_after_runtime_was_stopped():
    coordinator = LocalVisionRuntimeCoordinator(runtime_factory=FakeRuntime)
    first = coordinator.acquire(_assets(), profile='vision')

    first.stop()
    with pytest.raises(RuntimeError, match='shared_runtime_stopped'):
        coordinator.acquire(_assets(), profile='vision')

    first.release()
    replacement = coordinator.acquire(_assets(), profile='vision')
    assert replacement.runtime is not first.runtime
    replacement.release()


def test_shared_coordinator_rejects_conflicting_profiles_without_spawning_second_runtime():
    created = []

    def factory(assets, **kwargs):
        runtime = FakeRuntime(assets, **kwargs)
        created.append(runtime)
        return runtime

    coordinator = LocalVisionRuntimeCoordinator(runtime_factory=factory)
    vision = coordinator.acquire(_assets(), profile='vision')

    with pytest.raises(RuntimeError, match='shared_runtime_profile_conflict'):
        coordinator.acquire(_assets(), profile='text')

    assert len(created) == 1
    vision.release()


def test_shared_coordinator_rejects_a_second_asset_set_without_spawning_second_runtime():
    created = []

    def factory(assets, **kwargs):
        runtime = FakeRuntime(assets, **kwargs)
        created.append(runtime)
        return runtime

    coordinator = LocalVisionRuntimeCoordinator(runtime_factory=factory)
    first = coordinator.acquire(_assets(), profile='vision')
    other_assets = SimpleNamespace(
        server_path='runtime/other-server.exe',
        model_path='models/other.gguf',
        projector_path='models/other-mmproj.gguf',
    )

    with pytest.raises(RuntimeError, match='shared_runtime_asset_conflict'):
        coordinator.acquire(other_assets, profile='vision')

    assert len(created) == 1
    first.release()


def test_shared_coordinator_release_is_idempotent_and_removes_last_asset():
    created = []

    def factory(assets, **kwargs):
        runtime = FakeRuntime(assets, **kwargs)
        created.append(runtime)
        return runtime

    coordinator = LocalVisionRuntimeCoordinator(runtime_factory=factory)
    first = coordinator.acquire(_assets(), profile='text')

    first.release()
    first.release()

    assert first.runtime.stop_calls == 1
    assert coordinator.active_lease_count == 0


class BlockingReadyRuntime(FakeRuntime):
    def __init__(self, assets, *, profile='vision', **kwargs):
        super().__init__(assets, profile=profile, **kwargs)
        self.start_entered = threading.Event()
        self.allow_start = threading.Event()

    def start(self):
        self.start_entered.set()
        if not self.allow_start.wait(timeout=2):
            raise TimeoutError("test_start_timeout")
        self.state = SimpleNamespace(name='ready')
        return self.state


def test_stop_then_release_during_inflight_start_stops_runtime_after_it_becomes_ready():
    created = []

    def factory(assets, **kwargs):
        runtime = BlockingReadyRuntime(assets, **kwargs)
        created.append(runtime)
        return runtime

    coordinator = LocalVisionRuntimeCoordinator(runtime_factory=factory)
    lease = coordinator.acquire(_assets(), profile='vision')
    result = {}

    thread = threading.Thread(
        target=lambda: result.setdefault('state', lease.start()),
        daemon=True,
    )
    thread.start()
    assert created[0].start_entered.wait(timeout=1)

    lease.stop()
    lease.release()
    assert coordinator.active_lease_count == 0

    created[0].allow_start.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert result['state'].name == 'ready'
    assert created[0].state.name == 'stopped'
    assert created[0].stop_calls == 2

    replacement = coordinator.acquire(_assets(), profile='vision')
    assert replacement.runtime is not created[0]
    replacement.release()
