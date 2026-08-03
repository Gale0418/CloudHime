"""Non-activating research draft contract for Knowledge Pack building."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Callable, Protocol

from knowledge_search import ResearchProviderError, SearchProvider, SearchResult, normalize_http_url

RESEARCH_DRAFT_SCHEMA_VERSION = 1
RESEARCH_DRAFT_STATUS = "draft"
MAX_DRAFT_SOURCES = 20
MAX_TITLE_LENGTH = 240
MAX_QUERY_LENGTH = 240
MAX_METADATA_TEXT_LENGTH = 500
MAX_CONTENT_LENGTH = 32_000
_SOURCE_ID_LENGTH = 16
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ResearchDraftError(RuntimeError):
    """Raised when a research draft cannot be built safely."""


class ResearchDraftValidationError(ValueError):
    """Raised when untrusted draft data does not satisfy the local contract."""


class ReaderProvider(Protocol):
    def read(self, url: str) -> str:
        """Read a bounded public source."""


@dataclass(frozen=True, slots=True)
class ResearchDraftSource:
    source_id: str
    url: str
    title: str
    snippet: str
    status: str
    fetched_at: str
    content: str = ""
    content_sha256: str = ""
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "status": self.status,
            "fetched_at": self.fetched_at,
            "content": self.content,
            "content_sha256": self.content_sha256,
            "error": self.error,
        }


def _clean_text(value: Any, field: str, maximum: int, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ResearchDraftValidationError(f"{field} must be text")
    normalized = " ".join(value.replace("\x00", "").split())
    if required and not normalized:
        raise ResearchDraftValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ResearchDraftValidationError(f"{field} is too long")
    return normalized


def _validate_timestamp(value: Any, field: str) -> str:
    normalized = _clean_text(value, field, 80, required=True)
    try:
        parsed = datetime.fromisoformat(normalized)
    except (TypeError, ValueError) as exc:
        raise ResearchDraftValidationError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ResearchDraftValidationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _source_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:_SOURCE_ID_LENGTH]


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _timestamp(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _failed_source(
    result: SearchResult,
    url: str,
    fetched_at: str,
    status: str,
    error: str,
) -> ResearchDraftSource:
    def safe_metadata(value: Any) -> str:
        try:
            return _clean_text(value, "source metadata", MAX_METADATA_TEXT_LENGTH)
        except Exception:
            return ""

    return ResearchDraftSource(
        source_id=_source_id(url),
        url=url,
        title=safe_metadata(getattr(result, "title", "")),
        snippet=safe_metadata(getattr(result, "snippet", "")),
        status=status,
        fetched_at=fetched_at,
        error=error,
    )


def build_research_draft(
    title: str,
    *,
    search_provider: SearchProvider,
    reader_provider: ReaderProvider,
    query: str | None = None,
    max_sources: int = 8,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect bounded source evidence without creating or activating a pack.

    Search failure is a research-level error. Individual source failures remain in
    the draft so the caller can show an incomplete result without hiding provenance.
    """
    normalized_title = _clean_text(title, "title", MAX_TITLE_LENGTH, required=True)
    normalized_query = _clean_text(query or normalized_title, "query", MAX_QUERY_LENGTH, required=True)
    if isinstance(max_sources, bool) or not isinstance(max_sources, int) or not 0 < max_sources <= MAX_DRAFT_SOURCES:
        raise ValueError(f"max_sources must be between 1 and {MAX_DRAFT_SOURCES}")

    try:
        results = search_provider.search(normalized_query)
    except ResearchProviderError as exc:
        raise ResearchDraftError("Knowledge research search failed") from exc
    except Exception as exc:
        raise ResearchDraftError("Knowledge research search failed") from exc

    fetched_at = _timestamp(now)
    sources: list[ResearchDraftSource] = []
    seen_urls: set[str] = set()
    for result in results or ():
        if not isinstance(result, SearchResult):
            continue
        url = normalize_http_url(result.url)
        if url is None or url in seen_urls:
            continue
        seen_urls.add(url)
        if len(sources) >= max_sources:
            break
        try:
            content = reader_provider.read(url)
            if not isinstance(content, str) or not content.strip():
                raise ResearchProviderError("empty reader response")
            normalized_content = content.strip()
            if len(normalized_content) > MAX_CONTENT_LENGTH:
                sources.append(_failed_source(result, url, fetched_at, "rejected", "source_content_too_large"))
                continue
            sources.append(
                ResearchDraftSource(
                    source_id=_source_id(url),
                    url=url,
                    title=_clean_text(result.title, "source title", MAX_METADATA_TEXT_LENGTH),
                    snippet=_clean_text(result.snippet, "source snippet", MAX_METADATA_TEXT_LENGTH),
                    status="read",
                    fetched_at=fetched_at,
                    content=normalized_content,
                    content_sha256=_content_digest(normalized_content),
                )
            )
        except Exception as exc:
            sources.append(
                _failed_source(
                    result,
                    url,
                    fetched_at,
                    "read_failed",
                    f"{type(exc).__name__}",
                )
            )

    draft = {
        "schema_version": RESEARCH_DRAFT_SCHEMA_VERSION,
        "status": RESEARCH_DRAFT_STATUS,
        "title": normalized_title,
        "query": normalized_query,
        "created_at": fetched_at,
        "sources": [source.as_dict() for source in sources],
        "entries": [],
        "review": {
            "owner_confirmed": False,
            "approver": None,
            "approved_at": None,
        },
    }
    return validate_research_draft(draft)


def _validate_source(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResearchDraftValidationError("source must be an object")
    url = normalize_http_url(value.get("url"))
    if url is None:
        raise ResearchDraftValidationError("source url must be a public HTTP(S) URL")
    source_id = value.get("source_id")
    if source_id != _source_id(url):
        raise ResearchDraftValidationError("source_id does not match source url")
    title = _clean_text(value.get("title", ""), "source title", MAX_METADATA_TEXT_LENGTH)
    snippet = _clean_text(value.get("snippet", ""), "source snippet", MAX_METADATA_TEXT_LENGTH)
    status = value.get("status")
    if status not in {"read", "read_failed", "rejected"}:
        raise ResearchDraftValidationError("invalid source status")
    fetched_at = _validate_timestamp(value.get("fetched_at"), "fetched_at")
    content = value.get("content", "")
    if not isinstance(content, str):
        raise ResearchDraftValidationError("source content must be text")
    if len(content) > MAX_CONTENT_LENGTH:
        raise ResearchDraftValidationError("source content is too long")
    content_sha256 = value.get("content_sha256", "")
    if not isinstance(content_sha256, str):
        raise ResearchDraftValidationError("content_sha256 must be text")
    error = _clean_text(value.get("error", ""), "source error", 120)
    if status == "read":
        if not content.strip() or not _SHA256_PATTERN.fullmatch(content_sha256):
            raise ResearchDraftValidationError("read source must include content and sha256")
        if _content_digest(content) != content_sha256:
            raise ResearchDraftValidationError("source content hash mismatch")
        if error:
            raise ResearchDraftValidationError("read source cannot contain an error")
    else:
        if content or content_sha256:
            raise ResearchDraftValidationError("failed source cannot contain content")
        if not error:
            raise ResearchDraftValidationError("failed source must include an error")
    return {
        "source_id": source_id,
        "url": url,
        "title": title,
        "snippet": snippet,
        "status": status,
        "fetched_at": fetched_at,
        "content": content,
        "content_sha256": content_sha256,
        "error": error,
    }


def validate_research_draft(value: Any) -> dict[str, Any]:
    """Validate an untrusted draft; this contract intentionally has no entries."""
    if not isinstance(value, dict):
        raise ResearchDraftValidationError("research draft must be an object")
    if value.get("schema_version") != RESEARCH_DRAFT_SCHEMA_VERSION:
        raise ResearchDraftValidationError("unsupported research draft schema")
    if value.get("status") != RESEARCH_DRAFT_STATUS:
        raise ResearchDraftValidationError("only draft status is accepted")
    title = _clean_text(value.get("title"), "title", MAX_TITLE_LENGTH, required=True)
    query = _clean_text(value.get("query"), "query", MAX_QUERY_LENGTH, required=True)
    created_at = _validate_timestamp(value.get("created_at"), "created_at")
    raw_sources = value.get("sources")
    if not isinstance(raw_sources, list) or len(raw_sources) > MAX_DRAFT_SOURCES:
        raise ResearchDraftValidationError("sources must be a bounded list")
    sources = [_validate_source(item) for item in raw_sources]
    source_ids = [item["source_id"] for item in sources]
    if len(set(source_ids)) != len(source_ids):
        raise ResearchDraftValidationError("duplicate research source")
    if value.get("entries") != []:
        raise ResearchDraftValidationError("research drafts cannot contain active entries")
    review = value.get("review")
    if review != {"owner_confirmed": False, "approver": None, "approved_at": None}:
        raise ResearchDraftValidationError("research draft is not owner-confirmed")
    return {
        "schema_version": RESEARCH_DRAFT_SCHEMA_VERSION,
        "status": RESEARCH_DRAFT_STATUS,
        "title": title,
        "query": query,
        "created_at": created_at,
        "sources": sources,
        "entries": [],
        "review": dict(review),
    }