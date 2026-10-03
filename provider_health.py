from __future__ import annotations

from dataclasses import dataclass

from model_catalog import LOCAL_MODEL_IDS




@dataclass(frozen=True)
class ProviderHealth:
    code: str
    summary: str
    detail: str
    tone: str


def _language(ui_language: str) -> str:
    language = str(ui_language or "").lower().replace("_", "-").split("-", 1)[0]
    return language if language in {"en", "ja"} else "zh"


def _pick(language: str, en: str, zh: str, ja: str) -> str:
    if language == "en":
        return en
    if language == "ja":
        return ja
    return zh


def _local_setup_note(language: str) -> str:
    return _pick(
        language,
        "CloudHime manages this model. No Ollama, Python, Conda, or pip setup is required.",
        "CloudHime 會管理此模型，不需 Ollama、Python、Conda 或 pip。",
        "このモデルは CloudHime が管理します。Ollama、Python、Conda、pip の設定は不要です。",
    )


def _failure_guidance(detail: str, language: str) -> str:
    code = str(detail or "").lower()
    gpu_failure = any(token in code for token in ("cuda", "vram", "out of memory", "ggml_cuda"))
    if gpu_failure:
        return _pick(
            language,
            "GPU startup failed. Close GPU-heavy apps and retry; CloudHime will try CPU fallback when possible.",
            "GPU 啟動失敗。請關閉佔用 GPU 的程式後重試；CloudHime 會在可能時嘗試 CPU 備援。",
            "GPU の起動に失敗しました。GPU を多く使用するアプリを終了して再試行してください。可能な場合、CloudHime は CPU に切り替えて再試行します。",
        )
    if "timeout" in code:
        return _pick(
            language,
            "Model startup timed out. Close GPU-heavy apps and retry; Google Translate remains available.",
            "模型啟動逾時。請關閉佔用 GPU 的程式後重試；Google 翻譯仍可使用。",
            "モデルの起動がタイムアウトしました。GPU を多く使用するアプリを終了して再試行してください。Google 翻訳は引き続き利用できます。",
        )
    if "model_missing" in code:
        return _pick(
            language,
            "The local model has not been downloaded. Connect to the internet and select the local engine again to download and verify it.",
            "尚未下載本地模型。請連上網路後重新選擇本機引擎，下載並驗證模型。",
            "ローカルモデルが未ダウンロードです。インターネットに接続し、ローカルエンジンを選び直してモデルをダウンロード・検証してください。",
        )
    if any(token in code for token in ("asset", "hash", "sha", "projector")):
        return _pick(
            language,
            "Model verification failed. Restart the download; CloudHime will reject damaged files.",
            "模型驗證失敗。請重新啟動下載；CloudHime 會拒絕損壞檔案。",
            "モデルを検証できませんでした。ダウンロードをやり直してください。CloudHime は破損したファイルを使用しません。",
        )
    if "runtime_missing" in code or "server" in code:
        return _pick(
            language,
            "The embedded inference runtime is missing. Repair or reinstall CloudHime.",
            "缺少內建推論元件。請修復或重新安裝 CloudHime。",
            "内蔵推論ランタイムが見つかりません。CloudHime を修復または再インストールしてください。",
        )
    if "port" in code:
        return _pick(
            language,
            "The local service could not reserve a loopback port. Restart CloudHime and retry.",
            "內建服務無法取得本機連線埠。請重新啟動 CloudHime 後重試。",
            "ローカルサービスがループバックポートを確保できませんでした。CloudHime を再起動して再試行してください。",
        )
    return _pick(
        language,
        "Local AI could not start. Restart CloudHime; Google Translate remains available.",
        "本地 AI 無法啟動。請重新啟動 CloudHime；Google 翻譯仍可使用。",
        "ローカル AI を起動できませんでした。CloudHime を再起動してください。Google 翻訳は引き続き利用できます。",
    )


def local_model_failure_message(detail: str, ui_language: str) -> str:
    """Return recovery guidance without putting runtime diagnostics in the UI."""
    return _failure_guidance(detail, _language(ui_language))


def _progress_label(detail: str, language: str, mode: str = "") -> str:
    raw = str(detail or "")
    progress = ""
    phase = raw
    if "|" in raw:
        progress, phase = raw.split("|", 1)
        progress = progress.strip()
    labels = {
        "checking_disk": ("Checking disk space", "檢查磁碟空間", "ディスクの空き容量を確認中"),
        "checking_assets": ("Checking model files", "檢查模型檔案", "モデルファイルを確認中"),
        "downloading": ("Downloading local Gemma", "下載本地 Gemma", "ローカル Gemma をダウンロード中"),
        "verifying": ("Verifying local Gemma", "驗證本地 Gemma", "ローカル Gemma を検証中"),
        "loading_model": ("Loading local Gemma", "載入本地 Gemma", "ローカル Gemma を読み込み中"),
        "loading_tensors": ("Loading model weights", "載入模型權重", "モデルの重みを読み込み中"),
        "initializing": ("Initializing GPU", "初始化 GPU", "GPU を初期化中"),
        "warming_up": ("Warming up local Gemma", "暖身本地 Gemma", "ローカル Gemma をウォームアップ中"),
        "model_loaded": ("Checking local service", "確認本地服務", "ローカルサービスを確認中"),
        "starting_server": ("Starting embedded runtime", "啟動內建推論元件", "内蔵ランタイムを起動中"),
    }
    if phase == "initializing" and str(mode or "").lower() == "cpu":
        en, zh, ja = "Initializing CPU", "初始化 CPU", "CPU を初期化中"
    else:
        en, zh, ja = labels.get(phase, ("Preparing local Gemma", "準備本地 Gemma", "ローカル Gemma を準備中"))
    label = _pick(language, en, zh, ja)
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
    language = _language(ui_language)
    requested = bool(ai_requested or ai_enabled)
    label = str(model_label or model_id or "AI").strip()
    model = str(model_id or "").strip().lower()

    if not requested:
        return ProviderHealth(
            "google_ready",
            _pick(language, "Ready - Google Translate", "可使用 - Google 翻譯", "利用可能 - Google 翻訳"),
            _pick(language, "No API key is required.", "不需 API Key。", "API キーは不要です。"),
            "accent",
        )

    if model not in LOCAL_MODEL_IDS:
        if not has_api_key:
            return ProviderHealth(
                "remote_key_required",
                _pick(language, f"Setup needed - AI - {label}", f"需要設定 - AI - {label}", f"設定が必要 - AI - {label}"),
                _pick(
                    language,
                    "Enter a Google API key to use this remote AI model. Google Translate remains available without a key.",
                    "請輸入 Google API Key 以使用此雲端 AI 模型；Google 翻譯仍可免 Key 使用。",
                    "このオンライン AI モデルを使うには Google API キーを入力してください。Google 翻訳はキーなしで引き続き利用できます。",
                ),
                "warning",
            )
        return ProviderHealth(
            "remote_configured",
            _pick(language, f"Configured - AI - {label}", f"已設定 - AI - {label}", f"設定済み - AI - {label}"),
            _pick(
                language,
                "The API key is present. Connectivity is checked when translation starts.",
                "已設定 API Key；網路與額度會在翻譯開始時檢查。",
                "API キーは設定済みです。接続は翻訳開始時に確認します。",
            ),
            "accent",
        )

    if local_multimodal_enabled and not embedded_runtime_available:
        return ProviderHealth(
            "local_runtime_missing",
            _pick(language, f"Repair needed - Local AI - {label}", f"需要修復 - 本地 AI - {label}", f"修復が必要 - ローカル AI - {label}"),
            _failure_guidance("runtime_missing", language),
            "danger",
        )

    selected_state = local_vision_state if local_multimodal_enabled else local_model_state
    state = str(selected_state or "stopped").lower()
    detail = str(local_vision_detail if local_multimodal_enabled else local_model_detail or "")

    if state == "progress":
        progress_mode = local_vision_mode if local_multimodal_enabled else ""
        progress_label = _progress_label(detail, language, progress_mode)
        return ProviderHealth(
            "local_progress",
            f"{progress_label} - {label}",
            _local_setup_note(language),
            "accent",
        )
    if state in {"starting", "loading"}:
        return ProviderHealth(
            "local_loading",
            _pick(language, f"Loading - Local AI - {label}", f"載入中 - 本地 AI - {label}", f"読み込み中 - ローカル AI - {label}"),
            _pick(
                language,
                "Keep CloudHime open while the model is verified and warmed up. " + _local_setup_note("en"),
                "請保持 CloudHime 開啟，等待模型驗證與暖身完成。" + _local_setup_note("zh"),
                "モデルの検証とウォームアップが終わるまで CloudHime を開いたままにしてください。" + _local_setup_note("ja"),
            ),
            "accent",
        )
    if state == "failed":
        return ProviderHealth(
            "local_failed",
            _pick(language, f"Startup failed - Local AI - {label}", f"啟動失敗 - 本地 AI - {label}", f"起動失敗 - ローカル AI - {label}"),
            _failure_guidance(detail, language),
            "danger",
        )
    if state == "missing":
        if "server" in detail.lower() or ".exe" in detail.lower():
            return ProviderHealth(
                "local_runtime_missing",
                _pick(language, f"Repair needed - Local AI - {label}", f"\u9700\u8981\u4fee\u5fa9 - \u672c\u5730 AI - {label}", f"修復が必要 - ローカル AI - {label}"),
                _failure_guidance("runtime_missing", language),
                "danger",
            )
        model_assets_present = False
    if state == "ready" or local_text_ready:
        mode = str(local_vision_mode or "").lower()
        if local_multimodal_enabled and mode == "cpu":
            return ProviderHealth(
                "local_ready_cpu",
                _pick(language, f"Ready on CPU - Local AI - {label}", f"CPU 已就緒 - 本地 AI - {label}", f"CPU で利用可能 - ローカル AI - {label}"),
                _pick(
                    language,
                    "CPU mode is available but slower; a supported GPU is recommended. " + _local_setup_note("en"),
                    "CPU 模式可用，但速度較慢；建議使用支援的 GPU。" + _local_setup_note("zh"),
                    "CPU モードは利用できますが、速度は低下します。対応 GPU の使用をおすすめします。" + _local_setup_note("ja"),
                ),
                "warning",
            )
        return ProviderHealth(
            "local_ready_gpu" if mode == "gpu" else "local_ready",
            _pick(language, f"Ready - Local AI - {label}", f"已就緒 - 本地 AI - {label}", f"利用可能 - ローカル AI - {label}"),
            _pick(
                language,
                ("GPU acceleration is active. " if mode == "gpu" else "The local model is ready. ") + _local_setup_note("en"),
                ("GPU 加速已啟用。" if mode == "gpu" else "本地模型已就緒。") + _local_setup_note("zh"),
                ("GPU アクセラレーションが有効です。" if mode == "gpu" else "ローカルモデルを利用できます。") + _local_setup_note("ja"),
            ),
            "accent",
        )
    if model_assets_present:
        return ProviderHealth(
            "local_start_pending",
            _pick(language, f"Preparing - Local AI - {label}", f"準備中 - 本地 AI - {label}", f"準備中 - ローカル AI - {label}"),
            _pick(
                language,
                "Model files are present and will start automatically. " + _local_setup_note("en"),
                "模型檔案已就緒，將自動啟動。" + _local_setup_note("zh"),
                "モデルファイルは準備できており、自動的に起動します。" + _local_setup_note("ja"),
            ),
            "accent",
        )
    return ProviderHealth(
        "local_download_required",
        _pick(language, f"Download required - Local AI - {label}", f"需要下載 - 本地 AI - {label}", f"ダウンロードが必要 - ローカル AI - {label}"),
        _pick(
            language,
            "CloudHime will download and verify the local model in AppData. " + _local_setup_note("en"),
            "CloudHime 會將本地模型下載到 AppData 並完成驗證。" + _local_setup_note("zh"),
            "CloudHime はローカルモデルを AppData にダウンロードして検証します。" + _local_setup_note("ja"),
        ),
        "warning",
    )
