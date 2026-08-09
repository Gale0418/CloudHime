from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path
import pytest
from vision_product_path_collector import (
    _is_loopback_endpoint,
    collect_condition_raw,
    evaluate_product_path_pair,
)

@dataclass
class Event:
    stage: str
    outcome: str
    provider: str
    fallback_reason: str
    elapsed_ms: float

class FakeWorker:
    def __init__(self, number, *, fail=False, fallback_reason=""):
        self.number, self.fail, self.fallback_reason = number, fail, fallback_reason
        self.cleanup_calls = self.scan_calls = 0
        self.cleaned = False
        self.capture_scan_area = None
        self.last_combined_text, self.last_results = "", []
        self.last_scan_trace = type("Trace", (), {"events": []})()
    def run_scan_once(self):
        self.scan_calls += 1
        image, x, y = self.capture_scan_area()
        assert (x, y) == (0, 0)
        self.captured_image = image
        if self.fail: raise RuntimeError("scan failed")
        self.last_combined_text, self.last_results = "\u539f\u6587", [("\u6b63\u78ba\u7ffb\u8b6f", 1, 2, 3, 4)]
        self.last_scan_trace.events = [Event("capture", "ok", "local", "", 2.0), Event("ocr", "ok", "local", self.fallback_reason, 3.0)]
    def cleanup(self):
        self.cleanup_calls += 1
        self.cleaned = True

def _condition(name, route):
    runtime_profile = "text" if route == "baseline" else "vision"
    return {"condition_id": name, "route": route, "model_sha256": "1"*64, "runtime_sha256": "2"*64, "prompt_sha256": "3"*64, "target": "zh-Hant", "sampling": {"temperature": 0}, "context": {"window": 4}, "gpu_mode": "gpu", "runtime_profile": runtime_profile}


@pytest.mark.parametrize(("route", "runtime_profile"), [("baseline", "text"), ("candidate", "vision")])
def test_condition_runtime_profile_tracks_route(route, runtime_profile):
    assert _condition("condition", route)["runtime_profile"] == runtime_profile

def _manifest(image_bytes):
    return {"version": 1, "cases": [{"id": "unicode-case", "source_group": "group", "image": "\u7d20\u6750/\u56fa\u5b9a.png", "image_sha256": hashlib.sha256(image_bytes).hexdigest(), "split": "test", "source_lang": "ja", "target_lang": "zh-Hant", "reference_source": "\u539f\u6587", "reference_translations": ["\u6b63\u78ba\u7ffb\u8b6f"], "required_terms": ["\u6b63\u78ba"], "source_family": "family", "annotation_revision": "r1", "usage_status": "locked_test", "ground_truth_confirmed_by_owner": True}]}

def _collect(**overrides):
    image, image_bytes, made = {"pixels": "fixed"}, b"fixed-image", []
    options = {"manifest": _manifest(image_bytes), "condition": _condition("baseline", "baseline-route"), "worker_factory": lambda: made.append(FakeWorker(len(made))) or made[-1], "configure_worker": lambda worker, condition: setattr(worker, "configured", condition["route"]), "image_loader": lambda case: (image, image_bytes), "residual_probe": lambda worker: 0, "runtime_mode_probe": lambda worker: "gpu"}
    options.update(overrides)
    return collect_condition_raw(**options), made, image

def test_fixed_pixels_call_scan_once_and_isolate_every_repeat():
    run, made, image = _collect()
    assert len(run["records"]) == 5 and len(made) == 5
    assert all(worker.scan_calls == 1 and worker.captured_image == image for worker in made)
    assert all(worker.captured_image is not image for worker in made)
    assert len({id(worker.captured_image) for worker in made}) == 5
    assert all(worker.configured == "baseline-route" for worker in made)
    assert [record["repeat"] for record in run["records"]] == [1, 2, 3, 4, 5]

def test_cleanup_on_failure_and_residual_is_probed_after_cleanup():
    made = []
    with pytest.raises(RuntimeError, match="scan failed"):
        _collect(worker_factory=lambda: made.append(FakeWorker(len(made), fail=True)) or made[-1])
    assert made[0].cleanup_calls == 1
    run, made, _ = _collect(residual_probe=lambda worker: 0 if worker.cleaned else -1)
    assert run["records"] and all(worker.cleaned for worker in made)

def test_trace_stage_sum_wall_total_and_quality_are_raw_only():
    run, _, _ = _collect()
    record = run["records"][0]
    assert record["stages_ms"]["capture"] == 2.0 and record["stages_ms"]["ocr"] == 3.0
    assert record["stages_ms"]["total"] >= 0.0
    assert record["detected_source"] == "\u539f\u6587" and record["translation"] == "\u6b63\u78ba\u7ffb\u8b6f"

@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", False),
        ("provider", 0),
        ("fallback_reason", False),
        ("fallback_reason", 0),
    ],
)
def test_trace_tokens_reject_non_string_values_before_truthiness(field, value):
    class InvalidTokenWorker(FakeWorker):
        def run_scan_once(self):
            super().run_scan_once()
            setattr(self.last_scan_trace.events[0], field, value)

    with pytest.raises(ValueError, match=field):
        _collect(worker_factory=lambda: InvalidTokenWorker(0))


def test_candidate_fallback_token_and_final_report_excludes_quality_text():
    image_bytes, made = b"fixed-image", []
    factory = lambda: made.append(FakeWorker(len(made), fallback_reason="remote_timeout")) or made[-1]
    report = evaluate_product_path_pair(_manifest(image_bytes), _condition("baseline", "baseline-route"), _condition("candidate", "candidate-route"), worker_factory=factory, configure_worker=lambda worker, condition: None, image_loader=lambda case: ({"pixels": "fixed"}, image_bytes), residual_probe=lambda worker: 0, runtime_mode_probe=lambda worker: "gpu")
    assert {record["fallback_reason"] for record in report["records"]} == {"remote_timeout"}

    assert "translation" not in report["records"][0] and "detected_source" not in report["records"][0]

def test_hash_mismatch_and_invalid_probes_are_rejected():
    with pytest.raises(ValueError, match="image_sha256"): _collect(image_loader=lambda case: ({"pixels": "fixed"}, b"wrong"))
    with pytest.raises(ValueError, match="residual"): _collect(residual_probe=lambda worker: -1)
    with pytest.raises(ValueError, match="runtime_mode"): _collect(runtime_mode_probe=lambda worker: "GPU!!")

def test_exactly_five_repeats_is_enforced():
    with pytest.raises(ValueError, match="exactly 5"): _collect(repeats=4)


def test_quality_collects_all_nonempty_translations_in_order():
    class MultiResultWorker(FakeWorker):
        def run_scan_once(self):
            super().run_scan_once()
            self.last_results = [("first", 1), ["", 2], ["second", 3], ("third",)]

    run, _, _ = _collect(worker_factory=lambda: MultiResultWorker(0))

    assert run["records"][0]["translation"] == "first\nsecond\nthird"


@pytest.mark.parametrize("bad_item", ["not-a-result", [], [123]])
def test_quality_rejects_every_malformed_result_item(bad_item):
    class MalformedResultWorker(FakeWorker):
        def run_scan_once(self):
            super().run_scan_once()
            self.last_results = [("valid",), bad_item]

    with pytest.raises(ValueError, match="last_results"):
        _collect(worker_factory=lambda: MalformedResultWorker(0))


def test_capture_rejects_pixels_without_callable_copy():
    with pytest.raises(ValueError, match="copy"):
        _collect(image_loader=lambda case: (object(), b"fixed-image"))


def test_real_scan_trace_enums_emit_plain_stage_and_outcome_values():
    from scan_pipeline import ScanOutcome, ScanStage, ScanTrace, ScanTraceEvent

    class ContractWorker(FakeWorker):
        def run_scan_once(self):
            super().run_scan_once()
            self.last_scan_trace = ScanTrace(events=(
                ScanTraceEvent(
                    stage=ScanStage.CAPTURE,
                    outcome=ScanOutcome.SUCCESS,
                    provider="local",
                    elapsed_ms=1.0,
                ),
                ScanTraceEvent(
                    stage=ScanStage.TRANSLATION,
                    outcome=ScanOutcome.SUCCESS,
                    provider="local",
                    elapsed_ms=2.0,
                ),
            ))

    run, _, _ = _collect(worker_factory=lambda: ContractWorker(0))
    record = run["records"][0]

    assert set(record["stages_ms"]) == {"capture", "translation", "total"}
    assert [event["stage"] for event in record["trace_events"]] == [
        "capture", "translation"
    ]
    assert [event["outcome"] for event in record["trace_events"]] == [
        "success", "success"
    ]


def test_cleanup_failure_still_runs_both_post_cleanup_probes():
    calls = []

    class CleanupFailureWorker(FakeWorker):
        def cleanup(self):
            self.cleaned = True
            calls.append("cleanup")
            raise RuntimeError("cleanup failed")

    def residual(worker):
        calls.append("residual")
        assert worker.cleaned
        return 0

    def runtime(worker):
        calls.append("runtime")
        assert worker.cleaned
        return "gpu"

    with pytest.raises(RuntimeError, match="cleanup failed"):
        _collect(
            worker_factory=lambda: CleanupFailureWorker(0),
            residual_probe=residual,
            runtime_mode_probe=runtime,
        )

    assert calls == ["cleanup", "residual", "runtime"]

class WarmSession(FakeWorker):
    def __init__(self, *, fail=False, evidence=None):
        super().__init__(0, fail=fail)
        self.start_cold_calls = self.close_calls = self.run_repeat_calls = 0
        self.evidence = evidence or {
            "ready": True,
            "mode": "gpu",
            "gpu_backend_confirmed": True,
            "gpu_offload_layers": 99,
            "runtime_profile": "vision",
            "endpoint": "127.0.0.1:43123",
            "owned_pid": 4242,
            "server_executable_identity": "2"*64,
            "cache_hit": False,
        }

    def start_cold(self, condition):
        self.start_cold_calls += 1
        self.started_condition = condition
        return self.evidence

    def run_repeat(self, case_id, pixels):
        self.run_repeat_calls += 1
        assert case_id == "unicode-case" and pixels is not None
        self.capture_scan_area = lambda: (pixels.copy(), 0, 0)
        self.run_scan_once()
        observation = {"case_id": case_id, "pixels_sha256": hashlib.sha256(bytes(pixels)).hexdigest(), "provider": "local", "source": self.last_combined_text, "translation": "\n".join(item[0] for item in self.last_results),
                "trace_events": self.last_scan_trace.events, "stages_ms": {"capture": 2.0, "ocr": 3.0},
                "wall_time_ms": 1.0, "runtime_evidence": self.evidence}
        self.last_observation = observation
        return observation

    def close(self):
        self.close_calls += 1
        self.cleaned = True
        return {"owned_pid": self.evidence["owned_pid"], "owned_process_exited": True}


def _warm_condition():
    return _condition("baseline", "baseline-route")


def _collect_warm(session_factory):
    return collect_condition_raw(
        _manifest(b"fixed-image"), _warm_condition(),
        worker_factory=lambda: pytest.fail("legacy worker must not be used"),
        session_factory=session_factory,
        configure_worker=lambda worker, condition: setattr(worker, "configured", condition["route"]),
        image_loader=lambda case: (bytearray(b"fixed-image"), b"fixed-image"),
        residual_probe=lambda worker: 0,
        runtime_mode_probe=lambda worker: "gpu",
    )


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("localhost", True),
        ("127.0.0.1:43123", True),
        ("http://127.0.0.1:43123/v1", True),
        ("http://localhost:43123/v1", True),
        ("http://10.0.0.1:43123/v1", False),
    ],
)
def test_loopback_endpoint_accepts_url_form_and_plain_loopback(endpoint, expected):
    assert _is_loopback_endpoint(endpoint) is expected


def test_warm_session_is_condition_scoped_and_excludes_lifecycle_from_scan_latency():
    session = WarmSession()
    run = _collect_warm(lambda: session)

    assert session.start_cold_calls == session.close_calls == 1
    assert session.run_repeat_calls == session.scan_calls == 5
    assert all(record["stages_ms"]["total"] >= 0 for record in run["records"])
    assert run["cold_start"]["runtime_evidence"] == {
        key: session.evidence[key]
        for key in (
            "ready", "mode", "runtime_profile", "endpoint", "owned_pid",
            "server_executable_identity", "cache_hit",
        )
    }
    assert session.evidence["gpu_backend_confirmed"] is True
    assert session.evidence["gpu_offload_layers"] > 0
    assert session.last_observation["case_id"] == "unicode-case"
    assert session.last_observation["pixels_sha256"] == hashlib.sha256(b"fixed-image").hexdigest()
    assert run["cleanup"]["owned_process_exited"] is True
    assert "detected_source" not in run["cold_start"]
    assert "translation" not in run["cleanup"]


def test_real_local_adapter_session_contract_integrates_with_collector():
    from vision_product_path_local_adapter import ProductPathLocalSession

    class Process:
        pid = 73
        exited = False
        def poll(self):
            return 0 if self.exited else None

    class AdapterWorker(FakeWorker):
        def __init__(self):
            super().__init__(0)
            self.process = Process()
            self.local_multimodal_provider = type(
                "Provider", (), {"clear_cache": lambda _provider: None}
            )()
            self.local_vision_runtime = type(
                "VisionRuntime", (), {"_context_size": 4096, "_gpu_layers": 99}
            )()

        def _clear_translation_memories(self):
            for name in (
                "translation_cache",
                "preferred_text_memory",
                "hud_memory",
                "exact_image_cache",
            ):
                memory = getattr(self, name, None)
                if hasattr(memory, "clear"):
                    memory.clear()

        def ensure_local_runtime_ready(self, *, timeout_seconds):
            return True

        def local_runtime_evidence(self):
            return {
                "ready": True,
                "profile": "vision",
                "mode": "gpu",
                "gpu_backend_confirmed": True,
                "gpu_offload_layers": 99,
                "base_url": "http://127.0.0.1:43123",
                "owned_process": True,
                "owned_process_handle": self.process,
                "pid": self.process.pid,
                "server_path": __file__,
            }

        def cleanup(self):
            super().cleanup()
            self.process.exited = True

    worker = AdapterWorker()
    condition = _condition("candidate", "candidate")
    condition["context"]["n_ctx"] = 4096
    condition["runtime_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    run = collect_condition_raw(
        _manifest(b"fixed-image"), condition,
        worker_factory=lambda: pytest.fail("legacy worker must not be used"),
        session_factory=lambda: ProductPathLocalSession(lambda: worker),
        configure_worker=lambda *_: pytest.fail("warm must not configure session as a worker"),
        image_loader=lambda case: (bytearray(b"fixed-image"), b"fixed-image"),
        residual_probe=lambda _: pytest.fail("warm must not use legacy residual probe"),
        runtime_mode_probe=lambda _: pytest.fail("warm must not use legacy mode probe"),
    )
    assert worker.scan_calls == 5 and worker.cleanup_calls == 1
    assert run["cleanup"]["owned_process_exited"] is True

    invalid_gpu = AdapterWorker()
    evidence = invalid_gpu.local_runtime_evidence()
    evidence["gpu_backend_confirmed"] = False
    invalid_gpu.local_runtime_evidence = lambda: evidence
    with pytest.raises(ValueError, match="ready gpu"):
        collect_condition_raw(
            _manifest(b"fixed-image"), condition,
            worker_factory=lambda: pytest.fail("legacy worker must not be used"),
            session_factory=lambda: ProductPathLocalSession(lambda: invalid_gpu),
            configure_worker=lambda *_: pytest.fail("warm must not configure session as a worker"),
            image_loader=lambda case: (bytearray(b"fixed-image"), b"fixed-image"),
            residual_probe=lambda _: pytest.fail("warm must not use legacy residual probe"),
            runtime_mode_probe=lambda _: pytest.fail("warm must not use legacy mode probe"),
        )


def test_warm_session_closes_after_scan_failure_and_rejects_invalid_runtime_evidence():
    failed = WarmSession(fail=True)
    with pytest.raises(RuntimeError, match="scan failed"):
        _collect_warm(lambda: failed)
    assert failed.close_calls == 1

    for field, value in [
        ("ready", False), ("mode", "cpu"), ("runtime_profile", "other"),
        ("endpoint", "10.0.0.1:43123"), ("owned_pid", 0),
        ("server_executable_identity", "other"), ("cache_hit", True),
    ]:
        evidence = WarmSession().evidence.copy()
        evidence[field] = value
        with pytest.raises(ValueError, match=field):
            _collect_warm(lambda evidence=evidence: WarmSession(evidence=evidence))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider", "remote", "local"),
        ("fallback_reason", "remote_timeout", "fallback_reason"),
        ("cache_hit", True, "cache_hit"),
    ],
)
def test_warm_session_rejects_nonlocal_provider_fallback_and_cache_hit_trace(
    field, value, message
):
    class InvalidTraceSession(WarmSession):
        def run_repeat(self, case_id, pixels):
            observation = super().run_repeat(case_id, pixels)
            setattr(self.last_scan_trace.events[-1], field, value)
            observation["trace_events"] = self.last_scan_trace.events
            return observation

    with pytest.raises(ValueError, match=message):
        _collect_warm(InvalidTraceSession)


def test_warm_session_preserves_scan_error_when_cleanup_evidence_is_missing():
    class ScanAndCleanupFailureSession(WarmSession):
        def run_repeat(self, case_id, pixels):
            raise RuntimeError("scan failed")

        def close(self):
            self.close_calls += 1
            raise RuntimeError("cleanup failed")

    session = ScanAndCleanupFailureSession()
    with pytest.raises(RuntimeError, match="scan failed"):
        _collect_warm(lambda: session)

    assert session.close_calls == 1


def test_warm_session_reports_cleanup_error_without_masking_it():
    class CleanupFailureSession(WarmSession):
        def close(self):
            self.close_calls += 1
            raise RuntimeError("cleanup failed")

    with pytest.raises(RuntimeError, match="cleanup failed"):
        _collect_warm(CleanupFailureSession)
