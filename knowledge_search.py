"""Small, dependency-light search and reader providers for knowledge research."""
from __future__ import annotations
from dataclasses import dataclass
import importlib
import ipaddress
import socket
from typing import Any, Callable, Iterable, Mapping, Protocol, runtime_checkable
from urllib import error as urlerror
from urllib import request
from urllib.parse import SplitResult, urlsplit, urlunsplit

MAX_SEARCH_RESULTS = 50

@dataclass(frozen=True, slots=True)
class SearchResult:
    """A normalized web-search result."""
    title: str
    url: str
    snippet: str = ""

class ResearchProviderError(RuntimeError):
    """Raised when a research provider cannot safely complete its work."""

@runtime_checkable
class SearchProvider(Protocol):
    """Interface implemented by web search providers."""
    def search(self, query: str) -> tuple[SearchResult, ...]:
        """Return normalized results for *query*."""

def normalize_http_url(value: object) -> str | None:
    """Return a canonical HTTP(S) URL, or ``None`` when it is not usable."""
    if not isinstance(value, str): return None
    raw = value.strip()
    if not raw: return None
    try:
        parsed = urlsplit(raw); scheme = parsed.scheme.lower(); host = parsed.hostname; port = parsed.port
    except ValueError: return None
    if scheme not in {"http", "https"} or not host or parsed.username or parsed.password: return None
    host = host.rstrip(".").lower()
    if not host: return None
    display_host = f"[{host}]" if ":" in host else host
    netloc = f"{display_host}:{port}" if port is not None and port != (80 if scheme == "http" else 443) else display_host
    return urlunsplit(SplitResult(scheme, netloc, parsed.path or "/", parsed.query, ""))

class DDGSSearchProvider:
    """DuckDuckGo search provider with a lazy optional ``ddgs`` dependency."""
    def __init__(self, *, timeout: float = 10.0, max_results: int = 10, region: str = "us-en", safesearch: str = "moderate", backend: str = "auto") -> None:
        if timeout <= 0: raise ValueError("timeout must be positive")
        if not 0 < max_results <= MAX_SEARCH_RESULTS: raise ValueError(f"max_results must be between 1 and {MAX_SEARCH_RESULTS}")
        self.timeout, self.max_results = timeout, max_results
        self.region, self.safesearch, self.backend = region, safesearch, backend
    def search(self, query: str) -> tuple[SearchResult, ...]:
        if not isinstance(query, str) or not query.strip(): raise ResearchProviderError("Search query must not be empty.")
        try:
            client = importlib.import_module("ddgs").DDGS(timeout=self.timeout)
            raw_results = client.text(query.strip(), region=self.region, safesearch=self.safesearch, backend=self.backend, max_results=self.max_results)
            return self._normalize_results(raw_results)
        except ImportError as exc: raise ResearchProviderError("DDGS search dependency is unavailable.") from exc
        except ResearchProviderError: raise
        except Exception as exc: raise ResearchProviderError("DDGS search failed.") from exc
    def _normalize_results(self, raw_results: Iterable[Mapping[str, Any]] | None) -> tuple[SearchResult, ...]:
        if raw_results is None: return ()
        normalized: list[SearchResult] = []; seen_urls: set[str] = set()
        for item in raw_results:
            if not isinstance(item, Mapping): continue
            url = normalize_http_url(item.get("href") or item.get("url"))
            if url is None or url in seen_urls: continue
            seen_urls.add(url)
            normalized.append(SearchResult(_clean_text(item.get("title")), url, _clean_text(item.get("body") or item.get("snippet"))))
            if len(normalized) == self.max_results: break
        return tuple(normalized)

class JinaReaderProvider:
    """Fetch a public HTTP(S) page through Jina Reader with size limits."""
    def __init__(self, *, timeout: float = 15.0, max_bytes: int = 1_000_000, opener: Callable[..., Any] | None = None, dns_resolver: Callable[..., Any] | None = None) -> None:
        if timeout <= 0: raise ValueError("timeout must be positive")
        if max_bytes <= 0: raise ValueError("max_bytes must be positive")
        self.timeout, self.max_bytes = timeout, max_bytes
        self._opener, self._dns_resolver = opener or request.urlopen, dns_resolver or socket.getaddrinfo
    def read(self, url: str) -> str:
        """Read a validated public URL through ``https://r.jina.ai/``."""
        target_url = self._validate_target(url)
        reader_request = request.Request(f"https://r.jina.ai/{target_url}", headers={"Accept": "text/plain"})
        try:
            with self._opener(reader_request, timeout=self.timeout) as response:
                if getattr(response, "status", None) is not None and response.status >= 400: raise ResearchProviderError("Jina Reader returned an error response.")
                content = response.read(self.max_bytes + 1)
        except ResearchProviderError: raise
        except (TimeoutError, socket.timeout) as exc: raise ResearchProviderError("Jina Reader request timed out.") from exc
        except urlerror.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)): raise ResearchProviderError("Jina Reader request timed out.") from exc
            raise ResearchProviderError("Jina Reader request failed.") from exc
        except Exception as exc: raise ResearchProviderError("Jina Reader request failed.") from exc
        if not isinstance(content, bytes): raise ResearchProviderError("Jina Reader returned an invalid response body.")
        if len(content) > self.max_bytes: raise ResearchProviderError("Jina Reader response exceeds the configured size limit.")
        return content.decode("utf-8", errors="replace")
    def _validate_target(self, url: str) -> str:
        normalized = normalize_http_url(url)
        if normalized is None: raise ResearchProviderError("Reader URL must be a valid HTTP(S) URL without user info.")
        parsed = urlsplit(normalized)
        try: port = parsed.port
        except ValueError as exc: raise ResearchProviderError("Reader URL contains an invalid port.") from exc
        if port is not None and port not in {80, 443}: raise ResearchProviderError("Reader URL port must be 80 or 443.")
        host = parsed.hostname
        if host is None or host == "localhost" or host.endswith(".local"): raise ResearchProviderError("Reader URL host is not publicly routable.")
        try:
            literal_ip = ipaddress.ip_address(host)
        except ValueError:
            literal_ip = None
        if literal_ip is not None and not literal_ip.is_global:
            raise ResearchProviderError("Reader URL host is not publicly routable.")
        self._require_public_dns(host, port or (443 if parsed.scheme == "https" else 80))
        return normalized
    def _require_public_dns(self, host: str, port: int) -> None:
        try: addresses = self._dns_resolver(host, port, type=socket.SOCK_STREAM)
        except (OSError, ValueError) as exc: raise ResearchProviderError("Reader URL host could not be resolved safely.") from exc
        if not addresses: raise ResearchProviderError("Reader URL host did not resolve to a public address.")
        for address in addresses:
            try: ip = ipaddress.ip_address(address[4][0])
            except (IndexError, TypeError, ValueError) as exc: raise ResearchProviderError("Reader URL DNS response was invalid.") from exc
            if not ip.is_global: raise ResearchProviderError("Reader URL host resolved to a non-public address.")

def _clean_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""