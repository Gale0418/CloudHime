# Notes
## 2026-08-04：MSIX 信任與正式發佈 Prior Art

| Pre-search idea | Source | Adopted insight | License status |
| --- | --- | --- | --- |
| 以自簽憑證同時處理測試與公開發佈 | [Microsoft：MSIX 簽章總覽](https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview) | 拆成雙軌；自簽只供本機／CI，Subject 固定與 manifest Publisher 相同，正式公開版不要求使用者匯入憑證 | 官方文件，N/A |
| 正式版自行購買或代管公開憑證 | [Microsoft：Windows App 簽章選項](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options) | 第一版採 Store MSIX 代簽；Azure Artifact Signing／第三方 OV 僅保留為未來非 Store 直發候選 | 官方文件，N/A |
| 直接沿用開發 Identity 上傳 Store | [Microsoft：首次發佈 Windows App](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/publish-first-app) | 拒絕自行猜值；先在 Partner Center 保留產品，再原樣複製 Identity Name、Publisher 與 PublisherDisplayName 注入 builder | 官方文件，N/A |
| 先選任意 Partner Center 帳號再調整 | [Microsoft：開發者帳號類型](https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/open-a-developer-account) | onboarding 前先決定個人或公司身分；目前註冊費為零，但個人帳號不能直接升級為公司帳號 | 官方文件，N/A |

- 核准方向：路線 1 為 `CN=CloudHime Development` 的短命自簽測試；路線 2 為 Microsoft Store 正式代簽、安裝與更新。
- 非目標：本輪不購買 OV／EV 憑證、不建立 Azure Artifact Signing、不把任何 PFX／私鑰提交到 repo 或放進 dist。
- 第一個可驗收里程碑：CH-T52 在具管理員權限的乾淨 Windows 完成 sign → verify → trust → install → launch → uninstall → certificate/package cleanup。
- 帳號準備狀態：個人帳號已建立、狀態使用中、公開 Publisher=WindSheep；詳細資料驗證仍處理中。CloudHime 尚未建立產品，正式 Store 身分值仍不存在，也不得建造或宣稱正式提交包。

- 上一輪 UI 改造與穩定化 Sprint 1 / Sprint 2 已完成，目前不再以畫面花俏程度作為主軸。
- 與 Gemini 的分工是：由她先提供產品方向與任務草案，最後的範圍控制、優先級調整與驗收由 Codex 完成。
- 產品最終販售目標已收斂為 Microsoft Store，但不代表現在要先做上架包裝；現階段先處理會直接影響評價的準確與速度。
- 第一里程碑鎖定為 `準確度基準資料集 -> 速度基準與分段量測 -> 字典修正最小工作流`。
- 本地多模態相關任務不是取消，而是暫時降到 Backlog，待主通道品質有基準後再續做。
- 2026-07-02：CH-T13 已恢復並完成自動化接線；`local_multimodal_enabled` 會真正控制本地多模態 provider availability，URL / model 於欄位 editingFinished 才套用，避免每打一字刷新 worker registry。
- `CH-T17` 已先量本機 deterministic pipeline；後續若要比較 API / 本地模型實機速度，應沿用同一份 case 與 summary 格式追加，不覆蓋本機 baseline。
- `CH-T18` 已把字典修正最小工作流接進文字與多模態 provider；Mac 端可驗自動化與 prompt / cache / benchmark，Windows 原生 OCR、熱鍵與真實截圖泡泡體感仍需回 Windows 實機驗。
- 2026-07-10：Antigravity scoped review 已完成（HYBRID_REVIEW_DONE）；建議優先 OCR threshold/preprocess search，本地多模態與本地 Gemma 參數作為後續驗證，provider 路由暫緩結構改動。
- 2026-07-10：Prior art gate：Optuna TPE 有 random startup trials 與 pruner，Ray Tune ASHA 偏大規模訓練 early stopping，scikit-optimize GP 適合低維連續空間；CloudHime 第一刀先自製離線基準，等有穩定訊號再評估 Optuna。
- 2026-07-10：本地模型路徑固定為內嵌 `models/gemma-3-4b-it.Q4_K_M.gguf` 搭配 `llama-cpp-python`；不得把 Ollama 視為使用者前置安裝、產品依賴或 CH-T31 驗證條件。

- 2026-07-11：CH-T31 完成。Local Gemma3 改由背景 executor 載入，UI 提供不定進度、成功與失敗狀態；真實 GGUF 翻譯 smoke 為 `1 passed in 3.71s`，targeted regression 為 `34 passed, 1 skipped`。Gemini 最終審查後補上 executor 提交失敗、舊 Future callback 與 Python 3.8 shutdown 相容防護。

- 2026-07-13：CH-T14 真正多模態 smoke 完成。資產為 runtime/llama-server.exe、models/gemma-3-4b-it.Q4_K_M.gguf、models/mmproj-model-f16.gguf；使用 example/2026-07-10 00 37 20.png，GPU ready，啟動 4.61s、圖片請求 2.32s，回傳包含「這個版本沒有模型」與 Roboflow 的繁中翻譯，runtime 已正常停止。
- 2026-07-13：實機曾因另一個 llama-server 佔用 VRAM 而卡在 load_model；runtime 現在只在 GPU health timeout 且 stderr 明確含載入訊號時降級一次 -ngl 0，一般 timeout 不會被誤判成 CPU fallback。產品路徑仍是程式內嵌模型，與 Ollama 無關。
- 2026-07-13：CH-T34 已新增 `vision_smoke_benchmark.py`，使用 embedded `runtime/llama-server.exe`、`gemma-3-4b-it.Q4_K_M.gguf` 與 `mmproj-model-f16.gguf`；runner 支援 startup timeout、context size、force CPU、逐案 latency 與 line-match 指標，Ollama 不在路徑中。
- 2026-07-13：目前 Windows GPU 有另一個 `D:\MyGame\Dreamsprite\tools\llama-server.exe` 佔用約 7521/12288 MiB；CloudHime 的 GPU smoke 在 `-c 4096` 與 `-c 2048` 都卡在 load_model health timeout。依使用者要求未終止該外部程序，下一輪需在隔離 GPU 資源後重跑。
- 2026-07-13：CPU 5-case smoke 5/5 成功；中文 `quote_cn` line-match 1.0，日文字幕有 `終り/終わり` 與 `遠ぐ/遠くへ` 類字元誤讀，英文 UI 兩行命中，英文文章首行命中但整頁請求約 42.52s。這支持先調 OCR / prompt 與輸入切段，再談速度。

- 2026-07-13：CH-T34 smoke runner 現在可用 --ocr-hint，由 Windows OCR 產生提示後交給內嵌 Gemma 3 多模態；結果顯示 OCR hint 是目前唯一有可量化精度提升且平均延遲近乎持平的候選。整條路徑是程式內嵌 GGUF + llama-cpp-python / llama-server + mmproj，與 Ollama 無關。
- 2026-07-13：全圖 / 區域 / 氣泡 / 浮雕 / 截圖矩陣 7 tests 通過；發現截圖 layout 先移到掃描框外後又被 arrange_bubbles 搬回框內，已加最小 guard 修正。
- 2026-07-14：GPU smoke runner 已加入 --gpu-layers 與 --require-gpu；require_gpu 不接受 CPU fallback、force_cpu 或 gpu_layers=0，且 runtime 對 -ngl 0 回報 CPU mode。分段欄位包含 hint、image encode、model request、postprocess；路徑仍是內嵌 GGUF + llama-server + mmproj，與 Ollama 無關。
- 2026-07-14：實測 context=512/-ngl 20/startup=12s 與 context=512/-ngl 1/startup=90s 都在 load_model/load_tensors 後 health timeout；CloudHime 沒有殘留程序，唯一 llama-server 是外部 Dreamsprite PID 26364。未終止它，待釋放或隔離 VRAM 後重跑 GPU request。- 2026-07-14：補測 context=512/-ngl 999 全 offload，同樣在 load_model/load_tensors 後 health timeout；未進入 request，也未把 CPU fallback 當成功。
- 2026-07-14：Store-first packaging 約束已重新確認：CloudHime 最終目標是 Microsoft Store；目前 install.ps1 會安裝 Miniconda、pip 依賴並下載模型，install.bat / build_exe.bat 也只是開發者流程，未來不能直接當商店安裝器。候選基線是 MSIX，且要把 package read-only、AppData 可寫路徑、更新與模型資產大小一起納入設計。
- 2026-07-14：Microsoft 官方文件確認 Win32 / Qt 應用可透過 MSIX 發布到 Microsoft Store；MSIX 安裝檔位於受保護位置，應用不應寫入 package 目錄。CloudHime 的 GGUF + mmproj 約 3.34 GB raw，模型隨包發布或獨立受控取得仍待 CH-T26 決策；不把 Miniconda、pip 或 Ollama列為使用者前置條件。
- 2026-07-14：模型資產策略已拍板為核心 MSIX + app-managed model asset download。MSIX 內放主程式與必要執行檔；Gemma GGUF / mmproj 由 CloudHime 下載到使用者可寫的 AppData 資產目錄，完成版本、SHA-256、磁碟空間、斷點續傳與進度管理後才啟用本地 GPU 路徑。第一版不依賴 Store optional package。
- 2026-07-14：補充 optional package 研究：Microsoft 官方文件明確要求送 Store 前取得 permission，申請入口指向 Windows Developer Support，但沒有公開保證核准或標準處理時程。因此第一版維持 app-managed model asset，不讓上架依賴這個許可；待 Partner Center 帳號與產品用途說明準備好後再申請。

## 2026-07-15：日文專用 OCR Prior Art

- Google Gemma 3 官方資料：視覺編碼為 896x896，Pan-and-Scan 能增加細節但提高推論成本；因此不採全域高解析重跑。
- llama.cpp 官方 server 文件：多模態仍屬實驗功能，支援 mmproj GPU offload 與動態圖片 token；本輪不改全域 token 預設。
- meikiocr 0.3.1：專為日文遊戲文字訓練的 ONNX OCR，逐字提供 bbox/confidence；本機三權重約 43.8 MiB，CPU 完整 OCR 約 0.29s。
- 授權：PyPI 套件標示 Apache-2.0；官方 detection/recognition 模型卡標示 LGPL-3.0。正式 Store 發布前需保留授權、來源與可替換/重新下載邊界。
- 排除：EasyOCR 在目前 Windows 程序發生 libomp/libiomp5md 衝突；不採 `KMP_DUPLICATE_LIB_OK=TRUE`，因上游警告可能造成未定義行為。RapidOCR 對目標日文圖 4.44s 且無輸出。

## 2026-07-15：CH-T35 實作與驗證備忘

- 新增 japanese_ocr_assets.py：管理 AppData 路徑、pinned URL、續傳、大小與 SHA-256；新增 japanese_ocr_runtime.py：延遲匯入 meiki、背景下載與三模型 CPU 暖身、可取消狀態。
- worker 採 fail-open：只有 gate 通過且 meiki 候選可信時，才讓內嵌 Gemma 3 對原圖追加一次驗證；新結果必須對高信心字元的相似度嚴格提升才採用。
- 依賴固定為 meikiocr==0.3.1 與 opencv-python-headless==4.13.0.92，避免同時安裝 GUI / headless OpenCV namespace；未加入 Ollama。
- 真實 CPU runtime 對目標圖讀出「過ぎた街並は終わりの愛と遠くた」，後續 Gemma rescue 可校正為完整預期句。一次暫態異常輸出經直接套件、暖身順序與重跑檢查後未再重現。
- 中文版與英文版皆覆蓋日文 rescue 開關與啟用、下載、暖身、完成、失敗狀態；targeted regression 共 72 passed。

## 2026-07-16：CH-T36 字體盤點

- 原本 CloudHime.py 先指定 Helvetica Neue，再手動註冊 C:\Windows\Fonts 下的微軟正黑體、雅黑與細明體；TransBubble 又另外硬編碼 Microsoft JhengHei，造成應用字體與翻譯字體策略不一致。
- Gemini 建議移除硬編碼與字體打包；Codex 實測發現 stylesheet 建立順序下 self.font() 未必取得 overlay 的顯式字體，因此 helper 改為優先複製 parentWidget().font()，沒有 parent 才退回 QApplication.font()。
- 系統字體策略不新增下載、外部服務或 Ollama 前置條件，適合目前 Microsoft Store 核心包方向。

- 2026-07-16：漫畫封面 holdout 來源採 Wikimedia Commons 的《Tôbaé》(1888)、《少女世界》創刊號(1906)、《正チャンの冒険》(1923)、《少女畫報》(1926)、《少年倶楽部》(1929) 與《眼で見る時局雑誌／漫画》(1943)。每筆來源頁、原檔 URL、公版標記、尺寸與 SHA-256 記於 benchmarks/manga_cover_cases.json；未採授權狀態有爭議的現代商業封面。
- 2026-07-16：CH-T25 provider health 已接入 Translation 設定欄，狀態文字維持欄內顯示，不建立額外 Python 視窗；長英文提示以 word-wrap 與 width-ignored size policy 保持 430x720 緊湊版面不重疊。CodeRabbit base branch 問題確認源於暫存 review repo／缺少 origin/HEAD，主 repo 已補為 origin/main。
## 2026-07-18：CH-T40 協作與審查備忘

- Gemini 提醒 4K 動態畫面配置抖動與字典熱更新；前者採「先淘汰再配置」修正，後者因 provider 本來只在啟動時載入字典，重啟會同時清快取，目前不是快取獨有漏洞。
- Luna 獨立確認 4 個 worker finding 均成立，另發現 orientation 層也可能讓空噪音壓過有效負分短文字；兩層候選選擇都改為非空優先。
- CodeRabbit scoped review 只含 8 個程式／測試檔，排除圖片、模型、runtime 與 scratch；第一輪 6 findings 均成立並修正，第二輪 0 findings。
- 產品路徑仍是程式內嵌／受管下載 Gemma 與本地 runtime，與 Ollama 無關。

## 2026-07-18：CH-T41 實機觀察

- 首次 90 秒 GPU probe 停在 load_model/load_tensors；原始讀檔隔離後確認 model 已進 OS cache，而 mmproj 冷讀 86.54 秒，是 D 槽 I/O 而非 CUDA 死亡。
- 暖快取 1-case GPU probe startup 7.18s、request 10.18s；正式 25-case baseline 後 startup 降至 3.59s。冷啟動與暖快取數字必須分開報告。
- 正式 rescue 的日文候選為「過ぎた街並は終わりの愛と遠くた」，優於 baseline「過ぎた街並は終りの愛と遠ぐ」，但二次 VLM 仲裁未採用；顯示瓶頸已從 OCR 候選移到仲裁規則。
- Gemini 提醒 240 秒不可假死；現有進度 callback 已保留，另新增 runtime cancel event 與並行 stop 測試。

## 2026-07-23：Knowledge Pack 發行研究摘要

- `ddgs==9.14.4` 目前只列為待實作驗證的候選版；正式鎖定前須確認 Windows wheel、實際 transitive dependencies、搜尋可用性與 PyInstaller／MSIX 收集結果。
- DDGS GitHub／PyPI 標示 MIT，但 README 同時有 educational purposes only 免責聲明；發行時保留 attribution／license notice，並把 backend 定位為 best-effort／experimental，不宣稱商業 SLA 或官方搜尋授權。
- 現有 PyInstaller 腳本排除 `lxml`，若 DDGS 依賴鏈需要它會造成 packaged import／runtime 缺件；CH-T50 必須以實際鎖定版本重查 hidden imports、資料檔與 exclusions。
- 目前沒有已提交且可重現的 MSIX pipeline；現有 bootstrap／PyInstaller 流程不能當成 Microsoft Store 發行驗證。Knowledge Pack 的乾淨 Windows 搜尋能力留待 CH-T50／CH-T51。

## 2026-08-01：CH-T23 下一階段 release gate 研究

- Microsoft Learn 的 MSIX 文件確認 package install location 是受保護／唯讀；持久資料應放在 package 外的 `%APPDATA%`／`%LOCALAPPDATA%`，與 CH-T24／CH-T44 的 AppData-only 策略一致。
- 官方分發路徑比較指出 Microsoft Store 可提供 discoverability、trusted install、代簽章與更新交付；但真實 Store identity、WACK 與 Partner Center 仍不能由本地 contract 或 GitHub dummy dist 代替。
- 本機 `dist/CloudHime` 已有 457 個檔案、`CloudHime.exe` 與 embedded runtime；目前缺少 `makeappx.exe`／`signtool.exe`，下一個可執行 gate 是在具 Windows SDK 的環境用真實 dist 建包、安裝、GPU/AppData onboarding，再接 WACK／Store identity。
- 參考：[MSIX on Windows 10 and Windows 11](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/msix-windows10-windows11)、[Choose a distribution path for your Windows app](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/choose-distribution-path)、[MSIX containerization overview](https://learn.microsoft.com/en-us/windows/msix/msix-containerization-overview)。
## 2026-08-01：真實 dist smoke 邊界

- `dist/CloudHime/CloudHime.exe` 已完成 18 秒 packaged startup smoke，且 11 項必要 release asset 全數存在；這只驗證 PyInstaller dist 可啟動。
- 下一個 gate 仍必須在有 Windows SDK／簽章工具的環境執行真實 MSIX build、clean-account install/uninstall、AppData 模型下載與 GPU ready；不能把 dist smoke 升格成 Store readiness。
- 2026-08-03：已用 GPT 多模態視覺判讀 `example\轉生重騎士` 001～003，產生待主人確認的候選標註；目前不把它們宣稱成人工 ground truth。評估器新增 eligibility gate，會拒絕 draft／false／非布林 eligibility manifest。- 2026-08-03：CH-E8 新增 knowledge_research_draft.py，完成不觸發 active pack 的 DDGS／Jina 研究草稿契約；研究草稿 entries=[]、owner confirmation=false，來源保留 URL／時間／雜湊／bounded content。Knowledge Pack catalog 也加入 canonical file recovery。CH-T46 的 Gemma 4 extraction、來源合併與人工核准仍未完成。
## 2026-08-03：GPT 多模態候選擴充

- 以 GPT 視覺重新檢查 `example\転生重騎士\001.jpg`～`004.jpg`；001～003 與既有候選互相核對，004 新增旁白、標題與對話候選。
- `.private_japanese_subtitle_candidate_annotations.json` 現為 4 張候選，明確保留 `draft_requires_owner_confirmation`、`ground_truth_eligible=false` 與人工逐項確認規則；模型文字仍不是 ground truth。
- 因本地 `view_image` 受 Windows sandbox 限制，改以 workspace 內圖片縮圖送入目前 GPT 視覺能力，未使用 OCR 結果產生 anchors。

## 2026-08-03：CH-T46 extraction contract

- 新增 `knowledge_extraction.py` 與 15 個 focused tests：嚴格 schema、來源 allowlist、來源 ID 上限、重複 JSON key、回應大小／深度上限、Unicode 控制字元拒絕、低信心過濾、alias identity merge 與衝突隔離。
- 輸出永遠固定為 `status=candidate`、`owner_confirmed=false`；此模組不載入、不寫入、不啟用 Knowledge Pack。
- extraction 檔案等待下一個 CodeRabbit review window 後才建立 Git checkpoint。
## 2026-08-03：CH-T47 Worker 第一刀

- 新增 `knowledge_builder_worker.py`：research → extraction → merge → ready 分段進度，取消事件、job generation stale callback 防護與錯誤隔離。
- worker 只產生 `candidate`，不自動 activate；`promote(owner_confirmed=True)` 才透過既有 KnowledgePackStore atomic save 寫入非 active pack。
- focused worker regression `4 passed`；尚未接 UI、Gemma endpoint 或實機網路研究。
## 2026-08-03：CH-T47 Terra finding 修正

- Terra 只讀複核找出 5 個 worker 生命週期問題：取消完成競態、stale callback check-to-call race、promote lock gap／重複 promote、non-active 契約不明確、frozen result 可變資料外洩；另補出 JSON recursion error 邊界。
- 已修正：callback dispatch 與 generation／cancel 在同一 lock 線性化；promote 持鎖到 non-active save 完成並拒絕重複；結果以 deep snapshot 保存／回呼／讀取；extractor 使用 draft copy；RecursionError 轉為 ExtractionValidationError。
- 新增 `KnowledgePackStore.save_pack_non_active()` 明確表達不切換 active revision。修正後 extraction + worker 為 24 passed。
## 2026-08-03：GPT／Gemini 全頁視覺候選交叉覆核

- example\\転生重騎士 的 38 張 JPG 已由 5 批 GPT 多模態視覺 reviewer 與 5 批 Gemini 3.6 Flash High RPC 視覺 reviewer 覆核；所有輸出仍是 candidate，未使用 OCR 答案作 ground truth。
- 私有候選紀錄標記 ground_truth_eligible=false、owner_confirmation=pending，並列出 20 個高優先差異；主人必須逐頁確認，模型一致也不自動升格。
- Gemini 曾有一批 RPC 空輸出與 agy proxy 拒絕，重新 discovery 後改新 RPC 對話完成；失敗結果未納入覆核。

## 2026-08-03：CH-T47 checkpoint

- knowledge_extraction.py、knowledge_builder_worker.py 與 KnowledgePackStore.save_pack_non_active 已建立 Git checkpoint 1b2a5a5 並推送 origin/main。
- focused extraction／worker tests 26 passed；CodeRabbit 隔離 5-file 修正版複審 reviewedFiles=5、findings=0。
- store tests 12 collected，實際 non-active smoke 為 revision=1、active=None、packs=1；全量 store pytest 仍受本機 pytest 暫存目錄 ACL 阻塞，未宣稱全綠。

## 2026-08-03：CH-T48 bounded retrieval 第一刀

- 新增 knowledge_retrieval.py 與 9 個聚焦測試：exact／alias／casefold 優先、長度與結果數上限、短查詢不做 fuzzy、壞 entry fail-open、來源 ID 與 evidence context 邊界。
- build_evidence_context() 明確標記資料為 untrusted，拒絕混用不同 pack revision，並將 evidence 長度封頂；不改寫 OCR 原文，也不自動 activate。
- 35 focused tests passed（extraction + worker + retrieval），checkpoint 510811c 已推送。
- CodeRabbit 第一輪 4 issues 已修正；第二輪遇到免費 CLI rate limit，待冷卻後補審查。

## 2026-08-03：CH-T48 prompt evidence 與 revision cache 接線

- Gemini 3.6 Flash High 只讀審查建議：provider 內部 context、不改 translate(text) 契約、multimodal evidence 放 JSON 格式要求前、Worker 只在 pack 切換時更新 token。
- 新增 knowledge_prompt_context.py；LocalGemmaProvider、GemmaTranslationProvider、LocalMultimodalProvider 接入 bounded untrusted evidence，cache key 與 Worker exact-image context 納入 knowledge-pack revision。
- retrieval 補 contains 命中、fuzzy 256 字元 guard、跨多段 OCR 的 evidence 總量上限；不覆寫 OCR 原文。
- 32 focused passed；exact-image + cloudhime_workers 85 passed；checkpoint 01cb09f 已推送。
- CodeRabbit 有效問題已修正；最後複審因免費額度 rate limit 未完成，保持 Review，不記成 clean。
- 尚缺 Settings active pack 載入與 Save／Cancel 接線，CH-T48／CH-T49 不提前結案。
## 2026-08-03：CH-T49 Settings active work 第一刀

- SettingsWindowRevamp 頂部 Theme／Language 同列加入作品 QLineEdit、compact status 與 Research／Update action；沿用 theme token，輸入框優先縮小。
- `active_work_title` 進入 settings schema normalization、Controller payload、AppData load；本機 pack 以 title／alias 比對，不觸發 DDGS／Jina。
- Save 會 commit title 並載入對應 runtime pack；Cancel 只還原設定草稿，不刪除已存在的本機 pack。
- Research 按鈕目前明確 fail-open 為「Research is not configured yet」，因 Controller 尚未有可注入的 DDGS/Jina/Gemma4 builder；不能把 UI 佈線冒充完整研究管線。
- Verification：`py_compile`、`git diff --check`、settings normalization 7 passed、UI smoke 3 passed、pack title/alias manual smoke passed。
## 2026-08-03：CH-T49 Research builder 接線

- `knowledge_research_service.py` 將明確 Research 組成 DDGS → Jina Reader → Gemma4 structured JSON；來源內容以 untrusted evidence prompt 傳入，限制來源數、每來源字數、總 prompt 長度，並保持完整 source tags。
- `GemmaTranslationProvider.generate_structured_text()` 僅供明確 Knowledge research 使用，固定 JSON MIME、bounded output 與 Gemma4 model；一般翻譯不會呼叫網路研究。
- `Controller` 以 `KnowledgeBuildWorker` 接 service，progress／finished／error／cancelled 用 Qt signals 回 UI；Research 按鈕視為主人明確確認，promote 只寫 non-active pack，Save 才套用 active。
- Settings Cancel／關閉會取消研究並還原 title draft；CloudHime close_app 會取消並最多等待 2 秒，避免離開後留下活躍 Knowledge thread。
- CodeRabbit：第一輪 3 findings 已修正；修正版第二輪遭免費 CLI rate limit，保留 Review。Gemini RPC 120 秒逾時，沒有可採用回覆。

## 2026-08-14 - Fullscreen geometry Vision experiment

- Scope: CH-E9 hardening slice. OCR is used only for bounding boxes; local Vision is required to provide source text and translation. OCR text is blanked before the Vision request.
- Controls: locked owner-confirmed fullscreen manifest, same local GPU runtime, same model and product path, geometry_hints candidate, fail-closed execution marker.
- Results: three real GPU runs (batched, local-batch-ID remap, and per-region fallback) all stopped with bounded `response_region_mismatch` before promotion. No quality or speed promotion is claimed.
- Interpretation: the Heavy Knight Reincarnation episode is sufficient as a smoke corpus to expose the contract failure, but not sufficient as a generalization benchmark. The current local region-JSON contract remains unproven on real manga images.
- Decision: keep strict parsing and the execution gate; do not weaken validation or promote geometry mode. Preserve this as negative evidence for the next region-response contract investigation.

## 2026-08-14 - Fullscreen Vision crop/grid hybrid route gate

- Scope: CH-E9 accuracy-first fullscreen Vision hardening. OCR remains a location hint only for crop/grid routes; OCR text is not sent into the Vision prompt. A reliable short OCR cluster, including vertical Japanese bubble text, is deliberately kept on the local text route.
- Regression coverage: added padded/upscaled OCR-box crops, no-OCR 2x2 overlapping grid, transcription-to-text fallback, bounded observability codes, adapter/collector completion marker, and reliable OCR route tests. Existing unreliable OCR rescue remains protected by `is_unreliable_manga_ocr()`.
- Single-case GPU paired benchmark, locked owner case `owner-review-manga-2026-07-02`, 5 repeats: baseline quality `0.3141666667`, candidate `0.3141666667`, delta `0`, promotion gate `true`; baseline total average `1030.97 ms`, candidate `1016.63 ms`; candidate Vision prompt/decode coverage `0`, proving the reliable OCR text route.
- Full 4-case GPU paired rerun, same model/runtime/sampling/context and `--scan-mode fullscreen --geometry-hints --execution-order baseline_then_candidate`: baseline quality `0.1957581248`, candidate `0.3038367158`, baseline nonempty `0.75`, candidate nonempty `1.0`, all four case regressions `0`, promotion gate `true`. Per-case delta: contract `+0.0901478590`, game stream `+0.2897820717`, vertical short manga `0`, Marchen Crown `+0.0523844332`.
- Speed remains an explicit tradeoff: full-corpus baseline total average `2783.73 ms`, candidate `11181.79 ms`; candidate translation average `9357.65 ms`. Accuracy gate passed; speed is not promoted.
- First full-corpus rerun stopped fail-closed at exit 2 on `translation_fullscreen_crop_vision_request_http_500`; it is retained as negative runtime-stability evidence. A second rerun completed successfully at exit 0. No HTTP 500 is hidden or counted as a pass.
- Evidence: `.codex-heavy-knight-coverage-20260814/product-path-fullscreen-crop-grid-final-hybrid-rerun.json`, `.codex-heavy-knight-coverage-20260814/crop-single-manga-case.json`. The full run was not a balanced latency-order experiment; no Store, WACK, clean-machine, or broad public holdout claim is made.
## 2026-08-14 - Final after unreliable-OCR guard

- Final worktree GPU rerun completed with the existing locked 4-case manifest: baseline quality `0.1957581248`, candidate quality `0.3057910587`, baseline nonempty `0.75`, candidate nonempty `1.0`, per-case regressions `0`, promotion gate `true`.
- Per-case final deltas: contract `+0.0912110974`, game stream `+0.2923057764`, vertical short manga `0`, Marchen Crown `+0.0566148619`.
- Final speed evidence: baseline total average `2790.92 ms`, candidate `10978.13 ms`; accuracy is promoted for this locked corpus, speed is explicitly not promoted. Final evidence file: `.codex-heavy-knight-coverage-20260814/product-path-fullscreen-crop-grid-final-after-unreliable-guard.json`.
## 2026-08-14 - No-OCR grid direct translation speed slice

- Scope: CH-E9 performance follow-up after the accuracy gate. Only the no-OCR 2x2 grid may try direct `translate_screenshot`; an empty/error response falls back to the existing transcription -> text translation route. OCR-backed crop Vision is unchanged.
- Regression coverage: `test_fullscreen_grid_direct_translate_avoids_transcription_round_trip` proves direct mode uses one request per tile and preserves the old route when the flag is off; candidate adapter explicitly controls the mode.
- GPU game single-case experiment: candidate quality `0.2973055252`, nonempty `1.0`, promotion gate `true`, candidate total average `11123.48 ms`; prior grid route was about `19096.75 ms`. This is an accuracy-preserving speed improvement for the no-OCR game case.
- Final locked 4-case GPU paired run with candidate condition enabled and no environment override: baseline quality `0.1957581248`, candidate `0.3023028235`, baseline nonempty `0.75`, candidate `1.0`, regressions `0`, promotion gate `true`. Per-case delta: contract `+0.0889230222`, game `+0.2982899386`, vertical short manga `0`, Marchen Crown `+0.0389658339`.
- Final speed comparison: baseline total average `2781.17 ms`, candidate `8886.87 ms`, candidate translation `7077.14 ms`; approximately 19% faster than the previous candidate route, but still not a speed promotion against baseline.
- Evidence: `.codex-heavy-knight-coverage-20260814/product-path-fullscreen-grid-game-direct-translate-experiment.json`, `.codex-heavy-knight-coverage-20260814/product-path-fullscreen-crop-grid-final-direct-grid-condition.json`. No Store/WACK/clean-machine claim is made.

## 2026-08-14 - Shared runtime blocked-start cleanup regression

- Scope: single `llama-server.exe` lifecycle hardening. Added assertions to `test_coordinator_release_during_blocked_start_removes_entry` so coordinator release must leave the spawned process terminated and `LocalVisionRuntime.owned_process` cleared, not merely remove the lease table entry.
- Regression result: targeted admin-isolated pytest `1 passed in 0.17s`; full `tests/test_local_vision_runtime.py` `58 passed in 0.66s` with `QT_QPA_PLATFORM=offscreen`, `-p no:cacheprovider`, and workspace basetemp.
- Environment evidence: ordinary-token pytest first produced `7 passed, 51 errors` because pytest-qt could not access `C:\Users\USER\AppData\Local\Temp\pytest-of-David2019` (`WinError 5`); this is retained as an environment/ACL limitation, not counted as a code pass or failure of the runtime assertions.
- No real model, GPU, Store, WACK, or clean-machine lifecycle claim is made by this unit-test slice.
## 2026-08-14 - In-flight runtime release cleanup hardening

- Root cause: when the final lease was released while llama-server.exe startup was still in flight, the coordinator could mark the entry stopped and later skip cleanup if startup returned ready.
- TDD RED: the new coordinator regression produced 1 failed, 8 passed; the failure showed a runtime returning ready after the last lease had been released, with the runtime still not stopped.
- GREEN: $env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests\test_local_runtime_coordinator.py tests\test_local_vision_runtime.py -q -p no:cacheprovider --basetemp=.codex-runtime-lifecycle-final-admin-20260814 -> 67 passed in 0.94s.
- python -m compileall -q local_runtime_coordinator.py tests\test_local_runtime_coordinator.py and git diff --check -- local_runtime_coordinator.py tests\test_local_runtime_coordinator.py both exited 0.
- No real model, GPU, Store, WACK, or clean-machine claim is made by this unit-test slice.