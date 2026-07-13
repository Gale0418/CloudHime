from hybrid_search_benchmark import (
    SearchStrategy,
    TrialResult,
    choose_best_result,
    should_prune_strategy,
)


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
