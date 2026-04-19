from __future__ import annotations

import json
import hashlib
import difflib
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Sequence
from urllib import error, request

from deep_translator import GoogleTranslator

from translation_contracts import TranslationProvider, TranslationResult
from translation_helpers import (
    build_gemma_prompt_conservative,
    build_gemma_multimodal_prompt,
    clean_model_output,
    clean_model_output_multiline,
    build_gemma_screenshot_prompt_v2,
    clean_screenshot_translation_output,
    is_valid_screenshot_translation,
    detect_source_language,
    extract_gemma_text,
    parse_segmented_translation_json,
    split_translated_lines,
)

GOOGLE_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMMA_MODEL = "gemma-3-27b-it"
SUPPORTED_GEMMA_MODEL_NAMES = ("gemma-3-27b-it", "gemma-4-31b-it")
GEMMA_RATE_LIMIT_WINDOW_SEC = 60
GEMMA_RATE_LIMIT_MAX_CALLS = 15
TRANSLATION_CACHE_LIMIT = 512


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
        self._translators: dict[str, GoogleTranslator] = {}
        self._translation_cache: OrderedDict[Any, Any] = OrderedDict()

    def set_target_lang(self, target_lang: str) -> None:
        target_lang = (target_lang or "").strip() or "zh-TW"
        if target_lang != self.target_lang:
            self.target_lang = target_lang
            self._translators.clear()

    def available(self) -> bool:
        return True

    def _get_translator(self, source_lang: str) -> GoogleTranslator:
        translator = self._translators.get(source_lang)
        if translator is None:
            translator = GoogleTranslator(source=source_lang, target=self.target_lang)
            self._translators[source_lang] = translator
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
        normalized = clean_model_output(text).strip() if text else ""
        if not normalized:
            return TranslationResult(text="", provider=self.name)
        source_lang = source_lang if source_lang != "auto" else detect_source_language(normalized)
        cache_key = (source_lang, normalized, target_lang or self.target_lang)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return TranslationResult(text=str(cached), provider=self.name, from_cache=True)
        translator = self._get_translator(source_lang)
        translated = translator.translate(normalized).strip()
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

            cache_key = ("google-batch", batch_source_lang, tuple(group_texts), target_lang or self.target_lang)
            batch_result = self._get_cached(cache_key)
            if batch_result is None:
                translator = self._get_translator(batch_source_lang)
                combined_source = "\n".join(group_texts)
                combined_translated = translator.translate(combined_source).strip()
                batch_result = split_translated_lines(combined_translated, len(group_texts))
                if len(batch_result) != len(group_texts):
                    return []
                self._remember(cache_key, batch_result)
            for offset, line in enumerate(batch_result):
                translated[group_start + offset] = TranslationResult(text=line, provider=self.name)
                self._remember((batch_source_lang, group_texts[offset], target_lang or self.target_lang), line)

        return [item for item in translated if item is not None]


class GemmaTranslationProvider:
    name = "gemma"

    def __init__(
        self,
        *,
        google_api_key: str = "",
        gemma_model: str = DEFAULT_GEMMA_MODEL,
        target_lang: str = "zh-TW",
        gemma_enabled: bool = False,
        auto_switch_enabled: bool = False,
        supported_models: Sequence[str] = SUPPORTED_GEMMA_MODEL_NAMES,
    ):
        self.google_api_key = (google_api_key or "").strip()
        self.target_lang = target_lang
        self.enabled = bool(gemma_enabled)
        self.auto_switch_enabled = bool(auto_switch_enabled)
        self.supported_models = tuple(supported_models) if supported_models else SUPPORTED_GEMMA_MODEL_NAMES
        self.gemma_model = self.normalize_gemma_model(gemma_model)
        self._translation_cache: OrderedDict[Any, Any] = OrderedDict()
        self._call_timestamps: dict[str, list[float]] = {name: [] for name in self.supported_models}

    def update_config(
        self,
        *,
        google_api_key: str | None = None,
        gemma_model: str | None = None,
        target_lang: str | None = None,
        gemma_enabled: bool | None = None,
        auto_switch_enabled: bool | None = None,
        supported_models: Sequence[str] | None = None,
    ) -> None:
        if google_api_key is not None:
            self.google_api_key = (google_api_key or "").strip()
        if gemma_model is not None:
            self.gemma_model = self.normalize_gemma_model(gemma_model)
        if target_lang is not None:
            self.target_lang = (target_lang or "").strip() or self.target_lang
        if gemma_enabled is not None:
            self.enabled = bool(gemma_enabled)
        if auto_switch_enabled is not None:
            self.auto_switch_enabled = bool(auto_switch_enabled)
        if supported_models is not None:
            new_supported_models = tuple(supported_models) if supported_models else SUPPORTED_GEMMA_MODEL_NAMES
            if new_supported_models != self.supported_models:
                previous_timestamps = self._call_timestamps
                self.supported_models = new_supported_models
                self._call_timestamps = {
                    name: list(previous_timestamps.get(name, []))
                    for name in self.supported_models
                }

    def available(self) -> bool:
        return bool(self.google_api_key and self.enabled)

    def normalize_gemma_model(self, model_name: str | None) -> str:
        model_name = (model_name or "").strip()
        return model_name if model_name in self.supported_models else DEFAULT_GEMMA_MODEL

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

    def _normalize_compare_text(self, text: Any) -> str:
        normalized = clean_model_output(text)
        if not normalized:
            return ""
        normalized = re.sub(r"[\s\(\)（）\[\]【】「」『』《》<>“”\"'、，。！？!?…：;；\-—~]+", "", normalized)
        return normalized.lower()

    def _should_fallback_to_text_translation(self, source_text_hint: Any, translated_text: Any) -> bool:
        if re.search(r"[\u3040-\u30ff]", str(translated_text or "")):
            return True
        source_norm = self._normalize_compare_text(source_text_hint)
        translated_norm = self._normalize_compare_text(translated_text)
        if not source_norm or not translated_norm:
            return False
        if source_norm == translated_norm:
            return True
        similarity = difflib.SequenceMatcher(None, source_norm, translated_norm).ratio()
        return similarity >= 0.82

    def _prune_timestamps(self, model_name: str) -> None:
        cutoff = time.monotonic() - GEMMA_RATE_LIMIT_WINDOW_SEC
        self._call_timestamps[model_name] = [ts for ts in self._call_timestamps.get(model_name, []) if ts >= cutoff]

    def _can_call(self, model_name: str) -> bool:
        self._prune_timestamps(model_name)
        return len(self._call_timestamps.get(model_name, [])) < GEMMA_RATE_LIMIT_MAX_CALLS

    def _record_call(self, model_name: str) -> None:
        self._prune_timestamps(model_name)
        self._call_timestamps.setdefault(model_name, []).append(time.monotonic())

    def _resolve_model(self) -> str:
        model = self.normalize_gemma_model(self.gemma_model)
        if self._can_call(model):
            return model
        if self.auto_switch_enabled:
            for candidate in self.supported_models:
                if candidate == model:
                    continue
                if self._can_call(candidate):
                    self.gemma_model = candidate
                    return candidate
        return model

    def _request(self, model_name: str, prompt: str, *, image_parts: Sequence[dict[str, Any]] | None = None, max_output_tokens: int = 1024, temperature: float = 0.2, response_mime_type: str = "text/plain") -> dict[str, Any]:
        req_body = {
            "contents": [
                {
                    "parts": ([*image_parts] if image_parts else []) + [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "topP": 0.9,
                "topK": 32,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": response_mime_type,
            },
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
        with request.urlopen(req, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))

    def translate(
        self,
        text: str,
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> TranslationResult:
        normalized = clean_model_output(text).strip() if text else ""
        if not normalized:
            return TranslationResult(text="", provider=self.name, model=self.gemma_model)
        if not self.google_api_key:
            raise ValueError("missing_google_api_key")
        model_name = self._resolve_model()
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")
        cache_key = ("gemma", model_name, normalized, target_lang or self.target_lang)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return TranslationResult(text=str(cached), provider=self.name, model=model_name, from_cache=True)
        payload = self._request(model_name, build_gemma_prompt_conservative(normalized), max_output_tokens=1024, temperature=0.2)
        self._record_call(model_name)
        translated = clean_model_output(extract_gemma_text(payload))
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
        model_name = self._resolve_model()
        if not self._can_call(model_name):
            raise ValueError("gemma_rate_limited")
        normalized_texts = tuple(clean_model_output(text).strip() if text else "" for text in texts)
        cache_key = ("gemma-mm", model_name, normalized_texts, target_lang or self.target_lang)
        cached = self._get_cached(cache_key)
        if cached is not None:
            translated_items, raw_text = cached
            return [
                TranslationResult(text=item, provider=self.name, model=model_name, raw_text=raw_text, from_cache=True)
                for item in translated_items
            ]

        payload = self._request(
            model_name,
            build_gemma_multimodal_prompt(texts),
            image_parts=image_parts,
            max_output_tokens=2048,
            temperature=0.1,
        )
        self._record_call(model_name)
        raw_text = extract_gemma_text(payload)
        translated = parse_segmented_translation_json(raw_text, len(texts))
        if not translated:
            translated = split_translated_lines(clean_model_output(raw_text), len(texts))
        if len(translated) != len(texts):
            raise ValueError("empty_gemma_multimodal_response")
        self._remember(cache_key, (translated, raw_text))
        return [TranslationResult(text=line, provider=self.name, model=model_name, raw_text=raw_text) for line in translated]

    def translate_screenshot(
        self,
        image_parts: Sequence[dict[str, Any]],
        *,
        target_lang: str = "zh-TW",
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
        cache_key = ("gemma-screenshot", model_name, hashlib.sha1(cache_seed.encode("utf-8")).hexdigest(), target_lang or self.target_lang)
        cached = self._get_cached(cache_key)
        if cached is not None:
            translated_text, raw_text = cached
            return TranslationResult(text=str(translated_text), provider=self.name, model=model_name, raw_text=raw_text, from_cache=True)

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
            prompt = build_gemma_screenshot_prompt_v2(retry_note)
            payload = self._request(
                model_name,
                prompt,
                image_parts=image_parts,
                max_output_tokens=2048,
                temperature=0.0 if attempt_index else 0.1,
                response_mime_type="application/json",
            )
            self._record_call(model_name)
            last_raw_text = extract_gemma_text(payload)
            translated = clean_screenshot_translation_output(last_raw_text)
            if is_valid_screenshot_translation(translated):
                break
            translated = ""
        if not translated:
            raise ValueError("empty_gemma_screenshot_response")
        if source_text_hint and self._should_fallback_to_text_translation(source_text_hint, translated):
            try:
                source_lang = detect_source_language(source_text_hint)
                translator = GoogleTranslator(source=source_lang, target=target_lang or self.target_lang)
                translated = clean_model_output(translator.translate(clean_model_output(source_text_hint)).strip()) or translated
            except Exception:
                translated = self.translate(source_text_hint, target_lang=target_lang).text or translated
        self._remember(cache_key, (translated, last_raw_text))
        return TranslationResult(text=translated, provider=self.name, model=model_name, raw_text=last_raw_text)
