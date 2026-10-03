from __future__ import annotations

from collections import deque

import pytest
import requests
from deep_translator.exceptions import RequestError, TooManyRequests, TranslationNotFound

import google_translation_transport as transport


class FakeResponse:
    def __init__(self, status_code=200, chunks=(), encoding="utf-8"):
        self.status_code = status_code
        self.chunks = chunks
        self.encoding = encoding
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


def html(text, selector="t0"):
    return f'<div class="{selector}">{text}</div>'.encode("utf-8")


def test_success_uses_bounded_stream_and_closes_response(monkeypatch):
    response = FakeResponse(chunks=[html("你好")])
    calls = []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr(transport.requests, "get", get)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    assert translator.translate("hello") == "你好"
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


def test_missing_both_supported_selectors_raises_and_closes(monkeypatch):
    response = FakeResponse(chunks=[b"<html><p>unrecognized response</p></html>"])
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(TranslationNotFound):
        translator.translate("hello")
    assert response.closed


def test_response_size_limit_closes(monkeypatch):
    response = FakeResponse(chunks=[b"x" * (transport.MAX_HTML_BYTES + 1)])
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(transport.GoogleTranslationResponseLimitError):
        translator.translate("hello")
    assert response.closed


def test_elapsed_budget_closes_empty_slow_response(monkeypatch):
    response = FakeResponse(chunks=[])
    times = iter([0.0, transport.MAX_ELAPSED_SECONDS + 0.1])
    monkeypatch.setattr(transport.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(transport.requests, "get", lambda *_a, **_kw: response)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")

    with pytest.raises(RequestError, match="elapsed-time budget"):
        translator.translate("hello")
    assert response.closed


def test_same_source_short_circuits_http(monkeypatch):
    def unexpected_get(*_args, **_kwargs):
        pytest.fail("same-source translation must not perform HTTP")

    monkeypatch.setattr(transport.requests, "get", unexpected_get)
    translator = transport.GoogleTranslator(source="en", target="en")

    assert translator.translate("  hello  ") == "hello"


def test_hl_retry_removes_hl_and_preserves_result(monkeypatch):
    responses = deque(
        [
            FakeResponse(chunks=[html("hello")]),
            FakeResponse(chunks=[html("你好", selector="result-container")]),
        ]
    )
    request_params = []

    def get(_url, **kwargs):
        request_params.append(dict(kwargs["params"]))
        return responses.popleft()

    monkeypatch.setattr(transport.requests, "get", get)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")
    translator._url_params["hl"] = "en"

    assert translator.translate("hello") == "你好"
    assert "hl" in request_params[0]
    assert "hl" not in request_params[1]


def test_unchanged_punctuation_returns_text_without_retry(monkeypatch):
    response = FakeResponse(chunks=[html("...")])
    calls = []

    def get(*_args, **_kwargs):
        calls.append(True)
        return response

    monkeypatch.setattr(transport.requests, "get", get)
    translator = transport.GoogleTranslator(source="en", target="zh-TW")
    assert translator.translate(" ... ") == "..."
    assert calls == [True]
    assert response.closed
