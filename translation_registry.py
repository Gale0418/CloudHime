from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from urllib.parse import urlsplit

from model_catalog import REGISTRY_DEFAULT_MODEL, REMOTE_TRANSLATION_MODEL_IDS
from translation_contracts import TranslationProvider
from translation_providers import (
    GemmaTranslationProvider,
    GoogleTranslationProvider,
    LocalMultimodalProvider,
    TranslationProviderConfig,
)


@dataclass(frozen=True)
class TranslationProviderRegistryConfig:
    google_api_key: str = ""
    gemma_model: str = REGISTRY_DEFAULT_MODEL
    gemma_prompt: str = ""
    screenshot_gemma_prompt: str = ""
    gemma_enabled: bool = False
    gemma_auto_switch_enabled: bool = False
    target_lang: str = "zh-TW"
    supported_models: Sequence[str] = REMOTE_TRANSLATION_MODEL_IDS
    local_gemma_temperature: float = 0.2
    local_gemma_repeat_penalty: float = 1.15
    local_multimodal_enabled: bool = False
    local_multimodal_base_url: str = "http://127.0.0.1:8080/v1"
    local_multimodal_model: str = ""
    local_multimodal_timeout_seconds: int = 20
    local_runtime_validated: bool = False


class TranslationProviderRegistry:
    def __init__(self, providers: Sequence[TranslationProvider]):
        self._providers = {provider.name: provider for provider in providers}

    def register(self, name: str, provider: TranslationProvider) -> None:
        normalized = (name or "").strip().lower()
        if not normalized:
            raise ValueError("provider_name_required")
        self._providers[normalized] = provider

    def get(self, name: str) -> TranslationProvider | None:
        return self._providers.get((name or "").strip().lower())

    def available(self) -> list[str]:
        return [name for name, provider in self._providers.items() if provider.available()]

    def resolve_chain(self, preferred_chain: Sequence[str] | None = None) -> list[TranslationProvider]:
        chain = [str(name).strip().lower() for name in preferred_chain or [] if str(name).strip()]
        if not chain:
            chain = ["gemma", "google"]
        resolved: list[TranslationProvider] = []
        for name in chain:
            provider = self.get(name)
            if provider is not None and provider.available():
                resolved.append(provider)
        return resolved

def _is_validated_loopback_endpoint(value: str) -> bool:
    try:
        parsed = urlsplit((value or "").rstrip("/"))
        return (
            parsed.scheme == "http"
            and parsed.hostname == "127.0.0.1"
            and parsed.port is not None
            and parsed.path == "/v1"
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
    except (TypeError, ValueError):
        return False


def build_translation_registry(config: TranslationProviderRegistryConfig) -> TranslationProviderRegistry:
    providers: list[TranslationProvider] = [
        GoogleTranslationProvider(target_lang=config.target_lang),
    ]
    if config.google_api_key:
        providers.append(
            GemmaTranslationProvider(
                google_api_key=config.google_api_key,
                gemma_model=config.gemma_model,
                gemma_prompt=config.gemma_prompt,
                screenshot_gemma_prompt=config.screenshot_gemma_prompt,
                target_lang=config.target_lang,
                gemma_enabled=config.gemma_enabled,
                auto_switch_enabled=config.gemma_auto_switch_enabled,
                supported_models=config.supported_models,
            )
        )
    if (
        config.local_multimodal_enabled
        and config.local_multimodal_model
        and config.local_runtime_validated
        and _is_validated_loopback_endpoint(config.local_multimodal_base_url)
    ):
        providers.append(
            LocalMultimodalProvider(
                base_url=config.local_multimodal_base_url,
                model_name=config.local_multimodal_model,
                target_lang=config.target_lang,
                enabled=True,
                timeout_seconds=config.local_multimodal_timeout_seconds,
            )
        )
    return TranslationProviderRegistry(providers)
