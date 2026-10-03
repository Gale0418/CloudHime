# CloudHime 產品體驗：狀態、推薦與連續閱讀驗收

狀態：本輪完成產品體驗來源修正、CodeRabbit 查證修復及 Git 同步前驗證；提交與遠端結果見文末收尾紀錄。完整可販售／打包／Store 驗收仍未完成。既有品牌以 DESIGN.md 的 Current shipping direction 為準。

## 已實作

- 本機文字／Vision 啟動失敗只顯示三語系、安全且可採取行動的指引，不把原始 runtime detail、路徑或長 stderr 送上主窗。
- 缺少模型與驗證失敗使用不同指引；正常停止 Vision 使用停用配色。
- 已切離的本機引擎回報仍更新內部健康狀態，但不覆蓋目前翻譯狀態與額度條。
- 主窗狀態強制 PlainText，翻譯、設定與本地化狀態的 tooltip／statusTip 同步更新。
- Provider 尚有 rolling quota 容量時不回報假等待；使用中的憑證沒有確定釋放時間時不捏造倒數。
- 主窗常態顯示所選主引擎與準備狀態，待設定的新引擎不冒充已切換成功；雲端金鑰存在只標示「金鑰已設定，連線未驗證」。
- 主窗新增三語資料去向摘要與直達翻譯引擎的入口。本機模式明示雲端 OCR、遠端端點與線上備援仍可能送出內容。
- 新手提示先框選小段清楚文字；未選範圍不再顯示「區域已選好」。移除未對應套件版本的 v3.0 標題。
- README 以使用情境、第一次翻譯、失敗恢復與限制組織內容，並區分來源、舊 EXE 與 Store 證據。

## 本輪驗證

Windows x64、CPython 3.10.11、PySide6 6.10.1。測試使用既有隔離 test-venv；沒有安裝依賴。UI 驗證採 Qt offscreen。

| 範圍 | 結果 | 證據 |
| --- | --- | --- |
| 產品體驗單檔 | 64 passed | output/experience-20261004/recommendation-product-final.xml、recommendation-product-final.log |
| 設定／主題單檔 | 15 passed | output/experience-20261004/recommendation-theme.xml、recommendation-theme.log |
| UI smoke／Provider health | 109 passed | output/experience-20261004/recommendation-ui-health-final.xml、recommendation-ui-health-final.log |
| Provider runtime／orchestrator／registry | 27 passed | output/experience-20261004/provider-tests.xml |
| 白晝／星夜／高對比恢復畫面、繁中／英／日首次使用 | Pass；文字可讀、控制區完整可見、OCR thread drain | output/experience-20261004/recommendation-inspection.json、recommendation-inspection-confirm.log、recommendation-*.png |
| Git 空白／差異檢查 | git diff --check exit 0 | 本輪工具輸出 |

兩輪合計 215 個不同通過案例（27 個 Provider 案例沿用前輪，該來源未再修改；本輪新增 17 案）。英文金鑰文案與主引擎 helper 命名收尾後，14 個受影響案例另行通過，證據 recommendation-copy-delta.xml；不重複計入總數。初始回歸測試曾以失敗證實原始 detail 暴露、狀態提示陳舊、inactive event 覆蓋及 quota 等待估計錯誤；修正後相關案例通過。來源 SHA-256 清單為 output/experience-20261004/recommendation-source-manifest.json。

### 失敗與限制

混跑 product_experience 與 settings_window_theme_polish 時，約第 26 案出現 Windows access violation，主執行緒堆疊落在 `_setup_remote_model_availability()` 的 `QThread(self)` 建構。該行未修改；Luna 唯讀診斷指出歷史同類崩潰也曾落在 QTimer 建構，應追查相鄰 UI fixture 的 QObject／thread teardown，不能把 constructor 行當成根因。本輪改採現行 CI 使用的單檔隔離方式，兩檔分別通過，**不代表混跑崩潰已修復**。失敗堆疊在本輪工具輸出；未生成完整失敗 JUnit。後續須保存 -vv 相鄰 nodeid、join 狀態與 DeferredDelete 時序再建立最小重現。

獨立截圖 harness 初版將 MagicMock 當成 Controller 的 Qt signal target，於啟動時 native crash。改用普通 lambda 作 signal target 後，同一個 harness 三主題正常執行並完成 shutdown；這是 harness 修正，不是產品啟動修復。

後續 bounded `-vv --maxfail=1` 混跑於 32 個通過案例後，先因短螢幕設定窗的 portrait 可見性斷言失敗而停止。前一案例與失敗案例的相鄰重跑也觀察到相同斷言失敗；兩案 teardown 的 OCR thread 都已停止，遠端／清理 worker 與活躍集合為空。證據：combined-result.json、combined.log、adjacent.log、lifecycle.jsonl。這既不能歸因 native crash，也不能宣稱 native crash 已不再重現。

行銷輪截圖 harness 切換模擬引擎後曾保留上一條額度失敗文案；補呼叫正式 indicator refresh 後三語初次使用畫面正確。關閉觀察 timer 一度在 `_close_app_finished` 尚未建立時讀取它，改用 getattr 後確認完整 drain；這兩項均為 harness 修正。最終 confirm log 沒有該 traceback。既有 test-venv 沒有 opencc，啟動日誌有相應提示；本輪未安裝新依賴，沒有驗證繁簡轉換品質。

本輪沒有 live 翻譯、GPU／模型品質、實體桌面、高 DPI、重建 EXE、WACK／完整 Store package、Store 更新或 clean-machine 的新驗收證據。沒有修改私人設定、憑證、舊套件或既有未追蹤美術檔。

## CodeRabbit

本輪使用已驗證本機 CLI 0.7.6／已登入帳號。原 repo 的 uncommitted 審查回傳了大於本輪差異的 reviewedFiles 清單，結果保留於 output/experience-20261004/coderabbit.ndjson。唯一 minor 為 quota 等待條件；以三個先失敗的公開契約案例查證，修正 retry_after／_next_wait 的 quota 滿額條件。

改以六個來源／測試檔的獨立 projection 審查。第一次缺少 base branch，未成功；指定 --base main 後審查成功，回報一個 minor：缺少模型不應被說成驗證損壞。已新增 dedicated model_missing 指引與三語測試，影響範圍 106 案通過。原始審查結果：output/experience-20261004/coderabbit-focused-base.ndjson。最後文字修正沒有再次 CodeRabbit 複審，不宣稱 0 issues；projection 的 snapshot 為修正前版本，不能用來宣稱最後來源評議完成。

行銷輪將 projection 擴為上述九個來源／測試／README 檔案，再執行 `review --agent -t uncommitted --base main -c .coderabbit.yaml`，exit 0、review_completed、兩個 minor、沒有 P0/P1。證據 coderabbit-recommendation.ndjson／stderr。

- README 日期被當成未來紀錄：本機時間為 2026-10-04T03:49:24+08:00，UTC 為 2026-10-03 19:49:24。已查證記錄日期正確並明列 Asia/Taipei，沒有改寫已完成測試為「計畫」。
- 缺少 runtime 時仍顯示「缺少模型」標題：三語回歸先出現 3 failed（runtime-heading-red.xml/log），再依 runtime_missing／model_missing 選正確標題與額度條；修正後 UI／health 109 案通過。

獨立 Luna 文案檢視另指出英文 “Key saved” 的持久化暗示超過記憶體金鑰存在判斷，已改為 “API key configured; connection unverified”。沒有 key 值輸出或三語缺漏的確定發現。這是實作檢視，並非正式 Mission Center critic_full。最後兩個 minor 處置後沒有再跑 CodeRabbit，不宣稱最終來源為 0 issues。

## 連續閱讀輪：字幕等使用者讀完

使用者要求改善「樂趣」後，採用遊戲／漫畫閱讀節奏作為方向，保留現有視覺與背景翻譯架構。沒有新增分數、音效、連續使用獎勵、依賴或模型品質承諾。

- **暫停與停止分開。** 自動掃描運作中的按鈕直接標示「暫停」，保留倒數／翻譯中回饋；按下後停止自動與顯示計時器、使目前 generation 失效，留下已顯示字幕。按鈕改為「繼續自動掃描」。繼續保留原間隔，暫停時改間隔也會套用；不立刻重複送出翻譯。
- **保持看到的那一句。** 暫停快照只取已渲染 bubbles 的文字及原擷取座標，不採用待更新串流。切換主題後不會退回上一段完成結果。使用者可在暫停期間按「立即翻譯」，更新字幕但不自動恢復掃描。
- **同一頁保持穩定。** 完全相同的結果與顯示條件沿用現有泡泡；文字、座標、主題、字型、DPR、可用螢幕幾何或顯示設定改變時重建。兩種串流更新與 clear 都會使重用狀態失效。這是 Qt widget 沿用的功能證據，不是遊戲 FPS／延遲提升的量測。
- **停止確實收乾淨。** Stop 清除 last_scan_results、暫停間隔與泡泡重用狀態，泡泡先 hide 再 deleteLater；之後換主題不會恢復舊字幕。
- 三語按鈕、提示與 README 同步。既有 smoke 的日文 idle 斷言更新為暫停後的 Resume 狀態，並追加明確 Stop 後回到 idle 的驗證。
- 新的 test_reading_overlay.py 加入 ci/test_groups.json 的 ui 群組，沿用既有 Windows UI 單檔隔離執行方式；本機清單契約通過，不宣稱已執行遠端 CI。

| 本輪驗證 | 結果 | 證據（皆在 output/experience-20261004） |
| --- | --- | --- |
| 產品體驗 | 74 案整檔通過；新增手動翻譯案另行通過，合計 75 不同案例 | reading-product-final.xml/log、reading-manual-delta.xml/log |
| 最後鍵盤操作／pause 文案差異 | 10 passed，不重複計數 | reading-product-copy-delta.xml/log |
| UI smoke | 64 passed | reading-smoke-final.xml/log |
| 泡泡沿用、串流、clear、字型／主題 | 10 passed | reading-overlay-final.xml/log |
| CI 清單與 runner 契約 | 9 passed | reading-ci-inventory.xml/log |
| 真實 Qt offscreen 畫面與生命週期 | 5 個語言／主題組合，控制區在 800×600 內；暫停保留範例字幕；Stop 清除；OCR thread drain | reading-inspection.json、reading-inspection-confirm.log、reading-*.png |
| 空白檢查 | git diff --check exit 0 | 工具輸出 |

本輪合計 **158 個不同案例通過**，reading-verification.json 以各 JUnit 的 classname／name 去重確認且無 failure、error 或 skipped。三輪累積 245 個不同案例；前輪 Provider／health／設定主題的 87 案未因本輪重跑，不把歷史證據冒充最新整套回歸。閱讀輪來源 manifest：reading-source-manifest.json。

紅測試先證實：暫停會清字幕、停止後主題變更復活舊字幕（reading-product-red.xml/log，2 failed），以及三個渲染模式都重建相同字幕（reading-overlay-red.xml/log，3 failed）。本輪第一次完整 UI／overlay 混跑因舊日文 idle 斷言停止（reading-ui-final.xml/log，1 failed、14 passed）；修正既定期待並加入 Stop 狀態後 UI smoke 64 案通過。未刪除失敗紀錄。

獨立 Luna 唯讀驗收涵蓋 render key、快照、pending／late generation、interval／Resume 與 Stop。唯一確定發現為上述舊測試期待衝突，已修正並驗證；未見其他確定產品缺陷。這不是正式 Mission Center critic_full。本輪沒有再呼叫 CodeRabbit；前兩輪已完成三次成功審查，不擴增既定外部審查額度，也不宣稱前輪 CodeRabbit 結果覆蓋本輪。

畫面中的村長對話為自行撰寫的範例字幕，沒有呼叫翻譯服務、擷取實際遊戲、量測長時間閱讀品質或重建 EXE。五個組合為繁中三主題、英文與日文白晝，並非全部語言×主題矩陣。截圖初輪的範例 completion 少了正常 status／indicator 流程，使額度條留在預設 0%；補齊 indicator 更新後 confirm 顯示 Google。這是 harness 修正，不是已查證產品缺陷。

本輪只改善閱讀操作與字幕重建；先前原生 Qt 混跑崩潰仍未知。短暫擷取失敗的空結果與「成功但沒有文字」目前仍共用 completion 契約，需獨立設計結果語意，沒有用本地化錯誤字串猜測或擅自保留過時字幕。

## 待確認的整體任務草案

建議交付：保留雲朵／天宮書房，Windows 原生、可下載試用 EXE。主要成功路徑為初次啟動→選定引擎與清楚知道資料去向→框選→理解翻譯結果或可恢复的失敗→取消／停止→關閉重開設定仍正常。Microsoft Store 更新為獨立後續發行 gate。

1. **可信任的操作狀態。** 收束已查證缺陷；追查本輪原生崩潰。首個里程碑逐項驗收三語錯誤恢復、切換引擎後背景回報隔離、missing／stopped／failed 差異、busy／取消／關閉生命週期與真實 Qt 畫面。現有修正與 198 案為部分證據。
2. **第一次使用就懂。** 讓主窗可見目前實際翻譯引擎與準備狀態；設定入口能直接到需要處理的項目；準備模型、缺少 Key、離線與資料去向都有明確說明。不新增未驗證的品質／速度承諾。
3. **閱讀與操控品質。** 在明暗／高對比、繁中／英／日、Windows 縮放與短螢幕檢查焦點、文字換行、控制區與錯誤／等待可讀性。限制兩輪成批畫面檢查，不反覆微調。
4. **同一來源的試用交付。** 鎖定來源、重建獨立 EXE／ZIP、檢查 provenance／OCR／啟動關閉與乾淨環境；評議該實際產物，交付操作與限制。正式 Store gate 承接 CH-T55／CH-T56，不能由來源測試代替。

以上是待核准的任務地圖，尚未加入 tasks.md。使用者若選擇全面重設或 Store 一起完成，依其選擇調整範圍與驗收。

Mission Center 正式可販售／發行評議採 critic_full。尚未取得本新任務的 total／per-seat／tool／wall-clock 明確預算；not dispatched: approval/budget missing。建議第一波及必要差異收尾共 8,000 tokens：四席每席上限 1,500，主代理整合預留 2,000；工具 24 次、20 分鐘。四席為三個 Luna critic 與獨立證據仲裁。預算用完保持未完成 checkpoint，不宣稱 passed。此前 CH-T117 的授權不能推定涵蓋這項全新產品任務。


## 2026-10-04T04:43:46+08:00：main 同步收尾

使用者授權直接提交／推送 main、更新 README 與 Mission Center，並以 CodeRabbit 補審較早的小檔案；未建立專案分支。這是來源同步切片，既有 CH-T117 完成狀態及 Store gates 仍依 tasks.md；沒有把本輪實作檢視登記為新的正式 critic_full。

### 審查範圍與額度

初審 projection 有 148 個 payload：11 個本次變更、137 個歷史小檔案。修改中的大 UI／smoke 檔保留真實差異，未因大小跳過；未修改的大檔、模型、私人資料、輸出、美術與授權 HTML 排除。148 留兩個名額避免服務計數差異；complete.reviewedFiles 實際為 148。較早評議 snapshot 的八個排除大檔與現況 SHA-256 完全相同（cloudhime_workers、其測試、local_vision_runtime／msix_packaging／ocr_worker_mode_matrix 測試、translation_helpers／providers／settings_panel）；這是沿用歷史來源證据，並非本輪 CodeRabbit 重審。

初審 6 issues（3 major／3 minor）；最後 21 檔完整差異複審 exit 0、review_completed、**CodeRabbit raised 0 issues.** 兩次開始前均以歷史執行時間核對 rolling hour，不超過每小時 3 次、每次 150 檔；先前 base 前置錯誤也保守計次。中間一次 shell 因 projection 目錄尚未建立而無法啟動，未呼叫 CodeRabbit；建立完成後才執行最後一輪。

| 六項建議 | 查證與處置 |
| --- | --- |
| major：AI debug 另存檔 | helper 無條件另寫無輪替檔案已移除，走既有 rotating logger。現行 callsites 主要傳模式、長度與錯誤類別，沒有已洩漏 OCR／翻譯正文的證據，不誇大成已發生外洩。 |
| major：舊下載腳本 | latest 與未驗 hash 的 ZIP／projector 使用確實存在。改要求固定 tag、archive 名、SHA-256、source commit，沿用既有驗證後解壓／provenance 工具；projector 用既有固定 revision／size／SHA-256，model 也驗既有 hash。不新增任意最新版本或執行真下載。 |
| major：paired quality 基準 | 同一 case 任一側／repeat 無 source 時，兩側共同用 translation_only；有 source 的原始 OCR 指標保留。反例原本 0.925 vs 1.0，修後雙側 1.0；兩側有 source 的 case 維持原規則。單次掃描 records，沒有增加平方級比較。 |
| minor：OCR None | 偵測空值確實會解參考；空值視為未就緒並啟動安裝，完成回報仍未知時安全顯示警告。回歸不啟動真 installer。 |
| minor：rgba alpha | 小數 0.5 被截成 0 已查證；小數／指數 opacity 在 [0,1] 時換算。Qt 整數 1 的既有語意保留，不照建議一律 scale；四種 alpha 回歸涵蓋 0.5、1.0、1、220。 |
| minor：models payload | 非 Mapping 的 JSON 會直接 AttributeError，已改為 invalid_models_payload，讓既有未驗證 fallback 接手。 |

來源 scope 與原始 NDJSON 保留在 output/main-sync-20261004；只有驗收文件進 Git，不上傳 output、私人設定或原有未追蹤 logo_v2。首次 scope 的 source digest 綁定修補前 snapshot，最終 21 檔另有 manifest；不能拿第一次的零其他發現冒充全部 repo 無 bug。

### 最新收尾驗證

Windows／Python 3.10.11／PySide6 6.10.1、Qt offscreen、隔離 APPDATA，使用既有 test-venv。七份成功 JUnit 去重合計 **245 個不同案例**；這是本次收尾切片，與前述三輪累積 245 的範圍不同，不能相加或當作全套 inventory。

| 檢查 | 通過 | 證據（output/main-sync-20261004） |
| --- | --- | --- |
| 產品體驗整檔 | 80 | product-experience-final.xml/log |
| UI smoke 整檔 | 64 | shipping-smoke.xml/log |
| paired evaluator 整檔 | 49 | paired-tests.xml/log |
| 遠端模型清單整檔 | 17 | remote-model-discovery.xml/log |
| logging 整檔 | 3 | logging-tests.xml/log |
| downloader、asset stream、CI 清單 | 30 | download-tests.xml/log |
| 真 PowerShell 安全解壓契約 | 2 | runtime-fetch-tests.xml/log；驗證正常 archive、錯誤 hash 與 ZIP traversal |
| 去重與來源綁定 | PASS | shipping-verification.json；final-review-scope.json 21 檔 hash 核對 |
| 空白檢查 | PASS | git diff --check exit 0 |

其中 downloader 15 案為本輪新清單，加入 core CI；overlay 新單檔仍列 ui CI。沒有新增依賴或變更 benchmark lock；paired evaluator 不在現行鎖定來源內。pytest cache 寫入遭拒是警告，成功 JUnit 無 failure／error／skip。

UI 收尾中一次 product_experience 整檔仍出現 Windows access violation（setup_worker）；product-experience-native-crash.log 保留。更早無 XML 的 80-pass 短 log 曾被覆寫，不計證據；改用不建立 Controller／QThread 的直接 panel 回歸後，最終整檔 80-pass XML 可追溯。這是新測試 fixture 的隔離，不能證明 native 根因已修。沒有新 frozen EXE、live API／GPU、真遊戲閱讀、實體桌面或 Store 發布驗收。

### 可追溯摘要

- coderabbit-148.ndjson SHA-256：`6ec3445edc111ba854e5624909a369b90f6431ab2b49b094582d121460478ab7`
- coderabbit-final.ndjson SHA-256：`bf7a811d842ae5491b55a85fc94d1afbbd0f1464648587c9eab3ffbb3f4b63c0`
- final-review-scope.json SHA-256：`85777c640b1ee8f42991b7d87cf1c7557fb1348232832cd5007d391cd16b1726`
- shipping-verification.json SHA-256：`4beade4033c6607e989b7ac6b77f95f0c69e30eeab8707da6a26ce1162458403`
