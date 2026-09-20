# Meiki 補救路徑退場（CH-T35）

## 摘要

2026-09-20 主人明確要求移除 Meiki，並刪除上游詢問。原因是未證明穩定品質收益，不希望繼續承擔額外模型、供應鏈及授權釐清成本。這是取消原產品化方向，不是原功能通過準度驗收。Gemma、本地 llama-server、Windows OCR 與其他既有 OCR backend 保留。

## 已完成

- 移除 Meiki 的 UI、狀態訊號、背景載入 executor、CPU runtime、資產下載與候選複核路徑。
- 舊 `japanese_ocr_rescue_enabled` 設定在正規化時丟棄；不再儲存或恢復。
- 移除 Meiki 專屬 benchmark 開關及計分欄位；舊 CLI flag 明確拒絕，不會默默使用另一種測試。
- 以原版 pin constraints 重新解析 Windows CPython 3.10 生產／CI 依賴，再由既有 dependency_contract 生成 hash lock。生產 54→38、CI 60→45 個元件；保留套件版本與 SHA 未改。
- PyInstaller 明確排除 meikiocr／onnxruntime；移除 frozen import smoke 對它們的要求，以及不再適用的第三方 notices。
- 本機 `C:\Users\USER\AppData\Local\CloudHime\models\japanese-ocr\meiki-0.3.1` 下三個 ONNX 檔逐一比對舊 manifest SHA 成功後移至資源回收筒，共 45,970,040 bytes；可還原。未更動 Gemma 模型或全域 Python 套件。
- 原建置 session 78548 已中止（exit 1），不得作為新版本通過證據；確認原建置父程序及直屬子程序不存在。

## 上游發文處置

https://github.com/rtr46/meikiocr/issues/15

已驗證作者 Gale0418。`gh issue delete` 回覆 `does not have the correct permissions to execute DeleteIssue`。因此未徹底刪除；已將標題改為 `Withdrawn`、內文改為 `Withdrawn by the author. No response needed.`，並以 `not planned` 關閉。API 確認 CLOSED。編輯歷史可能仍保留原文；永久刪除需要上游具有適當權限者處理，沒有繞過權限或宣稱刪除成功。

## 驗證

- 最初誤用未裝 pytest 的 production Python，未啟動測試；改用已驗證的既有測試環境。
- 第一輪受影響測試：374 passed、1 skipped、1 failed；唯一失敗是測試仍 mock 已刪除的 JapaneseOCRRuntime，已移除該殘留並新增 runtime 不存在斷言。
- 初始 pip 23 dry-run 缺新式 license metadata，contract 拒絕；改用隔離 resolver 的 pip 26.2.1，沒有修改全域 pip。生產／CI dependency contract 分別為 38／45 components PASS。
- 完整 CI inventory：1421 passed、7 skipped、1 failed in 218.78s。唯一失敗為 `test_production_and_ci_locks_keep_distinct_graphs` 的舊預期：移除 ONNX 後 `packaging` 只屬於 CI，不再是 production dependency。修正此預期後，dependency／packaging／benchmark／settings／UI panel／worker 相關測試 226 passed in 20.01s；未把前輪完整執行改寫為全綠。
- 新增 regression：舊設定 opt-in 被丟棄、worker 不再建立 Meiki runtime／executor、UI 勾選框不存在、PyInstaller 排除 Meiki／ONNX、requirements／lock 無這兩項依賴、舊 benchmark flags 回傳 CLI error 2。
- 原始碼啟動檢查：在獨立子程序的 import finder 明確拒絕 Meiki、ONNX Runtime 與已刪除的三個模組，`import CloudHime` 及 `run_packaged_import_smoke()` 仍成功；不是 frozen EXE 驗證。
- CodeRabbit 使用獨立 snapshot，範圍為 32 個變更檔，排除 examples、二進位、generated、lockfile 和 MissionCenter 文件；初次於本機準備階段因缺比較基準退出，指定既有 `main` 基準後完成，0 issues、exit 0。未為了追求結果重複掃描。
- Mission Center sync／resume 確認 sourceFresh=true；doctor status=pass，既有 legacy completion-passport unknown warnings 保留。T35 仍為 Review，沒有建立新完成 passport。

## 未完成與風險

- CH-T35 維持 Review，僅剩移除後的新發行包驗證，不再追蹤 Meiki 授權或品質提升。
- 尚未建立移除後的 fresh EXE／MSIX；本輪未執行新套件 WACK、Store submission 或乾淨 Windows 驗收。
- 主人確認無乾淨 Windows／VM；宿主隔離測試不替代真正乾淨機。
- 專用 resolver venv 位於 `.tmp/meiki-resolver`，沒有殘留執行中程序；刪除此暫存目錄的命令被執行政策拒絕，因此保留未追蹤目錄，沒有改用其他方法繞過。

## 回顧

先確認功能是否仍值得保留，再追舊任務的外部驗收。歷史 no-regression 不等於有增益，也不應自動延續成產品需求。
