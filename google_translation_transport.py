"""Bounded HTTP transport for Google's public JSON translation endpoint."""

from __future__ import annotations

import json
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from threading import Lock
from typing import List, Optional

import requests
from deep_translator import GoogleTranslator as _DeepTranslatorGoogleTranslator
from deep_translator.exceptions import RequestError, TooManyRequests, TranslationNotFound
from deep_translator.validate import is_empty, is_input_valid, request_failed


REQUEST_TIMEOUT = (5, 20)
TRANSLATE_API_URL = "https://translate.googleapis.com/translate_a/single"
MAX_RESPONSE_BYTES = 1024 * 1024
# Preserve the earlier constant for callers that inspect this transport.
MAX_HTML_BYTES = MAX_RESPONSE_BYTES
MAX_ELAPSED_SECONDS = 30.0
READ_CHUNK_BYTES = 8192
DEFAULT_429_COOLDOWN_SECONDS = 60

_cooldown_lock = Lock()
_cooldown_until = 0.0


def _retry_after_seconds(value: Optional[str], wall_time: float) -> Optional[float]:
    """Parse Retry-After as delay-seconds or an HTTP date."""
    if value is None:
        return None

    value = value.strip()
    if value.isascii() and value.isdigit():
        try:
            return float(int(value))
        except (ValueError, OverflowError):
            # A syntactically valid but unrepresentably large delay must not
            # be shortened to the fallback and retried before Google's limit.
            return float("inf")

    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, retry_at.timestamp() - wall_time)
    except (TypeError, ValueError, OverflowError):
        return None


def _cooldown_remaining(now: float) -> float:
    with _cooldown_lock:
        return max(0.0, _cooldown_until - now)


def _start_cooldown(seconds: float, now: float) -> None:
    global _cooldown_until
    with _cooldown_lock:
        # Concurrent 429 responses must never shorten an existing cooldown.
        _cooldown_until = max(_cooldown_until, now + seconds)


class GoogleTranslationResponseLimitError(RequestError):
    """Raised when Google returns a response beyond the configured budget."""


class GoogleTranslator(_DeepTranslatorGoogleTranslator):
    """Google JSON translator with scoped time, size, and cleanup bounds."""

    def __init__(
        self,
        source: str = "auto",
        target: str = "en",
        proxies: Optional[dict] = None,
        **kwargs,
    ) -> None:
        self.proxies = proxies
        super().__init__(source=source, target=target, proxies=proxies, **kwargs)
        self._base_url = TRANSLATE_API_URL

    def translate(self, text: str, **kwargs) -> str:
        if is_input_valid(text, max_chars=5000):
            text = text.strip()
            if self._same_source_target() or is_empty(text):
                return text

            if _cooldown_remaining(time.monotonic()) > 0:
                raise TooManyRequests()

            params = {
                "client": "gtx",
                "sl": self._source,
                "tl": self._target,
                "dt": "t",
                "q": text,
            }

            started = time.monotonic()
            with requests.get(
                self._base_url,
                params=params,
                proxies=self.proxies,
                timeout=REQUEST_TIMEOUT,
                stream=True,
            ) as response:
                if response.status_code == 429:
                    wall_time = time.time()
                    delay = _retry_after_seconds(
                        response.headers.get("Retry-After"), wall_time
                    )
                    if delay is None:
                        delay = DEFAULT_429_COOLDOWN_SECONDS
                    else:
                        delay = max(DEFAULT_429_COOLDOWN_SECONDS, delay)
                    _start_cooldown(delay, time.monotonic())
                    raise TooManyRequests()
                if request_failed(status_code=response.status_code):
                    raise RequestError()

                body = bytearray()
                for chunk in response.iter_content(chunk_size=READ_CHUNK_BYTES):
                    if time.monotonic() - started > MAX_ELAPSED_SECONDS:
                        raise RequestError("Google Translate response exceeded elapsed-time budget")
                    if not chunk:
                        continue
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise GoogleTranslationResponseLimitError(
                            "Google Translate response exceeded 1 MiB"
                        )
                    body.extend(chunk)

                if time.monotonic() - started > MAX_ELAPSED_SECONDS:
                    raise RequestError("Google Translate response exceeded elapsed-time budget")

                encoding = response.encoding or "utf-8"
                try:
                    payload = json.loads(bytes(body).decode(encoding))
                except (LookupError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise RequestError("Google Translate returned invalid JSON") from exc

            if not isinstance(payload, list) or not payload:
                raise RequestError("Google Translate returned an invalid response structure")
            segments = payload[0]
            if not isinstance(segments, list):
                raise RequestError("Google Translate returned an invalid response structure")
            if not segments:
                raise TranslationNotFound(text)

            translated_parts = []
            for segment in segments:
                if (
                    not isinstance(segment, list)
                    or not segment
                    or not isinstance(segment[0], str)
                ):
                    raise RequestError("Google Translate returned an invalid translation segment")
                translated_parts.append(segment[0])

            translated = "".join(translated_parts)
            if not translated.strip():
                raise TranslationNotFound(text)
            return translated

    def translate_file(self, path: str, **kwargs) -> str:
        return self._translate_file(path, **kwargs)

    def translate_batch(self, batch: List[str], **kwargs) -> List[str]:
        return self._translate_batch(batch, **kwargs)
