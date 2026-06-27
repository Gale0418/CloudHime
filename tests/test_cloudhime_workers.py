from types import SimpleNamespace

import pytest

from cloudhime_workers import OCRWorker


def make_worker_stub():
    worker = OCRWorker.__new__(OCRWorker)
    worker.refresh_count = 0
    worker.use_gemma_translation = False
    worker.google_api_key = ""
    worker.gemma_model = "gemma-3-27b-it"
    worker.active_gemma_model = worker.gemma_model

    def refresh_registry():
        worker.refresh_count += 1

    worker._refresh_translation_registry = refresh_registry
    return worker


def test_set_local_gemma_params_rejects_non_numeric_values():
    worker = make_worker_stub()

    with pytest.raises((TypeError, ValueError)):
        OCRWorker.set_local_gemma_params(worker, None, 1.15)


@pytest.mark.parametrize(
    ("temperature", "repeat_penalty"),
    [
        (-0.1, 1.15),
        (1.1, 1.15),
        (0.2, 0.9),
        (0.2, 2.1),
    ],
)
def test_set_local_gemma_params_rejects_out_of_range_values(temperature, repeat_penalty):
    worker = make_worker_stub()

    with pytest.raises(ValueError):
        OCRWorker.set_local_gemma_params(worker, temperature, repeat_penalty)


def test_set_local_gemma_params_accepts_valid_values_and_refreshes_registry():
    worker = make_worker_stub()

    OCRWorker.set_local_gemma_params(worker, 0.2, 1.15)

    assert worker.local_gemma_temperature == 0.2
    assert worker.local_gemma_repeat_penalty == 1.15
    assert worker.refresh_count == 1


def test_multimodal_routing_local_model():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "translategemma-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    worker.google_api_key = "test_key"

    assert worker.has_local_multimodal_ai() is True
    assert worker.has_remote_multimodal_ai() is False
    assert worker.resolve_multimodal_provider_name() == "local_multimodal"


def test_multimodal_routing_remote_model():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "gemma-3-27b-it"
    worker.active_gemma_model = worker.gemma_model
    worker.google_api_key = "test_key"

    assert worker.has_local_multimodal_ai() is False
    assert worker.has_remote_multimodal_ai() is True
    assert worker.resolve_multimodal_provider_name() == "gemma"


def test_multimodal_routing_fallback():
    worker = make_worker_stub()

    assert worker.has_local_multimodal_ai() is False
    assert worker.has_remote_multimodal_ai() is False
    assert worker.resolve_multimodal_provider_name() is None


def test_translate_text_preferred_uses_local_ai_without_google_api_key():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "translategemma-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    worker._get_translation_provider = lambda name: object() if name == "gemma" else None
    worker.translate_text_gemma = lambda text: f"AI:{text}"
    worker.translate_text_google = lambda text: f"GOOGLE:{text}"

    assert OCRWorker.translate_text_preferred(worker, "Hello") == "AI:Hello"


def test_translate_multimodal_gemma_prefers_local_provider_for_local_model():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "translategemma-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    worker.translation_target_lang = "zh-TW"
    worker.convert_to_trad = lambda text: text
    worker.normalize_gemma_model = lambda model: model or worker.gemma_model
    worker.sync_gemma_call_timestamps_from_provider = lambda provider: None

    class Provider:
        def __init__(self):
            self.called = False
            self.last_target_lang = None

        def translate_multimodal(self, source_texts, image_parts, target_lang):
            self.called = True
            self.last_target_lang = target_lang
            return [SimpleNamespace(text="本地翻譯", model="translategemma-4b-it-local")]

    provider = Provider()
    worker._get_translation_provider = lambda name: provider if name == "local_multimodal" else None

    translated = OCRWorker.translate_multimodal_gemma(worker, [{"inline_data": {"mime_type": "image/png", "data": "Zm9v"}}], ["hello"])

    assert provider.called is True
    assert provider.last_target_lang == "zh-TW"
    assert "本地翻譯" in translated


def test_translate_multimodal_gemma_prefers_remote_provider_for_api_model():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "gemma-3-27b-it"
    worker.active_gemma_model = worker.gemma_model
    worker.google_api_key = "test_key"
    worker.translation_target_lang = "zh-TW"
    worker.convert_to_trad = lambda text: text
    worker.normalize_gemma_model = lambda model: model or worker.gemma_model
    worker.sync_gemma_call_timestamps_from_provider = lambda provider: None

    class Provider:
        def __init__(self):
            self.called = False

        def translate_multimodal(self, source_texts, image_parts, target_lang):
            self.called = True
            return [SimpleNamespace(text="遠端翻譯", model="gemma-3-27b-it")]

    provider = Provider()
    worker._get_translation_provider = lambda name: provider if name == "gemma" else None

    translated = OCRWorker.translate_multimodal_gemma(worker, [{"inline_data": {"mime_type": "image/png", "data": "YmFy"}}], ["hello"])

    assert provider.called is True
    assert "遠端翻譯" in translated
