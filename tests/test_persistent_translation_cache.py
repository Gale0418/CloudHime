import json

import pytest

from persistent_translation_cache import (
    DEFAULT_MAX_ENTRY_BYTES,
    DEFAULT_MAX_LOAD_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
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


def test_persistent_cache_skips_utf8_entry_over_single_entry_budget(tmp_path, monkeypatch):
    import persistent_translation_cache as cache_module

    monkeypatch.setattr(cache_module, "DEFAULT_MAX_ENTRY_BYTES", 128)
    cache = PersistentTranslationCache(tmp_path / "translation-cache.json")

    assert cache.remember(
        "key",
        TranslationResult(text="翻" * 100, provider="google"),
    ) is False
    assert len(cache) == 0
    assert not cache.path.exists()
    assert DEFAULT_MAX_ENTRY_BYTES == 64 * 1024


def test_persistent_cache_enforces_total_utf8_budget_and_load_file_limit(tmp_path, monkeypatch):
    import persistent_translation_cache as cache_module

    monkeypatch.setattr(cache_module, "DEFAULT_MAX_ENTRY_BYTES", 256)
    monkeypatch.setattr(cache_module, "DEFAULT_MAX_TOTAL_BYTES", 220)
    monkeypatch.setattr(cache_module, "DEFAULT_MAX_LOAD_BYTES", 512)
    path = tmp_path / "translation-cache.json"
    cache = PersistentTranslationCache(path)

    for index in range(3):
        assert cache.remember(
            f"key-{index}",
            TranslationResult(text="翻譯內容", provider="google"),
        )

    assert path.stat().st_size <= 220
    assert cache.get("key-0") is None
    assert DEFAULT_MAX_TOTAL_BYTES == 2 * 1024 * 1024
    assert DEFAULT_MAX_LOAD_BYTES == 4 * 1024 * 1024

    path.write_text(
        json.dumps({"schema_version": 1, "entries": [], "padding": "x" * 600}),
        encoding="utf-8",
    )
    oversized = PersistentTranslationCache(path)
    assert len(oversized) == 0
    assert oversized.last_error_code == "load_failed"


def test_persistent_cache_compact_utf8_budget_is_exact_and_eviction_is_linear(
    tmp_path, monkeypatch
):
    import persistent_translation_cache as cache_module

    entry = {
        "key": "日本語",
        "text": "翻譯",
        "provider": "google",
        "model": None,
        "requested_provider": None,
    }
    entry_bytes = json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    prefix = b'{"schema_version":1,"entries":['
    suffix = b"]}"
    exact_size = len(prefix) + len(entry_bytes) + len(suffix)
    monkeypatch.setattr(cache_module, "DEFAULT_MAX_TOTAL_BYTES", exact_size)
    path = tmp_path / "exact-cache.json"
    cache = PersistentTranslationCache(path)

    assert cache.remember("日本語", TranslationResult(text="翻譯", provider="google"))
    assert path.read_bytes() == prefix + entry_bytes + suffix

    monkeypatch.setattr(cache_module, "DEFAULT_MAX_TOTAL_BYTES", exact_size - 1)
    rejected = PersistentTranslationCache(tmp_path / "too-small-cache.json")
    assert rejected.remember("日本語", TranslationResult(text="翻譯", provider="google")) is False
    assert not rejected.path.exists()

    rows = [
        {
            "key": f"key-{index}",
            "text": "翻譯內容" * 8,
            "provider": "google",
            "model": None,
            "requested_provider": None,
        }
        for index in range(40)
    ]
    source_path = tmp_path / "many-entries.json"
    source_path.write_text(
        json.dumps({"schema_version": 1, "entries": rows}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(cache_module, "DEFAULT_MAX_TOTAL_BYTES", 700)
    serialization_calls = 0
    serialize_entry = cache_module._entry_utf8_bytes

    def count_serializations(key, record):
        nonlocal serialization_calls
        serialization_calls += 1
        return serialize_entry(key, record)

    monkeypatch.setattr(cache_module, "_entry_utf8_bytes", count_serializations)
    loaded = PersistentTranslationCache(source_path)

    assert serialization_calls == len(rows)
    assert len(loaded) < len(rows)
    assert next(reversed(loaded._entries)) == "key-39"
    assert loaded._total_payload_bytes == len(prefix) + len(suffix) + sum(
        len(value) for value in loaded._encoded_entries.values()
    ) + max(0, len(loaded) - 1)
    assert loaded._total_payload_bytes <= 700


def test_persistent_cache_persists_lru_order_after_get_and_overwrite(tmp_path):
    path = tmp_path / "lru-cache.json"
    cache = PersistentTranslationCache(path, max_entries=2)
    assert cache.remember("oldest", TranslationResult(text="舊", provider="google"))
    assert cache.remember("newest", TranslationResult(text="新", provider="google"))

    assert cache.get("oldest") is not None
    assert cache.remember("oldest", TranslationResult(text="更新", provider="google"))
    assert list(cache._entries) == ["newest", "oldest"]

    restored = PersistentTranslationCache(path, max_entries=2)
    assert list(restored._entries) == ["newest", "oldest"]
    assert restored.remember("third", TranslationResult(text="第三", provider="google"))
    assert restored.get("newest") is None
    assert restored.get("oldest") is not None


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


def test_worker_ignores_persisted_untranslated_mixed_language_result(tmp_path):
    from cloudhime_workers import OCRWorker

    worker = _make_worker_for_persistent_route(PersistentTranslationCache(tmp_path / "cache.json"))
    worker.translation_target_lang = "en"
    source = "研究 Gemini 橋接方案升級"
    key = worker._build_persistent_translation_cache_key(source, "gemma")
    worker.persistent_translation_cache.remember(
        key, TranslationResult(text=source, provider="gemma"), requested_provider="gemma"
    )
    calls = []
    worker._translate_text_gemma_result = lambda text: calls.append(text) or TranslationResult(
        text="Research an upgrade to the Gemini bridge", provider="gemma"
    )

    result = OCRWorker._translate_text_preferred_result(worker, source)

    assert result.text == "Research an upgrade to the Gemini bridge"
    assert calls == [source]
    assert worker.persistent_translation_cache.get(key).text == result.text


def test_worker_rejects_partial_batch_before_persisting_it(tmp_path):
    from cloudhime_workers import OCRWorker

    worker = _make_worker_for_persistent_route(PersistentTranslationCache(tmp_path / "cache.json"))
    worker.translation_target_lang = "en"
    worker.split_translated_lines = lambda text, count: text.splitlines()
    worker.translate_text_gemma_with_provider = lambda text: (
        "Corrected Bridge Skill Version Sync\n研究 Gemini 橋接方案升級", "gemma"
    )
    worker.translate_text_google_batch = lambda texts: pytest.fail("Retry incomplete items separately")

    result = OCRWorker.translate_text_batch_with_provider(
        worker, ["修正橋接技能版本同步", "研究 Gemini 橋接方案升級"]
    )

    assert result == ([], "")
    assert len(worker.persistent_translation_cache) == 0


@pytest.mark.parametrize("target_lang", ["en", "ja"])
def test_worker_google_batch_explicitly_passes_target_language(tmp_path, target_lang):
    from cloudhime_workers import OCRWorker

    worker = _make_worker_for_persistent_route(PersistentTranslationCache(tmp_path / "cache.json"))
    worker.translation_target_lang = target_lang
    calls = []

    class Provider:
        def translate_batch(self, texts, *, target_lang="zh-TW"):
            calls.append(target_lang)
            return [TranslationResult(text="translated", provider="google") for _ in texts]

    worker._get_translation_provider = lambda name: Provider()
    worker.log_translation_debug = lambda message: None

    assert worker.translate_text_google_batch(["source"])
    assert calls == [target_lang]


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
