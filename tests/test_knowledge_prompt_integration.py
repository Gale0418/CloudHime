from collections import OrderedDict

import numpy as np

from cloudhime_workers import OCRWorker
from exact_image_cache import ExactImageCache
from dev_local_gemma_provider import LocalGemmaProvider

from translation_providers import (
    GemmaTranslationProvider,
    LocalMultimodalProvider,
)


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


class FakeLocalLlm:
    def __init__(self):
        self.prompts = []
        self.responses = iter(("第一翻譯", "第二翻譯"))

    def create_completion(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return {"choices": [{"text": next(self.responses)}]}


def test_local_gemma_uses_evidence_and_revision_scoped_cache():
    provider = LocalGemmaProvider(enabled=False)
    provider.enabled = True
    provider._llm = FakeLocalLlm()
    provider.set_knowledge_pack(pack(1))

    first = provider.translate("聖騎士")
    assert first.text == "第一翻譯"
    assert "[UNTRUSTED KNOWLEDGE EVIDENCE]" in provider._llm.prompts[0]
    assert "A holy knight used as a named class." in provider._llm.prompts[0]
    first_key = next(iter(provider._translation_cache))
    assert first_key[-1] == "knowledge-pack:work:r1"

    provider.set_knowledge_pack(pack(2))
    second = provider.translate("聖騎士")
    assert second.text == "第二翻譯"
    assert second.from_cache is False
    assert len(provider._llm.prompts) == 2
    assert next(iter(provider._translation_cache))[-1] == "knowledge-pack:work:r2"


def test_gemma_api_prompt_uses_evidence_without_network_call():
    provider = GemmaTranslationProvider(
        google_api_key="test-key",
        gemma_model="gemma-4-31b-it",
    )
    provider.set_knowledge_pack(pack(1))

    prompt = provider._build_prompt("聖騎士")
    assert "[UNTRUSTED KNOWLEDGE EVIDENCE]" in prompt
    assert "A holy knight used as a named class." in prompt


def test_local_multimodal_keeps_json_contract_after_evidence_prefix():
    provider = LocalMultimodalProvider(
        base_url="http://127.0.0.1:8080/v1",
        model_name="gemma-local",
        enabled=True,
    )
    provider.set_knowledge_pack(pack(1))
    payloads = []

    def fake_request(payload):
        payloads.append(payload)
        return '{"segments":[{"index":0,"translation":"聖騎士"}]}'

    provider._request_chat_completion = fake_request
    results = provider.translate_multimodal(
        ["聖騎士"],
        [{"inline_data": {"mime_type": "image/png", "data": "Zm9v"}}],
    )

    prompt = payloads[0]["messages"][0]["content"][0]["text"]
    assert results[0].text == "聖騎士"
    assert "[UNTRUSTED KNOWLEDGE EVIDENCE]" in prompt
    assert "Return JSON only in this exact shape" in prompt
    assert payloads[0]["response_format"] == {"type": "json_object"}


class ProviderProbe:
    def __init__(self):
        self.packs = []

    def set_knowledge_pack(self, pack):
        self.packs.append(pack)


def test_worker_pack_revision_is_in_exact_image_context_and_clears_memories():
    worker = OCRWorker.__new__(OCRWorker)
    worker.active_knowledge_pack = None
    worker.knowledge_revision_token = "knowledge-pack:none"
    worker.translation_cache = OrderedDict({"old": "translation"})
    worker.preferred_text_memory = OrderedDict({"old": "translation"})
    worker.hud_memory = OrderedDict({"old": "translation"})
    worker.exact_image_cache = ExactImageCache()
    worker.last_combined_text = "old"
    worker.last_results = [("old",)]
    worker.last_provider = "old"
    worker.gemma_translation_provider = ProviderProbe()
    worker.local_multimodal_provider = ProviderProbe()
    worker.scan_mode = "fullscreen"
    worker.region_render_mode = "bubble"
    worker.scan_region = None
    worker.ocr_backend_chain = ()
    worker.ocr_backends = []
    worker.binary_threshold = 100
    worker.auto_threshold_enabled = False
    worker.google_ocr_enabled = False
    worker.japanese_rescue_enabled = False
    worker.japanese_rescue_runtime = None
    worker.use_gemma_translation = True
    worker.gemma_auto_switch_enabled = False
    worker.gemma_model = "gemma-3-27b-it"
    worker.gemma_prompt = ""
    worker.screenshot_gemma_prompt = ""
    worker.google_api_key = ""
    worker.local_multimodal_enabled = False
    worker.local_multimodal_base_url = ""
    worker.local_multimodal_model = ""
    worker.local_gemma_temperature = 0.2
    worker.local_gemma_repeat_penalty = 1.15

    worker.set_knowledge_pack(pack(1))
    first_context = worker._exact_image_cache_context(0, 0)
    assert worker.knowledge_revision_token == "knowledge-pack:work:r1"
    assert first_context[1] == "knowledge-pack:work:r1"
    assert not worker.translation_cache
    assert not worker.preferred_text_memory
    assert not worker.hud_memory
    assert worker.last_results == []

    worker.set_knowledge_pack(pack(2))
    second_context = worker._exact_image_cache_context(0, 0)
    assert first_context != second_context
    assert second_context[1] == "knowledge-pack:work:r2"
    assert all(probe.packs[-1]["revision"] == 2 for probe in (
        worker.gemma_translation_provider,
        worker.local_multimodal_provider,
    ))
