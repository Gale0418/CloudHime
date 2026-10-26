from translation_registry import TranslationProviderRegistryConfig, build_translation_registry


def test_registry_passes_local_generation_settings_to_multimodal_provider():
    registry = build_translation_registry(
        TranslationProviderRegistryConfig(
            local_multimodal_enabled=True,
            local_multimodal_model="local-test",
            local_multimodal_base_url="http://127.0.0.1:8080/v1",
            local_runtime_validated=True,
            local_gemma_temperature=0.65,
            local_gemma_repeat_penalty=1.3,
        )
    )

    provider = registry.get("local_multimodal")
    assert provider.temperature == 0.65
    assert provider.repeat_penalty == 1.3
