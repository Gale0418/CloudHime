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
## 2026-08-21 - Background Hybrid Search exact-frame commit gate

- Root cause: background threshold calibration computed against a copied frame and could commit its result after auto mode was disabled, the user changed the threshold, the scan mode changed, or a newer captured frame replaced the calibration source.
- Implementation: threshold search can now run without committing; the background path adopts a result only while auto mode remains enabled, the base threshold and scan mode are unchanged, and shape/dtype/offset plus np.array_equal still match the latest captured frame. Threshold state and capture snapshot writes share a narrow RLock; OCR work remains outside the lock.
- Same-frame rescans remain eligible, while different frames fail closed. No new OCR candidate, dependency, network request, GPU work, or Ollama dependency was added.
- TDD evidence: the commit contract first failed with 3 failed, 83 passed; the newer-frame contract separately failed with 1 failed, 3 passed, 83 deselected; the scan-mode contract failed with 1 failed, 88 deselected, then passed with 1 passed, 88 deselected. Final affected suite: 243 passed in 12.73s.
- compileall and diff-check both exited 0.
- CodeRabbit review was not executed: the external payload gate rejected this uncommitted two-file diff because prior authorization covered a different isolated five-file review payload. No CodeRabbit pass is claimed.
- No real OCR accuracy benchmark, GPU, Store, WACK, clean-machine, or latency promotion claim is made by this correctness slice.
## 2026-08-22 - Confidence-aware bounded Hybrid Search rescue

- Root cause: the production OCR path discarded backend line/word confidence in `extract_raw_items()` and again during orientation remapping. Threshold/preprocess and multi-backend ranking therefore treated confidence-capable results as unknown, while runtime bounded preprocessing only ran for empty OCR.
- Implementation: confidence is normalized to 0..1 and preserved through extraction/remapping. Empty OCR keeps the existing bounded rescue. Nonempty OCR triggers the same two-preprocess rescue only when observed weighted confidence is below 0.45; replacement requires candidate confidence >= 0.60, a >= 0.15 confidence gain, and a strictly better relaxed local score. Unknown/high-confidence fast paths add no OCR calls.
- TDD RED: five new contracts failed (`5 failed`): confidence was absent, equal-length threshold selection chose the first low-confidence result, quality helpers were missing, and nonempty low-confidence OCR was not rescued. Targeted GREEN: `5 passed in 1.96s`.
- Verification: affected worker/mode/Hybrid suite `214 passed in 11.59s`; complete CI OCR group from `ci/test_groups.json` `284 passed in 15.98s`; OCR text/backend thread-safety suite `11 passed in 1.50s`; compileall and `git diff --check` passed.
- Windows OCR screening: `python hybrid_search_benchmark.py benchmarks\ocr_accuracy_cases.json --backend windows --max-cases 5 --max-strategies 24 --json` exited 0. Best complete strategies were `gray:t70:x2` and `gray:t130:x2`, each `3/5` hits; this is a small screening result, not a global accuracy claim.
- Microsoft Learn documents no confidence property on Windows.Media.Ocr `OcrLine` or `OcrWord`. Therefore Windows-only output remains fail-conservative; the new gate primarily benefits confidence-capable backends and mixed-backend arbitration. No GPU, GGUF, Store, WACK, clean-machine, or end-to-end latency claim is made.
- One attempted supplemental command named nonexistent `tests/test_ocr_backends.py` and ran zero tests; it is explicitly excluded from pass evidence. CodeRabbit was not retried because this new payload has no separate external-review authorization.
## 2026-08-22 - Fixed-profile runtime policy paired gate

- Added a target-leakage-free paired evaluator to `hybrid_search_benchmark.py`. Each unique source is decoded once; a fixed `binary_invert:t100:x2` baseline and the bounded `adaptive_invert` / `clahe_otsu_invert` candidates use the same ordered backend chain. Ground truth is consulted only after policy selection.
- The evaluator reports assertion hits plus source-level adoptions, improvements, regressions, completeness, and baseline/policy latency. `promotion_safe` means complete with no regression; the CLI succeeds only when `accuracy_promoted` also proves a net hit improvement. Missing images fail closed.
- TDD: evaluator RED `4 failed, 10 deselected`, GREEN `4 passed, 10 deselected`; evidence-driven promotion/default-off contracts RED `6 failed, 10 deselected`, GREEN `7 passed, 10 deselected`.
- Production response to the negative benchmark: confidence propagation and confidence-aware backend ranking remain active with zero added calls. Nonempty low-confidence preprocessing rescue is now experimental and disabled by default; only `CLOUDHIME_LOW_CONFIDENCE_HYBRID_RESCUE=1` opts in. Empty OCR keeps the existing bounded rescue.
- Final affected suite: `229 passed in 48.19s`; complete CI OCR group: `285 passed in 19.57s`; targeted core inventory/benchmark lock/Hybrid suite: `35 passed in 5.38s`; compileall and diff-check passed.
- The full core group was not completed: an unbounded local invocation reached about 34%, then produced no progress beyond the CI runner's normal 120-second limit and was interrupted. Follow-up probes passed `tests/test_knowledge_search.py` (`14 passed`) and model/remote/backend-installer files (`29 passed`); these probes do not turn the interrupted full group into a pass.
- Fixed-profile 25-case Windows+RapidOCR paired rerun: baseline/selected `13 -> 13`, adoptions `1`, improvements `0`, regressions `0`, complete `true`, promotion safe `true`, accuracy promoted `false`, average latency `8367.46 -> 9701.01 ms/source`; command returned nonzero as designed.
- Fixed-profile Windows-only comparison: `11 -> 11`, adoptions `1`, improvements/regressions `0/0`, average latency `91.51 -> 100.01 ms/source`, accuracy promoted `false`. The mixed chain gains 2/25 hits but costs roughly 91x baseline latency in this fixed profile, so neither removing RapidOCR nor enabling unconditional rescue is promoted. Next evidence target is a Windows-first conditional RapidOCR waterfall.
- This evaluator is explicitly a fixed-strategy profile, not a complete replay of production dynamic scaling, regions, orientations, cache, Vision-first routing, or GPU behavior. CodeRabbit was not run because this payload lacks separate external-review authorization.
## 2026-08-22 - Backend waterfall paired rejection gate

- Added a fixed-profile all_backends versus primary_then_empty evaluator and CLI mode to hybrid_search_benchmark.py. Policy selection sees only the image, strategy, and ordered backend chain; expected text is used only afterward for paired scoring.
- Contracts now distinguish thrown exceptions and OCRResult(error=...) from ordinary empty OCR, preserve deterministic backend-order ties, fail promotion on incomplete evaluation, and require accuracy preservation plus both average and p95 latency improvement.
- TDD RED: 5 failed, 14 deselected in 1.89s before the evaluator existed. GREEN: the full benchmark module passed 21 passed in 0.83s; the private pytest runner then passed CI inventory, benchmark lock, and Hybrid benchmark tests: 42 passed in 10.16s. compileall and diff-check passed.
- Fixed binary_invert:t100:x2, Windows then RapidOCR, 25 cases / 7 sources: baseline 13/25, candidate 11/25, improvements 0, regressions 1, secondary attempts 1, failed backend calls 0, complete true. Average latency improved 5817.83 -> 511.61 ms/source; p95 improved 11413.82 -> 1892.06 ms/source; speedup 11.37x; promotion_ready=false.
- The single regressing source was example/2026-05-01 14 09 56.png: Windows produced "Exclusive lnvite: Forbes" and "\Vine Club", while RapidOCR produced both expected lines. No source-specific punctuation heuristic was added because that would tune on the evaluation case rather than prove generalization.
- Production OCRWorker behavior was intentionally unchanged. The next safe evidence step is a pre-registered observable reliability gate evaluated on an untouched holdout; simple first-nonempty fallback is rejected despite its speed.
- One direct combined pytest run encountered the known Windows basetemp cleanup WinError 5 and is not counted as a pass. A first runner invocation passed the three paths as one comma-delimited argument and ran zero tests; it is also excluded. No GPU, Store, WACK, clean-machine, or production latency claim is made.
## 2026-08-22 - Explicit low-confidence fullscreen Vision admission gate

- Root cause: should_skip_fullscreen_crop_vision_for_reliable_ocr() classified short/compact nonempty OCR as reliable without considering backend confidence. Explicitly low-confidence output could therefore skip fullscreen crop Vision and remain on the text route.
- TDD RED reproduced the gap: 1 failed, 111 passed. The first proposed policy treated missing confidence as unreliable. Unit tests passed, but the owner-confirmed GPU paired gate rejected it: aggregate quality improved 0.195758 -> 0.287449 and nonempty 0.75 -> 1.0, while owner-review-manga-2026-07-02 regressed 0.314167 -> 0.235294. That policy was not retained.
- Final policy is narrower and evidence-driven: when every nonempty OCR item exposes confidence, weighted confidence below 0.60 cannot skip Vision. Unknown or partially missing confidence preserves the existing geometry/text route; high-confidence compact OCR keeps the fast path. Empty placeholders are excluded consistently from confidence, anomaly, count, and geometry calculations.
- Final affected worker/mode/pipeline/provider/product-path suite: 284 passed in 10.65s. compileall and git diff --check passed. An intermediate mechanical edit caused 5 failed, 279 passed by referencing nonempty_items before initialization; it was corrected and is not counted as pass evidence.
- Final owner-confirmed GPU gate, 4 cases x 5 repeats: candidate quality 0.309355 versus baseline 0.195758; nonempty 1.0 versus 0.75; coverage 1.0; case regressions none; promotion gate true; all records local/GPU with residual_processes=0. Latency remained slower: total average 5447.32 -> 16201.97 ms and p95 7039.43 -> 34322.98 ms. This is an accuracy/correctness pass, not a speed promotion.
- Windows OCR language inventory on this machine contains only ja and zh-Hant-TW. An en-US train/dev probe returned no engine, so no English-language-pack routing assumption was added. Microsoft Windows.Media.Ocr supports language-specific recognizers, but installed packs vary by machine.
- A visible-first Gemini bridge attempt failed first with unable to open database file and then with planner config is not declarative: not set; no Gemini answer or review is claimed. Three local Luna read-only reviews completed and were closed.
- The remaining llama-server process was verified as D:/MyGame/Dreamsprite/tools/llama-server.exe and was not touched. The nine private .codex-* evidence directories remain untracked and untouched. CodeRabbit was not invoked for this new payload because no separate external-review authorization was established.
## 2026-08-24：Knowledge Pack／remote discovery regression rerun

- 重新執行 Knowledge Builder、extraction、Pack Store、prompt context／integration、research、retrieval、search，以及 remote model discovery／availability worker：`105 passed in 6.61s`；使用 `QT_QPA_PLATFORM=offscreen` 與隔離 runtime fixture，未把 pytest temp ACL 問題誤算成產品失敗。
- CH-T48 的 retrieval／prompt evidence／revision cache correctness 維持通過，但因既有 CodeRabbit 複審尚未完成，任務仍保持 Review；CH-T49 同理，未因測試綠燈提前結案。
- CH-T67 的 offline snapshot／worker regression 維持通過；沒有有效 API key，因此沒有宣稱 live `models.list` 或遠端 availability 已完成。
- 本地 `main` 已推送 `524d096` 到 `origin/main`。相對於 origin 的 56 個 tracked changes 中，新增／修改 example 圖片數為 0；受保護的私有 evidence 目錄未觸碰。
## 2026-08-24 - Packaged functional smoke evidence-chain hardening

- Root cause: `packaging/test_release_smoke.ps1` previously used `test_clean_machine.ps1` only to prove the frozen EXE stayed alive, then ran the real functional Vision smoke with host `$PythonPath`. A broken packaged entrypoint could therefore pass the functional stage.
- Implementation: added the opt-in `packaged_functional_smoke` entry mode to `CloudHime.py`; `test_clean_machine.ps1` can now wait for a functional exit code and pass controlled environment variables; `test_release_smoke.ps1` validates inputs with host Python but obtains the final functional result from `CloudHime.exe`. The frozen spec bundles the dynamically loaded `packaging/runtime_manifest.py` validator.
- TDD RED: `4 failed, 8 passed in 1.39s`; GREEN targeted release functional/orchestrator/packaging `37 passed in 3.78s`; affected release/MSIX/CI contract run `74 passed, 1 deselected in 61.29s`; UI regression group `54 passed in 4.08s`; compileall and diff-check passed.
- Frozen build boundary: the authorized `build_exe.bat` attempt was interrupted because the current CloudHime `runtime/llama-server.exe` did not produce `--version` within the deterministic 5-second probe; `packaging/runtime_manifest.py` exited 1 with `RuntimeError: llama-server --version timed out after 5s`. No CloudHime-owned server remained afterward. The unrelated `D:/MyGame/Dreamsprite/tools/llama-server.exe` process was left untouched.
- No frozen EXE functional pass, real GPU benchmark, clean Windows VM, WACK, Store, or live Models API claim is made from this slice. The packaged functional path is contract-tested, but still requires a valid runtime and real frozen build for hardware evidence.
- Collaboration note: the local Gemini bridge suggested a mutex/timeout direction but hallucinated a nonexistent `translation_orchestrator.py`; existing `_LocalRequestScheduler` and `LocalVisionRuntimeCoordinator` already cover the relevant serialization/lifecycle boundaries. The read-only Luna/Bacon review identified the packaged-versus-host functional smoke gap that this slice closes.
## 2026-08-24 - Frozen release GPU packaged smoke passed

- Runtime diagnosis: the 9,216-byte `llama-server.exe` is a valid PE launcher and its adjacent `llama-server-impl.dll` is required. The first manifest timeout came from an incomplete interrupted `build/runtime` staging directory; the staged copy returned Windows `0xC0000139` until all CUDA/OpenMP dependencies were copied.
- Build recovery: completed staging of 26 runtime files, generated a valid manifest, prepared release provenance with 54 components, built PyInstaller dist, and passed the built-in packaged import smoke plus `verify_release_dist.ps1`. Final dist preflight reported `FileCount=391`, `ModelFiles=0`, `Bytes=1584915941`.
- Real packaged GPU smoke command used the fresh `dist/CloudHime` with the existing local Gemma 3 4B GGUF, mmproj, and `example/10001.png`, with `-RequireGpu -LaunchWaitSeconds 30 -TimeoutSeconds 300`. It passed release preflight, input validation, environment-isolated packaged launch, and functional Vision smoke executed from inside `CloudHime.exe`.
- Machine-readable result was accepted by the orchestrator; the result JSON was redacted and removed. A precise executable-path check found `0` CloudHime-owned `llama-server.exe` processes after cleanup. The unrelated Dreamsprite runtime was not inspected for cleanup and was not touched.
- Provenance boundary: the source runtime directory did not contain `runtime-source.json` or `llama-runtime-commit.txt`, so this local build explicitly supplied `LLAMA_RUNTIME_COMMIT=1d1d9a9ed`, matching the server's `--version` build identifier. This proves the local build path, but is not equivalent to archived download URL/hash provenance; CI/runtime fetch provenance remains the stronger release path.
- No accuracy score, translation quality promotion, clean Windows VM, WACK, Store certification, or live Models API claim is made by this smoke. It proves packaged runtime wiring and one real GPU Vision request only.
## 2026-08-24 - Unsigned MSIX build and unpack contract passed

- MSIX preflight against the fresh frozen dist passed: `FileCount=391`, `ModelFiles=0`, `Bytes=1584915941`, release provenance verification passed.
- Windows SDK x64 `makeappx.exe` was found at `10.0.26100.0`. `packaging/build_msix.ps1` created the unsigned development package `dist/CloudHime-0.1.0.0-x64.msix`; package creation succeeded. The one-shot stage directory was removed by the builder.
- The package was unpacked with the same x64 `makeappx.exe` into a unique temporary directory. Strict recheck passed: manifest `Name=CloudHime`, `Publisher=CN=CloudHime Development`, `Version=0.1.0.0`; `393` unpacked files; extracted runtime manifest valid with `26` files; `0` GGUF/mmproj model files; temporary unpack directory removed.
- A naive filename scan reported one `api-ms-win-crt-private-l1-1-0.dll`; this is a Windows CRT API shim, not private material. The only PEM was the public `certifi/cacert.pem` CA bundle. No `.env`, `.pfx`, `.key`, secret, or API-key material was found after those allowlist distinctions.
- This is an unsigned development MSIX contract result only. CH-T52 installation requires an explicit owner-authorized short-lived `CN=CloudHime Development` certificate, x64 SignTool, Administrator/AppX deployment, activation, and cleanup. It must not be reported as Store identity or Store certification.

## 2026-08-30：CH-T107 Prior Art 預註冊

- Pre-search idea：在既有 TranslationProvider 契約外新增 provider capability 與 model-specific rate／cooldown state，讓 UI 只依狀態模型渲染，不直接驅動遠端實作。
- 比較路徑：Adopt 現成 retry／quota library、Adapt 官方 API 契約、Learn 開源 provider router、或以現有小型架構 clean-room build。
- 硬限制：不新增未經核准的 runtime dependency；不讀取或持久化 OWO.TXT；來源優先官方文件；GitHub 專案須記錄維護、授權、依賴與退出成本。

### Representative screening

| 候選 | 分類 | 採用洞見 | 授權／成本 |
| --- | --- | --- | --- |
| `openai/openai-python` | Learn | Responses、`output_text` 與同步／非同步 client 契約 | Apache-2.0；第一階段不加依賴 |
| `googleapis/python-genai` | Learn | typed content/image adapter 與 API migration 警示 | Apache-2.0；即將有 major AFC 變更，先不採 |
| `BerriAI/litellm` | Reject runtime | 可學 provider normalization、routing 與 virtual key 分層 | gateway／SDK 面積與營運成本超過桌面 app 需求 |
| `pbakaus/impeccable` | Learn | Operate mode、方向契約、bounded visual QA | Apache-2.0；僅設計流程，不進 runtime |

- Adopt／build：以既有 urllib 為 transport，新增 CloudHime 自有小型 model／quota runtime，讓單一 Google API key 在兩個 Gemma 模型間依各自 rate／cooldown 選擇；完整決策見 `docs/adr/001-online-provider-routing.md`。

## 2026-08-30：CH-T107 專家收斂與基線

- 三個 Luna 唯讀專家分別完成 API 架構、PyQt／遊戲 UX、資安／QA 審查；Antigravity 的 `gemini-3.6-flash-high` 唯讀研究亦已取回完成 marker。
- 共識：採中央 runtime、provider adapters、單一 Google API key 的 DPAPI secret、非同步 UI 與故障注入；Online Gemma 使用 `gemma-4-26b-a4b-it`／`gemma-4-31b-it` 雙模型並保留 Local Gemma。
- 否決：不從 key 或不保證存在的 header 猜 Google Project ID；Google 官方 limits per project 且 each model variation has its own rate limit，因此只按模型維護 cooldown。安全輪替限明確 429／404／503 且無串流輸出；timeout／URLError 不重播、不切換。
- 契約基線：所有 Gemma 使用 `thinkingLevel=minimal`；Luna 使用 reasoning effort `none`。
- 主代理可重現基線：`python -m pytest -q tests/test_secret_store.py tests/test_settings_store.py tests/test_translation_providers.py tests/test_translation_orchestrator.py tests/test_remote_model_availability_worker.py tests/test_cloudhime_workers.py tests/test_cloudhime_ui_smoke.py` → `229 passed in 3.32s`。
- Mission Center CLI 相容性：`doctor` 與 `sync` 可解析新增 canonical rows，但 `transition CH-T107/CH-T108 ...` 仍回 `unknown_task`；保留錯誤證據，不手改 managed lifecycle summary。

## 2026-10-02T18:24:18+08:00：CH-T117 原始碼審查與同步

- 審查採忽略目錄下的獨立 Git 投影：本輪 18 檔用原始 HEAD 差異，歷史檔用空基線完整補審；投影歷史不是產品新增檔案的歷史。
- 排除資產、模型、產物、機密與不相關大型檔案；有修改的核心大檔保留完整上下文。排除不代表已證明無缺陷。
- CodeRabbit 第一輪 too_many_files 後用新範圍重試；只有完整 finding 事件與完成訊號才算完成審查。正式結果逐項查證後才修改。
- 原始碼推送依主人明確授權直接 main；正式評議與套件發行狀態各自記錄。詳細範圍與 SHA-256 在 output/mission-center-evidence/rabbit-retry-scope-20261002.json。

## 2026-10-02T18:47:18+08:00：CH-T117 技術審查完成

- Timestamp：2026-10-02T18:47:18+08:00
- Change：148 檔初審的 12 issues 已逐項查證修復，20 檔聚焦複審 0 issues；指定驗證 531 個不同案例通過，README 與 CI inventory 已更新。
- Reason：依主人「確認真的有問題再修」及每小時三次、每次 150 檔限制完成。首次 too_many_files 與未完成的正式評議都保留真實狀態。
- Impact：主窗、引擎與歷史程式可追溯至 reviews/2026-10-02-coderabbit-main-sync.md；原始輸入雜湊見 coderabbit-scope.json。正式 critic_full 預算未授權，CH-T117 Review／SmokeTest YES／Review NO。

## 2026-10-02T18:54:39+08:00：CH-T117 main 同步與 CI 對帳

- Timestamp：2026-10-02T18:54:39+08:00
- Change：原始碼 2a802305ee91d05e9e9bfc8f5053dfab61f7297f 已直接推送 GitHub main，遠端與本地 SHA 相同；CI run 36997658191 completed／success。
- Reason：主人授權存 Git、CodeRabbit、README／Mission Center 更新與 main 上傳；以真實遠端結果補登，避免預先宣稱成功。
- Impact：八個必需 CI 工作成功；兩個 real frozen release 工作依既有條件 skipped。純文件對帳提交使用 [skip ci]，程式碼驗證對應原始碼 SHA。正式評議仍缺明確預算授權，Review 保留；Store 與新套件未完成項不改寫。
- CI：[執行結果](https://github.com/Gale0418/CloudHime/actions/runs/36997658191)。

## 2026-10-02T20:12:14+08:00：CH-T117 原生驗收與新 light 預覽

- Timestamp：2026-10-02T20:12:14+08:00
- Change：Windows 原生啟動觸發 SelectionOverlay 提示尚未初始化的 AttributeError；以最小事件順序修復並補回歸。224 個不同案例通過；CodeRabbit 本小時一次，實際 135 檔／0 issues。
- Reason：主人授權 Computer Use GO，從實際 Python 3.10 啟動查證問題，再重建獨立 light EXE；舊 dist／Store 保留。
- Impact：新 EXE 建置／import／dist verifier 通過；原生主窗、設定開關、退出、設定寫出重啟與 CPU 單圖 Vision smoke 通過。capture timeout／click geometry unavailable，外觀、框選與完整 UI 流程未完成。CH-T117 保留 Review／Review NO；正式評議 not dispatched: approval/budget missing。
- Evidence：reviews/2026-10-02-native-acceptance.md；原始紀錄在 output/acceptance-ui-20261002、建置在 output/acceptance-20261002-194531。

## 2026-10-02T20:16:55+08:00：CH-T117 原生修復 main／CI 對帳

- Timestamp：2026-10-02T20:16:55+08:00
- Change：main 原始碼 7c93c153d345483ae489aae5a5c6dd07ba9abf48 已推送並對帳；GitHub CI 37005380465 completed／success，八個必需工作成功、兩個 frozen release 工作 skipped。
- Reason：依實際遠端結果補登，本次純文件提交 [skip ci]，不把文件 SHA 當程式碼 CI SHA。
- Impact：新本機 light EXE 與 CPU 單圖 smoke 各有獨立證據；完整 UI／Store 與正式評論仍未完成，CH-T117 Review 保留。

## 2026-10-03T10:11:56+08:00：雲朵版來源、驗證與候選套件

- Timestamp：2026-10-03T10:11:56+08:00
- Change：2026-10-03 雲朵來源 bff0c4f 已同步 main，CI 37084989820 success／八項成功、兩項手動 skipped；CodeRabbit 15 檔初審一項 minor 已修、2 檔複審 0 issues；238 個不同測試通過。新 EXE frozen OCR 兩行、import、CPU Vision 1/1、light/full verifier 與 40-component provenance 通過；light ZIP、unsigned dev MSIX、完整 Store 0.1.2.0 候選 MSIX／upload 已建立並核對 CRC／manifest／模型與 EXE 雜湊；尚未上傳或發布，WACK／本次安裝與正式評議未執行。
- Reason：主人定案雲朵並 GO；依實際產物而非舊預覽驗證。
- Impact：保留 Review／Backlog，未更新私人 Store 舊安裝；未宣稱一般 GUI 啟動後偏好 hash 完全不變。正式評議 not dispatched: approval/budget missing。
- Evidence：reviews/2026-10-03-ocr-cloud-release.md；docs/release-two-track.md；output/cloud-release-20261003/artifact-verification.json。

## 2026-10-04T00:29:43+08:00：CH-T117 來源修復與評議 checkpoint

- Timestamp：2026-10-04T00:29:43+08:00
- Change：修復Google transport、租約release、快取容量/LRU、背景關閉。來源1623 passed／6 skipped；CodeRabbit修正審查0issues。
- Reason：使用者全面抓蟲與已核准正式評議。
- Impact：三評論／仲裁判limited，resources實作coverage不足且席次工具用完；Review保留，未Done或發布。另有Antigravity越界憑證事件待owner rotation，token值未保存。
- Evidence：reviews/2026-10-04-hardening.md；output/mission-center-critique/CH-T117-hardening-20261004.json。

## 2026-10-04T01:13:07+08:00：CH-T117 CI 與資源收尾續作

- Timestamp：2026-10-04T01:13:07+08:00
- Change：e3dae59 的 CI37137115838 七項成功、UI 群組原生 access violation。native join補查有舊callback提早完成的red證據；候選合併UI仍timeout180秒，保留stack且僅回收自己測試程序樹。
- Reason：使用者核准追加4000tokens／12工具／10分鐘並要求本任務持續至無P0/P1、不再重複詢問。保留先前limited／工具用量，不把授權當驗證結果。
- Impact：Review保留；獨立資源席補查cache／lease／retrieval／packstore，提出兩項P2待重現；增派限定知識包資源覆蓋3000tokens／6工具／10分鐘，計入追加用量。UI及runtime修復分檔獨立進行。
- Evidence：reviews/2026-10-04-hardening.md；output/audit-hardening-20261003/join-diagnosis-result.json；output/mission-center-critique/CH-T117-hardening-20261004/resources-closure-report.json。

- 2026-10-04 CH-T117：定稿 229 案來源雜湊固定驗證通過；stop/start 競態、知識 worker 真正終止與 Qt DeferredDelete 排序修復。使用者授權任務內持續收尾；新 CI 和 final council 完成前仍 Review。

## 2026-10-04T02:56:59+08:00：CH-T117 最終來源收尾

- 來源 cfee16c 已同步 main；CI37143598031八必需成功、兩手動frozen skipped。
- 三評論與全新獨立仲裁核對255項manifest，最終passed；13項finding為10 fixed／3具體反證駁回，沒有未處置P0／P1或已確認範圍內P2／P3。原limited、失敗與超額用量保留。
- CH-T117完成來源驗收，passport與原生transition為正式生命週期證據；續讀reviews/2026-10-04-hardening.md與output/mission-center-critique/CH-T117-closure-proof-20261004.json。
- 沒有新EXE／Store／live／實體桌面驗收；其他任務gate維持。PAT事件仍需owner撤銷替換憑證、確認Antigravity當次工作停止，沒有聲稱解除；同一任務的追加收尾已獲持續授權。


## 2026-10-04T04:43:46+08:00：產品體驗來源與 main 同步收尾

- Timestamp：2026-10-04T04:43:46+08:00
- Change：可信任狀態、引擎／資料去向摘要、字幕暫停／繼續／停止已完成來源修正；CodeRabbit 148 檔初審 6 issues 查證修復，21 檔複審 0 issues；收尾七份 JUnit 去重 245 案通過，README／驗收紀錄已更新。main 提交與上傳已獲使用者授權，遠端結果待提交後確認。
- Reason：主人要求存 Git、餵兔子、GitHub main 一次收尾；以每小時 3 次／每次 150 檔上限執行，排除未修改大檔與非來源資料。
- Impact：不改既有任務生命週期；CH-T117 的先前正式完成證據保留，本新產品全面可販售任務草案尚未轉成正式 Epic。原生 Qt 崩潰根因未知、沒有新 EXE／Store／live 驗收，不能將來源同步等同正式發行。
- Evidence：reviews/2026-10-04-sale-readiness.md；output/main-sync-20261004/shipping-verification.json、review-scope.json、final-review-scope.json、excluded-large-evidence.json、coderabbit-148.ndjson、coderabbit-final.ndjson、product-experience-native-crash.log。


## 2026-10-04T04:49:33+08:00：GitHub main／CI 實際回執

- Timestamp：2026-10-04T04:49:33+08:00
- Change：來源提交 `f76f401c0bc76dd0b2626addd68ae87be3e8b312` 已推上 main，本機 git ls-remote 與 GitHub ref 均核對一致；[CI 37152671554](https://github.com/Gale0418/CloudHime/actions/runs/37152671554) completed／success，八必要工作全數成功、兩手動 frozen 工作 skipped。
- Reason：完成主人授權的存 Git、CodeRabbit 查證修復、main 上傳與任務中心補登；以實際 provider 回執確認，不把預期結果當已完成。
- Impact：文件回執提交使用 [skip ci]，來源 CI 對應上述程式碼 SHA，未宣稱文件 SHA 有新程式碼驗證。沒有新產品 EXE／正式 Store 發行；本機 Qt 原生 crash 的失敗紀錄保留，遠端成功不證明根因已修。
- Evidence：output/main-sync-20261004/github-receipt.json；審查原始 NDJSON、21 檔最終來源 manifest、七份 245-pass JUnit 均同目錄。任務狀態保持 canonical tasks.md，不將來源同步冒充新全面可販售 Epic 完成。
- Cleanup：本次兩個 projection 已封存為 review-148-snapshot.zip／review-final-snapshot.zip；遞迴刪除被自動批准審查拒絕，僅回 blocked by policy，因此臨時資料夾保留、不重試刪除。所有本次測試／CodeRabbit 執行已結束，未終止其他程序。

## 2026-10-04T06:59:01.5019898+08:00：Qt 原生崩潰追查與設定頁回呼修正

- Timestamp：2026-10-04T06:59:01.5019898+08:00
- Change：從 Windows Application1000 與本地 CDB minidump 核對歷史故障；相同 PySide 空指標簽章最早可查 9/21 21:14，當次 Python 專案未知；9/24 08:26 明確影響 Store0.1.0.0 EXE，10/4 03:19／04:36 的 Python3.10 仍同位置。舊 dump 證實 retrieveMetaObject+0x24 讀 NULL，但未含 self heap，最後失效 wrapper 未確認。
- Reason：主人追問何時發生、現在是否仍會，以及未重建 EXE 的含義；不將來源／CI 通過冒充產品 EXE 根治。
- Impact：獨立 red 重現設定頁 contextless QTimer.singleShot 在元件刪除後仍讀 QLabel；改成元件持有的單次 timer／QObject slot，green 與207案UI回歸通過。原生 Controller／設定關閉刪除GC壓力修正前第5～6輪AV，修正後CDB20輪／一般程序40輪通過。歷史NULL簽章與本次原生壓力故障尚未併因；任務生命週期不變，沒有重建EXE／替換Store，原產物不含此修正。
- Review：CodeRabbit 基準分支前置失敗未送審，明確 --base main 後審查2檔／0 issues；本時段2個CLI指令、1次實際審查，未用credits。排除未修改大檔、models、assets、dumps、settings與憑證。
- Evidence：reviews/2026-10-04-qt-native-diagnosis.md；output/qt-crash-20261004/windows-native-events.json、historical-043627-native.txt、lifetime-retain-object.txt、disclosure-red.xml、disclosure-green.xml、provider-fix-validation.xml、lifetime-after-timer.xml、lifetime-fixed-normal.xml、coderabbit-base-main.ndjson、review-scope.json。main／最後去除診斷參照的對照結果於後續回執補登。


## 2026-10-04T07:17:01+08:00：Qt CI 原生失敗反證與快捷鍵關閉回歸

- Timestamp：2026-10-04T07:17:01+08:00
- Change：來源 0373861710194bf63cd6918774978854f5c2274b 已上 main，但 GitHub CI37160325279 於 07:02:03 在設定外觀第12案建立 QThread 時發生 native AV；7必要工作成功、UI失敗、2手動frozen跳過，不能宣稱根治。本機相同單檔CDB冷啟15案通過，新GC前置診斷15案通過，仍未捕獲原始NULL的full heap證據。
- Reason：主人問「什麼時候、現在還會嗎、原因」；9/24 08:26 Store EXE已證實同RVA1ba6c，今日遠端仍崩，必須保存反證。
- Impact：另以red確認關閉後500ms快捷鍵回呼仍重新註冊；改由Controller持有單次timer、關閉停止、Slot和shutdown guard。214案相關UI／關閉回歸通過；此修正不是已確認的NULL根因。歷史根因未完成，不變更任務生命周期，不重建或替換EXE／Store。
- Review：快捷鍵2檔CodeRabbit0 issues，SHA256匹配；本時段累計3個CLI審查指令／2次實際審查，排除無關大檔、資產、模型、dump、設定與憑證。沒有超過使用者限制。
- Evidence：reviews/2026-10-04-qt-native-diagnosis.md；https://github.com/Gale0418/CloudHime/actions/runs/37160325279；output/qt-crash-20261004/hotkey-close-red.xml、hotkey-validation.xml、settings-cold-native.xml、settings-before-worker-gc.xml、coderabbit-hotkey.ndjson、hotkey-review-scope.json。來源上傳後續回執核對，不將本機214pass當完整CI成功。


## 2026-10-04T07:24:17+08:00：Qt 設定窗殘留修正與最新來源驗證

- Timestamp：2026-10-04T07:24:17+08:00
- Change：快捷鍵修正685fd91的CI37161334665八必要工作成功、兩手動frozen跳過；保留0373861於07:02原生AV反證。進一步觀察發現6個hidden設定窗跨案仍有效、Controller已invalid，GC後仍在；獨立clean red確認Controller刪除後設定窗未刪。
- Impact：SettingsWindowRevamp由Controller持有QObject parent，保留Qt.Tool與close/hide/reopen；新215案UI回歸通過，CDB相同單檔15案通過且每案設定窗殘留0。歷史NULL首次失效物件仍未知，未宣稱上述三個已修缺陷就是共同原生根因；沒有新EXE、Store替換或任務Done轉移。
- Review：ownership2檔CodeRabbit0issues，最終SHA256匹配。此小時3次實際審查各2檔，另1個CLI指令因git base前置失敗沒有送審，未超過3次／150檔，沒有第四次實際送審。
- Evidence：reviews/2026-10-04-qt-native-diagnosis.md；output/qt-crash-20261004/settings-survivor-observation-survivors.jsonl、settings-owner-red-clean.xml、settings-owner-green.xml、settings-owned-observation-survivors.jsonl、coderabbit-ownership.ndjson、ownership-review-scope.json、hotkey-ci-receipt.json。


## 2026-10-04T07:28:20+08:00：Qt 調查 checkpoint／main 與 CI 回執

- Timestamp：2026-10-04T07:28:20+08:00
- Completed：三個直接red/green確認的生命週期缺陷已修並推上main來源eb5ee34eb67bb40c0e5d5dc0d39e951b5d2b7c2d，遠端ref相同；CodeRabbit最後2檔0issues且bytes匹配。本時段3次實際審查，另1次base前置失敗沒有送審，遵守每小時3次／150檔。
- Smoke tests：215個相關UI案例通過；最終CDB20輪Controller／設定／native joins／刪除／GC完整1pass；CI37161687605 completed/success，八必要工作成功、兩手動frozen跳過。設定窗跨案殘留6→0。
- Unfinished／Risks：原始retrieveMetaObject NULL的最初失效wrapper仍未知，07:02較早來源的原生AV反證保留，後續來源通過不等於完整根因確定。未重建EXE／替換Store，既有產物不含新修正；不把原生事故或全面可販售任務標Done。
- Retro：下次原始NULL故障需要含self heap的任務隔離full dump，才能確認type／BindingManager；避免將一般Qt斷言修正、單次CI綠燈或不同native stack混為同根因。
- Evidence：https://github.com/Gale0418/CloudHime/actions/runs/37161687605；reviews/2026-10-04-qt-native-diagnosis.md；output/qt-crash-20261004/final-github-receipt.json、ownership-verification.json、lifetime-final-ownership.xml與cycles.jsonl。回執文件提交採[skip ci]；CI針對來源eb5ee34。
- Cleanup：本次測試／CDB／CodeRabbit子程序均結束，未清除其他MCP程序。dump只保存在本機ignored目錄，未加入Git、未送CodeRabbit；使用者原有untracked assets/cloudhime_logo_v2.png保持原狀。

## 2026-10-04T14:33:24.8210095+08:00：Qt 錯誤分支因果確認與未完成事故 checkpoint

- Timestamp：2026-10-04T14:33:24.8210095+08:00
- Change：舊來源34b4141於08:21第2輪捕獲設定頁已刪除QLabel例外；Shiboken Sbk_GetPyOverride錯誤分支對borrowed nativeEventFilter function減引用至0，class dict仍持有同一指標。原生指令、完整heap、Python traceback與官方6.10.1來源一致，確認此event filter故障鏈；此前parent-owned timer修正移除本程式已知觸發。
- Verification：目前來源08:26相同hardware watch完成20輪／1passed，sessionfinish exitstatus0；function直到Py_FinalizeEx才由PyDict_Clear釋放。不是整個debugger程序正常退出的宣稱。舊設定頁重複四輪共60次／15不同案例、72個ctor/meta配對均一致，但程序收尾總時限120秒timeout；另一全量trace180秒timeout沒有JUnit，兩次都不算完整probe通過。
- Impact：原始9/24及10/4 retrieveMetaObject NULL dump顯示註冊wrapper與傳入wrapper不同，但缺舊self heap／live map，producer仍未知，不能與上述已確認故障合併。未改產品程式、未patch依賴、未重建EXE／替換Store、不轉Done；本輪僅診斷與文件，CodeRabbit實際送審次數維持先前三次，沒有上傳dump或設定。
- Next：若原始NULL再發生，需捕獲精確C++ key的map entries／wrapper type與release順序；已有mismatch條件斷點及健康檢查。停止無新假說的重跑。先讀reviews/2026-10-04-qt-native-diagnosis.md後半部，對照ignored output/qt-crash-20261004/的本地證據。
- Cleanup：本次narrow及full trace已停止，Windows程序查詢無相同probe標籤的Python／CDB殘留。既有untracked assets/cloudhime_logo_v2.png未修改。聊天平台的顯示限制提示非程式故障證據，觸發原因未知；不改寫完成狀態。


## 2026-10-04T15:26:27+08:00：新版 Store 發行／成品與評論額度 checkpoint

- Timestamp：2026-10-04T15:26:27+08:00
- Change：主人將目前工作切至新版上架。從014e0e7隔離快照重建EXE，本機light/full、frozen import、Windows OCR兩行、CPU Vision1/1、GUI20秒通過；35檔CodeRabbit一次0issues。Submission3草稿已建立，沿用0.1.1.0現行私人群組／免費，0.1.2.0封裝與全新斷網CPU Sandbox進行中。
- Reason：舊產物不含本次Qt生命週期修正，不能用舊WACK／Sandbox抵替新版證據。授權文件換行及OCR無字fixture的兩次驗證失敗已保留並修正測試材料，不改產品行為。
- Impact：CH-T55維持Review、T56未Closeout；EXE SHA19df640299d1c6502b5e2ee93ed0833571cdf3c63838bb67fb113ef6629ccdba。正常GUI全流程因Windows capture timeout／geometry缺失未完成；測試GUI PID52820精確清理，未動原Store及主人設定。
- Approval：主人明確採用本輪評論總24,000 tokens、四席各4,000、整合8,000、每席工具8／總32、30分鐘，含必要修正複核；成品與證據固定後才派送三Luna與獨立arbiter。
- Next：收齊完整包／Sandbox、補Store package安裝更新與WACK、封存快照並正式評論；通過再上傳與送認證，取得實際Store更新回執。詳見reviews/2026-10-04-store-release.md；output/store-release-20261004/。

## 2026-10-04T16:08:19+08:00：CH-T55 新版乾淨環境失敗／改用語言能力診斷

- Timestamp：2026-10-04T16:08:19+08:00
- Change：014e0e7完整Store封裝通過但候選撤換，因本輪Sandbox Windows OCR exit2；import已通過，Vision／GUI未到達。2GiB原生診斷顯示只有en-US engine可建立、profile engine為null；OS capability inventory失敗單獨保留。
- Reason：程式缺已安裝語言後援，且將engine初始化失敗轉成一般空文字。fake fail-first三案例已重現；最小修正、錯誤聚合與三語提示驗證進行中，未聲稱新來源已通過。
- Impact：CH-T55維持Review、當前Smoke NO／Critic NO；待修正來源新EXE、MSIX、focused CodeRabbit與新Sandbox。已封裝候選不會上傳；Submission3更新說明同步，仍未認證／发布。
- Cleanup：本輪兩個Sandbox owned client／launcher均remaining0；未移除使用者Store安裝、其他VM或原logo。
- Evidence：reviews/2026-10-04-store-release.md；output/store-release-20261004/sandbox/output/result.json、sandbox-ocr-diagnosis/output/ocr-diagnosis.json、兩輪cleanup.json、package-result.json。評論額度已授權但尚未派送／起算。

## 2026-10-04T16:19:36+08:00：CH-T55 OCR 修正／17案來源驗證

- Timestamp：2026-10-04T16:19:36+08:00
- Change：背景Windows OCR依日文、profile、已安裝語言選引擎；全部初始化失敗有三語Windows語言提示，generic OCR失敗不假稱未安裝，正常空結果與文字fallback保留。失敗初始化不永久快取，可在語言支援恢復後再試。
- Verification：Luna15pass轉錄receipt；主代理delta先2failed，最終17pass actual JUnit／log。第一次write guard因換行假設拒絕寫入、當時green仍2failed，保留反證。diff --check通過；不重跑未受影響215UI、不宣稱frozen／Sandbox通過。
- Next：直接main固定來源，5檔focused CodeRabbit與fresh EXE，驗證OS語言後援後完成Store full package／install-update／WACK及正式評論。模型以同磁碟hardlink避免重複大拷貝，仍full hash verify。CH-T55 Review／Smoke NO／Critic NO。
- Evidence：output/store-release-20261004/ocr-source-verification-receipt.json、ocr-main-red.xml、ocr-main-green.xml（失敗）、ocr-main-green-final.xml與各.log／receipt；reviews/2026-10-04-store-release.md。

## 2026-10-04T16:45:54+08:00：CH-T55 新候選本機反證與 GUI 實測進度

新來源 `2ee51b9999e5462b9f2acdaca650ae0699855d7f` 已推送 main；GitHub push CI `37189052512` 為 success：8 個必要工作成功，2 個手動 frozen 工作 skipped，不能計為實際 frozen pass。5 個 OCR 程式／測試檔 focused CodeRabbit 16:23:05至16:24:25完成，0 findings；scope SHA 與不可變來源完全相符，回執 `review-binding.json`。

新 EXE SHA-256 `cdd66015fbe7f568e6af7cbf446eaece2dec6e633af82c6a989432d694f9c099`，16:29:57重建完成。light/full verifier、40-component provenance、固定模型 hash、frozen import、Windows OCR兩行與獨立20秒GUI存活通過。CPU Vision exit2，故整體 `verification-result.json` 為 failed／stage cpu-vision；固定模型與runtime相同不足以證明只是資源問題。目前 generic smoke 輸出吞掉根因、原harness清除隔離profile；已準備 source diagnostic 保存redacted bounded stderr／階段耗時，不能把來源diagnostic替代frozen驗收。未在GUI模型操作同時跑VM或另一模型。

一般GUI仍由主人操作驗證。16:42:53截圖顯示已框選測試圖、當前Google Translate，UI顯示rate limited；不能據此證明實際Google帳號配額用完或翻譯成功。已引導切換Local Gemma、開啟本機多模態與CPU-only。第一次隔離GUI PID51480正常退出code0；主人要求重開後，同一獨立profile PID1436再啟動，完整設定／翻譯／暫停旅程待回覆，不宣稱通過。

Submission3 四語更新說明已按Save並返回overview；zh-tw與en-us重新開頁確認持久化，ja-jp與zh-hant-tw仍待重讀。沒有上傳新package、送認證或發布；私人／免費設定保留。正式評論尚未派送／起算，使用主人核准24k tokens、各席4k、整合8k、各席8工具／合計32、30分鐘。CH-T55 Review／Smoke NO／Critic NO；CH-T56不Closeout。

證據：`output/store-release-20261004-ocr-fixed/` 的 build-result、ci-result、review-binding、verification-result、windows-ocr、cpu-vision、gui-liveness、manual-gui-result、manual-gui-reopen-result、vision-triage；主人截圖 `D:/Downloads/2026-10-04 16 42 53.png`。新MSIX尚未封裝／驗證，不使用前一撤換候選。

## 2026-10-04T17:03:17+08:00：主人實測發現目標語言缺陷，候選再次撤換

主人16:48:36截圖：英文UI、Local Gemma model ready；英文句被譯為中文、日文保留原文。isolated profile為ui_language=en／use_gemma_translation=true／provider_chain local_multimodal／local_multimodal_enabled=false，實際走本機純文字模式。正常關閉pid1436 exit0，沒有完成自動掃描暫停／繼續完整旅程。主代理起初口頭說UI與目標語言分開，與source不符，已向主人更正；localization契約en→en、ja→ja、zh-TW→zh-TW。

已查證兩個單句provider呼叫漏傳worker.translation_target_lang；provider方法預設zh-TW覆蓋registry已設en。Google與Gemma兩處明傳target_lang；新增en／ja兩provider四例RED全失敗，GREEN及目標快取隔離5案通過。主代理整份worker matrix141案通過（actual JUnit／log／SHA）。UI rate indicator將本機純文字模式誤標Google也已RED重現；修正顯示Local Gemma3並保留loading／ready／failed既有進度。4案focused與完整UI smoke67案通過。共208個不同worker／UI案例通過；不表示fresh EXE／Sandbox／Store gate通過。

原2ee51b9 EXE因上述GUI缺陷撤換，不上傳。日文特定句為何保留仍須新EXE實測，不以舊Google TooManyRequests warning直接歸因該張圖。本機Vision源碼診斷（相同固定runtime／模型、不是frozen驗收）在90秒health deadline失敗，redacted stderr停在模型載入；原production上限240秒，因此獨立240秒診斷正在執行，保留90秒反證，不宣稱根因已完全確定。

四份Store更新說明（zh-tw88、en-us4、ja-jp17、zh-hant-tw480）均重新開頁確認持久化；仍只是Submission3草稿，未上傳／認證／發布。package sandbox helper及source-derived hardlink staging wrapper已準備但未運行安裝閘門；只在guest副本做自簽、update與WACK，不動原Store。新產物將另存output/store-release-20261004-target-fixed/，固定新source、4檔CodeRabbit、重新建EXE及受影響gates。

CH-T55保持Review／Smoke NO／Critic NO。正式24k／32工具／30分鐘評論尚未派送／起算。證據：target-routing-red／green.junit.xml、target-routing-fix-receipt、worker-regression.xml／log／receipt、local-indicator-red／green及receipt、manual-gui-reopen-result、vision-diagnostic/result、vision-diagnostic-240/，均在output/store-release-20261004-ocr-fixed/；主人截圖D:/Downloads/2026-10-04 16 48 36.png。

## 2026-10-04T17:15:32+08:00：CodeRabbit minor 修正、測試替身與真實 CPU 壓力條件

來源b10d3e5的4檔CodeRabbit17:05:52至17:07:01完成，提出1個minor：本機Vision未ready時indicator錯讀local_model_state覆蓋starting/progress。讀source與RED兩案確認有效，已共用local runtime state選擇，與engine summary一致；focused6案及full UI smoke69案通過。先前4檔0-finding binding assertion拒絕這1-finding結果，沒有生成passed binding，不把提出問題的審查說成0問題。修正需新來源，原b10 EXE收集階段已終止owned PyInstaller27496／parent25568正常保存非零build-result；build-cancelled.json記原因，產物不宣稱建置成功。

GitHub b10 push CI37190933923為failure（7 required成功／OCR組失敗／2manual skipped）：tests/test_cloudhime_workers.py兩個__new__替身未建立translation_target_lang，fake translate也漏keyword。只補兩替身初始化與keyword契約並驗明收到en，保留原模型／provider attribution驗證；產品初始化已具target_lang，沒有修改正常流程迎合stub。完整CI OCR九檔295案通過，JUnit／原始log／workerSHA保存；加最新UI69，共364不同案例。這次main commit仍須新CI確認。

主人指出其他使用者會同時玩遊戲，明確要求以當前忙碌CPU當壓力條件。17:12左右aggregate CPU讀值100%，freeRAM約8.97GiB；只有單次取樣，不能歸因某程序或代表整段負載。將在fresh frozen功能驗證期間採集aggregate CPU與freeRAM；不額外飽和CPU，不停止其他工作。240秒source診斷成功：startup158.761秒、request14.528秒、CPU image1/1。這支持90秒閘門太短；尚非新EXE／乾淨Sandbox驗收。下一次建置採BelowNormal優先權，產品測試保留正常priority／原production240秒啟動契約，重型gate排隊。

Mission Center0.5.2本地未包附critic_contract.py；從插件作者官方repo取得相同immutable094c367556b56de1b6e9541ac782552978df4c8c的純JSON唯讀validator（預設分支與該commit內容相同、import僅stdlib、無network/subprocess/write），存ignored critic_contract.upstream.py。這是advisory record驗證補件，非Rust生命週期fallback／插件安裝，尚未宣稱正式critic contract通過。

新候選將存output/store-release-20261004-final/；尚未上傳、認證或發布。CH-T55 Review／Smoke NO／Critic NO；正式24k／32tools／30min尚未開始。Evidence：output/store-release-20261004-target-fixed/coderabbit-review.ndjson、local-indicator-delta*.xml／stdout／receipt、ocr-group-fixture-regression.xml／log／receipt、ci-ocr-failed-excerpt.log、build-cancelled.json；source diagnostic在ocr-fixed/vision-diagnostic-240/result.json。


## 2026-10-04T17:31:40+08:00：停止狀態複審修正與候選撤換

2b3a60f main push CI37191591138 success，八個required job成功，兩個manual frozen job skipped；ci-result.json保存清單，不將skip當成EXE驗收。17:24:32至17:25:30的3檔CodeRabbit複審完成，提出1個minor：Vision stopped狀態會被indicator timer覆蓋為Local Gemma3。source on_local_vision_status與RED回歸確認有效；只在多模態模式保留stopped，純文字模式原有label行為保留。完整UI smoke70案通過，與既有OCR295合計365個不同案例；RED/原始log/JUnit/receipt在output/store-release-20261004-final-ui-delta/。首次測試使用base Python沒有pytest，該入口錯誤不算RED；改用既有isolated test-venv取得實際failure。

2b低優先build在COLLECT階段因修正需要新固定來源而精確停止owned PyInstaller15192，build-result exit4294967295與build-cancelled.json保存；partial EXE不得當新候選使用。下一個完整候選另存output/store-release-20261004-release-ready/，先完成本次focused修正複審再建置，避免同時替換正在建置的source。Rabbit quota保持一小時最多3次/一次150檔案。

CPU取樣在17:27附近42至72%，freeRAM約7.1GiB；先前100%只是單次值，負載仍波動，會在實際frozen/mannual翻譯期間保存aggregate CPU/freeRAM的bounded取樣。沒有製造額外負載或停止其他工作。所有旧候選均未上傳；Store Submission3仍草稿/private/free。CH-T55 Review／Smoke NO／Critic NO；正式評論24k/32工具/30分鐘尚未開始。


## 2026-10-04T17:39:22+08:00：停止狀態初始化邊界修正

bc6fb87 main push CI37192500697 success。2檔CodeRabbit複審17:34:10至17:35:01完成，提出1 minor：多模態尚未收到status callback且stopped時，保留分支可能沿用Google舊label。新參數化回歸RED為1 failed/1 passed，失敗label確實Google；改為主動依目前語言顯示Vision stopped，與on_local_vision_status共用label，不修改上方一般status message。純文字stopped仍Local Gemma3。allowlist／隔離profile／offscreen完整UI71案GREEN，worker/OCR295 unchanged，合計366不同案例；stopped-initial-red/green.xml與log、fix-receipt皆在output/store-release-20261004-release-ready/。

該來源未啟動EXE build，沒有冒稱兔子0問題或成功release；新immutable候選改存output/store-release-20261004-release-ready-v2/。一小時三次Rabbit额度現已用完，下一次不早於18:05:52+08:00；會先做本機建置與驗收、約18:06後才能補審。Store更新仍未上傳／認證／發布，正式critic budget尚未啟動，CH-T55維持Review／Smoke NO／Critic NO。


## 2026-10-04T18:11:31+08:00：新 EXE 忙碌 CPU 與主人翻譯驗收

固定來源 0931ca0、EXE SHA 5e1aba948f48f69f531ac4e416f09168f521a23f5c3a12d6171d63cec5f1699f。BelowNormal 建置於 17:39:33 至 17:46:05 完成，exit 0；light 369 檔、full 375 檔、40 個元件來源核對、frozen import、Windows OCR 兩行、CPU Vision 單張圖片／單次請求皆通過。CPU 推論階段五次整體取樣皆為 100%，取樣窗口 17:49:24 至 17:50:20；這不是精確載入／請求耗時，也不是遊戲 FPS 或辨識準確度證據，限制保存於 stress-load-summary.json。

取樣器 Get-Content 的讀取鎖撞到 verifier 最後的 Set-Content，導致原執行 exit 1。原 verification.log、orchestration 與 verification-before-observer-race.json 均保留。僅將 ignored 取樣器改為 FileShare ReadWrite/Delete；同一 EXE 補跑 GUI 20 秒成功，PID 19788，所屬殘留程序為零，verification completionRecovery 明確記錄恢復流程。第一次恢復誤把 ModelFiles 當六個，實際為兩個 GGUF 與四份授權文件，防護檢查在 GUI 啟動前拒絕；原日誌保留，校正後才成功。不重跑已通過的模型請求，也不隱瞞失敗。

CodeRabbit 於 18:07:05 至 18:07:51 複審兩檔，0 issues，審查檔案 SHA 與固定來源一致。配額依完成時間保守計算，一小時內原兩次加本次一次，未超過三次。CI 37192858615 八項必要檢查成功，兩項手動 frozen 檢查 skipped。主人明示「成功翻譯而且都是英文~」；18:05:16 截圖確認 Local Gemma Model ready／Local Gemma3 狀態列沒有 Google 誤標。human-target-acceptance.json 保存來源、截圖 SHA、已確認與未確認項目。截圖未顯示字幕內容，英文目標語言的證據來自主人的文字回覆。

主人要求將會換成兩行的地方改為跑馬燈。目前針對主視窗引擎摘要、資料處理提示、翻譯狀態與框選提示，規劃單行、溢出才滾動、短文靜止、滑鼠移入暫停與完整提示／無障礙文字。設定頁長說明與字幕不擴大改動。0931 候選仍可使用；最終發行須依新來源重建。原 wait_manual_sandbox 觀察程序 PID 16172 已精確停止，避免舊候選自動執行 VM；主人的 manual app PID 46592 未停止。

Store 四份版本說明已加入翻譯目標、Local Gemma 狀態與 Windows OCR 修正，儲存後返回 overview；英文、日文、中文台灣重開確認持久化，繁體中文台灣待重讀。尚未上傳新 MSIX、送認證或發布。CH-T55 維持 Review／Smoke NO／Critic NO；24k tokens、32 次工具、30 分鐘正式評論尚未派送起算。


## 2026-10-04T18:25:43+08:00：主視窗單行跑馬燈來源驗證

主人要求長提示跑馬燈化；新增 MarqueeLabel，套用引擎摘要、資料處理提示、翻譯狀態與框選提示四處。超出才啟動 parent-owned QTimer，隱藏時停止、顯示時恢復，QObject slot 避免 contextless 回呼；短文靜止、滑鼠移入暫停，完整 tooltip／statusTip／accessibleName 隨文字更新。設定頁長段落與翻譯字幕不變。驗收補修同文字刷新保留位移，以及字型／樣式改變時重新計算；五個元件案例加既有兩組 UI 共 156 案、29.51 秒通過。首輪 155 與失敗診斷日誌保留，最新證據為 output/store-release-20261004-marquee/pytest-ui-final.xml、final-ui-binding.json，非整個測試 inventory。

README、任務下一步與本紀錄已更新；新來源尚待固定 main 提交、重建 EXE、配額內三檔 CodeRabbit、實機與乾淨環境／MSIX／WACK／正式評論。0931 的 frozen 與兔子 0 issues 不冒充本次來源通過。Store 四語版本說明均重讀確認持久化；尚未上傳新套件或送認證。CH-T55 Review／Smoke NO／Critic NO；正式評論預算未開始。


## 2026-10-04T19:02:53+08:00：混合語言漏翻與本機等待訊息修正

主人 18:32:22 截圖顯示上行已翻英文，下行「研究 Gemini 橋接方案升級」仍中文；等待時顯示 Google 的證據來自主人的文字回報，該截圖本身是完成／快取狀態。已從隔離 profile 的舊快取重建完整 context，來源正是該中文句、目標 en、provider local_multimodal，計算 key 與錯誤快取完全一致（parent-cache-context.json）。先前主人確認的英文翻譯只代表單句局部成功，不能當成所有內容驗收。

原品質檢查因句中有 Gemini 英文字而漏掉保留中文的結果。現在英文品質檢查會識別原文連續四字以上中文片段，保留短人名與原本英文；這是有範圍的品質防護，非翻譯準確度保證。LocalMultimodalProvider 不使用不合格記憶體快取，首次不合格會以同一本機模型重試一次，仍失敗則不快取；持久快取讀取、新結果寫入與批次逐行皆檢查，半套翻譯會改走逐項處理。Google 批次補上明確目標語言。文字掃描的初始、批次與逐項等待狀態改依實際引擎，本機 Gemma 三語提示與相同畫面快取提示已本地化。

品質 guard RED 3 案、持久快取／批次 RED 4 案與英文快取提示 RED 1 案均保留。首次整合 568 案為 565 passed／3 failed，確認是兩個 __new__ 替身缺少目標語言與一個英文測試卻回傳中文的 mock；補正測試輸入，未放寬產品品質檢查。第二輪同 profile 卡在產品體驗第 68 案附近，超過八分鐘無進展；保存 integrated-hung.log／receipt，精確停止本輪三個 owned PID，未生成 passing receipt。無 stack，Qt 卡住根因仍未確認。改用全新唯一 profile、verbose／60 秒 faulthandler 與 150 秒硬逾時，15 檔整合 568 passed in 32.14s，零 failure/error/skip，來源 SHA 前後一致；JUnit SHA 026e9f985df23e6499e048dd3837a6154876857708643ea1b7c8da0f5e55f9ef。證據在 output/store-release-20261004-second-line/。

14ae2df 跑馬燈 EXE 雖完成建置、三檔 CodeRabbit 0 issues，但已因上述新反證撤換；舊觀察程序已停止，未送沙箱／封裝／上傳。6e1a14f 只補 CI inventory，CI 37195667976 success；這不是最新修正的 CI 證據。接著固定 main 新來源、配額內聚焦審查、重建 EXE 與驗收。原 0931 隔離視窗於 18:32:46 正常 exit 0，只證明正常退出，不代表暫停／繼續／取消框選皆完成。Store 仍私人免費 Submission 3 草稿，尚未上傳新套件／認證／發布，現行版 0.1.1.0；CH-T55 Review／Smoke NO／Critic NO，正式評論預算未開始。


## 2026-10-04T19:09:32+08:00：11 檔兔子補審與本地化差異修正

36e7838 已推 main；固定來源與 568 案測試逐檔 SHA／EOL binding 保存於 output/store-release-20261004-translation-ready/。CodeRabbit 11 檔、994036 bytes，排除模型／runtime／設定／憑證，配額依所有歷史 receipt 的完成時間保守計算；完整審查提出 2 minor issues，並非 0 issues。查證為 Controller 快取提示只辨認繁中 catalog，以及遠端／Google 批次等待仍寫死中文。新增三語輸入與雙引擎三語狀態回歸，RED 6 failed／3 passed；修正後 9 passed，JUnit、原始 log、receipt 在 second-line/review-delta-red 與 review-delta-green。保留原文字 trimming／狀態流程；沒有擴大到其他 UI。

36e7838 的 BelowNormal PyInstaller 在 19:06:16 精確停止 owned PID 15960，parent 正常保存 exit 4294967295 與 build-cancelled.json；不使用部分產物、不執行舊 verifier。下一候選須以修正後新來源重建與複審。先前卡住的 Qt 混跑根因未定；最新全新 profile／verbose／faulthandler／硬逾時整合 576 passed，零 failure/error/skip、來源 SHA 前後一致，JUnit SHA c1bce6381ff9501ae0f90e428ec19aa24521602be6c42856f980065ec80103d8。Store 未上傳／認證／發布，CH-T55 仍 Review、Smoke NO、Critic NO，正式評論額度尚未起算。


## 2026-10-04：translation-final 驗證更新

來源 `main` `466780b`；整合結果為 576 passed、31.23 秒，收據 `second-line/integrated-receipt.json`。原始產物：

- `output/store-release-20261004-translation-final/verification-result.json`
- `output/store-release-20261004-translation-final/ci-result.json`
- `output/store-release-20261004-translation-final/coderabbit-receipt.json`
- `output/store-release-20261004-translation-final/source-text-probe.json`

CI 最新為 8 required success、2 manual skipped。CodeRabbit 的 2 minor 已修正；來源 `466780b` 的 4 檔複審為 0 issues，僅涵蓋該次範圍，不能推論整個儲存庫沒有問題。新 EXE `1015aa86…fda1863` 的 host frozen OCR 兩行、CPU vision 1/1、GUI 20 秒驗證通過；公開測試句的 Gemma 單句和 batch 第 2 行實際回傳英文，且未用 Google。此結果僅驗證固定來源的模型文字呼叫，尚未完成整段 GUI 操作驗收；使用者 暫停／繼續／重新框選取消 全流程驗收待完成。

全新 sandbox OCR 失敗。identity MSIX 已獲證明，但仍回 `E_FAIL`。native-first guest stream 的 BGRA8 decode 成功，`RecognizeAsync` 失敗，C Windows OCR 為空；缺少 payload 仍是候選，控制實驗未完成，根因未定，也不能宣稱全面修復。raw failure 保留。

Store 仍為 0.1.1.0；0.1.2.0 套件封裝 進行中，尚未上傳或認證。正式評論 尚未派送，核准額度未變。

### 20:01 OCR 語言資源控制實驗

原始 `sandbox/`、`ocr-identity/` 及 `ocr-native-first/` 的失敗保留。native-first 使用首次成功建立的同一 engine，Store／Flush／解碼均成功（1000×300、BGRA8），到 RecognizeAsync 才失敗，排除探針先丟棄 engine 的疑點。取得 MSIX 身分也未改善。

`ocr-payload-control/` 首次寫入沙箱 Windows OCR 目錄遭拒，該失敗未覆蓋。`ocr-payload-control-v2/sandbox/output/result.json` 在僅限 WDAGUtilityAccount 的拋棄式沙箱補入主機既有 ja／zh OCR 資源後，原生辨識 2 行、同來源 frozen 程式初次與再次辨識均 2 行且 error 為空；owned 程序清理為 0。這確認沙箱語言資源缺失或不可用會造成本次失敗，並非只靠套件身分可修復。沒有變更產品 OCR 來源；未將 Windows 資源打包、上傳或當成正式 Windows capability 安裝。

後續 `sandbox-ocr-prerequisite/` 明示「新沙箱＋診斷用 OCR 前置資源」，不替代原始未修改沙箱的失敗紀錄。啟動時因可用 RAM 未達 6 GiB 被 guard 拒絕；沒有啟動 VM，也沒有清理無關程式。待封裝與記憶體允許後繼續完整 EXE OCR／CPU／GUI，以及 MSIX 安裝／更新／WACK。CH-T55 保持 Review，Smoke NO、Critic NO；原 Store 0.1.1.0 保留。


### 2026-10-04 本機模型準備與 Google 誤路由修正

20:13 實機截圖顯示候選 EXE 停在 Preparing model、charge bar 誤寫 Google、框選中文未翻譯；這次驗收失敗，466780b 的候選 MSIX／upload 已退回且未上傳。封裝診斷確認兩個內附 GGUF 與 runtime 都存在，未選到受管下載路徑。完整來源 Controller 診斷顯示背景在首次 SHA 驗證讀模型；併行封裝 I/O 下未於時限內就緒，這僅解釋診斷中的等待，尚未證明實機失敗的全部根因。

修正明列 local-only provider chain 時的隱性 Google fallback 與舊 Google 快取偷渡；設定頁改讀實際 local_multimodal provider。內附模型驗證增加實際位元組進度及區塊間取消，仍核對 SHA，只有成功驗證才寫 receipt。文字模式保留驗證階段，CPU 文案不再宣稱初始化 GPU；未就緒時按翻譯保留字幕並提示等待，明列 Google 的 fallback 保持可用。

相關回歸 313 passed；CodeRabbit 僅審本輪 9 個程式／測試檔、0 issues，未包含模型、DLL、大型輸出或使用者另留的 logo。證據：output/store-release-20261004-local-warmup/checkpoint-evidence.json、regression.xml、coderabbit-scope.json 與 coderabbit-review.ndjson。新 EXE 完整啟動／翻譯、GUI 操作、沙箱／MSIX／WACK與正式評論仍待完成；Store 仍為 0.1.1.0，CH-T55 保持 Review。


### 2026-10-04T21:21+08:00：本機準備修正版 EXE 與實際 Controller 驗證

固定來源 adf8d39 新 EXE 已重建，SHA 931d24c73099cead2fa016523afc6efb71365cbd0614a5975a2bad88496af846。模型完整性、frozen import、host Windows OCR 兩行、CPU vision 1/1 與正常 GUI 20 秒啟動均通過；GitHub CI 37203714789 八個必要工作成功、兩個手動 frozen 工作跳過。本輪回歸 313 passed、CodeRabbit 九檔零 issues；這些不是全專案或完整 GUI 操作驗收。

另用相同固定來源的實際 Controller、正常設定載入與該 EXE 的內附模型／runtime 做來源診斷：SHA 驗證進度 0→30→55%、模型載入、就緒，約 17.156 秒；「確認連線狀態」以 local_multimodal 翻成 Check Connection Status，未取快取，翻譯等待期間有 70 次 UI event tick。此診斷不是 frozen EXE 的完整人工旅程；offscreen 原生快捷鍵排除，不能推論暫停／繼續／取消框選全部通過。Controller cleanup 完成，自有 llama-server 已終止；其 wrapper exit 1，沒有冒稱正常 exit 0。證據：output/store-release-20261004-local-warmup/verification-result.json、controller-startup/result.json、verified-checkpoint.json。

主人指定文案由 Gemini 撰寫，已透過 Antigravity Bridge 送出；同一 cascade 卡在 filesystem/describe 實際工具授權，已排入不使用工具的純文字後續要求，尚未取得文案，未以 Codex 代寫冒充。20:13 失敗候選維持退回。最新 MSIX／完整人工操作／沙箱前置環境／更新安裝／WACK／正式評論仍待完成，Store 0.1.1.0 保留，CH-T55 Review、Smoke NO、Critic NO；24k 正式評論尚未起算，尚未上傳或認證。


### 2026-10-05 Gemini 全介面文案

三語 624 目錄文字與 497 內嵌候選已審閱，337 目錄文字修改；OCR／快速鍵三語接線完成，未知診斷保留。最終相關回歸 428 passed；CodeRabbit 18 檔兩項 Minor 已修、兩檔複審零 issues。工具授權舊卡點已解除。CH-T55 保持 Review；含文案新 EXE／完整 GUI／MSIX／WACK／正式評論／Store 待驗收，未上傳。見 reviews/2026-10-05-gemini-ui-copy.md。

### 2026-10-05 含文案候選封裝與草稿

來源 fe88bab 的 EXE cbbcf0b8…694e842 通過 host import／Windows OCR 兩行／CPU vision 1/1／GUI 20 秒／full provenance；自然 CPU 負載最高 90%，不是完整操作壓力驗收。main fb36dca CI 37220416100 八 required success、兩 manual skipped，shipping 218 inputs 與 build source byte-identical。0.1.2.0 MSIX／upload 已完成並核對 SHA、stage 清理；第一次 MakeAppx OOM 已保留，SDK /np 序列封裝成功。Gemini 四份商店更新說明已存草稿並重新讀取核對；未上傳套件或認證。九張 source offscreen 三語版面圖完成，僅 presentation fixture，不冒充 native GUI。最新完整人工操作、隔離更新／WACK及已核准正式評論仍待完成；CH-T55 Review／Smoke NO／Critic NO，正式 Store 0.1.1.0 保留。詳見 reviews/2026-10-05-gemini-ui-copy.md。


### 2026-10-05 沙箱套件通過與 WACK 工具崩潰

來源 fe88bab 的相同 0.1.2.0 MSIX 在斷網 Windows Sandbox 完成 0.1.1.0→0.1.2.0 更新，PFN 不變且合成 LocalState 保留；全新安裝／AUMID 20 秒啟動／移除通過。這不是實際使用者設定或翻譯功能驗收。WACK appcert.exe test 以 -532462766（0xE0434352）結束，沒有 wack.xml；錯誤碼只指向未處理 CLR 例外，工具／環境／測試相容性根因未明，不能判定套件認證 PASS 或套件本身失敗。guest 套件／短效憑證清理無錯，精確 PID／路徑／父程序／建立時間核對後已回收本次 Sandbox，殘留為零。最新相同 EXE 使用獨立英文 CPU-only 設定開啟，完整人工操作仍待主人回報；正式 24k 評議尚未啟動。Store 尚未上傳或送認證，CH-T55 保持 Review／Smoke NO／Critic NO。

證據：`output/store-release-20261005-gemini-copy/package-sandbox/output/package-result.json`、`package-sandbox/disposal-receipt.json`、`manual-preview-launch.json`。
