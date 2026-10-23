import json

import pytest

import vision_scheduling_benchmark as benchmark


def test_mock_benchmark_proves_fifo_single_flight_and_queued_cancel():
    result = benchmark.run_benchmark(repeats=3, burst_size=4, work_ms=0)

    assert result["runtime"] == "mock"
    assert result["max_inflight"] == 1
    assert result["serialization"] == {
        **result["serialization"],
        "valid": True,
        "dispatch_order": [0, 1, 2, 3],
    }
    assert result["queued_cancellation"]["valid"] is True
    assert result["queued_cancellation"]["dispatch_order"] == [0, 3]
    assert result["queued_cancellation"]["cancelled_queued"] == 2
    assert result["promotion_gate"] is False
    assert result["gpu_latency_claim"] is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"repeats": 0}, "repeats must be positive"),
        ({"burst_size": 1}, "burst_size must be at least 2"),
        ({"work_ms": -1}, "work_ms must be non-negative"),
    ],
)
def test_mock_benchmark_rejects_invalid_bounds(kwargs, message):
    with pytest.raises(ValueError, match=message):
        benchmark.run_benchmark(**kwargs)


def test_cli_emits_json_contract_without_gpu_claim(capsys):
    assert benchmark.main(["--repeats", "1", "--burst-size", "3", "--work-ms", "0"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["benchmark"] == "local_vision_request_scheduler"
    assert result["runtime"] == "mock"
    assert result["promotion_gate"] is False
    assert result["gpu_latency_claim"] is False
