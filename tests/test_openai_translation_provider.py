import io
import json
import socket
from types import SimpleNamespace
from urllib import error

import pytest

import openai_translation_provider as provider_module
from cloudhime_workers import OCRWorker
from openai_translation_provider import (
    OpenAIRequestCancelled,
    OpenAITranslationProvider,
)
from translation_contracts import TranslationResult


class FakeResponse:
    def __init__(self, body):
        self.body = body
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        body = self.body[self.offset :]
        self.offset = len(self.body)
        return body


def install_response(monkeypatch, body, captured=None):
    def fake_urlopen(req, timeout):
        if captured is not None:
            captured["request"] = req
            captured["timeout"] = timeout
        return FakeResponse(body)

    monkeypatch.setattr(provider_module.request, "urlopen", fake_urlopen)


def test_provider_defaults_are_redacted_and_available():
    provider = OpenAITranslationProvider(openai_api_key="super-secret")

    assert provider.name == "openai"
    assert provider.model == "gpt-6-luna"
    assert provider.available() is True
    assert "super-secret" not in repr(provider)


@pytest.mark.parametrize("effort", ["none", "low", "medium", "high", "xhigh", "max", "ultra"])
def test_reasoning_effort_is_forced_to_none_for_legacy_and_unknown_values(monkeypatch, effort):
    captured = {}
    install_response(monkeypatch, b'{"output_text":"ok"}', captured)
    provider = OpenAITranslationProvider(openai_api_key="secret", reasoning_effort=effort)

    provider.translate("hello")

    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert provider.reasoning_effort == "none"
    assert payload["reasoning"] == {"effort": "none"}
    assert "reasoning_effort='none'" in repr(provider)


def test_translate_posts_responses_payload_and_parses_output_text(monkeypatch):
    captured = {}
    install_response(monkeypatch, b'{"output_text":"  translated  "}', captured)
    provider = OpenAITranslationProvider(openai_api_key="secret-key", timeout_seconds=17)

    result = provider.translate("hello", source_lang="en", target_lang="zh-TW")

    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert captured["request"].full_url == "https://api.openai.com/v1/responses"
    assert captured["request"].get_header("Authorization") == "Bearer secret-key"
    assert captured["timeout"] == 17
    assert payload["model"] == "gpt-6-luna"
    assert payload["store"] is False
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["input"][0]["content"][0]["type"] == "input_text"
    assert result.text == "translated"
    assert result.provider == "openai"


def test_translate_batch_payload_disables_reasoning(monkeypatch):
    captured = {}
    install_response(monkeypatch, b'{"output_text":"one\\ntwo"}', captured)
    provider = OpenAITranslationProvider(openai_api_key="secret")

    results = provider.translate_batch(["1", "2"])

    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert payload["reasoning"] == {"effort": "none"}
    assert [result.text for result in results] == ["one", "two"]


@pytest.mark.parametrize(
    ("target_lang", "instruction"),
    [("en", "natural English"), ("zh-TW", "natural Traditional Chinese used in Taiwan"), ("ja", "natural Japanese")],
)
def test_translation_prompt_keeps_selected_output_language(monkeypatch, target_lang, instruction):
    captured = {}
    install_response(monkeypatch, b'{"output_text":"translated"}', captured)
    provider = OpenAITranslationProvider(openai_api_key="secret")

    provider.translate("Translate this into another language", target_lang=target_lang)

    payload = json.loads(captured["request"].data.decode("utf-8"))
    prompt = payload["input"][0]["content"][0]["text"]
    assert f"Every output line must be in {instruction}" in prompt


def test_multimodal_converts_gemini_inline_data_to_data_url(monkeypatch):
    captured = {}
    install_response(monkeypatch, b'{"output":[],"output_text":"one\\ntwo"}', captured)
    provider = OpenAITranslationProvider(openai_api_key="secret")

    results = provider.translate_multimodal(
        ["one", "two"],
        [{"inline_data": {"mime_type": "image/jpeg", "data": "Zm9v"}}],
    )

    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert payload["reasoning"] == {"effort": "none"}
    content = payload["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert {item["type"] for item in content} == {"input_text", "input_image"}
    assert content[1] == {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64,Zm9v",
    }
    assert [item.text for item in results] == ["one", "two"]


def test_output_content_form_is_supported_and_region_schema_is_sent(monkeypatch):
    body = json.dumps(
        {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"regions":[{"id":4,"source_text":"原文","translation":"譯文","confidence":0.8}]}'
                        }
                    ],
                }
            ]
        }
    ).encode("utf-8")
    captured = {}
    install_response(monkeypatch, body, captured)
    provider = OpenAITranslationProvider(openai_api_key="secret")

    result = provider.interpret_regions(
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
        [{"id": 4, "x": 0, "y": 0, "w": 20, "h": 10, "text": "OCR"}],
        image_width=20,
        image_height=10,
    )

    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["text"]["format"]["type"] == "json_schema"
    assert result[0].translation == "譯文"


def test_screenshot_payloads_disable_reasoning(monkeypatch):
    captured = {}
    image_parts = [{"inline_data": {"mime_type": "image/png", "data": "abc"}}]
    provider = OpenAITranslationProvider(openai_api_key="secret")

    install_response(monkeypatch, b'{"output_text":"detected text"}', captured)
    provider.transcribe_screenshot(image_parts)
    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert payload["reasoning"] == {"effort": "none"}

    install_response(monkeypatch, b'{"output_text":"translated text"}', captured)
    provider.translate_screenshot(image_parts)
    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert payload["reasoning"] == {"effort": "none"}


def test_structured_text_requires_valid_nonempty_json(monkeypatch):
    captured = {}
    install_response(monkeypatch, b'{"output_text":"{\\"ok\\":true}"}', captured)
    provider = OpenAITranslationProvider(openai_api_key="secret")

    assert provider.generate_structured_text("return an object", schema={"type": "object"}) == '{"ok":true}'
    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["text"]["format"]["schema"] == {"type": "object"}

    install_response(monkeypatch, b'{"output_text":"not-json"}')
    with pytest.raises(ValueError, match="openai_response_schema_invalid"):
        provider.generate_structured_text("return json")

    install_response(monkeypatch, b'{"output_text":""}')
    with pytest.raises(ValueError, match="openai_empty_response"):
        provider.generate_structured_text("return json")


@pytest.mark.parametrize(
    ("exc", "token"),
    [
        (error.HTTPError("https://api.openai.com", 400, "secret", {}, io.BytesIO(b"secret")), "openai_http_400"),
        (error.HTTPError("https://api.openai.com", 401, "secret", {}, io.BytesIO(b"secret")), "openai_http_401"),
        (error.HTTPError("https://api.openai.com", 403, "secret", {}, io.BytesIO(b"secret")), "openai_http_403"),
        (error.HTTPError("https://api.openai.com", 404, "secret", {}, io.BytesIO(b"secret")), "openai_http_404"),
        (error.HTTPError("https://api.openai.com", 429, "secret", {}, io.BytesIO(b"secret")), "openai_http_429"),
        (error.HTTPError("https://api.openai.com", 503, "secret", {}, io.BytesIO(b"secret")), "openai_http_5xx"),
        (TimeoutError("secret timeout"), "openai_timeout"),
        (error.URLError("secret transport"), "openai_transport_error"),
    ],
)
def test_network_failures_are_bounded_and_not_retried(monkeypatch, exc, token):
    calls = []

    def fake_urlopen(*_args, **_kwargs):
        calls.append(True)
        raise exc

    monkeypatch.setattr(provider_module.request, "urlopen", fake_urlopen)
    provider = OpenAITranslationProvider(openai_api_key="secret")

    with pytest.raises(ValueError, match=token) as raised:
        provider.translate("secret prompt")
    assert len(calls) == 1
    assert "secret" not in str(raised.value)


def test_response_body_limit_and_cancellation_are_fail_closed(monkeypatch):
    provider = OpenAITranslationProvider(openai_api_key="secret", max_response_bytes=8)
    install_response(monkeypatch, b'{"too":"large"}')
    with pytest.raises(ValueError, match="openai_response_too_large"):
        provider.translate("hello")

    provider = OpenAITranslationProvider(openai_api_key="secret")
    calls = []
    monkeypatch.setattr(provider_module.request, "urlopen", lambda *_args, **_kwargs: calls.append(True))
    with pytest.raises(OpenAIRequestCancelled):
        provider.translate("hello", cancel_predicate=lambda: True)
    assert calls == []

    cancelled = {"value": False}

    def response_then_cancel(*_args, **_kwargs):
        cancelled["value"] = True
        return FakeResponse(b'{"output_text":"result"}')

    monkeypatch.setattr(provider_module.request, "urlopen", response_then_cancel)
    with pytest.raises(OpenAIRequestCancelled):
        provider.translate("hello", cancel_predicate=lambda: cancelled["value"])


class FakeWorkerProvider:
    def __init__(self, name, available=True):
        self.name = name
        self._available = available
        self.text_calls = 0
        self.screenshot_calls = 0

    def available(self):
        return self._available

    def translate(self, text, **_kwargs):
        self.text_calls += 1
        return TranslationResult(
            text=f"{self.name}:{text}",
            provider=self.name,
            model="gpt-6-luna" if self.name == "openai" else "gemma-4-31b-it",
        )

    def translate_screenshot(self, _image_parts, **_kwargs):
        self.screenshot_calls += 1
        return TranslationResult(
            text=f"{self.name}:screenshot",
            provider=self.name,
            model="gpt-6-luna" if self.name == "openai" else "gemma-4-31b-it",
        )

    def translate_multimodal(self, texts, _image_parts, **_kwargs):
        return [
            TranslationResult(
                text=f"{self.name}:{text}",
                provider=self.name,
                model="gpt-6-luna" if self.name == "openai" else "gemma-4-31b-it",
            )
            for text in texts
        ]


def make_routing_worker(provider_chain, providers):
    worker = OCRWorker.__new__(OCRWorker)
    worker.provider_chain = tuple(provider_chain)
    worker.translation_registry = SimpleNamespace(
        get=lambda name: providers.get(str(name).strip().casefold())
    )
    worker.use_gemma_translation = True
    worker.google_api_key = "fake-google-key"
    worker.google_api_keys = ()
    worker.gemma_model = "gemma-4-31b-it"
    worker.active_gemma_model = worker.gemma_model
    worker.local_multimodal_enabled = False
    worker.local_multimodal_model = ""
    worker.translation_target_lang = "zh-TW"
    worker.scan_mode = "region"
    worker.region_render_mode = "screenshot"
    worker.convert_to_trad = lambda text: text
    worker.sync_gemma_call_timestamps_from_provider = lambda _provider: None
    worker.log_ai_debug = lambda _message: None
    worker._clear_translation_memories = lambda: None
    return worker


def test_worker_openai_chain_routes_text_and_screenshot_to_openai():
    openai = FakeWorkerProvider("openai")
    gemma = FakeWorkerProvider("gemma")
    worker = make_routing_worker(
        ("openai",),
        {"openai": openai, "gemma": gemma},
    )
    worker.google_api_key = ""

    assert worker._get_translation_provider("gemma") is openai
    assert worker.has_ai_text_provider() is True
    assert worker.has_remote_multimodal_ai() is True
    assert worker.resolve_multimodal_provider_name() == "openai"
    assert worker.get_current_ai_provider() == "openai"
    assert worker._is_local_model_active() is False

    assert OCRWorker.translate_text_gemma(worker, "hello") == "openai:hello"
    assert OCRWorker.translate_screenshot_gemma(worker, [{"inline_data": {"data": "fake"}}]) == "openai:screenshot"
    assert openai.text_calls == 1
    assert openai.screenshot_calls == 1
    assert gemma.text_calls == 0
    assert gemma.screenshot_calls == 0


def test_worker_openai_chain_does_not_fall_back_to_gemma_without_openai():
    openai = FakeWorkerProvider("openai", available=False)
    gemma = FakeWorkerProvider("gemma")
    worker = make_routing_worker(
        ("openai",),
        {"openai": openai, "gemma": gemma},
    )

    assert worker._get_translation_provider("gemma") is None
    assert worker.has_ai_text_provider() is False
    assert worker.has_remote_multimodal_ai() is False
    assert worker.resolve_multimodal_provider_name() is None
    assert worker.get_current_ai_provider() == "google"
    assert worker._is_local_model_active() is False
    with pytest.raises(ValueError, match="translation_provider_unavailable"):
        OCRWorker.translate_screenshot_gemma(worker, [{"inline_data": {"data": "fake"}}])
    assert gemma.screenshot_calls == 0


def test_worker_gemma_chain_restores_gemma_and_cache_fingerprint_changes():
    gemma = FakeWorkerProvider("gemma")
    worker = make_routing_worker(
        ("gemma", "google"),
        {"gemma": gemma},
    )

    assert worker._get_translation_provider("gemma") is gemma
    assert worker.has_ai_text_provider() is True
    assert worker.get_current_ai_provider() == "gemma"
    assert worker.resolve_multimodal_provider_name() == "gemma"

    worker.gemma_model = "gemma-3-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    assert worker._is_local_model_active() is True
    worker.provider_chain = ("openai",)
    assert worker._is_local_model_active() is False

    worker.provider_chain = ("openai",)
    worker.openai_enabled = True
    worker.openai_api_key = "fake-openai-key"
    openai_context = OCRWorker._exact_image_cache_context(worker, 0, 0)
    openai_key = OCRWorker._build_persistent_translation_cache_key(worker, "hello", "openai")
    worker.provider_chain = ("gemma", "google")
    gemma_context = OCRWorker._exact_image_cache_context(worker, 0, 0)
    gemma_key = OCRWorker._build_persistent_translation_cache_key(worker, "hello", "gemma")
    assert openai_context != gemma_context
    assert openai_key != gemma_key
