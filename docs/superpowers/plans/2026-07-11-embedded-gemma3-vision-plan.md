# 內嵌 Gemma 3 Vision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 CloudHime 自行管理本機 Gemma 3 Vision runtime，能翻譯 `example/` 圖片且不要求使用者安裝 Ollama 或另行啟動服務。

**Architecture:** 新增獨立 `LocalVisionRuntime` 管理隨附 `llama-server.exe`、動態 loopback port、健康檢查與關閉回收。沿用 `LocalMultimodalProvider` 的 OpenAI-compatible 圖片請求，由 worker 非阻塞啟動 runtime 並把 ready base URL 注入 provider，UI 只呈現狀態。

**Tech Stack:** Python 3、PySide6、`subprocess`、`socket`、`urllib`、`llama.cpp/libmtmd`、pytest、Gemma 3 4B Q4_K_M、`mmproj-model-f16.gguf`

## Global Constraints

- 不依賴 current working directory；所有 runtime/model 路徑由 application root 解析。
- Server 只綁定 `127.0.0.1` 並使用 OS 配置的可用 port。
- 不經 shell 啟動命令，不記錄圖片 base64、完整 prompt 或 API key。
- 啟動與健康等待不得阻塞 Qt UI thread。
- 只回收本 instance 建立的 process handle，不依程序名稱掃殺。
- 第一階段模型直接放 `models/`；自動下載另案。
- 每項程式變更先 RED、再最小 GREEN，保留現有 Google 與文字 Gemma 行為。

---

### Task 1: 真機 preflight 與資產契約

**Files:**
- Create: `scripts/verify_local_vision_assets.py`
- Create: `tests/test_local_vision_assets.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `resolve_vision_assets(app_root: Path) -> VisionAssets`
- Produces: `verify_asset(path: Path, expected_sha256: str | None, minimum_bytes: int) -> None`
- `VisionAssets` fields: `server_path`, `model_path`, `projector_path`

- [ ] **Step 1: 寫 RED 測試**

```python
def test_assets_resolve_from_app_root_not_cwd(tmp_path, monkeypatch):
    app = tmp_path / "app"
    (app / "runtime").mkdir(parents=True)
    (app / "models").mkdir()
    monkeypatch.chdir(tmp_path)
    assets = resolve_vision_assets(app)
    assert assets.server_path == app / "runtime" / "llama-server.exe"
    assert assets.projector_path == app / "models" / "mmproj-model-f16.gguf"

def test_verify_asset_rejects_truncated_file(tmp_path):
    path = tmp_path / "mmproj.gguf"
    path.write_bytes(b"short")
    with pytest.raises(VisionAssetError, match="asset_too_small"):
        verify_asset(path, None, minimum_bytes=800_000_000)
```

- [ ] **Step 2: 確認 RED**

Run: `python -m pytest -q tests/test_local_vision_assets.py`

Expected: FAIL，因 `scripts.verify_local_vision_assets` 尚不存在。

- [ ] **Step 3: 實作最小資產解析與驗證**

```python
@dataclass(frozen=True)
class VisionAssets:
    server_path: Path
    model_path: Path
    projector_path: Path

def resolve_vision_assets(app_root: Path) -> VisionAssets:
    return VisionAssets(
        server_path=app_root / "runtime" / "llama-server.exe",
        model_path=app_root / "models" / "gemma-3-4b-it.Q4_K_M.gguf",
        projector_path=app_root / "models" / "mmproj-model-f16.gguf",
    )
```

驗證器以串流 SHA-256 讀檔；`.gitignore` 忽略 `runtime/`、`models/mmproj-*.gguf` 與真機輸出，但保留腳本與測試。

- [ ] **Step 4: GREEN 與資產盤點**

Run: `python -m pytest -q tests/test_local_vision_assets.py`

Expected: PASS。

Run: `python scripts/verify_local_vision_assets.py --app-root .`

Expected: 在資產尚未備齊時列出精確缺件並 exit 2；備齊後列出三個絕對路徑、大小與 projector SHA-256。

- [ ] **Step 5: Commit**

```powershell
git add .gitignore scripts/verify_local_vision_assets.py tests/test_local_vision_assets.py
git commit -m "test: define local vision asset contract"
```

---

### Task 2: `LocalVisionRuntime` 生命週期

**Files:**
- Create: `local_vision_runtime.py`
- Create: `tests/test_local_vision_runtime.py`

**Interfaces:**
- Consumes: `VisionAssets`
- Produces: `VisionRuntimeState(name: str, detail: str, base_url: str, mode: str)`
- Produces: `LocalVisionRuntime.start() -> VisionRuntimeState`
- Produces: `LocalVisionRuntime.stop() -> VisionRuntimeState`
- Constructor injection: `popen_factory`, `urlopen`, `port_allocator`, `sleep`

- [ ] **Step 1: 寫路徑、命令與狀態 RED 測試**

```python
def test_start_uses_loopback_dynamic_port_and_mmproj(fake_assets):
    popen = RecordingPopen()
    runtime = make_runtime(fake_assets, popen=popen, health=[True], port=43123)
    state = runtime.start()
    assert state.name == "ready"
    assert state.base_url == "http://127.0.0.1:43123/v1"
    assert popen.args[:4] == [str(fake_assets.server_path), "--host", "127.0.0.1", "--port"]
    assert "--mmproj" in popen.args

def test_start_is_idempotent_while_ready(fake_assets):
    runtime = make_runtime(fake_assets, health=[True])
    first = runtime.start()
    second = runtime.start()
    assert first.base_url == second.base_url
    assert runtime.spawn_count == 1
```

- [ ] **Step 2: 確認 RED**

Run: `python -m pytest -q tests/test_local_vision_runtime.py`

Expected: FAIL，因 runtime 尚不存在。

- [ ] **Step 3: 實作狀態機與 Windows 隱藏啟動**

```python
args = [
    str(assets.server_path), "--host", "127.0.0.1", "--port", str(port),
    "-m", str(assets.model_path), "--mmproj", str(assets.projector_path),
    "-c", "4096", "-ngl", "999",
]
creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
self._process = self._popen_factory(
    args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    text=True, encoding="utf-8", errors="replace", creationflags=creationflags,
)
```

健康輪詢檢查 process `poll()` 與 `http://127.0.0.1:<port>/health`；detail 只保留最多 2,000 字元 stderr。

- [ ] **Step 4: 寫並驗證失敗／fallback／stop 測試**

```python
def test_cuda_start_failure_retries_once_in_cpu_mode(fake_assets):
    runtime = make_runtime(fake_assets, processes=[Exited("CUDA out of memory"), Running()], health=[True])
    state = runtime.start()
    assert state.name == "ready"
    assert state.mode == "cpu"
    assert runtime.spawn_count == 2

def test_stop_terminates_only_owned_process(runtime):
    process = runtime.owned_process
    assert runtime.stop().name == "stopped"
    assert process.terminate_calls == 1
```

Run: `python -m pytest -q tests/test_local_vision_runtime.py`

Expected: PASS，包含 missing、health timeout、early exit、單次 fallback、stop 與 port release。

- [ ] **Step 5: Commit**

```powershell
git add local_vision_runtime.py tests/test_local_vision_runtime.py
git commit -m "feat: manage embedded Gemma vision runtime"
```

---

### Task 3: Provider、registry 與 worker 非阻塞接線

**Files:**
- Modify: `translation_providers.py`
- Modify: `cloudhime_workers.py`
- Modify: `translation_contracts.py`
- Test: `tests/test_local_multimodal_provider.py`
- Test: `tests/test_cloudhime_workers.py`

**Interfaces:**
- Consumes: `LocalVisionRuntime.start/stop`
- Produces signal: `local_vision_status = Signal(str, str)`
- Produces: `request_local_vision_start() -> None`
- Provider addition: `update_runtime(base_url: str, model_name: str, ready: bool) -> None`

- [ ] **Step 1: 寫 provider availability RED 測試**

```python
def test_embedded_provider_is_available_only_after_runtime_ready():
    provider = LocalMultimodalProvider(enabled=True, model_name="gemma-3-4b-it")
    provider.update_runtime("http://127.0.0.1:43123/v1", "gemma-3-4b-it", ready=False)
    assert provider.available() is False
    provider.update_runtime("http://127.0.0.1:43123/v1", "gemma-3-4b-it", ready=True)
    assert provider.available() is True
```

- [ ] **Step 2: 寫 worker 非阻塞 RED 測試**

```python
def test_worker_starts_vision_runtime_in_executor():
    worker = make_worker_with_fake_vision_runtime(state="ready")
    OCRWorker.request_local_vision_start(worker)
    assert worker.vision_executor.submitted == [worker.local_vision_runtime.start]
    assert worker.statuses == [("starting", ""), ("ready", "")]
    assert worker.local_multimodal_provider.base_url.endswith("/v1")
```

Run: `python -m pytest -q tests/test_local_multimodal_provider.py tests/test_cloudhime_workers.py -k "vision or embedded"`

Expected: FAIL，因 runtime readiness 尚未接線。

- [ ] **Step 3: 實作最小接線**

Worker 建立單 worker executor；callback 只透過 Qt signal 傳遞 immutable state。`ready` 時呼叫：

```python
self.local_multimodal_provider.update_runtime(
    state.base_url,
    "gemma-3-4b-it",
    ready=True,
)
self._refresh_translation_registry()
self.local_vision_status.emit(state.name, state.detail)
```

`failed/missing/stopped` 時把 provider readiness 設為 false。保留既有手動 HTTP provider 設定的相容讀取，但內嵌模式不使用該 URL。

- [ ] **Step 4: GREEN 與路由回歸**

Run: `python -m pytest -q tests/test_local_multimodal_provider.py tests/test_cloudhime_workers.py tests/test_translation_providers.py`

Expected: 全部 PASS；圖片路由優先 ready 的本機 provider，文字 Local Gemma 仍可用。

- [ ] **Step 5: Commit**

```powershell
git add translation_providers.py translation_contracts.py cloudhime_workers.py tests/test_local_multimodal_provider.py tests/test_cloudhime_workers.py
git commit -m "feat: route images through embedded vision runtime"
```

---

### Task 4: UI 狀態與關閉回收

**Files:**
- Modify: `cloudhime_ui.py`
- Modify: `translation_settings_panel.py`
- Test: `tests/test_cloudhime_ui_smoke.py`
- Test: `tests/test_translation_panel_advanced.py`

**Interfaces:**
- Consumes signal: `local_vision_status(str, str)`
- Produces: `Controller.on_local_vision_status(state: str, detail: str) -> None`
- Close contract: `worker.shutdown_local_vision_runtime()` before `ocr_thread.quit()`

- [ ] **Step 1: 寫 UI RED 測試**

```python
def test_local_vision_starting_uses_indeterminate_progress(controller):
    controller.on_local_vision_status("starting", "")
    assert controller.charge_bar.indeterminate is True
    assert "Gemma3 Vision" in controller.charge_bar.label

def test_close_stops_vision_before_worker_thread(controller):
    controller.close_app()
    assert controller.events.index("vision_stop") < controller.events.index("thread_quit")
```

- [ ] **Step 2: 確認 RED**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_cloudhime_ui_smoke.py tests/test_translation_panel_advanced.py -k vision`

Expected: FAIL，因 handler 與 close contract 尚未實作。

- [ ] **Step 3: 實作狀態 mapping 與設定簡化**

```python
labels = {
    "missing": "Gemma3 Vision 缺少模型",
    "starting": "Gemma3 Vision 載入中",
    "ready": "Gemma3 Vision 已就緒",
    "failed": "Gemma3 Vision 啟動失敗",
    "stopped": "Gemma3 Vision 已停止",
}
```

`starting` 使用不定進度；`ready` 顯示 100%；`missing/failed` 使用 danger 色。內嵌模式隱藏 Base URL 與 model name 編輯欄，只保留啟用切換與狀態。關閉順序先停止兩個 local model executors/runtime，再 quit/wait QThread。

- [ ] **Step 4: GREEN**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_cloudhime_ui_smoke.py tests/test_translation_panel_advanced.py`

Expected: PASS，且不建立真 subprocess。

- [ ] **Step 5: Commit**

```powershell
git add cloudhime_ui.py translation_settings_panel.py tests/test_cloudhime_ui_smoke.py tests/test_translation_panel_advanced.py
git commit -m "feat: show embedded vision runtime status"
```

---

### Task 5: 真實 `example/` 驗收與 Mission Center

**Files:**
- Create: `tests/test_local_vision_integration.py`
- Modify: `MissionCenter/tasks.md`
- Modify: `MissionCenter/progress.md`
- Modify: `MissionCenter/notes.md`
- Modify: `MissionCenter/smoke-tests.md`

**Interfaces:**
- Opt-in env: `CLOUDHIME_RUN_LOCAL_VISION=1`
- Optional image override: `CLOUDHIME_LOCAL_VISION_IMAGE=<absolute path>`

- [ ] **Step 1: 建立 opt-in integration test**

```python
@pytest.mark.skipif(
    os.getenv("CLOUDHIME_RUN_LOCAL_VISION") != "1",
    reason="requires embedded llama-server and Gemma 3 vision assets",
)
def test_gemma3_vision_reads_example_image():
    runtime = LocalVisionRuntime.from_application_root(PROJECT_ROOT)
    state = runtime.start()
    try:
        assert state.name == "ready", state.detail
        result = provider_for(state).translate_screenshot(
            [image_part(EXAMPLE_IMAGE)], target_lang="zh-TW",
            source_text_hint="",
        )
        assert result.text.strip()
        assert any(term in result.text for term in EXPECTED_VISUAL_TERMS)
    finally:
        runtime.stop()
    assert runtime.process is None
```

固定圖片先人工檢視，`EXPECTED_VISUAL_TERMS` 只放畫面可客觀辨識的文字／專名，不以輸出完全相等判斷生成模型。

- [ ] **Step 2: 一般回歸（預設 skip 真模型）**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_local_vision_runtime.py tests/test_local_vision_assets.py tests/test_local_multimodal_provider.py tests/test_cloudhime_workers.py tests/test_cloudhime_ui_smoke.py tests/test_translation_providers.py tests/test_local_vision_integration.py`

Expected: 所有 deterministic tests PASS，integration 顯示 1 skipped。

- [ ] **Step 3: 真機圖片 smoke**

Run: `$env:CLOUDHIME_RUN_LOCAL_VISION='1'; python -m pytest -q -s tests/test_local_vision_integration.py`

Expected: `1 passed`，輸出記錄冷啟動秒數、回應秒數、runtime mode、非空翻譯與被命中的 visual term；結束後無 `llama-server.exe` 殘留。

- [ ] **Step 4: 有限循環與語法檢查**

Run: `$env:CLOUDHIME_RUN_LOCAL_VISION='1'; python -m pytest -q -s tests/test_local_vision_integration.py --count=3`

若專案未安裝 repeat plugin，改由測試內 parameterize 三次請求同一 runtime。Expected: 三次皆成功，記憶體未持續無界上升，stop 後 port 可重綁。

Run: `python -m py_compile local_vision_runtime.py cloudhime_workers.py cloudhime_ui.py translation_providers.py tests/test_local_vision_integration.py`

Expected: exit 0。

- [ ] **Step 5: 回寫 Mission Center**

新增 CH-T34「內嵌 Gemma3 Vision runtime」，只有在真實 integration PASS、關閉無殘留與 Gemini review 完成後才設為 Done；`smoke-tests.md` 記錄日期、命令、預期、觀察、結果與類型，並重申 Ollama 不屬於需求或安裝前提。

- [ ] **Step 6: Commit**

```powershell
git add tests/test_local_vision_integration.py MissionCenter/tasks.md MissionCenter/progress.md MissionCenter/notes.md MissionCenter/smoke-tests.md
git commit -m "test: verify embedded Gemma 3 vision end to end"
```
