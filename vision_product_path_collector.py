"""In-memory paired collector for fixed-image OCR product-path benchmarks."""
from __future__ import annotations

import hashlib
import ipaddress
import math
import re
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

import vision_e2e_benchmark as evaluator

REPEATS = 5
_LOCAL_PROVIDER_TOKENS = frozenset({"local", "local_gemma", "local_multimodal"})
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


def _events_from(worker: Any, *, require_provider: bool = True) -> tuple[list[dict[str, Any]], dict[str, float], str, str]:
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
    if require_provider and not provider:
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


def _is_loopback_endpoint(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 256:
        return False
    raw = value.strip()
    try:
        if "://" in raw:
            parsed = urlsplit(raw)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
            ):
                return False
            host = parsed.hostname
            _ = parsed.port
        else:
            try:
                return ipaddress.ip_address(raw).is_loopback
            except ValueError:
                host = raw.rsplit(":", 1)[0].strip("[]")
    except ValueError:
        return False
    if host == "localhost":
        return True
    try:
        return isinstance(host, str) and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False

def _warm_runtime_evidence(evidence: Any, condition: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise ValueError("runtime evidence must be a mapping")
    if evidence.get("ready") is not True:
        raise ValueError("ready must be true")
    if evidence.get("mode") != "gpu":
        raise ValueError("mode must be gpu")
    profile = condition.get("runtime_profile")
    if not isinstance(profile, str) or not profile:
        raise ValueError("condition runtime_profile must be a non-empty string")
    if evidence.get("runtime_profile") != profile:
        raise ValueError("runtime_profile must match condition")
    endpoint = evidence.get("endpoint")
    if not _is_loopback_endpoint(endpoint):
        raise ValueError("endpoint must be loopback")
    owned_pid = evidence.get("owned_pid")
    if isinstance(owned_pid, bool) or not isinstance(owned_pid, int) or owned_pid <= 0:
        raise ValueError("owned_pid must be a positive int")
    identity = condition.get("runtime_sha256")
    if not isinstance(identity, str) or not identity:
        raise ValueError("condition runtime_sha256 must be a non-empty string")
    if evidence.get("server_executable_identity") != identity:
        raise ValueError("server_executable_identity must match condition")
    if evidence.get("cache_hit") is not False:
        raise ValueError("cache_hit must be false")
    return {"ready": True, "mode": "gpu", "runtime_profile": profile,
            "endpoint": endpoint, "owned_pid": owned_pid,
            "server_executable_identity": identity, "cache_hit": False}


def _warm_events_from_observation(observation: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, float], str, str]:
    raw_events = observation.get("trace_events", ())
    if not isinstance(raw_events, (list, tuple)):
        raise ValueError("last_scan_trace events must be a sequence")
    if any(_value(event, "cache_hit", False) is not False for event in raw_events):
        raise ValueError("cache_hit must be false")
    class Trace:
        def __init__(self, items: Any) -> None:
            self.events = items
    class Observation:
        def __init__(self, items: Any) -> None:
            self.last_scan_trace = Trace(items)
    events, stages, provider, fallback = _events_from(Observation(raw_events), require_provider=False)
    final_provider = observation.get("provider")
    if final_provider != "local":
        raise ValueError("warm session provider must be local")
    provider = final_provider
    if fallback:
        raise ValueError("warm session fallback_reason must be empty")
    normalized_events: list[dict[str, Any]] = []
    for event in events:
        if event["provider"] and event["provider"] not in _LOCAL_PROVIDER_TOKENS:
            raise ValueError("warm session provider must be local")
        if event["fallback_reason"]:
            raise ValueError("warm session fallback_reason must be empty")
        if event["outcome"].lower() in {"failure", "failed", "cancelled", "canceled", "cache_hit"}:
            raise ValueError("warm session trace must not fail, cancel, or hit cache")
        if _value(event, "cache_hit", False) is not False:
            raise ValueError("cache_hit must be false")
        normalized_events.append({**event, "provider": "local"} if event["provider"] else event)
    return normalized_events, stages, provider, fallback


def _collect_warm_condition_raw(manifest: Mapping[str, Any], condition: Mapping[str, Any], *,
                                session_factory: Callable[[], Any],
                                configure_worker: Callable[[Any, Mapping[str, Any]], None],
                                image_loader: Callable[[Mapping[str, Any]], tuple[Any, bytes]],
                                residual_probe: Callable[[Any], int],
                                runtime_mode_probe: Callable[[Any], str]) -> dict[str, Any]:
    session = session_factory()
    if session is None:
        raise ValueError("session_factory returned None")
    records: list[dict[str, Any]] = []
    cold_start: dict[str, Any] = {}
    cleanup: dict[str, Any] = {}
    cleanup_evidence: Any = None
    primary_error: Exception | None = None
    close_error: Exception | None = None
    cleanup_validation_error: Exception | None = None
    try:
        started = time.perf_counter()
        evidence = _warm_runtime_evidence(session.start_cold(condition), condition)
        cold_start = {"elapsed_ms": (time.perf_counter() - started) * 1000.0,
                      "runtime_evidence": evidence}
        fingerprint = evaluator.condition_fingerprint(condition)
        cases = [case for case in evaluator.validate_manifest(manifest)
                 if case["usage_status"] in evaluator.LOCKED_USAGE]
        for case in cases:
            pixels, image_bytes = image_loader(case)
            _validate_image(case, image_bytes)
            for repeat in range(1, REPEATS + 1):
                observation = session.run_repeat(case["id"], pixels)
                if not isinstance(observation, Mapping):
                    raise ValueError("session run_repeat must return an observation mapping")
                trace_events, trace_stages, provider, fallback = _warm_events_from_observation(observation)
                stages = observation.get("stages_ms")
                if not isinstance(stages, Mapping):
                    raise ValueError("observation stages_ms must be a mapping")
                stages = {str(name): float(value) for name, value in stages.items()}
                stages.update(trace_stages)
                wall = observation.get("wall_time_ms")
                if isinstance(wall, bool) or not isinstance(wall, (int, float)) or wall < 0:
                    raise ValueError("observation wall_time_ms must be non-negative")
                stages["total"] = float(wall)
                if _warm_runtime_evidence(observation.get("runtime_evidence"), condition) != evidence:
                    raise ValueError("observation runtime evidence must match cold start")
                source, translation = observation.get("source"), observation.get("translation")
                if not isinstance(source, str) or not isinstance(translation, str):
                    raise ValueError("observation source and translation must be strings")
                records.append({"case_id": case["id"], "repeat": repeat,
                                "condition_fingerprint": fingerprint, "provider": provider,
                                "fallback_reason": fallback, "runtime_mode": evidence["mode"],
                                "residual_processes": 0, "runtime_profile": evidence["runtime_profile"], "stages_ms": stages,
                                "detected_source": source, "translation": translation,
                                "trace_events": trace_events})
    except Exception as exc:
        primary_error = exc
    finally:
        close_started = time.perf_counter()
        try:
            cleanup_evidence = session.close()
        except Exception as exc:
            close_error = exc
        if (
            not isinstance(cleanup_evidence, Mapping)
            or cleanup_evidence.get("owned_process_exited") is not True
        ):
            cleanup_validation_error = ValueError(
                "session close must prove owned_process_exited"
            )
        else:
            cleanup = {
                "elapsed_ms": (time.perf_counter() - close_started) * 1000.0,
                "owned_pid": cleanup_evidence.get("owned_pid"),
                "owned_process_exited": True,
            }
    if primary_error is not None:
        raise primary_error
    if close_error is not None:
        raise close_error
    if cleanup_validation_error is not None:
        raise cleanup_validation_error
    return {"condition": dict(condition), "records": records,
            "cold_start": cold_start, "cleanup": cleanup}


def collect_condition_raw(manifest: Mapping[str, Any], condition: Mapping[str, Any], *,
                          worker_factory: Callable[[], Any],
                          configure_worker: Callable[[Any, Mapping[str, Any]], None],
                          image_loader: Callable[[Mapping[str, Any]], tuple[Any, bytes]],
                          residual_probe: Callable[[Any], int],
                          runtime_mode_probe: Callable[[Any], str],
                          repeats: int = REPEATS,
                          session_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    """Collect exactly five fixed-image scans into an in-memory run."""
    if repeats != REPEATS:
        raise ValueError("product-path collection requires exactly 5 repeats")
    if not callable(configure_worker):
        raise TypeError("configure_worker must be callable")
    if session_factory is not None:
        if not callable(session_factory):
            raise TypeError("session_factory must be callable")
        return _collect_warm_condition_raw(
            manifest, condition, session_factory=session_factory,
            configure_worker=configure_worker, image_loader=image_loader,
            residual_probe=residual_probe, runtime_mode_probe=runtime_mode_probe)

    fingerprint = evaluator.condition_fingerprint(condition)
    cases = [case for case in evaluator.validate_manifest(manifest)
             if case["usage_status"] in evaluator.LOCKED_USAGE]
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
                residual, runtime_mode = _probe_after_cleanup(worker, residual_probe, runtime_mode_probe)
            if scan_error is not None:
                raise scan_error
            if cleanup_error is not None:
                raise cleanup_error
            stages["total"] = (time.perf_counter() - started) * 1000.0
            records.append({"case_id": case["id"], "repeat": repeat,
                            "condition_fingerprint": fingerprint, "provider": provider,
                            "fallback_reason": fallback, "runtime_mode": runtime_mode,
                            "residual_processes": residual, "runtime_profile": condition["runtime_profile"], "stages_ms": stages,
                            "detected_source": source, "translation": translation,
                            "trace_events": trace_events})
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
