# 2026-10-26 Git 保存與歷史程式碼審查

本輪依使用者授權在 main 保存程式與資源、擴大 CodeRabbit 歷史審查、修復已查證問題，並更新 README／Mission Center。後續另依要求將私人 example 與 run.bat 移回儲存庫根目錄。

## 審查範圍與額度

第一份隔離快照選入 150 個既有自有檔案，Git 與 WSL Git 均顯示 150 個差異檔；CodeRabbit 計為 151 而拒絕，沒有產生 finding。採用 CLI 建議的 `--dir app` 縮限後，實際完成 149 檔、約 2.67 MiB 的歷史完整檔案審查：核心模組、封裝、原生程式、CI 輔助及代表性測試。沒有送圖片、模型、private example、金鑰、生成產物、第三方來源或授權大文件。既有程式碼在暫存 Git 中表示成新增，供全檔靜態閱讀，不表示新增 149 個產品功能，也不代表全庫或翻譯品質認證。

前三次 CLI 嘗試分別為檔數前置失敗、149 檔審查、25 檔修補差異複核（UTC 12:23、12:26、12:46）。跨過原額度視窗後，UTC 15:41 再送根目錄搬移差異：20 個邏輯路徑，CLI 以 rename 計為 19 檔；未購買額外額度，任一滾動小時均不超過三次。原始 manifest、NDJSON、時間與退出碼保存於 `app/output/git-review-20261026/`。

## 意見查證與處理

149 檔審查提出 5 Major／9 Minor，共 14 issues；查證後修正 13 項，1 項誤報。25 檔複核沒有新 Major，另提出 1 項 HTTP 測試伺服器改善，已修並複測。搬移審查另提出 1 Major 驗證要求：確認 `ci.corpus_paths` 納入 frozen 包且符合封裝政策。PyInstaller 會沿正常 import 自動收錄；新 EXE 已抽出並核對該模組及 vision smoke 的編譯內容，無需額外 hiddenimport 或移動模組。未把驗證要求當成已重現的產品 bug，也沒有冒稱外部審查回報零 issues。

| 範圍 | 結果與驗證 |
| --- | --- |
| Google 金鑰隱藏後仍明文 | 關閉／隱藏面板時 Google、Luna 都恢復遮罩，按鈕文案同步；真實 Qt 回歸。 |
| 本機採樣參數未傳入 provider | registry 傳入 temperature／repeat penalty，建構與設定回歸。 |
| 金鑰欄位重複樣式覆蓋 | 移除後段覆蓋，保留 hover／focus／disabled；主題回歸。 |
| 預設提示詞句子相連 | 補空格，保留舊版無空格繁中預設與語言鎖的辨識；新舊保存值回歸。 |
| 省略 target_lang 蓋過 provider 設定 | 預設改 None，由 provider 設定決定；顯式目標維持；共用 Protocol 同步。 |
| Benchmark 偷補 geometry hints | 非 crop 策略明確要求 fullscreen／geometry hints，錯誤由 parser 拒絕。 |
| 金鑰儲存失敗無法選擇退出 | 明確詢問；拒絕保留視窗並重設旗標，同意才結束。 |
| CI 帶空格路徑與程序退出碼 | 逐參數保留空格、先取得程序 handle、缺 ExitCode 視為失敗；實際子程序成功／失敗回歸。 |
| Threshold judge 誤走雲端／漏限額 | 只允許已啟用遠端 Gemma 與合法模型，送出前檢查並記錄單模型限額；mock network 確認其他路線不送出。 |
| Gemma 載入參數缺驗證 | **誤報**：load_settings 已先呼叫 normalize_settings_payload，涵蓋非數字／非有限值／範圍；新增原碼即通過的 controller／worker 一致性案例。 |
| 等待憑證更新後仍用舊候選 | acquire／wait 每輪在鎖內重新查候選，移除後明確 unavailable；實際執行緒同步回歸。 |
| Provenance 腳本的 PowerShell 版本 | 宣告最低 7.0；Windows PowerShell 5.1 會在任何輸出或檔案操作前以明確版本錯誤停止。 |
| 認證請求自動跟隨 redirect | Responses 專用 opener 拒絕自動轉址，維持 bounded HTTP 錯誤；本機 HTTP 302 確認 target 未收到 Authorization。 |
| Frozen smoke 外層逾時太短 | 外層涵蓋 startup＋request＋30 秒；單階段最多 285 秒以維持外層 600 秒上限，超出者參數即拒絕。以實際 PowerShell wrapper＋受控 helper 驗證 180／285。 |
| 複核：HTTP 測試未讀 POST body | 兩個測試 handler 先讀完 Content-Length；未改產品行為，相關測試重跑通過。 |

## 驗證與資源

合併後 20 檔回歸初次抓到一項舊 UI 替身未提供新的退出確認依賴；補上明確拒絕回覆並保留「不退出」斷言。同時更新既有 Responses 測試的 transport 注入點，避免測試誤發真實網路。歷史修補去重為 869 passed／2 skipped；加入根入口與 corpus 搬移回歸，以最新 XML 相同 classname／name 去重後為 **1,007 passed、0 failed、4 skipped**：三項 Windows 建立符號連結權限跳過、一項需顯式啟用真實本機模型的 opt-in 測試。未放寬條件，也未將重複套件結果累加。

兩張背景圖已驗證為有效 1672×941 PNG，與目前預覽使用的圖及建置來源 manifest 位元組相同，本輪一併保存 Git。1254×1254 透明備用 Logo 保存為設計來源，未切換主程式圖示，也未加入本輪可執行包。圖片不送 CodeRabbit。

歷史修補預覽 `84d42e99…25b91f` 已另保留；包含最終搬移相容模組的新技術預覽 SHA-256：`0ce088c0196697dc8e5475cb0663ea8c8963f8e2cdc118b5c37706224b68b7b8`。11 個相關模組的包內 PYZ 與建置來源編譯一致；1,562 個 runtime／Qt／provenance／模型等依賴使用相同硬連結並核對身分／大小／時間，不重複複製模型。兩版的新 EXE 均通過 import、真實 Windows OCR（1 圖／2 行）與 20 秒啟動；最終版本另實跑 `verify_release_dist.ps1`，provenance、Qt、runtime、授權與兩個模型的固定雜湊政策通過（1,563 files、4,831,974,416 bytes）。這是封裝政策驗證，沒有重跑 CPU Vision、線上 API、乾淨 Windows 或 Store 認證。最終建置／原位替換證據位於 `app/output/git-layout-20261026/`。

## 根目錄入口與私人範例

`example/` 已搬回根目錄，113 檔、114,185,076 bytes，搬移前後數量與大小一致；沒有留下圖片副本。根 `run.bat` 自動切換 `app/`、優先使用 `app/.venv`，再找 PATH Python；從其他工作目錄、含空格路徑的真實 cmd 啟動測試涵蓋兩條路線。

`.gitignore` 明確忽略 `/example/` 與舊 `/app/example/`，CodeRabbit 也排除兩者；索引與提交清單不得包含任一位置的圖片。固定 benchmark manifest／hash 不為搬移重寫；本機 corpus 搬移回歸 109 passed／1 權限 skipped，另有 launcher／封裝契約 41 passed／1 opt-in skipped。保留明確 image root、一般相對路徑及絕對路徑的原契約；受控 `run_release_smoke → run_smoke` 回歸曾先重現絕對路徑被拒絕，再修正通過。

## 收尾狀態

來源修補與根入口已提交並推送 main：[e979da9](https://github.com/Gale0418/CloudHime/commit/e979da9c371d60adeac70d13b8721690bb571bc6)；[本次 CI](https://github.com/Gale0418/CloudHime/actions/runs/40355230310) 八個必要工作全部成功，兩個僅手動執行的 frozen 工作依條件跳過。README／Mission Center 已同步本機與 CI 結果，私人 example 在提交中為零檔。MSIX／Store 草稿及 CH-T55 Review 不變；不以來源同步當成商店發行完成。下一次保留固定 manifest 位元組並使用共用路徑解析，不再讓整理目錄與測試圖片位置互相綁住。
