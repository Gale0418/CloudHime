# 視覺指揮中心

這個 HUD 現在跟著 `MissionCenter/tasks.md` 走，不再把 `active-agents.json` 當真相。
任務由上到下排序，前 10 個非 `Done` 任務會顯示；`Done` 會進休息區，總可見不超過 15。
背景監控器會盯著任務檔與進度檔，資料一變就自動重跑同步。

## 入口

- [開啟 HUD](./command-center.html)

## 顯示規則

- 任務短標題就是小人名稱。
- `Intake` = 任務已存在但還沒接。
- `In Progress` = 正在做。
- `Blocked` = 下一步是 smoke test。
- `Review` = 下一步是 review。
- `Done` = 完成並進休息區。
- `Done` 不算前十。
- 可見角色超過 15 時，最早完成的 `Done` 先退場。
- 區域內保留慢速漂移，不使用瞬移。
- HUD 會每 5 秒讀一次最新 `visual-state.json`，所以同步完後會自動刷新。
