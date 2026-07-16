from __future__ import annotations

from dataclasses import dataclass

LOCAL_MODEL_IDS = frozenset({"gemma-3-4b-it-local", "translategemma-4b-it-local"})


@dataclass(frozen=True)
class ProviderHealth:
    code: str
    summary: str
    detail: str
    tone: str


def _is_english(ui_language: str) -> bool:
    return str(ui_language or "").lower().replace("_", "-").split("-", 1)[0] == "en"


def _pick(english: bool, en: str, zh: str) -> str:
    return en if english else zh


def _local_setup_note(english: bool) -> str:
    return _pick(
        english,
        "CloudHime manages this model. No Ollama, Python, Conda, or pip setup is required.",
        "CloudHime 會管理此模型，不需 Ollama、Python、Conda 或 pip。",
    )


def _failure_guidance(detail: str, english: bool) -> str:
    code = str(detail or "").lower()
    if "timeout" in code or "cuda" in code or "memory" in code:
        return _pick(
            english,
            "Model startup timed out. Close GPU-heavy apps and retry; CPU fallback is available but slower.",
            "模型啟動逾時。請關閉佔用 GPU 的程式後重試；CPU 仍可用，但速度較慢。",
        )
    if any(token in code for token in ("asset", "hash", "sha", "model_missing", "projector")):
        return _pick(
            english,
            "Model verification failed. Restart the download; CloudHime will reject damaged files.",
            "模型驗證失敗。請重新啟動下載；CloudHime 會拒絕損壞檔案。",
        )
    if "runtime_missing" in code or "server" in code:
        return _pick(
            english,
            "The embedded inference runtime is missing. Repair or reinstall CloudHime.",
            "缺少內建推論元件。請修復或重新安裝 CloudHime。",
        )
    if "port" in code:
        return _pick(
            english,
            "The local service could not reserve a loopback port. Restart CloudHime and retry.",
            "內建服務無法取得本機連線埠。請重新啟動 CloudHime 後重試。",
        )
    return _pick(
        english,
        "Local AI could not start. Restart CloudHime; Google Translate remains available.",
        "本地 AI 無法啟動。請重新啟動 CloudHime；Google 翻譯仍可使用。",
    )


def _progress_label(detail: str, english: bool) -> str:
    raw = str(detail or "")
    progress = ""
    phase = raw
    if "|" in raw:
        progress, phase = raw.split("|", 1)
        progress = progress.strip()
    labels = {
        "checking_disk": ("Checking disk space", "檢查磁碟空間"),
        "checking_assets": ("Checking model files", "檢查模型檔案"),
        "downloading": ("Downloading local Gemma", "下載本地 Gemma"),
        "verifying": ("Verifying local Gemma", "驗證本地 Gemma"),
        "loading_model": ("Loading local Gemma", "載入本地 Gemma"),
        "loading_tensors": ("Loading model weights", "載入模型權重"),
        "initializing": ("Initializing GPU", "初始化 GPU"),
        "warming_up": ("Warming up local Gemma", "暖身本地 Gemma"),
        "model_loaded": ("Checking local service", "確認本地服務"),
        "starting_server": ("Starting embedded runtime", "啟動內建推論元件"),
    }
    en, zh = labels.get(phase, ("Preparing local Gemma", "準備本地 Gemma"))
    label = _pick(english, en, zh)
    suffix = f" {progress}%" if progress.isdigit() else ""
    return label + suffix


def assess_provider_health(
    *,
    ui_language: str = "zh-TW",
    ai_requested: bool = False,
    ai_enabled: bool = False,
    model_id: str = "",
    model_label: str = "AI",
    has_api_key: bool = False,
    local_multimodal_enabled: bool = False,
    embedded_runtime_available: bool = True,
    local_vision_state: str = "stopped",
    local_vision_detail: str = "",
    local_vision_mode: str = "",
    local_model_state: str = "stopped",
    local_model_detail: str = "",
    local_text_ready: bool = False,
    model_assets_present: bool = False,
) -> ProviderHealth:
    english = _is_english(ui_language)
    requested = bool(ai_requested or ai_enabled)
    label = str(model_label or model_id or "AI").strip()
    model = str(model_id or "").strip().lower()

    if not requested:
        return ProviderHealth(
            "google_ready",
            _pick(english, "Ready - Google Translate", "可使用 - Google 翻譯"),
            _pick(english, "No API key is required.", "不需 API Key。"),
            "accent",
        )

    if model not in LOCAL_MODEL_IDS:
        if not has_api_key:
            return ProviderHealth(
                "remote_key_required",
                _pick(english, f"Setup needed - AI - {label}", f"需要設定 - AI - {label}"),
                _pick(
                    english,
                    "Enter a Google API key to use this remote AI model. Google Translate remains available without a key.",
                    "請輸入 Google API Key 以使用此雲端 AI 模型；Google 翻譯仍可免 Key 使用。",
                ),
                "warning",
            )
        return ProviderHealth(
            "remote_configured",
            _pick(english, f"Configured - AI - {label}", f"已設定 - AI - {label}"),
            _pick(
                english,
                "The API key is present. Connectivity is checked when translation starts.",
                "已設定 API Key；網路與額度會在翻譯開始時檢查。",
            ),
            "accent",
        )

    if local_multimodal_enabled and not embedded_runtime_available:
        return ProviderHealth(
            "local_runtime_missing",
            _pick(english, f"Repair needed - Local AI - {label}", f"需要修復 - 本地 AI - {label}"),
            _failure_guidance("runtime_missing", english),
            "danger",
        )

    selected_state = local_vision_state if local_multimodal_enabled else local_model_state
    state = str(selected_state or "stopped").lower()
    detail = str(local_vision_detail if local_multimodal_enabled else local_model_detail or "")

    if state == "progress":
        progress_label = _progress_label(detail, english)
        return ProviderHealth(
            "local_progress",
            _pick(english, f"{progress_label} - {label}", f"{progress_label} - {label}"),
            _local_setup_note(english),
            "accent",
        )
    if state in {"starting", "loading"}:
        return ProviderHealth(
            "local_loading",
            _pick(english, f"Loading - Local AI - {label}", f"載入中 - 本地 AI - {label}"),
            _pick(
                english,
                "Keep CloudHime open while the model is verified and warmed up. " + _local_setup_note(True),
                "請保持 CloudHime 開啟，等待模型驗證與暖身完成。" + _local_setup_note(False),
            ),
            "accent",
        )
    if state == "failed":
        return ProviderHealth(
            "local_failed",
            _pick(english, f"Startup failed - Local AI - {label}", f"啟動失敗 - 本地 AI - {label}"),
            _failure_guidance(detail, english),
            "danger",
        )
    if state == "missing":
        if "server" in detail.lower() or ".exe" in detail.lower():
            return ProviderHealth(
                "local_runtime_missing",
                _pick(english, f"Repair needed - Local AI - {label}", f"\u9700\u8981\u4fee\u5fa9 - \u672c\u5730 AI - {label}"),
                _failure_guidance("runtime_missing", english),
                "danger",
            )
        model_assets_present = False
    if state == "ready" or local_text_ready:
        mode = str(local_vision_mode or "").lower()
        if local_multimodal_enabled and mode == "cpu":
            return ProviderHealth(
                "local_ready_cpu",
                _pick(english, f"Ready on CPU - Local AI - {label}", f"CPU 已就緒 - 本地 AI - {label}"),
                _pick(
                    english,
                    "CPU mode is available but slower; a supported GPU is recommended. " + _local_setup_note(True),
                    "CPU 模式可用，但速度較慢；建議使用支援的 GPU。" + _local_setup_note(False),
                ),
                "warning",
            )
        return ProviderHealth(
            "local_ready_gpu" if mode == "gpu" else "local_ready",
            _pick(english, f"Ready - Local AI - {label}", f"已就緒 - 本地 AI - {label}"),
            _pick(
                english,
                ("GPU acceleration is active. " if mode == "gpu" else "The local model is ready. ") + _local_setup_note(True),
                ("GPU 加速已啟用。" if mode == "gpu" else "本地模型已就緒。") + _local_setup_note(False),
            ),
            "accent",
        )
    if model_assets_present:
        return ProviderHealth(
            "local_start_pending",
            _pick(english, f"Preparing - Local AI - {label}", f"準備中 - 本地 AI - {label}"),
            _pick(
                english,
                "Model files are present and will start automatically. " + _local_setup_note(True),
                "模型檔案已就緒，將自動啟動。" + _local_setup_note(False),
            ),
            "accent",
        )
    return ProviderHealth(
        "local_download_required",
        _pick(english, f"Download required - Local AI - {label}", f"需要下載 - 本地 AI - {label}"),
        _pick(
            english,
            "CloudHime will download and verify the local model in AppData. " + _local_setup_note(True),
            "CloudHime 會將本地模型下載到 AppData 並完成驗證。" + _local_setup_note(False),
        ),
        "warning",
    )
