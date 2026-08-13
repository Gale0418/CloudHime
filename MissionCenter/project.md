<!-- mission-center-managed-summary v=1 -->
# 專案

- 專案: CloudHime
- 目標: 準確度優先、local-first，先收斂 Region Vision 偶發 fallback，再完成發行供應鏈與 clean-machine gate
- 週期: CH-E9 漸進式 Hardening：Region Vision reliability
- 標籤: execution,verification,vision-first,reliability,release
- 活動紀錄:
  - [2026-08-11] CH-E10 MissionCenter 工作區現代化完成：修復 canonical 表格、依 evidence 收束 lifecycle、重建 brief/focus/HUD、建立 snapshot/closeout，最新版 doctor 通過。
  - [2026-08-11] 舊 project、progress、CH-E1 closeout 與 legacy HUD 已移至 `MissionCenter/archive/`；canonical 任務真相維持 `tasks.md`。
  - [2026-08-11] 產品焦點回到 CH-E9／CH-T79；CH-T64 與 CH-T67 不因文件遷移升格。
  - [2026-08-12] CH-T79 後續 hardening：Google OCR 預取改為 30 秒 bounded wait、executor 收尾冪等，並移除損壞的問號 hint marker；受影響測試 `93 passed`。CodeRabbit 前兩輪發現均已修正，最後複審因 WSL `E_ACCESSDENIED` 未完成，未宣稱通過。
  - [2026-08-12] CH-T84 完成 local Vision provider single-flight：FIFO、獨立 payload、不合併圖片；排隊中的 stale request 可取消，已送出的 request 不強制中斷。核心受影響測試 `215 passed`，未宣稱 GPU 速度改善。
  - [2026-08-12] CH-T85 建立 model-free scheduling benchmark：burst 8、10 repeats 驗證 `max_inflight=1`、FIFO 與 queued cancellation；CodeRabbit 四次 scope 嘗試仍未取得有效覆蓋結果（正確 scope 受 free review rate limit 擋下），任務維持 Review。
  - [2026-08-12] CH-T86 完成 local Vision shutdown cancellation hardening：scheduler close 對已排隊 request 發出取消語意，worker cleanup 先失效 active generation；217 passed，未宣稱 GPU latency 或 CodeRabbit 通過。
  - [2026-08-12] CH-T87 補上 local Vision warm-up cancellation gate：取消在 warm-up 前、資產檢查中，以及 runtime spawn/health 邊界都不再保留 server；`142 + 79 + 17 passed`，另 runtime 外部取消案例 `2 passed`；CodeRabbit 複審 `0 issues`。完整 local runtime suite 受既有 Windows pytest temp ACL `WinError 5` 卡在 setup，未宣稱 GPU benchmark。
  - [2026-08-12] CH-T86／CH-T87 完成 lifecycle closeout：completion council、受影響回歸、CodeRabbit `0 issues` 與 Git checkpoint 均有紀錄；兩項任務升為 Done。
- 開放問題:
  - CH-T79 已完成：bounded fallback attribution 與兩種順序 GPU balanced rerun 均通過；候選品質提升但延遲仍待後續受控優化。
  - CH-T64：post-change WACK、clean-machine 與 Store gate 尚未完成。
  - CH-T67：尚待真實 API key 驗證 Models API availability。
