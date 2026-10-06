from urllib import error

import pytest

import openai_connection_check as check_module
from openai_connection_check import (
    MAX_RESPONSE_BYTES,
    LunaConnectionResult,
    probe_luna_connection,
)


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status
        self.read_sizes = []
        self.closed = False

    def getcode(self):
        return self.status

    def read(self, size=-1):
        self.read_sizes.append(size)
        return self.body[:size]

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def open(self, req, timeout):
        self.calls.append((req, timeout))
        if self.exc is not None:
            raise self.exc
        return self.response


def test_probe_sends_get_bearer_header_and_checks_model_id():
    opener = FakeOpener(FakeResponse(b'{"object":"model","id":"gpt-6-luna"}'))

    result = probe_luna_connection("secret-key", timeout_seconds=3.5, opener=opener)

    req, timeout = opener.calls[0]
    assert result == LunaConnectionResult("verified")
    assert req.full_url == "https://api.openai.com/v1/models/gpt-6-luna"
    assert req.get_method() == "GET"
    assert req.get_header("Authorization") == "Bearer secret-key"
    assert timeout == 3.5


@pytest.mark.parametrize(
    ("code", "status"),
    [(401, "invalid_key"), (403, "forbidden"), (404, "model_unavailable"), (429, "rate_limited"), (503, "server_error"), (302, "invalid_response")],
)
def test_http_errors_are_mapped_without_reading_error_body(code, status):
    exc = error.HTTPError("https://api.openai.com/", code, "reason", {}, None)
    opener = FakeOpener(exc=exc)

    assert probe_luna_connection("secret", opener=opener) == LunaConnectionResult(status)


@pytest.mark.parametrize(
    "body",
    [b"not-json", b"\xff", b"[]", b'{"object":"model","id":"other-model"}', b'{"object":"list","id":"gpt-6-luna"}'],
)
def test_invalid_body_or_model_is_rejected(body):
    result = probe_luna_connection("secret", opener=FakeOpener(FakeResponse(body)))

    assert result == LunaConnectionResult("invalid_response")


def test_body_is_read_with_one_byte_over_limit_and_oversized_body_rejected():
    response = FakeResponse(b"x" * (MAX_RESPONSE_BYTES + 1))

    result = probe_luna_connection("secret", opener=FakeOpener(response))

    assert result == LunaConnectionResult("invalid_response")
    assert response.read_sizes == [MAX_RESPONSE_BYTES + 1]
    assert response.closed is True


def test_no_key_and_control_characters_do_not_dispatch_request():
    opener = FakeOpener(FakeResponse(b'{"object":"model","id":"gpt-6-luna"}'))

    assert probe_luna_connection("  ", opener=opener) == LunaConnectionResult("no_key")
    assert probe_luna_connection("bad\r\nkey", opener=opener) == LunaConnectionResult("invalid_key")
    assert opener.calls == []


def test_timeout_and_network_errors_are_classified_without_exposing_exception():
    timeout = probe_luna_connection("secret", opener=FakeOpener(exc=TimeoutError("secret timeout details")))
    network = probe_luna_connection("secret", opener=FakeOpener(exc=error.URLError("secret network details")))

    assert timeout == LunaConnectionResult("timeout")
    assert network == LunaConnectionResult("network_error")
    assert "secret" not in repr(timeout)
    assert "secret" not in repr(network)


def test_default_opener_refuses_redirects_without_following_them(monkeypatch):
    created = {}

    class Opener:
        def open(self, req, timeout):
            redirect = created["handler"]
            assert redirect.redirect_request(req, None, 302, "Found", {}, "https://evil.example/") is None
            created["redirect_called"] = True
            raise error.HTTPError(req.full_url, 302, "Found", {}, None)

    def build_opener(handler):
        created["handler"] = handler
        return Opener()

    monkeypatch.setattr("openai_connection_check.request.build_opener", build_opener)
    result = probe_luna_connection("secret")

    assert isinstance(created["handler"], check_module._NoRedirectHandler)
    assert created.get("redirect_called") is True
    assert result == LunaConnectionResult("invalid_response")
