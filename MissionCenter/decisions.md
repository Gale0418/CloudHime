# Decisions

| 日期 | 決策 | 原因 |
| --- | --- | --- |
| 2026-04-29 | 設定頁採用寬版三欄 | 更接近 image2 mockup，也比 2x2 卡片更像商業化設定面板 |
| 2026-04-29 | 頂部只保留 Theme / UI Language chip | 使用者指定放在顏色模式旁邊，且不讓文字標籤擠壞排版 |
| 2026-04-29 | 只搬 UI，不重寫功能 | 現有 controller、signal、設定儲存已可用，重寫風險高 |
| 2026-04-29 | MissionCenter 主表清掉舊任務 | HUD 由 tasks.md 驅動，舊 Done 任務會干擾新任務生命週期 |
