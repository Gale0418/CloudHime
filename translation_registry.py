from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from model_catalog import REGISTRY_DEFAULT_MODEL, REMOTE_TRANSLATION_MODEL_IDS
from translation_contracts import TranslationProvider
from translation_providers import (
    GemmaTranslationProvider,
    GoogleTranslationProvider,
    LocalMultimodalProvider,
    TranslationProviderConfig,
)
from openai_translation_provider import (
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_REASONING_EFFORT,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    OpenAITranslationProvider,
)


@dataclass(frozen=True)
class TranslationProviderRegistryConfig:
    google_api_key: str = ""
    # Singular key is the Online Gemma contract.  ``google_api_keys`` remains
    # accepted only as a legacy settings migration input; the provider keeps
    # its first usable secret and never performs multi-key routing.
    google_api_keys: Sequence[str] | Mapping[str, str] = ()
    # Metadata is deliberately secret-free.  ``google_api_key_metadata`` is
    # the historical provider-facing spelling; the credential spelling is the
    # preferred registry API.  Both are accepted for a painless migration.
    google_credential_metadata: Sequence[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]] = ()
    google_api_key_metadata: Sequence[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]] = ()
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
    openai_api_key: str = ""
    openai_enabled: bool = False
    openai_model: str = DEFAULT_OPENAI_MODEL
    openai_reasoning_effort: str = DEFAULT_OPENAI_REASONING_EFFORT
    openai_timeout_seconds: float = DEFAULT_OPENAI_TIMEOUT_SECONDS
    # Empty means the long-standing gemma -> google fallback.  A non-empty
    # chain is an explicit opt-in and may include OpenAI.
    provider_chain: Sequence[str] = ()


class TranslationProviderRegistry:
    def __init__(
        self,
        providers: Sequence[TranslationProvider],
        *,
        provider_chain: Sequence[str] | None = None,
    ):
        self._providers = {provider.name: provider for provider in providers}
        self._provider_chain = tuple(provider_chain or ())

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
        requested_chain = preferred_chain if preferred_chain is not None else self._provider_chain
        chain = [str(name).strip().lower() for name in requested_chain or [] if str(name).strip()]
        if not chain:
            chain = ["gemma", "google"]
        resolved: list[TranslationProvider] = []
        for name in chain:
            provider = self.get(name)
            if provider is not None and provider.available():
                resolved.append(provider)
        return resolved


def _has_nonempty_secret(value: Any) -> bool:
    """Return whether a legacy or multi-key setting contains a secret."""
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_has_nonempty_secret(item) for item in value.values())
    if value is None:
        return False
    try:
        return any(
            _has_nonempty_secret(item.get("secret", item.get("api_key", "")))
            if isinstance(item, Mapping)
            else _has_nonempty_secret(item)
            for item in value
        )
    except TypeError:
        return False


def _normalize_google_metadata(value: Any) -> Any:
    """Map settings-layer slot/scope names to runtime credential metadata.

    Secret values are intentionally not synthesized here; this function only
    copies non-secret descriptors and leaves provider-side secret filtering in
    place.
    """
    if value is None:
        return None
    if isinstance(value, Mapping):
        if "key_id" in value or "slot" in value or "secret" in value:
            items = [value]
        else:
            items = [dict(item, key_id=str(key_id)) for key_id, item in value.items() if isinstance(item, Mapping)]
    else:
        try:
            items = list(value)
        except TypeError:
            return None
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        descriptor = {
            key: field_value
            for key, field_value in item.items()
            if str(key).strip().casefold().replace("-", "_")
            not in {"secret", "api_key", "google_api_key"}
        }
        if descriptor.get("key_id") is None and descriptor.get("slot") is not None:
            descriptor["key_id"] = descriptor["slot"]
        if descriptor.get("quota_scope") is None and descriptor.get("scope") is not None:
            descriptor["quota_scope"] = descriptor["scope"]
        normalized.append(descriptor)
    return normalized

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


def _first_google_api_key(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        if "secret" in value or "api_key" in value:
            candidate = value.get("secret", value.get("api_key", ""))
            return candidate.strip() if isinstance(candidate, str) else ""
        values = value.values()
    else:
        try:
            values = iter(value or ())
        except TypeError:
            return ""
    for item in values:
        candidate = item.get("secret", item.get("api_key", "")) if isinstance(item, Mapping) else item
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def build_translation_registry(config: TranslationProviderRegistryConfig) -> TranslationProviderRegistry:
    providers: list[TranslationProvider] = [
        GoogleTranslationProvider(target_lang=config.target_lang),
    ]
    google_api_key = (
        config.google_api_key.strip()
        if isinstance(config.google_api_key, str) and config.google_api_key.strip()
        else _first_google_api_key(config.google_api_keys)
    )
    google_metadata = config.google_credential_metadata or config.google_api_key_metadata
    if google_api_key:
        providers.append(
            GemmaTranslationProvider(
                google_api_key=google_api_key,
                credential_metadata=_normalize_google_metadata(google_metadata),
                gemma_model=config.gemma_model,
                gemma_prompt=config.gemma_prompt,
                screenshot_gemma_prompt=config.screenshot_gemma_prompt,
                target_lang=config.target_lang,
                gemma_enabled=config.gemma_enabled,
                auto_switch_enabled=config.gemma_auto_switch_enabled,
                supported_models=config.supported_models,
            )
        )
    if config.openai_enabled and _has_nonempty_secret(config.openai_api_key):
        providers.append(
            OpenAITranslationProvider(
                openai_api_key=config.openai_api_key,
                model=config.openai_model,
                target_lang=config.target_lang,
                reasoning_effort=config.openai_reasoning_effort,
                timeout_seconds=config.openai_timeout_seconds,
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
    return TranslationProviderRegistry(providers, provider_chain=config.provider_chain)
