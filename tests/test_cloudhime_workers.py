import json
from collections import OrderedDict
from concurrent.futures import Future
from types import SimpleNamespace

import numpy as np
import pytest

import cloudhime_workers as workers_module
from cloudhime_workers import OCRWorker
from exact_image_cache import ExactImageCache


def make_worker_stub():
    worker = OCRWorker.__new__(OCRWorker)
    worker.refresh_count = 0
    worker.use_gemma_translation = False
    worker.google_api_key = ""
    worker.gemma_model = "gemma-3-27b-it"
    worker.active_gemma_model = worker.gemma_model
    worker.local_multimodal_enabled = False
    worker.local_multimodal_base_url = "http://127.0.0.1:8080/v1"
    worker.local_multimodal_model = ""
    worker.local_multimodal_timeout_seconds = 20
    worker.local_multimodal_cpu_only = False

    def refresh_registry():
        worker.refresh_count += 1

    worker._refresh_translation_registry = refresh_registry
    return worker


def test_translation_setting_changes_clear_all_translation_memories():
    worker = make_worker_stub()
    worker.translation_target_lang = "zh-TW"
    worker.gemma_prompt = "old prompt"
    worker.screenshot_gemma_prompt = "old screenshot prompt"
    worker.translation_cache = OrderedDict({("source", "text"): "old translation"})
    worker.preferred_text_memory = OrderedDict({"hello": {"translated_text": "old translation"}})
    worker.hud_memory = OrderedDict({"hello": {"translated_text": "old translation"}})
    worker.exact_image_cache = ExactImageCache()
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    worker.exact_image_cache.put(image, "context", ["cached"], "google", "state")
    worker.last_combined_text = "old"
    worker.last_results = [("old", 1, 2, 3, 4)]
    worker.last_provider = "google"
    worker.unrelated_setting = "keep"

    OCRWorker.set_translation_target_lang(worker, "en")

    assert worker.translation_target_lang == "en"
    assert not worker.translation_cache
    assert not worker.preferred_text_memory
    assert not worker.hud_memory
    assert len(worker.exact_image_cache) == 0
    assert worker.last_combined_text == ""
    assert worker.last_results == []
    assert worker.last_provider == ""
    assert worker.unrelated_setting == "keep"

    for setter, value in (
        (OCRWorker.set_gemma_prompt, "new prompt"),
        (OCRWorker.set_screenshot_gemma_prompt, "new screenshot prompt"),
    ):
        worker.translation_cache["new"] = "translation"
        worker.preferred_text_memory["new"] = {"translated_text": "translation"}
        worker.hud_memory["new"] = {"translated_text": "translation"}
        worker.exact_image_cache.put(image, "context", ["cached"], "google", "state")
        worker.last_results = [("old", 1, 2, 3, 4)]

        setter(worker, value)

        assert not worker.translation_cache
        assert not worker.preferred_text_memory
        assert not worker.hud_memory
        assert len(worker.exact_image_cache) == 0
        assert worker.last_results == []


def test_background_threshold_change_invalidates_exact_image_cache():
    worker = make_worker_stub()
    worker.binary_threshold = 100
    worker.exact_image_cache = ExactImageCache()
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    worker.exact_image_cache.put(image, "context", ["cached"], "google", "state")

    def refresh_threshold(*_args, **_kwargs):
        OCRWorker.set_binary_threshold(worker, 120)
        return 120, []

    worker.run_ocr_with_best_threshold = refresh_threshold
    worker._bg_threshold_running = True

    OCRWorker._run_background_threshold(worker, image, 0, 0, "region")

    assert len(worker.exact_image_cache) == 0
    assert worker._bg_threshold_running is False


def test_gemma_text_fallback_cache_isolated_by_target_and_prompt(monkeypatch):
    worker = make_worker_stub()
    worker.google_api_key = "test_key"
    worker.translation_target_lang = "zh-TW"
    worker.gemma_prompt = "old prompt"
    worker.translation_cache = OrderedDict()
    worker._get_translation_provider = lambda name: None
    worker.resolve_gemma_model_for_call = lambda preferred_model=None: "gemma-3-27b-it"
    worker.can_call_gemma = lambda model_name=None: True
    worker.record_gemma_call = lambda model_name=None: None
    worker.extract_gemma_text = lambda payload: payload["translation"]
    worker.clean_model_output = lambda text: text
    worker.convert_to_trad = lambda text: text
    responses = iter(["舊語言翻譯", "英文翻譯", "新 prompt 翻譯"])
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(req, timeout):
        requests.append(json.loads(req.data.decode("utf-8")))
        return Response({"translation": next(responses)})

    monkeypatch.setattr(workers_module.request, "urlopen", fake_urlopen)

    assert OCRWorker.translate_text_gemma(worker, "hello") == "舊語言翻譯"
    OCRWorker.set_translation_target_lang(worker, "en")
    assert OCRWorker.translate_text_gemma(worker, "hello") == "英文翻譯"
    OCRWorker.set_gemma_prompt(worker, "new prompt")
    assert OCRWorker.translate_text_gemma(worker, "hello") == "新 prompt 翻譯"

    prompts = [item["contents"][0]["parts"][0]["text"] for item in requests]
    assert len(requests) == 3
    assert prompts[0] != prompts[1]
    assert "natural English" in prompts[1]
    assert "new prompt" in prompts[2]


def test_gemma_multimodal_fallback_cache_includes_target_and_effective_prompt(monkeypatch):
    worker = make_worker_stub()
    worker.google_api_key = "test_key"
    worker.translation_target_lang = "zh-TW"
    worker.gemma_prompt = "old prompt"
    worker.translation_cache = OrderedDict()
    worker.resolve_multimodal_provider_name = lambda: "gemma"
    worker._get_translation_provider = lambda name: None
    worker.resolve_gemma_model_for_call = lambda preferred_model=None: "gemma-3-27b-it"
    worker.can_call_gemma = lambda model_name=None: True
    worker.record_gemma_call = lambda model_name=None: None
    worker.extract_gemma_text = lambda payload: payload["translation"]
    worker.convert_to_trad = lambda text: text
    responses = iter(["舊多模態翻譯", "不同影像翻譯", "新多模態翻譯"])
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(req, timeout):
        requests.append(json.loads(req.data.decode("utf-8")))
        return Response({"translation": next(responses)})

    monkeypatch.setattr(workers_module.request, "urlopen", fake_urlopen)
    image_parts = [{"inline_data": {"mime_type": "image/png", "data": "Zm9v"}}]

    assert OCRWorker.translate_multimodal_gemma(worker, image_parts, ["hello"]) == "舊多模態翻譯"
    old_key = next(iter(worker.translation_cache))
    expected_digest = workers_module.hashlib.sha256(
        json.dumps(image_parts, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert old_key[0:2] == ("gemma-mm", "gemma-3-27b-it")
    assert old_key[3] == expected_digest
    assert old_key[4] == "zh-TW"
    assert "old prompt" in old_key[5]

    assert OCRWorker.translate_multimodal_gemma(worker, image_parts, ["hello"]) == "舊多模態翻譯"
    assert len(requests) == 1

    different_image_parts = [{"inline_data": {"mime_type": "image/png", "data": "YmFy"}}]
    assert OCRWorker.translate_multimodal_gemma(worker, different_image_parts, ["hello"]) == "不同影像翻譯"
    different_key = next(key for key in worker.translation_cache if key[3] != old_key[3])
    assert different_key[0:2] == ("gemma-mm", "gemma-3-27b-it")
    assert different_key[4] == "zh-TW"
    assert "old prompt" in different_key[5]
    assert len(requests) == 2

    OCRWorker.set_gemma_prompt(worker, "new prompt")
    assert OCRWorker.translate_multimodal_gemma(worker, different_image_parts, ["hello"]) == "新多模態翻譯"
    new_key = next(key for key in worker.translation_cache if "new prompt" in key[5])
    assert new_key[3] == different_key[3]
    assert new_key[4] == "zh-TW"
    assert "new prompt" in new_key[5]
    assert len(requests) == 3
    assert requests[0]["contents"][0]["parts"][-1]["text"] != requests[2]["contents"][0]["parts"][-1]["text"]


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


def test_set_local_multimodal_config_accepts_values_and_refreshes_registry():
    worker = make_worker_stub()

    OCRWorker.set_local_multimodal_config(
        worker,
        enabled=True,
        base_url="http://localhost:11434/v1/",
        model_name="vision-local",
        timeout_seconds=45,
        cpu_only=True,
    )

    assert worker.local_multimodal_enabled is True
    assert worker.local_multimodal_base_url == "http://localhost:11434/v1"
    assert worker.local_multimodal_model == "vision-local"
    assert worker.local_multimodal_timeout_seconds == 45
    assert worker.local_multimodal_cpu_only is True
    assert worker.refresh_count == 1


def test_local_multimodal_mode_change_is_async_and_restarts():
    calls = []
    submitted = []

    class Executor:
        def submit(self, callback):
            future = Future()
            submitted.append((callback, future))
            return future

    class Runtime:
        def stop(self):
            calls.append("stop")

        def set_gpu_layers(self, layers):
            calls.append(("layers", layers))

    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.local_vision_runtime = Runtime()
    worker._local_vision_executor = Executor()
    worker._local_vision_load_future = None
    worker.request_local_vision_start = lambda: calls.append("restart")

    OCRWorker.set_local_multimodal_config(
        worker,
        enabled=True,
        base_url="http://127.0.0.1:8080/v1",
        model_name="vision-local",
        timeout_seconds=20,
        cpu_only=True,
    )

    assert calls == []
    assert len(submitted) == 1
    callback, future = submitted.pop()
    callback()
    future.set_result(None)
    assert calls == ["stop", ("layers", 0), "restart"]


def test_local_multimodal_mode_changes_during_startup_are_coalesced():
    calls = []
    submitted = []
    loading = Future()

    class Executor:
        def submit(self, callback):
            future = Future()
            submitted.append((callback, future))
            return future

    class Runtime:
        def stop(self):
            calls.append("stop")

        def set_gpu_layers(self, layers):
            calls.append(("layers", layers))

    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.local_multimodal_enabled = True
    worker.local_vision_runtime = Runtime()
    worker._local_vision_executor = Executor()
    worker._local_vision_load_future = loading
    worker.request_local_vision_start = lambda: calls.append("restart")

    OCRWorker.set_local_multimodal_config(
        worker,
        enabled=True,
        base_url="http://127.0.0.1:8080/v1",
        model_name="vision-local",
        timeout_seconds=20,
        cpu_only=True,
    )
    OCRWorker.set_local_multimodal_config(
        worker,
        enabled=True,
        base_url="http://127.0.0.1:8080/v1",
        model_name="vision-local",
        timeout_seconds=20,
        cpu_only=False,
    )

    assert submitted == []
    loading.set_result(None)
    assert len(submitted) == 1
    callback, future = submitted.pop()
    callback()
    future.set_result(None)

    assert calls == ["stop", ("layers", 999), "restart"]
    assert worker.local_multimodal_cpu_only is False


def test_multimodal_routing_local_model():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    worker.google_api_key = "test_key"
    worker.local_multimodal_enabled = True
    worker.local_multimodal_model = "translategemma-4b-it-local"

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


def test_remote_multimodal_routing_respects_catalog_capability_and_provider():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.google_api_key = "test_key"

    worker.gemma_model = "gemma-3-1b-it"
    worker.active_gemma_model = worker.gemma_model
    assert worker.has_remote_multimodal_ai() is False

    worker.gemma_model = "gemini-3.5-flash"
    worker.active_gemma_model = worker.gemma_model
    assert worker.has_remote_multimodal_ai() is True
    assert worker.get_current_ai_provider() == "gemini"

    worker.gemma_model = "gemma-4-31b-it"
    worker.active_gemma_model = worker.gemma_model
    assert worker.get_current_ai_provider() == "gemma"


def test_multimodal_routing_fallback():
    worker = make_worker_stub()

    assert worker.has_local_multimodal_ai() is False
    assert worker.has_remote_multimodal_ai() is False
    assert worker.resolve_multimodal_provider_name() is None


def test_local_gemma_model_id_selects_local_runtime():
    worker = make_worker_stub()
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.active_gemma_model = worker.gemma_model

    assert OCRWorker._is_local_model_active(worker) is True


@pytest.mark.parametrize(
    ("result", "runtime_state", "last_error", "expected"),
    (
        (True, workers_module.JapaneseOCRRuntimeState.ready, "", ("ready", "")),
        (False, workers_module.JapaneseOCRRuntimeState.failed, "asset missing", ("failed", "asset missing")),
        (False, workers_module.JapaneseOCRRuntimeState.disabled, "", ("disabled", "")),
    ),
)
def test_japanese_rescue_callback_reports_terminal_status(
    result, runtime_state, last_error, expected
):
    statuses = []
    future = Future()
    future.set_result(result)
    worker = SimpleNamespace(
        _japanese_rescue_load_future=future,
        japanese_rescue_runtime=SimpleNamespace(
            state=runtime_state,
            last_error=last_error,
        ),
        japanese_rescue_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
    )

    OCRWorker._on_japanese_rescue_start_done(worker, future)

    assert worker._japanese_rescue_load_future is None
    assert statuses == [expected]


def test_stale_japanese_rescue_callback_is_silent_and_preserves_new_future():
    statuses = []
    old_future = Future()
    old_future.set_result(True)
    new_future = Future()
    worker = SimpleNamespace(
        _japanese_rescue_load_future=new_future,
        japanese_rescue_runtime=SimpleNamespace(
            state=workers_module.JapaneseOCRRuntimeState.ready,
            last_error="",
        ),
        japanese_rescue_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
    )

    OCRWorker._on_japanese_rescue_start_done(worker, old_future)

    assert worker._japanese_rescue_load_future is new_future
    assert statuses == []


def test_request_japanese_rescue_start_reports_executor_submit_failure():
    statuses = []

    class ClosedExecutor:
        def submit(self, callback):
            raise RuntimeError("executor closed")

    old_future = Future()
    old_future.set_result(False)
    worker = SimpleNamespace(
        japanese_rescue_enabled=True,
        japanese_rescue_runtime=SimpleNamespace(
            state=workers_module.JapaneseOCRRuntimeState.disabled,
            start=lambda: True,
        ),
        _japanese_rescue_executor=ClosedExecutor(),
        _japanese_rescue_load_future=old_future,
        japanese_rescue_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
    )

    OCRWorker.request_japanese_rescue_start(worker)

    assert worker._japanese_rescue_load_future is None
    assert statuses == [
        ("starting", ""),
        ("failed", "RuntimeError: executor closed"),
    ]


def test_request_japanese_rescue_start_does_not_submit_duplicate_pending_future():
    statuses = []
    submitted = []
    pending = Future()

    class Executor:
        def submit(self, callback):
            submitted.append(callback)
            return pending

    worker = SimpleNamespace(
        japanese_rescue_enabled=True,
        japanese_rescue_runtime=SimpleNamespace(
            state=workers_module.JapaneseOCRRuntimeState.starting,
            start=lambda: True,
        ),
        _japanese_rescue_executor=Executor(),
        _japanese_rescue_load_future=None,
        japanese_rescue_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
    )

    OCRWorker.request_japanese_rescue_start(worker)
    OCRWorker.request_japanese_rescue_start(worker)

    assert len(submitted) == 1
    assert worker._japanese_rescue_load_future is pending
    assert statuses == [("starting", "")]


def test_cleanup_disables_japanese_runtime_and_shuts_down_executor():
    calls = []

    class Runtime:
        def disable(self):
            calls.append("disable")

    class Executor:
        def shutdown(self, **kwargs):
            calls.append(("shutdown", kwargs))

    worker = SimpleNamespace(
        japanese_rescue_runtime=Runtime(),
        _japanese_rescue_executor=Executor(),
        shutdown_local_vision_runtime=lambda: calls.append("vision"),
    )

    OCRWorker.cleanup(worker)

    assert calls == [
        "disable",
        ("shutdown", {"wait": True}),
        "vision",
    ]

def test_translate_text_preferred_uses_local_ai_without_google_api_key():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    worker.local_multimodal_enabled = True
    worker.local_multimodal_model = "translategemma-4b-it-local"
    worker._get_translation_provider = lambda name: object() if name == "gemma" else None
    worker.translate_text_gemma = lambda text: f"AI:{text}"
    worker.translate_text_google = lambda text: f"GOOGLE:{text}"

    assert OCRWorker.translate_text_preferred(worker, "Hello") == "AI:Hello"


def test_translate_multimodal_gemma_prefers_local_provider_for_local_model():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    worker.local_multimodal_enabled = True
    worker.local_multimodal_model = "translategemma-4b-it-local"
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
            return [SimpleNamespace(text="本地翻譯", model="gemma-3-4b-it-local")]

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


def test_refresh_translation_registry_applies_local_multimodal_config():
    from translation_providers import (
        GemmaTranslationProvider,
        GoogleTranslationProvider,
        LocalMultimodalProvider,
    )

    worker = make_worker_stub()
    worker.use_gemma_translation = False
    worker.gemma_prompt = ""
    worker.screenshot_gemma_prompt = "remote screenshot prompt"
    worker.gemma_auto_switch_enabled = False
    worker.translation_target_lang = "zh-TW"
    worker.local_gemma_temperature = 0.2
    worker.local_gemma_repeat_penalty = 1.15
    worker.local_multimodal_enabled = True
    worker.local_vision_runtime = None
    worker.local_multimodal_base_url = "http://localhost:11434/v1"
    worker.local_multimodal_model = "vision-local"
    worker.local_multimodal_timeout_seconds = 45
    worker._translation_registry_batch_depth = 0
    worker._translation_registry_batch_dirty = False
    worker.google_translation_provider = GoogleTranslationProvider(target_lang="zh-TW")
    worker.gemma_translation_provider = GemmaTranslationProvider(
        google_api_key="",
        gemma_model="gemma-3-27b-it",
        target_lang="zh-TW",
    )
    worker.local_multimodal_provider = LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="old-model",
        target_lang="en",
        enabled=False,
        timeout_seconds=20,
    )

    OCRWorker._refresh_translation_registry(worker)

    provider = worker.translation_registry.get("local_multimodal")
    assert provider.available() is True
    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.model_name == "vision-local"
    assert provider.timeout_seconds == 45
    assert worker.gemma_translation_provider.screenshot_gemma_prompt == "remote screenshot prompt"

def test_refresh_translation_registry_gates_embedded_runtime_readiness():
    from translation_providers import (
        GemmaTranslationProvider,
        GoogleTranslationProvider,
        LocalMultimodalProvider,
    )

    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    worker.gemma_prompt = ""
    worker.screenshot_gemma_prompt = ""
    worker.gemma_auto_switch_enabled = False
    worker.translation_target_lang = "zh-TW"
    worker.local_gemma_temperature = 0.2
    worker.local_gemma_repeat_penalty = 1.15
    worker.local_multimodal_enabled = True
    worker.local_multimodal_base_url = "http://fake-config:11434/v1"
    worker.local_multimodal_model = "vision-local"
    worker.local_multimodal_timeout_seconds = 45
    worker._translation_registry_batch_depth = 0
    worker._translation_registry_batch_dirty = False
    worker.google_translation_provider = GoogleTranslationProvider(target_lang="zh-TW")
    worker.gemma_translation_provider = GemmaTranslationProvider(
        google_api_key="",
        gemma_model="gemma-3-27b-it",
        target_lang="zh-TW",
    )
    
    worker.local_vision_runtime = SimpleNamespace(_state=SimpleNamespace(name="stopped", detail=""))
    worker.local_multimodal_provider = LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="old-model",
        target_lang="en",
        enabled=False,
        timeout_seconds=20,
    )
    worker.request_local_vision_start = lambda: None

    OCRWorker._refresh_translation_registry(worker)

    provider = worker.translation_registry.get("local_multimodal")
    assert provider.available() is False
    assert provider.base_url == ""
    assert worker.translation_registry.get("gemma") is provider

def test_multimodal_routing_uses_enabled_local_endpoint_for_non_local_text_model():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "gemma-3-27b-it"
    worker.active_gemma_model = worker.gemma_model
    worker.local_multimodal_enabled = True
    worker.local_multimodal_model = "vision-local"

    assert worker.has_local_multimodal_ai() is True
    assert worker.resolve_multimodal_provider_name() == "local_multimodal"

def test_request_local_vision_start_runs_runtime_in_single_executor():
    statuses = []
    refreshes = []
    submitted = []

    class ImmediateExecutor:
        def submit(self, callback):
            submitted.append(callback)
            future = Future()
            future.set_result(callback())
            return future

    class FakeRuntime:
        def start(self):
            return SimpleNamespace(
                name="ready",
                detail="",
                base_url="http://127.0.0.1:43123/v1",
                mode="cpu",
            )

    class FakeProvider:
        def __init__(self):
            self.runtime_updates = []

        def update_runtime(self, base_url, model_name, ready):
            self.runtime_updates.append((base_url, model_name, ready))

    runtime = FakeRuntime()
    provider = FakeProvider()
    worker = SimpleNamespace(
        use_gemma_translation=True,
        local_multimodal_enabled=True,
        local_vision_runtime=runtime,
        local_multimodal_provider=provider,
        vision_executor=ImmediateExecutor(),
        _local_vision_load_future=None,
        local_vision_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
        _refresh_translation_registry=lambda: refreshes.append(True),
    )

    OCRWorker.request_local_vision_start(worker)

    assert len(submitted) == 1
    assert statuses == [("starting", ""), ("ready", "")]
    assert provider.runtime_updates == [
        ("http://127.0.0.1:43123/v1", "gemma-3-4b-it", True),
    ]
    assert refreshes == [True]


def test_failed_vision_runtime_keeps_local_server_route_unavailable():
    future = Future()
    future.set_result(SimpleNamespace(name="failed", detail="health_timeout", base_url="", mode="gpu"))
    registrations = []
    statuses = []
    worker = SimpleNamespace(
        _local_vision_load_future=future,
        local_multimodal_provider=SimpleNamespace(
            update_runtime=lambda *args, **kwargs: None,
        ),
        gemma_translation_provider=SimpleNamespace(),
        _is_local_model_active=lambda: True,
        local_multimodal_model="gemma-3-4b-it",
        translation_registry=SimpleNamespace(
            register=lambda *args: registrations.append(args),
        ),
        local_vision_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
    )

    OCRWorker._on_local_vision_load_done(worker, future)

    assert registrations == []
    assert statuses == [("failed", "health_timeout")]


def test_failed_vision_runtime_keeps_remote_text_provider_unchanged():
    future = Future()
    future.set_result(SimpleNamespace(name="failed", detail="health_timeout", base_url="", mode="gpu"))
    registrations = []
    remote_provider = SimpleNamespace()
    worker = SimpleNamespace(
        _local_vision_load_future=future,
        local_multimodal_provider=SimpleNamespace(update_runtime=lambda *args, **kwargs: None),
        gemma_translation_provider=remote_provider,
        _is_local_model_active=lambda: False,
        local_multimodal_model="gemma-3-4b-it",
        translation_registry=SimpleNamespace(register=lambda *args: registrations.append(args)),
        local_vision_status=SimpleNamespace(emit=lambda *args: None),
    )
    worker._restore_configured_text_provider = lambda: OCRWorker._restore_configured_text_provider(worker)

    OCRWorker._on_local_vision_load_done(worker, future)

    assert registrations == []


def test_vision_runtime_exception_keeps_remote_text_provider_unchanged():
    future = Future()
    future.set_exception(RuntimeError("startup failed"))
    registrations = []
    statuses = []
    remote_provider = SimpleNamespace()
    worker = SimpleNamespace(
        _local_vision_load_future=future,
        local_multimodal_provider=SimpleNamespace(update_runtime=lambda *args, **kwargs: None),
        gemma_translation_provider=remote_provider,
        _is_local_model_active=lambda: False,
        translation_registry=SimpleNamespace(register=lambda *args: registrations.append(args)),
        local_vision_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
    )
    worker._restore_configured_text_provider = lambda: OCRWorker._restore_configured_text_provider(worker)

    OCRWorker._on_local_vision_load_done(worker, future)

    assert registrations == []
    assert statuses == [("failed", "RuntimeError: startup failed")]

def test_request_local_vision_start_does_not_submit_duplicate_future():
    statuses = []
    submitted = []
    pending = Future()

    class Executor:
        def submit(self, callback):
            submitted.append(callback)
            return pending

    worker = SimpleNamespace(
        use_gemma_translation=True,
        local_multimodal_enabled=True,
        local_vision_runtime=SimpleNamespace(start=lambda: None),
        local_multimodal_provider=SimpleNamespace(),
        vision_executor=Executor(),
        _local_vision_load_future=None,
        local_vision_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
    )

    OCRWorker.request_local_vision_start(worker)
    OCRWorker.request_local_vision_start(worker)

    assert len(submitted) == 1
    assert statuses == [("starting", "")]


def test_request_local_vision_start_reports_submit_failure():
    statuses = []

    class ClosedExecutor:
        def submit(self, callback):
            raise RuntimeError("executor closed")

    provider = SimpleNamespace(runtime_updates=[])
    provider.update_runtime = lambda *args: provider.runtime_updates.append(args)
    worker = SimpleNamespace(
        use_gemma_translation=True,
        local_multimodal_enabled=True,
        local_vision_runtime=SimpleNamespace(start=lambda: None),
        local_multimodal_provider=provider,
        vision_executor=ClosedExecutor(),
        _local_vision_load_future=None,
        local_vision_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
        _refresh_translation_registry=lambda: None,
    )

    OCRWorker.request_local_vision_start(worker)

    assert statuses == [
        ("starting", ""),
        ("failed", "RuntimeError: executor closed"),
    ]
    assert provider.runtime_updates[-1] == ("", "", False)

def test_local_model_status_wrapper_ignores_deleted_qt_signal():
    class DeletedSignalWorker:
        @property
        def local_model_status(self):
            raise RuntimeError("C++ object already deleted")

    OCRWorker._emit_local_model_status(DeletedSignalWorker(), "failed", "closed")


def test_run_ocr_explores_thresholds_after_fast_path_misses():
    class ThresholdBackend:
        def recognize(self, image):
            if float(image.mean()) < 200:
                return SimpleNamespace(lines=[])
            line = SimpleNamespace(
                text="x",
                words=[],
                bounding_rect=SimpleNamespace(x=0, y=0, width=12, height=12),
            )
            return SimpleNamespace(lines=[line])

    worker = OCRWorker.__new__(OCRWorker)
    worker.ocr_backends = [ThresholdBackend()]
    worker.scan_mode = "fullscreen"
    worker.binary_threshold = 100
    worker.auto_threshold_enabled = False
    worker.exact_image_cache = ExactImageCache()
    cached_image = np.zeros((2, 2, 3), dtype=np.uint8)
    worker.exact_image_cache.put(cached_image, "old-threshold", ["cached"], "google", "state")
    emitted_thresholds = []
    worker.threshold_suggested = SimpleNamespace(emit=emitted_thresholds.append)

    image = np.full((20, 40, 3), 240, dtype=np.uint8)
    used_threshold, items = worker.run_ocr_with_best_threshold(image, 0, 0)

    assert used_threshold == 250
    assert emitted_thresholds == [250]
    assert [item["text"] for item in items] == ["x"]
    assert len(worker.exact_image_cache) == 0
def _make_threshold_selection_worker(recognized_results):
    worker = OCRWorker.__new__(OCRWorker)
    worker.binary_threshold = 100
    worker.auto_threshold_enabled = False
    worker.google_api_key = ""
    worker.scan_mode = "region"
    worker.last_auto_threshold_refresh_ms = 0.0
    worker.exact_image_cache = ExactImageCache()
    worker.threshold_suggested = SimpleNamespace(emit=lambda _value: None)
    worker.rotate_crop_for_ocr = lambda crop, _orientation: crop
    results = iter(recognized_results)
    worker._recognize_with_backends = lambda _image: next(results)
    worker.extract_raw_items = lambda result, *_args: result or []
    worker.remap_items_from_orientation = lambda items, *_args: items
    worker.score_ocr_items = lambda items: (-5, items) if items else (-1, [])
    return worker


def test_threshold_selection_does_not_replace_nonempty_negative_score_with_empty():
    valid_item = {"text": "1", "x": 0, "y": 0, "w": 10, "h": 10}
    worker = _make_threshold_selection_worker([[valid_item], []])

    threshold, items = OCRWorker.run_ocr_with_best_threshold(
        worker,
        np.full((20, 40, 3), 128, dtype=np.uint8),
        0,
        0,
        candidate_thresholds=[100, 200],
        orientation_candidates=[0],
        force_bg_refresh=True,
    )

    assert threshold == 100
    assert items == [valid_item]


def test_orientation_selection_prefers_nonempty_result_over_higher_empty_score():
    valid_item = {"text": "1", "x": 0, "y": 0, "w": 10, "h": 10}
    worker = _make_threshold_selection_worker([[valid_item], []])

    threshold, items = OCRWorker.run_ocr_with_best_threshold(
        worker,
        np.full((20, 40, 3), 128, dtype=np.uint8),
        0,
        0,
        candidate_thresholds=[100],
        orientation_candidates=[0, 90],
        force_bg_refresh=True,
    )

    assert threshold == 100
    assert items == [valid_item]

def test_prepare_local_vision_ensures_assets_before_runtime_start(monkeypatch):
    calls = []
    assets = SimpleNamespace(managed=True)
    runtime = SimpleNamespace(start=lambda: calls.append("start") or "ready")
    worker = SimpleNamespace(
        _local_vision_assets=assets,
        _local_vision_cancel_event=None,
        local_vision_runtime=runtime,
        local_vision_status=SimpleNamespace(emit=lambda *args: None),
    )
    monkeypatch.setattr(
        workers_module,
        "ensure_vision_model_assets",
        lambda selected, **kwargs: calls.append(("ensure", selected)),
    )

    result = OCRWorker._prepare_and_start_local_vision(worker)

    assert result == "ready"
    assert calls == [("ensure", assets), "start"]


def test_disabling_local_multimodal_cancels_pending_asset_download():
    cancel_event = SimpleNamespace(set_calls=0)
    cancel_event.set = lambda: setattr(cancel_event, "set_calls", cancel_event.set_calls + 1)
    worker = make_worker_stub()
    worker._local_vision_cancel_event = cancel_event

    OCRWorker.set_local_multimodal_config(
        worker,
        enabled=False,
        base_url="http://127.0.0.1:8080/v1",
        model_name="gemma-3-4b-it",
        timeout_seconds=20,
    )

    assert cancel_event.set_calls == 1

def _make_segment_repair_worker(target_lang="zh-TW"):
    worker = OCRWorker.__new__(OCRWorker)
    worker.translation_target_lang = target_lang
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker.debug_messages = []
    worker.log_ai_debug = worker.debug_messages.append
    return worker


def test_multimodal_segment_repair_only_retries_source_echo():
    worker = _make_segment_repair_worker()
    calls = []
    worker.translate_text_preferred_with_provider = (
        lambda source: calls.append(source) or ("葡萄酒俱樂部", "google")
    )

    repaired, providers = OCRWorker._repair_suspicious_multimodal_segments(
        worker,
        ["Hello world", "Wine Club", "これは日本語です"],
        ["你好世界", "Wine Club", "這是日文"],
    )

    assert repaired == ["你好世界", "葡萄酒俱樂部", "這是日文"]
    assert providers == ["local_multimodal", "google", "local_multimodal"]
    assert calls == ["Wine Club"]
    assert "reason=source_echo" in worker.debug_messages[0]
    assert "Wine Club" not in worker.debug_messages[0]


def test_multimodal_segment_repair_keeps_valid_short_translations_without_retry():
    worker = _make_segment_repair_worker()
    calls = []
    worker.translate_text_preferred_with_provider = lambda source: calls.append(source) or ("錯誤", "google")

    repaired, providers = OCRWorker._repair_suspicious_multimodal_segments(
        worker,
        ["Yes", "Done", "こんにちは"],
        ["好", "完成", "你好"],
    )

    assert repaired == ["好", "完成", "你好"]
    assert providers == ["local_multimodal"] * 3
    assert calls == []
    assert worker.debug_messages == []


def test_multimodal_segment_repair_retries_multiline_low_coverage():
    worker = _make_segment_repair_worker()
    source = "First detailed line.\nSecond detailed line.\nThird detailed line."
    worker.translate_text_preferred_with_provider = lambda value: ("第一行\n第二行\n第三行", "google")

    repaired, providers = OCRWorker._repair_suspicious_multimodal_segments(worker, [source], ["短"])

    assert repaired == ["第一行\n第二行\n第三行"]
    assert providers == ["google"]
    assert "reason=low_coverage" in worker.debug_messages[0]


def test_translate_items_with_ai_and_providers_fails_open_to_text_route():
    worker = _make_segment_repair_worker()
    worker.has_any_multimodal_ai = lambda: True

    def raise_multimodal_failure(*_args, **_kwargs):
        raise ValueError("degenerate_local_multimodal_response")

    worker.translate_multimodal_gemma = raise_multimodal_failure
    worker.translate_items_in_batches_with_providers = (
        lambda source_texts, batch_size=8: (["葡萄酒俱樂部"], ["google"])
    )

    translated, providers = OCRWorker.translate_items_with_ai_and_providers(
        worker,
        ["Wine Club"],
        [{"image": "x"}],
    )

    assert translated == ["葡萄酒俱樂部"]
    assert providers == ["google"]


def test_translate_items_with_ai_and_providers_fails_open_when_parser_raises():
    worker = _make_segment_repair_worker()
    worker.has_any_multimodal_ai = lambda: True
    worker.translate_multimodal_gemma = lambda image_parts, source_texts: "payload"

    def raise_parser_failure(*_args, **_kwargs):
        raise ValueError("malformed_segmented_json")

    worker.parse_segmented_translation_json = raise_parser_failure
    worker.translate_items_in_batches_with_providers = (
        lambda source_texts, batch_size=8: (["葡萄酒俱樂部"], ["google"])
    )

    translated, providers = OCRWorker.translate_items_with_ai_and_providers(
        worker,
        ["Wine Club"],
        [{"image": "x"}],
    )

    assert translated == ["葡萄酒俱樂部"]
    assert providers == ["google"]


def test_degenerate_multimodal_gate_rejects_long_repeated_outputs():
    assert OCRWorker._has_degenerate_multimodal_segments(
        [
            "This is a long source line one",
            "This is a long source line two",
            "This is a long source line three",
            "This is a long source line four",
        ],
        ["這是一個長篇重複翻譯"] * 3 + ["另一個不同結果"],
    )


def test_degenerate_multimodal_gate_allows_short_repeated_exclamations():
    assert not OCRWorker._has_degenerate_multimodal_segments(
        ["Oh!", "Oh?", "Oh...", "Oh!!"],
        ["喔！"] * 4,
    )


def test_degenerate_multimodal_gate_rejects_short_output_for_long_sources():
    assert OCRWorker._has_degenerate_multimodal_segments(
        [
            "This is a long source line one",
            "This is a long source line two",
            "This is a long source line three",
            "This is a long source line four",
        ],
        ["無"] * 4,
    )


def test_degenerate_multimodal_gate_allows_repeated_source_lines():
    assert not OCRWorker._has_degenerate_multimodal_segments(
        ["這是一段很長的原文"] * 4,
        ["這是一個長篇重複翻譯"] * 4,
    )


def test_translate_items_with_ai_and_providers_fails_open_on_degenerate_segments():
    worker = _make_segment_repair_worker()
    worker.has_any_multimodal_ai = lambda: True
    worker.translate_multimodal_gemma = lambda image_parts, source_texts: "payload"
    worker.parse_segmented_translation_json = lambda payload, count: (
        ["這是一個長篇重複翻譯"] * 3 + ["另一個不同結果"]
    )
    worker.translate_items_in_batches_with_providers = (
        lambda source_texts, batch_size=8: (["文字路由結果"] * len(source_texts), ["google"] * len(source_texts))
    )

    translated, providers = OCRWorker.translate_items_with_ai_and_providers(
        worker,
        ["這是第一段很長的原文", "這是第二段很長的原文", "這是第三段很長的原文", "這是第四段很長的原文"],
        [{"image": "x"}],
    )

    assert translated == ["文字路由結果"] * 4
    assert providers == ["google"] * 4


def test_translate_items_with_ai_fails_open_on_degenerate_segments():
    worker = _make_segment_repair_worker()
    worker.has_any_multimodal_ai = lambda: True
    worker.translate_multimodal_gemma = lambda image_parts, source_texts: "payload"
    worker.parse_segmented_translation_json = lambda payload, count: (
        ["這是一個長篇重複翻譯"] * 3 + ["另一個不同結果"]
    )
    worker.translate_items_in_batches = (
        lambda source_texts, batch_size=8: ["文字路由結果"] * len(source_texts)
    )

    translated = OCRWorker.translate_items_with_ai(
        worker,
        ["這是第一段很長的原文", "這是第二段很長的原文", "這是第三段很長的原文", "這是第四段很長的原文"],
        [{"image": "x"}],
    )

    assert translated == ["文字路由結果"] * 4


def test_translate_items_with_ai_repairs_parsed_segments_selectively():
    worker = _make_segment_repair_worker()
    worker.has_any_multimodal_ai = lambda: True
    worker.translate_multimodal_gemma = lambda image_parts, source_texts: "payload"
    worker.parse_segmented_translation_json = lambda payload, count: ["Wine Club", "完成"]
    calls = []
    worker.translate_text_preferred_with_provider = (
        lambda source: calls.append(source) or ("葡萄酒俱樂部", "google")
    )

    translated = OCRWorker.translate_items_with_ai(worker, ["Wine Club", "Done"], [{"image": "x"}])

    assert translated == ["葡萄酒俱樂部", "完成"]
    assert calls == ["Wine Club"]

def test_multimodal_segment_repair_rejects_invalid_text_fallback():
    worker = _make_segment_repair_worker()
    worker.translate_text_preferred_with_provider = lambda source: (source, "google")

    repaired, providers = OCRWorker._repair_suspicious_multimodal_segments(
        worker,
        ["Wine Club"],
        ["Wine Club"],
    )

    assert repaired == ["Wine Club"]
    assert providers == ["local_multimodal"]

def test_screenshot_provider_empty_result_fails_after_text_fallback_exhausted():
    worker = _make_segment_repair_worker()
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.scan_mode = "region"
    worker.region_render_mode = "screenshot"
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    provider = SimpleNamespace(
        translate_screenshot=lambda image_parts, **kwargs: SimpleNamespace(text="", model="local")
    )
    worker._get_translation_provider = lambda name: provider
    worker.normalize_gemma_model = lambda model: model
    worker.sync_gemma_call_timestamps_from_provider = lambda value: None
    worker.convert_to_trad = lambda text: text
    calls = []
    worker.translate_text_preferred_with_provider = (
        lambda source: calls.append(source) or ("", "")
    )

    with pytest.raises(ValueError, match="empty_gemma_screenshot_response"):
        OCRWorker.translate_screenshot_gemma(worker, [{"image": "x"}], "Hello world")

    assert calls == []
    assert any("reason=empty" in message for message in worker.debug_messages)

def test_screenshot_provider_fallback_records_actual_provider_once():
    worker = _make_segment_repair_worker()
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.scan_mode = "region"
    worker.region_render_mode = "screenshot"
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    provider = SimpleNamespace(
        translate_screenshot=lambda image_parts, **kwargs: SimpleNamespace(text="Wine Club", model="local")
    )
    worker._get_translation_provider = lambda name: provider
    worker.normalize_gemma_model = lambda model: model
    worker.sync_gemma_call_timestamps_from_provider = lambda value: None
    worker.convert_to_trad = lambda text: text
    calls = []
    worker.translate_text_preferred_with_provider = (
        lambda source: calls.append(source) or ("葡萄酒俱樂部", "google")
    )

    translated = OCRWorker.translate_screenshot_gemma(worker, [{"image": "x"}], "Wine Club")

    assert translated == "葡萄酒俱樂部"
    assert worker._last_screenshot_translation_provider == "google"
    assert calls == ["Wine Club"]


def test_refresh_translation_registry_does_not_require_embedded_provider_for_remote_model():
    worker = OCRWorker.__new__(OCRWorker)
    worker._translation_registry_batch_depth = 0
    worker._translation_registry_batch_dirty = False
    worker.google_api_key = "test-key"
    worker.gemma_model = "gemma-4-31b-it"
    worker.gemma_prompt = ""
    worker.screenshot_gemma_prompt = ""
    worker.use_gemma_translation = True
    worker.gemma_auto_switch_enabled = False
    worker.translation_target_lang = "zh-TW"
    worker.local_multimodal_enabled = False
    worker.local_multimodal_base_url = "http://127.0.0.1:8080/v1"
    worker.local_multimodal_model = "vision-local"
    worker.local_multimodal_timeout_seconds = 20
    worker.local_vision_runtime = None
    worker.request_local_vision_start = lambda: None

    class Provider:
        def __init__(self, name):
            self.name = name

        def available(self):
            return True

    worker.google_translation_provider = SimpleNamespace(set_target_lang=lambda value: None, name="google")
    worker.gemma_translation_provider = Provider("gemma")
    worker.gemma_translation_provider.update_config = lambda **kwargs: None
    worker.local_multimodal_provider = Provider("local_multimodal")
    worker.local_multimodal_provider.enabled = False
    worker.local_multimodal_provider.timeout_seconds = 20
    worker.local_multimodal_provider.update_runtime = lambda *args, **kwargs: None
    worker.local_multimodal_provider.update_generation_config = lambda **kwargs: None

    OCRWorker._refresh_translation_registry(worker)

    assert worker.translation_registry.get("gemma") is worker.gemma_translation_provider

def test_refresh_translation_registry_exposes_bounded_error_code(monkeypatch):
    worker = OCRWorker.__new__(OCRWorker)
    worker._translation_registry_batch_depth = 0
    worker.translation_registry = "last-known-good"
    worker._build_translation_registry_config = lambda: (_ for _ in ()).throw(
        RuntimeError("secret prompt and API key must not be logged")
    )
    messages = []
    monkeypatch.setattr(workers_module.logger, "error", messages.append)

    OCRWorker._refresh_translation_registry(worker)

    assert worker.translation_registry_error_code == "translation_registry_refresh_failed"
    assert worker.translation_registry == "last-known-good"
    assert messages
    assert "translation_registry_refresh_failed" in messages[0]
    assert "secret prompt" not in messages[0]
    assert "API key" not in messages[0]


def test_preferred_result_attributes_expected_ai_failure_to_google_cache_hit():
    from urllib import error
    from translation_contracts import TranslationResult

    worker = OCRWorker.__new__(OCRWorker)
    worker.has_ai_text_provider = lambda: True
    worker.get_current_ai_provider = lambda: "local_multimodal"
    worker._translate_text_gemma_result = lambda _text: (_ for _ in ()).throw(
        error.URLError("private OCR text")
    )
    worker._translate_text_google_result = lambda _text: TranslationResult(
        text="Google 譯文",
        provider="google",
        from_cache=True,
    )

    result = OCRWorker._translate_text_preferred_result(worker, "source")

    assert result.text == "Google 譯文"
    assert result.provider == "google"
    assert result.from_cache is True
    assert result.requested_provider == "local_multimodal"
    assert result.fallback_reason == "provider_error"

def test_worker_reports_actual_provider_from_gemma_result():
    from translation_contracts import TranslationResult

    worker = OCRWorker.__new__(OCRWorker)
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.active_gemma_model = worker.gemma_model
    worker.convert_to_trad = lambda text: text
    worker.normalize_gemma_model = lambda model: model
    worker.sync_gemma_call_timestamps_from_provider = lambda provider: None
    worker.get_current_ai_provider = lambda: "gemma-3"

    class Provider:
        def translate(self, text):
            return TranslationResult(
                text="Google 翻譯",
                provider="google",
                model="local",
                requested_provider="local_gemma",
                fallback_reason="bad_translation",
            )

    worker._get_translation_provider = lambda name: Provider()

    translated, provider = OCRWorker.translate_text_gemma_with_provider(worker, "source")

    assert translated == "Google 翻譯"
    assert provider == "google"
    assert worker.active_gemma_model == worker.gemma_model


def test_worker_uses_provider_attribution_from_screenshot_result():
    worker = _make_segment_repair_worker()
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.scan_mode = "region"
    worker.region_render_mode = "screenshot"
    worker.resolve_multimodal_provider_name = lambda: "local_multimodal"
    provider = SimpleNamespace(
        translate_screenshot=lambda image_parts, **kwargs: SimpleNamespace(
            text="翻譯結果",
            model="local",
            provider="google",
            requested_provider="local_multimodal",
            fallback_reason="server_fallback",
        )
    )
    worker._get_translation_provider = lambda name: provider
    worker.normalize_gemma_model = lambda model: model
    worker.sync_gemma_call_timestamps_from_provider = lambda value: None
    worker.convert_to_trad = lambda text: text

    translated = OCRWorker.translate_screenshot_gemma(worker, [{"image": "x"}], "Wine Club")

    assert translated == "翻譯結果"
    assert worker._last_screenshot_translation_provider == "google"
    assert worker._last_screenshot_translation_result.provider == "google"
    assert worker._last_screenshot_translation_result.requested_provider == "local_multimodal"
    assert worker._last_screenshot_translation_result.fallback_reason == "server_fallback"

def test_worker_initialization_has_no_embedded_provider_or_loader(monkeypatch):
    monkeypatch.setattr(workers_module, "resolve_preferred_vision_assets", lambda _root: SimpleNamespace())

    class Runtime:
        def __init__(self, *_args, **_kwargs):
            self._state = SimpleNamespace(name="stopped", detail="", base_url="")
            self.profile_name = "vision"

    class JapaneseRuntime:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(workers_module, "LocalVisionRuntime", Runtime)
    monkeypatch.setattr(workers_module, "JapaneseOCRRuntime", JapaneseRuntime)

    worker = OCRWorker()

    assert "LocalGemmaProvider" not in workers_module.__dict__
    for attribute in (
        "local_gemma_provider",
        "_local_model_executor",
        "_local_model_load_future",
        "_local_model_cancel_event",
    ):
        assert not hasattr(worker, attribute)


def test_old_local_model_loader_api_is_unreachable():
    for name in (
        "_prepare_and_load_local_model",
        "request_local_model_load",
        "_on_local_model_load_done",
        "shutdown_local_model_loader",
    ):
        assert not hasattr(OCRWorker, name)


def test_server_status_continues_local_model_status_for_text_profile():
    vision_statuses = []
    model_statuses = []
    worker = SimpleNamespace(
        _local_runtime_profile="text",
        local_vision_status=SimpleNamespace(emit=lambda *args: vision_statuses.append(args)),
        local_model_status=SimpleNamespace(emit=lambda *args: model_statuses.append(args)),
    )

    OCRWorker._emit_local_vision_status(worker, "starting", "")
    OCRWorker._emit_local_vision_status(worker, "progress", "42|model_download")
    OCRWorker._emit_local_vision_status(worker, "ready", "")

    assert vision_statuses == [
        ("starting", ""),
        ("progress", "42|model_download"),
        ("ready", ""),
    ]
    assert model_statuses == [
        ("loading", ""),
        ("loading", "42|model_download"),
        ("ready", ""),
    ]


def test_cleanup_only_shuts_down_server_runtime():
    calls = []
    worker = SimpleNamespace(
        _bg_threshold_executor=SimpleNamespace(shutdown=lambda **kwargs: calls.append(("background", kwargs))),
        japanese_rescue_runtime=SimpleNamespace(disable=lambda: calls.append(("japanese", {}))),
        _japanese_rescue_executor=SimpleNamespace(shutdown=lambda **kwargs: calls.append(("japanese_executor", kwargs))),
        shutdown_local_vision_runtime=lambda: calls.append(("server", {})),
    )

    OCRWorker.cleanup(worker)

    assert calls == [
        ("background", {"wait": True}),
        ("japanese", {}),
        ("japanese_executor", {"wait": True}),
        ("server", {}),
    ]

def test_failed_vision_runtime_never_restores_embedded_local_model():
    future = Future()
    future.set_result(SimpleNamespace(name="failed", detail="health_timeout", base_url="", mode="gpu"))
    registrations = []
    local_multimodal = SimpleNamespace(update_runtime=lambda *args, **kwargs: None)
    worker = SimpleNamespace(
        _local_vision_load_future=future,
        local_multimodal_provider=local_multimodal,
        gemma_translation_provider=SimpleNamespace(),
        _is_local_model_active=lambda: True,
        local_multimodal_model="gemma-3-4b-it",
        translation_registry=SimpleNamespace(register=lambda *args: registrations.append(args)),
        local_vision_status=SimpleNamespace(emit=lambda *args: None),
    )

    OCRWorker._on_local_vision_load_done(worker, future)

    assert registrations == []

def test_prepare_local_text_runtime_requests_text_profile(monkeypatch):
    calls = []
    profiles = []

    class Runtime:
        profile_name = "vision"

        def set_profile(self, profile):
            profiles.append(profile)

        def start(self):
            return "ready"

    worker = SimpleNamespace(
        _local_vision_assets=SimpleNamespace(),
        _local_vision_cancel_event=None,
        local_vision_runtime=Runtime(),
        _local_text_runtime_required=True,
        local_multimodal_enabled=False,
        local_vision_status=SimpleNamespace(emit=lambda *args: None),
    )
    monkeypatch.setattr(
        workers_module,
        "ensure_vision_model_assets",
        lambda _assets, **kwargs: calls.append(kwargs),
    )

    assert OCRWorker._prepare_and_start_local_vision(worker) == "ready"
    assert profiles == ["text"]
    assert calls[0]["required_fields"] == ("server_path", "model_path")
