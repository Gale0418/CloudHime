# 任務

| 編號 | 標題 | 類型 | 上層 | 優先級 | 狀態 | 負責人 | 依賴 | 下一步 | 驗證 | SmokeTest | Review | 預估 | 標籤 | 備註 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CH-E1 | 設定面板視覺大改造 | Epic |  | P0 | Done | Owner / Codex |  | 依 image2 mockup 重做設定頁 | 完成三欄 UI、雙語切換與 smoke test | YES | YES | 8h | ui, settings, localization | Epic 不進 HUD |
| CH-T1 | 重設 MissionCenter 任務中心 | Task | CH-E1 | P0 | Done | Codex |  | 清掉舊亂碼任務並建立新任務樹 | HUD 同步後只顯示本次 UI 改造任務 | YES | YES | 30m | planning, hud | 已先重設 |
| CH-T2 | 對齊 mockup 的設定頁骨架 | Task | CH-E1 | P0 | Done | Codex | CH-T1 | 建立 header、top chips、三欄內容與 footer | PySide6 建立 SettingsWindowRevamp 不爆版 | YES | YES | 2h | layout, pyqt | 保留現有 signal 與 controller |
| CH-T3 | 美化 Translation 欄 | Task | CH-E1 | P0 | Done | Codex | CH-T2 | 讓翻譯卡片接近 mockup 的層次與 spacing | Google/AI 切換、API key、模型與 prompt 可用 | YES | YES | 1.5h | translation, ui | 不重寫翻譯邏輯 |
| CH-T4 | 美化 OCR 欄 | Task | CH-E1 | P0 | Done | Codex | CH-T2 | 將 OCR backend、滑鼠穿透、自動掃描與閥值刷新整理成同一欄 | OCR backend 狀態、數值調整與摘要同步正常 | YES | YES | 1.5h | ocr, ui | OCR backend panel 移入 OCR 欄 |
| CH-T5 | 美化 Rendering 欄 | Task | CH-E1 | P0 | Done | Codex | CH-T2 | 整理文字模式、截圖 prompt 與浮離細節 | Bubble/Relief/Screenshot 切換與浮離控制正常 | YES | YES | 1.5h | rendering, ui | Relief disabled 狀態要清楚 |
| CH-T6 | 補齊雙語與排版 smoke test | Task | CH-E1 | P0 | Done | Codex | CH-T2, CH-T3, CH-T4, CH-T5 | 驗證 en / zh-TW、暗色模式、設定值同步 | py_compile、PySide6 smoke test、截圖或可見文字檢查通過 | YES | YES | 1.5h | verification, localization | 不再只口頭說有測 |
| CH-T7 | 更新 MissionCenter closeout | Task | CH-E1 | P1 | Done | Codex | CH-T6 | 回寫進度、smoke-tests、snapshot 與 HUD | visual-state.json 顯示收工狀態 | YES | YES | 30m | closeout | 已收尾 |
