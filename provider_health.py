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
        "CloudHime manages this model directly. No Ollama, Python, Conda, or pip setup is required. (・ω・)",
        "CloudHime 會為主人管理此模型，不需安裝 Ollama、Python、Conda 或 pip 喔～ (・ω・)",
        "このモデルは CloudHime が管理します。Ollama、Python、Conda、pip の設定は不要ですよ (・ω・)",
    )


def _failure_guidance(detail: str, language: str) -> str:
    code = str(detail or "").lower()
    gpu_failure = any(token in code for token in ("cuda", "vram", "out of memory", "ggml_cuda"))
    if gpu_failure:
        return _pick(
            language,
            "Inference engine failed to start. Close heavy background apps and retry; CloudHime will try CPU fallback when possible. (｡•́︿•̀｡)",
            "推論環境啟動遇到狀況。請關閉高負載程式後重試；CloudHime 會在可行時嘗試 CPU 備援喔 (｡•́︿•̀｡)",
            "推論環境の起動に失敗しました。負荷の高いアプリを終了して再試行してください。可能な場合、CloudHime は CPU に切り替えて再試行します (｡•́︿•̀｡)",
        )
    if "timeout" in code:
        return _pick(
            language,
            "Model startup timed out. Free up system resources and retry; Google Translate remains available. (｡•́︿•̀｡)",
            "模型啟動逾時。請釋放系統資源後重試；若有網路，Google 翻譯仍可使用喔 (｡•́︿•̀｡)",
            "モデルの起動がタイムアウトしました。システムの負荷を減らして再試行してください。Google 翻訳は引き続き利用できます (｡•́︿•̀｡)",
        )
    if "model_missing" in code:
        return _pick(
            language,
            "The local model is not downloaded yet. Connect to the internet and select the local engine to download and verify it. (｡•ㅅ•｡)",
            "尚未下載本機模型。請確認網路連線後重新選擇本機引擎，以完成下載與驗證喔 (｡•ㅅ•｡)",
            "ローカルモデルが未ダウンロードです。インターネットに接続し、ローカルエンジンを選び直してダウンロードと検証を行ってくださいね (｡•ㅅ•｡)",
        )
    if any(token in code for token in ("asset", "hash", "sha", "projector")):
        return _pick(
            language,
            "Model verification failed. Please restart the download; CloudHime will reject corrupted files. (｡•́︿•̀｡)",
            "模型驗證失敗。請重新嘗試下載，CloudHime 會自動把關並阻擋損壞的檔案喔 (｡•́︿•̀｡)",
            "モデルの検証に失敗しました。ダウンロードをやり直してください。破損ファイルは安全のため除外されます (｡•́︿•̀｡)",
        )
    if "runtime_missing" in code or "server" in code:
        return _pick(
            language,
            "Embedded inference runtime is missing. Please repair or reinstall CloudHime. (｡•́︿•̀｡)",
            "缺少內建推論元件。請嘗試修復或重新安裝 CloudHime 喔 (｡•́︿•̀｡)",
            "内蔵推論ランタイムが見つかりません。CloudHime の修復または再インストールをお試しくださいね (｡•́︿•̀｡)",
        )
    if "port" in code:
        return _pick(
            language,
            "Local service could not reserve a loopback port. Please restart CloudHime and retry. (｡•́︿•̀｡)",
            "內建服務無法取得本機連線埠。請重新啟動 CloudHime 後再試一次喔 (｡•́︿•̀｡)",
            "ローカルサービスがループバックポートを確保できませんでした。CloudHime を再起動して再試行してくださいね (｡•́︿•̀｡)",
        )
    return _pick(
        language,
        "Local AI could not start. Please restart CloudHime; Google Translate remains available. (｡•́︿•̀｡)",
        "本機 AI 無法啟動。請重新啟動 CloudHime；Google 翻譯仍可繼續使用喔 (｡•́︿•̀｡)",
        "ローカル AI を起動できませんでした。CloudHime を再起動してください。Google 翻訳は引き続き利用できますね (｡•́︿•̀｡)",
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
        "downloading": ("Downloading local Gemma", "下載本機 Gemma", "ローカル Gemma をダウンロード中"),
        "verifying": ("Verifying local Gemma", "驗證本機 Gemma", "ローカル Gemma を検証中"),
        "loading_model": ("Loading local Gemma", "載入本機 Gemma", "ローカル Gemma を読み込み中"),
        "loading_tensors": ("Loading model weights", "載入模型權重", "モデルの重みを読み込み中"),
        "initializing": ("Initializing inference runtime", "初始化推論環境", "推論環境を初期化中"),
        "warming_up": ("Warming up local Gemma", "本機 Gemma 暖身中", "ローカル Gemma をウォームアップ中"),
        "model_loaded": ("Checking local service", "確認本機服務", "ローカルサービスを確認中"),
        "starting_server": ("Starting embedded runtime", "啟動內建推論元件", "内蔵ランタイムを起動中"),
    }
    if phase == "initializing" and str(mode or "").lower() == "cpu":
        en, zh, ja = "Initializing CPU", "初始化 CPU", "CPU を初期化中"
    else:
        en, zh, ja = labels.get(phase, ("Preparing local Gemma", "準備本地 Gemma", "ローカル Gemma を準備中"))
    label = _pick(language, en, zh, ja)
    suffix = f" {progress}%" if progress.isdigit() else ""
    return label + suffix


def local_model_progress_message(detail: str, ui_language: str, *, cpu_only=False) -> str:
    """Describe asset/runtime progress without exposing raw diagnostic details."""
    return _progress_label(detail, _language(ui_language), "cpu" if cpu_only else "")


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
            _pick(language, "No API key is required. (・∀・)", "不需 API Key 即可使用喔！ (・∀・)", "API キーは不要で利用できますよ (・∀・)"),
            "accent",
        )

    if model not in LOCAL_MODEL_IDS:
        if not has_api_key:
            return ProviderHealth(
                "remote_key_required",
                _pick(language, f"Setup needed - AI - {label}", f"需要設定 - AI - {label}", f"設定が必要 - AI - {label}"),
                _pick(
                    language,
                    "Enter a Google API key to use this remote AI model. Google Translate remains available without a key. (｡•ㅅ•｡)",
                    "請輸入 Google API Key 以使用此雲端 AI 模型；若需免金鑰可使用 Google 翻譯喔 (｡•ㅅ•｡)",
                    "このオンライン AI モデルを使うには Google API キーを入力してください。Google 翻訳はキーなしで利用できますよ (｡•ㅅ•｡)",
                ),
                "warning",
            )
        return ProviderHealth(
            "remote_configured",
            _pick(language, f"Configured - AI - {label}", f"已設定 - AI - {label}", f"設定済み - AI - {label}"),
            _pick(
                language,
                "API key configured. Connectivity and quota are checked when translation starts. (・ω・)",
                "已設定 API Key；網路連線與額度會在翻譯開始時檢查喔 (・ω・)",
                "API キーは設定済みです。接続と利用枠は翻訳開始時に確認します (・ω・)",
            ),
            "accent",
        )

    if local_multimodal_enabled and not embedded_runtime_available:
        return ProviderHealth(
            "local_runtime_missing",
            _pick(language, f"Repair needed - Local AI - {label}", f'需要修復 - 本機 AI - {label}', f"修復が必要 - ローカル AI - {label}"),
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
            _pick(language, f"Loading - Local AI - {label}", f'載入中 - 本機 AI - {label}', f"読み込み中 - ローカル AI - {label}"),
            _pick(
                language,
                "Keep CloudHime open while the model is verified and warmed up. " + _local_setup_note("en"),
                "請保持 CloudHime 開啟，等待模型驗證與暖身完成喔～ (｡•ㅅ•｡)" + " " + _local_setup_note("zh"),
                "モデルの検証とウォームアップが終わるまで CloudHime を開いたままにしてね (｡•ㅅ•｡)" + " " + _local_setup_note("ja"),
            ),
            "accent",
        )
    if state == "failed":
        return ProviderHealth(
            "local_failed",
            _pick(language, f"Startup failed - Local AI - {label}", f'啟動失敗 - 本機 AI - {label}', f"起動失敗 - ローカル AI - {label}"),
            _failure_guidance(detail, language),
            "danger",
        )
    if state == "missing":
        if "server" in detail.lower() or ".exe" in detail.lower():
            return ProviderHealth(
                "local_runtime_missing",
                _pick(language, f"Repair needed - Local AI - {label}", f'需要修復 - 本機 AI - {label}', f"修復が必要 - ローカル AI - {label}"),
                _failure_guidance("runtime_missing", language),
                "danger",
            )
        model_assets_present = False
    if state == "ready" or local_text_ready:
        mode = str(local_vision_mode or "").lower()
        if local_multimodal_enabled and mode == "cpu":
            return ProviderHealth(
                "local_ready_cpu",
                _pick(language, f"Ready on CPU - Local AI - {label}", f'CPU 已就緒 - 本機 AI - {label}', f"CPU で利用可能 - ローカル AI - {label}"),
                _pick(
                    language,
                    "CPU mode is available but slower; a supported GPU is recommended. " + _local_setup_note("en"),
                    "CPU 模式可用，運算耗時較長；若有支援的 GPU 會更流暢喔～ (・ω・)" + " " + _local_setup_note("zh"),
                    "CPU モードは利用できますが処理に時間がかかります。対応 GPU の使用をおすすめします (・ω・)" + " " + _local_setup_note("ja"),
                ),
                "warning",
            )
        return ProviderHealth(
            "local_ready_gpu" if mode == "gpu" else "local_ready",
            _pick(language, f"Ready - Local AI - {label}", f'已就緒 - 本機 AI - {label}', f"利用可能 - ローカル AI - {label}"),
            _pick(
                language,
                ("GPU acceleration is active. " if mode == "gpu" else "The local model is ready. ") + _local_setup_note("en"),
                ("GPU 加速已啟用囉！ (๑•̀ㅂ•́)و✧" if mode == "gpu" else "本機模型已就緒，隨時可以翻譯囉！ (๑•̀ㅂ•́)و✧") + " " + _local_setup_note("zh"),
                ("GPU アクセラレーションが有効です！ (๑•̀ㅂ•́)و✧" if mode == "gpu" else "ローカルモデルの準備が完了しました！いつでも利用できます (๑•̀ㅂ•́)و✧") + " " + _local_setup_note("ja"),
            ),
            "accent",
        )
    if model_assets_present:
        return ProviderHealth(
            "local_start_pending",
            _pick(language, f"Preparing - Local AI - {label}", f'準備中 - 本機 AI - {label}', f"準備中 - ローカル AI - {label}"),
            _pick(
                language,
                "Model files are present and will start automatically. " + _local_setup_note("en"),
                "模型檔案已確認，將自動啟動推論環境喔～ (・ω・)" + " " + _local_setup_note("zh"),
                "モデルファイルを確認しました。自動的に起動しますね (・ω・)" + " " + _local_setup_note("ja"),
            ),
            "accent",
        )
    return ProviderHealth(
        "local_download_required",
        _pick(language, f"Download required - Local AI - {label}", f"需要下載 - 本地 AI - {label}", f"ダウンロードが必要 - ローカル AI - {label}"),
        _pick(
            language,
            "CloudHime will download and verify the local model in AppData. " + _local_setup_note("en"),
            "CloudHime 會將本地模型下載到 AppData 並完成驗證。" + " " + _local_setup_note("zh"),
            "CloudHime はローカルモデルを AppData にダウンロードして検証します。" + " " + _local_setup_note("ja"),
        ),
        "warning",
    )
