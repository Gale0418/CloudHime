"""Cancellable Knowledge Pack builder orchestration without UI or network policy."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Iterable, Mapping, Protocol
import uuid

from knowledge_extraction import (
    ExtractionValidationError,
    merge_extraction_candidates,
    parse_extraction_response,
)
from knowledge_pack_store import KnowledgePackStore
from knowledge_research_draft import validate_research_draft


class KnowledgeBuildError(RuntimeError):
    """Raised when a Knowledge Pack build cannot complete safely."""


class KnowledgeBuildCancelled(KnowledgeBuildError):
    """Raised internally when the current build was cancelled."""


class ResearchBuilder(Protocol):
    def __call__(self, cancel_event: threading.Event) -> Mapping[str, Any]:
        """Build and return one validated-or-validation-ready research draft."""


class CandidateExtractor(Protocol):
    def __call__(self, draft: Mapping[str, Any], cancel_event: threading.Event) -> Any:
        """Return one JSON response, object, or iterable of either."""


@dataclass(frozen=True, slots=True)
class BuildProgress:
    job_id: str
    stage: str
    percent: int
    detail: str = ""


@dataclass(frozen=True, slots=True)
class KnowledgeBuildResult:
    job_id: str
    research_draft: dict[str, Any]
    candidate: dict[str, Any]


ProgressCallback = Callable[[BuildProgress], None]
FinishedCallback = Callable[[KnowledgeBuildResult], None]
ErrorCallback = Callable[[str, Exception], None]
CancelledCallback = Callable[[str], None]


def _candidate_payloads(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, (str, bytes)):
        return [parse_extraction_response(value)]
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Iterable):
        payloads: list[dict[str, Any]] = []
        for item in value:
            payloads.extend(_candidate_payloads(item))
        return payloads
    raise ExtractionValidationError("extractor output must be JSON text or object")


def _read_source_ids(draft: Mapping[str, Any]) -> list[str]:
    return [
        source["source_id"]
        for source in draft["sources"]
        if source.get("status") == "read"
    ]


def _clone_result(result: KnowledgeBuildResult) -> KnowledgeBuildResult:
    return KnowledgeBuildResult(
        result.job_id,
        deepcopy(result.research_draft),
        deepcopy(result.candidate),
    )


class KnowledgeBuildWorker:
    """Run research and candidate extraction in a cancellable background thread.

    A new start invalidates callbacks from the previous generation. The worker only
    creates a non-active candidate; explicit owner confirmation is required before
    ``promote`` writes a pack through the store's atomic persistence path.
    """

    def __init__(
        self,
        *,
        research_builder: ResearchBuilder,
        extractor: CandidateExtractor,
        store: KnowledgePackStore | None = None,
        on_progress: ProgressCallback | None = None,
        on_finished: FinishedCallback | None = None,
        on_error: ErrorCallback | None = None,
        on_cancelled: CancelledCallback | None = None,
    ):
        self._research_builder = research_builder
        self._extractor = extractor
        self._store = store
        self._on_progress = on_progress
        self._on_finished = on_finished
        self._on_error = on_error
        self._on_cancelled = on_cancelled
        self._lock = threading.RLock()
        self._callback_lock = threading.RLock()
        self._generation = 0
        self._current_job_id: str | None = None
        self._current_cancel_event: threading.Event | None = None
        self._current_thread: threading.Thread | None = None
        self._threads: set[threading.Thread] = set()
        self._last_result: KnowledgeBuildResult | None = None
        self._promoted_job_ids: set[str] = set()

    @property
    def current_job_id(self) -> str | None:
        with self._lock:
            return self._current_job_id

    @property
    def last_result(self) -> KnowledgeBuildResult | None:
        with self._lock:
            return None if self._last_result is None else _clone_result(self._last_result)

    def is_running(self) -> bool:
        with self._lock:
            return self._current_thread is not None and self._current_thread.is_alive()

    def start(self) -> str:
        with self._lock:
            if self._current_cancel_event is not None:
                self._current_cancel_event.set()
            self._generation += 1
            generation = self._generation
            job_id = uuid.uuid4().hex
            cancel_event = threading.Event()
            thread = threading.Thread(
                target=self._run,
                args=(generation, job_id, cancel_event),
                name=f"CloudHime-KnowledgeBuild-{job_id[:8]}",
                daemon=True,
            )
            self._current_job_id = job_id
            self._current_cancel_event = cancel_event
            self._current_thread = thread
            self._last_result = None
            self._promoted_job_ids.clear()
            self._threads.add(thread)
            thread.start()
            return job_id

    def cancel(self) -> bool:
        with self._lock:
            event = self._current_cancel_event
            running = self._current_thread is not None and self._current_thread.is_alive()
        if event is None or not running:
            return False
        event.set()
        return True

    def wait(self, timeout: float | None = None) -> None:
        with self._lock:
            thread = self._current_thread
        if thread is not None:
            thread.join(timeout)

    def wait_for_all(self, timeout: float | None = None) -> None:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                threads = tuple(self._threads)
            if not threads:
                return
            for thread in threads:
                remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
                thread.join(remaining)
            if deadline is not None and time.monotonic() >= deadline:
                return

    def promote(
        self,
        result: KnowledgeBuildResult,
        *,
        owner_confirmed: bool,
        pack_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist a confirmed, non-active pack; never activates it implicitly."""
        if type(owner_confirmed) is not bool or not owner_confirmed:
            raise KnowledgeBuildError("owner confirmation is required before promotion")
        if self._store is None:
            raise KnowledgeBuildError("Knowledge Pack store is not configured")
        with self._lock:
            if not isinstance(result, KnowledgeBuildResult):
                raise KnowledgeBuildError("build result is invalid")
            if result.job_id != self._current_job_id or self._last_result is None:
                raise KnowledgeBuildError("build result is stale")
            if result.job_id in self._promoted_job_ids:
                raise KnowledgeBuildError("build result was already promoted")
            snapshot = _clone_result(self._last_result)
            candidate = snapshot.candidate
            if candidate.get("status") != "candidate" or candidate.get("owner_confirmed") is not False:
                raise KnowledgeBuildError("candidate activation boundary is invalid")
            aliases = [
                item["text"]
                for item in candidate.get("aliases", [])
                if isinstance(item, Mapping) and isinstance(item.get("text"), str)
            ]
            saved = self._store.save_pack_non_active(
                snapshot.research_draft["title"],
                aliases=aliases,
                entries=candidate.get("entries", []),
                sources=snapshot.research_draft.get("sources", []),
                pack_id=pack_id,
            )
            self._promoted_job_ids.add(result.job_id)
            return saved

    def _dispatch(
        self,
        generation: int,
        cancel_event: threading.Event,
        callback: Callable[..., None] | None,
        *args: Any,
        allow_cancelled: bool = False,
    ) -> bool:
        """Linearize generation checks, then deliver outside the state lock."""
        with self._callback_lock:
            with self._lock:
                if generation != self._generation:
                    return False
                if cancel_event.is_set() and not allow_cancelled:
                    return False
            self._safe_callback(callback, *args)
            return True

    def _safe_callback(self, callback: Callable[..., None] | None, *args: Any) -> None:
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:
            # UI callbacks must never kill the builder thread or alter persistence.
            return

    def _progress(self, generation: int, progress: BuildProgress, cancel_event: threading.Event) -> bool:
        return self._dispatch(generation, cancel_event, self._on_progress, progress)

    def _check_cancelled(self, cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            raise KnowledgeBuildCancelled("Knowledge Pack build cancelled")

    def _finish(
        self,
        generation: int,
        cancel_event: threading.Event,
        result: KnowledgeBuildResult,
    ) -> None:
        with self._callback_lock:
            with self._lock:
                if generation != self._generation or cancel_event.is_set():
                    return
                self._last_result = _clone_result(result)
                snapshot = _clone_result(self._last_result)
            self._safe_callback(self._on_finished, snapshot)

    def _run(
        self,
        generation: int,
        job_id: str,
        cancel_event: threading.Event,
    ) -> None:
        thread = threading.current_thread()
        try:
            self._progress(generation, BuildProgress(job_id, "research", 0), cancel_event)
            draft = validate_research_draft(self._research_builder(cancel_event))
            self._check_cancelled(cancel_event)

            self._progress(generation, BuildProgress(job_id, "extraction", 35), cancel_event)
            payloads = _candidate_payloads(self._extractor(deepcopy(draft), cancel_event))
            self._check_cancelled(cancel_event)

            self._progress(generation, BuildProgress(job_id, "merge", 70), cancel_event)
            candidate = merge_extraction_candidates(
                payloads,
                allowed_source_ids=_read_source_ids(draft),
                expected_title=draft["title"],
            )
            self._check_cancelled(cancel_event)
            result = KnowledgeBuildResult(job_id, draft, candidate)
            self._progress(generation, BuildProgress(job_id, "ready", 100), cancel_event)
            self._finish(generation, cancel_event, result)
        except KnowledgeBuildCancelled:
            self._dispatch(
                generation,
                cancel_event,
                self._on_progress,
                BuildProgress(job_id, "cancelled", 0),
                allow_cancelled=True,
            )
            self._dispatch(
                generation,
                cancel_event,
                self._on_cancelled,
                job_id,
                allow_cancelled=True,
            )
        except Exception as exc:
            if cancel_event.is_set():
                self._dispatch(
                    generation,
                    cancel_event,
                    self._on_progress,
                    BuildProgress(job_id, "cancelled", 0),
                    allow_cancelled=True,
                )
                self._dispatch(
                    generation,
                    cancel_event,
                    self._on_cancelled,
                    job_id,
                    allow_cancelled=True,
                )
            else:
                self._dispatch(
                    generation,
                    cancel_event,
                    self._on_progress,
                    BuildProgress(job_id, "failed", 0, type(exc).__name__),
                    allow_cancelled=True,
                )
                self._dispatch(
                    generation,
                    cancel_event,
                    self._on_error,
                    job_id,
                    exc,
                    allow_cancelled=True,
                )
        finally:
            with self._lock:
                self._threads.discard(thread)
                if generation == self._generation:
                    self._current_thread = None
                    self._current_cancel_event = None