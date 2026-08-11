# 專案

- 專案: CloudHime
- 目標: 準確度優先、local-first，先收斂 Region Vision 偶發 fallback，再完成發行供應鏈與 clean-machine gate
- 週期: CH-E9 漸進式 Hardening：Region Vision reliability
- 標籤: execution, verification, vision-first, reliability, release
- 活動紀錄:
  - [2026-08-11] CH-E10 MissionCenter 工作區現代化完成：修復 canonical 表格、依 evidence 收束 lifecycle、重建 brief/focus/HUD、建立 snapshot/closeout，最新版 doctor 通過。
  - [2026-08-11] 舊 project、progress、CH-E1 closeout 與 legacy HUD 已移至 `MissionCenter/archive/`；canonical 任務真相維持 `tasks.md`。
  - [2026-08-11] 產品焦點回到 CH-E9／CH-T79；CH-T64 與 CH-T67 不因文件遷移升格。
  - [2026-08-12] CH-T79 後續 hardening：Google OCR 預取改為 30 秒 bounded wait、executor 收尾冪等，並移除損壞的問號 hint marker；受影響測試 `93 passed`。CodeRabbit 前兩輪發現均已修正，最後複審因 WSL `E_ACCESSDENIED` 未完成，未宣稱通過。
- 開放問題:
  - CH-T79 已完成：bounded fallback attribution 與兩種順序 GPU balanced rerun 均通過；候選品質提升但延遲仍待後續受控優化。
  - CH-T64：post-change WACK、clean-machine 與 Store gate 尚未完成。
  - CH-T67：尚待真實 API key 驗證 Models API availability。
