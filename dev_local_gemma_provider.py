"""Development-only in-process Gemma compatibility provider.

Production CloudHime inference uses the bundled llama-server HTTP runtime.
This module remains available only for optional compatibility tests and local
developer experiments that explicitly install requirements-llama-dev.txt.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict, deque
from typing import Any

from deep_translator import GoogleTranslator

from knowledge_prompt_context import KnowledgePromptContext
from translation_contracts import TranslationResult
from translation_helpers import (
    append_missing_dictionary_terms,
    build_dictionary_prompt_hint,
    build_gemma_prompt_with_override,
    clean_model_output_multiline,
    load_translation_dictionary,
)
from translation_providers import TRANSLATION_CACHE_LIMIT


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
        self.last_stream_result: TranslationResult | None = None
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

    def translate_stream(self, text: str, *, target_lang: str | None = None):
        self.last_stream_result = None
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
                self.last_stream_result = cached
                yield cached.text
            else:
                self.last_stream_result = TranslationResult(
                    text=str(cached), provider=self.name, model="local", from_cache=True
                )
                yield str(cached)
            return

        prompt = self._build_prompt(normalized, resolved_target)
        stream = self._llm.create_completion(
            prompt,
            max_tokens=1024,
            temperature=self.temperature,
            repeat_penalty=self.repeat_penalty,
            stream=True,
        )

        accumulated = ""
        for chunk in stream:
            chunk_text = chunk["choices"][0].get("text", "")
            if chunk_text:
                accumulated += chunk_text

        final = clean_model_output_multiline(accumulated)
        final = self._apply_post_processing(normalized, final)
        if self._is_bad_translation(normalized, final):
            fallback_text = self._fallback_translate(normalized, resolved_target)
            result = TranslationResult(
                text=fallback_text,
                provider="google",
                model="local",
                raw_text=f"{accumulated} [Fallback]",
                requested_provider=self.name,
                fallback_reason="bad_translation",
            )
            self._remember(cache_key, result)
            self.last_stream_result = result
            self._context_buffer.append((normalized, fallback_text, resolved_target))
            yield fallback_text
            return

        if final:
            result = TranslationResult(
                text=final,
                provider=self.name,
                model="local",
                raw_text=accumulated,
            )
            self._remember(cache_key, result)
            self.last_stream_result = result
            self._context_buffer.append((normalized, final, resolved_target))
            yield final
    def translate(
        self,
        text: str,
        *,
        source_lang: str = "auto",
        target_lang: str | None = None,
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
