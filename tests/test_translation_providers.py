import json
from urllib import error

import pytest

from dev_local_gemma_provider import LocalGemmaProvider

from translation_providers import GoogleTranslationProvider
from translation_providers import (
    GemmaTranslationProvider,
    LocalMultimodalProvider,
    classify_region_vision_failure,
)
from translation_helpers import build_gemma_prompt


def test_google_provider_does_not_expose_stream_translation():
    provider = GoogleTranslationProvider()

    assert not hasattr(provider, "translate_stream")


class FakeTranslator:
    def __init__(self, response=None):
        self.calls = []
        self.response = response

    def translate(self, text):
        self.calls.append(text)
        return self.response if self.response is not None else text


def test_google_provider_applies_dictionary_before_single_translation():
    provider = GoogleTranslationProvider()
    translator = FakeTranslator()
    provider._get_translator = lambda source_lang, target_lang: translator

    result = provider.translate("Shares of Leader Harmonious Drive Systems jumped.")

    assert "綠的諧波" in translator.calls[0]
    assert "Leader Harmonious" not in translator.calls[0]
    assert "綠的諧波" in result.text


def test_google_provider_applies_dictionary_before_batch_translation():
    provider = GoogleTranslationProvider()
    translator = FakeTranslator("雙點博物館\n葡萄酒俱樂部")
    provider._get_translator = lambda source_lang, target_lang: translator

    results = provider.translate_batch(["TWO POINT MUSEUM", "Wine Club"])

    assert "雙點博物館" in translator.calls[0]
    assert "TWO POINT MUSEUM" not in translator.calls[0]
    assert [result.text for result in results] == ["雙點博物館", "葡萄酒俱樂部"]


def test_gemma_provider_prompt_includes_dictionary_hint():
    provider = GemmaTranslationProvider(google_api_key="test-key", gemma_model="gemma-4-31b-it")

    prompt = provider._build_prompt("Leader Harmonious Drive Systems")

    assert "'Leader Harmonious' -> '綠的諧波'" in prompt


def test_gemma_prompt_accepts_model_name_argument():
    prompt = build_gemma_prompt("hello", "zh-TW", "gemma-4-31b-it")

    assert "hello" in prompt


def test_local_gemma_provider_exposes_explicit_load_model():
    provider = LocalGemmaProvider(model_path="fake.gguf", enabled=False)
    provider.enabled = True
    provider._load_model = lambda: setattr(provider, "_llm", object())

    assert provider.load_model() is True
    assert provider.available() is True
class RecordingGoogleTranslator(FakeTranslator):
    def __init__(self, source, target):
        super().__init__()
        self.source = source
        self.target = target


def test_google_translator_cache_is_scoped_by_source_and_target(monkeypatch):
    created = []

    def factory(source, target):
        translator = RecordingGoogleTranslator(source, target)
        created.append(translator)
        return translator

    monkeypatch.setattr("translation_providers.GoogleTranslator", factory)
    provider = GoogleTranslationProvider(target_lang="zh-TW")

    first = provider._get_translator("en", "en")
    same = provider._get_translator("en", "en")
    other_target = provider._get_translator("en", "zh-TW")

    assert first is same
    assert first.target == "en"
    assert other_target.target == "zh-TW"
    assert len(created) == 2


def test_local_gemma_prompt_and_context_use_resolved_target():
    class FakeLocalLlm:
        def __init__(self):
            self.prompts = []
            self.responses = iter(["英文結果", "中文結果", "另一個英文結果"])

        def create_completion(self, prompt, **kwargs):
            self.prompts.append(prompt)
            return {"choices": [{"text": next(self.responses)}]}

    provider = LocalGemmaProvider(enabled=False)
    provider.enabled = True
    provider._llm = FakeLocalLlm()

    provider.translate("first source", target_lang="en")
    provider.translate("second source", target_lang="zh-TW")
    provider.translate("third source", target_lang="en")

    assert "natural English" in provider._llm.prompts[0]
    assert "natural Traditional Chinese" in provider._llm.prompts[1]
    assert "first source" not in provider._llm.prompts[1]
    assert "first source" in provider._llm.prompts[2]


def test_local_gemma_update_config_loads_on_disabled_to_enabled():
    provider = LocalGemmaProvider(enabled=False)
    load_calls = []
    provider._load_model = lambda: load_calls.append(True)

    provider.update_config(enabled=True)

    assert load_calls == [True]


def test_local_gemma_cache_isolated_when_generation_params_change():
    class FakeLocalLlm:
        def __init__(self):
            self.prompts = []
            self.responses = iter(("first", "second"))

        def create_completion(self, prompt, **kwargs):
            self.prompts.append(prompt)
            return {"choices": [{"text": next(self.responses)}]}

    provider = LocalGemmaProvider(
        enabled=False,
        temperature=0.2,
        repeat_penalty=1.15,
    )
    provider.enabled = True
    provider._llm = FakeLocalLlm()

    first = provider.translate("hello")
    provider.update_config(temperature=0.35)
    second = provider.translate("hello")

    assert first.from_cache is False
    assert second.from_cache is False
    assert second.text == "second"
    assert len(provider._llm.prompts) == 2
    assert "first" not in provider._llm.prompts[1]

def test_local_multimodal_translate_checks_availability_before_empty_input():
    provider = LocalMultimodalProvider(enabled=False)
    provider._request_chat_completion = lambda payload: pytest.fail("request should not run")

    with pytest.raises(ValueError, match="local_multimodal_unavailable"):
        provider.translate("")


@pytest.mark.parametrize("operation", [
    "translate_multimodal",
    "interpret_regions",
    "transcribe_screenshot",
    "translate_screenshot",
])
def test_local_multimodal_image_apis_check_availability(operation):
    provider = LocalMultimodalProvider(enabled=False)
    provider._request_chat_completion = lambda *args, **kwargs: pytest.fail(
        "request should not run"
    )
    image_parts = [{"inline_data": {"data": "image"}}]

    calls = {
        "translate_multimodal": lambda: provider.translate_multimodal(
            ["source"], image_parts
        ),
        "interpret_regions": lambda: provider.interpret_regions(
            image_parts,
            [{"id": "region-1", "x": 0, "y": 0, "w": 10, "h": 10, "text": "source"}],
            image_width=100,
            image_height=100,
        ),
        "transcribe_screenshot": lambda: provider.transcribe_screenshot(image_parts),
        "translate_screenshot": lambda: provider.translate_screenshot(image_parts),
    }

    with pytest.raises(ValueError, match="local_multimodal_unavailable"):
        calls[operation]()

@pytest.mark.parametrize("operation", [
    "translate_multimodal",
    "transcribe_screenshot",
    "translate_screenshot",
])
def test_local_multimodal_image_apis_reject_missing_image_context(operation):
    provider = LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="gemma-local",
        enabled=True,
    )
    provider._request_chat_completion = lambda *args, **kwargs: pytest.fail(
        "request should not run"
    )

    calls = {
        "translate_multimodal": lambda: provider.translate_multimodal(
            ["source"], []
        ),
        "transcribe_screenshot": lambda: provider.transcribe_screenshot([]),
        "translate_screenshot": lambda: provider.translate_screenshot([]),
    }

    with pytest.raises(ValueError, match="missing_image_context"):
        calls[operation]()

def test_local_multimodal_translate_uses_target_for_prompt_and_cache():
    provider = LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="gemma-local",
        enabled=True,
    )
    payloads = []

    def fake_request(payload):
        payloads.append(payload)
        return "翻譯結果"

    provider._request_chat_completion = fake_request

    first = provider.translate("hello", target_lang="en")
    second = provider.translate("hello", target_lang="en")

    assert "natural English" in payloads[0]["messages"][0]["content"][0]["text"]
    assert first.from_cache is False
    assert second.from_cache is True
    assert len(payloads) == 1

def test_local_multimodal_cache_is_isolated_by_runtime_endpoint():
    provider = LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="gemma-local",
        enabled=True,
    )
    responses = iter(("first endpoint", "second endpoint"))
    provider._request_chat_completion = lambda payload: next(responses)

    first = provider.translate("hello", target_lang="en")
    provider.update_runtime("http://127.0.0.1:9090/v1", "gemma-local", True)
    second = provider.translate("hello", target_lang="en")

    assert first.text == "first endpoint"
    assert second.text == "second endpoint"
    assert second.from_cache is False

def test_local_gemma_fallback_reports_google_and_preserves_attribution_on_cache_hit(monkeypatch):
    class EchoLlm:
        def create_completion(self, prompt, **kwargs):
            return {"choices": [{"text": "same source"}]}

    monkeypatch.setattr(
        "dev_local_gemma_provider.GoogleTranslator",
        lambda source, target: FakeTranslator("翻譯結果"),
    )
    provider = LocalGemmaProvider(enabled=False)
    provider.enabled = True
    provider._llm = EchoLlm()

    first = provider.translate("same source")
    second = provider.translate("same source")

    assert first.provider == "google"
    assert first.requested_provider == "local_gemma"
    assert first.fallback_reason == "bad_translation"
    assert second.provider == "google"
    assert second.requested_provider == "local_gemma"
    assert second.fallback_reason == "bad_translation"
    assert second.from_cache is True


def test_local_gemma_close_is_idempotent_and_releases_reference_on_close_failure():
    class ClosableLlm:
        def __init__(self, raises=False):
            self.calls = 0
            self.raises = raises

        def close(self):
            self.calls += 1
            if self.raises:
                raise RuntimeError("close failed")

    provider = LocalGemmaProvider(enabled=False)
    provider.enabled = True
    provider._llm = ClosableLlm(raises=True)
    provider._translation_cache["key"] = "value"
    provider._context_buffer.append(("source", "translation", "zh-TW"))

    provider.close()
    provider.close()

    assert provider.enabled is False
    assert provider._llm is None
    assert not provider._translation_cache
    assert not provider._context_buffer
    assert provider.last_load_error == "model_close_failed: RuntimeError"

def test_local_gemma_update_config_disable_releases_model():
    class ClosableLlm:
        def __init__(self):
            self.calls = 0

        def close(self):
            self.calls += 1

    provider = LocalGemmaProvider(enabled=False)
    provider.enabled = True
    llm = ClosableLlm()
    provider._llm = llm
    provider._translation_cache["key"] = "value"
    provider._context_buffer.append(("source", "translation", "zh-TW"))

    provider.update_config(enabled=False)

    assert provider.enabled is False
    assert provider._llm is None
    assert llm.calls == 1
    assert not provider._translation_cache
    assert not provider._context_buffer

def test_screenshot_debug_log_reports_lengths_without_model_or_ocr_text():
    secret = "OCR_SECRET prompt=PRIVATE api-key=SECRET"
    provider = GemmaTranslationProvider(
        google_api_key="test-key",
        gemma_model="gemma-4-31b-it",
    )
    provider._resolve_model = lambda: "gemma-4-31b-it"
    provider._can_call = lambda _model: True
    provider._request = lambda *_args, **_kwargs: {
        "candidates": [{"content": {"parts": [{"text": secret}]}}]
    }
    logs = []

    with pytest.raises(ValueError, match="empty_gemma_screenshot_response"):
        provider.translate_screenshot(
            [{"inline_data": {"data": "ignored"}}],
            debug_log=logs.append,
        )

    rendered = "\n".join(logs)
    assert "raw_len=" in rendered
    assert "last_raw_len=" in rendered
    assert secret not in rendered
    assert "OCR_SECRET" not in rendered
def test_remote_request_sampling_fields_follow_model_capability(monkeypatch):
    payloads = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"candidates": []}'

    def fake_urlopen(req, timeout):
        payloads.append(json.loads(req.data.decode("utf-8")))
        return Response()

    monkeypatch.setattr("translation_providers.request.urlopen", fake_urlopen)
    provider = GemmaTranslationProvider(
        google_api_key="test-key",
        gemma_model="gemini-3.5-flash",
    )

    provider._request("gemini-3.5-flash", "hello")
    provider._request("gemma-4-31b-it", "hello")

    gemini_config = payloads[0]["generationConfig"]
    assert "temperature" not in gemini_config
    assert "topP" not in gemini_config
    assert "topK" not in gemini_config
    assert payloads[1]["generationConfig"]["temperature"] == 0.2


def test_local_multimodal_sampling_settings_reach_payload_and_cache_key():
    provider = LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="gemma-local",
        enabled=True,
        temperature=0.35,
        repeat_penalty=1.2,
    )
    payloads = []
    provider._request_chat_completion = (
        lambda payload: payloads.append(payload) or "translated"
    )

    first = provider.translate("hello")
    provider.update_generation_config(temperature=0.4, repeat_penalty=1.25)
    second = provider.translate("hello")

    assert first.from_cache is False
    assert second.from_cache is False
    assert payloads[0]["temperature"] == 0.35
    assert payloads[0]["repeat_penalty"] == 1.2
    assert payloads[1]["temperature"] == 0.4
    assert payloads[1]["repeat_penalty"] == 1.25


@pytest.mark.parametrize(
    ("provider_factory", "configure_response"),
    [
        (
            lambda: GemmaTranslationProvider(google_api_key="test-key", gemma_model="gemma-4-31b-it"),
            lambda provider: setattr(provider, "_request", lambda *_args, **_kwargs: {"candidates": [{"content": {"parts": [{"text": '{"regions":[{"id":7,"source_text":"Actual text","translation":"translated","confidence":0.9}]}'}]}}]}),
        ),
        (
            lambda: LocalMultimodalProvider(base_url="http://127.0.0.1:8080/v1", model_name="gemma-local", enabled=True),
            lambda provider: setattr(provider, "_request_chat_completion", lambda _payload: '{"regions":[{"id":7,"source_text":"Actual text","translation":"translated","confidence":0.9}]}'),
        ),
    ],
)
def test_interpret_regions_uses_image_to_correct_ocr_hint(provider_factory, configure_response):
    provider = provider_factory()
    configure_response(provider)

    results = provider.interpret_regions(
        [{"inline_data": {"data": "ignored"}}],
        [{"id": 7, "x": 1, "y": 2, "w": 30, "h": 12, "text": "Wrong OCR"}],
        image_width=320,
        image_height=240,
    )

    assert results[0].source_text == "Actual text"
    assert results[0].source_text != "Wrong OCR"
    assert results[0].translation == "translated"


@pytest.mark.parametrize(
    "provider",
    [
        GemmaTranslationProvider(google_api_key="test-key"),
        LocalMultimodalProvider(base_url="http://127.0.0.1:8080/v1", model_name="gemma-local", enabled=True),
    ],
)
def test_interpret_regions_rejects_missing_image_hints_and_empty_regions(provider):
    provider._request = lambda *_args, **_kwargs: {"candidates": [{"content": {"parts": [{"text": '{"regions":[]}'}]}}]}
    provider._request_chat_completion = lambda _payload: '{"regions":[]}'
    hint = {"id": 7, "x": 1, "y": 2, "w": 30, "h": 12, "text": "OCR"}

    with pytest.raises(ValueError):
        provider.interpret_regions([], [hint], image_width=320, image_height=240)
    with pytest.raises(ValueError):
        provider.interpret_regions([{"inline_data": {"data": "ignored"}}], [], image_width=320, image_height=240)
    with pytest.raises(ValueError, match="empty_region"):
        provider.interpret_regions([{"inline_data": {"data": "ignored"}}], [hint], image_width=320, image_height=240)


def test_interpret_regions_uses_text_response_for_legacy_non_json_model():
    provider = GemmaTranslationProvider(
        google_api_key="test-key",
        gemma_model="gemma-3-27b-it",
        supported_models=("gemma-3-27b-it",),
    )
    requests = []

    def fake_request(model_name, prompt, **kwargs):
        requests.append((model_name, prompt, kwargs))
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"regions":[{"id":0,"source_text":"source",'
                                    '"translation":"translated","confidence":0.8}]}'
                                )
                            }
                        ]
                    }
                }
            ]
        }

    provider._request = fake_request
    provider.interpret_regions(
        [{"inline_data": {"data": "ignored"}}],
        [{"id": 0, "x": 0, "y": 0, "w": 20, "h": 10, "text": "hint"}],
        image_width=20,
        image_height=10,
    )

    assert requests[0][0] == "gemma-3-27b-it"
    assert requests[0][2]["response_mime_type"] == "text/plain"


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (ValueError("Response is not valid JSON."), "response_json_invalid"),
        (ValueError("empty_region_vision_response"), "response_empty"),
        (ValueError("incomplete_region_vision_response"), "response_region_mismatch"),
        (ValueError("Response contains an id outside allowed_ids."), "response_region_mismatch"),
        (ValueError("source_text and translation must be non-empty strings."), "response_schema_invalid"),
        (TimeoutError("private timeout details"), "request_timeout"),
        (RuntimeError("prompt and OCR text must never be logged"), "provider_error"),
    ],
)
def test_region_vision_failure_classification_is_bounded(exception, expected):
    assert classify_region_vision_failure(exception) == expected


def test_region_vision_http_failure_classification_keeps_only_status_code():
    response = type(
        "Response",
        (),
        {
            "read": lambda self: b"secret prompt",
            "close": lambda self: None,
        },
    )()
    exception = error.HTTPError(
        "http://127.0.0.1/private", 400, "private response", {}, response
    )

    assert classify_region_vision_failure(exception) == "request_http_400"
class LocalGemmaStreamLlm:
    def __init__(self, streamed_text='translated'):
        self.streamed_text = streamed_text
        self.prompts = []

    def create_completion(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if kwargs.get('stream'):
            return iter([{'choices': [{'text': self.streamed_text}]}])
        return {'choices': [{'text': self.streamed_text}]}


def test_local_gemma_uses_configured_target_when_target_is_omitted():
    llm = LocalGemmaStreamLlm('translated')
    provider = LocalGemmaProvider(target_lang='en', enabled=False)
    provider.enabled = True
    provider._llm = llm

    result = provider.translate('こんにちは')

    assert result.text == 'translated'
    assert provider._context_buffer[-1][2] == 'en'


def test_local_gemma_stream_buffers_bad_candidate_and_preserves_fallback_cache_attribution(monkeypatch):
    llm = LocalGemmaStreamLlm('same source')
    provider = LocalGemmaProvider(enabled=False)
    provider.enabled = True
    provider._llm = llm
    monkeypatch.setattr(
        'dev_local_gemma_provider.GoogleTranslator',
        lambda source, target: FakeTranslator('翻譯結果'),
    )

    chunks = list(provider.translate_stream('same source'))
    cached = provider.translate('same source')

    assert chunks == ['翻譯結果']
    assert cached.text == '翻譯結果'
    assert cached.provider == 'google'
    assert cached.requested_provider == 'local_gemma'
    assert cached.fallback_reason == 'bad_translation'
    assert cached.from_cache is True


def test_local_gemma_stream_emits_only_validated_result():
    llm = LocalGemmaStreamLlm('valid translation')
    provider = LocalGemmaProvider(enabled=False)
    provider.enabled = True
    provider._llm = llm

    assert list(provider.translate_stream('source text')) == ['valid translation']
