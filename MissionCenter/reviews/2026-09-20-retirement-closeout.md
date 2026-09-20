# T35 退場收尾

## 摘要

2026-09-20，CH-T35 已由正式 Rust CLI transition 從 Review 進入 Done；operation `ch-t35-retirement-20260920-complete`，completion passport 已驗證。完成的是主人要求的 Meiki 退場，不是原 Meiki 功能產品化／準度驗收。

## 已完成

- Meiki 程式、UI、下載、依賴移除；舊 opt-in 載入時忽略，正常保存／關閉不再寫回；Gemma、Windows OCR 保留。
- 新 EXE／ZIP／unsigned MSIX 的 bounded 驗證與封裝來源證據完成，詳見 `2026-09-20-release-followup.md`。沒有上傳實驗圖片或二進位到 Git。
- 修正移除後暴露的 CI PyYAML 與 build validator packaging 隱性依賴；兩者未加入正式 runtime graph。CI `67f7c78` 通過。

## 未完成

- T64：真正乾淨 Windows、當前套件管理員安裝／WACK 與發行供應鏈；主人無另台乾淨機／VM，Sandbox 方案尚待選擇，未啟用、未重開機。
- T53～T55：正式 Partner Center 產品身分、套件對齊、認證／首次發行；依既有決策尚未開始外部提交。
- T56：依正式發行結果完成雙軌文件收尾；T65：T64 穩定後才再評估新功能。

## 風險

- 本輪未執行完整 MSIX unpack 後 verifier、簽署、安裝、WACK、乾淨 VM 或 GPU 品質驗收；歷史 PASS 不轉移成新版本 PASS。
- 過去 GitHub 詢問已撤回並關閉，但永久刪除仍受上游權限限制。
- `build/runtime` 與 `dist/retire-20260920/CloudHime-msix-stage` 的精確清理命令被政策拒絕，留存可重建暫存，未繞過限制。

## 煙霧測試

31 項修正相關測試 PASS；新 EXE 362 files／0 model files，PYZ 857 modules 無退休模組；隔離 import 與 20 秒啟動 PASS。ZIP 所有 362 payload SHA-256 與 dist 相符；MSIX pack、identity、內含 EXE hash 及退場檔名檢查 PASS。ZIP／MSIX notice 與無 Meiki 的來源檔 SHA-256 相符。詳細歷史失敗與修正保留於 release-followup，不覆寫成全程成功。

## 完成評論委員會

3 位真正獨立 Luna/high 評論者，初稿互盲封存後由另 1 位 Luna/high 裁定；均無對話歷史且唯讀。初輪約 339 秒，代理均已關閉，未啟動 delta wave。已下達主人核准的 16,000 tokens／每席 4,000、16 次工具／每席 4 次、10 分鐘限制；工具沒有提供可獨立驗證的總 token 用量，因此不聲稱精確消耗。

兩項 Medium 意見與不同意見完整保留：

- `CACC-CH-T35-settings-migration-76114dad-1`：評論／裁定要求啟動即重寫；主席依固定版本 `close_app() → save_settings() → normalize_settings_payload()` 與忽略舊開關的路徑反證，處置 `rejected-with-counterevidence`。沒有宣稱全票一致。
- `CACC-CH-T35-notice-hardening-77f993db-1`：固定產物無殘留；未來任意 dist 的 notice 一致性加固 `deferred`，已回寫 T64，非忽略／刪除發現。

機器紀錄：`output/mission-center-critique/CH-T35-retirement-20260920.json`，正式 Rust `critic --input` 驗證 PASS。`criticProposedDisposition: fixed` 是契約對「評論建議修復」的列舉表示，不代表曾做該修復；實際處置以 `chairFinalDisposition` 與原稿為準。評論不是測試證據。

## 回顧

功能移除除了刪 runtime，也要分開驗證 CI 與建置工具依賴。評論要求應比對實際生命周期與固定產物，避免為理論殘留新增不必要的啟動寫檔。
