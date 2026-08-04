from urllib import error

import pytest

from translation_contracts import TranslationResult
from translation_orchestrator import (
    TranslationCancelled,
    TranslationOrchestrationError,
    TranslationOrchestrator,
)


def test_primary_result_keeps_actual_provider_and_cache_attribution():
    orchestrator = TranslationOrchestrator()
    cached = TranslationResult(
        text="譯文",
        provider="google",
        from_cache=True,
        requested_provider="local_gemma",
        fallback_reason="bad_translation",
    )

    result = orchestrator.execute(
        requested_provider="local_gemma",
        primary=lambda: cached,
    )

    assert result == cached


def test_expected_primary_failure_uses_fallback_with_route_attribution():
    orchestrator = TranslationOrchestrator(fallback_exceptions=(error.URLError,))
    calls = []

    result = orchestrator.execute(
        requested_provider="gemma",
        primary=lambda: (_ for _ in ()).throw(error.URLError("private OCR text")),
        fallback_provider="google",
        fallback=lambda: calls.append("fallback") or TranslationResult(
            text="譯文",
            provider="google",
            from_cache=True,
        ),
        fallback_reason="provider_error",
    )

    assert calls == ["fallback"]
    assert result.text == "譯文"
    assert result.provider == "google"
    assert result.from_cache is True
    assert result.requested_provider == "gemma"
    assert result.fallback_reason == "provider_error"


def test_unexpected_programming_error_is_not_masked_by_fallback():
    orchestrator = TranslationOrchestrator(fallback_exceptions=(ValueError,))

    with pytest.raises(TypeError, match="programming bug"):
        orchestrator.execute(
            requested_provider="gemma",
            primary=lambda: (_ for _ in ()).throw(TypeError("programming bug")),
            fallback_provider="google",
            fallback=lambda: TranslationResult(text="譯文", provider="google"),
        )


def test_cancelled_route_never_calls_provider_or_fallback():
    orchestrator = TranslationOrchestrator()
    calls = []

    with pytest.raises(TranslationCancelled) as captured:
        orchestrator.execute(
            requested_provider="gemma",
            primary=lambda: calls.append("primary"),
            fallback_provider="google",
            fallback=lambda: calls.append("fallback"),
            cancelled=lambda: True,
        )

    assert calls == []
    assert str(captured.value) == "translation_cancelled"


def test_double_failure_exposes_only_bounded_error_code():
    secret = "OCR_SECRET api-key=SECRET prompt=PRIVATE"
    orchestrator = TranslationOrchestrator(fallback_exceptions=(ValueError,))

    with pytest.raises(TranslationOrchestrationError) as captured:
        orchestrator.execute(
            requested_provider="gemma",
            primary=lambda: (_ for _ in ()).throw(ValueError(secret)),
            fallback_provider="google",
            fallback=lambda: (_ for _ in ()).throw(RuntimeError(secret)),
        )

    rendered = repr(captured.value) + str(captured.value)
    assert captured.value.code == "translation_fallback_failed"
    assert captured.value.primary_exception == "ValueError"
    assert captured.value.fallback_exception == "RuntimeError"
    assert secret not in rendered