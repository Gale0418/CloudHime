import pytest

from translation_providers import GoogleTranslationProvider
from translation_providers import GemmaTranslationProvider, LocalGemmaProvider, LocalMultimodalProvider
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
        "translation_providers.GoogleTranslator",
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
