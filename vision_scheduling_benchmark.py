"""Deterministic, model-free benchmark for the local Vision request scheduler.

The harness measures scheduling correctness only.  It never starts a model
runtime, sends HTTP, or claims a GPU latency improvement.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from statistics import mean
from typing import Any

from translation_providers import LocalRequestCancelled, _LocalRequestScheduler


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * percentile) - 1))
    return round(ordered[index], 3)


def _run_trial(*, burst_size: int, work_ms: float, cancel_queued: bool) -> dict[str, Any]:
    scheduler = _LocalRequestScheduler()
    state_lock = threading.Lock()
    active = 0
    max_active = 0
    dispatch_order: list[int] = []
    errors: list[str] = []
    cancelled_count = 0
    first_started = threading.Event()
    release_first = threading.Event()
    threads: list[threading.Thread] = []
    waiting_events = [threading.Event() for _ in range(burst_size)]
    cancel_events = [threading.Event() for _ in range(burst_size)]

    def run_job(index: int):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
            dispatch_order.append(index)
        if index == 0:
            first_started.set()
            if not release_first.wait(2):
                raise RuntimeError("first_job_release_timeout")
        if work_ms > 0:
            time.sleep(work_ms / 1000.0)
        with state_lock:
            active -= 1
        return index

    def run_request(index: int):
        nonlocal cancelled_count
        def cancel_predicate() -> bool:
            waiting_events[index].set()
            return cancel_events[index].is_set()

        try:
            scheduler.run(
                lambda: run_job(index),
                cancel_predicate=cancel_predicate if index > 0 else None,
            )
        except LocalRequestCancelled:
            with state_lock:
                cancelled_count += 1
            return
        except Exception as exc:
            with state_lock:
                errors.append(type(exc).__name__)

    started_at = time.perf_counter()
    first = threading.Thread(target=run_request, args=(0,), name="mock-vision-0")
    threads.append(first)
    first.start()
    if not first_started.wait(2):
        errors.append("first_job_start_timeout")

    for index in range(1, burst_size):
        thread = threading.Thread(
            target=run_request,
            args=(index,),
            name=f"mock-vision-{index}",
        )
        threads.append(thread)
        thread.start()
        if not waiting_events[index].wait(2):
            errors.append(f"queued_job_{index}_timeout")

    if cancel_queued:
        for index in range(1, max(1, burst_size - 1)):
            cancel_events[index].set()
    release_first.set()
    for thread in threads:
        thread.join(timeout=3)
        if thread.is_alive():
            errors.append("thread_join_timeout")
    scheduler.close()

    return {
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000.0, 3),
        "dispatch_order": dispatch_order,
        "max_inflight": max_active,
        "cancelled_queued": cancelled_count,
        "errors": errors,
    }


def run_benchmark(*, repeats: int = 5, burst_size: int = 4, work_ms: float = 2.0) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    if burst_size < 2:
        raise ValueError("burst_size must be at least 2")
    if work_ms < 0:
        raise ValueError("work_ms must be non-negative")

    serialization = [
        _run_trial(burst_size=burst_size, work_ms=work_ms, cancel_queued=False)
        for _ in range(repeats)
    ]
    cancellation = [
        _run_trial(burst_size=burst_size, work_ms=work_ms, cancel_queued=True)
        for _ in range(repeats)
    ]
    serialization_elapsed = [item["elapsed_ms"] for item in serialization]
    cancellation_elapsed = [item["elapsed_ms"] for item in cancellation]
    serialization_valid = all(
        item["dispatch_order"] == list(range(burst_size))
        and item["max_inflight"] == 1
        and not item["errors"]
        for item in serialization
    )
    cancellation_valid = all(
        item["dispatch_order"] == [0, burst_size - 1]
        and item["max_inflight"] == 1
        and item["cancelled_queued"] == burst_size - 2
        and not item["errors"]
        for item in cancellation
    )
    return {
        "schema_version": 1,
        "benchmark": "local_vision_request_scheduler",
        "runtime": "mock",
        "policy": "fifo_single_flight_with_queued_cancel",
        "repeats": repeats,
        "burst_size": burst_size,
        "work_ms": work_ms,
        "max_inflight": max(
            [item["max_inflight"] for item in serialization + cancellation],
            default=0,
        ),
        "serialization": {
            "valid": serialization_valid,
            "dispatch_order": serialization[0]["dispatch_order"],
            "elapsed_ms_avg": round(mean(serialization_elapsed), 3),
            "elapsed_ms_p95": _percentile(serialization_elapsed, 0.95),
        },
        "queued_cancellation": {
            "valid": cancellation_valid,
            "dispatch_order": cancellation[0]["dispatch_order"],
            "cancelled_queued": cancellation[0]["cancelled_queued"],
            "elapsed_ms_avg": round(mean(cancellation_elapsed), 3),
            "elapsed_ms_p95": _percentile(cancellation_elapsed, 0.95),
        },
        "promotion_gate": False,
        "gpu_latency_claim": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Model-free local Vision scheduling benchmark")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--burst-size", type=int, default=4)
    parser.add_argument("--work-ms", type=float, default=2.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        result = run_benchmark(**vars(build_parser().parse_args(argv)))
    except (ValueError, RuntimeError):
        print("benchmark_failed", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["serialization"]["valid"] and result["queued_cancellation"]["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
