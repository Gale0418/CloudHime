# Smoke Tests

| 日期 | 任務 | 測試名稱 | 操作 | 預期結果 | 觀察結果 | 結果 | 類型 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-04-29 | CH-T1 | MissionCenter 重設 | `python MissionCenter/sync_visual_state.py` | HUD 只顯示本次設定頁改造任務 | visual-state 已同步，任務表改為本次 UI 改造 | Pass | automated |
| 2026-04-29 | CH-T2 | 設定頁語法檢查 | `python -m py_compile CloudHime.py translation_settings_panel.py ocr_backend_panel.py translation_helpers.py` | 無 SyntaxError | 通過 | Pass | automated |
| 2026-04-29 | CH-T6 | 設定頁 PySide6 smoke test | 建立 `SettingsWindowRevamp`，切換 en / zh-TW 與 dark theme | 視窗可建立，主要文字正確，控制項可同步 | 視窗 1180x740；en/zh-TW subtitle 與 save 文案正確；suffix 已改為 sec/min | Pass | automated |
| 2026-04-29 | CH-T6 | 版面可視檢查 | 擷取設定頁或讀取 widget 幾何資訊 | 三欄存在，footer 存在，沒有主要控制項消失 | 已產生 `MissionCenter/settings-panel-smoke.png`；三欄 x=[0,339,735]，footer 存在 | Pass | manual |
