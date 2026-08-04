"""Small, dependency-free owner of translation fallback routing."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from translation_contracts import TranslationResult


class TranslationOrchestrationError(RuntimeError):
    """A bounded route failure that never retains raw provider messages."""

    def __init__(
        self,
        code: str,
        *,
        primary_exception: str = "",
        fallback_exception: str = "",
    ) -> None:
        self.code = str(code or "translation_failed")
        self.primary_exception = str(primary_exception or "")[:64]
        self.fallback_exception = str(fallback_exception or "")[:64]
        super().__init__(self.code)


class TranslationCancelled(TranslationOrchestrationError):
    def __init__(self) -> None:
        super().__init__("translation_cancelled")


def _exception_token(exception: BaseException | None) -> str:
    if exception is None:
        return ""
    name = getattr(type(exception), "__name__", "UnknownError")
    return name[:64] if name.isidentifier() else "UnknownError"


def _as_result(value: TranslationResult | str, provider: str) -> TranslationResult:
    if isinstance(value, TranslationResult):
        return value
    return TranslationResult(text=str(value or ""), provider=provider)


def attribute_fallback(
    result: TranslationResult,
    *,
    requested_provider: str,
    fallback_provider: str,
    fallback_reason: str,
) -> TranslationResult:
    """Attach route lineage while preserving provider-owned cache/model metadata."""
    actual_provider = result.provider or fallback_provider
    return replace(
        result,
        provider=actual_provider,
        requested_provider=result.requested_provider or requested_provider,
        fallback_reason=result.fallback_reason or fallback_reason,
    )


class TranslationOrchestrator:
    """Execute one preferred provider chain without owning provider internals."""

    def __init__(self, *, fallback_exceptions: tuple[type[BaseException], ...] = (Exception,)):
        self._fallback_exceptions = fallback_exceptions

    @staticmethod
    def _raise_if_cancelled(cancelled: Callable[[], bool] | None) -> None:
        if cancelled is not None and cancelled():
            raise TranslationCancelled()

    def execute(
        self,
        *,
        requested_provider: str,
        primary: Callable[[], TranslationResult | str],
        fallback_provider: str = "",
        fallback: Callable[[], TranslationResult | str] | None = None,
        fallback_reason: str = "provider_error",
        cancelled: Callable[[], bool] | None = None,
    ) -> TranslationResult:
        self._raise_if_cancelled(cancelled)
        primary_exception: BaseException | None = None
        try:
            result = _as_result(primary(), requested_provider)
            if not result.text:
                raise ValueError("empty_translation")
            self._raise_if_cancelled(cancelled)
            return result
        except TranslationCancelled:
            raise
        except self._fallback_exceptions as exc:
            primary_exception = exc

        if fallback is None:
            raise TranslationOrchestrationError(
                "translation_provider_failed",
                primary_exception=_exception_token(primary_exception),
            )

        self._raise_if_cancelled(cancelled)
        try:
            fallback_result = _as_result(fallback(), fallback_provider)
            if not fallback_result.text:
                raise ValueError("empty_translation")
            self._raise_if_cancelled(cancelled)
        except TranslationCancelled:
            raise
        except Exception as exc:
            raise TranslationOrchestrationError(
                "translation_fallback_failed",
                primary_exception=_exception_token(primary_exception),
                fallback_exception=_exception_token(exc),
            ) from None

        return attribute_fallback(
            fallback_result,
            requested_provider=requested_provider,
            fallback_provider=fallback_provider,
            fallback_reason=fallback_reason,
        )