from translation_providers import GoogleTranslationProvider
from translation_providers import GemmaTranslationProvider, LocalGemmaProvider
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
    provider._get_translator = lambda source_lang: translator

    result = provider.translate("Shares of Leader Harmonious Drive Systems jumped.")

    assert "綠的諧波" in translator.calls[0]
    assert "Leader Harmonious" not in translator.calls[0]
    assert "綠的諧波" in result.text


def test_google_provider_applies_dictionary_before_batch_translation():
    provider = GoogleTranslationProvider()
    translator = FakeTranslator("雙點博物館\n葡萄酒俱樂部")
    provider._get_translator = lambda source_lang: translator

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