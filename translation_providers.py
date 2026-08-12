from __future__ import annotations

import json
import hashlib
import difflib
import re
import time
import math
import os
import threading
from collections import Counter, OrderedDict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Sequence
from urllib import error, request

from deep_translator import GoogleTranslator

from model_catalog import get_model_spec, REGISTRY_DEFAULT_MODEL, REMOTE_TRANSLATION_MODEL_IDS
from translation_contracts import TranslationProvider, TranslationResult
from knowledge_prompt_context import KnowledgePromptContext
from vision_region import (
    VisionRegionResult,
    build_region_vision_prompt,
    parse_region_vision_response,
)
from translation_helpers import (
    append_missing_dictionary_terms,
    apply_dictionary_pre_translation,
    build_gemma_prompt,
    build_gemma_prompt_conservative,
    build_gemma_prompt_with_override,
    build_gemma_multimodal_prompt,
    build_dictionary_prompt_hint,
    clean_model_output,
    clean_model_output_multiline,
    build_gemma_screenshot_prompt_v3,
    build_screenshot_prompt_with_override,
    clean_screenshot_translation_output,
    is_valid_screenshot_translation,
    detect_source_language,
    extract_gemma_text,
    load_translation_dictionary,
    parse_segmented_translation_json,
    split_translated_lines,
)

GOOGLE_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GOOGLE_STREAM_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
DEFAULT_GEMMA_MODEL = REGISTRY_DEFAULT_MODEL
SUPPORTED_GEMMA_MODEL_NAMES = REMOTE_TRANSLATION_MODEL_IDS
GEMMA_RATE_LIMIT_WINDOW_SEC = 60
GEMMA_RATE_LIMIT_MAX_CALLS_BY_MODEL = {
    "gemma-4-26b-a4b-it": 15,
    "gemma-4-31b-it": 15,
    "gemini-3.6-flash": 15,
    "gemini-3.5-flash": 15,
    "gemini-3.1-flash-lite": 15,
    "gemini-2.5-pro": 15,
}
TRANSLATION_CACHE_LIMIT = 512
LOCAL_MULTIMODAL_BATCH_SIZE = 4
LOCAL_MULTIMODAL_OCR_TEMPERATURE = 0.1
LOCAL_MULTIMODAL_OCR_REPEAT_PENALTY = 1.0

LOCAL_RUNTIME_METRIC_KEYS = frozenset({
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_n",
    "predicted_n",
    "prompt_ms",
    "predicted_ms",
})


_REGION_VISION_VALUE_ERROR_CODES = {
    "missing_image_context": "request_missing_image",
    "missing_region_hints": "request_missing_hints",
    "missing_google_api_key": "provider_unavailable",
    "gemma_rate_limited": "provider_rate_limited",
    "local_multimodal_unavailable": "provider_unavailable",
    "empty_region_vision_response": "response_empty",
    "incomplete_region_vision_response": "response_region_mismatch",
    "Response is not valid JSON.": "response_json_invalid",
    "Response contains text outside the JSON value.": "response_json_invalid",
    "Response must be text.": "response_schema_invalid",
    "Response must be a JSON object containing only regions.": "response_schema_invalid",
    "regions must be a JSON array.": "response_schema_invalid",
    "Each region must contain exactly id, source_text, translation, and confidence.": "response_schema_invalid",
    "source_text and translation must be non-empty strings.": "response_schema_invalid",
    "confidence must be a finite number.": "response_schema_invalid",
    "Region id must be an integer.": "response_region_mismatch",
    "Response contains an id outside allowed_ids.": "response_region_mismatch",
    "Response contains a duplicate region id.": "response_region_mismatch",
}


def classify_region_vision_failure(exception: BaseException | None) -> str:
    """Return a bounded diagnostic token without exposing exception text."""
    if exception is None:
        return "unknown"
    if isinstance(exception, error.HTTPError):
        status = getattr(exception, "code", None)
        if isinstance(status, int) and 100 <= status <= 599:
            return f"request_http_{status}"
        return "request_http_error"
    if isinstance(exception, TimeoutError):
        return "request_timeout"
    if isinstance(exception, error.URLError):
        return "request_transport"
    if isinstance(exception, json.JSONDecodeError):
        return "response_json_invalid"
    if isinstance(exception, (KeyError, IndexError, TypeError)):
        return "response_schema_invalid"
    if isinstance(exception, ValueError):
        # Only exact, internal sentinel messages are classified; arbitrary
        # provider text is intentionally collapsed to the generic token.
        return _REGION_VISION_VALUE_ERROR_CODES.get(str(exception), "provider_error")
    return "provider_error"


@dataclass(frozen=True)
class TranslationProviderConfig:
    google_api_key: str = ""
    gemma_model: str = DEFAULT_GEMMA_MODEL
    gemma_auto_switch_enabled: bool = False
    target_lang: str = "zh-TW"


class GoogleTranslationProvider:
    name = "google"

    def __init__(self, *, target_lang: str = "zh-TW"):
        self.target_lang = target_lang
        self._translators: dict[tuple[str, str], GoogleTranslator] = {}
        self._translation_cache: OrderedDict[Any, Any] = OrderedDict()
        self._dictionary = load_translation_dictionary()

    def set_target_lang(self, target_lang: str) -> None:
        target_lang = (target_lang or "").strip() or "zh-TW"
        if target_lang != self.target_lang:
            self.target_lang = target_lang
            self._translators.clear()

    def available(self) -> bool:
        return True

    def _get_translator(self, source_lang: str, target_lang: str) -> GoogleTranslator:
        cache_key = (source_lang, target_lang)
        translator = self._translators.get(cache_key)
        if translator is None:
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            self._translators[cache_key] = translator
        return translator

    def _get_cached(self, cache_key: Any):
        cached = self._translation_cache.get(cache_key)
        if cached is not None:
            self._translation_cache.move_to_end(cache_key)
        return cached

    def _remember(self, cache_key: Any, translated_text: Any) -> None:
        self._translation_cache[cache_key] = translated_text
        self._translation_cache.move_to_end(cache_key)
        if len(self._translation_cache) > TRANSLATION_CACHE_LIMIT:
            self._translation_cache.popitem(last=False)

    def translate(
        self,
        text: str,
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> TranslationResult:
        normalized = clean_model_output_multiline(text).strip() if text else ""
        if not normalized:
            return TranslationResult(text="", provider=self.name)
        resolved_target = target_lang or self.target_lang
        source_lang = source_lang if source_lang != "auto" else detect_source_language(normalized)
        cache_key = (source_lang, normalized, resolved_target)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return TranslationResult(text=str(cached), provider=self.name, from_cache=True)
        translator = self._get_translator(source_lang, resolved_target)
        source_for_translation = apply_dictionary_pre_translation(normalized, self._dictionary)
        translated_raw = translator.translate(source_for_translation)
        if not isinstance(translated_raw, str):
            raise ValueError("empty_google_translation")
        translated = translated_raw.strip()
        if not translated:
            raise ValueError("empty_google_translation")
        self._remember(cache_key, translated)
        return TranslationResult(text=translated, provider=self.name)

    def translate_batch(
        self,
        texts: Sequence[str],
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> list[TranslationResult]:
        normalized_texts = [clean_model_output(text).strip() if text else "" for text in texts]
        if not normalized_texts or any(not text for text in normalized_texts):
            return []
        resolved_target = target_lang or self.target_lang

        translated = [None] * len(normalized_texts)
        index = 0
        while index < len(normalized_texts):
            batch_source_lang = source_lang if source_lang != "auto" else detect_source_language(normalized_texts[index])
            group_start = index
            group_texts = [normalized_texts[index]]
            index += 1
            while index < len(normalized_texts):
                current_source_lang = source_lang if source_lang != "auto" else detect_source_language(normalized_texts[index])
                if current_source_lang != batch_source_lang:
                    break
                group_texts.append(normalized_texts[index])
                index += 1

            cache_key = ("google-batch", batch_source_lang, tuple(group_texts), resolved_target)
            batch_result = self._get_cached(cache_key)
            if batch_result is None:
                translator = self._get_translator(batch_source_lang, resolved_target)
                prepared_group_texts = [
                    apply_dictionary_pre_translation(item, self._dictionary)
                    for item in group_texts
                ]
                combined_source = "\n".join(prepared_group_texts)
                combined_translated_raw = translator.translate(combined_source)
                if not isinstance(combined_translated_raw, str):
                    return []
                combined_translated = combined_translated_raw.strip()
                if not combined_translated:
                    return []
                batch_result = split_translated_lines(combined_translated, len(group_texts))
                if len(batch_result) != len(group_texts):
                    return []
                self._remember(cache_key, batch_result)
            for offset, line in enumerate(batch_result):
                translated[group_start + offset] = TranslationResult(text=line, provider=self.name)
                self._remember((batch_source_lang, group_texts[offset], resolved_target), line)

        return [item for item in translated if item is not None]


class GemmaTranslationProvider(KnowledgePromptContext):
    name = "gemma"

    def __init__(
        self,
        *,
        google_api_key: str = "",
        gemma_model: str = DEFAULT_GEMMA_MODEL,
        gemma_prompt: str = "",
        screenshot_gemma_prompt: str = "",
        target_lang: str = "zh-TW",
        gemma_enabled: bool = False,
        auto_switch_enabled: bool = False,
        supported_models: Sequence[str] = SUPPORTED_GEMMA_MODEL_NAMES,
    ):
        self.google_api_key = (google_api_key or "").strip()
        self.target_lang = target_lang
        self.enabled = bool(gemma_enabled)
        self.auto_switch_enabled = bool(auto_switch_enabled)
        self.gemma_prompt = (gemma_prompt or "").strip()
        self.screenshot_gemma_prompt = (screenshot_gemma_prompt or "").strip()
        self.supported_models = tuple(supported_models) if supported_models else SUPPORTED_GEMMA_MODEL_NAMES
        self.last_config_warning = ""
        self.gemma_model = self.normalize_gemma_model(gemma_model)
        self._translation_cache: OrderedDict[Any, Any] = OrderedDict()
        self._rate_limit_lock = threading.RLock()
        self._call_timestamps: dict[str, list[float]] = {name: [] for name in self.supported_models}
        self._init_knowledge_prompt_context()
        self._dictionary = load_translation_dictionary()

    def update_config(
        self,
        *,
        google_api_key: str | None = None,
        gemma_model: str | None = None,
        gemma_prompt: str | None = None,
        screenshot_gemma_prompt: str | None = None,
        target_lang: str | None = None,
        gemma_enabled: bool | None = None,
        auto_switch_enabled: bool | None = None,
        supported_models: Sequence[str] | None = None,
    ) -> str | None:
        self.last_config_warning = ""
        if google_api_key is not None:
            self.google_api_key = (google_api_key or "").strip()
        if supported_models is not None:
            new_supported_models = tuple(supported_models) if supported_models else SUPPORTED_GEMMA_MODEL_NAMES
            if new_supported_models != self.supported_models:
                with self._rate_limit_lock:
                    previous_timestamps = self._call_timestamps
                    self.supported_models = new_supported_models
                    self._call_timestamps = {
                        name: list(previous_timestamps.get(name, []))
                        for name in self.supported_models
                    }
        if gemma_model is not None:
            self.gemma_model = self.normalize_gemma_model(gemma_model)
        if gemma_prompt is not None:
            self.gemma_prompt = (gemma_prompt or "").strip()
        if screenshot_gemma_prompt is not None:
            self.screenshot_gemma_prompt = (screenshot_gemma_prompt or "").strip()
        if target_lang is not None:
            self.target_lang = (target_lang or "").strip() or self.target_lang
        if gemma_enabled is not None:
            self.enabled = bool(gemma_enabled)
        if auto_switch_enabled is not None:
            self.auto_switch_enabled = bool(auto_switch_enabled)
        return self.last_config_warning or None

    def available(self) -> bool:
        return bool(self.google_api_key)

    def normalize_gemma_model(self, model_name: str | None) -> str:
        requested = (model_name or "").strip()
        if requested in self.supported_models:
            return requested
        fallback = DEFAULT_GEMMA_MODEL
        if fallback not in self.supported_models and self.supported_models:
            fallback = self.supported_models[0]
        self.last_config_warning = (
            f"invalid_model:{requested or '<empty>'};fallback={fallback}"
        )
        return fallback

    def _get_cached(self, cache_key: Any):
        cached = self._translation_cache.get(cache_key)
        if cached is not None:
            self._translation_cache.move_to_end(cache_key)
        return cached

    def _remember(self, cache_key: Any, translated_text: Any) -> None:
        self._translation_cache[cache_key] = translated_text
        self._translation_cache.move_to_end(cache_key)
        if len(self._translation_cache) > TRANSLATION_CACHE_LIMIT:
            self._translation_cache.popitem(last=False)

    def _build_prompt(self, text: str, target_lang: str | None = None) -> str:
        """用自訂 prompt 結合模型特定的預設 prompt。"""
        resolved_target = target_lang or self.target_lang
        dictionary_hint = build_dictionary_prompt_hint(text, self._dictionary)
        custom_prompt = "\n\n".join(part for part in (self.gemma_prompt, dictionary_hint) if part)
        base_prompt = build_gemma_prompt_with_override(text, custom_prompt, resolved_target, self.gemma_model)
        evidence = self._knowledge_evidence_for_texts((text,), max_chars=1_800)
        return self._prepend_knowledge_evidence(base_prompt, evidence)

    def _build_multimodal_prompt(self, texts, target_lang: str | None = None) -> str:
        """多模態版，自訂 prompt 附加在前面（保留原有格式）。"""
        resolved_target = target_lang or self.target_lang
        base = build_gemma_multimodal_prompt(texts, target_lang=resolved_target)
        dictionary_hint = build_dictionary_prompt_hint(texts, self._dictionary)
        custom = "\n\n".join(part for part in (self.gemma_prompt.strip(), dictionary_hint) if part)
        if custom:
            base = f"{custom}\n\n{base}"
        evidence = self._knowledge_evidence_for_texts(texts, max_chars=2_400)
        return self._prepend_knowledge_evidence(base, evidence)

    def _normalize_compare_text(self, text: Any) -> str:
        normalized = clean_model_output(text)
        if not normalized:
            return ""
        normalized = re.sub(r"[\s\(\)（）\[\]【】「」『』《》<>“”\"'、，。！？!?…：;；\-—~]+", "", normalized)
        return normalized.lower()

    def _should_fallback_to_text_translation(self, source_text_hint: Any, translated_text: Any) -> bool:
        """
        截圖模式fallback：極度保守，幾乎不切換到文字翻譯
        因為截圖模式有專用prompt，應該信任AI模型的輸出
        """
        translated_str = str(translated_text or "")

        # 只有在完全沒有輸出時才fallback
        if len(translated_str.strip()) < 1:
            return True

        # 其他情況都信任截圖模式的輸出
        return False

    def _prune_timestamps(self, model_name: str) -> None:
        cutoff = time.monotonic() - GEMMA_RATE_LIMIT_WINDOW_SEC
        with self._rate_limit_lock:
            self._call_timestamps[model_name] = [
                ts for ts in self._call_timestamps.get(model_name, []) if ts >= cutoff
            ]

    def _max_calls_for_model(self, model_name: str) -> int:
        model_name = (model_name or "").strip().lower()
        return GEMMA_RATE_LIMIT_MAX_CALLS_BY_MODEL.get(model_name, 15)

    def _can_call(self, model_name: str) -> bool:
        with self._rate_limit_lock:
            self._prune_timestamps(model_name)
            current_calls = len(self._call_timestamps.get(model_name, []))
            return current_calls < self._max_calls_for_model(model_name)

    def _record_call(self, model_name: str) -> None:
        with self._rate_limit_lock:
            self._prune_timestamps(model_name)
            self._call_timestamps.setdefault(model_name, []).append(time.monotonic())

    def _wait_if_needed(self, model_name: str) -> None:
        """如果需要，等待直到可以進行下一次調用。"""
        with self._rate_limit_lock:
            self._prune_timestamps(model_name)
            timestamps = list(self._call_timestamps.get(model_name, []))
            wait_time = 0.0
            if len(timestamps) >= self._max_calls_for_model(model_name):
                wait_time = GEMMA_RATE_LIMIT_WINDOW_SEC - (time.monotonic() - timestamps[0])

        if wait_time > 0:
            print(f"⏳ 速率限制：等待 {wait_time:.1f} 秒避免429錯誤...")
            time.sleep(wait_time + 1)
            self._prune_timestamps(model_name)

    def _request_timeout_seconds(self, model_name: str) -> int:
        spec = get_model_spec(model_name)
        return spec.timeout_seconds if spec is not None else 30

    def _should_retry_request(self, exc: Exception) -> bool:
        if isinstance(exc, error.HTTPError):
            return exc.code in {429, 500, 503, 504}
        return isinstance(exc, (TimeoutError, error.URLError))

    def _resolve_model(self) -> str:
        model = self.normalize_gemma_model(self.gemma_model)
        if self._can_call(model):
            return model
        if self.auto_switch_enabled:
            for candidate in self.supported_models:
                if candidate == model:
                    continue
                if self._can_call(candidate):
                    return candidate
        return model

    def _generation_config(
        self,
        model_name: str,
        *,
        max_output_tokens: int,
        temperature: float,
        response_mime_type: str | None = None,
    ) -> dict[str, Any]:
        config: dict[str, Any] = {
            "maxOutputTokens": max_output_tokens,
        }
        if response_mime_type:
            config["responseMimeType"] = response_mime_type
        spec = get_model_spec(model_name)
        if spec is None or spec.accepts_sampling_params:
            config.update({
                "temperature": temperature,
                "topP": 0.9,
                "topK": 32,
            })
        return config
    def _request(self, model_name: str, prompt: str, *, image_parts: Sequence[dict[str, Any]] | None = None, max_output_tokens: int = 1024, temperature: float = 0.2, response_mime_type: str = "text/plain") -> dict[str, Any]:
        req_body = {
            "contents": [
                {
                    "parts": ([*image_parts] if image_parts else []) + [{"text": prompt}],
                }
            ],
            "generationConfig": self._generation_config(
                model_name,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                response_mime_type=response_mime_type,
            ),
        }
        req = request.Request(
            GOOGLE_API_ENDPOINT.format(model=model_name),
            data=json.dumps(req_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.google_api_key,
            },
            method="POST",
        )
        timeout_seconds = self._request_timeout_seconds(model_name)
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                self._record_call(model_name)
                with request.urlopen(req, timeout=timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                last_exc = exc
                if attempt < 2 and self._should_retry_request(exc):
                    time.sleep(0.8 * (attempt + 1))
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("request_failed")

    def generate_structured_text(
        self,
        prompt: str,
        *,
        max_output_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> str:
        """Request bounded JSON text for explicit Knowledge research operations."""
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            raise ValueError("knowledge_prompt_empty")
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        model_name = self.normalize_gemma_model(self.gemma_model)
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")
        payload = self._request(
            model_name,
            normalized_prompt,
            max_output_tokens=max(1, min(8192, int(max_output_tokens))),
            temperature=max(0.0, min(1.0, float(temperature))),
            response_mime_type="application/json",
        )
        raw_text = extract_gemma_text(payload).strip()
        if not raw_text:
            raise ValueError("empty_structured_response")
        return raw_text

    def _stream_request(self, model_name: str, prompt: str, *, image_parts=None, max_output_tokens: int = 1024, temperature: float = 0.2):
        """Generator: 以 SSE 串流方式逐段 yield 文字 chunk。"""
        req_body = {
            "contents": [{"parts": ([*image_parts] if image_parts else []) + [{"text": prompt}]}],
            "generationConfig": self._generation_config(
                model_name,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            ),
        }
        req = request.Request(
            GOOGLE_STREAM_ENDPOINT.format(model=model_name),
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.google_api_key},
            method="POST",
        )
        self._record_call(model_name)
        with request.urlopen(req, timeout=30) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                try:
                    chunk_data = json.loads(data_str)
                    parts = chunk_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                    for part in parts:
                        text = part.get("text", "")
                        if text:
                            yield text
                except (json.JSONDecodeError, IndexError, KeyError):
                    pass

    def translate_stream(self, text: str, *, target_lang: str = "zh-TW"):
        """Generator: 串流翻譯，每次 yield 一個文字 chunk（打字機效果用）。"""
        normalized = clean_model_output(text).strip() if text else ""
        if not normalized:
            return
        resolved_target = target_lang or self.target_lang
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        model_name = self._resolve_model()
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")
        # 快取命中時直接 yield 完整結果
        cache_key = ("gemma", model_name, normalized, resolved_target, self.gemma_prompt, self.knowledge_revision_token)
        cached = self._get_cached(cache_key)
        if cached is not None:
            yield str(cached)
            return
        prompt = self._build_prompt(normalized, resolved_target)
        accumulated = ""
        for chunk in self._stream_request(model_name, prompt, max_output_tokens=1024, temperature=0.2):
            accumulated += chunk
            yield chunk
        final = clean_model_output(accumulated)
        if final:
            self._remember(cache_key, final)

    def translate(
        self,
        text: str,
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> TranslationResult:
        normalized = clean_model_output_multiline(text).strip() if text else ""
        if not normalized:
            return TranslationResult(text="", provider=self.name, model=self.gemma_model)
        resolved_target = target_lang or self.target_lang
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        model_name = self._resolve_model()
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")
        cache_key = (
            "gemma",
            model_name,
            normalized,
            resolved_target,
            self.gemma_prompt,
            self.knowledge_revision_token,
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            return TranslationResult(text=str(cached), provider=self.name, model=model_name, from_cache=True)
        payload = self._request(
            model_name,
            self._build_prompt(normalized, resolved_target),
            max_output_tokens=1024,
            temperature=0.2,
        )
        translated = clean_model_output_multiline(extract_gemma_text(payload))
        if not translated:
            raise ValueError("empty_gemma_response")
        self._remember(cache_key, translated)
        return TranslationResult(text=translated, provider=self.name, model=model_name, raw_text=extract_gemma_text(payload))

    def translate_batch(
        self,
        texts: Sequence[str],
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> list[TranslationResult]:
        normalized_texts = [clean_model_output(text).strip() if text else "" for text in texts]
        if not normalized_texts or any(not text for text in normalized_texts):
            return []
        combined_source = "\n".join(normalized_texts)
        result = self.translate(combined_source, source_lang=source_lang, target_lang=target_lang)
        split = split_translated_lines(result.text, len(normalized_texts))
        if len(split) != len(normalized_texts):
            return []
        return [TranslationResult(text=line, provider=self.name, model=result.model, raw_text=result.raw_text) for line in split]

    def translate_multimodal(
        self,
        texts: Sequence[str],
        image_parts: Sequence[dict[str, Any]],
        *,
        target_lang: str = "zh-TW",
    ) -> list[TranslationResult]:
        if not texts:
            return []
        if not image_parts:
            raise ValueError("missing_image_context")
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        resolved_target = target_lang or self.target_lang
        model_name = self._resolve_model()
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")
        normalized_texts = tuple(clean_model_output(text).strip() if text else "" for text in texts)
        image_seed = json.dumps(image_parts, sort_keys=True, ensure_ascii=False)
        cache_key = (
            "gemma-mm",
            model_name,
            normalized_texts,
            hashlib.sha1(image_seed.encode("utf-8")).hexdigest(),
            resolved_target,
            self.gemma_prompt,
            self.knowledge_revision_token,
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            translated_items, raw_text = cached
            return [
                TranslationResult(text=item, provider=self.name, model=model_name, raw_text=raw_text, from_cache=True)
                for item in translated_items
            ]

        payload = self._request(
            model_name,
            self._build_multimodal_prompt(texts, resolved_target),
            image_parts=image_parts,
            max_output_tokens=2048,
            temperature=0.1,
        )
        raw_text = extract_gemma_text(payload)
        translated = parse_segmented_translation_json(raw_text, len(texts))
        if not translated:
            translated = split_translated_lines(clean_model_output(raw_text), len(texts))
        if len(translated) != len(texts):
            raise ValueError("empty_gemma_multimodal_response")
        self._remember(cache_key, (translated, raw_text))
        return [TranslationResult(text=line, provider=self.name, model=model_name, raw_text=raw_text) for line in translated]

    def interpret_regions(
        self,
        image_parts: Sequence[dict[str, Any]],
        hints: Sequence[dict[str, Any]],
        *,
        image_width: int,
        image_height: int,
        target_lang: str = "zh-TW",
    ) -> list[VisionRegionResult]:
        if not image_parts:
            raise ValueError("missing_image_context")
        if not hints:
            raise ValueError("missing_region_hints")
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")

        resolved_target = target_lang or self.target_lang
        hint_texts = tuple(str(hint.get("text") or "") for hint in hints)
        dictionary_hint = build_dictionary_prompt_hint(hint_texts, self._dictionary)
        evidence = self._knowledge_evidence_for_texts(hint_texts, max_chars=1_800)
        knowledge_context = "  ".join(
            part for part in (dictionary_hint, evidence) if part
        )
        prompt = build_region_vision_prompt(
            hints,
            image_width=image_width,
            image_height=image_height,
            target_lang=resolved_target,
            knowledge_context=knowledge_context,
        )
        allowed_ids = [hint["id"] for hint in hints]
        model_name = self._resolve_model()
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")
        model_spec = get_model_spec(model_name)
        response_mime_type = (
            "application/json"
            if model_spec is None or model_spec.structured_json
            else "text/plain"
        )
        payload = self._request(
            model_name,
            prompt,
            image_parts=image_parts,
            max_output_tokens=2048,
            temperature=0.1,
            response_mime_type=response_mime_type,
        )
        results = parse_region_vision_response(
            extract_gemma_text(payload),
            allowed_ids=allowed_ids,
        )
        if not results:
            raise ValueError("empty_region_vision_response")
        return results

    def translate_screenshot(
        self,
        image_parts: Sequence[dict[str, Any]],
        *,
        target_lang: str = "zh-TW",
        source_text_hint: str | None = None,
        debug_log: Callable[[str], None] | None = None,
    ) -> TranslationResult:
        if not image_parts:
            raise ValueError("missing_image_context")
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        resolved_target = target_lang or self.target_lang
        model_name = self._resolve_model()
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")

        cache_seed = json.dumps(image_parts, sort_keys=True, ensure_ascii=False)
        cache_key = (
            "gemma-screenshot",
            model_name,
            hashlib.sha1(cache_seed.encode("utf-8")).hexdigest(),
            resolved_target,
            self.screenshot_gemma_prompt,
            hashlib.sha1((source_text_hint or "").encode("utf-8")).hexdigest(),
            self.knowledge_revision_token,
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            if isinstance(cached, tuple) and len(cached) >= 5:
                translated_text, raw_text, actual_provider, requested_provider, fallback_reason = cached
            else:
                translated_text, raw_text = cached
                actual_provider, requested_provider, fallback_reason = self.name, None, None
            return TranslationResult(
                text=str(translated_text),
                provider=actual_provider,
                model=model_name,
                raw_text=raw_text,
                from_cache=True,
                requested_provider=requested_provider,
                fallback_reason=fallback_reason,
            )

        last_raw_text = ""
        translated = ""
        payload = None
        for attempt_index in range(3):
            retry_note = None
            if attempt_index >= 1 and last_raw_text:
                retry_note = (
                    "Rewrite the previous answer as translation only. "
                    f"Previous answer was: {last_raw_text[:600]}"
                )
            dictionary_hint = build_dictionary_prompt_hint(source_text_hint or "", self._dictionary)
            custom_prompt = "\n\n".join(part for part in (self.screenshot_gemma_prompt, dictionary_hint) if part)
            prompt = build_screenshot_prompt_with_override(
                source_text_hint, retry_note, custom_prompt, target_lang=resolved_target
            )
            evidence = self._knowledge_evidence_for_texts((source_text_hint or "",), max_chars=1_800)
            prompt = self._prepend_knowledge_evidence(prompt, evidence)
            try:
                payload = self._request(
                    model_name, prompt, image_parts=image_parts, max_output_tokens=2048,
                    temperature=0.0 if attempt_index else 0.1,
                    # gemma-3-27b-it does not support JSON mode for screenshot requests.
                    # Keep the prompt JSON-shaped, but let the model answer in plain text so
                    # the existing cleaner can extract JSON or fallback text safely.
                    response_mime_type="text/plain",
                )
            except error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    body = ""
                if "Image input modality is not enabled" in body and source_text_hint:
                    return self.translate(source_text_hint, target_lang=resolved_target)
                if exc.code == 404 and source_text_hint:
                    break
                if exc.code in {429, 500, 503, 504} and attempt_index < 2:
                    time.sleep(0.8 * (attempt_index + 1))
                    continue
                raise
            except (TimeoutError, error.URLError):
                if source_text_hint:
                    break
                if attempt_index < 2:
                    time.sleep(0.8 * (attempt_index + 1))
                    continue
                raise
            last_raw_text = extract_gemma_text(payload)
            translated = clean_screenshot_translation_output(last_raw_text, target_lang=resolved_target)
            is_valid = is_valid_screenshot_translation(translated, target_lang=resolved_target)
            if debug_log is not None:
                debug_log(f"[screenshot attempt {attempt_index + 1}] model={model_name} valid={is_valid} raw_len={len(last_raw_text)} cleaned_len={len(translated)}")
            if is_valid:
                break
            translated = ""
        if not translated:
            actual_provider = self.name
            requested_provider = None
            fallback_reason = None
            if source_text_hint:
                try:
                    translated_result = self.translate(source_text_hint, target_lang=resolved_target)
                    translated = translated_result.text if translated_result else ""
                    actual_provider = translated_result.provider if translated_result else self.name
                    requested_provider = (
                        (translated_result.requested_provider or self.name)
                        if translated_result else self.name
                    )
                    fallback_reason = (
                        (translated_result.fallback_reason or "screenshot_fallback")
                        if translated_result else "screenshot_fallback"
                    )
                except Exception:
                    try:
                        translated = GoogleTranslator(source=detect_source_language(source_text_hint), target=resolved_target).translate(clean_model_output(source_text_hint)).strip()
                        actual_provider = "google"
                        requested_provider = self.name
                        fallback_reason = "screenshot_fallback"
                    except Exception:
                        translated = ""
            if debug_log is not None:
                debug_log(f"[screenshot failed] model={model_name} last_raw_len={len(last_raw_text)}")
            if translated:
                self._remember(cache_key, (translated, last_raw_text, actual_provider, requested_provider, fallback_reason))
                return TranslationResult(text=translated, provider=actual_provider, model=model_name, raw_text=last_raw_text, requested_provider=requested_provider, fallback_reason=fallback_reason)
            raise ValueError("empty_gemma_screenshot_response")
        actual_provider = self.name
        requested_provider = None
        fallback_reason = None
        if source_text_hint and self._should_fallback_to_text_translation(source_text_hint, translated):
            try:
                source_lang = detect_source_language(source_text_hint)
                candidate = clean_model_output(GoogleTranslator(source=source_lang, target=resolved_target).translate(clean_model_output(source_text_hint)).strip())
                if candidate:
                    translated = candidate
                    actual_provider = "google"
                    requested_provider = self.name
                    fallback_reason = "screenshot_fallback"
            except Exception:
                try:
                    translated_result = self.translate(source_text_hint, target_lang=resolved_target)
                    translated = translated_result.text or translated
                    actual_provider = translated_result.provider
                    requested_provider = translated_result.requested_provider
                    fallback_reason = translated_result.fallback_reason
                except Exception:
                    pass
        self._remember(cache_key, (translated, last_raw_text, actual_provider, requested_provider, fallback_reason))
        return TranslationResult(text=translated, provider=actual_provider, model=model_name, raw_text=last_raw_text, requested_provider=requested_provider, fallback_reason=fallback_reason)

    def transcribe_screenshot(
        self,
        image_parts: Sequence[dict[str, Any]],
        *,
        source_text_hint: str | None = None,
    ) -> TranslationResult:
        if not image_parts:
            raise ValueError("missing_image_context")
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        model_name = self._resolve_model()
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")

        cache_seed = json.dumps(image_parts, sort_keys=True, ensure_ascii=False)
        hint_seed = clean_model_output_multiline(source_text_hint or "").strip()
        cache_key = (
            "gemma-ocr",
            model_name,
            hashlib.sha1(cache_seed.encode("utf-8")).hexdigest(),
            hashlib.sha1(hint_seed.encode("utf-8")).hexdigest() if hint_seed else "",
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            transcription, raw_text = cached
            return TranslationResult(text=str(transcription), provider=self.name, model=model_name, raw_text=raw_text, from_cache=True)

        prompt = (
            "You are an OCR engine.\n"
            "Read every visible line of text in the image exactly as it appears.\n"
            "Do not translate, summarize, or explain.\n"
            "Preserve line breaks when possible.\n"
            "Return plain text only.\n"
            "If the image has no readable text, return an empty string."
        )
        if hint_seed:
            prompt += f"\n\nOCR hint:\n{hint_seed[:1200]}"

        payload = self._request(
            model_name,
            prompt,
            image_parts=image_parts,
            max_output_tokens=2048,
            temperature=0.0,
            response_mime_type="text/plain",
        )
        raw_text = extract_gemma_text(payload)
        transcription = clean_model_output_multiline(raw_text).strip()
        if not transcription:
            raise ValueError("empty_gemma_ocr_response")
        self._remember(cache_key, (transcription, raw_text))
        return TranslationResult(text=transcription, provider=self.name, model=model_name, raw_text=raw_text)

class LocalGemmaProvider(KnowledgePromptContext):
    name = "local_gemma"

    def __init__(
        self,
        *,
        model_path: str = "",
        gemma_prompt: str = "",
        target_lang: str = "zh-TW",
        enabled: bool = False,
        temperature: float = 0.2,
        repeat_penalty: float = 1.15,
    ):
        self.model_path = model_path
        self.target_lang = target_lang
        self.enabled = bool(enabled)
        self.gemma_prompt = (gemma_prompt or "").strip()
        self.temperature = temperature
        self.repeat_penalty = repeat_penalty
        self._llm = None
        self.last_load_error = ""
        self._translation_cache: OrderedDict[Any, Any] = OrderedDict()
        self._context_buffer = deque(maxlen=3)
        self._init_knowledge_prompt_context()
        self._dictionary = load_translation_dictionary()
        self._load_model()

    def update_config(
        self,
        *,
        model_path: str | None = None,
        gemma_prompt: str | None = None,
        target_lang: str | None = None,
        enabled: bool | None = None,
        **kwargs
    ) -> None:
        previous_enabled = self.enabled
        reload_needed = False
        if model_path is not None and model_path != self.model_path:
            self.model_path = model_path
            reload_needed = True
        if gemma_prompt is not None:
            self.gemma_prompt = (gemma_prompt or "").strip()
        if target_lang is not None:
            self.target_lang = (target_lang or "").strip() or self.target_lang
        if enabled is not None:
            self.enabled = bool(enabled)
        if "gemma_enabled" in kwargs and kwargs["gemma_enabled"] is not None:
            self.enabled = bool(kwargs["gemma_enabled"])
        generation_params_changed = False
        if "temperature" in kwargs and kwargs["temperature"] is not None:
            temperature = float(kwargs["temperature"])
            generation_params_changed = generation_params_changed or temperature != self.temperature
            self.temperature = temperature
        if "repeat_penalty" in kwargs and kwargs["repeat_penalty"] is not None:
            repeat_penalty = float(kwargs["repeat_penalty"])
            generation_params_changed = generation_params_changed or repeat_penalty != self.repeat_penalty
            self.repeat_penalty = repeat_penalty
        if generation_params_changed:
            self._translation_cache.clear()
            self._context_buffer.clear()
        if not self.enabled:
            self._release_model()
        elif reload_needed or not previous_enabled:
            if reload_needed:
                self._release_model()
            self._load_model()
    def _release_model(self) -> None:
        llm = self._llm
        self._llm = None
        self._translation_cache.clear()
        self._context_buffer.clear()
        if llm is None:
            return
        closer = getattr(llm, "close", None)
        if not callable(closer):
            return
        try:
            closer()
        except Exception as exc:
            self.last_load_error = f"model_close_failed: {type(exc).__name__}"


    def close(self) -> None:
        self.enabled = False
        self._release_model()


    def unload(self) -> None:
        self.close()


    def _load_model(self):
        if self._llm is not None and self.enabled and self.model_path and os.path.exists(self.model_path):
            return True
        self._release_model()
        if not self.enabled or not self.model_path or not os.path.exists(self.model_path):
            return False
        self.last_load_error = ""
        try:
            # We import locally to avoid requiring it if not enabled
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=2048,
                n_gpu_layers=-1, # Offload all to GPU
                verbose=False
            )
            return True
        except Exception as exc:
            self._llm = None
            self.last_load_error = f"{type(exc).__name__}: {exc}"
            return False

    def load_model(self) -> bool:
        self._load_model()
        return self.available()

    def available(self) -> bool:
        return self.enabled and self._llm is not None

    def _get_cached(self, cache_key: Any):
        cached = self._translation_cache.get(cache_key)
        if cached is not None:
            self._translation_cache.move_to_end(cache_key)
        return cached

    def _remember(self, cache_key: Any, translated_text: Any) -> None:
        self._translation_cache[cache_key] = translated_text
        self._translation_cache.move_to_end(cache_key)
        if len(self._translation_cache) > TRANSLATION_CACHE_LIMIT:
            self._translation_cache.popitem(last=False)

    def _build_prompt(self, text: str, target_lang: str | None = None) -> str:
        resolved_target = target_lang or self.target_lang
        dictionary_hint = build_dictionary_prompt_hint(text, self._dictionary)

        prompt = ""
        for src, tgt, context_target in self._context_buffer:
            if context_target != resolved_target:
                continue
            prompt += f"<start_of_turn>user\nTranslate:\n{src}<end_of_turn>\n<start_of_turn>model\n{tgt}<end_of_turn>\n"

        custom_prompt = "\n\n".join(part for part in (self.gemma_prompt, dictionary_hint) if part)
        raw_prompt = build_gemma_prompt_with_override(text, custom_prompt, resolved_target)
        evidence = self._knowledge_evidence_for_texts((text,), max_chars=1_800)
        raw_prompt = self._prepend_knowledge_evidence(raw_prompt, evidence)
        prompt += f"<start_of_turn>user\n{raw_prompt}<end_of_turn>\n<start_of_turn>model\n"
        return prompt

    def translate_stream(self, text: str, *, target_lang: str = "zh-TW"):
        if not self.available() or not self._llm:
            raise ValueError("local_model_unavailable")
        normalized = clean_model_output_multiline(text).strip() if text else ""
        if not normalized:
            return
        resolved_target = target_lang or self.target_lang

        cache_key = ("local_gemma", self.model_path, normalized, resolved_target, self.gemma_prompt, self.temperature, self.repeat_penalty, self.knowledge_revision_token)
        cached = self._get_cached(cache_key)
        if cached is not None:
            if isinstance(cached, TranslationResult):
                yield cached.text
            else:
                yield str(cached)
            return

        prompt = self._build_prompt(normalized, resolved_target)

        stream = self._llm.create_completion(
            prompt,
            max_tokens=1024,
            temperature=self.temperature,
            repeat_penalty=self.repeat_penalty,
            stream=True
        )

        accumulated = ""
        for chunk in stream:
            chunk_text = chunk["choices"][0].get("text", "")
            if chunk_text:
                accumulated += chunk_text
                yield chunk_text

        final = clean_model_output_multiline(accumulated)
        final = self._apply_post_processing(normalized, final)
        if self._is_bad_translation(normalized, final):
            final = self._fallback_translate(normalized, resolved_target)
            yield f"\n[Fallback] {final}"

        if final:
            self._remember(cache_key, final)
            self._context_buffer.append((normalized, final, resolved_target))

    def translate(
        self,
        text: str,
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> TranslationResult:
        normalized = clean_model_output_multiline(text).strip() if text else ""
        if not normalized:
            return TranslationResult(text="", provider=self.name, model="local")
        resolved_target = target_lang or self.target_lang
        if not self.available() or not self._llm:
            raise ValueError("local_model_unavailable")
        cache_key = (
            "local_gemma",
            self.model_path,
            normalized,
            resolved_target,
            self.gemma_prompt,
            self.temperature,
            self.repeat_penalty,
            self.knowledge_revision_token,
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            if isinstance(cached, TranslationResult):
                return TranslationResult(
                    text=cached.text,
                    provider=cached.provider,
                    model=cached.model,
                    raw_text=cached.raw_text,
                    from_cache=True,
                    requested_provider=cached.requested_provider,
                    fallback_reason=cached.fallback_reason,
                )
            return TranslationResult(text=str(cached), provider=self.name, model="local", from_cache=True)
        prompt = self._build_prompt(normalized, resolved_target)
        response = self._llm.create_completion(
            prompt,
            max_tokens=1024,
            temperature=self.temperature,
            repeat_penalty=self.repeat_penalty,
        )
        raw_text = response["choices"][0]["text"]
        translated = clean_model_output_multiline(raw_text)
        translated = self._apply_post_processing(normalized, translated)
        actual_provider = self.name
        requested_provider = None
        fallback_reason = None
        if self._is_bad_translation(normalized, translated):
            translated = self._fallback_translate(normalized, resolved_target)
            raw_text += " [Fallback]"
            actual_provider = "google"
            requested_provider = self.name
            fallback_reason = "bad_translation"
        if not translated:
            raise ValueError("empty_local_response")
        result = TranslationResult(
            text=translated,
            provider=actual_provider,
            model="local",
            raw_text=raw_text,
            requested_provider=requested_provider,
            fallback_reason=fallback_reason,
        )
        self._remember(cache_key, result)
        self._context_buffer.append((normalized, translated, resolved_target))
        return result

    def _apply_post_processing(self, source: str, translated: str) -> str:
        return append_missing_dictionary_terms(source, translated, self._dictionary)

    def _is_bad_translation(self, source: str, translated: str) -> bool:
        if not translated or len(translated.strip()) == 0:
            return True
        if translated.strip() == source.strip():
            return True
        if "<start_of_turn>" in translated or "<end_of_turn>" in translated:
            return True
        if "Translate:" in translated or "Source text:" in translated:
            return True
        return False

    def _fallback_translate(self, text: str, target_lang: str) -> str:
        try:
            translator = GoogleTranslator(source="auto", target=target_lang or self.target_lang)
            return str(translator.translate(text)).strip()
        except Exception as e:
            raise RuntimeError(f"Fallback translation failed: {e}")


class LocalRequestCancelled(RuntimeError):
    """A local inference request was cancelled before it reached HTTP."""


class _LocalRequestScheduler:
    """Serialize local inference without merging independent image prompts."""

    def __init__(self):
        self._condition = threading.Condition()
        self._next_ticket = 0
        self._serving_ticket = 0
        self._cancelled_tickets: set[int] = set()
        self._closed = False

    def _skip_cancelled_locked(self):
        while self._serving_ticket in self._cancelled_tickets:
            self._cancelled_tickets.remove(self._serving_ticket)
            self._serving_ticket += 1

    def run(self, callback: Callable[[], Any], *, cancel_predicate=None):
        with self._condition:
            if self._closed:
                raise RuntimeError("local_request_scheduler_closed")
            ticket = self._next_ticket
            self._next_ticket += 1
            while ticket != self._serving_ticket:
                if self._closed:
                    raise LocalRequestCancelled("local_request_scheduler_closed")
                if cancel_predicate is not None and cancel_predicate():
                    self._cancelled_tickets.add(ticket)
                    self._condition.notify_all()
                    raise LocalRequestCancelled("local_request_cancelled_before_dispatch")
                self._condition.wait(timeout=0.05)
            if self._closed:
                raise LocalRequestCancelled("local_request_scheduler_closed")
            if cancel_predicate is not None and cancel_predicate():
                self._serving_ticket += 1
                self._skip_cancelled_locked()
                self._condition.notify_all()
                raise LocalRequestCancelled("local_request_cancelled_before_dispatch")

        try:
            return callback()
        finally:
            with self._condition:
                self._serving_ticket += 1
                self._skip_cancelled_locked()
                self._condition.notify_all()

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()


class LocalMultimodalProvider(KnowledgePromptContext):
    name = "local_multimodal"

    def __init__(
        self,
        *,
        base_url: str = "",
        model_name: str = "",
        target_lang: str = "zh-TW",
        enabled: bool = False,
        timeout_seconds: int = 20,
        temperature: float = 0.2,
        repeat_penalty: float = 1.15,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.model_name = (model_name or "").strip()
        self.target_lang = target_lang
        self.enabled = bool(enabled)
        self.timeout_seconds = int(timeout_seconds)
        self.temperature = float(temperature)
        self.repeat_penalty = float(repeat_penalty)
        self._runtime_ready = bool(self.base_url and self.model_name)
        self._dictionary = load_translation_dictionary()
        self._translation_cache: OrderedDict[Any, TranslationResult] = OrderedDict()
        self._last_request_metrics: dict[str, int | float] = {}
        self._request_scheduler = _LocalRequestScheduler()
        self._init_knowledge_prompt_context()

    def available(self) -> bool:
        return self.enabled and self._runtime_ready and bool(self.base_url) and bool(self.model_name)

    def clear_cache(self) -> None:
        """Clear translation results without changing local runtime state."""
        self._translation_cache.clear()

    def close(self) -> None:
        self._request_scheduler.close()
        self._translation_cache.clear()
        self._last_request_metrics = {}

    def get_last_request_metrics(self) -> dict[str, int | float]:
        """Return bounded numeric server timing/token metrics only."""
        return dict(self._last_request_metrics)

    def update_runtime(self, base_url: str, model_name: str, ready: bool) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.model_name = (model_name or "").strip()
        self._runtime_ready = bool(ready and self.base_url and self.model_name)

    def update_generation_config(self, *, temperature: float, repeat_penalty: float) -> None:
        normalized_temperature = float(temperature)
        normalized_repeat_penalty = float(repeat_penalty)
        if (
            normalized_temperature == self.temperature
            and normalized_repeat_penalty == self.repeat_penalty
        ):
            return
        self.temperature = normalized_temperature
        self.repeat_penalty = normalized_repeat_penalty
        self._translation_cache.clear()

    def _inline_part_to_content(self, image_part: dict[str, Any]) -> dict[str, Any]:
        inline_data = image_part.get("inline_data") or {}
        mime_type = inline_data.get("mime_type", "image/png")
        encoded = inline_data.get("data", "")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
        }

    def _build_chat_payload(
        self,
        *,
        prompt: str,
        image_parts: Sequence[dict[str, Any]],
        response_format: str,
        max_tokens: int = 1024,
        temperature: float | None = None,
        repeat_penalty: float | None = None,
    ) -> dict[str, Any]:
        content = [{"type": "text", "text": prompt}]
        content.extend(self._inline_part_to_content(part) for part in image_parts)
        return {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content}],
            "temperature": self.temperature if temperature is None else float(temperature),
            "repeat_penalty": self.repeat_penalty if repeat_penalty is None else float(repeat_penalty),
            "stream": False,
            "max_tokens": max(64, int(max_tokens)),
            "response_format": {"type": response_format},
        }

    def _perform_chat_completion(self, payload: dict[str, Any]) -> str:
        self._last_request_metrics = {}
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        metrics: dict[str, int | float] = {}
        for container_name in ("usage", "timings"):
            container = body.get(container_name)
            if not isinstance(container, Mapping):
                continue
            for key in LOCAL_RUNTIME_METRIC_KEYS:
                value = container.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                if not math.isfinite(float(value)) or value < 0:
                    continue
                metrics[key] = value
        self._last_request_metrics = metrics
        choice = body["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("truncated_local_multimodal_response")
        return choice["message"]["content"]

    def _request_chat_completion(self, payload: dict[str, Any], *, cancel_predicate=None) -> str:
        return self._request_scheduler.run(
            lambda: self._perform_chat_completion(payload),
            cancel_predicate=cancel_predicate,
        )

    def _parse_segmented_response(self, raw_text: str, expected_count: int) -> list[str]:
        translated = parse_segmented_translation_json(raw_text, expected_count)
        if len(translated) != expected_count:
            translated = split_translated_lines(clean_model_output(raw_text), expected_count)
        if len(translated) != expected_count:
            raise ValueError("empty_local_multimodal_response")
        return translated

    def translate(
        self,
        text: str,
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> TranslationResult:
        if not self.available():
            raise ValueError("local_multimodal_unavailable")
        normalized = clean_model_output_multiline(text).strip() if text else ""
        if not normalized:
            return TranslationResult(text="", provider=self.name, model=self.model_name)
        resolved_target = target_lang or self.target_lang
        cache_key = (
            self.base_url,
            self.model_name,
            normalized,
            resolved_target,
            self.temperature,
            self.repeat_penalty,
            self.knowledge_revision_token,
        )
        cached = self._translation_cache.get(cache_key)
        if cached is not None:
            self._translation_cache.move_to_end(cache_key)
            return TranslationResult(
                text=cached.text,
                provider=self.name,
                model=self.model_name,
                raw_text=cached.raw_text,
                from_cache=True,
            )

        dictionary_hint = build_dictionary_prompt_hint(normalized, self._dictionary)
        prompt = build_gemma_prompt_with_override(
            normalized,
            dictionary_hint,
            resolved_target,
            self.model_name,
        )
        evidence = self._knowledge_evidence_for_texts((normalized,), max_chars=1_800)
        prompt = self._prepend_knowledge_evidence(prompt, evidence)
        raw_text = self._request_chat_completion(
            self._build_chat_payload(
                prompt=prompt,
                image_parts=(),
                response_format="text",
                max_tokens=512,
            )
        )
        translated = clean_model_output_multiline(raw_text).strip()
        if not translated:
            raise ValueError("empty_local_multimodal_response")
        result = TranslationResult(
            text=translated,
            provider=self.name,
            model=self.model_name,
            raw_text=raw_text,
        )
        self._translation_cache[cache_key] = result
        self._translation_cache.move_to_end(cache_key)
        if len(self._translation_cache) > TRANSLATION_CACHE_LIMIT:
            self._translation_cache.popitem(last=False)
        return result
    def translate_multimodal(self, texts: Sequence[str], image_parts: Sequence[dict[str, Any]], *, target_lang: str = "zh-TW") -> list[TranslationResult]:
        if len(texts) > LOCAL_MULTIMODAL_BATCH_SIZE:
            translated: list[TranslationResult] = []
            for start in range(0, len(texts), LOCAL_MULTIMODAL_BATCH_SIZE):
                translated.extend(
                    self.translate_multimodal(
                        texts[start:start + LOCAL_MULTIMODAL_BATCH_SIZE],
                        image_parts,
                        target_lang=target_lang,
                    )
                )
            return translated
        resolved_target = target_lang or self.target_lang
        dictionary_hint = build_dictionary_prompt_hint(texts, self._dictionary)
        base_prompt = build_gemma_multimodal_prompt(texts, target_lang=resolved_target)
        prompt = f"{dictionary_hint}\n\n{base_prompt}" if dictionary_hint else base_prompt
        evidence = self._knowledge_evidence_for_texts(texts, max_chars=2_400)
        prompt = self._prepend_knowledge_evidence(prompt, evidence)
        payload = self._build_chat_payload(
            prompt=prompt,
            image_parts=image_parts,
            response_format="json_object",
            max_tokens=1024,
        )
        try:
            raw_text = self._request_chat_completion(payload)
        except error.HTTPError as exc:
            # llama-server builds without JSON response-format support still accept the same multimodal request as text.
            if exc.code != 400:
                raise
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            body_lower = body.lower()
            format_error = not body or any(
                marker in body_lower
                for marker in ("response format", "json_object", "structured output", "json mode")
            )
            if not format_error:
                raise
            payload["response_format"] = {"type": "text"}
            raw_text = self._request_chat_completion(payload)
        translated = self._parse_segmented_response(raw_text, len(texts))
        return [TranslationResult(text=item, provider=self.name, model=self.model_name, raw_text=raw_text) for item in translated]

    def interpret_regions(
        self,
        image_parts: Sequence[dict[str, Any]],
        hints: Sequence[dict[str, Any]],
        *,
        image_width: int,
        image_height: int,
        target_lang: str = "zh-TW",
        cancel_predicate=None,
    ) -> list[VisionRegionResult]:
        if not image_parts:
            raise ValueError("missing_image_context")
        if not hints:
            raise ValueError("missing_region_hints")

        resolved_target = target_lang or self.target_lang
        hint_texts = tuple(str(hint.get("text") or "") for hint in hints)
        dictionary_hint = build_dictionary_prompt_hint(hint_texts, self._dictionary)
        evidence = self._knowledge_evidence_for_texts(hint_texts, max_chars=1_800)
        knowledge_context = "  ".join(
            part for part in (dictionary_hint, evidence) if part
        )
        prompt = build_region_vision_prompt(
            hints,
            image_width=image_width,
            image_height=image_height,
            target_lang=resolved_target,
            knowledge_context=knowledge_context,
        )
        allowed_ids = [hint["id"] for hint in hints]
        payload = self._build_chat_payload(
            prompt=prompt,
            image_parts=image_parts,
            response_format="json_object",
            max_tokens=min(2048, max(384, len(hints) * 160 + 128)),
        )
        request_kwargs = (
            {"cancel_predicate": cancel_predicate}
            if cancel_predicate is not None
            else {}
        )
        try:
            raw_text = self._request_chat_completion(payload, **request_kwargs)
        except error.HTTPError as exc:
            if exc.code != 400:
                raise
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            body_lower = body.lower()
            format_error = not body or any(
                marker in body_lower
                for marker in (
                    "response format",
                    "json_object",
                    "structured output",
                    "json mode",
                )
            )
            if not format_error:
                raise
            payload["response_format"] = {"type": "text"}
            raw_text = self._request_chat_completion(payload, **request_kwargs)
        results = parse_region_vision_response(
            raw_text,
            allowed_ids=allowed_ids,
        )
        if not results:
            raise ValueError("empty_region_vision_response")
        return results

    @staticmethod
    def _has_degenerate_repetition(text: str) -> bool:
        lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
        if len(lines) >= 8:
            counts = Counter(lines)
            most_common = max(counts.values(), default=0)
            if most_common >= 4 and (len(counts) / len(lines)) < 0.45:
                return True

        compact = re.sub(r"\s+", "", str(text or ""))
        max_unit = min(32, len(compact) // 4)
        for unit_size in range(1, max_unit + 1):
            if len(compact) % unit_size:
                continue
            repeats = len(compact) // unit_size
            unit = compact[:unit_size]
            if repeats >= 4 and unit * repeats == compact:
                return True
        return False

    def _parse_transcription_response(self, raw_text: str) -> str:
        transcription = clean_model_output_multiline(raw_text).strip()
        if not transcription:
            raise ValueError("empty_local_multimodal_ocr_response")
        if self._has_degenerate_repetition(transcription):
            raise ValueError("degenerate_local_multimodal_ocr_response")
        return transcription

    def transcribe_screenshot(
        self,
        image_parts: Sequence[dict[str, Any]],
        *,
        source_text_hint: str | None = None,
        ocr_prompt: str | None = None,
    ) -> TranslationResult:
        prompt = (ocr_prompt or "").strip() or "You are an OCR engine. Read every visible line exactly as it appears. Return plain text only."
        if source_text_hint:
            prompt += (
                "\n\nThe OCR hint below may contain recognition errors. "
                "Use the image as the source of truth and return one final transcription."
                f"\n\nOCR hint:\n{source_text_hint[:1200]}"
            )
        raw_text = self._request_chat_completion(
            self._build_chat_payload(
                prompt=prompt,
                image_parts=image_parts,
                response_format="text",
                max_tokens=384,
                temperature=LOCAL_MULTIMODAL_OCR_TEMPERATURE,
                repeat_penalty=LOCAL_MULTIMODAL_OCR_REPEAT_PENALTY,
            )
        )
        return TranslationResult(text=self._parse_transcription_response(raw_text), provider=self.name, model=self.model_name, raw_text=raw_text)

    def translate_screenshot(self, image_parts: Sequence[dict[str, Any]], *, target_lang: str = "zh-TW", source_text_hint: str | None = None, debug_log=None) -> TranslationResult:
        resolved_target = target_lang or self.target_lang
        dictionary_hint = build_dictionary_prompt_hint(source_text_hint or "", self._dictionary)
        prompt = build_screenshot_prompt_with_override(source_text_hint, None, custom_prompt=dictionary_hint, target_lang=resolved_target)
        evidence = self._knowledge_evidence_for_texts((source_text_hint or "",), max_chars=1_800)
        prompt = self._prepend_knowledge_evidence(prompt, evidence)
        raw_text = self._request_chat_completion(
            self._build_chat_payload(prompt=prompt, image_parts=image_parts, response_format="text", max_tokens=1024)
        )
        translated = clean_screenshot_translation_output(
            raw_text, target_lang=resolved_target
        )
        if not translated:
            raise ValueError("empty_local_multimodal_screenshot_response")
        return TranslationResult(text=translated, provider=self.name, model=self.model_name, raw_text=raw_text)
