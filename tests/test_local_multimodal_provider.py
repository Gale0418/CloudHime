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


def test_transcribe_screenshot_raises_on_empty_response():
    provider = make_provider()

    with pytest.raises(ValueError, match="empty_local_multimodal_ocr_response"):
        provider._parse_transcription_response("")
