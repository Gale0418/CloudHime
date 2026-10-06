from __future__ import annotations

import math
import json

import pytest
import requests
from deep_translator.exceptions import RequestError, TooManyRequests, TranslationNotFound

import google_translation_transport as transport


class FakeResponse:
    def __init__(self, status_code=200, chunks=(), encoding="utf-8", headers=None):
        self.status_code = status_code
        self.chunks = chunks
        self.encoding = encoding
        self.headers = headers or {}
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.closed = True

    def iter_content(self, chunk_size):
        assert chunk_size == transport.READ_CHUNK_BYTES
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


def json_response(*texts):
    return json.dumps(
        [[[text, "source"] for text in texts]], ensure_ascii=False
    ).encode("utf-8")


@pytest.fixture(autouse=True)
def reset_global_cooldown():
    with transport._cooldown_lock:
        transport._cooldown_until = 0.0
    yield
    with transport._cooldown_lock:
        transport._cooldown_until = 0.0


def test_success_uses_bounded_stream_and_closes_response(monkeypatch):
    response = FakeResponse(chunks=[json_response("你好")])
    calls = []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr(transport.requests, "get", get)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    assert translator.translate("hello") == "你好"
    assert calls[0][0][0] == transport.TRANSLATE_API_URL
    assert calls[0][1]["params"] == {
        "client": "gtx",
        "sl": "en",
        "tl": "zh-TW",
        "dt": "t",
        "q": "hello",
    }
    assert calls[0][1]["timeout"] == (5, 20)
    assert calls[0][1]["stream"] is True
    assert response.closed


def test_429_closes_response_before_raising(monkeypatch):
    response = FakeResponse(status_code=429)
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(TooManyRequests):
        translator.translate("hello")
    assert response.closed


def test_non_200_closes_response_before_raising(monkeypatch):
    response = FakeResponse(status_code=503)
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(RequestError):
        translator.translate("hello")
    assert response.closed


def test_read_timeout_closes_response(monkeypatch):
    response = FakeResponse(chunks=[requests.exceptions.ReadTimeout("slow read")])
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(requests.exceptions.ReadTimeout):
        translator.translate("hello")
    assert response.closed


def test_invalid_json_raises_and_closes(monkeypatch):
    response = FakeResponse(chunks=[b"not-json"])
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(RequestError, match="invalid JSON"):
        translator.translate("hello")
    assert response.closed


def test_response_size_limit_closes(monkeypatch):
    response = FakeResponse(chunks=[b"x" * (transport.MAX_RESPONSE_BYTES + 1)])
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(transport.GoogleTranslationResponseLimitError):
        translator.translate("hello")
    assert response.closed


def test_elapsed_budget_closes_empty_slow_response(monkeypatch):
    response = FakeResponse(chunks=[])
    times = iter([0.0, 0.0, transport.MAX_ELAPSED_SECONDS + 0.1])
    monkeypatch.setattr(transport.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(RequestError, match="elapsed-time budget"):
        translator.translate("hello")
    assert response.closed


def test_429_cooldown_is_shared_by_instances_and_expires(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    responses = [FakeResponse(status_code=429, headers={"Retry-After": "120"})]
    calls = []

    def get(*_args, **_kwargs):
        calls.append(True)
        return responses.pop(0)

    monkeypatch.setattr(transport.requests, "get", get)
    first = transport.GoogleTranslator(source="en", target="zh-TW")
    second = transport.GoogleTranslator(source="en", target="ja")

    with pytest.raises(TooManyRequests):
        first.translate("hello")
    with pytest.raises(TooManyRequests):
        second.translate("hello")
    assert len(calls) == 1

    now[0] = 220.0
    monkeypatch.setattr(
        transport.requests,
        "get",
        lambda *_a, **_kw: FakeResponse(chunks=[json_response("你好")]),
    )
    assert second.translate("hello") == "你好"


@pytest.mark.parametrize(
    ("retry_after", "expected_delay"),
    [
        ("15", 15.0),
        ("Mon, 05 Oct 2026 00:00:30 GMT", 30.0),
        ("0", 0.0),
        ("Sun, 04 Oct 2026 00:00:00 GMT", 0.0),
        ("not a date", transport.DEFAULT_429_COOLDOWN_SECONDS),
        ("١٥", transport.DEFAULT_429_COOLDOWN_SECONDS),
    ],
)
def test_retry_after_parsing_and_invalid_fallback(monkeypatch, retry_after, expected_delay):
    now = [100.0]
    wall = 1791158400.0  # 2026-10-05 00:00:00 UTC
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(transport.time, "time", lambda: wall)
    response = FakeResponse(status_code=429, headers={"Retry-After": retry_after})
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(TooManyRequests):
        translator.translate("hello")
    assert response.closed
    assert transport._cooldown_until == pytest.approx(
        100.0 + max(transport.DEFAULT_429_COOLDOWN_SECONDS, expected_delay)
    )


def test_429_without_retry_after_uses_default_cooldown(monkeypatch):
    monkeypatch.setattr(transport.time, "monotonic", lambda: 100.0)
    response = FakeResponse(status_code=429)
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(TooManyRequests):
        translator.translate("hello")
    assert transport._cooldown_until == 100.0 + transport.DEFAULT_429_COOLDOWN_SECONDS


def test_cooldown_does_not_block_same_source_shortcut(monkeypatch):
    with transport._cooldown_lock:
        transport._cooldown_until = 200.0
    monkeypatch.setattr(transport.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(
        transport.requests,
        "get",
        lambda *_a, **_kw: pytest.fail("same-source translation must not perform HTTP"),
    )
    translator = transport.GoogleTranslator(source="en", target="en")

    assert translator.translate("hello") == "hello"


def test_start_cooldown_never_shortens_existing_deadline():
    transport._start_cooldown(120.0, 100.0)
    transport._start_cooldown(60.0, 110.0)

    assert transport._cooldown_until == 220.0


def test_503_does_not_start_cooldown(monkeypatch):
    response = FakeResponse(status_code=503)
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(RequestError):
        translator.translate("hello")
    assert response.closed
    assert transport._cooldown_until == 0.0


def test_unrepresentable_retry_after_is_not_shortened():
    assert math.isinf(transport._retry_after_seconds("9" * 5000, 0.0))


def test_same_source_short_circuits_http(monkeypatch):
    def unexpected_get(*_args, **_kwargs):
        pytest.fail("same-source translation must not perform HTTP")

    monkeypatch.setattr(transport.requests, "get", unexpected_get)
    translator = transport.GoogleTranslator(source="en", target="en")

    assert translator.translate("  hello  ") == "hello"


def test_empty_input_short_circuits_http(monkeypatch):
    monkeypatch.setattr(
        transport.requests,
        "get",
        lambda *_a, **_kw: pytest.fail("empty translation must not perform HTTP"),
    )
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    assert translator.translate("  ") == ""


def test_multipart_translation_preserves_newlines(monkeypatch):
    response = FakeResponse(chunks=[json_response("第一段\n", " 第二段")])
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    assert translator.translate("hello") == "第一段\n 第二段"
    assert response.closed


def test_unchanged_punctuation_returns_text_without_retry(monkeypatch):
    response = FakeResponse(chunks=[json_response("...")])
    calls = []

    def get(*_args, **_kwargs):
        calls.append(True)
        return response

    monkeypatch.setattr(transport.requests, "get", get)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")
    assert translator.translate(" ... ") == "..."
    assert calls == [True]
    assert response.closed


@pytest.mark.parametrize(
    ("body", "error"),
    [
        (b"{}", RequestError),
        (b"[]", RequestError),
        (b"[{}]", RequestError),
        (b"[[]]", TranslationNotFound),
        (b"[[null]]", RequestError),
        (b"[[[]]]", RequestError),
        (b"[[[null]]]", RequestError),
        (b'[[["ok"], [null]]]', RequestError),
        (b'[[[""]]]', TranslationNotFound),
        (b'[[["  \\n  "]]]', TranslationNotFound),
    ],
)
def test_invalid_json_structure_or_empty_translation_raises(monkeypatch, body, error):
    response = FakeResponse(chunks=[body])
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(error):
        translator.translate("hello")
    assert response.closed
