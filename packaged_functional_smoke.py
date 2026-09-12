"""Run the functional Vision smoke from the frozen CloudHime executable."""

from __future__ import annotations

import json
import os
from pathlib import Path
import threading
from typing import Any, Callable, Mapping


PACKAGED_FUNCTIONAL_SMOKE_ENV = "CLOUDHIME_PACKAGED_FUNCTIONAL_SMOKE"
PACKAGED_KNOWLEDGE_SMOKE_ENV = "CLOUDHIME_PACKAGED_KNOWLEDGE_SMOKE"
PACKAGED_SMOKE_RESULT_PATH_ENV = "CLOUDHIME_PACKAGED_SMOKE_RESULT_PATH"
PACKAGED_KNOWLEDGE_TITLE_ENV = "CLOUDHIME_PACKAGED_KNOWLEDGE_TITLE"
PACKAGED_KNOWLEDGE_MODEL_ENV = "CLOUDHIME_PACKAGED_KNOWLEDGE_MODEL"
PACKAGED_KNOWLEDGE_SOURCE_URLS_ENV = "CLOUDHIME_PACKAGED_KNOWLEDGE_SOURCE_URLS"
PACKAGED_KNOWLEDGE_OPENAI_KEY_ENV = "CLOUDHIME_PACKAGED_KNOWLEDGE_OPENAI_KEY"
PACKAGED_KNOWLEDGE_GOOGLE_KEY_ENV = "CLOUDHIME_PACKAGED_KNOWLEDGE_GOOGLE_KEY"
PACKAGED_SMOKE_RUNTIME_DIR_ENV = "CLOUDHIME_PACKAGED_SMOKE_RUNTIME_DIR"
PACKAGED_SMOKE_MODEL_PATH_ENV = "CLOUDHIME_PACKAGED_SMOKE_MODEL_PATH"
PACKAGED_SMOKE_PROJECTOR_PATH_ENV = "CLOUDHIME_PACKAGED_SMOKE_PROJECTOR_PATH"
PACKAGED_SMOKE_IMAGE_PATH_ENV = "CLOUDHIME_PACKAGED_SMOKE_IMAGE_PATH"
PACKAGED_SMOKE_REQUIRE_GPU_ENV = "CLOUDHIME_PACKAGED_SMOKE_REQUIRE_GPU"
PACKAGED_SMOKE_FORCE_CPU_ENV = "CLOUDHIME_PACKAGED_SMOKE_FORCE_CPU"
PACKAGED_SMOKE_TIMEOUT_ENV = "CLOUDHIME_PACKAGED_SMOKE_TIMEOUT_SECONDS"
PACKAGED_SMOKE_STARTUP_TIMEOUT_ENV = "CLOUDHIME_PACKAGED_SMOKE_STARTUP_TIMEOUT_SECONDS"
PACKAGED_SMOKE_CONTEXT_SIZE_ENV = "CLOUDHIME_PACKAGED_SMOKE_CONTEXT_SIZE"
PACKAGED_SMOKE_GPU_LAYERS_ENV = "CLOUDHIME_PACKAGED_SMOKE_GPU_LAYERS"


def _env_text(environ: Mapping[str, str], name: str) -> str:
    value = str(environ.get(name, "") or "").strip()
    if not value:
        raise ValueError(f"missing_{name.lower()}")
    return value


def _env_bool(environ: Mapping[str, str], name: str) -> bool:
    value = str(environ.get(name, "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_int(environ: Mapping[str, str], name: str, default: int) -> int:
    value = str(environ.get(name, "") or "").strip()
    if not value:
        return default
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"invalid_{name.lower()}")
    return parsed


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the result machine-readable without persisting OCR/model text."""
    keys = (
        "runtime_mode",
        "evaluation_mode",
        "image_count",
        "case_count",
        "successful_images",
        "successful_cases",
        "request_success_images",
        "request_success_cases",
    )
    summary: dict[str, Any] = {
        "schema_version": 1,
        "status": "passed",
    }
    for key in keys:
        value = result.get(key, "")
        if key.endswith("_count") or key.endswith("_images") or key.endswith("_cases"):
            try:
                value = int(value or 0)
            except (TypeError, ValueError):
                value = 0
        summary[key] = value
    return summary


def _write_result(path: str, payload: Mapping[str, Any]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _run_knowledge_smoke(environment: Mapping[str, str]) -> dict[str, Any]:
    """Exercise frozen Research dependencies while persisting only redacted counts."""
    from knowledge_extraction import parse_extraction_response, validate_extraction_payload
    from knowledge_research_service import KnowledgeResearchService

    title = _env_text(environment, PACKAGED_KNOWLEDGE_TITLE_ENV)
    model_name = _env_text(environment, PACKAGED_KNOWLEDGE_MODEL_ENV)
    raw_urls = str(environment.get(PACKAGED_KNOWLEDGE_SOURCE_URLS_ENV, "") or "").strip()
    source_urls = None
    if raw_urls:
        decoded = json.loads(raw_urls)
        if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
            raise ValueError("invalid_packaged_knowledge_source_urls")
        source_urls = decoded

    service = KnowledgeResearchService(
        google_api_key=str(environment.get(PACKAGED_KNOWLEDGE_GOOGLE_KEY_ENV, "") or ""),
        openai_api_key=str(environment.get(PACKAGED_KNOWLEDGE_OPENAI_KEY_ENV, "") or ""),
        model_name=model_name,
    )
    cancel_event = threading.Event()
    draft = service.build_research_draft(
        title,
        cancel_event,
        source_urls=source_urls,
    )
    raw = service.extract_candidate(draft, cancel_event)
    allowed_source_ids = [
        source.get("source_id", "")
        for source in draft.get("sources", [])
        if isinstance(source, dict) and source.get("status") == "read"
    ]
    candidate = validate_extraction_payload(
        parse_extraction_response(raw),
        allowed_source_ids=allowed_source_ids,
        expected_title=title,
    )
    return {
        "schema_version": 1,
        "status": "passed",
        "smoke_kind": "knowledge_research",
        "source_mode": draft.get("source_mode", "search"),
        "source_count": len(draft.get("sources", [])),
        "readable_source_count": len(allowed_source_ids),
        "alias_count": len(candidate["aliases"]),
        "entry_count": len(candidate["entries"]),
        "model_name": model_name,
    }


def run_packaged_functional_smoke(
    *,
    environ: Mapping[str, str] | None = None,
    runner: Callable[..., Mapping[str, Any]] | None = None,
) -> int | None:
    """Return an exit code when opted in, otherwise ``None`` for normal GUI startup."""
    environment = os.environ if environ is None else environ
    vision_enabled = str(environment.get(PACKAGED_FUNCTIONAL_SMOKE_ENV, "")).strip() == "1"
    knowledge_enabled = str(environment.get(PACKAGED_KNOWLEDGE_SMOKE_ENV, "")).strip() == "1"
    if not vision_enabled and not knowledge_enabled:
        return None

    result_path = str(environment.get(PACKAGED_SMOKE_RESULT_PATH_ENV, "") or "").strip()
    try:
        if not result_path:
            raise ValueError("missing_packaged_smoke_result_path")
        if vision_enabled and knowledge_enabled:
            raise ValueError("conflicting_packaged_smoke_modes")
        if knowledge_enabled:
            _write_result(result_path, _run_knowledge_smoke(environment))
            return 0

        runtime_dir = _env_text(environment, PACKAGED_SMOKE_RUNTIME_DIR_ENV)
        model_path = _env_text(environment, PACKAGED_SMOKE_MODEL_PATH_ENV)
        projector_path = _env_text(environment, PACKAGED_SMOKE_PROJECTOR_PATH_ENV)
        image_path = _env_text(environment, PACKAGED_SMOKE_IMAGE_PATH_ENV)
        if runner is None:
            from release_functional_smoke import run_release_smoke

            runner = run_release_smoke
        result = runner(
            runtime_dir,
            model_path,
            projector_path,
            image_path,
            require_gpu=_env_bool(environment, PACKAGED_SMOKE_REQUIRE_GPU_ENV),
            force_cpu=_env_bool(environment, PACKAGED_SMOKE_FORCE_CPU_ENV),
            timeout_seconds=_env_int(environment, PACKAGED_SMOKE_TIMEOUT_ENV, 120),
            startup_timeout_seconds=_env_int(
                environment, PACKAGED_SMOKE_STARTUP_TIMEOUT_ENV, 90
            ),
            context_size=_env_int(environment, PACKAGED_SMOKE_CONTEXT_SIZE_ENV, 4096),
            gpu_layers=_env_int(environment, PACKAGED_SMOKE_GPU_LAYERS_ENV, 999),
        )
        _write_result(result_path, _summary(result))
        return 0
    except Exception:
        if result_path:
            try:
                _write_result(
                    result_path,
                    {
                        "error_code": "packaged_functional_smoke_failed",
                        "schema_version": 1,
                        "status": "failed",
                    },
                )
            except OSError:
                pass
        return 2
