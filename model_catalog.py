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
    lifecycle: str
    timeout_seconds: int
    rate_limit_bucket: str


MODEL_CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        "gemma-3-4b-it-local", "Gemma 3 4B (Local)", "gemma", "local",
        True, True, "local", 120, "local",
    ),
    ModelSpec(
        "gemma-3-1b-it", "Gemma 3 1B", "gemma", "remote",
        True, True, "stable", 30, "gemma-3-1b-it",
    ),
    ModelSpec(
        "gemma-3-27b-it", "Gemma 3 27B", "gemma", "remote",
        True, True, "stable", 30, "gemma-3-27b-it",
    ),
    ModelSpec(
        "gemma-4-26b-a4b-it", "Gemma 4 26B A4B", "gemma", "remote",
        True, True, "preview", 60, "gemma-4-26b-a4b-it",
    ),
    ModelSpec(
        "gemma-4-31b-it", "Gemma 4 31B", "gemma", "remote",
        True, True, "stable", 60, "gemma-4-31b-it",
    ),
    ModelSpec(
        "gemini-3.5-flash", "Gemini 3.5 Flash", "gemini", "remote",
        True, True, "stable", 30, "gemini-3.5-flash",
    ),
    ModelSpec(
        "gemini-2.5-pro", "Gemini 2.5 Pro", "gemini", "remote",
        True, True, "stable", 60, "gemini-2.5-pro",
    ),
    ModelSpec(
        "gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", "gemini", "remote",
        True, True, "stable", 30, "gemini-3.1-flash-lite",
    ),
    ModelSpec(
        "translategemma-4b-it-local", "TranslateGemma (Local)", "gemma", "local",
        True, True, "local", 120, "local",
    ),
)

MODEL_BY_ID = {spec.model_id: spec for spec in MODEL_CATALOG}
REMOTE_TRANSLATION_MODEL_IDS = tuple(
    spec.model_id for spec in MODEL_CATALOG if spec.locality == "remote"
)
LOCAL_MODEL_IDS = frozenset(
    spec.model_id for spec in MODEL_CATALOG if spec.locality == "local"
)
WORKER_MODEL_IDS = (
    "gemma-3-4b-it-local",
    "gemma-3-1b-it",
    "gemma-3-27b-it",
    "gemma-4-31b-it",
    "gemini-2.5-pro",
    "translategemma-4b-it-local",
)
WORKER_MODEL_CHOICES = tuple(
    (MODEL_BY_ID[model_id].display_name, model_id)
    for model_id in WORKER_MODEL_IDS
)
WORKER_DEFAULT_MODEL = "gemma-3-27b-it"
REGISTRY_DEFAULT_MODEL = WORKER_DEFAULT_MODEL


def get_model_spec(model_id: str) -> ModelSpec | None:
    return MODEL_BY_ID.get(str(model_id or "").strip())


if len(MODEL_BY_ID) != len(MODEL_CATALOG):
    raise RuntimeError("model_catalog contains duplicate model IDs")