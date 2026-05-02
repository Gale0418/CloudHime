# 視覺指揮中心

MissionCenter 現在改成「監控作業進度」的 HUD，不再把 `active-agents.json` 當唯一真相。
HUD 會讀 `MissionCenter/tasks.md`、`progress.md`，並同步到 `visual-state.json` / `visual-state.js`，再由 `command-center.html` 每 5 秒刷新。

## 入口

- [開啟 HUD](./command-center.html)

## 流程總結

1. 先更新 `project.md`，定義這一輪的目標。
2. 再更新 `tasks.md`，讓每個任務都有明確狀態與驗證條件。
3. `tasks.md` 的任務列現在要保留 `SmokeTest` 與 `Review` 欄位，值只用 `YES / NO`，方便追蹤有沒有做過煙測與審查。
4. 執行 `python MissionCenter/sync_visual_state.py` 後，HUD 會重新生成可視狀態。
5. 完成測試後，把結果寫進 `smoke-tests.md`、`progress.md`、`snapshot.md` 與 `closeout.md`。

## 顯示規則

- 任務短標題就是小人名稱。
- `Intake` = 任務已存在但還沒接。
- `In Progress` = 正在做。
- `SmokeTest` = 任務正在等煙測，小人會走到 SmokeTest 區。
- `Review` = 已完成主要實作，正在等審查。
- `Done` = 完成並進休息區。
- HUD 會顯示前 10 個非 `Done` 任務，`Done` 任務會進休息區。
- 可見角色超過 15 時，最早完成的 `Done` 先退場。

## 補充

- `tasks.md` 是任務真相來源。
- `smoke-tests.md` 是驗證紀錄來源。
- `progress.md` 是人類可讀的進度摘要。
- `snapshot.md` 是未來要回來接手時的第一份速讀檔。
