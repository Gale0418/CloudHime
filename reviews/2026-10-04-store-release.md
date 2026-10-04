# 2026-10-04 新版 Store 發行 checkpoint

更新時間：2026-10-04T15:26:27+08:00。任務 CH-T55，狀態維持 Review；CH-T56 等實際商店更新結果，不提前 Closeout。

本次從 Git 來源 `014e0e77458022116e74ca9a6609c47d64f26405` 的獨立快照重建；產品程式與 `eb5ee34` 相同，後續差異為診斷文件。建置使用 Python 3.10.11、PyInstaller 6.18.0，40 個 production 相依版本符合 provenance。建置完成於 14:55:07 +08:00，候選 EXE SHA-256 `19df640299d1c6502b5e2ee93ed0833571cdf3c63838bb67fb113ef6629ccdba`。輸出位於 ignored `output/store-release-20261004/`，不含主人既有設定、金鑰或未追蹤新 logo。

本機驗證：light/full payload 與 provenance 通過；完整包 375 檔／4,896,195,318 bytes、兩個固定 SHA 模型及四份授權文件。frozen import 通過；Windows OCR 固定文字圖 1 張／2 行通過；純 CPU Vision 技術功能呼叫 1/1 通過；隔離 GUI 啟動存活 20 秒通過，測試程序及其 helper 由 harness 收回。這不代表辨識／翻譯準度 promotion，也不代表正常 GUI 的框選→OCR→多模態→泡泡流程已驗收。

首次完整包檢查失敗於模型授權文件的位元組差異；四檔內容在換行正規化後完全相同，改用本次 immutable source 的原始位元組後重新驗證通過。首次 OCR smoke 誤用沒有文字的品牌背景圖而失敗；改用固定英文／日文 fixture 後通過。兩次失敗均保留本機回執，不刪除或計入通過。

CodeRabbit：本輪一次送審，35 個從前一 frozen 來源到本次來源的程式／測試檔，約 1 MB；未上傳模型、runtime、dump、個人設定、憑證或歷史大文件。CLI exit 0、complete event `findings: 0`，reviewedFiles 與 scope 相同，0 issues。每小時 3 次／每次 150 檔限制仍適用。

商店：2026-10-04 從 Partner Center 現行套件頁確認 Submission 2 為 x64 0.1.1.0。已依新版發行授權建立 Submission 3（ID `1152921505702037522`）草稿；沿用免費／240 市場／CloudHime Private Preview 私人對象，未改公開範圍。新版 0.1.2.0 正在以受控 Store 身分封裝；目前尚未上傳新套件、送認證或發布。

GUI 能力限制：新 EXE 的空白隔離 profile 已啟動，日誌確認 Windows OCR 可用，AX 可讀主介面；Windows Computer Use 畫面擷取回報 `FrameArrived timed out`／`window capture timed out`，點擊無有效 geometry。恢復仍失敗，已清理本輪 PID 52820；不把 source audit、AX 可讀或 frozen smoke 當成完整操作通過。原 Store 安裝與主人設定未動。

正式評論額度：主人本輪明確採用 CH-T55 total 24,000 tokens、三名 Luna critic 與獨立 arbiter 各 4,000、integrator 8,000、每席 8 次工具／合計 32、評論階段 30 分鐘，含必要修正複核，converge。待成品與證據固定後派送，不沿用其他任務預算。評論、完整 Store package install/update/WACK、Microsoft 認證與實際 Store 更新結果尚未完成。

原 Qt retrieveMetaObject NULL 最初失效物件仍未確定；已確認的 event-filter 借用引用釋放鏈與三項生命週期修正見 `reviews/2026-10-04-qt-native-diagnosis.md`。新版 frozen 檢查通過不等於全部歷史原生崩潰根治。

本機證據：`build-result.json`、`source-manifest.json`、`verification-result.json`、`verification-initial-model-terms-failed.json`、`verification-wrong-fixture-failed.json`、`windows-ocr.json`、`cpu-vision.json`、`gui-result.json`、`coderabbit-scope.json`、`coderabbit-review.ndjson`、`coderabbit-receipt.json`、`store-draft.jpg`。沙箱與封裝進行中的紀錄另存其子目錄，待完成再追加。
