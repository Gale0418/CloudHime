"""Bounded, dependency-free OpenAI model access probe."""

from __future__ import annotations

import json
import socket
import unicodedata
from dataclasses import dataclass
from http.client import HTTPException
from urllib import error, parse, request

from openai_translation_provider import DEFAULT_OPENAI_MODEL


OPENAI_MODELS_ENDPOINT = "https://api.openai.com/v1/models"
MAX_RESPONSE_BYTES = 64 * 1024


@dataclass(frozen=True)
class LunaConnectionResult:
    """A safe-to-display result that never retains request credentials."""

    status: str


class _NoRedirectHandler(request.HTTPRedirectHandler):
    """Prevent the bearer credential from being forwarded to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_status_result(status_code: int) -> str:
    if status_code == 401:
        return "invalid_key"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "model_unavailable"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code <= 599:
        return "server_error"
    return "invalid_response"


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    return isinstance(exc, error.URLError) and isinstance(exc.reason, (TimeoutError, socket.timeout))


def probe_luna_connection(
    api_key: str | None,
    *,
    timeout_seconds: float = 5,
    opener=None,
) -> LunaConnectionResult:
    """Check whether the key can retrieve the configured Luna model.

    This only verifies authentication and model access. It does not exercise
    Responses generation, text translation, or image translation.
    """

    if api_key is None or api_key == "":
        return LunaConnectionResult("no_key")
    if not isinstance(api_key, str):
        return LunaConnectionResult("invalid_key")
    if any(unicodedata.category(char) == "Cc" for char in api_key):
        return LunaConnectionResult("invalid_key")
    if not api_key.strip():
        return LunaConnectionResult("no_key")

    model_path = parse.quote(DEFAULT_OPENAI_MODEL, safe="")
    req = request.Request(
        f"{OPENAI_MODELS_ENDPOINT}/{model_path}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    transport = opener if opener is not None else request.build_opener(_NoRedirectHandler())

    try:
        response = transport.open(req, timeout=timeout_seconds)
    except error.HTTPError as exc:
        exc.close()
        return LunaConnectionResult(_http_status_result(exc.code))
    except (error.URLError, TimeoutError, socket.timeout, OSError, HTTPException) as exc:
        return LunaConnectionResult("timeout" if _is_timeout(exc) else "network_error")

    try:
        status_code = response.getcode()
        if not isinstance(status_code, int) or not 200 <= status_code <= 299:
            return LunaConnectionResult(_http_status_result(status_code) if isinstance(status_code, int) else "invalid_response")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    except (TimeoutError, socket.timeout, error.URLError, OSError, HTTPException) as exc:
        return LunaConnectionResult("timeout" if _is_timeout(exc) else "network_error")
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()

    if not isinstance(body, bytes) or len(body) > MAX_RESPONSE_BYTES:
        return LunaConnectionResult("invalid_response")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return LunaConnectionResult("invalid_response")
    if not isinstance(payload, dict) or payload.get("object") != "model" or payload.get("id") != DEFAULT_OPENAI_MODEL:
        return LunaConnectionResult("invalid_response")
    return LunaConnectionResult("verified")


__all__ = ["LunaConnectionResult", "probe_luna_connection"]
