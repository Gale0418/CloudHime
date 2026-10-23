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

def _runtime_policy_strategy(preprocess):
    return SearchStrategy(preprocess=preprocess, threshold=100, scale=2.0)


class _RuntimePolicyBackend:
    def __init__(self, outputs, calls):
        self.outputs = outputs
        self.calls = calls

    def recognize(self, prepared):
        source, preprocess = prepared
        self.calls.append((source, preprocess))
        text, confidence = self.outputs[preprocess]
        return SimpleNamespace(lines=[SimpleNamespace(
            text=text,
            confidence=confidence,
            box=SimpleNamespace(x=0, y=0, w=80, h=20),
        )])


def _evaluate_fake_runtime_policy(monkeypatch, outputs, expected):
    from hybrid_search_benchmark import evaluate_runtime_policy

    calls = []
    monkeypatch.setattr(
        "hybrid_search_benchmark._load_image",
        lambda image_path: image_path.name,
    )
    monkeypatch.setattr(
        "hybrid_search_benchmark._prepare_image",
        lambda image, strategy: (image, strategy.preprocess),
    )
    result = evaluate_runtime_policy(
        [{"sample_source": "sample.png", "expected": expected}],
        backends=[_RuntimePolicyBackend(outputs, calls)],
        baseline_strategy=_runtime_policy_strategy("binary_invert"),
        rescue_strategies=[
            _runtime_policy_strategy("adaptive_invert"),
            _runtime_policy_strategy("clahe_otsu_invert"),
        ],
    )
    return result, calls


def test_runtime_policy_evaluator_counts_adoption_and_ground_truth_improvement(monkeypatch):
    result, calls = _evaluate_fake_runtime_policy(
        monkeypatch,
        {
            "binary_invert": ("誤認文字", 0.2),
            "adaptive_invert": ("正解文字", 0.9),
            "clahe_otsu_invert": ("別候補文", 0.7),
        },
        "正解文字",
    )

    assert calls == [
        ("sample.png", "binary_invert"),
        ("sample.png", "adaptive_invert"),
        ("sample.png", "clahe_otsu_invert"),
    ]
    assert result.baseline_hits == 0
    assert result.selected_hits == 1
    assert result.adoptions == 1
    assert result.improvements == 1
    assert result.regressions == 0
    assert result.complete is True
    assert result.promotion_safe is True
    assert result.accuracy_promoted is True


def test_runtime_policy_evaluator_keeps_high_confidence_fast_path(monkeypatch):
    result, calls = _evaluate_fake_runtime_policy(
        monkeypatch,
        {
            "binary_invert": ("正解文字", 0.9),
            "adaptive_invert": ("不應執行", 0.9),
            "clahe_otsu_invert": ("不應執行", 0.9),
        },
        "正解文字",
    )

    assert calls == [("sample.png", "binary_invert")]
    assert result.baseline_hits == result.selected_hits == 1
    assert result.adoptions == 0
    assert result.improvements == result.regressions == 0
    assert result.promotion_safe is True
    assert result.accuracy_promoted is False


def test_runtime_policy_evaluator_reports_regression_fail_closed(monkeypatch):
    result, _calls = _evaluate_fake_runtime_policy(
        monkeypatch,
        {
            "binary_invert": ("正解文字", 0.2),
            "adaptive_invert": ("錯誤文字", 0.9),
            "clahe_otsu_invert": ("另一錯字", 0.8),
        },
        "正解文字",
    )

    assert result.baseline_hits == 1
    assert result.selected_hits == 0
    assert result.adoptions == 1
    assert result.improvements == 0
    assert result.regressions == 1
    assert result.promotion_safe is False
    assert result.accuracy_promoted is False


def test_runtime_policy_evaluator_rejects_partial_missing_source(monkeypatch):
    from hybrid_search_benchmark import evaluate_runtime_policy

    monkeypatch.setattr("hybrid_search_benchmark._load_image", lambda _path: None)
    result = evaluate_runtime_policy(
        [{"sample_source": "missing.png", "expected": "文字"}],
        backends=[_RuntimePolicyBackend({}, [])],
        baseline_strategy=_runtime_policy_strategy("binary_invert"),
        rescue_strategies=[_runtime_policy_strategy("adaptive_invert")],
    )

    assert result.cases == 1
    assert result.evaluated_cases == 0
    assert result.complete is False
    assert result.promotion_safe is False
    assert result.accuracy_promoted is False

class _NamedWaterfallBackend:
    def __init__(self, name, output, calls):
        self.name = name
        self.output = output
        self.calls = calls

    def recognize(self, prepared):
        source, preprocess = prepared
        self.calls.append((self.name, source, preprocess))
        if isinstance(self.output, Exception):
            raise self.output
        if hasattr(self.output, "lines"):
            return self.output
        text, confidence = self.output
        lines = [] if not text else [SimpleNamespace(
            text=text,
            confidence=confidence,
            box=SimpleNamespace(x=0, y=0, w=80, h=20),
        )]
        return SimpleNamespace(lines=lines)


def _evaluate_fake_backend_waterfall(monkeypatch, primary_output, secondary_output, expected):
    from hybrid_search_benchmark import evaluate_backend_waterfall

    calls = []
    monkeypatch.setattr(
        "hybrid_search_benchmark._load_image",
        lambda image_path: image_path.name,
    )
    monkeypatch.setattr(
        "hybrid_search_benchmark._prepare_image",
        lambda image, strategy: (image, strategy.preprocess),
    )
    result = evaluate_backend_waterfall(
        [{"sample_source": "sample.png", "expected": expected}],
        backends=[
            _NamedWaterfallBackend("windows", primary_output, calls),
            _NamedWaterfallBackend("rapidocr", secondary_output, calls),
        ],
        strategy=_runtime_policy_strategy("binary_invert"),
    )
    return result, calls


def test_backend_waterfall_stops_after_nonempty_primary_without_accuracy_loss(monkeypatch):
    result, calls = _evaluate_fake_backend_waterfall(
        monkeypatch,
        ("正解文字", None),
        ("正解文字", 0.9),
        "正解文字",
    )

    assert calls == [
        ("windows", "sample.png", "binary_invert"),
        ("rapidocr", "sample.png", "binary_invert"),
        ("windows", "sample.png", "binary_invert"),
    ]
    assert result.baseline_hits == result.candidate_hits == 1
    assert result.improvements == result.regressions == 0
    assert result.candidate_secondary_attempts == 0
    assert result.complete is True
    assert result.accuracy_preserved is True


def test_backend_waterfall_reports_primary_wrong_secondary_correct_regression(monkeypatch):
    result, _calls = _evaluate_fake_backend_waterfall(
        monkeypatch,
        ("誤認文字", None),
        ("正解文字", 0.9),
        "正解文字",
    )

    assert result.baseline_hits == 1
    assert result.candidate_hits == 0
    assert result.improvements == 0
    assert result.regressions == 1
    assert result.regression_sources == ("sample.png",)
    assert result.improvement_sources == ()
    assert result.accuracy_preserved is False
    assert result.promotion_ready is False


def test_backend_waterfall_uses_secondary_after_empty_primary(monkeypatch):
    result, calls = _evaluate_fake_backend_waterfall(
        monkeypatch,
        ("", None),
        ("正解文字", 0.9),
        "正解文字",
    )

    assert calls[-2:] == [
        ("windows", "sample.png", "binary_invert"),
        ("rapidocr", "sample.png", "binary_invert"),
    ]
    assert result.baseline_hits == result.candidate_hits == 1
    assert result.candidate_secondary_attempts == 1
    assert result.regressions == 0


def test_backend_waterfall_backend_error_fails_completeness(monkeypatch):
    result, _calls = _evaluate_fake_backend_waterfall(
        monkeypatch,
        ("正解文字", None),
        RuntimeError("secondary failed"),
        "正解文字",
    )

    assert result.complete is False
    assert result.failed_backend_calls >= 1
    assert result.accuracy_preserved is False
    assert result.promotion_ready is False


def test_backend_waterfall_error_result_fails_completeness(monkeypatch):
    error_result = SimpleNamespace(lines=[], error="engine unavailable")
    result, calls = _evaluate_fake_backend_waterfall(
        monkeypatch,
        error_result,
        ("正解文字", 0.9),
        "正解文字",
    )

    assert calls[-2:] == [
        ("windows", "sample.png", "binary_invert"),
        ("rapidocr", "sample.png", "binary_invert"),
    ]
    assert result.failed_backend_calls >= 1
    assert result.complete is False
    assert result.promotion_ready is False


def test_backend_waterfall_baseline_tie_preserves_backend_order(monkeypatch):
    result, calls = _evaluate_fake_backend_waterfall(
        monkeypatch,
        ("第一候選", 0.9),
        ("第二候選", 0.9),
        "第一候選",
    )

    assert calls[:2] == [
        ("windows", "sample.png", "binary_invert"),
        ("rapidocr", "sample.png", "binary_invert"),
    ]
    assert result.baseline_hits == result.candidate_hits == 1
    assert result.regressions == 0

def test_backend_waterfall_promotion_requires_accuracy_and_speed():
    from hybrid_search_benchmark import BackendWaterfallResult

    promoted = BackendWaterfallResult(
        cases=10,
        evaluated_cases=10,
        evaluated_sources=5,
        baseline_hits=8,
        candidate_hits=8,
        improvements=0,
        regressions=0,
        candidate_secondary_attempts=1,
        failed_backend_calls=0,
        baseline_avg_latency_ms=100.0,
        candidate_avg_latency_ms=40.0,
        baseline_p95_latency_ms=120.0,
        candidate_p95_latency_ms=50.0,
        improvement_sources=(),
        regression_sources=(),
        complete=True,
    )
    not_faster = BackendWaterfallResult(
        **{
            **promoted.__dict__,
            "candidate_avg_latency_ms": 100.0,
        }
    )
    p95_not_faster = BackendWaterfallResult(
        **{
            **promoted.__dict__,
            "candidate_p95_latency_ms": 120.0,
        }
    )

    assert promoted.accuracy_preserved is True
    assert promoted.speed_improved is True
    assert promoted.p95_speed_improved is True
    assert promoted.promotion_ready is True
    assert not_faster.speed_improved is False
    assert not_faster.promotion_ready is False
    assert p95_not_faster.p95_speed_improved is False
    assert p95_not_faster.promotion_ready is False
