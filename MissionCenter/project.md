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
  - [2026-08-12] CH-T84 完成 local Vision provider single-flight：FIFO、獨立 payload、不合併圖片；排隊中的 stale request 可取消，已送出的 request 不強制中斷。核心受影響測試 `215 passed`，未宣稱 GPU 速度改善。
  - [2026-08-12] CH-T85 建立 model-free scheduling benchmark：burst 8、10 repeats 驗證 `max_inflight=1`、FIFO 與 queued cancellation；CodeRabbit 本小時三次 scope 嘗試未取得有效覆蓋結果，任務維持 Review。
- 開放問題:
  - CH-T79 已完成：bounded fallback attribution 與兩種順序 GPU balanced rerun 均通過；候選品質提升但延遲仍待後續受控優化。
  - CH-T64：post-change WACK、clean-machine 與 Store gate 尚未完成。
  - CH-T67：尚待真實 API key 驗證 Models API availability。
