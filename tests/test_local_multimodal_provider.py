import pytest

from translation_providers import LocalMultimodalProvider


def make_provider():
    return LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="gemma-3n-local",
        target_lang="zh-TW",
        enabled=True,
        timeout_seconds=12,
    )


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
