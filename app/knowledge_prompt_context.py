"""Shared active Knowledge Pack context for translation providers."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Iterable

from knowledge_retrieval import (
    KnowledgeRetrievalError,
    build_evidence_context,
    pack_revision_token,
    retrieve,
)

KNOWLEDGE_NONE_REVISION_TOKEN = "knowledge-pack:none"
KNOWLEDGE_EVIDENCE_MAX_HITS = 4
KNOWLEDGE_EVIDENCE_MAX_CHARS = 2_400


class KnowledgePromptContext:
    """Keep an immutable-in-use pack snapshot and bounded prompt evidence."""

    def _init_knowledge_prompt_context(self) -> None:
        self._knowledge_pack: dict[str, Any] | None = None
        self._knowledge_revision_token = KNOWLEDGE_NONE_REVISION_TOKEN

    @property
    def knowledge_revision_token(self) -> str:
        return getattr(self, "_knowledge_revision_token", KNOWLEDGE_NONE_REVISION_TOKEN)

    def set_knowledge_pack(self, pack: Mapping[str, Any] | None) -> None:
        """Install or clear the active pack and invalidate provider-local state."""
        if pack is None:
            normalized = None
            revision_token = KNOWLEDGE_NONE_REVISION_TOKEN
        elif not isinstance(pack, Mapping):
            raise KnowledgeRetrievalError("active Knowledge Pack must be an object")
        else:
            normalized = deepcopy(dict(pack))
            revision_token = pack_revision_token(normalized)

        changed = revision_token != self.knowledge_revision_token
        self._knowledge_pack = normalized
        self._knowledge_revision_token = revision_token
        if not changed:
            return

        cache = getattr(self, "_translation_cache", None)
        if hasattr(cache, "clear"):
            cache.clear()
        context_buffer = getattr(self, "_context_buffer", None)
        if hasattr(context_buffer, "clear"):
            context_buffer.clear()

    def _knowledge_evidence_for_texts(
        self,
        texts: Iterable[Any],
        *,
        max_results: int = KNOWLEDGE_EVIDENCE_MAX_HITS,
        max_chars: int = KNOWLEDGE_EVIDENCE_MAX_CHARS,
    ) -> str:
        pack = getattr(self, "_knowledge_pack", None)
        if not pack:
            return ""

        hits = []
        seen: set[tuple[str, int, str]] = set()
        for text in texts:
            if len(hits) >= max_results:
                break
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                candidates = retrieve(pack, text, max_results=max_results)
            except KnowledgeRetrievalError:
                continue
            for hit in candidates:
                if len(hits) >= max_results:
                    break
                key = (hit.pack_id, hit.revision, hit.name)
                if key in seen:
                    continue
                seen.add(key)
                hits.append(hit)

        if not hits:
            return ""
        try:
            return build_evidence_context(hits, max_chars=max_chars)
        except KnowledgeRetrievalError:
            return ""

    @staticmethod
    def _prepend_knowledge_evidence(prompt: str, evidence: str) -> str:
        if not evidence:
            return prompt
        return f"{evidence}\n\n{prompt}"
