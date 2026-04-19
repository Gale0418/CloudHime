from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class TranslationResult:
    text: str
    provider: str
    model: str | None = None
    raw_text: str | None = None
    from_cache: bool = False


class TranslationProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def translate(
        self,
        text: str,
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> TranslationResult:
        ...

    def translate_batch(
        self,
        texts: Sequence[str],
        *,
        source_lang: str = "auto",
        target_lang: str = "zh-TW",
    ) -> list[TranslationResult]:
        ...
