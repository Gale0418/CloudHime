from __future__ import annotations
import hashlib
from dataclasses import dataclass
import pytest
from vision_product_path_collector import collect_condition_raw, evaluate_product_path_pair

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
    return {"condition_id": name, "route": route, "model_sha256": "1"*64, "runtime_sha256": "2"*64, "prompt_sha256": "3"*64, "target": "zh-Hant", "sampling": {"temperature": 0}, "context": {"window": 4}, "gpu_mode": "gpu"}

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