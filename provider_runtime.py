"""Thread-safe, process-local credential leasing and provider health state.

This module deliberately owns no persistence.  A credential secret lives only in
the ``RuntimeCredential`` object held by this process and is never included in
representations, exceptions, or snapshots.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from uuid import uuid4


class RuntimeCredentialError(RuntimeError):
    """Base class for safe runtime pool errors."""


class CredentialUnavailable(RuntimeCredentialError):
    """No matching credential can be leased at this time."""


class AcquireCancelled(RuntimeCredentialError):
    """An acquire wait was cancelled by the caller."""


class InvalidLease(RuntimeCredentialError):
    """A lease was released by the wrong pool or more than once."""


def parse_retry_after(value: Any, *, now: datetime | float | None = None) -> float | None:
    """Parse a Retry-After value into non-negative seconds.

    Both the HTTP seconds form and HTTP-date form are accepted.  Invalid or
    negative values return ``None`` rather than raising provider-controlled
    text into the caller.
    """

    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            seconds = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return seconds if math.isfinite(seconds) and seconds >= 0 else None

    text = str(value).strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except (TypeError, ValueError, OverflowError):
        seconds = None
    if seconds is not None:
        return seconds if math.isfinite(seconds) and seconds >= 0 else None

    try:
        target = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return None
    if target is None:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    if now is None:
        current = datetime.now(timezone.utc)
    elif isinstance(now, datetime):
        current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    else:
        try:
            current = datetime.fromtimestamp(float(now), tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            return None
    return max(0.0, (target - current).total_seconds())


@dataclass(frozen=True, slots=True)
class RuntimeCredential:
    """A process-local credential descriptor.

    ``secret`` is intentionally excluded from the generated representation and
    comparisons.  It is still available to a lease holder for the provider
    request that it is responsible for making.
    """

    provider: str
    key_id: str
    model: str
    secret: str = field(repr=False, compare=False)
    project_id: str | None = None
    quota_scope: str | None = field(default=None, compare=False)

    def __repr__(self) -> str:
        return (
            "RuntimeCredential("
            f"provider={self.provider!r}, key_id={self.key_id!r}, model={self.model!r}, "
            f"project_id={self.project_id!r})"
        )


@dataclass(slots=True)
class _CredentialState:
    credential: RuntimeCredential
    active: bool = False
    lease_token: str | None = None
    quarantined: bool = False
    cooldown_until: float = 0.0
    backoff_level: int = 0
    backoff_seconds: float = 0.0
    last_outcome: str | None = None


@dataclass(slots=True)
class _QuotaState:
    calls: deque[float] = field(default_factory=deque)
    cooldown_until: float = 0.0


class CredentialLease:
    """A single-use lease for one runtime credential."""

    __slots__ = ("_pool", "_identity", "_token", "_credential", "_released")

    def __init__(self, pool: RuntimeCredentialPool, state: _CredentialState, token: str):
        self._pool = pool
        self._identity = _identity(state.credential)
        self._token = token
        self._credential = state.credential
        self._released = False

    @property
    def credential(self) -> RuntimeCredential:
        return self._credential

    @property
    def secret(self) -> str:
        return self._credential.secret

    @property
    def provider(self) -> str:
        return self._credential.provider

    @property
    def key_id(self) -> str:
        return self._credential.key_id

    @property
    def model(self) -> str:
        return self._credential.model

    @property
    def project_id(self) -> str | None:
        return self._credential.project_id

    def release(
        self,
        outcome: str | None = None,
        *,
        status_code: int | None = None,
        retry_after: Any = None,
        error: BaseException | None = None,
        ambiguous: bool = False,
    ) -> None:
        self._pool.release(
            self,
            outcome=outcome,
            status_code=status_code,
            retry_after=retry_after,
            error=error,
            ambiguous=ambiguous,
        )

    def __enter__(self) -> CredentialLease:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        # A caller may intentionally report the outcome before leaving the
        # context.  Do not let a second release mask the block's result.
        if not self._released:
            if exc is None:
                self.release()
            else:
                self.release(error=exc)

    def __repr__(self) -> str:
        return (
            "CredentialLease("
            f"provider={self.provider!r}, key_id={self.key_id!r}, model={self.model!r}, "
            f"released={self._released!r})"
        )


def _identity(credential: RuntimeCredential) -> tuple[str, str, str]:
    return credential.provider, credential.key_id, credential.model


class RuntimeCredentialPool:
    """Thread-safe runtime credential pool with bounded provider health state."""

    def __init__(
        self,
        credentials: Iterable[RuntimeCredential | Mapping[str, Any]] = (),
        *,
        clock: Callable[[], float] | None = None,
        quota_limit: int | None = None,
        quota_window_seconds: float = 60.0,
        rolling_window_limit: int | None = None,
        rolling_window_seconds: float | None = None,
        rate_limit_cooldown: float = 60.0,
        server_error_backoff_base: float = 1.0,
        server_error_backoff_max: float = 30.0,
    ):
        self._clock = clock or time.monotonic
        self._condition = threading.Condition(threading.RLock())
        self._states: dict[tuple[str, str, str], _CredentialState] = {}
        self._scopes: dict[tuple[Any, ...], _QuotaState] = {}
        self._round_robin = 0
        self.quota_limit = rolling_window_limit if rolling_window_limit is not None else quota_limit
        self.quota_window_seconds = (
            rolling_window_seconds if rolling_window_seconds is not None else quota_window_seconds
        )
        self.rate_limit_cooldown = max(0.0, float(rate_limit_cooldown))
        self.server_error_backoff_base = max(0.0, float(server_error_backoff_base))
        self.server_error_backoff_max = max(
            self.server_error_backoff_base, float(server_error_backoff_max)
        )
        if self.quota_limit is not None and int(self.quota_limit) < 1:
            raise ValueError("quota_limit must be positive")
        if self.quota_window_seconds <= 0:
            raise ValueError("quota_window_seconds must be positive")
        for item in credentials:
            if isinstance(item, RuntimeCredential):
                self.add(item)
            elif isinstance(item, Mapping):
                self.register(
                    item.get("provider"),
                    item.get("key_id"),
                    item.get("secret"),
                    item.get("model"),
                    project_id=item.get("project_id"),
                    quota_scope=item.get("quota_scope"),
                )
            else:
                raise ValueError("credential must be a runtime credential or mapping")

    def add(self, credential: RuntimeCredential) -> RuntimeCredential:
        if not isinstance(credential, RuntimeCredential):
            raise ValueError("credential must be a RuntimeCredential")
        self.register(
            credential.provider,
            credential.key_id,
            credential.secret,
            credential.model,
            project_id=credential.project_id,
            quota_scope=credential.quota_scope,
        )
        return credential

    def register(
        self,
        provider: str,
        key_id: str,
        secret: str,
        model: str,
        *,
        project_id: str | None = None,
        quota_scope: str | None = None,
    ) -> RuntimeCredential:
        provider, key_id, model = self._validate_identity(provider, key_id, model)
        if not isinstance(secret, str) or not secret:
            raise ValueError("credential secret must be non-empty")
        credential = RuntimeCredential(
            provider=provider,
            key_id=key_id,
            model=model,
            secret=secret,
            project_id=project_id,
            quota_scope=quota_scope,
        )
        identity = _identity(credential)
        with self._condition:
            old = self._states.get(identity)
            if old is not None and old.active:
                raise RuntimeCredentialError("cannot replace an active credential")
            self._states[identity] = _CredentialState(credential=credential)
            self._scopes.setdefault(self._scope_for(credential), _QuotaState())
            self._condition.notify_all()
        return credential

    def remove(self, provider: str, key_id: str, model: str) -> None:
        identity = self._validate_identity(provider, key_id, model)
        with self._condition:
            state = self._states.get(identity)
            if state is None:
                return
            if state.active:
                raise RuntimeCredentialError("cannot remove an active credential")
            del self._states[identity]
            self._condition.notify_all()

    def unquarantine(self, provider: str, key_id: str, model: str) -> None:
        identity = self._validate_identity(provider, key_id, model)
        with self._condition:
            state = self._states.get(identity)
            if state is not None:
                state.quarantined = False
                state.cooldown_until = 0.0
                state.last_outcome = None
                self._condition.notify_all()

    def acquire(
        self,
        provider: str,
        model: str | None = None,
        *,
        project_id: str | None = None,
        key_id: str | None = None,
        wait: bool = True,
        timeout: float | None = None,
        cancel_event: Any = None,
    ) -> CredentialLease:
        provider = self._clean(provider)
        model = self._clean(model) if model is not None else None
        key_id = self._clean(key_id) if key_id is not None else None
        deadline = None if timeout is None else self._clock() + max(0.0, float(timeout))
        with self._condition:
            matches = self._matching(provider, model, project_id, key_id)
            if not matches:
                raise CredentialUnavailable("no matching runtime credential")
            while True:
                self._check_cancel(cancel_event)
                now = self._clock()
                self._prune_scopes(now)
                candidate = self._select(matches, now)
                if candidate is not None:
                    state, scope = candidate
                    state.active = True
                    state.lease_token = uuid4().hex
                    scope.calls.append(now)
                    return CredentialLease(self, state, state.lease_token)
                if not wait:
                    raise CredentialUnavailable("matching credentials are unavailable")
                remaining = None if deadline is None else deadline - now
                if remaining is not None and remaining <= 0:
                    raise CredentialUnavailable("timed out waiting for a runtime credential")
                wait_for = self._next_wait(matches, now)
                if remaining is not None:
                    wait_for = min(wait_for, remaining)
                self._condition.wait(max(0.01, wait_for))

    def wait_until_available(
        self,
        provider: str,
        model: str | None = None,
        *,
        project_id: str | None = None,
        key_id: str | None = None,
        timeout: float | None = None,
        cancel_event: Any = None,
    ) -> bool:
        """Wait without reserving a lease; cancellation raises ``AcquireCancelled``."""

        provider = self._clean(provider)
        model = self._clean(model) if model is not None else None
        key_id = self._clean(key_id) if key_id is not None else None
        deadline = None if timeout is None else self._clock() + max(0.0, float(timeout))
        with self._condition:
            matches = self._matching(provider, model, project_id, key_id)
            if not matches:
                raise CredentialUnavailable("no matching runtime credential")
            while True:
                self._check_cancel(cancel_event)
                now = self._clock()
                self._prune_scopes(now)
                if self._select(matches, now) is not None:
                    return True
                remaining = None if deadline is None else deadline - now
                if remaining is not None and remaining <= 0:
                    return False
                wait_for = self._next_wait(matches, now)
                if remaining is not None:
                    wait_for = min(wait_for, remaining)
                self._condition.wait(max(0.01, wait_for))

    wait_for_available = wait_until_available

    def retry_after(
        self,
        provider: str,
        model: str | None = None,
        *,
        project_id: str | None = None,
        key_id: str | None = None,
    ) -> float | None:
        """Return a bounded estimate until a matching lease can be acquired.

        This is intentionally metadata-only: it never exposes credential
        secrets and does not reserve a lease.  ``None`` means no matching
        credential exists or every matching credential is quarantined/active
        with no deterministic wake-up time.
        """

        provider = self._clean(provider)
        model = self._clean(model) if model is not None else None
        key_id = self._clean(key_id) if key_id is not None else None
        with self._condition:
            matches = self._matching(provider, model, project_id, key_id)
            if not matches:
                return None
            now = self._clock()
            self._prune_scopes(now)
            waits: list[float] = []
            for state in matches:
                if state.quarantined:
                    continue
                if state.cooldown_until > now:
                    waits.append(state.cooldown_until - now)
                scope = self._scopes.setdefault(self._scope_for(state.credential), _QuotaState())
                if scope.cooldown_until > now:
                    waits.append(scope.cooldown_until - now)
                elif self.quota_limit is not None and scope.calls:
                    waits.append(max(0.01, scope.calls[0] + self.quota_window_seconds - now))
                elif not state.active:
                    return 0.0
            return max(0.0, min(waits)) if waits else None

    def release(
        self,
        lease: CredentialLease,
        *,
        outcome: str | None = None,
        status_code: int | None = None,
        retry_after: Any = None,
        error: BaseException | None = None,
        ambiguous: bool = False,
    ) -> None:
        if not isinstance(lease, CredentialLease) or lease._pool is not self:
            raise InvalidLease("lease does not belong to this pool")
        with self._condition:
            state = self._states.get(lease._identity)
            if state is None or not state.active or state.lease_token != lease._token or lease._released:
                raise InvalidLease("lease is no longer active")
            classification = self._classify(outcome, status_code, error, ambiguous)
            now = self._clock()
            scope = self._scope_for(state.credential)
            quota = self._scopes.setdefault(scope, _QuotaState())
            state.active = False
            state.lease_token = None
            state.last_outcome = classification
            lease._released = True
            if classification in {"unauthorized", "forbidden"}:
                state.quarantined = True
                state.cooldown_until = 0.0
                state.backoff_level = 0
                state.backoff_seconds = 0.0
            elif classification == "rate_limited":
                delay = parse_retry_after(retry_after)
                if delay is None:
                    delay = self.rate_limit_cooldown
                quota.cooldown_until = max(quota.cooldown_until, now + delay)
            elif classification == "server_error":
                state.backoff_level += 1
                delay = min(
                    self.server_error_backoff_max,
                    self.server_error_backoff_base * (2 ** (state.backoff_level - 1)),
                )
                state.backoff_seconds = delay
                state.cooldown_until = max(state.cooldown_until, now + delay)
            elif classification == "success":
                state.backoff_level = 0
                state.backoff_seconds = 0.0
                state.cooldown_until = 0.0
            self._condition.notify_all()

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        """Return safe, non-secret state metadata."""

        with self._condition:
            now = self._clock()
            self._prune_scopes(now)
            snapshots = []
            for identity in sorted(self._states):
                state = self._states[identity]
                quota = self._scopes.get(self._scope_for(state.credential), _QuotaState())
                scope_remaining = max(0.0, quota.cooldown_until - now)
                credential_remaining = max(0.0, state.cooldown_until - now)
                if state.quarantined:
                    status = "quarantined"
                elif state.active:
                    status = "leased"
                elif scope_remaining:
                    status = "cooldown"
                elif credential_remaining:
                    status = "backoff"
                else:
                    status = "ready"
                snapshots.append(
                    {
                        "provider": state.credential.provider,
                        "key_id": state.credential.key_id,
                        "model": state.credential.model,
                        "project_id": state.credential.project_id,
                        "quota_scope": self._scope_label(state.credential),
                        "status": status,
                        "active": state.active,
                        "quarantined": state.quarantined,
                        "cooldown_remaining": scope_remaining,
                        "backoff_seconds": state.backoff_seconds,
                        "backoff_level": state.backoff_level,
                        "last_outcome": state.last_outcome,
                        "rolling_calls": len(quota.calls),
                    }
                )
            return tuple(snapshots)

    def __repr__(self) -> str:
        with self._condition:
            return f"RuntimeCredentialPool(credentials={len(self._states)})"

    @staticmethod
    def _clean(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    @classmethod
    def _validate_identity(cls, provider: Any, key_id: Any, model: Any) -> tuple[str, str, str]:
        provider, key_id, model = cls._clean(provider), cls._clean(key_id), cls._clean(model)
        if not provider or not key_id or not model:
            raise ValueError("provider, key_id, and model are required")
        return provider, key_id, model

    def _scope_for(self, credential: RuntimeCredential) -> tuple[Any, ...]:
        if credential.quota_scope:
            return ("custom", credential.provider, credential.model, credential.quota_scope)
        return ("project", credential.provider, credential.project_id, credential.model)

    def _scope_label(self, credential: RuntimeCredential) -> str:
        scope = self._scope_for(credential)
        return ":".join("" if value is None else str(value) for value in scope)

    def _matching(
        self, provider: str, model: str | None, project_id: str | None, key_id: str | None
    ) -> list[_CredentialState]:
        return [
            state
            for state in self._states.values()
            if state.credential.provider == provider
            and (model is None or state.credential.model == model)
            and (project_id is None or state.credential.project_id == project_id)
            and (key_id is None or state.credential.key_id == key_id)
        ]

    def _select(self, matches: list[_CredentialState], now: float) -> tuple[_CredentialState, _QuotaState] | None:
        if not matches:
            return None
        ordered = matches[self._round_robin % len(matches) :] + matches[: self._round_robin % len(matches)]
        for state in ordered:
            if state.active or state.quarantined or state.cooldown_until > now:
                continue
            scope = self._scopes.setdefault(self._scope_for(state.credential), _QuotaState())
            if scope.cooldown_until > now:
                continue
            if self.quota_limit is not None and len(scope.calls) >= int(self.quota_limit):
                continue
            self._round_robin = (self._round_robin + 1) % max(1, len(matches))
            return state, scope
        return None

    def _next_wait(self, matches: list[_CredentialState], now: float) -> float:
        waits = [0.5]
        for state in matches:
            if not state.active and not state.quarantined:
                if state.cooldown_until > now:
                    waits.append(state.cooldown_until - now)
                scope = self._scopes.setdefault(self._scope_for(state.credential), _QuotaState())
                if scope.cooldown_until > now:
                    waits.append(scope.cooldown_until - now)
                elif self.quota_limit is not None and scope.calls:
                    waits.append(max(0.01, scope.calls[0] + self.quota_window_seconds - now))
        return max(0.01, min(waits))

    def _prune_scopes(self, now: float) -> None:
        for scope in self._scopes.values():
            while scope.calls and scope.calls[0] + self.quota_window_seconds <= now:
                scope.calls.popleft()

    @staticmethod
    def _check_cancel(cancel_event: Any) -> None:
        if cancel_event is None:
            return
        is_set = getattr(cancel_event, "is_set", None)
        if callable(is_set):
            cancelled = is_set()
        elif callable(cancel_event):
            cancelled = cancel_event()
        else:
            cancelled = False
        if cancelled:
            raise AcquireCancelled("credential acquire was cancelled")

    @staticmethod
    def _classify(
        outcome: str | None, status_code: int | None, error: BaseException | None, ambiguous: bool
    ) -> str:
        if ambiguous:
            return "ambiguous"
        if outcome:
            normalized = str(outcome).strip().lower().replace("-", "_")
            if normalized in {"success", "ok", "completed"}:
                return "success"
            if normalized in {"timeout", "timed_out"}:
                return "timeout"
            if normalized in {"ambiguous", "uncertain"}:
                return "ambiguous"
            if normalized in {"rate_limited", "ratelimited", "429"}:
                return "rate_limited"
            if normalized in {"unauthorized", "401"}:
                return "unauthorized"
            if normalized in {"forbidden", "403"}:
                return "forbidden"
            if normalized in {"server_error", "5xx", "server"}:
                return "server_error"
            return "provider_error"
        if error is not None:
            if isinstance(error, TimeoutError):
                return "timeout"
            status_code = getattr(error, "code", status_code)
        if isinstance(status_code, int):
            if status_code == 401:
                return "unauthorized"
            if status_code == 403:
                return "forbidden"
            if status_code == 429:
                return "rate_limited"
            if 500 <= status_code <= 599:
                return "server_error"
            if 200 <= status_code <= 399:
                return "success"
            return "provider_error"
        return "success"


CredentialPool = RuntimeCredentialPool
Lease = CredentialLease

__all__ = [
    "AcquireCancelled",
    "CredentialLease",
    "CredentialPool",
    "CredentialUnavailable",
    "InvalidLease",
    "Lease",
    "RuntimeCredential",
    "RuntimeCredentialError",
    "RuntimeCredentialPool",
    "parse_retry_after",
]
