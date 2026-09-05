"""Dependency-free OpenAI Responses translation provider.

The provider deliberately keeps the transport small and synchronous.  Runtime
code can decide whether and how to retry the bounded errors emitted here.
"""

from __future__ import annotations

import json
import math
import socket
from collections.abc import Mapping, Sequence
from typing import Any, Callable
from urllib import error, request

from responses_contract import load_strict_json, require_complete_response
from translation_contracts import TranslationResult
from translation_helpers import clean_model_output_multiline, split_translated_lines
from vision_region import (
    VisionRegionResult,
    build_region_vision_prompt,
    parse_region_vision_response,
)


OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
MAX_OPENAI_RESPONSE_BYTES = 8 * 1024 * 1024
DEFAULT_OPENAI_REASONING_EFFORT = "none"
SUPPORTED_OPENAI_REASONING_EFFORTS = frozenset({"none"})


class OpenAIRequestCancelled(RuntimeError):
    """A request was cancelled before dispatch or after response parsing."""


class OpenAITranslationProvider:
    name = "openai"

    def __init__(
        self,
        *,
        openai_api_key: str = "",
        api_key: str | None = None,
        model: str = DEFAULT_OPENAI_MODEL,
        target_lang: str = "zh-TW",
        timeout_seconds: float = DEFAULT_OPENAI_TIMEOUT_SECONDS,
        max_response_bytes: int = MAX_OPENAI_RESPONSE_BYTES,
        reasoning_effort: str = DEFAULT_OPENAI_REASONING_EFFORT,
    ) -> None:
        # ``api_key`` is accepted as a small convenience for callers that use
        # provider-neutral configuration.  Never include either value in repr.
        self.openai_api_key = (api_key if api_key is not None else openai_api_key or "").strip()
        self.model = (model or DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
        self.target_lang = (target_lang or "zh-TW").strip() or "zh-TW"
        normalized_effort = str(reasoning_effort or "").strip().casefold()
        self.reasoning_effort = (
            normalized_effort
            if normalized_effort in SUPPORTED_OPENAI_REASONING_EFFORTS
            else DEFAULT_OPENAI_REASONING_EFFORT
        )
        try:
            timeout = float(timeout_seconds)
        except (TypeError, ValueError, OverflowError):
            timeout = DEFAULT_OPENAI_TIMEOUT_SECONDS
        if not math.isfinite(timeout):
            timeout = DEFAULT_OPENAI_TIMEOUT_SECONDS
        self.timeout_seconds = max(0.1, min(timeout, 600.0))
        try:
            size_limit = int(max_response_bytes)
        except (TypeError, ValueError, OverflowError):
            size_limit = MAX_OPENAI_RESPONSE_BYTES
        self.max_response_bytes = max(1, min(size_limit, MAX_OPENAI_RESPONSE_BYTES))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(model={self.model!r}, "
            f"target_lang={self.target_lang!r}, timeout_seconds={self.timeout_seconds!r}, "
            f"reasoning_effort={self.reasoning_effort!r})"
        )

    def available(self) -> bool:
        return bool(self.openai_api_key)

    @staticmethod
    def _check_cancel(cancel_predicate: Callable[[], bool] | None) -> None:
        if cancel_predicate is not None and cancel_predicate():
            raise OpenAIRequestCancelled("openai_request_cancelled")

    @staticmethod
    def _http_error_token(status: Any) -> str:
        if isinstance(status, int) and status in {400, 401, 403, 404, 429}:
            return f"openai_http_{status}"
        if isinstance(status, int) and 500 <= status <= 599:
            return "openai_http_5xx"
        return "openai_http_error"

    def _read_response(
        self, response: Any, *, cancel_predicate: Callable[[], bool] | None = None,
    ) -> bytes:
        # Read in bounded chunks so a broken/malicious endpoint cannot exhaust
        # process memory before JSON validation gets a chance to run.
        chunks: list[bytes] = []
        remaining = self.max_response_bytes + 1
        while remaining > 0:
            self._check_cancel(cancel_predicate)
            try:
                chunk = response.read(min(64 * 1024, remaining))
            except TypeError:
                # A few lightweight test doubles (and old urllib wrappers)
                # expose ``read()`` without the optional size argument.
                chunk = response.read()
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            chunks.append(bytes(chunk))
            remaining -= len(chunk)
        self._check_cancel(cancel_predicate)
        body = b"".join(chunks)
        if len(body) > self.max_response_bytes:
            raise ValueError("openai_response_too_large")
        return body

    def _request(
        self,
        payload: Mapping[str, Any],
        *,
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        if not self.available():
            raise ValueError("openai_api_key_missing")
        self._check_cancel(cancel_predicate)
        req = request.Request(
            OPENAI_RESPONSES_ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = self._read_response(response, cancel_predicate=cancel_predicate)
        except error.HTTPError as exc:
            token = self._http_error_token(getattr(exc, "code", None))
            try:
                exc.close()
            except Exception:
                pass
            raise ValueError(token) from None
        except (TimeoutError, socket.timeout):
            raise ValueError("openai_timeout") from None
        except error.URLError:
            raise ValueError("openai_transport_error") from None

        try:
            decoded = load_strict_json(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ValueError("openai_response_invalid_json") from None
        if not isinstance(decoded, dict):
            raise ValueError("openai_response_schema_invalid")
        self._check_cancel(cancel_predicate)
        return decoded

    @staticmethod
    def _image_and_text_content(
        image_parts: Sequence[Mapping[str, Any]] | None,
        prompt: str,
    ) -> list[dict[str, str]]:
        content: list[dict[str, str]] = [{"type": "input_text", "text": prompt}]
        for part in image_parts or ():
            if not isinstance(part, Mapping):
                raise ValueError("openai_image_part_invalid")
            inline_data = part.get("inline_data")
            if isinstance(inline_data, Mapping):
                data = inline_data.get("data")
                if not isinstance(data, str) or not data:
                    raise ValueError("openai_image_part_invalid")
                mime_type = inline_data.get("mime_type", "image/png")
                if not isinstance(mime_type, str) or not mime_type:
                    raise ValueError("openai_image_part_invalid")
                content.append({
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{data}",
                })
                continue
            if part.get("type") == "input_image" and isinstance(part.get("image_url"), str):
                content.append({"type": "input_image", "image_url": part["image_url"]})
                continue
            if isinstance(part.get("text"), str):
                content.append({"type": "input_text", "text": part["text"]})
                continue
            raise ValueError("openai_image_part_invalid")
        return content

    def _build_payload(
        self,
        prompt: str,
        *,
        image_parts: Sequence[Mapping[str, Any]] | None = None,
        max_output_tokens: int = 1024,
        text_format: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "store": False,
            "reasoning": {"effort": self.reasoning_effort},
            "input": [{"role": "user", "content": self._image_and_text_content(image_parts, prompt)}],
            "max_output_tokens": max(1, min(int(max_output_tokens), 16384)),
        }
        if text_format is not None:
            payload["text"] = {"format": dict(text_format)}
        return payload

    @staticmethod
    def _extract_output_text(response: Mapping[str, Any]) -> str:
        require_complete_response(response)
        direct = response.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        if direct is not None and not isinstance(direct, str):
            raise ValueError("openai_response_schema_invalid")
        output = response.get("output")
        if not isinstance(output, list):
            raise ValueError("openai_empty_response" if "output_text" in response else "openai_response_schema_invalid")
        texts: list[str] = []
        for item in output:
            if not isinstance(item, Mapping):
                raise ValueError("openai_response_schema_invalid")
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, Mapping):
                    raise ValueError("openai_response_schema_invalid")
                if block.get("type") == "output_text":
                    text = block.get("text")
                    if not isinstance(text, str):
                        raise ValueError("openai_response_schema_invalid")
                    texts.append(text)
        joined = "\n".join(texts)
        if not joined.strip():
            raise ValueError("openai_empty_response")
        return joined

    @classmethod
    def _matches_schema(cls, value: Any, schema: Mapping[str, Any]) -> bool:
        """Validate the small JSON-Schema subset used by response formats."""
        if not isinstance(schema, Mapping):
            return False
        if "enum" in schema and value not in schema["enum"]:
            return False
        schema_type = schema.get("type")
        if schema_type == "object":
            if not isinstance(value, dict):
                return False
            required = schema.get("required")
            if required is not None and not isinstance(required, list):
                return False
            if any(key not in value for key in (required or ())):
                return False
            properties = schema.get("properties", {})
            if not isinstance(properties, Mapping):
                return False
            if schema.get("additionalProperties") is False and any(key not in properties for key in value):
                return False
            return all(
                key not in value or isinstance(child_schema, Mapping) and cls._matches_schema(value[key], child_schema)
                for key, child_schema in properties.items()
            )
        if schema_type == "array":
            if not isinstance(value, list):
                return False
            item_schema = schema.get("items")
            return item_schema is None or isinstance(item_schema, Mapping) and all(
                cls._matches_schema(item, item_schema) for item in value
            )
        if schema_type == "string":
            return isinstance(value, str)
        if schema_type == "number":
            return (isinstance(value, (int, float)) and not isinstance(value, bool)
                    and (not isinstance(value, float) or math.isfinite(value)))
        if schema_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if schema_type == "boolean":
            return isinstance(value, bool)
        if schema_type == "null":
            return value is None
        return schema_type is None

    def _complete(
        self,
        prompt: str,
        *,
        image_parts: Sequence[Mapping[str, Any]] | None = None,
        max_output_tokens: int = 1024,
        text_format: Mapping[str, Any] | None = None,
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> str:
        payload = self._build_payload(
            prompt,
            image_parts=image_parts,
            max_output_tokens=max_output_tokens,
            text_format=text_format,
        )
        response = self._request(payload, cancel_predicate=cancel_predicate)
        raw_text = self._extract_output_text(response)
        self._check_cancel(cancel_predicate)
        return raw_text

    def translate(
        self,
        text: str,
        *,
        source_lang: str = "auto",
        target_lang: str | None = None,
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> TranslationResult:
        normalized = clean_model_output_multiline(text).strip() if text else ""
        if not normalized:
            return TranslationResult(text="", provider=self.name, model=self.model)
        resolved_target = target_lang or self.target_lang
        prompt = (
            f"Translate the following text from {source_lang or 'auto'} to {resolved_target}.\n"
            "Return translation only, preserving meaning and line breaks.\n\n"
            f"Text:\n{normalized}"
        )
        raw_text = self._complete(prompt, max_output_tokens=1024, cancel_predicate=cancel_predicate)
        translated = clean_model_output_multiline(raw_text).strip()
        if not translated:
            raise ValueError("openai_empty_response")
        return TranslationResult(text=translated, provider=self.name, model=self.model, raw_text=raw_text)

    def translate_batch(
        self,
        texts: Sequence[str],
        *,
        source_lang: str = "auto",
        target_lang: str | None = None,
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> list[TranslationResult]:
        normalized = [clean_model_output_multiline(text).strip() if text else "" for text in texts]
        if not normalized or any(not text for text in normalized):
            return []
        resolved_target = target_lang or self.target_lang
        numbered = "\n".join(f"{index}: {value}" for index, value in enumerate(normalized))
        prompt = (
            f"Translate each numbered line from {source_lang or 'auto'} to {resolved_target}. "
            "Return exactly one translated line per input line, preserving numbering order, "
            "without numbers or commentary.\n\n"
            f"Input lines:\n{numbered}"
        )
        raw_text = self._complete(prompt, max_output_tokens=min(4096, max(1024, len(normalized) * 256)), cancel_predicate=cancel_predicate)
        translated = split_translated_lines(raw_text, len(normalized))
        if len(translated) != len(normalized):
            raise ValueError("openai_batch_response_schema_invalid")
        return [TranslationResult(text=line, provider=self.name, model=self.model, raw_text=raw_text) for line in translated]

    def translate_multimodal(
        self,
        texts: Sequence[str],
        image_parts: Sequence[Mapping[str, Any]],
        *,
        target_lang: str | None = None,
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> list[TranslationResult]:
        if not texts:
            return []
        if not image_parts:
            raise ValueError("missing_image_context")
        normalized = [clean_model_output_multiline(text).strip() if text else "" for text in texts]
        if any(not text for text in normalized):
            return []
        resolved_target = target_lang or self.target_lang
        prompt = (
            f"Translate each supplied text line to {resolved_target}, using the image as visual context. "
            "Return exactly one translated line per input line, with no commentary.\n\n"
            "Text lines:\n" + "\n".join(f"{i}: {value}" for i, value in enumerate(normalized))
        )
        raw_text = self._complete(
            prompt,
            image_parts=image_parts,
            max_output_tokens=min(4096, max(1024, len(normalized) * 256)),
            cancel_predicate=cancel_predicate,
        )
        translated = split_translated_lines(raw_text, len(normalized))
        if len(translated) != len(normalized):
            raise ValueError("openai_multimodal_response_schema_invalid")
        return [TranslationResult(text=line, provider=self.name, model=self.model, raw_text=raw_text) for line in translated]

    def transcribe_screenshot(
        self,
        image_parts: Sequence[Mapping[str, Any]],
        *,
        source_text_hint: str | None = None,
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> TranslationResult:
        if not image_parts:
            raise ValueError("missing_image_context")
        prompt = (
            "Read every visible line in the attached image exactly as shown. "
            "Return OCR text only and preserve line breaks."
        )
        if source_text_hint:
            prompt += f"\nOCR hint (may be wrong):\n{str(source_text_hint)[:1200]}"
        raw_text = self._complete(prompt, image_parts=image_parts, max_output_tokens=2048, cancel_predicate=cancel_predicate)
        transcription = clean_model_output_multiline(raw_text).strip()
        if not transcription:
            raise ValueError("openai_empty_response")
        return TranslationResult(text=transcription, provider=self.name, model=self.model, raw_text=raw_text)

    def translate_screenshot(
        self,
        image_parts: Sequence[Mapping[str, Any]],
        *,
        target_lang: str | None = None,
        source_text_hint: str | None = None,
        debug_log: Callable[[str], None] | None = None,
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> TranslationResult:
        if not image_parts:
            raise ValueError("missing_image_context")
        resolved_target = target_lang or self.target_lang
        prompt = (
            f"Translate all readable text in the attached image to {resolved_target}. "
            "The image is the source of truth. Return translation only, preserving reading order."
        )
        if source_text_hint:
            prompt += f"\nOCR hint (may be wrong):\n{str(source_text_hint)[:1200]}"
        raw_text = self._complete(prompt, image_parts=image_parts, max_output_tokens=2048, cancel_predicate=cancel_predicate)
        translated = clean_model_output_multiline(raw_text).strip()
        if debug_log is not None:
            debug_log(f"[openai screenshot] model={self.model} raw_len={len(raw_text)} cleaned_len={len(translated)}")
        if not translated:
            raise ValueError("openai_empty_response")
        return TranslationResult(text=translated, provider=self.name, model=self.model, raw_text=raw_text)

    def interpret_regions(
        self,
        image_parts: Sequence[Mapping[str, Any]],
        hints: Sequence[Mapping[str, Any]],
        *,
        image_width: int,
        image_height: int,
        target_lang: str | None = None,
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> list[VisionRegionResult]:
        if not image_parts:
            raise ValueError("missing_image_context")
        if not hints:
            raise ValueError("missing_region_hints")
        resolved_target = target_lang or self.target_lang
        prompt = build_region_vision_prompt(
            hints,
            image_width=image_width,
            image_height=image_height,
            target_lang=resolved_target,
        )
        schema = {
            "type": "json_schema",
            "name": "region_translations",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "regions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "id": {"type": "integer"},
                                "source_text": {"type": "string"},
                                "translation": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                            "required": ["id", "source_text", "translation", "confidence"],
                        },
                    }
                },
                "required": ["regions"],
            },
        }
        raw_text = self._complete(
            prompt,
            image_parts=image_parts,
            max_output_tokens=min(4096, max(768, len(hints) * 256 + 256)),
            text_format=schema,
            cancel_predicate=cancel_predicate,
        )
        results = parse_region_vision_response(raw_text, allowed_ids=[hint["id"] for hint in hints])
        if len(results) != len(hints):
            raise ValueError("openai_response_region_mismatch")
        self._check_cancel(cancel_predicate)
        return results

    def generate_structured_text(
        self,
        prompt: str,
        *,
        max_output_tokens: int = 4096,
        temperature: float = 0.1,
        schema: Mapping[str, Any] | None = None,
        schema_name: str = "structured_response",
        cancel_predicate: Callable[[], bool] | None = None,
    ) -> str:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            raise ValueError("knowledge_prompt_empty")
        if schema is not None and not isinstance(schema, Mapping):
            raise ValueError("openai_schema_invalid")
        validation_schema = dict(schema) if schema is not None else {"type": "object"}
        if schema is None:
            # An unconstrained object is JSON mode, not a valid strict schema.
            format_spec: dict[str, Any] = {"type": "json_object"}
            normalized_prompt += "\nReturn a JSON object."
        else:
            format_spec = {
                "type": "json_schema",
                "name": str(schema_name or "structured_response"),
                "strict": True,
                "schema": validation_schema,
            }
        raw_text = self._complete(
            normalized_prompt,
            max_output_tokens=max(1, min(16384, int(max_output_tokens))),
            text_format=format_spec,
            cancel_predicate=cancel_predicate,
        ).strip()
        if not raw_text:
            raise ValueError("openai_empty_response")
        try:
            decoded = load_strict_json(raw_text)
        except (ValueError, RecursionError):
            raise ValueError("openai_response_schema_invalid") from None
        if not self._matches_schema(decoded, validation_schema):
            raise ValueError("openai_response_schema_invalid")
        return raw_text


__all__ = [
    "DEFAULT_OPENAI_MODEL",
    "DEFAULT_OPENAI_REASONING_EFFORT",
    "DEFAULT_OPENAI_TIMEOUT_SECONDS",
    "MAX_OPENAI_RESPONSE_BYTES",
    "OPENAI_RESPONSES_ENDPOINT",
    "OpenAIRequestCancelled",
    "OpenAITranslationProvider",
    "SUPPORTED_OPENAI_REASONING_EFFORTS",
]
