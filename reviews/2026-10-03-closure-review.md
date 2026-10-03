# 2026-10-03 追加差異評議與局部成功顯示驗收

使用者以「准奏」核准追加 4,000 tokens、每席 800／整合 800、20 次工具／每席 3、10 分鐘。依同一封存快照執行三位獨立 Luna 評論者與另一位 Luna 仲裁者；沒有模擬專家、沒有修改產品或重建套件。原版來源仍為 bff0c4f。

## 正式結果：limited，保留 Review

共同快照 `output/mission-center-critique/CH-T117-closure-20261003-2245/snapshot.json` SHA-256 `273b99db9bceab2d0803aaf313c48740c01166f700ba8f7b53a5a0d116cc1b54`；主席逐檔核對 230 個 content-addressed entries。四席各自產生真實報告，全部在本席三次工具內完成；仲裁只在三席封存後讀取其報告。

| 席位 | 報告 SHA-256 | 結論 |
|---|---|---|
| flow | `713697098e48a2efe4ec7cf4491abc8e949d893d2fe60988e54a3108ae0e5fa8` | Worker 來源綁定修復；成功 GUI 的版本綁定仍 unknown |
| icon | `ee57d13ee9d52feac32f9c9c4fc9fe5ae70eb68dac1d0345a2e888d97d8221f8` | icon／runtime_taskbar covered；逐檔封裝來源與人眼回報有界線 |
| failure | `058034510a2ae665e2b82b87033e6e9e942fcd6458a9b179848ec43306562eb5` | 受控雙失敗 Qt／cache acceptance covered；報告 evidence.md hash 有筆誤 |
| arbiter | `852292c621546f06526ee739b4be011e89722b1a068da126120e242a27f46f94` | limited；三項舊 finding fixed，flow required lane unknown |

報告位於上述快照目錄。三項舊 finding 的根因分別為 Worker SHA 誤用、MSIX 圖示逐檔來源缺漏、雙 provider 失敗原文呈現缺少直接證據；本輪均有修復證據。沒有確認新的產品缺陷。

主席另發現 failure 報告的 evidence.md SHA 實際仍錯誤；作者已送出正確值 `38a8872bb6d03a727505387a2e69cae60fd6e8620b5084f47df74add52f9813b`，但未改寫封存報告。仲裁報告稱該欄已正確，與主席實際讀檔及 hash 比對不符；此不同意見保留，不能只沿用仲裁結論。部分代理寫出的中文理由已有 replacement characters，原始 bytes 保留，主席不冒稱重新編碼能復原。這些報告品質問題不等於產品失敗，但 final closure 仍須完成精確證據綁定。

正式主席紀錄 `output/mission-center-critique/CH-T117-closure-limited-20261003.json` 已經實際 Rust `critic` validator：valid=true、errors=[]。結構通過不等於 passed；兩個剩餘項維持 deferred：成功 GUI 版本綁定、封存 failure report 的證據欄位筆誤。主席比對結果獨立保存在 `chair-verification.json`，原報告均未覆寫。

## 評議後的局部成功顯示驗收

只針對缺少的成功路徑新增隔離 harness，不展開新的廣泛缺陷搜尋。Python 3.10 執行真實 `OCRWorker.run_scan_once` → Controller generation slot → `OverlayWindow.update_bubbles` → `TransBubble` QLabel 與 Qt paint。

- OCR 與 Google provider 是 deterministic mocks；Google 回傳 `TranslationResult(text="你好", provider="google")`，primary 呼叫 0、Google 呼叫 1。
- 真實 QLabel 顯示「你好」，Controller 狀態為 `✅ Translation complete`；實際繪製 96×42 PNG，非只檢查資料字串。
- 使用專屬 AppData／Temp／cache，Controller 關閉並結束測試程序；沒有執行 live API、模型或 GPU。這是 offscreen Qt 驗收，不是實體螢幕或 frozen EXE 自動點擊。
- 原產品來源沒有變更；未重跑 238 個已通過案例。環境有既有 opencc 缺少提示，未把本次局部測試外推完整語言功能。

證據封存於 `output/mission-center-evidence/ch-t117-success-20261003/`：

| 檔案 | SHA-256 |
|---|---|
| `harness.py` | `f3ea992979392a9917612ceeba87395d41d7ba2e8f9ff41bdbafe719c55c4ca3` |
| `result.log` | `3be1b4d07371eaaaa643287c7c56a9283f73af24a43fef05a82e60a6e7c702f8` |
| `success-translated-overlay.png` | `ea194624dffaf944471d3c4caa15834ca536ccf68e0ef222d3cec4136e89ed4c` |

追加評議 startedAt 為 22:59:33（Asia/Taipei）；23:12 checkpoint 時已過 12.51 分鐘，10 分鐘席位時限已結束。上列局部證據是在正式評議後補入，尚未由四席作 final-snapshot closure；不回溯宣稱已通過，也不再派送超額席位。下一次僅需核對此成功證據、作者正確重發的證據欄位及四席 final closure；不重新審查整個程式或開新廣泛 wave。Store／WACK／私鑰／Python 3.13 gate 維持獨立範圍。
