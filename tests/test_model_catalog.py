from __future__ import annotations

from model_catalog import (
    MODEL_BY_ID,
    MODEL_CATALOG,
    LOCAL_MODEL_IDS,
    REMOTE_TRANSLATION_MODEL_IDS,
    WORKER_MODEL_CHOICES,
    WORKER_MODEL_IDS,
    WORKER_DEFAULT_MODEL,
    REGISTRY_DEFAULT_MODEL,
    get_model_spec,
)
from translation_providers import GemmaTranslationProvider, SUPPORTED_GEMMA_MODEL_NAMES


def test_model_catalog_ids_are_unique_and_removed_ids_are_absent():
    ids = [spec.model_id for spec in MODEL_CATALOG]
    assert len(ids) == len(set(ids))
    assert "gemma-3-1b-it" not in MODEL_BY_ID
    assert get_model_spec("gemma-3-1b-it") is None
    assert "gemma-4-26b-it" not in MODEL_BY_ID
    assert "gemma-4-26b-it" not in SUPPORTED_GEMMA_MODEL_NAMES


def test_worker_and_provider_surfaces_use_catalog_models():
    assert all(model_id in MODEL_BY_ID for model_id in WORKER_MODEL_IDS)
    assert all(model_id in MODEL_BY_ID for _, model_id in WORKER_MODEL_CHOICES)
    assert all(model_id in MODEL_BY_ID for model_id in REMOTE_TRANSLATION_MODEL_IDS)
    assert all(model_id not in LOCAL_MODEL_IDS for model_id in REMOTE_TRANSLATION_MODEL_IDS)
    assert 'gemma-3-1b-it' not in REMOTE_TRANSLATION_MODEL_IDS
    assert 'gemma-3-27b-it' not in REMOTE_TRANSLATION_MODEL_IDS
    assert 'gemma-3-1b-it' not in WORKER_MODEL_IDS
    assert all(model_id != 'gemma-3-1b-it' for _, model_id in WORKER_MODEL_CHOICES)


def test_catalog_specs_expose_required_policy_fields():
    for spec in MODEL_CATALOG:
        assert spec.model_id == spec.model_id.strip()
        assert spec.display_name
        assert spec.provider in {"gemma", "gemini"}
        assert spec.locality in {"local", "remote"}
        assert spec.lifecycle in {"stable", "preview", "legacy", "local"}
        assert spec.timeout_seconds > 0
        assert spec.rate_limit_bucket
        assert get_model_spec(spec.model_id) == spec


def test_provider_supported_models_are_catalog_remote_models():
    assert tuple(SUPPORTED_GEMMA_MODEL_NAMES) == REMOTE_TRANSLATION_MODEL_IDS
    assert GemmaTranslationProvider(google_api_key="test").supported_models == REMOTE_TRANSLATION_MODEL_IDS


def test_all_remote_entrypoints_share_the_catalog_default_and_timeout_policy():
    provider = GemmaTranslationProvider(google_api_key="test")

    assert WORKER_DEFAULT_MODEL == REGISTRY_DEFAULT_MODEL
    assert provider.gemma_model == REGISTRY_DEFAULT_MODEL
    assert provider._request_timeout_seconds("gemma-4-26b-a4b-it") == get_model_spec("gemma-4-26b-a4b-it").timeout_seconds
    assert get_model_spec("gemini-3.1-flash-lite").lifecycle == "stable"

def test_invalid_model_update_returns_observable_warning_after_supported_models_change():
    provider = GemmaTranslationProvider(google_api_key="test")

    warning = provider.update_config(
        supported_models=("gemma-4-31b-it",),
        gemma_model="gemma-4-26b-a4b-it",
    )

    assert provider.gemma_model == "gemma-4-31b-it"
    assert warning == "invalid_model:gemma-4-26b-a4b-it;fallback=gemma-4-31b-it"
    assert provider.last_config_warning == warning

def test_catalog_ui_selection_and_sampling_policy_are_explicit():
    assert "translategemma-4b-it-local" not in MODEL_BY_ID
    assert WORKER_MODEL_IDS == tuple(
        spec.model_id for spec in MODEL_CATALOG if spec.ui_selectable
    )
    assert WORKER_MODEL_CHOICES == tuple(
        (spec.display_name, spec.model_id)
        for spec in MODEL_CATALOG
        if spec.ui_selectable
    )
    assert WORKER_DEFAULT_MODEL == "gemma-4-31b-it"

    gemma_3_27b = get_model_spec("gemma-3-27b-it")
    assert gemma_3_27b is not None
    assert gemma_3_27b.ui_selectable is False
    assert gemma_3_27b.lifecycle != "stable"
    assert gemma_3_27b.structured_json is False

    for spec in MODEL_CATALOG:
        assert spec.model_id != "gemma-3-1b-it"
        assert spec.accepts_sampling_params is (not spec.model_id.startswith("gemini-3."))
