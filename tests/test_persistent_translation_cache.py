import json

import pytest

from persistent_translation_cache import (
    PersistentTranslationCache,
    build_translation_cache_key,
)
from translation_contracts import TranslationResult


def test_persistent_cache_round_trips_unicode_and_provider_metadata(tmp_path):
    path = tmp_path / "translation-cache.json"
    key = build_translation_cache_key(
        {
            "source_text": "守りに特化で",
            "requested_provider": "local_multimodal",
            "target_lang": "zh-TW",
            "knowledge_revision": "knowledge-pack:work:r1",
        }
    )
    cache = PersistentTranslationCache(path)
    assert cache.remember(
        key,
        TranslationResult(
            text="專精於防守",
            provider="local_multimodal",
            model="gemma-3-4b-it",
        ),
        requested_provider="local_multimodal",
    )

    restored = PersistentTranslationCache(path).get(key)

    assert restored is not None
    assert restored.text == "專精於防守"
    assert restored.provider == "local_multimodal"
    assert restored.model == "gemma-3-4b-it"
    assert restored.from_cache is True
    assert restored.requested_provider == "local_multimodal"


def test_persistent_cache_key_changes_when_translation_context_changes():
    base = {
        "source_text": "守りに特化で",
        "requested_provider": "gemma",
        "target_lang": "zh-TW",
        "knowledge_revision": "knowledge-pack:none",
    }

    assert build_translation_cache_key(base) == build_translation_cache_key(dict(base))
    assert build_translation_cache_key(base) != build_translation_cache_key(
        {**base, "target_lang": "en"}
    )
    assert build_translation_cache_key(base) != build_translation_cache_key(
        {**base, "source_text": "粉砕特化で"}
    )


def test_persistent_cache_rejects_corrupt_payload_without_raising(tmp_path):
    path = tmp_path / "translation-cache.json"
    path.write_text("{not-json", encoding="utf-8")

    cache = PersistentTranslationCache(path)

    assert len(cache) == 0
    assert cache.last_error_code == "load_failed"


def test_persistent_cache_is_bounded_and_uses_schema_version(tmp_path):
    path = tmp_path / "translation-cache.json"
    cache = PersistentTranslationCache(path, max_entries=2)

    for index in range(3):
        assert cache.remember(
            f"key-{index}",
            TranslationResult(text=f"翻譯 {index}", provider="google"),
            requested_provider="google",
        )

    restored_payload = json.loads(path.read_text(encoding="utf-8"))
    assert restored_payload["schema_version"] == 1
    assert [item["key"] for item in restored_payload["entries"]] == ["key-1", "key-2"]
    assert cache.get("key-0") is None


def test_persistent_cache_write_failure_is_fail_open(tmp_path, monkeypatch):
    path = tmp_path / "translation-cache.json"
    cache = PersistentTranslationCache(path)
    monkeypatch.setattr(cache, "_write_payload", lambda _payload: (_ for _ in ()).throw(OSError("disk full")))

    result = cache.remember(
        "key",
        TranslationResult(text="翻譯", provider="google"),
        requested_provider="google",
    )

    assert result is False
    assert cache.get("key").text == "翻譯"
    assert cache.last_error_code == "write_failed"


def test_persistent_cache_does_not_store_empty_or_unattributed_values(tmp_path):
    cache = PersistentTranslationCache(tmp_path / "translation-cache.json")

    assert cache.remember("empty", TranslationResult(text="", provider="google")) is False
    assert cache.remember("no-provider", TranslationResult(text="翻譯", provider="")) is False
    assert len(cache) == 0


def _make_worker_for_persistent_route(cache):
    from cloudhime_workers import OCRWorker

    worker = OCRWorker.__new__(OCRWorker)
    worker.persistent_translation_cache = cache
    worker.translation_target_lang = "zh-TW"
    worker.knowledge_revision_token = "knowledge-pack:none"
    worker.gemma_model = "gemma-4-31b-it"
    worker.gemma_prompt = ""
    worker.local_multimodal_model = ""
    worker.local_gemma_temperature = 0.2
    worker.local_gemma_repeat_penalty = 1.15
    worker.has_ai_text_provider = lambda: True
    worker.get_current_ai_provider = lambda: "gemma"
    worker._translation_route_cancelled = lambda: False
    return worker


def test_worker_persists_primary_result_and_hits_it_after_restart(tmp_path):
    from cloudhime_workers import OCRWorker

    cache_path = tmp_path / "translation-cache.json"
    first = _make_worker_for_persistent_route(PersistentTranslationCache(cache_path))
    calls = []

    def primary(_text):
        calls.append("gemma")
        return TranslationResult(text="專精於防守", provider="gemma", model="gemma-4-31b-it")

    first._translate_text_gemma_result = primary
    first_result = OCRWorker._translate_text_preferred_result(first, "守りに特化で")

    second = _make_worker_for_persistent_route(PersistentTranslationCache(cache_path))
    second_calls = []
    second._translate_text_gemma_result = lambda _text: second_calls.append("gemma") or TranslationResult(
        text="不應該重新呼叫",
        provider="gemma",
    )

    second_result = OCRWorker._translate_text_preferred_result(second, "守りに特化で")

    assert first_result.text == "專精於防守"
    assert calls == ["gemma"]
    assert second_result.text == "專精於防守"
    assert second_result.provider == "gemma"
    assert second_result.from_cache is True
    assert second_calls == []


def test_worker_does_not_persist_google_fallback_for_local_or_remote_request(tmp_path):
    from cloudhime_workers import OCRWorker

    cache = PersistentTranslationCache(tmp_path / "translation-cache.json")
    worker = _make_worker_for_persistent_route(cache)
    worker._translate_text_gemma_result = lambda _text: (_ for _ in ()).throw(
        ValueError("provider unavailable")
    )
    worker._translate_text_google_result = lambda _text: TranslationResult(
        text="Google 翻譯",
        provider="google",
    )

    result = OCRWorker._translate_text_preferred_result(worker, "原文")

    assert result.provider == "google"
    assert result.requested_provider == "gemma"
    assert result.fallback_reason == "provider_error"
    assert len(cache) == 0


def test_worker_batch_route_persists_only_a_complete_primary_batch(tmp_path):
    from cloudhime_workers import OCRWorker

    cache_path = tmp_path / "translation-cache.json"
    first = _make_worker_for_persistent_route(PersistentTranslationCache(cache_path))
    first.has_ai_text_provider = lambda: False
    first.get_current_ai_provider = lambda: "google"
    first.split_translated_lines = lambda text, count: text.splitlines() if count == 2 else [text]
    first.translate_text_google_batch = lambda _texts: ["第一句", "第二句"]

    first_result = OCRWorker.translate_text_batch_with_provider(first, ["一", "二"])

    second = _make_worker_for_persistent_route(PersistentTranslationCache(cache_path))
    second.has_ai_text_provider = lambda: False
    second.get_current_ai_provider = lambda: "google"
    second.split_translated_lines = lambda text, count: text.splitlines() if count == 2 else [text]
    second.translate_text_google_batch = lambda _texts: pytest.fail("cache should avoid a second request")

    second_result = OCRWorker.translate_text_batch_with_provider(second, ["一", "二"])

    assert first_result == (["第一句", "第二句"], "google")
    assert second_result == first_result