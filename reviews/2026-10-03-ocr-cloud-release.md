# 2026-10-03 OCR 修復、雲朵圖示與發行準備

任務 CH-T117、CH-T55；CH-T56 文件先行準備。主人確認 OCR 修復預覽版一般使用正常，定案純雲朵 logo，並授權依 T117 → T55 → T56 推進、同步 main。

## 修正與圖示

- 補齊 WinRT Foundation／Foundation.Collections 3.2.1 的生產與 CI hash locks、PyInstaller hidden imports 與可用性預檢，修正原生 async completion 因缺件卡住。
- 逐項翻譯失敗保留原文、顯示未完成或限流提示；失敗項不寫入 translation／preferred-text／HUD cache。保留 exact-image cache 的完整 provider guard。
- AI 退回 Google 後的 TooManyRequests 經 orchestrator 包裝，仍辨識為 Google fallback 限流；不用偏好引擎名稱推斷實際失敗來源。新增真實 primary → fallback 路由回歸，未送網路請求。
- 純雲朵來源 `assets/cloudhime_logo_cloud.png` 套入主 PNG 與 44／50／150px 圖示，保留透明度。未採用的人物稿留在本機，不納入版控／發行來源。

## CodeRabbit

CLI 0.7.6 已登入。審查使用獨立 Git 快照，core.autocrlf 與主工作區一致；不傳 Store identity、模型、產物、私人設定或人物稿。

1. 第一次因投影未指定基準分支退出，未完成分析，不列通過。
2. 明確指定 main 後，15 檔審查完成：1 minor issue，AI 偏好引擎退回 Google 時可能漏判限流。查證成立並修復。
3. 2 檔聚焦複審完成：CodeRabbit raised 0 issues.

原始 NDJSON、來源快照與測試日誌保留於 `output/cloud-release-20261003/`，不推送產物或憑證。CLI 的更新提示未作為執行指令；本次審查正常完成。

## 本機驗證

Python 3.13.11、PySide6 6.10.1、offscreen，分批執行，未宣稱完整 3.13 相容性：

- 修復後 OCR worker／orchestrator：136 passed（131 worker＋5 orchestrator）。
- 新圖示下產品互動：38 passed。
- OCR thread safety／dependency／release packaging／functional smoke：64 passed。
- 共 238 個不同案例；pytest cache 有既有 WinError 5 警告。diff-check 通過。
- 固定 Gemma 模型與 projector 的大小／SHA-256 與 manifest 相符，僅本機核對，未下載新模型。

新增 `docs/release-two-track.md` 與 README 連結，說明自簽 sideload、Store identity／版本、unsigned 上傳輸入、清理與恢復。信任位置核對 Microsoft 一手文件及 CI，LocalMachine TrustedPeople 的操作需要系統管理員工作階段；不宣稱已完成本次安裝測試。

## 套件、CI 與未完成項

本段先記錄來源準備；新套件建置、雜湊、frozen OCR／import、Store MSIX／upload、main／CI 對帳在取得結果後補登，不以舊 EXE 冒充新雲朵版。

正式 critic_full 尚缺 total／per-seat／tool／wall-clock 明確預算，保留 CH-T117 Review；本機工作階段未提升權限，WACK 與需要權限的自簽安装驗證尚未執行。Store 準備包不代表 Partner Center 已上傳、認證或發行，CH-T55 Review、CH-T56 Backlog 保留。
