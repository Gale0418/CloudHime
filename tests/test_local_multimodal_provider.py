import json
import threading
from io import BytesIO

import pytest

import translation_providers as providers_module

from translation_providers import (
    LocalMultimodalProvider,
    LocalRequestCancelled,
    _LocalRequestScheduler,
)


def make_provider():
    return LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="gemma-3n-local",
        target_lang="zh-TW",
        enabled=True,
        timeout_seconds=12,
    )


def test_local_request_scheduler_serializes_fifo_without_merging_jobs():
    scheduler = _LocalRequestScheduler()
    first_started = threading.Event()
    release_first = threading.Event()
    second_queued = threading.Event()
    calls = []
    results = []

    def first_job():
        calls.append("first")
        first_started.set()
        assert release_first.wait(1)
        return "first-result"

    def second_job():
        calls.append("second")
        return "second-result"

    def second_cancel_predicate():
        second_queued.set()
        return False

    first_thread = threading.Thread(
        target=lambda: results.append(scheduler.run(first_job))
    )
    second_thread = threading.Thread(
        target=lambda: results.append(
            scheduler.run(second_job, cancel_predicate=second_cancel_predicate)
        )
    )
    first_thread.start()
    assert first_started.wait(1)
    second_thread.start()
    assert second_queued.wait(1)
    assert calls == ["first"]

    release_first.set()
    first_thread.join(timeout=1)
    second_thread.join(timeout=1)
    scheduler.close()

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert calls == ["first", "second"]
    assert sorted(results) == ["first-result", "second-result"]


def test_local_request_scheduler_cancels_queued_job_before_dispatch():
    scheduler = _LocalRequestScheduler()
    first_started = threading.Event()
    release_first = threading.Event()
    cancel_second = threading.Event()
    second_queued = threading.Event()
    dispatched = []
    errors = []

    def first_job():
        dispatched.append("first")
        first_started.set()
        assert release_first.wait(1)

    def second_job():
        dispatched.append("second")

    def second_cancel_predicate():
        second_queued.set()
        return cancel_second.is_set()

    first_thread = threading.Thread(target=lambda: scheduler.run(first_job))
    first_thread.start()
    assert first_started.wait(1)

    def run_second():
        try:
            scheduler.run(second_job, cancel_predicate=second_cancel_predicate)
        except LocalRequestCancelled:
            errors.append("cancelled")

    second_thread = threading.Thread(target=run_second)
    second_thread.start()
    assert second_queued.wait(1)
    cancel_second.set()
    second_thread.join(timeout=1)
    release_first.set()
    first_thread.join(timeout=1)
    scheduler.close()

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert dispatched == ["first"]
    assert errors == ["cancelled"]


def test_local_request_scheduler_cancels_queued_job_when_closed():
    scheduler = _LocalRequestScheduler()
    first_started = threading.Event()
    release_first = threading.Event()
    second_queued = threading.Event()
    dispatched = []
    errors = []

    def first_job():
        dispatched.append("first")
        first_started.set()
        assert release_first.wait(1)

    def second_job():
        dispatched.append("second")

    def second_cancel_predicate():
        second_queued.set()
        return False

    first_thread = threading.Thread(target=lambda: scheduler.run(first_job))
    first_thread.start()
    assert first_started.wait(1)

    def run_second():
        try:
            scheduler.run(second_job, cancel_predicate=second_cancel_predicate)
        except LocalRequestCancelled as exc:
            errors.append(str(exc))

    second_thread = threading.Thread(target=run_second)
    second_thread.start()
    assert second_queued.wait(1)

    scheduler.close()
    second_thread.join(timeout=1)
    release_first.set()
    first_thread.join(timeout=1)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert dispatched == ["first"]
    assert errors == ["local_request_scheduler_closed"]


def test_local_multimodal_provider_close_rejects_new_requests():
    provider = make_provider()

    provider.close()
    assert provider.available() is False

    with pytest.raises(RuntimeError, match="local_request_scheduler_closed"):
        provider._request_chat_completion({})


def test_local_multimodal_provider_close_cannot_reactivate_runtime():
    provider = make_provider()

    provider.close()
    provider.enabled = True
    provider.update_runtime(
        "http://127.0.0.1:8080/v1",
        "gemma-3n-local",
        ready=True,
    )

    assert provider.available() is False


def test_translate_multimodal_builds_openai_compatible_payload():
    provider = make_provider()
    payload = provider._build_chat_payload(
        prompt="Translate these lines",
        image_parts=[{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
        response_format="segmented_json",
    )

    assert payload["model"] == "gemma-3n-local"
    assert payload["messages"][0]["content"][0]["type"] == "text"
    assert payload["messages"][0]["content"][0]["text"] == "Translate these lines"
    assert payload["messages"][0]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,abc"},
    }


def test_translate_multimodal_parses_segmented_json_response():
    provider = make_provider()
    parsed = provider._parse_segmented_response(
        '{"segments":[{"index":0,"translation":"測試"},{"index":1,"translation":"選單"}]}',
        expected_count=2
    )

    assert parsed == ["測試", "選單"]


def test_translate_multimodal_retries_plain_text_when_json_mode_is_rejected():
    provider = make_provider()
    response_types = []

    def fake_request(payload):
        response_type = payload["response_format"]["type"]
        response_types.append(response_type)
        if response_type == "json_object":
            raise providers_module.error.HTTPError(
                url="http://127.0.0.1:8080/v1/chat/completions",
                code=400,
                msg="response format unsupported",
                hdrs=None,
                fp=None,
            )
        return '{"segments":[{"index":0,"translation":"翻譯"}]}'

    provider._request_chat_completion = fake_request
    result = provider.translate_multimodal(
        ["原文"],
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
    )

    assert [item.text for item in result] == ["翻譯"]
    assert response_types == ["json_object", "text"]

def test_translate_multimodal_does_not_retry_context_size_400():
    provider = make_provider()
    response_types = []

    def fake_request(payload):
        response_types.append(payload["response_format"]["type"])
        raise providers_module.error.HTTPError(
            url="http://127.0.0.1:8080/v1/chat/completions",
            code=400,
            msg="context too small",
            hdrs=None,
            fp=BytesIO(b'{"type":"exceed_context_size_error"}'),
        )

    provider._request_chat_completion = fake_request
    with pytest.raises(providers_module.error.HTTPError):
        provider.translate_multimodal(
            ["原文"],
            [{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
        )

    assert response_types == ["json_object"]

def test_translate_multimodal_prompt_includes_dictionary_hint():
    provider = make_provider()
    captured = {}

    def fake_request(payload):
        captured["prompt"] = payload["messages"][0]["content"][0]["text"]
        return '{"segments":[{"index":0,"translation":"雙點博物館"}]}'

    provider._request_chat_completion = fake_request

    provider.translate_multimodal(
        ["TWO POINT MUSEUM"],
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
    )

    assert "'TWO POINT MUSEUM' -> '雙點博物館'" in captured["prompt"]


def test_translate_text_reuses_multimodal_runtime_and_cache():
    provider = make_provider()
    payloads = []

    def fake_request(payload):
        payloads.append(payload)
        return "翻譯結果"

    provider._request_chat_completion = fake_request

    first = provider.translate("Translate me")
    second = provider.translate("Translate me")

    assert first.text == "翻譯結果"
    assert first.from_cache is False
    assert second.text == "翻譯結果"
    assert second.from_cache is True
    assert len(payloads) == 1
    assert payloads[0]["messages"][0]["content"] == [
        {"type": "text", "text": payloads[0]["messages"][0]["content"][0]["text"]}
    ]
    assert payloads[0]["response_format"] == {"type": "text"}


def test_clear_cache_forces_a_new_text_request_without_changing_runtime():
    provider = make_provider()
    payloads = []

    def fake_request(payload):
        payloads.append(payload)
        return "翻譯結果"

    provider._request_chat_completion = fake_request
    runtime_before = (provider.base_url, provider.model_name, provider.available())

    first = provider.translate("Translate me")
    cached = provider.translate("Translate me")
    provider.clear_cache()
    after_clear = provider.translate("Translate me")

    assert first.from_cache is False
    assert cached.from_cache is True
    assert after_clear.from_cache is False
    assert len(payloads) == 2
    assert (provider.base_url, provider.model_name, provider.available()) == runtime_before


def test_transcribe_screenshot_raises_on_empty_response():
    provider = make_provider()

    with pytest.raises(ValueError, match="empty_local_multimodal_ocr_response"):
        provider._parse_transcription_response("")


def test_embedded_provider_is_available_only_after_runtime_ready():
    provider = LocalMultimodalProvider(
        model_name="gemma-3-4b-it",
        enabled=True,
    )

    provider.update_runtime(
        "http://127.0.0.1:43123/v1",
        "gemma-3-4b-it",
        ready=False,
    )
    assert provider.available() is False

    provider.update_runtime(
        "http://127.0.0.1:43123/v1",
        "gemma-3-4b-it",
        ready=True,
    )
    assert provider.available() is True

    provider.update_runtime("", "", ready=False)
    assert provider.available() is False

def test_transcribe_screenshot_marks_ocr_hint_as_untrusted():
    provider = make_provider()
    captured = {}

    def fake_request(payload):
        captured["prompt"] = payload["messages"][0]["content"][0]["text"]
        return "修正結果"

    provider._request_chat_completion = fake_request
    result = provider.transcribe_screenshot(
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
        source_text_hint="可能有誤",
        ocr_prompt="STRICT OCR",
    )

    assert result.text == "修正結果"
    assert "may contain recognition errors" in captured["prompt"]
    assert "return one final transcription" in captured["prompt"]
    assert captured["prompt"].endswith("OCR hint:\n可能有誤")


def test_transcribe_screenshot_accepts_ocr_prompt_override() -> None:
    provider = make_provider()
    captured = {}

    def fake_request(payload):
        captured["prompt"] = payload["messages"][0]["content"][0]["text"]
        return "Wine Club"

    provider._request_chat_completion = fake_request
    result = provider.transcribe_screenshot(
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
        ocr_prompt="STRICT OCR",
    )

    assert result.text == "Wine Club"
    assert captured["prompt"] == "STRICT OCR"


def test_transcribe_screenshot_default_prompt_is_strict_ocr():
    provider = make_provider()
    captured = {}

    def fake_request(payload):
        captured["prompt"] = payload["messages"][0]["content"][0]["text"]
        return "OCR result"

    provider._request_chat_completion = fake_request
    provider.transcribe_screenshot(
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}]
    )

    assert "Do not translate, summarize, correct, complete, or infer text." in captured["prompt"]
    assert "Preserve the original line order, line breaks, punctuation" in captured["prompt"]

def test_transcribe_screenshot_uses_ocr_sampling_profile():
    provider = make_provider()
    payloads = []

    def fake_request(payload):
        payloads.append(payload)
        return "OCR result"

    provider._request_chat_completion = fake_request
    provider.transcribe_screenshot(
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}]
    )

    assert payloads[0]["temperature"] == pytest.approx(0.1)
    assert payloads[0]["repeat_penalty"] == pytest.approx(1.15)


def test_translate_keeps_translation_sampling_profile():
    provider = make_provider()
    payloads = []

    def fake_request(payload):
        payloads.append(payload)
        return "翻譯結果"

    provider._request_chat_completion = fake_request
    provider.translate("hello")

    assert payloads[0]["temperature"] == pytest.approx(0.2)
    assert payloads[0]["repeat_penalty"] == pytest.approx(1.15)


def test_transcribe_screenshot_rejects_degenerate_repetition():
    provider = make_provider()
    repeated = "\n".join(["光が"] * 12)

    with pytest.raises(ValueError, match="degenerate_local_multimodal_ocr_response"):
        provider._parse_transcription_response(repeated)
    with pytest.raises(ValueError, match="degenerate_local_multimodal_ocr_response"):
        provider._parse_transcription_response("光が" * 12)


def test_request_chat_completion_rejects_truncated_response(monkeypatch):
    provider = make_provider()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": "incomplete"},
                        }
                    ]
                }
            ).encode("utf-8")

    monkeypatch.setattr(
        providers_module.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )

    with pytest.raises(ValueError, match="truncated_local_multimodal_response"):
        provider._request_chat_completion({"model": "test"})


def test_request_chat_completion_keeps_only_safe_numeric_runtime_metrics(monkeypatch):
    provider = make_provider()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": "{}"},
                }],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 9,
                    "secret": "must-not-survive",
                },
                "timings": {
                    "prompt_ms": 321.5,
                    "predicted_ms": 456.25,
                    "raw_text": "must-not-survive",
                },
            }).encode("utf-8")

    monkeypatch.setattr(
        providers_module.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )

    assert provider._request_chat_completion({"model": "test"}) == "{}"
    assert provider.get_last_request_metrics() == {
        "prompt_tokens": 120,
        "completion_tokens": 9,
        "prompt_ms": 321.5,
        "predicted_ms": 456.25,
    }


def test_interpret_regions_scales_output_budget_with_hint_count():
    provider = make_provider()
    payloads = []

    def fake_request(payload, *, cancel_predicate=None):
        payloads.append(payload)
        prompt = payload["messages"][0]["content"][0]["text"]
        count = 8 if "id=7" in prompt else 1
        return json.dumps({
            "regions": [
                {"id": index, "source_text": "source", "translation": "翻譯", "confidence": 0.9}
                for index in range(count)
            ]
        }, ensure_ascii=False)

    provider._request_chat_completion = fake_request
    one_hint = [{"id": 0, "x": 0, "y": 0, "w": 100, "h": 100, "text": "hint"}]
    many_hints = [
        {"id": index, "x": index, "y": index, "w": 100, "h": 100, "text": f"id={index}"}
        for index in range(8)
    ]

    provider.interpret_regions(
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
        one_hint,
        image_width=800,
        image_height=600,
    )
    provider.interpret_regions(
        [{"inline_data": {"mime_type": "image/png", "data": "abc"}}],
        many_hints,
        image_width=800,
        image_height=600,
    )

    assert [payload["max_tokens"] for payload in payloads] == [384, 1408]


def test_local_multimodal_operations_bound_output_tokens():
    provider = make_provider()
    payloads = []

    def fake_request(payload):
        payloads.append(payload)
        response_type = payload["response_format"]["type"]
        if response_type == "json_object":
            prompt = payload["messages"][0]["content"][0]["text"]
            count = 4 if "段" in prompt else 1
            segments = [{"index": index, "translation": "翻譯"} for index in range(count)]
            return json.dumps({"segments": segments}, ensure_ascii=False)
        return "完整翻譯結果"

    provider._request_chat_completion = fake_request
    image_parts = [{"inline_data": {"mime_type": "image/png", "data": "abc"}}]

    provider.translate("bounded text")
    provider.translate_multimodal(["原文"], image_parts)
    provider.translate_multimodal(["段"] * 16, image_parts)
    provider.transcribe_screenshot(image_parts)
    provider.translate_screenshot(image_parts, source_text_hint="原文")

    assert [payload["max_tokens"] for payload in payloads] == [512, 1024, 1024, 1024, 1024, 1024, 384, 1024]
