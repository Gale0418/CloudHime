import pytest

from provider_health import assess_provider_health, local_model_failure_message


@pytest.mark.parametrize("language, guidance", [("en", "download"), ("zh-TW", "下載"), ("ja", "ダウンロード")])
def test_missing_model_is_download_guidance_instead_of_verification_failure(language, guidance):
    message = local_model_failure_message("model_missing", language)
    assert guidance in message
    assert message != local_model_failure_message("asset_hash_failed", language)


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
    assert "Connectivity" in configured.detail
    assert "checked when translation starts" in configured.detail
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
    assert "Close heavy background apps" in health.detail
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

def test_text_progress_ignores_vision_mode():
    health = _health(
        local_multimodal_enabled=False,
        local_model_state="progress",
        local_model_detail="70|initializing",
        local_vision_mode="cpu",
    )

    assert health.code == "local_progress"
    without_vision_mode = _health(
        local_multimodal_enabled=False,
        local_model_state="progress",
        local_model_detail="70|initializing",
    )
    assert health.summary == without_vision_mode.summary
    assert "Initializing inference runtime" in health.summary
    assert "70%" in health.summary

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


@pytest.mark.parametrize(
    ("overrides", "expected_code", "summary_text", "detail_text"),
    [
        (
            {"ai_requested": False, "ai_enabled": False, "model_id": "gemma-3-27b-it"},
            "google_ready",
            "Google 翻訳",
            "API キーは不要",
        ),
        (
            {"model_id": "gemma-3-27b-it", "has_api_key": False},
            "remote_key_required",
            "設定が必要",
            "Google API キー",
        ),
        (
            {"model_id": "gemma-3-27b-it", "has_api_key": True},
            "remote_configured",
            "設定済み",
            "翻訳開始時",
        ),
        (
            {"local_vision_state": "progress", "local_vision_detail": "38|downloading"},
            "local_progress",
            "38%",
            "Ollama",
        ),
        (
            {"local_vision_state": "starting"},
            "local_loading",
            "読み込み中",
            "ウォームアップ",
        ),
        (
            {"local_vision_state": "failed", "local_vision_detail": "health_timeout"},
            "local_failed",
            "起動失敗",
            "タイムアウト",
        ),
        (
            {"embedded_runtime_available": False},
            "local_runtime_missing",
            "修復が必要",
            "再インストール",
        ),
        (
            {"local_vision_state": "ready", "local_vision_mode": "cpu"},
            "local_ready_cpu",
            "CPU で利用可能",
            "処理に時間がかかります",
        ),
        (
            {"local_vision_state": "ready", "local_vision_mode": "gpu"},
            "local_ready_gpu",
            "利用可能",
            "GPU アクセラレーション",
        ),
        (
            {"model_assets_present": True},
            "local_start_pending",
            "準備中",
            "自動的に起動",
        ),
        (
            {},
            "local_download_required",
            "ダウンロードが必要",
            "AppData",
        ),
    ],
)
def test_japanese_health_states_localize_without_changing_state_or_tone(
    overrides, expected_code, summary_text, detail_text
):
    japanese = _health(ui_language="ja", **overrides)
    english = _health(ui_language="en", **overrides)

    assert japanese.code == expected_code
    assert japanese.code == english.code
    assert japanese.tone == english.tone
    assert summary_text in japanese.summary
    assert detail_text in japanese.detail
    if expected_code != "google_ready":
        assert "Gemma Local" in japanese.summary


@pytest.mark.parametrize(
    ("phase", "mode", "expected"),
    [
        ("checking_disk", "", "ディスクの空き容量を確認中"),
        ("checking_assets", "", "モデルファイルを確認中"),
        ("downloading", "", "ローカル Gemma をダウンロード中"),
        ("verifying", "", "ローカル Gemma を検証中"),
        ("loading_model", "", "ローカル Gemma を読み込み中"),
        ("loading_tensors", "", "モデルの重みを読み込み中"),
        ("initializing", "gpu", "推論環境を初期化中"),
        ("initializing", "cpu", "CPU を初期化中"),
        ("warming_up", "", "ローカル Gemma をウォームアップ中"),
        ("model_loaded", "", "ローカルサービスを確認中"),
        ("starting_server", "", "内蔵ランタイムを起動中"),
        ("unknown_phase", "", "ローカル Gemma を準備中"),
    ],
)
def test_japanese_progress_localizes_phase_and_preserves_percent(phase, mode, expected):
    japanese = _health(
        ui_language="ja",
        local_vision_state="progress",
        local_vision_mode=mode,
        local_vision_detail=f"73|{phase}",
    )
    english = _health(
        ui_language="en",
        local_vision_state="progress",
        local_vision_mode=mode,
        local_vision_detail=f"73|{phase}",
    )

    assert japanese.code == "local_progress"
    assert japanese.tone == english.tone
    assert expected in japanese.summary
    assert "73%" in japanese.summary
    assert "Gemma Local" in japanese.summary


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ("CUDA out of memory", "負荷の高いアプリ"),
        ("health_timeout", "タイムアウトしました"),
        ("asset_hash_mismatch", "破損ファイル"),
        ("runtime_missing", "内蔵推論ランタイム"),
        ("port_unavailable", "ループバックポート"),
        ("unknown_failure", "Google 翻訳は引き続き利用できます"),
    ],
)
def test_japanese_failure_guidance_is_actionable_and_does_not_echo_detail(detail, expected):
    health = _health(
        ui_language="ja",
        local_vision_state="failed",
        local_vision_detail=f"{detail}: PRIVATE USER TEXT",
    )

    assert health.code == "local_failed"
    assert expected in health.detail
    assert "PRIVATE USER TEXT" not in health.detail
