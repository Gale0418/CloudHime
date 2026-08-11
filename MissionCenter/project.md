# 專案

- 專案: CloudHime
- 目標: 準確度優先、local-first，先收斂 Region Vision 偶發 fallback，再完成發行供應鏈與 clean-machine gate
- 週期: CH-E9 漸進式 Hardening：Region Vision reliability
- 標籤: execution, verification, vision-first, reliability, release
- 活動紀錄:
  - [2026-08-11] CH-E10 MissionCenter 工作區現代化完成：修復 canonical 表格、依 evidence 收束 lifecycle、重建 brief/focus/HUD、建立 snapshot/closeout，最新版 doctor 通過。
  - [2026-08-11] 舊 project、progress、CH-E1 closeout 與 legacy HUD 已移至 `MissionCenter/archive/`；canonical 任務真相維持 `tasks.md`。
  - [2026-08-11] 產品焦點回到 CH-E9／CH-T79；CH-T64 與 CH-T67 不因文件遷移升格。
- 開放問題:
  - CH-T79：定位 Region Vision 偶發 fallback，完成兩種順序的 balanced rerun。
  - CH-T79 本輪已完成 bounded failure attribution；兩種順序實跑均因 `translation_region_vision_request_timeout` exit 1，待 GPU 空閒後重跑。
  - CH-T64：post-change WACK、clean-machine 與 Store gate 尚未完成。
  - CH-T67：尚待真實 API key 驗證 Models API availability。
