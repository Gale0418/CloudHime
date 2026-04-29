# Smoke Tests

| 日期 | 關聯任務 | 測試項目 | 測試方式 | 預期結果 | 實際結果 | 結果 | 類型 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-04-29 | CH-P0 | MissionCenter 重建檔案 | 檢查標準檔案是否存在且可讀 | project/progress/tasks/decisions/notes/smoke-tests/snapshot 都存在 | MissionCenter 標準檔案已重建 | Pass | automated |
| 2026-04-29 | CH-V1 | 視覺指揮中心檔案存在 | 檢查 `MissionCenter/command-center.html` | 本機 HTML 面板存在 | 檔案已建立 | Pass | automated |
| 2026-04-29 | CH-V1 | 視覺指揮中心動態 | 在內建瀏覽器開啟 `command-center.html`，確認 1-role 基地底圖 | helper roster 能在基地底圖上顯示，且控制按鈕可用 | 基地底圖上顯示 1 個 helper，控制可用，動態可循環 | Pass | manual |
| 2026-04-29 | CH-V1 | 單人 HUD 與隨機外觀 | 重新同步 `visual-state.json` 並檢查 `command-center.html` | 沒有活躍子 AGENT 時只顯示主程式，helper 外觀會隨機抽選，且畫面大小足夠清楚 | `visual-state.json` 只剩 1 個 agent，主程式 avatar 重新抽選，單人顯示已放大 | Pass | automated |
| 2026-04-29 | CH-T1 | Python 語法健康檢查 | 執行主要 Python 檔案的 `python -m py_compile` | 沒有 SyntaxError | 在重建前通過 | Pass | automated |
|  | CH-S1.1 | 熱鍵行為 | 啟動 App 並觀察熱鍵註冊與備援行為 | 就算熱鍵失敗，App 仍然可用 | 尚未執行 | Pending | manual |
|  | CH-S1.2 | 設定視窗 | 開啟/關閉設定並查看 UI error log | 不應新增 settings traceback | 尚未執行 | Pending | manual |
|  | CH-T2 | OCR / 翻譯品質 | 用 benchmark 清單跑代表性圖片 | 摘要要能顯示命中率與失敗案例 | 尚未執行 | Pending | automated |
|  | CH-T3 | 速度基準 | 記錄掃描到顯示的耗時 | 需要有平均值與 P95 | 尚未執行 | Pending | manual |
|  | CH-T4 | 打包版驗證 | 在乾淨的 Windows 機器上啟動打包版 | App 能啟動並清楚完成掃描 / 翻譯，或清楚失敗 | 尚未執行 | Pending | manual |
