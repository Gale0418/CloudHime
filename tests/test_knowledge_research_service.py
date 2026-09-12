import hashlib
import json
import threading

import pytest

from knowledge_research_service import (
    DEFAULT_GEMMA4_MODEL,
    MAX_EXTRACT_PROMPT_CHARS,
    RESEARCH_MODEL_IDS,
    KnowledgeResearchService,
)
from knowledge_search import SearchResult


class FakeSearch:
    def search(self, query):
        return (SearchResult("Official", "https://example.com/work", "summary"),)


class FakeReader:
    def read(self, url):
        return "Official facts. " + ("untrusted text " * 1000)


class FakeModel:
    def __init__(self):
        self.prompts = []

    def generate_structured_text(self, prompt, **kwargs):
        self.prompts.append((prompt, kwargs))
        source_id = hashlib.sha256("https://example.com/work".encode()).hexdigest()[:16]
        return json.dumps(
            {
                "schema_version": 1,
                "title": "Work",
                "aliases": [],
                "entries": [
                    {
                        "name": "Hero",
                        "aliases": [],
                        "kind": "character",
                        "description": "Official facts.",
                        "confidence": 0.9,
                        "source_ids": [source_id],
                    }
                ],
            }
        )


def test_service_composes_bounded_research_and_extraction():
    model = FakeModel()
    service = KnowledgeResearchService(
        google_api_key="unused",
        search_provider=FakeSearch(),
        reader_provider=FakeReader(),
        model_provider=model,
    )
    cancel_event = threading.Event()

    draft = service.build_research_draft("Work", cancel_event)
    raw = service.extract_candidate(draft, cancel_event)

    assert draft["title"] == "Work"
    assert json.loads(raw)["entries"][0]["name"] == "Hero"
    assert "untrusted evidence" in model.prompts[0][0]
    assert "source_id:" in model.prompts[0][0]
    prompt = model.prompts[0][0]
    assert len(prompt) <= MAX_EXTRACT_PROMPT_CHARS
    assert prompt.count("<source>\n") == prompt.count("</source>")
    assert model.prompts[0][1]["max_output_tokens"] == 4096


def test_service_checks_cancellation_before_each_stage():
    service = KnowledgeResearchService(
        google_api_key="unused",
        search_provider=FakeSearch(),
        reader_provider=FakeReader(),
        model_provider=FakeModel(),
    )
    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(RuntimeError, match="cancelled"):
        service.build_research_draft("Work", cancel_event)


def test_service_forwards_explicit_sources_and_validates_model():
    search = FakeSearch()
    reader = FakeReader()
    service = KnowledgeResearchService(
        google_api_key="unused",
        search_provider=search,
        reader_provider=reader,
        model_provider=FakeModel(),
        model_name=DEFAULT_GEMMA4_MODEL,
    )

    draft = service.build_research_draft(
        "Work",
        threading.Event(),
        source_urls=["https://example.com/work"],
    )

    assert draft["source_mode"] == "explicit"
    with pytest.raises(ValueError, match="unsupported knowledge research model"):
        KnowledgeResearchService(google_api_key="unused", model_name="gemini-unknown")
    assert "gpt-5.6-luna" in RESEARCH_MODEL_IDS


def test_service_can_select_existing_openai_structured_provider():
    service = KnowledgeResearchService(
        openai_api_key="openai-secret",
        model_name="gpt-5.6-luna",
    )

    assert service.model_name == "gpt-5.6-luna"
    assert service.model_provider.available() is True
    assert "openai-secret" not in repr(service.model_provider)


@pytest.mark.parametrize("sources", [[], [{"status": "failed"}],
                                     [{"status": "read", "source_id": "a", "content": "  "}],
                                     [{"status": "read", "content": "facts"}]])
def test_extraction_without_readable_evidence_does_not_call_model(sources):
    model = FakeModel()
    service = KnowledgeResearchService(google_api_key="unused", model_provider=model)
    with pytest.raises(ValueError, match="knowledge_research_no_readable_sources"):
        service.extract_candidate({"title": "Work", "sources": sources}, threading.Event())
    assert model.prompts == []


def test_extraction_excludes_malformed_sources_when_valid_evidence_exists():
    model = FakeModel()
    service = KnowledgeResearchService(google_api_key="unused", model_provider=model)
    service.extract_candidate({"title": "Work", "sources": [
        {"status": "read", "source_id": "valid", "content": "Verified public facts."},
        {"status": "read", "content": "MALFORMED_UNCITED_CONTENT"},
    ]}, threading.Event())
    assert "Verified public facts." in model.prompts[0][0]
    assert "MALFORMED_UNCITED_CONTENT" not in model.prompts[0][0]
