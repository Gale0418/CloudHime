import hashlib
import json
import threading

import pytest

from knowledge_research_service import (
    MAX_EXTRACT_PROMPT_CHARS,
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