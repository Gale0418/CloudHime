"""Bounded HTTP transport for deep-translator's Google HTML translator.

The parsing and retry behavior follows the upstream GoogleTranslator adapter
(Copyright (C) 2020 Nidhal Baccouri, MIT licensed):
https://github.com/nidhaloff/deep-translator/blob/v1.11.4/deep_translator/google.py
"""

from __future__ import annotations

import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator as _DeepTranslatorGoogleTranslator
from deep_translator.exceptions import RequestError, TooManyRequests, TranslationNotFound
from deep_translator.validate import is_empty, is_input_valid, request_failed


REQUEST_TIMEOUT = (5, 20)
MAX_HTML_BYTES = 1024 * 1024
MAX_ELAPSED_SECONDS = 30.0
READ_CHUNK_BYTES = 8192


class GoogleTranslationResponseLimitError(RequestError):
    """Raised when Google returns an HTML response beyond the configured budget."""


class GoogleTranslator(_DeepTranslatorGoogleTranslator):
    """GoogleTranslator with scoped time, response-size, and cleanup bounds."""

    def __init__(
        self,
        source: str = "auto",
        target: str = "en",
        proxies: Optional[dict] = None,
        **kwargs,
    ) -> None:
        self.proxies = proxies
        super().__init__(source=source, target=target, proxies=proxies, **kwargs)
        self._alt_element_query = {"class": "result-container"}

    def translate(self, text: str, **kwargs) -> str:
        if is_input_valid(text, max_chars=5000):
            text = text.strip()
            if self._same_source_target() or is_empty(text):
                return text

            self._url_params["tl"] = self._target
            self._url_params["sl"] = self._source
            if self.payload_key:
                self._url_params[self.payload_key] = text

            started = time.monotonic()
            with requests.get(
                self._base_url,
                params=self._url_params,
                proxies=self.proxies,
                timeout=REQUEST_TIMEOUT,
                stream=True,
            ) as response:
                if response.status_code == 429:
                    raise TooManyRequests()
                if request_failed(status_code=response.status_code):
                    raise RequestError()

                body = bytearray()
                for chunk in response.iter_content(chunk_size=READ_CHUNK_BYTES):
                    if time.monotonic() - started > MAX_ELAPSED_SECONDS:
                        raise RequestError("Google Translate response exceeded elapsed-time budget")
                    if not chunk:
                        continue
                    if len(body) + len(chunk) > MAX_HTML_BYTES:
                        raise GoogleTranslationResponseLimitError(
                            "Google Translate response exceeded 1 MiB"
                        )
                    body.extend(chunk)

                if time.monotonic() - started > MAX_ELAPSED_SECONDS:
                    raise RequestError("Google Translate response exceeded elapsed-time budget")

                encoding = response.encoding or "utf-8"
                html = bytes(body).decode(encoding, errors="replace")

            soup = BeautifulSoup(html, "html.parser")
            element = soup.find(self._element_tag, self._element_query)
            if not element:
                element = soup.find(self._element_tag, self._alt_element_query)
                if not element:
                    raise TranslationNotFound(text)

            translated = element.get_text(strip=True)
            if translated == text.strip():
                to_translate_alpha = "".join(ch for ch in text.strip() if ch.isalnum())
                translated_alpha = "".join(ch for ch in translated if ch.isalnum())
                if to_translate_alpha and translated_alpha and to_translate_alpha == translated_alpha:
                    self._url_params["tl"] = self._target
                    if "hl" not in self._url_params:
                        return text.strip()
                    del self._url_params["hl"]
                    return self.translate(text)
            return translated

    def translate_file(self, path: str, **kwargs) -> str:
        return self._translate_file(path, **kwargs)

    def translate_batch(self, batch: List[str], **kwargs) -> List[str]:
        return self._translate_batch(batch, **kwargs)
