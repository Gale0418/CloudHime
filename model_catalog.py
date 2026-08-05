"""Single source of truth for CloudHime model capabilities and policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    provider: str
    locality: str
    multimodal: bool
    structured_json: bool
    ui_selectable: bool
    accepts_sampling_params: bool
    lifecycle: str
    timeout_seconds: int
    rate_limit_bucket: str


MODEL_CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        "gemma-3-4b-it-local", "Gemma 3 4B (Local)", "gemma", "local",
        True, True, True, True, "local", 120, "local",
    ),
    ModelSpec(
        "gemma-3-1b-it", "Gemma 3 1B", "gemma", "remote",
        False, True, False, True, "legacy", 30, "gemma-3-1b-it",
    ),
    ModelSpec(
        "gemma-3-27b-it", "Gemma 3 27B", "gemma", "remote",
        True, True, False, True, "legacy", 30, "gemma-3-27b-it",
    ),
    ModelSpec(
        "gemma-4-26b-a4b-it", "Gemma 4 26B A4B", "gemma", "remote",
        True, True, True, True, "stable", 60, "gemma-4-26b-a4b-it",
    ),
    ModelSpec(
        "gemma-4-31b-it", "Gemma 4 31B", "gemma", "remote",
        True, True, True, True, "stable", 60, "gemma-4-31b-it",
    ),
    ModelSpec(
        "gemini-3.6-flash", "Gemini 3.6 Flash", "gemini", "remote",
        True, True, True, False, "stable", 30, "gemini-3.6-flash",
    ),
    ModelSpec(
        "gemini-3.5-flash", "Gemini 3.5 Flash", "gemini", "remote",
        True, True, True, False, "stable", 30, "gemini-3.5-flash",
    ),
    ModelSpec(
        "gemini-2.5-pro", "Gemini 2.5 Pro", "gemini", "remote",
        True, True, True, True, "stable", 60, "gemini-2.5-pro",
    ),
    ModelSpec(
        "gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", "gemini", "remote",
        True, True, True, False, "stable", 30, "gemini-3.1-flash-lite",
    ),
)

MODEL_BY_ID = {spec.model_id: spec for spec in MODEL_CATALOG}
REMOTE_TRANSLATION_MODEL_IDS = tuple(
    spec.model_id
    for spec in MODEL_CATALOG
    if spec.locality == "remote" and spec.lifecycle != "legacy"
)
LOCAL_MODEL_IDS = frozenset(
    spec.model_id for spec in MODEL_CATALOG if spec.locality == "local"
)
WORKER_MODEL_IDS = tuple(
    spec.model_id for spec in MODEL_CATALOG if spec.ui_selectable
)
WORKER_MODEL_CHOICES = tuple(
    (spec.display_name, spec.model_id)
    for spec in MODEL_CATALOG
    if spec.ui_selectable
)
WORKER_DEFAULT_MODEL = "gemma-4-31b-it"
REGISTRY_DEFAULT_MODEL = WORKER_DEFAULT_MODEL


def get_model_spec(model_id: str) -> ModelSpec | None:
    return MODEL_BY_ID.get(str(model_id or "").strip())


if len(MODEL_BY_ID) != len(MODEL_CATALOG):
    raise RuntimeError("model_catalog contains duplicate model IDs")