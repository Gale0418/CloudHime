from datetime import datetime, timezone
import hashlib

import pytest

from knowledge_research_draft import (
    MAX_CONTENT_LENGTH,
    ResearchDraftError,
    ResearchDraftValidationError,
    build_research_draft,
    validate_research_draft,
)
from knowledge_search import ResearchProviderError, SearchResult


class FakeSearch:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return tuple(self.results)


class FakeReader:
    def __init__(self, contents=None, errors=None):
        self.contents = contents or {}
        self.errors = errors or {}
        self.urls = []

    def read(self, url):
        self.urls.append(url)
        if url in self.errors:
            raise self.errors[url]
        return self.contents.get(url, "")


def test_build_research_draft_keeps_evidence_and_never_creates_entries():
    result = SearchResult("Official page", "https://example.com/work", "A short snippet")
    search = FakeSearch([result, result])
    reader = FakeReader({"https://example.com/work": "  source text  "})

    draft = build_research_draft(
        "Princess Synergy",
        search_provider=search,
        reader_provider=reader,
        now=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    source = draft["sources"][0]
    assert search.queries == ["Princess Synergy"]
    assert reader.urls == ["https://example.com/work"]
    assert draft["status"] == "draft"
    assert draft["entries"] == []
    assert draft["review"]["owner_confirmed"] is False
    assert source["status"] == "read"
    assert source["content"] == "source text"
    assert source["content_sha256"] == hashlib.sha256(b"source text").hexdigest()


def test_source_failures_are_retained_without_aborting_other_sources():
    first = "https://example.com/first"
    second = "https://example.com/second"
    search = FakeSearch([
        SearchResult("First", first, "one"),
        SearchResult("Second", second, "two"),
    ])
    reader = FakeReader({first: "usable"}, {second: TimeoutError()})

    draft = build_research_draft("Work", search_provider=search, reader_provider=reader)

    assert [item["status"] for item in draft["sources"]] == ["read", "read_failed"]
    assert draft["sources"][1]["error"] == "TimeoutError"


def test_oversized_source_is_rejected_without_storing_content():
    url = "https://example.com/large"
    search = FakeSearch([SearchResult("Large", url, "")])
    reader = FakeReader({url: "x" * (MAX_CONTENT_LENGTH + 1)})

    draft = build_research_draft("Work", search_provider=search, reader_provider=reader)

    assert draft["sources"][0]["status"] == "rejected"
    assert draft["sources"][0]["content"] == ""
    assert draft["sources"][0]["error"] == "source_content_too_large"


def test_search_failure_is_a_research_error():
    search = FakeSearch(error=ResearchProviderError("offline"))
    with pytest.raises(ResearchDraftError, match="search failed"):
        build_research_draft("Work", search_provider=search, reader_provider=FakeReader())


def test_validate_rejects_owner_confirmation_or_entries():
    base = {
        "schema_version": 1,
        "status": "draft",
        "title": "Work",
        "query": "Work",
        "created_at": "2026-08-03T00:00:00+00:00",
        "sources": [],
        "entries": [],
        "review": {"owner_confirmed": False, "approver": None, "approved_at": None},
    }
    confirmed = dict(base, review={"owner_confirmed": True, "approver": "owner", "approved_at": "now"})
    with pytest.raises(ResearchDraftValidationError, match="owner-confirmed"):
        validate_research_draft(confirmed)
    with pytest.raises(ResearchDraftValidationError, match="active entries"):
        validate_research_draft(dict(base, entries=[{"name": "不可信"}]))


def test_validate_rejects_tampered_source_hash_and_duplicate_source():
    source = {
        "source_id": hashlib.sha256(b"https://example.com/a").hexdigest()[:16],
        "url": "https://example.com/a",
        "title": "A",
        "snippet": "",
        "status": "read",
        "fetched_at": "2026-08-03T00:00:00+00:00",
        "content": "body",
        "content_sha256": "0" * 64,
        "error": "",
    }
    base = {
        "schema_version": 1,
        "status": "draft",
        "title": "Work",
        "query": "Work",
        "created_at": "2026-08-03T00:00:00+00:00",
        "sources": [source],
        "entries": [],
        "review": {"owner_confirmed": False, "approver": None, "approved_at": None},
    }
    with pytest.raises(ResearchDraftValidationError, match="hash mismatch"):
        validate_research_draft(base)
    source["content_sha256"] = hashlib.sha256("body".encode()).hexdigest()
    with pytest.raises(ResearchDraftValidationError, match="duplicate"):
        validate_research_draft(dict(base, sources=[source, dict(source)]))

def test_failed_source_sanitizes_invalid_search_metadata():
    url = "https://example.com/bad"
    search = FakeSearch([SearchResult(123, url, object())])
    reader = FakeReader(errors={url: RuntimeError("reader down")})

    draft = build_research_draft("Work", search_provider=search, reader_provider=reader)

    source = draft["sources"][0]
    assert source["status"] == "read_failed"
    assert source["title"] == ""
    assert source["snippet"] == ""

def test_validate_rejects_malformed_or_timezone_free_timestamps():
    base = {
        "schema_version": 1,
        "status": "draft",
        "title": "Work",
        "query": "Work",
        "created_at": "not-a-timestamp",
        "sources": [],
        "entries": [],
        "review": {"owner_confirmed": False, "approver": None, "approved_at": None},
    }
    with pytest.raises(ResearchDraftValidationError, match="ISO-8601"):
        validate_research_draft(base)
    base["created_at"] = "2026-08-03T00:00:00"
    with pytest.raises(ResearchDraftValidationError, match="timezone"):
        validate_research_draft(base)