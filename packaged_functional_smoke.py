"""Run the functional Vision smoke from the frozen CloudHime executable."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping


PACKAGED_FUNCTIONAL_SMOKE_ENV = "CLOUDHIME_PACKAGED_FUNCTIONAL_SMOKE"
PACKAGED_SMOKE_RESULT_PATH_ENV = "CLOUDHIME_PACKAGED_SMOKE_RESULT_PATH"
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


def run_packaged_functional_smoke(
    *,
    environ: Mapping[str, str] | None = None,
    runner: Callable[..., Mapping[str, Any]] | None = None,
) -> int | None:
    """Return an exit code when opted in, otherwise ``None`` for normal GUI startup."""
    environment = os.environ if environ is None else environ
    if str(environment.get(PACKAGED_FUNCTIONAL_SMOKE_ENV, "")).strip() != "1":
        return None

    result_path = str(environment.get(PACKAGED_SMOKE_RESULT_PATH_ENV, "") or "").strip()
    try:
        runtime_dir = _env_text(environment, PACKAGED_SMOKE_RUNTIME_DIR_ENV)
        model_path = _env_text(environment, PACKAGED_SMOKE_MODEL_PATH_ENV)
        projector_path = _env_text(environment, PACKAGED_SMOKE_PROJECTOR_PATH_ENV)
        image_path = _env_text(environment, PACKAGED_SMOKE_IMAGE_PATH_ENV)
        if not result_path:
            raise ValueError("missing_packaged_smoke_result_path")

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
