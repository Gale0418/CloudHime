# Smoke Tests

| 日期 | 關聯任務 | 測試項目 | 測試方式 | 預期結果 | 實際結果 | 結果 | 類型 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-04-29 | CH-P0 | MissionCenter 標準檔案 | 檢查 `project/progress/tasks/decisions/notes/smoke-tests/snapshot` | 檔案齊全且可讀 | 已重建 | Pass | automated |
| 2026-04-29 | CH-T7 | 任務 HUD 存在 | 開啟 `MissionCenter/command-center.html` | 本機 HUD 可開啟 | 檔案存在且已接上新 state | Pass | automated |
| 2026-04-29 | CH-T7 | 任務驅動同步 | 修改 `tasks.md` 後執行 `python MissionCenter/sync_visual_state.py` | `visual-state.json` 以 tasks 生成，含 visible/rest/hidden 計數 | 目前 `progress=89`，`visibleTaskCount=3`，`restTaskCount=12`，`hiddenTaskCount=13` | Pass | automated |
| 2026-04-29 | CH-T7 | 任務排序與休息區 | 開啟 `command-center.html` 並比對 `tasks.md` 順序 | 小人依 `tasks.md` 由上到下顯示，Done 會進休息區 | 已用 headless Chrome 截圖確認：排序正確、Done 進休息區且摘要列同步 | Pass | manual |
| 2026-04-29 | CH-T7 | 溢出退場 | 檢查 `visual-state.json` | 可見人數不超過 15，Done 超量時最早完成者會被隱藏 | `visibleAgentCount=15`，`hiddenTaskCount=7` | Pass | automated |
| 2026-04-29 | CH-T7 | 自動監控同步 | 啟動 `watch_visual_state.py` 後修改 `tasks.md` | 檔案變動後會自動重跑同步，HUD 會跟著刷新 | watcher 已啟動並持續監控 | Pass | manual |
| 2026-04-29 | CH-S5.4 | UI 語言切換 smoke test | 透過設定切換 `zh-TW` / `en` | 介面、錯誤訊息與 HUD 文字會跟著語言切換 | 已通過，主按鈕與設定頁文字都能跟著切換 | Pass | manual |
| 2026-04-29 | CH-S5.4.4 | 多語 UI smoke test | 透過設定切換 `English / 繁中` | 設定頁、主視窗、錯誤提示與翻譯目標一致 | 已通過：PySide6 + Windows plugin，設定頁下拉顯示 `English / Traditional Chinese`，切到繁中後 `btn_now=立即翻譯`、`btn_30=隨機 3s~`、`lbl_page_title=設定頁面`、`lbl_ui_language=UI 語言`、`ctrl.get_ui_language()=zh-TW` | Pass | manual |
| 2026-04-29 | CH-T1 | Python 語法健康檢查 | `python -m py_compile CloudHime.py MissionCenter/sync_visual_state.py MissionCenter/watch_visual_state.py` | 沒有 SyntaxError | `CloudHime.py` 與同步腳本通過 | Pass | automated |
| 2026-04-29 | CH-T2 | benchmark manifest example | `python ocr_benchmark.py benchmark_manifest.example.json` | 可重跑且顯示 category/source/note/timing | 2/2 通過，`avg_timing_ms=14.80`，`p95_timing_ms=14.80` | Pass | automated |
| 2026-04-29 | CH-T3 | 速度基準 smoke test | `python ocr_benchmark.py benchmark_manifest.example.json` | 可重跑且顯示 avg / P95 | 2/2 通過，`avg_timing_ms=14.80`，`p95_timing_ms=14.80` | Pass | automated |
| 2026-04-29 | CH-S3.2 | 翻譯快取 | 以 dummy translator 連續翻同一句話兩次 | 第二次應命中快取，不再重複呼叫 translator | 已確認只翻譯 1 次 | Pass | automated |
| 2026-04-29 | CH-S3.3 | 低負載連掃模式 | 檢查 `CloudHime.py` 內的自動掃描分支 | `start_auto_scan` 與 `schedule_next_scan` 都有低負載節奏 | 已確認存在 `random_scan_center_seconds` 與 `current_auto_interval == 5000` 分支 | Pass | automated |
| 2026-04-29 | CH-T4 | 打包與啟動 smoke test | `cmd /c build_exe.bat`，再啟動 `dist\CloudHime\CloudHime.exe` | 打包完成且 exe 可以啟動 | `build_exe.bat` 成功，exe 啟動 5 秒仍存活 | Pass | manual |
| 2026-04-29 | CH-T5 | 商業化決策整理 | 檢查 `project.md`、`decisions.md`、`notes.md` | demo / pricing / store order / multilingual rules 都已定案 | 已補上功能限制、單次買斷、通路順序與 `zh-TW` / `en` 規則 | Pass | automated |
| 2026-04-29 | CH-T6 | 收尾驗證 | 檢查 `progress.md`、`snapshot.md`、`closeout.md` | closeout 已完成且快照可重開 | 已更新為完成狀態，MissionCenter 無待辦任務 | Pass | automated |
