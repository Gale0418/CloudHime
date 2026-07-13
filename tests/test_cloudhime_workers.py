from concurrent.futures import Future
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
    worker.local_multimodal_enabled = False
    worker.local_multimodal_base_url = "http://127.0.0.1:8080/v1"
    worker.local_multimodal_model = ""
    worker.local_multimodal_timeout_seconds = 20

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


def test_set_local_multimodal_config_accepts_values_and_refreshes_registry():
    worker = make_worker_stub()

    OCRWorker.set_local_multimodal_config(
        worker,
        enabled=True,
        base_url="http://localhost:11434/v1/",
        model_name="vision-local",
        timeout_seconds=45,
    )

    assert worker.local_multimodal_enabled is True
    assert worker.local_multimodal_base_url == "http://localhost:11434/v1"
    assert worker.local_multimodal_model == "vision-local"
    assert worker.local_multimodal_timeout_seconds == 45
    assert worker.refresh_count == 1


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


def test_multimodal_routing_fallback():
    worker = make_worker_stub()

    assert worker.has_local_multimodal_ai() is False
    assert worker.has_remote_multimodal_ai() is False
    assert worker.resolve_multimodal_provider_name() is None


def test_local_gemma_model_id_selects_embedded_provider():
    worker = make_worker_stub()
    worker.gemma_model = "gemma-3-4b-it-local"
    worker.active_gemma_model = worker.gemma_model

    assert OCRWorker._is_local_model_active(worker) is True


def test_request_local_model_load_emits_loading_then_ready():
    statuses = []

    class ImmediateExecutor:
        def submit(self, callback):
            future = Future()
            future.set_result(callback())
            return future

    worker = SimpleNamespace(
        use_gemma_translation=True,
        _is_local_model_active=lambda: True,
        local_gemma_provider=SimpleNamespace(
            available=lambda: False,
            load_model=lambda: True,
            last_load_error="",
        ),
        local_model_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
        _local_model_executor=ImmediateExecutor(),
        _local_model_load_future=None,
    )

    OCRWorker.request_local_model_load(worker)

    assert statuses == [("loading", ""), ("ready", "")]


def test_request_local_model_load_reports_executor_submit_failure():
    statuses = []

    class ClosedExecutor:
        def submit(self, callback):
            raise RuntimeError("executor closed")

    worker = SimpleNamespace(
        use_gemma_translation=True,
        _is_local_model_active=lambda: True,
        local_gemma_provider=SimpleNamespace(
            available=lambda: False,
            load_model=lambda: True,
        ),
        local_model_status=SimpleNamespace(emit=lambda *args: statuses.append(args)),
        _local_model_executor=ClosedExecutor(),
        _local_model_load_future=None,
    )

    OCRWorker.request_local_model_load(worker)

    assert statuses == [
        ("loading", ""),
        ("failed", "RuntimeError: executor closed"),
    ]


def test_old_local_model_callback_does_not_clear_new_future():
    old_future = Future()
    old_future.set_result(True)
    new_future = Future()
    worker = SimpleNamespace(
        _local_model_load_future=new_future,
        local_model_status=SimpleNamespace(emit=lambda *args: None),
        local_gemma_provider=SimpleNamespace(last_load_error=""),
    )

    OCRWorker._on_local_model_load_done(worker, old_future)

    assert worker._local_model_load_future is new_future

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
        LocalGemmaProvider,
        LocalMultimodalProvider,
    )

    worker = make_worker_stub()
    worker.use_gemma_translation = False
    worker.gemma_prompt = ""
    worker.screenshot_gemma_prompt = ""
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
    worker.local_gemma_provider = LocalGemmaProvider(
        model_path="models/gemma-3-4b-it.Q4_K_M.gguf",
        target_lang="zh-TW",
        enabled=False,
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

def test_refresh_translation_registry_gates_embedded_runtime_readiness():
    from translation_providers import (
        GemmaTranslationProvider,
        GoogleTranslationProvider,
        LocalGemmaProvider,
        LocalMultimodalProvider,
    )

    worker = make_worker_stub()
    worker.use_gemma_translation = True
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
    worker.local_gemma_provider = LocalGemmaProvider(
        model_path="models/gemma-3-4b-it.Q4_K_M.gguf",
        target_lang="zh-TW",
        enabled=False,
    )
    
    worker.local_vision_runtime = SimpleNamespace(_state=SimpleNamespace(name="stopped", detail=""))
    worker.local_multimodal_provider = LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="old-model",
        target_lang="en",
        enabled=False,
        timeout_seconds=20,
    )
    worker.request_local_model_load = lambda: None
    worker.request_local_vision_start = lambda: None

    OCRWorker._refresh_translation_registry(worker)

    provider = worker.translation_registry.get("local_multimodal")
    assert provider.available() is False
    assert provider.base_url == ""

def test_multimodal_routing_uses_enabled_local_endpoint_for_non_local_text_model():
    worker = make_worker_stub()
    worker.use_gemma_translation = True
    worker.gemma_model = "gemma-3-27b-it"
    worker.active_gemma_model = worker.gemma_model
    worker.local_multimodal_enabled = True
    worker.local_multimodal_model = "vision-local"

    assert worker.has_local_multimodal_ai() is True
    assert worker.resolve_multimodal_provider_name() == "local_multimodal"

def test_shutdown_local_model_loader_stops_executor():
    calls = []
    worker = SimpleNamespace(
        _local_model_executor=SimpleNamespace(
            shutdown=lambda **kwargs: calls.append(kwargs)
        )
    )

    OCRWorker.shutdown_local_model_loader(worker)

    assert calls == [{"wait": False, "cancel_futures": True}]

def test_shutdown_local_model_loader_supports_python_38_executor():
    calls = []

    class LegacyExecutor:
        def shutdown(self, **kwargs):
            calls.append(kwargs)
            if "cancel_futures" in kwargs:
                raise TypeError("unexpected keyword argument 'cancel_futures'")

    worker = SimpleNamespace(_local_model_executor=LegacyExecutor())

    OCRWorker.shutdown_local_model_loader(worker)

    assert calls == [
        {"wait": False, "cancel_futures": True},
        {"wait": False},
    ]

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

    assert submitted == [runtime.start]
    assert statuses == [("starting", ""), ("ready", "")]
    assert provider.runtime_updates == [
        ("http://127.0.0.1:43123/v1", "gemma-3-4b-it", True),
    ]
    assert refreshes == [True]


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
