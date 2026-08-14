import pytest

from japanese_ocr_rescue import (
    MeikiCandidate,
    MeikiCharacter,
    build_verification_hint,
    candidate_from_meiki_results,
    decide_rescue_text,
    is_usable_meiki_candidate,
    load_meiki_ocr,
    rescue_gate,
    trusted_text,
)


def japanese_candidate() -> MeikiCandidate:
    return MeikiCandidate(
        text="過ぎた街並は終わりの愛と遠くた",
        characters=tuple(
            MeikiCharacter(character, 0.9 if index < 14 else 0.2)
            for index, character in enumerate("過ぎた街並は終わりの愛と遠くた")
        ),
    )


def test_rescue_gate_accepts_manga_portrait_but_rejects_non_japanese_or_too_narrow_images() -> None:
    assert rescue_gate("過ぎた街並は終りの愛と遠ぐ", image_width=617, image_height=95)
    assert rescue_gate(
        "マジックワールド最強と呼ばれるインチキクラス",
        image_width=1124,
        image_height=1600,
    )
    assert not rescue_gate("合輯 - 空の境界 YouTube", image_width=617, image_height=95)
    assert not rescue_gate("ツーポイントミュージアム", image_width=292, image_height=800)


@pytest.mark.parametrize(
    ("image_width", "image_height"),
    [
        (1168, 1899),  # 0.6151: multi-panel manga page
        (1124, 1600),  # 0.7025: owner-confirmed page
        (704, 928),    # 0.7586: manga cover
        (450, 586),    # 0.7679: manga cover
    ],
)
def test_rescue_gate_accepts_common_manga_portrait_aspects(image_width, image_height) -> None:
    assert rescue_gate(
        "楽しいだろ魔術は！",
        image_width=image_width,
        image_height=image_height,
    )


def test_rescue_gate_portrait_window_has_explicit_boundaries() -> None:
    text = "楽しいだろ魔術は！"
    assert rescue_gate(text, image_width=3, image_height=5)  # 0.60
    assert rescue_gate(text, image_width=4, image_height=5)  # 0.80
    assert not rescue_gate(text, image_width=59, image_height=100)
    assert not rescue_gate(text, image_width=81, image_height=100)


def test_candidate_keeps_character_confidence_and_builds_hint() -> None:
    candidate = candidate_from_meiki_results(
        [{"text": "遠くた", "chars": [
            {"char": "遠", "conf": 0.9},
            {"char": "く", "conf": 0.2},
            {"char": "た", "conf": 0.3},
        ]}]
    )

    assert candidate.low_confidence_positions == (2, 3)
    assert trusted_text(candidate) == "遠"
    assert "position 2='く'" in build_verification_hint(candidate)
    assert "position 3='た'" in build_verification_hint(candidate)


def test_usable_candidate_requires_strong_mean_and_some_uncertainty() -> None:
    candidate = japanese_candidate()

    assert is_usable_meiki_candidate(candidate, "過ぎた街並は終りの愛と遠ぐ")
    assert not is_usable_meiki_candidate(candidate, candidate.text)


def test_second_result_is_adopted_only_when_trusted_text_similarity_improves() -> None:
    candidate = japanese_candidate()
    first = "過ぎた街並は終りの愛と遠ぐ"
    second = "過ぎた街並は終わりの愛と遠くへ"

    improved = decide_rescue_text(first, second, candidate)
    regressed = decide_rescue_text(first, "ぜんぜん違う", candidate)

    assert improved.adopted is True
    assert improved.selected_text == second
    assert improved.second_similarity > improved.first_similarity
    assert regressed.adopted is False
    assert regressed.selected_text == first


def test_second_result_cannot_trade_away_full_candidate_consistency() -> None:
    candidate = MeikiCandidate(
        text="ABCXYZ",
        characters=tuple(
            MeikiCharacter(character, 0.9 if index < 3 else 0.2)
            for index, character in enumerate("ABCXYZ")
        ),
    )

    # The second result is closer to the trusted high-confidence prefix, but
    # drops too much of the candidate that the baseline preserved.
    decision = decide_rescue_text("ABQXYZ", "ABCX", candidate)

    assert decision.adopted is False
    assert decision.selected_text == "ABQXYZ"

def test_meiki_loader_is_lazy_and_cpu_only() -> None:
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return object()

    assert load_meiki_ocr(factory) is not None
    assert calls == [{"provider": "CPUExecutionProvider"}]
