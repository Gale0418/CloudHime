from __future__ import annotations

import builtins
from dataclasses import dataclass
import hashlib
from types import SimpleNamespace

import pytest

from vision_product_path_local_adapter import (
    ProductPathLocalSession,
    _default_pixels_hash,
)


def _runtime_sha256() -> str:
    with open(__file__, "rb") as source:
        return hashlib.sha256(source.read()).hexdigest()


def _condition(route: str = "candidate", **extra):
    runtime_sha256 = extra.pop("runtime_sha256", None)
    if runtime_sha256 is None:
        runtime_sha256 = _runtime_sha256()
    return {
        "route": route,
        "runtime_sha256": runtime_sha256,
        "target": "zh-Hant",
        "context": {"n_ctx": 4096},
        "sampling": {"temperature": 0, "repeat_penalty": 1.05},
        **extra,
    }


@dataclass
class Event:
    stage: str
    outcome: str
    provider: str
    fallback_reason: str = ""
    detail: str = ""


class Pixels:
    def __bytes__(self):
        return b"pixels"

    def copy(self):
        return Pixels()


class FakeProcess:
    pid = 73

    def __init__(self):
        self.exited = False

    def poll(self):
        return 0 if self.exited else None


class FakeRegistry:
    def __init__(self, provider):
        self.provider = provider

    def get(self, name):
        if name == "gemma":
            return self.provider
        return None


class FakeLocalMultimodalProvider:
    def __init__(self):
        self.clear_cache_calls = 0

    def clear_cache(self):
        self.clear_cache_calls += 1


class FakeWorker:
    def __init__(self, *, fail_scan: bool = False):
        self.fail_scan = fail_scan
        self.ensure_calls = []
        self.cleanup_calls = 0
        self.scan_calls = 0
        self.refresh_calls = 0
        self.batch_depth = 0
        self.batch_dirty = False
        self.refresh_profiles = []
        self.capture_scan_area = None
        self.translation_cache = {"old": "value"}
        self.preferred_text_memory = {"old": "value"}
        self.hud_memory = {"old": "value"}
        self.exact_image_cache = {"old": "value"}
        self.last_scan_trace = type("Trace", (), {"events": ["stale"]})()
        self.last_combined_text = ""
        self.last_results = []
        self.process = FakeProcess()
        self.local_vision_runtime = SimpleNamespace(_context_size=4096, _gpu_layers=999)
        self.translation_registry = FakeRegistry("remote")
        self.google_api_key = "benchmark-fixture-key"
        self._local_runtime_profile = None
        self.local_multimodal_provider = FakeLocalMultimodalProvider()
        self.clear_worker_cache_calls = 0

    def _clear_translation_memories(self):
        self.clear_worker_cache_calls += 1
        self.translation_cache.clear()
        self.preferred_text_memory.clear()
        self.hud_memory.clear()
        self.exact_image_cache.clear()

    def reload_ocr_backends(self, chain, log=False):
        self.ocr_backend_chain = list(chain)
        self.ocr_backends = ["windows"] if chain else []

    def begin_translation_registry_batch(self):
        self.batch_depth += 1

    def end_translation_registry_batch(self):
        self.batch_depth -= 1
        if self.batch_depth == 0 and self.batch_dirty:
            self.batch_dirty = False
            self._refresh_translation_registry()

    def _refresh_translation_registry(self):
        if self.batch_depth:
            self.batch_dirty = True
            return
        self.refresh_calls += 1
        profile = "vision" if self.local_multimodal_enabled else "text"
        self._local_runtime_profile = profile
        self.refresh_profiles.append(profile)
        self.translation_registry = FakeRegistry("local")

    def get_current_ai_provider(self):
        return self.translation_registry.get("gemma")

    def ensure_local_runtime_ready(self, *, timeout_seconds):
        self.ensure_calls.append(timeout_seconds)
        return True

    def local_runtime_evidence(self):
        return {
            "ready": True,
            "profile": self._local_runtime_profile,
            "mode": "gpu",
            "gpu_backend_confirmed": True,
            "gpu_offload_layers": 99,
            "base_url": "http://127.0.0.1:43123",
            "owned_process": True,
            "owned_process_handle": self.process,
            "pid": self.process.pid,
            "server_path": __file__,
        }

    def run_scan_once(self):
        self.scan_calls += 1
        pixels, x, y = self.capture_scan_area()
        assert isinstance(pixels, Pixels)
        assert (x, y) == (0, 0)
        if self.fail_scan:
            raise RuntimeError("scan failed")
        self.last_combined_text = "原文"
        self.last_results = [("翻譯", 0, 0, 1, 1)]
        self.last_scan_trace.events = [Event("vision", "success", "local")]

    def cleanup(self):
        self.cleanup_calls += 1
        self.process.exited = True


@pytest.mark.parametrize(
    ("route", "profile", "ocr_chain"),
    [("baseline", "text", ["windows"]), ("candidate", "vision", [])],
)
def test_registry_refreshes_once_with_local_provider_and_correct_profile(
    route,
    profile,
    ocr_chain,
):
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker, timeout_seconds=9)

    evidence = session.start_cold(_condition(route))

    assert evidence["runtime_profile"] == profile
    assert worker.refresh_calls == 1
    assert worker.refresh_profiles == [profile]
    assert worker.translation_registry.get("gemma") == "local"
    assert worker.get_current_ai_provider() == "local"

    assert worker.gemma_model == "gemma-3-4b-it-local"
    assert worker.active_gemma_model == "gemma-3-4b-it-local"
    assert worker.local_multimodal_model == "gemma-3-4b-it"
    assert worker.use_gemma_translation is True
    assert worker.local_multimodal_enabled is (profile == "vision")
    assert worker.scan_mode == "region"
    assert worker.translation_target_lang == "zh-Hant"
    assert worker.local_gemma_temperature == 0
    assert worker.local_gemma_repeat_penalty == 1.05
    assert worker.ocr_backend_chain == ocr_chain
    assert worker.ensure_calls == [9]
    assert worker.google_api_key == ""


def test_fullscreen_scan_mode_is_explicitly_forwarded_to_worker():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker, timeout_seconds=9)

    session.start_cold(_condition(scan_mode="fullscreen"))

    assert worker.scan_mode == "fullscreen"
    assert worker.local_multimodal_enabled is True


def test_local_vision_width_experiment_is_applied_without_changing_default():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker, timeout_seconds=9)

    session.start_cold(_condition(vision_image_max_width=896))

    assert worker._local_vision_image_max_width == 896

    default_worker = FakeWorker()
    default_session = ProductPathLocalSession(lambda: default_worker, timeout_seconds=9)
    default_session.start_cold(_condition())

    assert default_worker._local_vision_image_max_width is None


@pytest.mark.parametrize(
    ("runtime_attribute", "runtime_value", "message"),
    [
        ("_context_size", 2048, "context"),
        ("_gpu_layers", 0, "gpu layers"),
    ],
)
def test_rejects_start_when_runtime_configuration_differs_from_benchmark_condition(
    runtime_attribute,
    runtime_value,
    message,
):
    worker = FakeWorker()
    setattr(worker.local_vision_runtime, runtime_attribute, runtime_value)

    with pytest.raises(ValueError, match=message):
        ProductPathLocalSession(lambda: worker).start_cold(_condition())

    assert worker.ensure_calls == []


def test_rejects_runtime_configuration_drift_before_repeat():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())

    worker.local_vision_runtime._context_size = 2048
    with pytest.raises(ValueError, match="context"):
        session.run_repeat("case-a", Pixels())

    worker.local_vision_runtime._context_size = 4096
    worker.local_vision_runtime._gpu_layers = 0
    with pytest.raises(ValueError, match="gpu layers"):
        session.run_repeat("case-a", Pixels())

    assert worker.scan_calls == 0

def test_owned_process_handle_wins_over_boolean_owned_process():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())

    evidence = session.close()

    assert evidence == {"owned_pid": 73, "owned_process_exited": True}
    assert worker.cleanup_calls == 1


def test_boolean_owned_process_is_not_accepted_as_a_handle():
    worker = FakeWorker()
    original_evidence = worker.local_runtime_evidence

    def evidence_without_handle():
        evidence = original_evidence()
        evidence.pop("owned_process_handle")
        return evidence

    worker.local_runtime_evidence = evidence_without_handle
    with pytest.raises(ValueError, match="process handle"):
        ProductPathLocalSession(lambda: worker).start_cold(_condition())


def test_server_hash_uses_chunked_reads(monkeypatch):
    worker = FakeWorker()
    real_open = builtins.open
    read_sizes = []

    class ChunkCheckedFile:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.wrapped.__exit__(*args)

        def read(self, size=-1):
            read_sizes.append(size)
            assert size > 0
            return self.wrapped.read(size)

    expected_sha = _runtime_sha256()

    def checked_open(path, mode="r", *args, **kwargs):
        opened = real_open(path, mode, *args, **kwargs)
        if path == __file__ and mode == "rb":
            return ChunkCheckedFile(opened)
        return opened

    monkeypatch.setattr(builtins, "open", checked_open)
    ProductPathLocalSession(lambda: worker).start_cold(
        _condition(runtime_sha256=expected_sha)
    )

    assert read_sizes
    assert set(read_sizes) == {1024 * 1024}


@pytest.mark.parametrize("bad_hash", ["A" * 64, "g" * 64, "0" * 63])
def test_runtime_sha256_requires_64_lowercase_hex_characters(bad_hash):
    with pytest.raises(ValueError, match="64 lowercase hex"):
        ProductPathLocalSession(lambda: FakeWorker()).start_cold(
            _condition(runtime_sha256=bad_hash)
        )


def test_one_cold_start_and_five_warm_repeats_reuse_runtime():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())

    records = [session.run_repeat("case-a", Pixels()) for _ in range(5)]

    assert worker.ensure_calls == [30]
    assert worker.scan_calls == 5
    assert all(record["provider"] == "local" for record in records)
    assert all(record["runtime_evidence"]["runtime_profile"] == "vision" for record in records)
    assert all(record["wall_time_ms"] >= 0 for record in records)
    assert worker.translation_cache == {}
    assert worker.exact_image_cache == {}
    assert worker.clear_worker_cache_calls == 5
    assert worker.local_multimodal_provider.clear_cache_calls == 5


@pytest.mark.parametrize(
    "evidence_update",
    [
        {"gpu_backend_confirmed": False},
        {"gpu_offload_layers": 0},
    ],
)
def test_rejects_gpu_mode_without_confirmed_backend_and_offload(evidence_update):
    worker = FakeWorker()
    original_evidence = worker.local_runtime_evidence

    def insufficient_evidence():
        evidence = original_evidence()
        evidence.update(evidence_update)
        return evidence

    worker.local_runtime_evidence = insufficient_evidence

    with pytest.raises(ValueError, match="gpu"):
        ProductPathLocalSession(lambda: worker).start_cold(_condition())


def test_accepts_gpu_process_confirmation_when_server_omits_offload_marker():
    worker = FakeWorker()
    original_evidence = worker.local_runtime_evidence

    def process_confirmed_evidence():
        evidence = original_evidence()
        evidence.update({"gpu_offload_layers": 0, "gpu_process_confirmed": True})
        return evidence

    worker.local_runtime_evidence = process_confirmed_evidence
    session = ProductPathLocalSession(lambda: worker)

    evidence = session.start_cold(_condition())

    assert evidence["gpu_process_confirmed"] is True
    assert evidence["gpu_backend_confirmed"] is True


@pytest.mark.parametrize("missing_api", ["_clear_translation_memories", "clear_cache"])
def test_rejects_benchmark_when_required_cache_clear_api_is_missing(missing_api):
    worker = FakeWorker()
    if missing_api == "_clear_translation_memories":
        worker._clear_translation_memories = None
    else:
        worker.local_multimodal_provider.clear_cache = None
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())

    with pytest.raises(RuntimeError, match="cache clear"):
        session.run_repeat("case-a", Pixels())


@pytest.mark.parametrize(
    "condition",
    [
        {"cpu_only": True},
        {"base_url": "http://127.0.0.1:11434"},
        {"base_url": "http://example.test/v1"},
    ],
)
def test_rejects_cpu_or_external_endpoint_conditions(condition):
    with pytest.raises(ValueError, match="cpu|endpoint"):
        ProductPathLocalSession(lambda: FakeWorker()).start_cold(
            _condition(**condition)
        )


def test_scan_failure_still_cleans_once_and_clears_content():
    worker = FakeWorker(fail_scan=True)
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())

    with pytest.raises(RuntimeError, match="scan failed"):
        session.run_repeat("case-a", Pixels())

    assert worker.cleanup_calls == 1
    assert worker.last_combined_text == ""
    assert worker.last_results == []


def test_scan_failure_preserves_original_exception_when_close_raises():
    worker = FakeWorker(fail_scan=True)
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())

    def failing_cleanup():
        worker.cleanup_calls += 1
        raise RuntimeError("cleanup failed")

    worker.cleanup = failing_cleanup

    with pytest.raises(RuntimeError, match="scan failed"):
        session.run_repeat("case-a", Pixels())

    assert worker.cleanup_calls == 1


def test_run_repeat_captures_wall_time_before_trace_hash_and_report_work():
    elapsed_seconds = [0.0]

    def monotonic():
        return elapsed_seconds[0]

    class DelayedTrace:
        @property
        def events(self):
            elapsed_seconds[0] += 1.0
            return [Event("vision", "success", "local")]

    worker = FakeWorker()
    original_scan = worker.run_scan_once

    def scan_with_elapsed_time():
        original_scan()
        elapsed_seconds[0] += 0.5
        worker.last_scan_trace = DelayedTrace()

    def delayed_pixels_hash(_pixels):
        elapsed_seconds[0] += 10.0
        return "pixels"

    worker.run_scan_once = scan_with_elapsed_time
    session = ProductPathLocalSession(
        lambda: worker,
        monotonic=monotonic,
        pixels_hash=delayed_pixels_hash,
    )
    session.start_cold(_condition())

    observation = session.run_repeat("case-a", Pixels())

    assert observation["wall_time_ms"] == 500.0


def test_rejects_cache_hit_trace_even_when_provider_is_local():
    class CacheHitWorker(FakeWorker):
        def run_scan_once(self):
            super().run_scan_once()
            self.last_scan_trace.events = [
                Event("cache", "cache_hit", "local")
            ]

    session = ProductPathLocalSession(lambda: CacheHitWorker())
    session.start_cold(_condition())

    with pytest.raises(ValueError, match="cache"):
        session.run_repeat("case-a", Pixels())


def test_rejects_real_frame_cache_hit_enum():
    from scan_pipeline import ScanOutcome, ScanStage

    class CacheHitWorker(FakeWorker):
        def run_scan_once(self):
            super().run_scan_once()
            self.last_scan_trace.events = [
                Event(ScanStage.FRAME_CACHE, ScanOutcome.HIT, "local")
            ]

    session = ProductPathLocalSession(lambda: CacheHitWorker())
    session.start_cold(_condition())

    with pytest.raises(ValueError, match="cache"):
        session.run_repeat("case-a", Pixels())


def test_accepts_real_local_multimodal_trace_provider():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())
    worker.last_scan_trace.events = []

    original_scan = worker.run_scan_once

    def scan_with_real_provider():
        original_scan()
        worker.last_scan_trace.events = [
            Event("translation", "success", "local_multimodal")
        ]

    worker.run_scan_once = scan_with_real_provider

    observation = session.run_repeat("case-a", Pixels())

    assert observation["provider"] == "local"

class UnhashablePixels:
    def copy(self):
        return UnhashablePixels()


def test_default_pixels_hash_rejects_values_without_a_byte_representation():
    with pytest.raises(TypeError, match="bytes-like"):
        _default_pixels_hash(UnhashablePixels())


@pytest.mark.parametrize("failure", ["configuration", "readiness", "evidence"])
def test_start_cold_failure_after_worker_creation_closes_session(failure):
    worker = FakeWorker()
    if failure == "configuration":
        worker.local_vision_runtime._gpu_layers = 0
    elif failure == "readiness":
        worker.ensure_local_runtime_ready = lambda **_: False
    else:
        worker.local_runtime_evidence = lambda: {"ready": False}
    session = ProductPathLocalSession(lambda: worker)

    with pytest.raises(ValueError):
        session.start_cold(_condition())

    assert worker.cleanup_calls == 1
    assert session.close() == {"owned_pid": None, "owned_process_exited": False}
    assert worker.cleanup_calls == 1


def test_close_caches_closed_evidence_when_cleanup_raises():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())

    def failing_cleanup():
        worker.cleanup_calls += 1
        raise RuntimeError("cleanup failed")

    worker.cleanup = failing_cleanup
    with pytest.raises(RuntimeError, match="cleanup failed"):
        session.close()

    assert session.close() == {"owned_pid": 73, "owned_process_exited": False}
    assert worker.cleanup_calls == 1


def test_run_repeat_aggregates_valid_trace_stage_elapsed_ms():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())

    original_scan = worker.run_scan_once

    def scan_with_elapsed_events():
        original_scan()
        worker.last_scan_trace.events = [
            {"stage": "ocr", "elapsed_ms": 1.5, "outcome": "success", "provider": "local"},
            SimpleNamespace(stage="ocr", elapsed_ms=2, outcome="success", provider="local"),
            {"stage": "translation", "elapsed_ms": 4, "outcome": "success", "provider": "local"},
            {"stage": "ignored", "elapsed_ms": -1, "outcome": "success", "provider": "local"},
            {"stage": "ignored", "elapsed_ms": float("nan"), "outcome": "success", "provider": "local"},
            {"stage": "", "elapsed_ms": 7, "outcome": "success", "provider": "local"},
        ]

    worker.run_scan_once = scan_with_elapsed_events
    observation = session.run_repeat("case-a", Pixels())

    assert observation["stages_ms"] == {"ocr": 3.5, "translation": 4.0}


def test_run_repeat_exposes_safe_local_vision_timing_stages():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())
    original_scan = worker.run_scan_once

    def scan_with_runtime_metrics():
        original_scan()
        worker.last_scan_trace.events = [
            {
                "stage": "translation",
                "elapsed_ms": 0.0,
                "outcome": "success",
                "provider": "local",
            },
        ]
        worker._last_local_vision_request_metrics = {
            "prompt_ms": 12.5,
            "predicted_ms": 34.75,
            "prompt_tokens": 99,
        }

    worker.run_scan_once = scan_with_runtime_metrics

    observation = session.run_repeat("case-a", Pixels())

    assert observation["stages_ms"] == {
        "translation": 0.0,
        "vision_prompt": 12.5,
        "vision_decode": 34.75,
    }


def test_run_repeat_keeps_stages_ms_empty_without_valid_elapsed_values():
    worker = FakeWorker()
    session = ProductPathLocalSession(lambda: worker)
    session.start_cold(_condition())
    worker.last_scan_trace.events = []

    original_scan = worker.run_scan_once

    def scan_without_elapsed_events():
        original_scan()
        worker.last_scan_trace.events = [
            Event("ocr", "success", "local"),
            {"stage": "translation", "elapsed_ms": "fast", "outcome": "success", "provider": "local"},
        ]

    worker.run_scan_once = scan_without_elapsed_events
    observation = session.run_repeat("case-a", Pixels())

    assert observation["stages_ms"] == {}


def test_trace_rejection_reports_safe_stage_diagnostics_without_source_text():
    event = Event(
        stage="translation",
        outcome="fallback",
        provider="local",
        fallback_reason="translation_region_vision_failed",
        detail="translation_region_vision_response_json_invalid",
    )

    with pytest.raises(ValueError) as raised:
        ProductPathLocalSession._require_local_trace((event,))

    message = str(raised.value)
    assert "stage=translation" in message
    assert "outcome=fallback" in message
    assert "provider=local" in message
    assert "fallback=translation_region_vision_failed" in message
    assert "detail=translation_region_vision_response_json_invalid" in message
    assert "原文" not in message
