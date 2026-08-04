"""Pure, dependency-free value contracts for scan pipeline observability.

Trace values deliberately retain only bounded, structured diagnostic tokens.  They
never retain OCR text, prompts, credentials, endpoints, image payloads, or raw
exception messages.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from enum import Enum
import math
import re
from typing import Final


MAX_TRACE_EVENTS: Final = 64
MAX_DETAIL_LENGTH: Final = 256
MAX_PROVIDER_LENGTH: Final = 128
MAX_FALLBACK_REASON_LENGTH: Final = 160
MAX_EXCEPTION_TOKEN_LENGTH: Final = 64
MAX_ELAPSED_MS: Final = 86_400_000.0
MAX_ITEM_COUNT: Final = 1_000_000
_REDACTED: Final = "redacted"
_SENSITIVE_VALUE = re.compile(
    r"(?:api[_ -]?key|authorization|bearer|token|secret|password|prompt|"
    r"https?://|base[_ -]?url|(?:^|[\s:=])sk-[a-z0-9_-]+|b['\"])",
    re.IGNORECASE,
)
_SAFE_DIAGNOSTIC = re.compile(
    r"(?:capture|frame_cache|ocr|translation|render_dispatch|cache|backend|"
    r"fallback|retry|pipeline|dispatch)_[a-z0-9_.:-]+|no_text",
)
_SAFE_PROVIDER = re.compile(r"[a-z][a-z0-9_.-]*", re.IGNORECASE)
_SAFE_EXCEPTION_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class ScanStage(str, Enum):
    CAPTURE = "capture"
    FRAME_CACHE = "frame_cache"
    OCR = "ocr"
    TRANSLATION = "translation"
    RENDER_DISPATCH = "render_dispatch"


class ScanOutcome(str, Enum):
    SUCCESS = "success"
    HIT = "hit"
    MISS = "miss"
    FALLBACK = "fallback"
    FAILURE = "failure"
    NO_TEXT = "no_text"
    CANCELLED = "cancelled"


class ScanErrorCode(str, Enum):
    NONE = "none"
    CAPTURE_FAILED = "capture_failed"
    FRAME_CACHE_FAILED = "frame_cache_failed"
    OCR_FAILED = "ocr_failed"
    TRANSLATION_FAILED = "translation_failed"
    RENDER_DISPATCH_FAILED = "render_dispatch_failed"
    SCAN_CANCELLED = "scan_cancelled"
    UNEXPECTED = "unexpected"


def safe_exception_token(exception: BaseException | type[BaseException] | None) -> str:
    """Return only a bounded exception class token; never inspect its message."""
    if exception is None:
        return ""
    exception_type = exception if isinstance(exception, type) else type(exception)
    name = getattr(exception_type, "__name__", "UnknownError")
    match = _SAFE_EXCEPTION_NAME.fullmatch(name)
    return (match.group(0) if match else "UnknownError")[:MAX_EXCEPTION_TOKEN_LENGTH]


def _safe_diagnostic(value: object, limit: int) -> str:
    if value is None or value == "":
        return ""
    text = str(value)
    if _SENSITIVE_VALUE.search(text) or not _SAFE_DIAGNOSTIC.fullmatch(text):
        return _REDACTED
    return text[:limit]


def _safe_provider(value: object) -> str:
    if value is None or value == "":
        return ""
    text = str(value)
    if _SENSITIVE_VALUE.search(text) or not _SAFE_PROVIDER.fullmatch(text):
        return _REDACTED
    return text[:MAX_PROVIDER_LENGTH]


@dataclass(frozen=True, slots=True)
class ScanTraceEvent:
    """A single safe, structured pipeline observation."""

    stage: ScanStage
    outcome: ScanOutcome
    error_code: ScanErrorCode = ScanErrorCode.NONE
    detail: str = ""
    provider: str = ""
    fallback_reason: str = ""
    elapsed_ms: float = 0.0
    item_count: int = 0
    exception_token: str = field(default="", init=False)
    exception: InitVar[BaseException | type[BaseException] | None] = None

    def __post_init__(
        self, exception: BaseException | type[BaseException] | None
    ) -> None:
        object.__setattr__(self, "stage", ScanStage(self.stage))
        object.__setattr__(self, "outcome", ScanOutcome(self.outcome))
        object.__setattr__(self, "error_code", ScanErrorCode(self.error_code))
        object.__setattr__(self, "detail", _safe_diagnostic(self.detail, MAX_DETAIL_LENGTH))
        object.__setattr__(self, "provider", _safe_provider(self.provider))
        object.__setattr__(
            self,
            "fallback_reason",
            _safe_diagnostic(self.fallback_reason, MAX_FALLBACK_REASON_LENGTH),
        )
        try:
            elapsed_ms = float(self.elapsed_ms)
        except (TypeError, ValueError):
            elapsed_ms = 0.0
        if not math.isfinite(elapsed_ms):
            elapsed_ms = 0.0
        object.__setattr__(self, "elapsed_ms", min(MAX_ELAPSED_MS, max(0.0, elapsed_ms)))
        try:
            item_count = int(self.item_count)
        except (TypeError, ValueError):
            item_count = 0
        object.__setattr__(self, "item_count", min(MAX_ITEM_COUNT, max(0, item_count)))
        object.__setattr__(self, "exception_token", safe_exception_token(exception))


@dataclass(frozen=True, slots=True)
class ScanTrace:
    """An immutable, bounded event trace with no global stage-order constraint."""

    events: tuple[ScanTraceEvent, ...] = ()
    dropped_events: int = 0

    def __post_init__(self) -> None:
        events = tuple(self.events)
        if any(not isinstance(event, ScanTraceEvent) for event in events):
            raise TypeError("events must contain ScanTraceEvent values")
        overflow = max(0, len(events) - MAX_TRACE_EVENTS)
        object.__setattr__(self, "events", events[overflow:])
        object.__setattr__(self, "dropped_events", max(0, int(self.dropped_events)) + overflow)

    def append(self, event: ScanTraceEvent) -> "ScanTrace":
        """Return a new trace, retaining the newest 64 events."""
        if not isinstance(event, ScanTraceEvent):
            raise TypeError("event must be a ScanTraceEvent")
        return ScanTrace(self.events + (event,), self.dropped_events)