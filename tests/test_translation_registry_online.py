from translation_registry import (
    TranslationProviderRegistryConfig,
    build_translation_registry,
)


def test_registry_keeps_legacy_google_key_and_default_chain():
    registry = build_translation_registry(
        TranslationProviderRegistryConfig(google_api_key="legacy-google-key")
    )

    assert registry.get("gemma") is not None
    assert registry.get("gemma").google_api_keys == ("legacy-google-key",)
    assert [provider.name for provider in registry.resolve_chain()] == ["gemma", "google"]


def test_registry_migrates_first_google_key_and_builds_two_model_states():
    registry = build_translation_registry(
        TranslationProviderRegistryConfig(
            google_api_keys=("google-a", "google-b"),
            google_credential_metadata=(
                {"slot": "primary", "scope": "project-a"},
                {"slot": "secondary", "scope": "project-a"},
            ),
            gemma_model="gemma-4-26b-a4b-it",
            supported_models=("gemma-4-26b-a4b-it", "gemma-4-31b-it"),
        )
    )

    provider = registry.get("gemma")
    assert provider.google_api_key == "google-a"
    assert provider.google_api_keys == ("google-a",)
    snapshot = provider._credential_pool.snapshot()
    assert {(item["key_id"], item["model"]) for item in snapshot} == {
        ("primary", "gemma-4-26b-a4b-it"),
        ("primary", "gemma-4-31b-it"),
    }
    assert {item["quota_scope"] for item in snapshot} == {
        "custom:google:gemma-4-26b-a4b-it:project-a",
        "custom:google:gemma-4-31b-it:project-a",
    }
    assert all("google-a" not in repr(item) and "google-b" not in repr(item) for item in snapshot)


def test_registry_drops_secret_values_from_google_metadata():
    registry = build_translation_registry(
        TranslationProviderRegistryConfig(
            google_api_keys=("real-key",),
            google_credential_metadata=(
                {
                    "slot": "primary",
                    "scope": "default",
                    "secret": "metadata-secret",
                    "api_key": "metadata-api-key",
                },
            ),
        )
    )

    provider = registry.get("gemma")
    assert provider.google_api_keys == ("real-key",)
    assert "metadata-secret" not in repr(provider._credential_metadata)
    assert "metadata-api-key" not in repr(provider._credential_metadata)


def test_registry_registers_openai_only_when_explicitly_enabled():
    disabled = build_translation_registry(
        TranslationProviderRegistryConfig(openai_api_key="openai-key")
    )
    enabled = build_translation_registry(
        TranslationProviderRegistryConfig(
            openai_api_key="openai-key",
            openai_enabled=True,
            openai_model="gpt-5.6-luna",
            openai_reasoning_effort="high",
            openai_timeout_seconds=17,
            provider_chain=("openai", "gemma", "google"),
        )
    )

    assert disabled.get("openai") is None
    assert enabled.get("openai").model == "gpt-5.6-luna"
    assert enabled.get("openai").reasoning_effort == "none"
    assert enabled.get("openai").timeout_seconds == 17
    assert [provider.name for provider in enabled.resolve_chain()] == ["openai", "google"]


def test_registry_does_not_enable_openai_from_key_alone_or_default_chain():
    registry = build_translation_registry(
        TranslationProviderRegistryConfig(
            google_api_key="google-key",
            openai_api_key="openai-key",
            openai_enabled=False,
        )
    )

    assert registry.get("openai") is None
    assert [provider.name for provider in registry.resolve_chain()] == ["gemma", "google"]
