from provider_health import assess_provider_health


def _health(**overrides):
    values = {
        "ui_language": "en",
        "ai_requested": True,
        "ai_enabled": True,
        "model_id": "gemma-3-4b-it-local",
        "model_label": "Gemma Local",
        "has_api_key": False,
        "local_multimodal_enabled": True,
        "embedded_runtime_available": True,
        "local_vision_state": "stopped",
        "local_vision_detail": "",
        "local_vision_mode": "",
        "local_model_state": "stopped",
        "local_model_detail": "",
        "local_text_ready": False,
        "model_assets_present": False,
    }
    values.update(overrides)
    return assess_provider_health(**values)


def test_google_translate_is_ready_without_api_key():
    health = _health(ai_requested=False, ai_enabled=False, model_id="gemma-3-27b-it")

    assert health.code == "google_ready"
    assert "No API key" in health.detail


def test_remote_ai_distinguishes_missing_key_from_configured():
    missing = _health(model_id="gemma-3-27b-it", model_label="Gemma Remote", has_api_key=False)
    configured = _health(model_id="gemma-3-27b-it", model_label="Gemma Remote", has_api_key=True)

    assert missing.code == "remote_key_required"
    assert "Google API key" in missing.detail
    assert configured.code == "remote_configured"
    assert "Connectivity is checked" in configured.detail
    assert "Ready" not in configured.summary


def test_local_download_onboarding_needs_no_external_runtime_setup():
    health = _health(ui_language="zh-TW")

    assert health.code == "local_download_required"
    assert "AppData" in health.detail
    assert "Ollama" in health.detail
    assert "Python" in health.detail
    assert "Conda" in health.detail
    assert "pip" in health.detail


def test_local_progress_reports_phase_and_percent():
    health = _health(local_vision_state="progress", local_vision_detail="40|downloading")

    assert health.code == "local_progress"
    assert "Downloading local Gemma" in health.summary
    assert "40%" in health.summary


def test_local_gpu_and_cpu_ready_are_distinct():
    gpu = _health(local_vision_state="ready", local_vision_mode="gpu", model_assets_present=True)
    cpu = _health(local_vision_state="ready", local_vision_mode="cpu", model_assets_present=True)

    assert gpu.code == "local_ready_gpu"
    assert "GPU acceleration" in gpu.detail
    assert cpu.code == "local_ready_cpu"
    assert cpu.tone == "warning"
    assert "available but slower" in cpu.detail


def test_local_timeout_is_actionable_without_exposing_raw_stderr():
    detail = "health_timeout: PRIVATE CUDA STACK AND USER TEXT"
    health = _health(local_vision_state="failed", local_vision_detail=detail)

    assert health.code == "local_failed"
    assert "Close GPU-heavy apps" in health.detail
    assert "CPU fallback" in health.detail
    assert "PRIVATE" not in health.detail
    assert "USER TEXT" not in health.detail


def test_cpu_progress_uses_cpu_label():
    health = _health(
        local_vision_state="progress",
        local_vision_mode="cpu",
        local_vision_detail="70|initializing",
    )

    assert health.code == "local_progress"
    assert "Initializing CPU" in health.summary

def test_missing_embedded_runtime_requests_repair():
    health = _health(embedded_runtime_available=False)

    assert health.code == "local_runtime_missing"
    assert "reinstall CloudHime" in health.detail


def test_assets_present_wait_for_automatic_start():
    health = _health(model_assets_present=True)

    assert health.code == "local_start_pending"
    assert "start automatically" in health.detail

def test_missing_server_is_repair_not_model_download():
    health = _health(
        local_vision_state="missing",
        local_vision_detail="runtime/llama-server.exe",
    )

    assert health.code == "local_runtime_missing"
    assert "reinstall CloudHime" in health.detail


def test_ready_local_text_provider_does_not_require_vision_runtime():
    health = _health(
        local_multimodal_enabled=False,
        embedded_runtime_available=False,
        local_model_state="ready",
        local_text_ready=True,
    )

    assert health.code == "local_ready"

def test_local_text_without_vision_runtime_still_offers_managed_download():
    health = _health(
        local_multimodal_enabled=False,
        embedded_runtime_available=False,
        local_model_state="stopped",
        local_text_ready=False,
        model_assets_present=False,
    )

    assert health.code == "local_download_required"
