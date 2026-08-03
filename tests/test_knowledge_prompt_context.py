from collections import OrderedDict, deque

from knowledge_prompt_context import KnowledgePromptContext


def pack(revision=1):
    return {
        "pack_id": "work",
        "revision": revision,
        "title": "Work",
        "entries": [
            {
                "name": "聖騎士",
                "aliases": ["パラディン"],
                "kind": "term",
                "description": "A holy knight used as a named class.",
                "source_ids": ["0123456789abcdef"],
            }
        ],
    }


class ContextProbe(KnowledgePromptContext):
    def __init__(self):
        self._translation_cache = OrderedDict({"old": "translation"})
        self._context_buffer = deque([("old", "old translation", "zh-TW")], maxlen=3)
        self._init_knowledge_prompt_context()


def test_pack_snapshot_and_revision_change_clear_provider_state():
    probe = ContextProbe()
    probe.set_knowledge_pack(pack(1))

    assert probe.knowledge_revision_token == "knowledge-pack:work:r1"
    assert not probe._translation_cache
    assert not probe._context_buffer

    probe._translation_cache["new"] = "translation"
    probe.set_knowledge_pack(pack(2))
    assert probe.knowledge_revision_token == "knowledge-pack:work:r2"
    assert not probe._translation_cache


def test_pack_snapshot_is_not_affected_by_caller_mutation():
    source = pack(1)
    probe = ContextProbe()
    probe.set_knowledge_pack(source)
    source["entries"][0]["description"] = "mutated outside provider"

    evidence = probe._knowledge_evidence_for_texts(("聖騎士",))
    assert "A holy knight used as a named class." in evidence
    assert "mutated outside provider" not in evidence


def test_evidence_is_empty_without_pack_or_without_matching_terms():
    probe = ContextProbe()
    assert probe._knowledge_evidence_for_texts(("聖騎士",)) == ""
    probe.set_knowledge_pack(pack())
    assert probe._knowledge_evidence_for_texts(("unrelated text",)) == ""

def test_aggregate_evidence_respects_total_hit_limit():
    probe = ContextProbe()
    data = pack()
    data["entries"].append({
        "name": "勇者",
        "aliases": [],
        "kind": "term",
        "description": "A hero.",
        "source_ids": ["0123456789abcdef"],
    })
    probe.set_knowledge_pack(data)
    evidence = probe._knowledge_evidence_for_texts(("聖騎士", "勇者"), max_results=1)
    assert evidence.count("source_ids=") == 1
