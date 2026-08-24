from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from vision_region import (
    VisionRegionResult,
    build_region_vision_prompt,
    parse_region_vision_response,
)


def test_result_is_frozen_dataclass() -> None:
    result = VisionRegionResult(1, "source", "translation", 0.5)

    assert is_dataclass(result)
    with pytest.raises(FrozenInstanceError):
        result.translation = "changed"


def test_build_prompt_makes_image_authoritative_and_includes_hints() -> None:
    prompt = build_region_vision_prompt(
        [{"id": 7, "x": 10, "y": 20, "w": 30, "h": 40, "text": "0CR?"}],
        image_width=1920,
        image_height=1080,
        target_lang="English",
        knowledge_context="Character names: Ada",
    )

    assert "source of truth" in prompt
    assert "OCR text may be wrong" in prompt
    assert "1920" in prompt
    assert "1080" in prompt
    assert "English" in prompt
    assert "Character names: Ada" in prompt
    assert '"regions"' in prompt
    assert '"id":7' in prompt
    assert '"text":"0CR?"' in prompt
    assert "using each supplied id exactly once" in prompt
    assert "Never invent ids" in prompt
    assert "not English unless the target language is English" in prompt


def test_build_prompt_binds_single_full_image_hint_to_one_id() -> None:
    prompt = build_region_vision_prompt(
        [{"id": 0, "x": 0, "y": 0, "w": 800, "h": 600, "text": "whole page"}],
        image_width=800,
        image_height=600,
        target_lang="zh-TW",
    )

    assert "exactly one region using that hint id" in prompt
    assert "zh-TW" in prompt


def test_build_prompt_does_not_invent_whole_region_hint() -> None:
    prompt = build_region_vision_prompt(
        [], image_width=100, image_height=200, target_lang="English"
    )

    assert "No region hints were provided." in prompt
    assert '"id": 0' not in prompt


def test_parse_accepts_pure_or_fenced_json_and_clamps_confidence() -> None:
    pure = '{"regions":[{"id":1,"source_text":"a","translation":"b","confidence":1.5}]}'
    fenced = "```json\n  {\"regions\":[{\"id\":2,\"source_text\":\"c\",\"translation\":\"d\",\"confidence\":-0.2}]}  \n```"

    assert parse_region_vision_response(pure, allowed_ids={1, 2}) == [
        VisionRegionResult(1, "a", "b", 1.0)
    ]
    assert parse_region_vision_response(fenced, allowed_ids={1, 2}) == [
        VisionRegionResult(2, "c", "d", 0.0)
    ]


def test_parse_accepts_strict_region_array_emitted_by_local_vision_models() -> None:
    raw = '[{"id":1,"source_text":"a","translation":"b","confidence":0.75}]'

    assert parse_region_vision_response(raw, allowed_ids={1}) == [
        VisionRegionResult(1, "a", "b", 0.75)
    ]


def test_parse_defaults_missing_confidence_for_strict_local_region_array() -> None:
    raw = '```json\n[{"id":1,"source_text":"a","translation":"b"}]\n```'

    assert parse_region_vision_response(raw, allowed_ids={1}) == [
        VisionRegionResult(1, "a", "b", 0.0)
    ]


@pytest.mark.parametrize(
    "raw_text",
    [
        '{"regions":[{"id":1,"source_text":"a","translation":"b","confidence":0.5},{"id":1,"source_text":"c","translation":"d","confidence":0.5}]}',
        '{"regions":[{"id":3,"source_text":"a","translation":"b","confidence":0.5}]}',
        '{"regions":[{"id":1,"translation":"b","confidence":0.5}]}',
        '{"regions":[{"id":1,"source_text":"a","confidence":0.5}]}',
        '{"regions":[{"id":1,"source_text":"","translation":"b","confidence":0.5}]}',
        '{"regions":[{"id":1,"source_text":"a","translation":"  ","confidence":0.5}]}',
        '{"regions":[{"id":1,"source_text":"a","translation":"b","confidence":NaN}]}',
        '{"regions":[{"id":1,"source_text":"a","translation":"b","confidence":Infinity}]}',
        'prefix {"regions":[]}',
        '{"regions":[]} suffix',
        '{"regions":[]}',
    ],
)
def test_parse_rejects_malformed_or_disallowed_responses(raw_text: str) -> None:
    if raw_text == '{"regions":[]}':
        assert parse_region_vision_response(raw_text, allowed_ids={1}) == []
    else:
        with pytest.raises(ValueError):
            parse_region_vision_response(raw_text, allowed_ids={1})


def test_parse_allows_a_partial_subset_of_ids() -> None:
    raw = '{"regions":[{"id":2,"source_text":"original","translation":"translated","confidence":0.75}]}'

    assert parse_region_vision_response(raw, allowed_ids={1, 2, 3}) == [
        VisionRegionResult(2, "original", "translated", 0.75)
    ]


def test_parse_normalizes_overflowing_confidence_to_validation_error() -> None:
    raw = (
        '{"regions":[{"id":1,"source_text":"a","translation":"b","confidence":'
        + ("9" * 400)
        + "}]}"
    )

    with pytest.raises(ValueError, match="finite number"):
        parse_region_vision_response(raw, allowed_ids={1})
