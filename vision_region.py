from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class VisionRegionResult:
    id: int
    source_text: str
    translation: str
    confidence: float


def build_region_vision_prompt(
    hints: Sequence[Mapping[str, Any]],
    *,
    image_width: int,
    image_height: int,
    target_lang: str,
    knowledge_context: str = "",
) -> str:
    """Build an image-first prompt for translating specified image regions."""
    serialized_hints = []
    for hint in hints:
        try:
            serialized_hints.append(
                {
                    "id": hint["id"],
                    "x": hint["x"],
                    "y": hint["y"],
                    "w": hint["w"],
                    "h": hint["h"],
                    "text": hint["text"],
                }
            )
        except KeyError as exc:
            raise ValueError("Each region hint must contain id, x, y, w, h, and text.") from exc

    lines = [
        "Translate the requested text regions in the attached image.",
        "The image is the source of truth. OCR text may be wrong.",
        "Use visual evidence from the image to correct OCR mistakes.",
        "Return only JSON with this exact shape:",
        '{"regions":[{"id":0,"source_text":"...","translation":"...","confidence":0.0}]}',
        "Do not return markdown, commentary, or any other keys.",
        "Confidence must be a finite number from 0 to 1.",
        "Image dimensions: {} x {}.".format(image_width, image_height),
        "Target language: {}.".format(target_lang),
    ]
    if knowledge_context:
        lines.extend(("Knowledge context:", knowledge_context))
    if serialized_hints:
        lines.extend(
            (
                "Region hints (coordinates are pixels; OCR text is only a hint):",
                json.dumps(serialized_hints, ensure_ascii=True, separators=(",", ":")),
            )
        )
    else:
        lines.append("No region hints were provided. The caller must supply any whole-region hint.")
    return "\n".join(lines)


def parse_region_vision_response(
    raw_text: str, *, allowed_ids: Iterable[int]
) -> list[VisionRegionResult]:
    """Strictly parse a model response into validated region results."""
    if not isinstance(raw_text, str):
        raise ValueError("Response must be text.")

    payload = _decode_json_response(raw_text)
    if not isinstance(payload, dict) or set(payload) != {"regions"}:
        raise ValueError("Response must be a JSON object containing only regions.")
    regions = payload["regions"]
    if not isinstance(regions, list):
        raise ValueError("regions must be a JSON array.")

    permitted_ids = set(allowed_ids)
    seen_ids: set[int] = set()
    results = []
    for region in regions:
        result = _parse_region(region, permitted_ids, seen_ids)
        seen_ids.add(result.id)
        results.append(result)
    return results


def _decode_json_response(raw_text: str) -> Any:
    match = re.fullmatch(r"\s*```(?:json)?[ \t]*\r?\n(.*?)\r?\n```\s*", raw_text, re.DOTALL)
    candidate = match.group(1).strip() if match else raw_text.strip()
    try:
        decoder = json.JSONDecoder()
        value, end = decoder.raw_decode(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("Response is not valid JSON.") from exc
    if candidate[end:].strip():
        raise ValueError("Response contains text outside the JSON value.")
    return value


def _parse_region(
    region: Any, permitted_ids: set[int], seen_ids: set[int]
) -> VisionRegionResult:
    required_keys = {"id", "source_text", "translation", "confidence"}
    if not isinstance(region, dict) or set(region) != required_keys:
        raise ValueError("Each region must contain exactly id, source_text, translation, and confidence.")

    region_id = region["id"]
    source_text = region["source_text"]
    translation = region["translation"]
    confidence = region["confidence"]
    if isinstance(region_id, bool) or not isinstance(region_id, int):
        raise ValueError("Region id must be an integer.")
    if region_id not in permitted_ids:
        raise ValueError("Response contains an id outside allowed_ids.")
    if region_id in seen_ids:
        raise ValueError("Response contains a duplicate region id.")
    if (
        not isinstance(source_text, str)
        or not source_text.strip()
        or not isinstance(translation, str)
        or not translation.strip()
    ):
        raise ValueError("source_text and translation must be non-empty strings.")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be a finite number.")

    try:
        confidence_value = float(confidence)
    except OverflowError as exc:
        raise ValueError("confidence must be a finite number.") from exc
    if not math.isfinite(confidence_value):
        raise ValueError("confidence must be a finite number.")
    return VisionRegionResult(
        id=region_id,
        source_text=source_text,
        translation=translation,
        confidence=max(0.0, min(1.0, confidence_value)),
    )
