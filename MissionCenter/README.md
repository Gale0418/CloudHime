# MissionCenter

這裡是 CloudHime 的任務與 HUD 控制中心。

## 目前運作方式

- `tasks.md` 是任務主表。
- `visual-hub.md` 是 HUD 與流程說明。
- `smoke-tests.md` 是煙測紀錄。
- `progress.md` 是進度摘要。
- `snapshot.md` 是重新接手時的快速入口。

## 任務表格式

目前任務列除了原本的欄位外，還會保留：

- `SmokeTest`
- `Review`

這兩欄用來標記該任務是否已做過煙測，以及是否已進入審查流程，值統一用 `YES / NO`。

## 更新順序

1. 先改 `project.md` 和 `tasks.md`。
2. 跑 `python MissionCenter/sync_visual_state.py` 同步 HUD 狀態。
3. 再把測試與結果回寫到 `smoke-tests.md`、`progress.md`、`snapshot.md`、`closeout.md`。
