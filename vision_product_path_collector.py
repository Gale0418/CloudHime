"""In-memory paired collector for fixed-image OCR product-path benchmarks."""
from __future__ import annotations

import hashlib
import math
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

import vision_e2e_benchmark as evaluator

REPEATS = 5
_SAFE_PROVIDER = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,63}$")
_SAFE_FALLBACK = re.compile(r"^(?:[a-z0-9][a-z0-9_.:-]{0,63})?$")
_SAFE_RUNTIME = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,63}$")


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _enum_text(value: Any, label: str) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"trace {label} must be a non-empty string")
    return raw.strip()


def _safe_token(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{label} must be a safe token")
    return value


def _events_from(worker: Any) -> tuple[list[dict[str, Any]], dict[str, float], str, str]:
    trace = getattr(worker, "last_scan_trace", None)
    events = _value(trace, "events", ())
    if not isinstance(events, (list, tuple)):
        raise ValueError("last_scan_trace events must be a sequence")

    extracted: list[dict[str, Any]] = []
    stages: dict[str, float] = {}
    provider = ""
    fallback = ""
    for event in events:
        stage = _value(event, "stage")
        outcome = _value(event, "outcome")
        event_provider = _value(event, "provider", "")
        event_fallback = _value(event, "fallback_reason", "")
        elapsed = _value(event, "elapsed_ms", _value(event, "elapsed", None))
        stage = _enum_text(stage, "stage")
        outcome = _enum_text(outcome, "outcome")
        if isinstance(elapsed, bool):
            raise ValueError("trace elapsed_ms must be finite and >= 0")
        try:
            elapsed_ms = float(elapsed)
        except (TypeError, ValueError) as exc:
            raise ValueError("trace elapsed_ms must be finite and >= 0") from exc
        if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
            raise ValueError("trace elapsed_ms must be finite and >= 0")
        stage = stage.strip()
        stages[stage] = stages.get(stage, 0.0) + elapsed_ms
        if not isinstance(event_provider, str):
            raise ValueError("provider must be a safe token")
        if not isinstance(event_fallback, str):
            raise ValueError("fallback_reason must be a safe token")
        validated_provider = (
            _safe_token(event_provider, _SAFE_PROVIDER, "provider")
            if event_provider
            else ""
        )
        validated_fallback = _safe_token(
            event_fallback, _SAFE_FALLBACK, "fallback_reason"
        )
        if validated_provider:
            provider = validated_provider
        if validated_fallback:
            fallback = validated_fallback
        extracted.append({
            "stage": stage,
            "outcome": outcome,
            "provider": validated_provider,
            "fallback_reason": validated_fallback,
            "elapsed_ms": elapsed_ms,
        })
    if not provider:
        raise ValueError("trace must provide a safe provider token")
    return extracted, stages, provider, fallback


def _quality_from(worker: Any) -> tuple[str, str]:
    source = getattr(worker, "last_combined_text", "")
    results = getattr(worker, "last_results", ())
    if not isinstance(source, str):
        raise ValueError("last_combined_text must be a string")
    if not isinstance(results, (list, tuple)):
        raise ValueError("last_results must be a list or tuple")
    translations: list[str] = []
    for index, item in enumerate(results):
        if (
            not isinstance(item, (list, tuple))
            or not item
            or not isinstance(item[0], str)
        ):
            raise ValueError(
                f"last_results item {index} must contain translation text"
            )
        if item[0].strip():
            translations.append(item[0])
    return source, "\n".join(translations)


def _validate_image(case: Mapping[str, Any], image_bytes: Any) -> None:
    image_path = case.get("image")
    if not isinstance(image_path, str) or not image_path:
        raise ValueError("case image path must be a non-empty Unicode string")
    if not isinstance(image_bytes, bytes):
        raise ValueError("image_loader must return image bytes")
    expected = case.get("image_sha256")
    actual = hashlib.sha256(image_bytes).hexdigest()
    if expected != actual:
        raise ValueError("image_sha256 mismatch")


def _probe_after_cleanup(worker: Any, residual_probe: Callable[[Any], int],
                         runtime_mode_probe: Callable[[Any], str]) -> tuple[int, str]:
    residual = residual_probe(worker)
    if isinstance(residual, bool) or not isinstance(residual, int) or residual < 0:
        raise ValueError("residual_probe must return a non-negative int")
    runtime_mode = runtime_mode_probe(worker)
    return residual, _safe_token(runtime_mode, _SAFE_RUNTIME, "runtime_mode_probe")


def collect_condition_raw(
    manifest: Mapping[str, Any],
    condition: Mapping[str, Any],
    *,
    worker_factory: Callable[[], Any],
    configure_worker: Callable[[Any, Mapping[str, Any]], None],
    image_loader: Callable[[Mapping[str, Any]], tuple[Any, bytes]],
    residual_probe: Callable[[Any], int],
    runtime_mode_probe: Callable[[Any], str],
    repeats: int = REPEATS,
) -> dict[str, Any]:
    """Collect exactly five isolated fixed-image scans into an in-memory run."""
    if repeats != REPEATS:
        raise ValueError("product-path collection requires exactly 5 repeats")
    if not callable(configure_worker):
        raise TypeError("configure_worker must be callable")
    fingerprint = evaluator.condition_fingerprint(condition)
    cases = [
        case for case in evaluator.validate_manifest(manifest)
        if case["usage_status"] in evaluator.LOCKED_USAGE
    ]
    records: list[dict[str, Any]] = []

    for case in cases:
        pixels, image_bytes = image_loader(case)
        _validate_image(case, image_bytes)
        copy_pixels = getattr(pixels, "copy", None)
        if not callable(copy_pixels):
            raise ValueError("image pixels must provide a callable copy")
        for repeat in range(1, REPEATS + 1):
            worker = worker_factory()
            if worker is None:
                raise ValueError("worker_factory returned None")
            started = time.perf_counter()
            scan_error: Exception | None = None
            trace_events: list[dict[str, Any]] = []
            stages: dict[str, float] = {}
            provider = fallback = ""
            source = translation = ""
            try:
                configure_worker(worker, condition)
                worker.capture_scan_area = lambda: (copy_pixels(), 0, 0)
                worker.run_scan_once()
                trace_events, stages, provider, fallback = _events_from(worker)
                source, translation = _quality_from(worker)
            except Exception as exc:
                scan_error = exc
            finally:
                cleanup_error: Exception | None = None
                try:
                    worker.cleanup()
                except Exception as exc:
                    cleanup_error = exc
                residual, runtime_mode = _probe_after_cleanup(
                    worker, residual_probe, runtime_mode_probe
                )
            if scan_error is not None:
                raise scan_error
            if cleanup_error is not None:
                raise cleanup_error
            stages["total"] = (time.perf_counter() - started) * 1000.0
            records.append({
                "case_id": case["id"],
                "repeat": repeat,
                "condition_fingerprint": fingerprint,
                "provider": provider,
                "fallback_reason": fallback,
                "runtime_mode": runtime_mode,
                "residual_processes": residual,
                "stages_ms": stages,
                "detected_source": source,
                "translation": translation,
                "trace_events": trace_events,
            })
    return {"condition": dict(condition), "records": records}


def evaluate_product_path_pair(
    manifest: Mapping[str, Any],
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    **collector_kwargs: Any,
) -> dict[str, Any]:
    """Collect both conditions and return only evaluator's redacted paired report."""
    baseline_raw = collect_condition_raw(manifest, baseline, **collector_kwargs)
    candidate_raw = collect_condition_raw(manifest, candidate, **collector_kwargs)
    return evaluator.evaluate_paired(manifest, baseline_raw, candidate_raw)
