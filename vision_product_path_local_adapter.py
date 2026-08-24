"""Structured local-runtime session adapter for product-path collection."""
from __future__ import annotations

import hashlib
import ipaddress
import math
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

_LOCAL_MODEL_ID = "gemma-3-4b-it-local"
_SERVER_MODEL_NAME = "gemma-3-4b-it"
_LOCAL_PROVIDERS = {"local", "local_multimodal", "local_vision"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HASH_CHUNK_BYTES = 1024 * 1024


def _default_pixels_hash(pixels: Any) -> str:
    try:
        payload = bytes(pixels)
    except (TypeError, ValueError, OverflowError) as error:
        raise TypeError("pixels must be bytes-like") from error
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as binary:
        while True:
            chunk = binary.read(_HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _endpoint(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("runtime endpoint is required")
    raw = value.strip()
    host_port = raw.split("://", 1)[-1].split("/", 1)[0]
    host = host_port.rsplit(":", 1)[0].strip("[]")
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        raise ValueError("runtime endpoint must be loopback")
    return host_port


class ProductPathLocalSession:
    """Reuse one worker-owned local runtime for one benchmark condition."""

    def __init__(
        self,
        worker_factory: Callable[[], Any],
        *,
        timeout_seconds: int = 30,
        pixels_hash: Callable[[Any], str] = _default_pixels_hash,
        monotonic: Callable[[], float] = time.perf_counter,
        progress_callback: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> None:
        if not callable(worker_factory):
            raise TypeError("worker_factory must be callable")
        if not callable(pixels_hash):
            raise TypeError("pixels_hash must be callable")
        if not callable(monotonic):
            raise TypeError("monotonic must be callable")
        if progress_callback is not None and not callable(progress_callback):
            raise TypeError("progress_callback must be callable")
        self._worker_factory = worker_factory
        self._pixels_hash = pixels_hash
        self._monotonic = monotonic
        self._progress_callback = progress_callback
        self._progress_observer_worker: Any = None
        self._progress_observer_previous: Any = None
        self._progress_observer_previous_scan: Any = None
        self._startup_started_at: float | None = None
        self._scan_status_count = 0
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._worker: Any = None
        self._condition: dict[str, Any] | None = None
        self._owned_process: Any = None
        self._evidence: dict[str, Any] | None = None
        self._closed_evidence: dict[str, Any] | None = None

    def set_progress_callback(
        self,
        callback: Callable[[Mapping[str, Any]], None] | None,
    ) -> None:
        if callback is not None and not callable(callback):
            raise TypeError("progress_callback must be callable")
        self._progress_callback = callback
        if callback is None:
            self._remove_progress_observer()
        elif self._worker is not None:
            self._install_progress_observer(self._worker)

    def start_cold(self, condition: Mapping[str, Any]) -> dict[str, Any]:
        if self._closed_evidence is not None:
            raise RuntimeError("session is closed")
        normalized = self._validate_condition(condition)
        if self._worker is None:
            self._worker = self._worker_factory()
            if self._worker is None:
                raise ValueError("worker_factory returned None")
        elif normalized != self._condition:
            raise RuntimeError("condition change requires a new session")

        self._startup_started_at = self._monotonic()
        self._scan_status_count = 0
        self._install_progress_observer(self._worker)
        self._emit_startup_progress("ensure_started", 0)
        try:
            self._configure_worker(self._worker, normalized)
            self._require_runtime_configuration(self._worker, normalized)
            ready = self._worker.ensure_local_runtime_ready(
                timeout_seconds=self._timeout_seconds
            )
            if not isinstance(ready, bool):
                raise ValueError("ensure_local_runtime_ready must return bool")
            if not ready:
                self._emit_startup_progress("runtime_not_ready", 0)
                raise ValueError("local runtime is not ready")

            raw_evidence = self._worker.local_runtime_evidence()
            self._evidence = self._normalize_evidence(raw_evidence, normalized)
            self._condition = normalized
            self._emit_startup_progress("runtime_evidence_ready", 100)
            return dict(self._evidence)
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise

    def _install_progress_observer(self, worker: Any) -> None:
        if self._progress_callback is None:
            return
        if self._progress_observer_worker is worker:
            return
        self._remove_progress_observer()
        attr = "_product_path_local_vision_status_observer"
        previous = getattr(worker, attr, None)
        scan_attr = "_product_path_scan_status_observer"
        previous_scan = getattr(worker, scan_attr, None)
        try:
            setattr(worker, attr, self._on_worker_local_vision_status)
            setattr(worker, scan_attr, self._on_worker_scan_status)
        except Exception:
            try:
                if previous is None:
                    delattr(worker, attr)
                else:
                    setattr(worker, attr, previous)
            except Exception:
                pass
            return
        self._progress_observer_worker = worker
        self._progress_observer_previous = previous
        self._progress_observer_previous_scan = previous_scan

    def _remove_progress_observer(self) -> None:
        worker = self._progress_observer_worker
        if worker is None:
            return
        attr = "_product_path_local_vision_status_observer"
        scan_attr = "_product_path_scan_status_observer"
        try:
            try:
                if self._progress_observer_previous is None:
                    delattr(worker, attr)
                else:
                    setattr(worker, attr, self._progress_observer_previous)
            except Exception:
                pass
            try:
                if self._progress_observer_previous_scan is None:
                    delattr(worker, scan_attr)
                else:
                    setattr(worker, scan_attr, self._progress_observer_previous_scan)
            except Exception:
                pass
        finally:
            self._progress_observer_worker = None
            self._progress_observer_previous = None
            self._progress_observer_previous_scan = None

    @staticmethod
    def _safe_progress_phase(value: Any, fallback: str) -> str:
        normalized = re.sub(r"[^a-z0-9_.:-]+", "_", str(value or "").lower())[:64]
        return normalized or fallback

    def _emit_progress_event(self, event: Mapping[str, Any]) -> None:
        callback = self._progress_callback
        if callback is None:
            return
        started = self._startup_started_at
        elapsed_ms = 0.0 if started is None else max(
            0.0, (self._monotonic() - started) * 1000.0
        )
        bounded = {
            "type": str(event.get("type", "progress")),
            "phase": self._safe_progress_phase(event.get("phase"), "progress"),
            "elapsed_ms": round(elapsed_ms, 3),
        }
        if bounded["type"] == "startup":
            bounded.update({
                "progress": max(0, min(100, int(event.get("progress", 0)))),
                "total": 100,
            })
        elif bounded["type"] == "scan":
            bounded["sequence"] = max(0, int(event.get("sequence", 0)))
        try:
            callback(bounded)
        except Exception:
            # Observability must never change benchmark semantics.
            return

    def _emit_startup_progress(self, phase: str, progress: int) -> None:
        self._emit_progress_event({
            "type": "startup",
            "phase": phase,
            "progress": progress,
        })

    def _on_worker_local_vision_status(self, *args: Any) -> None:
        status = str(args[0] if args else "").strip().lower()
        if status == "progress":
            payload = str(args[1] if len(args) > 1 else "")
            raw_progress, separator, raw_phase = payload.partition("|")
            try:
                progress = int(raw_progress)
            except (TypeError, ValueError):
                progress = 0
            phase = self._safe_progress_phase(
                raw_phase if separator else "progress",
                "progress",
            )
        elif status in {"starting", "loading"}:
            progress, phase = 0, status
        elif status == "ready":
            progress, phase = 100, "ready"
        elif status in {"failed", "stopped"}:
            progress, phase = 0, status
        else:
            return
        self._emit_startup_progress(phase, progress)

    def _on_worker_scan_status(self, phase: Any = "scan_status") -> None:
        self._scan_status_count += 1
        self._emit_progress_event({
            "type": "scan",
            "phase": phase,
            "sequence": self._scan_status_count,
        })

    def run_repeat(self, case_id: str, pixels: Any) -> dict[str, Any]:
        if self._worker is None or self._evidence is None:
            raise RuntimeError("start_cold must be called before run_repeat")
        if self._closed_evidence is not None:
            raise RuntimeError("session is closed")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case_id must be a non-empty string")
        self._require_runtime_configuration(self._worker, self._condition)
        copy_pixels = getattr(pixels, "copy", None)
        if not callable(copy_pixels):
            raise ValueError("pixels must provide copy()")

        self._clear_scan_state()
        self._worker.capture_scan_area = lambda: (copy_pixels(), 0, 0)
        started = self._monotonic()
        try:
            self._worker.run_scan_once()
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise

        wall_time_ms = (self._monotonic() - started) * 1000.0
        events = tuple(
            getattr(getattr(self._worker, "last_scan_trace", None), "events", ())
        )
        self._require_local_trace(events)
        stages = self._stages_ms(events)
        stages.update(self._local_vision_timing_stages())
        source = self._source()
        translation = self._translation()
        source_available = getattr(
            self._worker,
            "_last_scan_source_available",
            None,
        )
        if source_available is None:
            source_available = bool(source.strip())
        if not isinstance(source_available, bool):
            raise ValueError("worker source availability must be boolean")
        return {
            "case_id": case_id,
            "pixels_sha256": self._pixels_hash(pixels),
            "provider": "local",
            "source": source,
            "translation": translation,
            "source_available": source_available,
            "trace_events": events,
            "stages_ms": stages,
            "runtime_metrics": dict(
                getattr(self._worker, "_last_local_vision_request_metrics", {})
                if isinstance(
                    getattr(self._worker, "_last_local_vision_request_metrics", {}),
                    Mapping,
                )
                else {}
            ),
            "wall_time_ms": wall_time_ms,
            "runtime_evidence": dict(self._evidence),
        }

    def close(self) -> dict[str, Any]:
        if self._closed_evidence is not None:
            return dict(self._closed_evidence)
        try:
            if self._worker is not None:
                self._worker.cleanup()
        finally:
            self._remove_progress_observer()
            exited = False
            if self._owned_process is not None:
                exited = self._owned_process.poll() is not None
            self._closed_evidence = {
                "owned_pid": self._evidence["owned_pid"] if self._evidence else None,
                "owned_process_exited": exited,
            }
        return dict(self._closed_evidence)

    @staticmethod
    def _validate_condition(condition: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(condition, Mapping):
            raise TypeError("condition must be a mapping")
        route = str(condition.get("route", "")).strip().lower()
        if route not in {"baseline", "candidate"}:
            raise ValueError("condition route must be baseline or candidate")
        if condition.get("cpu_only") is True:
            raise ValueError("cpu runtime is not permitted")
        if str(condition.get("gpu_mode", "")).lower() == "cpu":
            raise ValueError("cpu runtime is not permitted")
        configured_endpoint = str(condition.get("base_url", "")).strip()
        if configured_endpoint:
            raise ValueError("external endpoint is not permitted")

        runtime_sha256 = condition.get("runtime_sha256")
        if not isinstance(runtime_sha256, str) or not _SHA256.fullmatch(runtime_sha256):
            raise ValueError("condition runtime_sha256 must be 64 lowercase hex characters")

        sampling = condition.get("sampling", {})
        if not isinstance(sampling, Mapping):
            raise ValueError("condition sampling must be a mapping")
        temperature = sampling.get("temperature", 0)
        repeat_penalty = sampling.get("repeat_penalty", 1.0)
        for name, value in (
            ("temperature", temperature),
            ("repeat_penalty", repeat_penalty),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"condition {name} must be finite")
            if not math.isfinite(float(value)):
                raise ValueError(f"condition {name} must be finite")

        target = condition.get("target", "zh-Hant")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("condition target must be a non-empty string")

        context = condition.get("context")
        if not isinstance(context, Mapping):
            raise ValueError("condition context must be a mapping")
        n_ctx = context.get("n_ctx")
        if isinstance(n_ctx, bool) or not isinstance(n_ctx, int) or n_ctx <= 0:
            raise ValueError("condition context.n_ctx must be a positive integer")
        vision_image_max_width = condition.get("vision_image_max_width")
        if vision_image_max_width is not None and (
            isinstance(vision_image_max_width, bool)
            or not isinstance(vision_image_max_width, int)
            or not 640 <= vision_image_max_width <= 1536
        ):
            raise ValueError(
                "condition vision_image_max_width must be an integer "
                "between 640 and 1536"
            )
        scan_mode = str(condition.get("scan_mode", "region")).strip().lower()
        if scan_mode not in {"region", "fullscreen"}:
            raise ValueError("condition scan_mode must be region or fullscreen")
        geometry_hints = condition.get("geometry_hints", False)
        if not isinstance(geometry_hints, bool):
            raise ValueError("condition geometry_hints must be boolean")
        if geometry_hints and scan_mode != "fullscreen":
            raise ValueError("condition geometry_hints requires fullscreen scan mode")
        vision_strategy = str(condition.get("vision_strategy", "crop")).strip().lower()
        if vision_strategy not in {"crop", "crop_batch", "geometry"}:
            raise ValueError("condition vision_strategy must be crop, crop_batch, or geometry")
        if vision_strategy == "geometry" and not geometry_hints:
            raise ValueError("condition vision_strategy geometry requires geometry_hints")
        return {
            "route": route,
            "runtime_profile": "text" if route == "baseline" else "vision",
            "runtime_sha256": runtime_sha256,
            "n_ctx": n_ctx,
            "target": target.strip(),
            "temperature": float(temperature),
            "repeat_penalty": float(repeat_penalty),
            "vision_image_max_width": vision_image_max_width,
            "scan_mode": scan_mode,
            "geometry_hints": geometry_hints,
            "vision_strategy": vision_strategy,
        }

    @staticmethod
    def _require_runtime_configuration(
        worker: Any,
        condition: Mapping[str, Any],
    ) -> None:
        runtime = getattr(worker, "local_vision_runtime", None)
        if runtime is None:
            raise ValueError("worker local_vision_runtime is required")

        actual_n_ctx = getattr(runtime, "_context_size", None)
        if isinstance(actual_n_ctx, bool) or not isinstance(actual_n_ctx, int):
            raise ValueError("local vision runtime context size must be an integer")
        if actual_n_ctx != condition["n_ctx"]:
            raise ValueError(
                "benchmark context.n_ctx must match local vision runtime context size"
            )

        gpu_layers = getattr(runtime, "_gpu_layers", None)
        if isinstance(gpu_layers, bool) or not isinstance(gpu_layers, int) or gpu_layers <= 0:
            raise ValueError("local vision runtime gpu layers must be greater than zero")

    @staticmethod
    def _configure_worker(worker: Any, condition: Mapping[str, Any]) -> None:
        begin_batch = getattr(worker, "begin_translation_registry_batch", None)
        end_batch = getattr(worker, "end_translation_registry_batch", None)
        refresh = getattr(worker, "_refresh_translation_registry", None)
        has_registry = getattr(worker, "translation_registry", None) is not None
        if has_registry and not callable(refresh):
            raise RuntimeError("worker translation registry refresh is required")
        use_batch = (
            callable(refresh)
            and callable(begin_batch)
            and callable(end_batch)
        )
        if use_batch:
            begin_batch()
        try:
            worker.gemma_model = _LOCAL_MODEL_ID
            worker.active_gemma_model = _LOCAL_MODEL_ID
            worker.use_gemma_translation = True
            worker.gemma_auto_switch_enabled = False
            worker.local_multimodal_model = _SERVER_MODEL_NAME
            worker.local_multimodal_cpu_only = False
            worker.local_multimodal_enabled = condition["runtime_profile"] == "vision"
            worker.translation_target_lang = condition["target"]
            worker.local_gemma_temperature = condition["temperature"]
            worker.local_gemma_repeat_penalty = condition["repeat_penalty"]
            worker._local_vision_image_max_width = condition["vision_image_max_width"]
            worker.local_multimodal_timeout_seconds = 30
            worker.auto_threshold_enabled = False
            worker.japanese_rescue_enabled = False
            # Product-path runs must prove local-only behavior; do not inherit
            # a host Google key into the benchmark fallback chain.
            worker.google_api_key = ""
            worker.google_ocr_enabled = False
            worker.scan_mode = condition["scan_mode"]
            worker.region_render_mode = "bubble"

            worker._local_fullscreen_geometry_hint_mode = bool(condition.get("geometry_hints", False))
            worker._local_fullscreen_crop_vision_mode = (
                bool(condition.get("geometry_hints", False))
                and condition.get("vision_strategy", "crop") in {"crop", "crop_batch"}
            )
            worker._local_fullscreen_grid_direct_translate_mode = bool(condition.get("geometry_hints", False))
            worker._local_fullscreen_crop_batch_mode = (
                bool(condition.get("geometry_hints", False))
                and condition.get("vision_strategy", "crop") == "crop_batch"
            )
            chain = ["windows"] if (
                condition["route"] == "baseline"
                or bool(condition.get("geometry_hints", False))
            ) else []
            reload_backends = getattr(worker, "reload_ocr_backends", None)
            if callable(reload_backends):
                reload_backends(chain, log=False)
            else:
                worker.ocr_backend_chain = chain
                worker.ocr_backends = []
            if callable(refresh):
                refresh()
            else:
                worker._local_runtime_profile = condition["runtime_profile"]
        finally:
            if use_batch:
                end_batch()

        provider_method = getattr(worker, "get_current_ai_provider", None)
        if has_registry and not callable(provider_method):
            raise RuntimeError("worker current provider evidence is required")
        if callable(provider_method) and provider_method() not in _LOCAL_PROVIDERS:
            raise ValueError("translation registry provider must be local")
        if getattr(worker, "_local_runtime_profile", None) != condition["runtime_profile"]:
            raise ValueError("translation registry runtime profile must match condition")

    def _normalize_evidence(
        self,
        raw: Any,
        condition: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise ValueError("runtime evidence must be a mapping")
        if (
            raw.get("ready") is not True
            or raw.get("mode") != "gpu"
            or raw.get("gpu_backend_confirmed") is not True
        ):
            raise ValueError("runtime evidence must be ready gpu")
        offload_layers = raw.get("gpu_offload_layers")
        process_confirmed = raw.get("gpu_process_confirmed") is True
        if (
            isinstance(offload_layers, bool)
            or not isinstance(offload_layers, (int, float))
            or offload_layers <= 0
        ) and not process_confirmed:
            raise ValueError("runtime evidence must report gpu offload layers")
        if raw.get("profile") != condition["runtime_profile"]:
            raise ValueError("runtime profile must match condition")

        path = raw.get("server_path")
        if not isinstance(path, str) or not path:
            raise ValueError("server_path is required")
        if "ollama" in path.lower():
            raise ValueError("Ollama runtime is not permitted")

        process = raw.get("owned_process_handle")
        if process is None:
            legacy_process = raw.get("owned_process")
            if not isinstance(legacy_process, bool):
                process = legacy_process
        pid = raw.get("pid", getattr(process, "pid", None))
        valid_pid = isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
        poll = getattr(process, "poll", None)
        if not valid_pid or not callable(poll) or poll() is not None:
            raise ValueError("owned live process handle is required")

        identity = _file_sha256(path)
        if identity != condition["runtime_sha256"]:
            raise ValueError("server_executable_identity must match condition")
        self._owned_process = process
        evidence = {
            "ready": True,
            "mode": "gpu",
            "gpu_backend_confirmed": True,
            "gpu_offload_layers": offload_layers,
            "runtime_profile": condition["runtime_profile"],
            "endpoint": _endpoint(raw.get("base_url")),
            "owned_pid": pid,
            "server_executable_identity": identity,
            "cache_hit": False,
        }
        if "gpu_process_confirmed" in raw:
            evidence["gpu_process_confirmed"] = process_confirmed
        return evidence

    def _clear_scan_state(self) -> None:
        clear_worker_caches = getattr(self._worker, "_clear_translation_memories", None)
        if not callable(clear_worker_caches):
            raise RuntimeError("worker cache clear API is required for benchmark")
        provider = getattr(self._worker, "local_multimodal_provider", None)
        clear_provider_cache = getattr(provider, "clear_cache", None)
        if not callable(clear_provider_cache):
            raise RuntimeError(
                "local multimodal provider cache clear API is required for benchmark"
            )
        clear_worker_caches()
        clear_provider_cache()
        events = getattr(getattr(self._worker, "last_scan_trace", None), "events", None)
        if hasattr(events, "clear"):
            events.clear()

    @staticmethod
    def _stages_ms(events: tuple[Any, ...]) -> dict[str, float]:
        stages: dict[str, float] = {}
        for event in events:
            if isinstance(event, Mapping):
                get_value = event.get
            else:
                get_value = lambda name, default=None: getattr(event, name, default)
            raw_stage = get_value("stage", "")
            stage = str(getattr(raw_stage, "value", raw_stage)).strip()
            elapsed_ms = get_value("elapsed_ms")
            if (
                not stage
                or isinstance(elapsed_ms, bool)
                or not isinstance(elapsed_ms, (int, float))
                or not math.isfinite(float(elapsed_ms))
                or elapsed_ms < 0
            ):
                continue
            stages[stage] = stages.get(stage, 0.0) + float(elapsed_ms)
        return stages

    @staticmethod
    def _require_local_trace(events: tuple[Any, ...]) -> None:
        def trace_code(value: Any) -> str:
            raw = str(getattr(value, "value", value) or "").strip().lower()
            if not raw:
                return "none"
            if not re.fullmatch(r"[a-z0-9_-]{1,64}", raw):
                return "redacted"
            return raw

        def reject(reason: str, event: Any) -> None:
            get_value = event.get if isinstance(event, Mapping) else lambda name, default=None: getattr(event, name, default)
            details = " ".join(
                (
                    f"stage={trace_code(get_value('stage'))}",
                    f"outcome={trace_code(get_value('outcome'))}",
                    f"provider={trace_code(get_value('provider'))}",
                    f"error_code={trace_code(get_value('error_code'))}",
                    f"fallback={trace_code(get_value('fallback_reason'))}",
                    f"detail={trace_code(get_value('detail'))}",
                    f"exception={trace_code(get_value('exception_token'))}",
                )
            )
            raise ValueError(f"scan trace rejected: reason={reason} {details}")

        if not events:
            raise ValueError("scan trace is required")
        rejected_outcomes = {
            "failure",
            "failed",
            "cancelled",
            "canceled",
            "cache_hit",
        }
        for event in events:
            if isinstance(event, Mapping):
                get_value = event.get
            else:
                get_value = lambda name, default=None: getattr(event, name, default)
            provider = get_value("provider", "")
            fallback = get_value("fallback_reason", "")
            raw_stage = get_value("stage", "")
            raw_outcome = get_value("outcome", "")
            stage = str(getattr(raw_stage, "value", raw_stage)).lower()
            outcome = str(getattr(raw_outcome, "value", raw_outcome)).lower()
            if provider and provider not in _LOCAL_PROVIDERS:
                reject("non_local_provider", event)
            if fallback:
                reject("fallback", event)
            cache_hit = "cache" in stage and outcome in {"hit", "cache_hit"}
            if outcome in rejected_outcomes or cache_hit:
                reject("rejected_outcome", event)

    def _source(self) -> str:
        source = getattr(self._worker, "last_combined_text", "")
        if not isinstance(source, str):
            raise ValueError("worker source must be a string")
        return source

    def _translation(self) -> str:
        results = getattr(self._worker, "last_results", ())
        if not isinstance(results, (list, tuple)):
            raise ValueError("worker results must be a sequence")
        translations = []
        for item in results:
            if (
                isinstance(item, (list, tuple))
                and item
                and isinstance(item[0], str)
                and item[0]
            ):
                translations.append(item[0])
        return "\n".join(translations)

    def _local_vision_timing_stages(self) -> dict[str, float]:
        metrics = getattr(self._worker, "_last_local_vision_request_metrics", {})
        if not isinstance(metrics, Mapping):
            return {}
        stages = {}
        for source_key, stage_key in (
            ("prompt_ms", "vision_prompt"),
            ("predicted_ms", "vision_decode"),
        ):
            value = metrics.get(source_key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not math.isfinite(float(value)) or value < 0:
                continue
            stages[stage_key] = float(value)
        return stages
