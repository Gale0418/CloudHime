from settings_store import normalize_settings_payload
from translation_registry import build_translation_registry, TranslationProviderRegistryConfig

def test_normalize_settings_payload_applies_local_multimodal_defaults():
    normalized = normalize_settings_payload({}, region_opacity=40)

    assert normalized["local_multimodal_enabled"] is False
    assert normalized["local_multimodal_base_url"] == "http://127.0.0.1:8080/v1"
    assert normalized["local_multimodal_model"] == ""
    assert normalized["local_multimodal_timeout_seconds"] == 20

def test_registry_registers_local_multimodal():
    config = TranslationProviderRegistryConfig(
        google_api_key="fake-key",
        local_multimodal_enabled=True,
        local_multimodal_model="gemma-3n-local"
    )
    registry = build_translation_registry(config)
    assert "local_multimodal" in registry._providers
    assert "gemma" in registry._providers
    assert "google" in registry._providers
