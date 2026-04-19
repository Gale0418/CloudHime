from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from translation_contracts import TranslationProvider
from translation_providers import (
    GemmaTranslationProvider,
    GoogleTranslationProvider,
    TranslationProviderConfig,
)


@dataclass(frozen=True)
class TranslationProviderRegistryConfig:
    google_api_key: str = ""
    gemma_model: str = "gemma-3-27b-it"
    gemma_enabled: bool = False
    gemma_auto_switch_enabled: bool = False
    target_lang: str = "zh-TW"
    supported_models: Sequence[str] = ("gemma-3-27b-it", "gemma-4-31b-it")


class TranslationProviderRegistry:
    def __init__(self, providers: Sequence[TranslationProvider]):
        self._providers = {provider.name: provider for provider in providers}

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


def build_translation_registry(config: TranslationProviderRegistryConfig) -> TranslationProviderRegistry:
    providers: list[TranslationProvider] = [
        GoogleTranslationProvider(target_lang=config.target_lang),
    ]
    if config.google_api_key and config.gemma_enabled:
        providers.insert(
            0,
            GemmaTranslationProvider(
                google_api_key=config.google_api_key,
                gemma_model=config.gemma_model,
                target_lang=config.target_lang,
                auto_switch_enabled=config.gemma_auto_switch_enabled,
                supported_models=config.supported_models,
            ),
        )
    return TranslationProviderRegistry(providers)
