"""Pure, bounded-error validation for OpenAI Responses envelopes and JSON.

Explicit failure/incomplete/refusal metadata always wins over nonempty text.
Missing status is accepted for existing compact adapters, not treated as proof
that a remote provider has completed a request.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import math
from typing import Any


def require_complete_response(response: Mapping[str, Any]) -> None:
    """Reject partial or refused output before a direct output_text shortcut."""
    if not isinstance(response, Mapping):
        raise ValueError("openai_response_schema_invalid")
    if response.get("error") is not None:
        raise ValueError("openai_response_failed")
    if "status" in response and response["status"] != "completed":
        raise ValueError("openai_response_incomplete")
    if response.get("incomplete_details") is not None:
        raise ValueError("openai_response_incomplete")
    if "output" not in response:
        return
    output = response["output"]
    if not isinstance(output, list):
        raise ValueError("openai_response_schema_invalid")
    for item in output:
        if not isinstance(item, Mapping):
            raise ValueError("openai_response_schema_invalid")
        if "status" in item and item["status"] != "completed":
            raise ValueError("openai_response_incomplete")
        if item.get("type") == "refusal":
            raise ValueError("openai_response_refused")
        content = item.get("content", [])
        if not isinstance(content, list):
            raise ValueError("openai_response_schema_invalid")
        for block in content:
            if not isinstance(block, Mapping):
                raise ValueError("openai_response_schema_invalid")
            if block.get("type") == "refusal":
                raise ValueError("openai_response_refused")


def _finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("json_number_not_finite")
    return value


def _reject_constant(_token: str) -> None:
    raise ValueError("json_constant_invalid")


def load_strict_json(text: str) -> Any:
    """Reject NaN, Infinity and overflowing exponents, including nested values."""
    return json.loads(text, parse_float=_finite_float, parse_constant=_reject_constant)
