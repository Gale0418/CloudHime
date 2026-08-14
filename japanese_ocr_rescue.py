"""Optional Japanese Hybrid OCR rescue helpers for repeatable benchmarks.

The module intentionally contains no eager import of meikiocr. The benchmark can
therefore keep its default path independent from the optional OCR package.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Any, Callable, Mapping, Sequence


_LOW_CONFIDENCE = 0.5
_MIN_MEAN_CONFIDENCE = 0.75
_MAX_LOW_CONFIDENCE_RATIO = 0.25
_MIN_KANA_RATIO = 0.25
_MIN_WIDE_ASPECT_RATIO = 3.0
_MIN_PORTRAIT_ASPECT_RATIO = 0.7
_MAX_PORTRAIT_ASPECT_RATIO = 0.75


class MeikiOCRUnavailable(RuntimeError):
    """Raised only when the optional MeikiOCR backend cannot be loaded."""


@dataclass(frozen=True)
class MeikiCharacter:
    """One MeikiOCR character and its recognition confidence."""

    text: str
    confidence: float


@dataclass(frozen=True)
class MeikiCandidate:
    """Normalized MeikiOCR candidate with character-level evidence."""

    text: str
    characters: tuple[MeikiCharacter, ...]

    @property
    def mean_confidence(self) -> float:
        if not self.characters:
            return 0.0
        return sum(character.confidence for character in self.characters) / len(self.characters)

    @property
    def low_confidence_positions(self) -> tuple[int, ...]:
        return tuple(
            index
            for index, character in enumerate(self.characters, start=1)
            if character.confidence < _LOW_CONFIDENCE
        )

    @property
    def low_confidence_ratio(self) -> float:
        if not self.characters:
            return 0.0
        return len(self.low_confidence_positions) / len(self.characters)


@dataclass(frozen=True)
class RescueDecision:
    """Pure result of comparing a baseline and a second VLM transcription."""

    adopted: bool
    selected_text: str
    trusted_text: str
    first_similarity: float
    second_similarity: float
    first_candidate_similarity: float = 0.0
    second_candidate_similarity: float = 0.0

def normalize_ocr_text(value: Any) -> str:
    """Normalize text for conservative OCR similarity comparisons."""

    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+", "", normalized)


def normalized_similarity(left: Any, right: Any) -> float:
    return SequenceMatcher(None, normalize_ocr_text(left), normalize_ocr_text(right)).ratio()


def japanese_kana_ratio(text: Any) -> float:
    """Return kana characters divided by non-whitespace characters."""

    value = str(text or "")
    considered = [character for character in value if not character.isspace()]
    if not considered:
        return 0.0
    kana_count = sum(
        "\u3040" <= character <= "\u309f" or "\u30a0" <= character <= "\u30ff"
        for character in considered
    )
    return kana_count / len(considered)


def rescue_gate(
    first_text: Any,
    *,
    image_width: int,
    image_height: int,
    min_kana_ratio: float = _MIN_KANA_RATIO,
    min_aspect_ratio: float = _MIN_PORTRAIT_ASPECT_RATIO,
) -> bool:
    """Return whether the optional rescue is worth initializing.

    Japanese manga pages are commonly portrait-oriented, while the original
    rescue path targeted wide subtitle strips. Keep both shapes explicit so a
    square or excessively narrow image does not incur a second model request.
    """

    if image_width <= 0 or image_height <= 0:
        return False
    aspect_ratio = image_width / image_height
    portrait_page = float(min_aspect_ratio) <= aspect_ratio <= _MAX_PORTRAIT_ASPECT_RATIO
    wide_text_strip = aspect_ratio >= _MIN_WIDE_ASPECT_RATIO
    return japanese_kana_ratio(first_text) >= float(min_kana_ratio) and (
        portrait_page or wide_text_strip
    )


def candidate_from_meiki_results(results: Any) -> MeikiCandidate:
    """Convert MeikiOCR line dictionaries into a testable candidate.

    MeikiOCR returns lines with text and chars entries. A mapping is accepted as
    a one-line result to keep fakes and small integrations simple.
    """

    if isinstance(results, Mapping):
        lines: list[Any] = [results]
    elif isinstance(results, Sequence) and not isinstance(results, (str, bytes, bytearray)):
        lines = list(results)
    else:
        lines = []

    text_lines: list[str] = []
    characters: list[MeikiCharacter] = []
    for line in lines:
        if not isinstance(line, Mapping):
            continue
        line_text = str(line.get("text") or "")
        if line_text:
            text_lines.append(line_text)
        raw_chars = line.get("chars") or []
        if not isinstance(raw_chars, Sequence) or isinstance(raw_chars, (str, bytes, bytearray)):
            continue
        for raw_char in raw_chars:
            if not isinstance(raw_char, Mapping):
                continue
            char_text = raw_char.get("char", raw_char.get("text", ""))
            if char_text is None:
                char_text = ""
            confidence = raw_char.get("conf", raw_char.get("confidence", raw_char.get("score")))
            if confidence is None:
                continue
            try:
                characters.append(MeikiCharacter(str(char_text), float(confidence)))
            except (TypeError, ValueError):
                continue

    text = "\n".join(text_lines)
    if not text and characters:
        text = "".join(character.text for character in characters)
    return MeikiCandidate(text=text, characters=tuple(characters))


def is_usable_meiki_candidate(
    candidate: MeikiCandidate,
    first_text: Any,
    *,
    min_mean_confidence: float = _MIN_MEAN_CONFIDENCE,
    max_low_confidence_ratio: float = _MAX_LOW_CONFIDENCE_RATIO,
    max_similarity: float = 0.95,
) -> bool:
    """Apply the strict candidate rules supplied for the rescue benchmark."""

    return bool(
        candidate.text
        and candidate.characters
        and candidate.mean_confidence >= float(min_mean_confidence)
        and 0.0 < candidate.low_confidence_ratio <= float(max_low_confidence_ratio)
        and normalized_similarity(first_text, candidate.text) < float(max_similarity)
    )


def trusted_text(candidate: MeikiCandidate) -> str:
    """Remove Meiki low-confidence characters before the VLM comparison."""

    low_positions = set(candidate.low_confidence_positions)
    if len(candidate.text) == len(candidate.characters):
        return "".join(
            character
            for index, character in enumerate(candidate.text, start=1)
            if index not in low_positions
        )
    return "".join(
        character.text
        for index, character in enumerate(candidate.characters, start=1)
        if index not in low_positions
    )


def build_verification_hint(candidate: MeikiCandidate) -> str:
    """Build a prompt hint naming every uncertain character position."""

    details = ", ".join(
        f"position {position}={candidate.characters[position - 1].text!r}"
        for position in candidate.low_confidence_positions
    )
    return (
        f"MeikiOCR candidate: {candidate.text}\n"
        "Low-confidence characters (verify against the image): "
        f"{details}"
    )


def decide_rescue_text(first_text: Any, second_text: Any, candidate: MeikiCandidate) -> RescueDecision:
    """Adopt second VLM output only on a strict trusted-text improvement."""

    trusted = trusted_text(candidate)
    first_score = normalized_similarity(first_text, trusted)
    second_score = normalized_similarity(second_text, trusted)
    first_candidate_score = normalized_similarity(first_text, candidate.text)
    second_candidate_score = normalized_similarity(second_text, candidate.text)
    adopted = (
        second_score > first_score
        and second_candidate_score >= first_candidate_score
    )
    return RescueDecision(
        adopted=adopted,
        selected_text=str(second_text if adopted else first_text),
        trusted_text=trusted,
        first_similarity=first_score,
        second_similarity=second_score,
        first_candidate_similarity=first_candidate_score,
        second_candidate_similarity=second_candidate_score,
    )


def load_meiki_ocr(factory: Callable[..., Any] | None = None) -> Any:
    """Lazily construct MeikiOCR on CPU, or raise a clear optional error."""

    if factory is not None:
        return factory(provider="CPUExecutionProvider")
    try:
        from meikiocr import MeikiOCR
    except ImportError as exc:
        raise MeikiOCRUnavailable(
            "japanese rescue requested but optional package 'meikiocr' is not installed"
        ) from exc
    try:
        return MeikiOCR(provider="CPUExecutionProvider")
    except Exception as exc:
        raise MeikiOCRUnavailable(f"failed to initialize meikiocr: {exc}") from exc


def run_meiki_ocr(ocr: Any, image: Any) -> MeikiCandidate:
    return candidate_from_meiki_results(ocr.run_ocr(image))
