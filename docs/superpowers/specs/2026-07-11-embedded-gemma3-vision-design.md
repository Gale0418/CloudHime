# 內嵌 Gemma 3 Vision 設計規格

## 目標

讓 CloudHime 在 Windows 本機直接處理 `example/` 圖片並輸出翻譯，不要求使用者安裝 Ollama、手動啟動模型服務或提供雲端 API。開發階段先由 `models/` 提供模型與 runtime；產品化下載流程另案處理。

## 非目標

- 不在本階段建立模型下載器或 Microsoft Store 配送流程。
- 不更換現有 Gemma 3 4B 主模型，也不導入 Qwen、LLaVA 等第二套模型。
- 不重寫既有 OCR、圖片編碼、翻譯 registry 或 Google fallback。
- 不把 runtime 暴露到區域網路，也不接受使用者任意指定啟動參數。

## 技術選擇

採用 CloudHime 管理的 `llama-server.exe` 子程序，使用 `llama.cpp/libmtmd` 官方 Gemma 3 Vision 支援。模型組合為：

- `models/gemma-3-4b-it.Q4_K_M.gguf`
- `models/mmproj-model-f16.gguf`
- `runtime/llama-server.exe` 及其必要 DLL

`llama-cpp-python` 目前沒有正式列出 Gemma 3 Vision 高階 chat handler，因此不在應用程式內仿造 handler。`llama-server.exe` 是 CloudHime 隨附並管理的本機 runtime，不是 Ollama，也不是使用者需自行安裝或維護的外部服務。

## 元件邊界

### `LocalVisionRuntime`

新增獨立模組，唯一責任是管理 vision runtime 生命週期：

- 解析 binary、文字模型與 projector 的絕對路徑。
- 檢查必要檔案與基本檔案大小。
- 配置僅供 loopback 使用的可用 port。
- 以隱藏視窗啟動 `llama-server.exe`。
- 輪詢健康端點並發出 `missing`、`starting`、`ready`、`failed`、`stopped` 狀態。
- 擷取有限長度的 stderr，供 UI 顯示失敗原因。
- 關閉時先正常終止，逾時後只強制停止自己建立且 PID/程序物件仍相符的子程序。

此元件不建構翻譯 prompt、不解析模型輸出，也不持有 Qt widget。

### `LocalMultimodalProvider`

保留現有 OpenAI-compatible HTTP client。由 worker 在 runtime `ready` 後注入 `http://127.0.0.1:<port>/v1`，不再要求一般使用者手填 URL。Provider 繼續負責：

- 將現有 base64 data URI 圖片送至 chat completions。
- 建構翻譯與截圖 prompt。
- 驗證、清理並回傳模型文字。
- 套用 timeout 與明確錯誤分類。

### `OCRWorker` 與 UI

Worker 擁有一個 runtime instance，將 runtime 狀態轉成既有 signal。UI 僅呈現狀態與進度，不直接管理 subprocess。關閉 CloudHime 時，Controller 要求 worker 停止 runtime，再結束 worker thread。

## 路徑解析

禁止依賴 current working directory。路徑根目錄依序為：

1. PyInstaller frozen 執行環境的 application/resource root。
2. 原始碼執行時模組所在目錄。

開發期固定尋找上述三個相對檔案。模型缺失時不得偷偷連網下載，必須進入 `missing` 並列出缺少的 basename。後續自動下載功能可替換模型取得層，不改 runtime 與 provider 介面。

## 啟動資料流

1. 使用者啟用內嵌本地多模態。
2. Worker 在背景 executor 呼叫 `LocalVisionRuntime.start()`，UI 顯示不定進度。
3. Runtime 驗證檔案，保留 loopback port，啟動 server 並等待健康檢查。
4. 健康檢查成功後，runtime 回報 base URL；worker 更新 provider 並刷新 registry。
5. 失敗時回報可理解原因，既有 Google 路徑仍可依原規則 fallback。
6. 重複啟用不得重複建立程序；已在 `starting/ready` 時回傳現有狀態。

## 圖片翻譯資料流

1. 現有截圖流程產生縮放後的 base64 data URI。
2. Worker 選擇已 ready 的內嵌 `LocalMultimodalProvider`。
3. Provider 傳送圖片與翻譯 prompt 至 loopback server。
4. Gemma 3 Vision 讀取畫面文字與上下文，回傳目標語言翻譯。
5. Provider 清理輸出並交回既有 bubble/render 流程。

內嵌多模態未 ready 時不得宣稱 provider 可用，也不得把圖片交給文字版 `LocalGemmaProvider`。

## 程序與安全

- Server 必須綁定 `127.0.0.1`，不可使用 `0.0.0.0`。
- Port 由 OS 動態選擇，不假定 8080 可用。
- Windows 使用 `CREATE_NO_WINDOW` 與隱藏 startup info。
- 命令列參數以 list 傳入，不經 shell 字串拼接。
- 只執行解析到應用程式 runtime 目錄內的 binary。
- 不記錄圖片 base64、完整 prompt、API key 或使用者敏感畫面。
- 關閉流程只回收本 instance 建立的 process handle，不依名稱掃殺其他程序。

## GPU 與 fallback

第一嘗試使用全 GPU offload、projector offload 與 `ctx=4096`，適配 RTX 3060 12GB。若程序在啟動期明確回報 CUDA/VRAM 錯誤，允許一次受控重啟：降低 GPU layers 或停用 projector offload。若仍失敗，回報 `failed`，不進行無限重試。

CPU fallback 可用於相容性診斷，但 UI 必須標示「CPU 模式，速度較慢」。正常產品路徑不應因 fallback 阻塞 UI thread。

## 狀態與錯誤

狀態機：

`stopped -> missing | starting -> ready | failed -> stopped`

錯誤至少分類為：

- `runtime_missing`
- `model_missing`
- `projector_missing`
- `port_unavailable`
- `process_start_failed`
- `health_timeout`
- `process_exited`
- `gpu_initialization_failed`
- `request_timeout`
- `invalid_response`

UI 對使用者顯示本地化短訊息；debug detail 保留錯誤類型與截斷後 stderr，不顯示大段底層日誌。

## 測試策略

### 單元測試

- frozen/source 路徑解析不受 cwd 影響。
- 缺少 binary、模型、projector 時回報正確狀態。
- subprocess 命令列包含 loopback host、動態 port、模型、mmproj 與 context。
- 健康檢查成功、逾時、提早退出與單次 GPU fallback。
- start idempotency 與 stop 只回收自身 process。
- Provider 僅在 runtime ready 時可用。

所有 subprocess、socket 與 HTTP 皆以 fake 注入，測試不啟動真模型。

### 整合測試

以環境變數顯式啟用，避免一般 pytest 載入數 GB 模型。測試必須：

1. 啟動隨附 runtime 與模型。
2. 等待健康檢查。
3. 將一張固定 `example/` 圖片以 data URI 送入。
4. 驗證回應非空、不是錯誤頁，且包含圖片中預先人工確認的至少一個關鍵文字或其合理翻譯。
5. 記錄冷啟動時間、首 token/完整回應時間、GPU/CPU 模式與峰值記憶體（可取得時）。
6. 停止 runtime，驗證 process 已退出且 port 可再次綁定。

## 驗收標準

- 一般使用者不需安裝或啟動 Ollama、LM Studio 或獨立模型服務。
- CloudHime 可從非專案 cwd 啟動本地 vision runtime。
- UI 在啟動期間保持可操作，並清楚呈現缺件、載入、成功或失敗。
- 至少一張 `example/` 真實圖片由 Gemma 3 Vision 產生可辨識內容的翻譯結果。
- 關閉 CloudHime 後不殘留 `llama-server.exe`，loopback port 被釋放。
- 文字版 Local Gemma 與 Google fallback 的既有 targeted tests 不退化。

## 資源、授權與打包風險

- `mmproj-model-f16.gguf` 約 851 MB，加上約 2.49 GB 文字模型；開發機需預留下載與解壓空間。
- Gemma GGUF 受 Gemma Terms 約束；正式配送前需保留授權通知並確認 Microsoft Store 配送符合條款。
- PyInstaller `onedir` 必須明確收錄 runtime binary/DLL；模型是否隨包配送留到產品化階段決定。
- CUDA wheel、runtime DLL 與 `llama-server.exe` 必須來自相容 llama.cpp revision，避免 ABI/功能不一致。
- 連續圖片請求可能有 MTMD GPU 記憶體壓力；整合 smoke 後需做有限次循環測試，若記憶體持續上升則在請求批次間重啟 runtime，而非容許無限增長。

## 分階段交付

### 階段一：真機證明

準備 `llama-server.exe`、DLL 與 `mmproj-model-f16.gguf`，建立 opt-in smoke，先證明指定 `example/` 圖片可被辨識與翻譯。

### 階段二：應用程式接線

實作 runtime manager、worker 狀態、provider 注入、UI 狀態與關閉清理，維持既有 fallback。

### 階段三：產品化

另案設計首次使用下載、續傳、SHA-256 驗證、授權同意、磁碟空間檢查與模型更新。此階段不改動本規格定義的 runtime/provider 邊界。
