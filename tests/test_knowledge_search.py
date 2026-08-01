from __future__ import annotations
import socket
import sys
import types
from urllib import error as urlerror
import pytest
from knowledge_search import DDGSSearchProvider, JinaReaderProvider, ResearchProviderError, SearchProvider

class FakeResponse:
    def __init__(self, body: bytes, status: int = 200): self.body, self.status, self.read_sizes = body, status, []
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return self.body if size < 0 else self.body[:size]
def public_dns(host: str, port: int, *, type: int):
    assert type == socket.SOCK_STREAM
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]

def test_ddgs_is_lazy_and_missing_dependency_becomes_provider_error(monkeypatch):
    provider = DDGSSearchProvider(); assert isinstance(provider, SearchProvider)
    monkeypatch.delitem(sys.modules, "ddgs", raising=False)
    monkeypatch.setattr("knowledge_search.importlib.import_module", lambda _name: (_ for _ in ()).throw(ImportError("missing")))
    with pytest.raises(ResearchProviderError, match="dependency"): provider.search("cloud hime")
def test_ddgs_normalizes_deduplicates_filters_and_limits_results(monkeypatch):
    init_calls = []
    calls = []
    class FakeDDGS:
        def __init__(self, **kwargs):
            init_calls.append(kwargs)

        def text(self, query, **kwargs):
            calls.append((query, kwargs)); return [{"title":" One ","href":"HTTPS://Example.COM:443/a#part","body":" Text "},{"title":"Duplicate","href":"https://example.com/a"},{"title":"Unsafe","href":"file:///secret"},{"title":"Two","url":"http://example.org"},{"title":"Three","href":"https://example.net"}]
    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=FakeDDGS))
    results = DDGSSearchProvider(timeout=3, max_results=2, region="tw-tzh", safesearch="on", backend="api").search("  test  ")
    assert [(x.title,x.url,x.snippet) for x in results] == [("One","https://example.com/a","Text"),("Two","http://example.org/","")]
    assert init_calls == [{"timeout": 3}]
    assert calls == [("test", {"region":"tw-tzh","safesearch":"on","backend":"api","max_results":2})]
def test_ddgs_search_errors_are_wrapped(monkeypatch):
    class BrokenDDGS:
        def text(self, *_args, **_kwargs): raise RuntimeError("network")
    monkeypatch.setitem(sys.modules, "ddgs", types.SimpleNamespace(DDGS=BrokenDDGS))
    with pytest.raises(ResearchProviderError, match="DDGS search failed"): DDGSSearchProvider().search("test")
@pytest.mark.parametrize("url", ["http://localhost/page", "https://service.local/page", "ftp://example.com", "https://user@example.com", "http://127.0.0.1", "https://example.com:8080"])
def test_jina_rejects_unsafe_targets_before_opening(url):
    opened = False
    def opener(*_args, **_kwargs):
        nonlocal opened; opened = True; raise AssertionError("must not open")
    with pytest.raises(ResearchProviderError): JinaReaderProvider(opener=opener, dns_resolver=public_dns).read(url)
    assert opened is False
def test_jina_rejects_any_non_public_dns_result():
    def mixed_dns(_host, port, *, type): return [(socket.AF_INET,socket.SOCK_STREAM,6,"",("8.8.8.8",port)),(socket.AF_INET,socket.SOCK_STREAM,6,"",("10.0.0.1",port))]
    with pytest.raises(ResearchProviderError, match="non-public"): JinaReaderProvider(dns_resolver=mixed_dns).read("https://example.com/article")
def test_jina_composes_reader_url_and_respects_byte_limit():
    response, seen = FakeResponse(b"hello"), []
    def opener(req, *, timeout): seen.append((req.full_url, timeout)); return response
    text = JinaReaderProvider(timeout=2.5,max_bytes=5,opener=opener,dns_resolver=public_dns).read("HTTPS://Example.COM:443/a#fragment")
    assert text == "hello"; assert seen == [("https://r.jina.ai/https://example.com/a",2.5)]; assert response.read_sizes == [6]
def test_jina_rejects_oversized_response():
    with pytest.raises(ResearchProviderError, match="size limit"): JinaReaderProvider(max_bytes=3,opener=lambda *_args,**_kwargs: FakeResponse(b"abcd"),dns_resolver=public_dns).read("https://example.com")
@pytest.mark.parametrize("failure,message", [(TimeoutError(),"timed out"),(urlerror.URLError("offline"),"request failed")])
def test_jina_wraps_timeout_and_transport_errors(failure, message):
    def opener(*_args, **_kwargs): raise failure
    with pytest.raises(ResearchProviderError, match=message): JinaReaderProvider(opener=opener,dns_resolver=public_dns).read("https://example.com")