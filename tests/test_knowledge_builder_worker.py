import hashlib
import json
import threading
import time

import pytest

from knowledge_builder_worker import KnowledgeBuildError, KnowledgeBuildWorker


SOURCE_URL = "https://example.com/knowledge"
SOURCE_ID = hashlib.sha256(SOURCE_URL.encode("utf-8")).hexdigest()[:16]
SOURCE_CONTENT = "A bounded trusted source."
SOURCE_HASH = hashlib.sha256(SOURCE_CONTENT.encode("utf-8")).hexdigest()


def draft():
    return {
        "schema_version": 1,
        "status": "draft",
        "title": "Work",
        "query": "Work",
        "created_at": "2026-08-03T04:00:00+00:00",
        "sources": [
            {
                "source_id": SOURCE_ID,
                "url": SOURCE_URL,
                "title": "Official source",
                "snippet": "A bounded snippet.",
                "status": "read",
                "fetched_at": "2026-08-03T04:00:00+00:00",
                "content": SOURCE_CONTENT,
                "content_sha256": SOURCE_HASH,
                "error": "",
            }
        ],
        "entries": [],
        "review": {
            "owner_confirmed": False,
            "approver": None,
            "approved_at": None,
        },
    }


def extraction_payload():
    return {
        "schema_version": 1,
        "title": "Work",
        "aliases": [],
        "entries": [
            {
                "name": "Hero",
                "aliases": [],
                "kind": "character",
                "description": "A bounded candidate.",
                "confidence": 0.9,
                "source_ids": [SOURCE_ID],
            }
        ],
    }


class RecordingStore:
    def __init__(self):
        self.calls = []

    def save_pack(self, title, **kwargs):
        self.calls.append((title, kwargs))
        return {"pack_id": kwargs.get("pack_id") or "generated", "revision": 1}

    def save_pack_non_active(self, title, **kwargs):
        return self.save_pack(title, **kwargs)


def test_worker_builds_candidate_without_activation():
    progress = []
    finished = []
    errors = []
    store = RecordingStore()

    worker = KnowledgeBuildWorker(
        research_builder=lambda cancel: draft(),
        extractor=lambda research, cancel: json.dumps(extraction_payload()),
        store=store,
        on_progress=progress.append,
        on_finished=finished.append,
        on_error=lambda job_id, error: errors.append((job_id, error)),
    )
    job_id = worker.start()
    worker.wait_for_all(2)

    assert not worker.is_running()
    assert errors == []
    assert len(finished) == 1
    result = finished[0]
    assert result.job_id == job_id
    assert result.candidate["status"] == "candidate"
    assert result.candidate["owner_confirmed"] is False
    assert [item.stage for item in progress] == ["research", "extraction", "merge", "ready"]
    assert store.calls == []


def test_promote_requires_confirmation_and_never_activates():
    store = RecordingStore()
    finished = []
    worker = KnowledgeBuildWorker(
        research_builder=lambda cancel: draft(),
        extractor=lambda research, cancel: extraction_payload(),
        store=store,
        on_finished=finished.append,
    )
    worker.start()
    worker.wait_for_all(2)
    result = finished[0]

    with pytest.raises(KnowledgeBuildError, match="confirmation"):
        worker.promote(result, owner_confirmed=False)

    saved = worker.promote(result, owner_confirmed=True, pack_id="work")
    assert saved["pack_id"] == "work"
    assert store.calls[0][0] == "Work"
    assert store.calls[0][1]["entries"][0]["name"] == "Hero"


def test_cancel_suppresses_finished_and_reports_cancelled():
    started = threading.Event()
    cancelled = []
    finished = []
    errors = []

    def slow_research(cancel_event):
        started.set()
        cancel_event.wait(2)
        return draft()

    worker = KnowledgeBuildWorker(
        research_builder=slow_research,
        extractor=lambda research, cancel: extraction_payload(),
        on_finished=finished.append,
        on_error=lambda job_id, error: errors.append((job_id, error)),
        on_cancelled=cancelled.append,
    )
    job_id = worker.start()
    assert started.wait(1)
    assert worker.cancel() is True
    worker.wait_for_all(2)

    assert cancelled == [job_id]
    assert finished == []
    assert errors == []


def test_restart_invalidates_callbacks_from_previous_generation():
    first_started = threading.Event()
    calls = {"count": 0}
    progress = []
    finished = []

    def research(cancel_event):
        calls["count"] += 1
        if calls["count"] == 1:
            first_started.set()
            while not cancel_event.is_set():
                time.sleep(0.005)
        return draft()

    worker = KnowledgeBuildWorker(
        research_builder=research,
        extractor=lambda research, cancel: extraction_payload(),
        on_progress=progress.append,
        on_finished=finished.append,
    )
    first_job = worker.start()
    assert first_started.wait(1)
    progress_before_restart = len(progress)
    second_job = worker.start()
    worker.wait_for_all(2)

    assert first_job != second_job
    assert len(finished) == 1
    assert finished[0].job_id == second_job
    assert all(item.job_id == second_job for item in progress[progress_before_restart:])

def test_result_from_previous_job_cannot_be_promoted():
    store = RecordingStore()
    finished = []
    worker = KnowledgeBuildWorker(
        research_builder=lambda cancel: draft(),
        extractor=lambda research, cancel: extraction_payload(),
        store=store,
        on_finished=finished.append,
    )
    worker.start()
    worker.wait_for_all(2)
    old_result = finished[-1]
    worker.start()
    worker.wait_for_all(2)

    with pytest.raises(KnowledgeBuildError, match='stale'):
        worker.promote(old_result, owner_confirmed=True)

def test_promote_uses_internal_snapshot_and_rejects_duplicate_promote():
    store = RecordingStore()
    finished = []
    worker = KnowledgeBuildWorker(
        research_builder=lambda cancel: draft(),
        extractor=lambda research, cancel: extraction_payload(),
        store=store,
        on_finished=finished.append,
    )
    worker.start()
    worker.wait_for_all(2)
    result = finished[0]
    result.candidate['entries'][0]['description'] = 'tampered'

    saved = worker.promote(result, owner_confirmed=True)
    assert saved['revision'] == 1
    assert store.calls[0][1]['entries'][0]['description'] == 'A bounded candidate.'
    with pytest.raises(KnowledgeBuildError, match='already'):
        worker.promote(result, owner_confirmed=True)

    cached = worker.last_result
    cached.candidate['entries'][0]['description'] = 'mutated copy'
    assert worker.last_result.candidate['entries'][0]['description'] == 'A bounded candidate.'

def test_extractor_receives_copy_and_cannot_change_source_allowlist():
    finished = []

    def mutating_extractor(research, cancel_event):
        research['sources'][0]['source_id'] = '0000000000000000'
        return extraction_payload()

    worker = KnowledgeBuildWorker(
        research_builder=lambda cancel: draft(),
        extractor=mutating_extractor,
        on_finished=finished.append,
    )
    worker.start()
    worker.wait_for_all(2)

    assert len(finished) == 1
    assert [entry['name'] for entry in finished[0].candidate['entries']] == ['Hero']


def test_exception_after_cancel_is_reported_as_cancelled():
    cancelled = []
    errors = []

    def cancelling_extractor(research, cancel_event):
        cancel_event.set()
        raise RuntimeError('late provider failure')

    worker = KnowledgeBuildWorker(
        research_builder=lambda cancel: draft(),
        extractor=cancelling_extractor,
        on_error=lambda job_id, error: errors.append(error),
        on_cancelled=cancelled.append,
    )
    job_id = worker.start()
    worker.wait_for_all(2)

    assert cancelled == [job_id]
    assert errors == []
def test_blocked_callback_does_not_block_control_plane():
    entered = threading.Event()
    release = threading.Event()
    cancel_completed = threading.Event()
    cancelled = []

    def blocking_progress(progress):
        if progress.stage == "research":
            entered.set()
            release.wait(2)

    worker = KnowledgeBuildWorker(
        research_builder=lambda cancel: draft(),
        extractor=lambda research, cancel: extraction_payload(),
        on_progress=blocking_progress,
        on_cancelled=cancelled.append,
    )
    job_id = worker.start()
    assert entered.wait(1)

    def cancel_worker():
        cancelled.append(worker.cancel())
        cancel_completed.set()

    threading.Thread(target=cancel_worker, daemon=True).start()
    assert cancel_completed.wait(0.5)
    release.set()
    worker.wait_for_all(2)

    assert cancelled == [True, job_id]