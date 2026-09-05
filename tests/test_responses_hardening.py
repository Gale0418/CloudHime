"""Response-envelope/transport unit tests; no live API or translation scoring.

The actual provider module is loaded with unrelated OCR/format helpers stubbed,
so these tests do not require Qt, a model, credentials, or network access.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def provider_module(monkeypatch):
    contracts = ModuleType("translation_contracts")
    contracts.TranslationResult = SimpleNamespace
    helpers = ModuleType("translation_helpers")
    helpers.clean_model_output_multiline = lambda text: text
    helpers.split_translated_lines = lambda text, count: text.splitlines()
    regions = ModuleType("vision_region")
    regions.VisionRegionResult = SimpleNamespace
    regions.build_region_vision_prompt = lambda *a, **k: "unused"
    regions.parse_region_vision_response = lambda *a, **k: []
    spec = importlib.util.spec_from_file_location(
        "_cloudhime_responses_unit", Path(__file__).resolve().parents[1] / "openai_translation_provider.py"
    )
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as scoped:
        for name, stub in (("translation_contracts", contracts), ("translation_helpers", helpers),
                           ("vision_region", regions)):
            scoped.setitem(sys.modules, name, stub)
        spec.loader.exec_module(module)
    return module


def response(**overrides):
    return dict(status="completed", error=None, incomplete_details=None,
                output=[dict(type="message", status="completed", role="assistant",
                             content=[dict(type="output_text", text="finished")])], **overrides)


@pytest.mark.parametrize("status", ["incomplete", "failed", "cancelled", "queued", "in_progress", None, False, "unknown"])
def test_partial_or_failed_responses_cannot_shortcut_to_success(provider_module, status):
    payload = response(output_text="truncated-but-nonempty")
    payload["status"] = status
    with pytest.raises(ValueError, match="openai_response_"):
        provider_module.OpenAITranslationProvider._extract_output_text(payload)


@pytest.mark.parametrize("field,value", [
    ("error", {"message": "secret-provider-message"}),
    ("incomplete_details", {"reason": "max_output_tokens"}),
])
def test_error_metadata_wins_over_completed_text(provider_module, field, value):
    payload = response(output_text="partial")
    payload[field] = value
    with pytest.raises(ValueError) as caught:
        provider_module.OpenAITranslationProvider._extract_output_text(payload)
    assert "secret-provider-message" not in str(caught.value)


def test_incomplete_message_is_not_a_completed_translation(provider_module):
    payload = response(output_text="shortcut")
    payload["output"][0]["status"] = "incomplete"
    with pytest.raises(ValueError, match="openai_response_"):
        provider_module.OpenAITranslationProvider._extract_output_text(payload)


def test_refusal_mixed_with_output_text_is_not_translation(provider_module):
    payload = response(output_text="shortcut")
    payload["output"][0]["content"].append({"type": "refusal", "refusal": "private reason"})
    with pytest.raises(ValueError, match="openai_response_refused"):
        provider_module.OpenAITranslationProvider._extract_output_text(payload)


@pytest.mark.parametrize("payload", [
    {"output_text": "legacy compact fixture"},
    response(),
    response(output_text="SDK compact text"),
])
def test_completed_and_legacy_compact_success_remain_supported(provider_module, payload):
    assert provider_module.OpenAITranslationProvider._extract_output_text(payload)


def test_optional_schema_uses_valid_json_mode(provider_module):
    provider = provider_module.OpenAITranslationProvider(api_key="test")
    seen = {}
    def complete(prompt, **kwargs):
        seen.update(prompt=prompt, **kwargs)
        return '{"result":"ok"}'
    provider._complete = complete
    assert json.loads(provider.generate_structured_text("Return a record")) == {"result": "ok"}
    assert seen["text_format"] == {"type": "json_object"}
    assert "JSON" in seen["prompt"]


def test_explicit_schema_keeps_strict_contract(provider_module):
    provider = provider_module.OpenAITranslationProvider(api_key="test")
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"result": {"type": "string"}}, "required": ["result"]}
    seen = {}
    def complete(prompt, **kwargs):
        seen.update(kwargs)
        return '{"result":"ok"}'
    provider._complete = complete
    provider.generate_structured_text("Return JSON", schema=schema)
    assert seen["text_format"]["type"] == "json_schema"
    assert seen["text_format"]["strict"] is True
    assert seen["text_format"]["schema"] == schema


@pytest.mark.parametrize("raw", ['[]', 'null', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'])
def test_structured_json_rejects_nonobjects_and_nonfinite_numbers(provider_module, raw):
    provider = provider_module.OpenAITranslationProvider(api_key="test")
    provider._complete = lambda *a, **k: raw
    with pytest.raises(ValueError, match="openai_response_schema_invalid"):
        provider.generate_structured_text("Return JSON")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 10**1000],
                         ids=["nan", "positive-infinity", "negative-infinity", "oversized-integer"])
def test_nonfinite_timeout_defaults_instead_of_crashing_or_accidental_minimum(provider_module, value):
    provider = provider_module.OpenAITranslationProvider(api_key="test", timeout_seconds=value)
    assert provider.timeout_seconds == provider_module.DEFAULT_OPENAI_TIMEOUT_SECONDS


def test_infinite_response_limit_is_normalized(provider_module):
    provider = provider_module.OpenAITranslationProvider(api_key="test", max_response_bytes=float("inf"))
    assert provider.max_response_bytes == provider_module.MAX_OPENAI_RESPONSE_BYTES


def test_read_cancellation_is_checked_between_chunks(provider_module):
    provider = provider_module.OpenAITranslationProvider(api_key="test")
    cancelled = False
    class Chunks(io.BytesIO):
        def read(self, size=-1):
            nonlocal cancelled
            chunk = super().read(min(size, 4))
            cancelled = True
            return chunk
    with pytest.raises(provider_module.OpenAIRequestCancelled):
        provider._read_response(Chunks(b"12345678"), cancel_predicate=lambda: cancelled)


def test_http_error_stream_is_closed_and_message_not_exposed(provider_module, monkeypatch):
    provider = provider_module.OpenAITranslationProvider(api_key="test")
    stream = io.BytesIO(b"private API error")
    error = provider_module.error.HTTPError("https://example.invalid", 401, "private", {}, stream)
    def request(*a, **k):
        raise error
    monkeypatch.setattr(provider_module.request, "urlopen", request)
    with pytest.raises(ValueError, match="^openai_http_401$"):
        provider._request({})
    assert stream.closed


@pytest.mark.parametrize("output", [{"ignored": True}, None, [None], [{"content": None}]])
def test_malformed_output_cannot_hide_behind_compact_text(provider_module, output):
    payload = response(output_text="shortcut")
    payload["output"] = output
    with pytest.raises(ValueError, match="openai_response_schema_invalid"):
        provider_module.OpenAITranslationProvider._extract_output_text(payload)


@pytest.mark.parametrize("operation", ["translate", "translate_batch", "translate_multimodal", "translate_screenshot", "interpret_regions"])
@pytest.mark.parametrize("override,expected", [(None, "en"), ("zh-TW", "zh-TW")])
def test_target_language_uses_configuration_unless_explicitly_overridden(provider_module, operation, override, expected):
    provider = provider_module.OpenAITranslationProvider(api_key="test", target_lang="en")
    seen = {}
    def complete(prompt, **kwargs):
        seen["prompt"] = prompt
        return "translated"
    provider._complete = complete
    kwargs = {} if override is None else {"target_lang": override}
    image = [{"inline_data": {"mime_type": "image/png", "data": "test"}}]
    if operation == "translate":
        provider.translate("source", **kwargs)
    elif operation == "translate_batch":
        provider.translate_batch(["source"], **kwargs)
    elif operation == "translate_multimodal":
        provider.translate_multimodal(["source"], image, **kwargs)
    elif operation == "translate_screenshot":
        provider.translate_screenshot(image, **kwargs)
    else:
        def region_prompt(*args, **kwargs):
            return "Translate to " + kwargs["target_lang"]
        provider_module.build_region_vision_prompt = region_prompt
        provider_module.parse_region_vision_response = lambda *a, **k: [SimpleNamespace()]
        provider.interpret_regions(image, [{"id": 1}], image_width=1, image_height=1, **kwargs)
    assert "to " + expected in seen["prompt"]
