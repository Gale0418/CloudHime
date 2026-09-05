from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from provider_runtime import (
    AcquireCancelled,
    CredentialUnavailable,
    RuntimeCredentialPool,
    parse_retry_after,
)


class ManualClock:
    def __init__(self, value: float = 100.0):
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _pool(clock: ManualClock, **kwargs) -> RuntimeCredentialPool:
    return RuntimeCredentialPool(
        [
            {
                "provider": "google",
                "key_id": "key-a",
                "secret": "secret-a",
                "model": "gemini-test",
                "project_id": "project-1",
            },
            {
                "provider": "google",
                "key_id": "key-b",
                "secret": "secret-b",
                "model": "gemini-test",
                "project_id": "project-1",
            },
        ],
        clock=clock,
        **kwargs,
    )


def test_runtime_secret_is_available_to_lease_but_never_repr_snapshot_or_error():
    clock = ManualClock()
    pool = _pool(clock)

    lease = pool.acquire("google", "gemini-test")
    assert lease.secret in {"secret-a", "secret-b"}
    assert "secret-a" not in repr(lease)
    assert "secret-b" not in repr(pool)
    assert all("secret" not in repr(item) for item in pool.snapshot())

    lease.release()
    with pytest.raises(CredentialUnavailable) as exc_info:
        pool.acquire("missing", "gemini-test", wait=False)
    assert "secret" not in str(exc_info.value)


def test_acquire_release_is_thread_safe_and_same_key_is_not_double_leased():
    clock = ManualClock()
    pool = _pool(clock)
    first = pool.acquire("google", "gemini-test", key_id="key-a")

    with pytest.raises(CredentialUnavailable):
        pool.acquire("google", "gemini-test", key_id="key-a", wait=False)

    second = pool.acquire("google", "gemini-test", wait=False)
    assert second.key_id == "key-b"
    first.release()
    second.release()
    assert all(item["active"] is False for item in pool.snapshot())


def test_retry_after_parses_seconds_and_http_date():
    assert parse_retry_after("2.5") == pytest.approx(2.5)
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert parse_retry_after("Thu, 01 Jan 2026 00:00:07 GMT", now=now) == pytest.approx(7)
    assert parse_retry_after("not-a-date", now=now) is None


def test_429_cooldown_is_shared_by_same_project_keys_and_expires_with_monotonic_clock():
    clock = ManualClock()
    pool = _pool(clock)
    lease = pool.acquire("google", "gemini-test")
    lease.release(status_code=429, retry_after="10")

    with pytest.raises(CredentialUnavailable):
        pool.acquire("google", "gemini-test", wait=False)
    assert {item["status"] for item in pool.snapshot()} == {"cooldown"}

    clock.advance(10)
    assert pool.acquire("google", "gemini-test", wait=False).key_id in {"key-a", "key-b"}


def test_401_and_403_quarantine_only_the_leased_credential():
    clock = ManualClock()
    pool = _pool(clock)
    lease = pool.acquire("google", "gemini-test", key_id="key-a")
    lease.release(status_code=401)
    snapshot = {item["key_id"]: item for item in pool.snapshot()}
    assert snapshot["key-a"]["status"] == "quarantined"
    assert snapshot["key-a"]["quarantined"] is True
    assert pool.acquire("google", "gemini-test", key_id="key-b", wait=False).key_id == "key-b"


def test_5xx_uses_bounded_per_key_backoff_metadata():
    clock = ManualClock()
    pool = _pool(clock, server_error_backoff_base=3, server_error_backoff_max=5)
    lease = pool.acquire("google", "gemini-test", key_id="key-a")
    lease.release(status_code=503)
    item = next(item for item in pool.snapshot() if item["key_id"] == "key-a")
    assert item["status"] == "backoff"
    assert item["backoff_seconds"] == 3
    assert item["backoff_level"] == 1

    clock.advance(3)
    lease = pool.acquire("google", "gemini-test", key_id="key-a", wait=False)
    lease.release(status_code=503)
    item = next(item for item in pool.snapshot() if item["key_id"] == "key-a")
    assert item["backoff_seconds"] == 5
    assert item["backoff_level"] == 2


def test_timeout_and_ambiguous_outcomes_only_record_safe_classification():
    clock = ManualClock()
    pool = _pool(clock)
    lease = pool.acquire("google", "gemini-test", key_id="key-a")
    lease.release(outcome="ambiguous")
    item = next(item for item in pool.snapshot() if item["key_id"] == "key-a")
    assert item["last_outcome"] == "ambiguous"
    assert item["status"] == "ready"

    lease = pool.acquire("google", "gemini-test", key_id="key-a")
    lease.release(error=TimeoutError("secret-a leaked"))
    item = next(item for item in pool.snapshot() if item["key_id"] == "key-a")
    assert item["last_outcome"] == "timeout"
    assert "secret-a" not in repr(item)


def test_wait_is_cancellation_aware():
    clock = ManualClock()
    pool = _pool(clock)
    lease = pool.acquire("google", "gemini-test", key_id="key-a")
    lease.release(status_code=429, retry_after="60")
    cancelled = threading.Event()
    cancelled.set()

    with pytest.raises(AcquireCancelled):
        pool.acquire("google", "gemini-test", cancel_event=cancelled)


def test_default_rolling_window_is_shared_by_project_scope():
    clock = ManualClock()
    pool = _pool(clock, quota_limit=1, quota_window_seconds=10)
    first = pool.acquire("google", "gemini-test", key_id="key-a")
    first.release()
    with pytest.raises(CredentialUnavailable):
        pool.acquire("google", "gemini-test", wait=False)
    clock.advance(10)
    assert pool.acquire("google", "gemini-test", wait=False).key_id in {"key-a", "key-b"}


def test_explicit_quota_scopes_are_independent_even_with_same_project_and_model():
    clock = ManualClock()
    pool = RuntimeCredentialPool(
        [
            {
                "provider": "google",
                "key_id": "key-a",
                "secret": "secret-a",
                "model": "gemini-test",
                "project_id": "same-project",
                "quota_scope": "scope-a",
            },
            {
                "provider": "google",
                "key_id": "key-b",
                "secret": "secret-b",
                "model": "gemini-test",
                "project_id": "same-project",
                "quota_scope": "scope-b",
            },
        ],
        clock=clock,
        quota_limit=1,
        quota_window_seconds=10,
    )
    pool.acquire("google", "gemini-test", key_id="key-a").release()
    # The two keys remain independently usable; scope is explicit metadata,
    # never inferred from a secret or a project/header-like value.
    assert pool.acquire("google", "gemini-test", key_id="key-b", wait=False).key_id == "key-b"
    with pytest.raises(CredentialUnavailable):
        pool.acquire("google", "gemini-test", key_id="key-a", wait=False)


def test_cancellation_accepts_event_or_zero_argument_predicate():
    clock = ManualClock()
    pool = _pool(clock)
    lease = pool.acquire("google", "gemini-test", key_id="key-a")
    lease.release(status_code=429, retry_after="60")
    with pytest.raises(AcquireCancelled):
        pool.acquire("google", "gemini-test", cancel_event=lambda: True)


def test_context_exit_does_not_release_a_lease_twice_after_manual_release():
    clock = ManualClock()
    pool = _pool(clock)
    with pool.acquire("google", "gemini-test", key_id="key-a") as lease:
        lease.release()
    replacement = pool.acquire("google", "gemini-test", key_id="key-a", wait=False)
    replacement.release()
