import cv2
import pytest
from types import SimpleNamespace

from hybrid_search_benchmark import (
    SearchStrategy,
    TrialResult,
    choose_best_result,
    build_default_search_space,
    choose_best_result,
    evaluate_strategy,
    select_bounded_strategies,
    should_prune_strategy,
)


def test_select_bounded_strategies_keeps_deterministic_search_coverage():
    strategies = build_default_search_space()

    selected = select_bounded_strategies(strategies, 12)

    assert len(selected) == 12
    assert selected[0] == strategies[0]
    assert selected[-1] == strategies[-1]
    assert selected == select_bounded_strategies(strategies, 12)


def test_select_bounded_strategies_rejects_non_positive_budget():
    with pytest.raises(ValueError, match="strategy budget"):
        select_bounded_strategies(build_default_search_space(), 0)


def test_select_bounded_strategies_without_budget_preserves_full_space():
    strategies = build_default_search_space()

    assert select_bounded_strategies(strategies, None) == strategies

def test_evaluate_strategy_recognizes_each_unique_source_once(monkeypatch):
    cases = [
        {"sample_source": "same.png", "expected": "Alpha"},
        {"sample_source": "same.png", "expected": "Bravo"},
        {"sample_source": "other.png", "expected": "Charlie"},
    ]
    backend_calls = []

    class FakeBackend:
        def recognize(self, prepared):
            backend_calls.append(prepared)
            texts = {
                "same.png": ["Alpha", "Bravo"],
                "other.png": ["Charlie"],
            }[prepared]
            return SimpleNamespace(
                lines=[
                    SimpleNamespace(
                        text=text,
                        confidence=0.95,
                        box=SimpleNamespace(x=0, y=index * 30, w=30, h=20),
                    )
                    for index, text in enumerate(texts)
                ]
            )

    monkeypatch.setattr(
        "hybrid_search_benchmark._load_image",
        lambda image_path: image_path.name,
    )
    monkeypatch.setattr(
        "hybrid_search_benchmark._prepare_image",
        lambda image, _strategy: image,
    )

    result = evaluate_strategy(
        SearchStrategy(preprocess="gray", threshold=110, scale=2.0),
        cases,
        backend=FakeBackend(),
    )

    assert backend_calls == ["same.png", "other.png"]
    assert result.cases == 3
    assert result.hits == 3
    assert result.evaluated_sources == 2
    assert result.complete is True


def test_choose_best_result_excludes_partial_pruned_trials():
    partial = TrialResult(
        strategy=SearchStrategy(preprocess="gray", threshold=70, scale=1.5),
        cases=3,
        hits=3,
        avg_score=100.0,
        avg_latency_ms=1.0,
        pruned=True,
        complete=False,
    )
    complete = TrialResult(
        strategy=SearchStrategy(preprocess="binary_invert", threshold=110, scale=2.0),
        cases=10,
        hits=8,
        avg_score=40.0,
        avg_latency_ms=35.0,
    )

    assert choose_best_result([partial, complete]) == complete
    assert choose_best_result([partial]) is None

def test_choose_best_result_prioritizes_accuracy_before_speed():
    slow_accurate = TrialResult(
        strategy=SearchStrategy(preprocess="adaptive_invert", threshold=110, scale=2.0),
        cases=10,
        hits=8,
        avg_score=42.0,
        avg_latency_ms=90.0,
    )
    fast_less_accurate = TrialResult(
        strategy=SearchStrategy(preprocess="gray", threshold=100, scale=1.5),
        cases=10,
        hits=7,
        avg_score=55.0,
        avg_latency_ms=15.0,
    )

    assert choose_best_result([fast_less_accurate, slow_accurate]) == slow_accurate


def test_choose_best_result_uses_speed_as_tiebreaker_after_accuracy_and_score():
    slower = TrialResult(
        strategy=SearchStrategy(preprocess="binary_invert", threshold=110, scale=2.0),
        cases=10,
        hits=8,
        avg_score=40.0,
        avg_latency_ms=80.0,
    )
    faster = TrialResult(
        strategy=SearchStrategy(preprocess="adaptive_invert", threshold=130, scale=2.0),
        cases=10,
        hits=8,
        avg_score=40.0,
        avg_latency_ms=35.0,
    )

    assert choose_best_result([slower, faster]) == faster


def test_should_prune_strategy_when_it_cannot_catch_current_best():
    assert should_prune_strategy(
        current_hits=1,
        evaluated_cases=6,
        total_cases=10,
        best_hits=8,
        min_cases=3,
    )


def test_should_not_prune_before_minimum_evidence():
    assert not should_prune_strategy(
        current_hits=0,
        evaluated_cases=2,
        total_cases=10,
        best_hits=8,
        min_cases=3,
    )


def test_unicode_path_loader_uses_path_bytes_and_cv2_imdecode(monkeypatch):
    class FakePath:
        def read_bytes(self):
            return b"encoded-image"

    received = {}

    def fake_decode(payload, flags):
        received["payload"] = bytes(payload)
        received["flags"] = flags
        return "pixels"

    monkeypatch.setattr("hybrid_search_benchmark.cv2.imread", lambda *args, **kwargs: pytest.fail("cv2.imread must not load Unicode paths"))
    monkeypatch.setattr("hybrid_search_benchmark.cv2.imdecode", fake_decode)

    from hybrid_search_benchmark import _load_image

    assert _load_image(FakePath()) == "pixels"
    assert received == {"payload": b"encoded-image", "flags": cv2.IMREAD_COLOR}