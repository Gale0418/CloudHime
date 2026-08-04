from dataclasses import FrozenInstanceError

import pytest

from scan_pipeline import (
    ScanErrorCode,
    ScanOutcome,
    ScanStage,
    ScanTrace,
    ScanTraceEvent,
    safe_exception_token,
)


def event(
    stage=ScanStage.CAPTURE,
    outcome=ScanOutcome.SUCCESS,
    error_code=ScanErrorCode.NONE,
    **kwargs,
):
    return ScanTraceEvent(
        stage=stage,
        outcome=outcome,
        error_code=error_code,
        **kwargs,
    )


def test_contract_values_are_frozen_and_slotted():
    item = event(detail="capture_ready")
    trace = ScanTrace()

    assert hasattr(item, "__slots__")
    assert hasattr(trace, "__slots__")
    with pytest.raises(FrozenInstanceError):
        item.detail = "mutated"
    with pytest.raises(FrozenInstanceError):
        trace.dropped_events = 1


def test_trace_append_is_immutable_and_bounded_to_64_events():
    trace = ScanTrace()
    for number in range(66):
        trace = trace.append(event(detail=f"capture_{number}"))

    assert len(trace.events) == 64
    assert trace.dropped_events == 2
    assert trace.events[0].detail == "capture_2"
    assert ScanTrace().events == ()


def test_event_fields_are_bounded_and_exception_token_is_class_only():
    item = event(
        detail="x" * 400,
        provider="provider_" + "x" * 400,
        fallback_reason="fallback_" + "x" * 400,
        exception=ValueError("do not expose this exception message"),
    )

    assert len(item.detail) <= 256
    assert len(item.provider) <= 128
    assert len(item.fallback_reason) <= 160
    assert item.exception_token == "ValueError"
    assert safe_exception_token(RuntimeError("api-key=not-for-trace")) == "RuntimeError"


def test_event_measurements_are_normalized_and_bounded():
    measured = event(elapsed_ms=12.75, item_count=3)
    invalid = event(elapsed_ms=float("nan"), item_count=-4)
    oversized = event(elapsed_ms=float("inf"), item_count=10_000_000)

    assert measured.elapsed_ms == 12.75
    assert measured.item_count == 3
    assert invalid.elapsed_ms == 0.0
    assert invalid.item_count == 0
    assert oversized.elapsed_ms == 0.0
    assert oversized.item_count == 1_000_000

def test_trace_redacts_raw_ocr_prompt_credentials_urls_and_image_bytes():
    ocr_text = "OCR_SECRET_TEXT_DO_NOT_LOG"
    prompt = "PROMPT_SECRET_TEXT_DO_NOT_LOG"
    api_key = "sk-super-secret-key"
    base_url = "https://provider.example/v1"
    image_bytes = b"\x89PNG\r\nprivate-image"
    item = event(
        stage=ScanStage.OCR,
        outcome=ScanOutcome.FAILURE,
        error_code=ScanErrorCode.OCR_FAILED,
        detail=f"{ocr_text} {prompt} {api_key} {base_url} {image_bytes!r}",
        provider=base_url,
        fallback_reason=prompt,
        exception=RuntimeError(f"{api_key}: network failure"),
    )
    rendered = repr(item)

    for secret in (ocr_text, prompt, api_key, base_url, "private-image", "network failure"):
        assert secret not in rendered
    assert item.detail == "redacted"
    assert item.provider == "redacted"
    assert item.fallback_reason == "redacted"
    assert item.error_code is ScanErrorCode.OCR_FAILED
    assert item.exception_token == "RuntimeError"


def test_successful_pipeline_trace_can_cover_all_stages():
    trace = ScanTrace()
    for stage in ScanStage:
        trace = trace.append(event(stage=stage, detail=f"{stage.value}_completed"))

    assert [item.stage for item in trace.events] == list(ScanStage)
    assert all(item.outcome is ScanOutcome.SUCCESS for item in trace.events)


def test_cache_hit_and_failure_traces_allow_stage_revisits_without_global_order():
    cache_hit = ScanTrace().append(
        event(ScanStage.CAPTURE, detail="capture_completed")
    ).append(
        event(ScanStage.FRAME_CACHE, ScanOutcome.HIT, detail="cache_hit")
    ).append(
        event(ScanStage.RENDER_DISPATCH, detail="render_dispatched")
    )
    failure = ScanTrace().append(
        event(ScanStage.OCR, ScanOutcome.FAILURE, ScanErrorCode.OCR_FAILED, exception=TimeoutError())
    ).append(
        event(
            ScanStage.OCR,
            ScanOutcome.FALLBACK,
            fallback_reason="backend_timeout",
        )
    ).append(event(ScanStage.OCR, ScanOutcome.NO_TEXT, detail="no_text"))

    assert [item.outcome for item in cache_hit.events] == [
        ScanOutcome.SUCCESS,
        ScanOutcome.HIT,
        ScanOutcome.SUCCESS,
    ]
    assert [item.stage for item in failure.events] == [ScanStage.OCR] * 3
    assert failure.events[0].error_code is ScanErrorCode.OCR_FAILED

def test_cancellation_is_representable_without_unbounded_details():
    trace = ScanTrace().append(
        event(
            ScanStage.FRAME_CACHE,
            ScanOutcome.CANCELLED,
            error_code=ScanErrorCode.SCAN_CANCELLED,
            detail="pipeline_cancelled",
        )
    )

    assert trace.events[0].outcome is ScanOutcome.CANCELLED
    assert trace.events[0].error_code is ScanErrorCode.SCAN_CANCELLED
    assert trace.events[0].detail == "pipeline_cancelled"


def test_uppercase_ocr_like_detail_is_redacted():
    item = event(
        stage=ScanStage.OCR,
        outcome=ScanOutcome.FAILURE,
        detail="OCR_SECRET_TEXT_DO_NOT_LOG",
    )

    assert item.detail == "redacted"
