"""Bounded OCR preprocessing policies shared by benchmark and production rescue."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

import cv2
import numpy as np


GRAYSCALE_PREPROCESS: Final[str] = "gray"
FAST_PREPROCESS: Final[str] = "binary_invert"
BOUNDED_RESCUE_PREPROCESSES: Final[tuple[str, ...]] = (
    "adaptive_invert",
    "clahe_otsu_invert",
)
SUPPORTED_PREPROCESSES: Final[frozenset[str]] = frozenset(
    (GRAYSCALE_PREPROCESS, FAST_PREPROCESS, *BOUNDED_RESCUE_PREPROCESSES)
)
MAX_RESCUE_PREPROCESSES: Final[int] = len(BOUNDED_RESCUE_PREPROCESSES)


def normalize_preprocess_candidates(
    candidates: Iterable[str] | None,
) -> tuple[str, ...]:
    """Normalize a strict, bounded preprocessing candidate list."""
    if candidates is None:
        return (FAST_PREPROCESS,)

    normalized: list[str] = []
    for candidate in candidates:
        name = str(candidate).strip().lower()
        if name not in SUPPORTED_PREPROCESSES:
            raise ValueError(f"unknown OCR preprocess: {name}")
        if name not in normalized:
            normalized.append(name)

    if len(normalized) > MAX_RESCUE_PREPROCESSES:
        raise ValueError("OCR preprocess candidate budget exceeded")
    return tuple(normalized)


def apply_ocr_preprocess(
    gray: np.ndarray,
    *,
    threshold: int,
    preprocess: str,
) -> np.ndarray:
    """Return a BGR OCR image for one bounded preprocessing strategy."""
    name = normalize_preprocess_candidates((preprocess,))[0]
    if name == GRAYSCALE_PREPROCESS:
        prepared = gray
    elif name == FAST_PREPROCESS:
        _, binary = cv2.threshold(gray, int(threshold), 255, cv2.THRESH_BINARY)
        prepared = cv2.bitwise_not(binary)
    elif name == "adaptive_invert":
        adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        prepared = cv2.bitwise_not(adaptive)
    else:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        _, binary = cv2.threshold(
            clahe,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        prepared = cv2.bitwise_not(binary)

    return cv2.cvtColor(prepared, cv2.COLOR_GRAY2BGR)