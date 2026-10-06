# Luna 設定控制項補齊

主人於人工驗收指出 Luna 沒有顯示／隱藏金鑰及檢查連線按鈕。已在同一個 Luna 設定區新增兩者，預設遮住金鑰，隱藏設定頁或停用 Luna 時重新遮住；繁中、英文、日文文案及既有主題均已接上。

連線檢查沿用既有背景 Qt worker，不新增常駐執行緒。以 GET `/v1/models/gpt-6-luna` 驗證認證與模型存取，禁止轉址、限制讀取大小及設定五秒 socket timeout；結果不保留金鑰或原始錯誤本文。重複點擊不重複派送，金鑰改變後舊結果不得覆蓋新狀態。成功文案明示文字／圖片翻譯需另測，不代表生成端點驗收通過。

## 驗證

- 2026-10-07，CH-T55 人工驗收修正：以專案既有測試環境執行 `tests/test_openai_connection_check.py`、`tests/test_remote_model_availability_worker.py`、`tests/test_translation_panel_advanced.py`、`tests/test_product_experience.py`、`tests/test_settings_window_theme_polish.py`，176 passed，47.41 秒。
- 預期：金鑰預設隱藏、按鈕可達、關閉重新遮蔽、三語狀態一致、背景派送、重複／過期結果隔離、HTTP 及格式錯誤安全分類。觀察：以上定向測試通過；未進行 live API 請求。
- JUnit：`output/luna-controls-20261007-tests.xml`。唯一警告為既有 `.pytest_cache` 寫入權限，未影響測試結果。
- `git diff --check` 通過。此切片未執行新的 CodeRabbit 或正式發行評論。
- 最新來源預覽 PID 52384 已啟動，啟動 log 到達 Controller shown，AppActivate 回傳 true；證據 `output/source-ui-luna-controls-20261007-004534/`，含啟動收據及啟動前設定備份。未把程序啟動或自動測試視為主人已完成實機操作驗收。

## 未完成範圍

請主人於設定 → 翻譯引擎 → Luna 操作兩個按鈕，並另測文字／圖片翻譯。既有 frozen EXE／MSIX 尚未重建，本次開啟的是來源預覽。CH-T55 保持 Review，授權覆蓋、最終封裝、WACK、Store 認證等發行閘門維持原狀。

官方 API 契約：[Retrieve a model](https://developers.openai.com/api/reference/resources/models/methods/retrieve)。

## 主人人工驗收回報

2026-10-07 主人回報「其他都沒問題」「Gemma 也可以正常運作」，附 `D:/Downloads/2026-10-07 00 32 29.png`。將既有清單的日文輸出、主題即時換色、看板娘、提示詞、擷取／停止記為主人整體操作回報通過；不推定未逐項說明的所有引擎或圖片模式組合都測過。

附圖直接可見日文字幕「明日午前九時、駅の前に待ち合わせます。」、本機 Gemma 狀態與翻譯完成訊息，支持本機 Gemma 日文輸出正常。這是主人提供的實機證據，未獨立綁定截圖中的程序／產物雜湊，亦不評為譯文品質 benchmark。

新 Luna 顯示／隱藏金鑰按鈕、連線檢查及 Luna 文字／圖片 API 實測尚無明確回報，維持待驗；線上 Gemma API 的獨立結果亦未明示。此人工回報不替代最終 MSIX 安裝／更新、WACK、授權覆蓋及 Store 認證，CH-T55 保持 Review。

## 00:48 Luna 人工結果與摘要同步修正

主人後續提供 `D:/Downloads/2026-10-07 00 48 43.png`，明確回報截圖模式完成且成功翻譯。圖中可見 Luna、gpt-6-luna、金鑰與模型存取正常、截圖翻譯完成及中文字幕。Luna 連線檢查與截圖翻譯因此記為主人人工驗收通過，取代上段對這兩項的待驗紀錄；不推定獨立文字模式或顯示／隱藏按鈕的每項操作已逐一回報。

同一張圖亦重現產品摘要錯誤：Luna 設定摘要只根據金鑰非空顯示未驗證，主面板只顯示 configured，兩者都未讀取連線結果。已將主面板、設定 provider 選項、狀態列與折疊標題同步到既有連線結果；成功顯示已驗證、檢查中顯示檢查中、失敗顯示檢查失敗。修改金鑰會撤銷舊驗證，重新開設定或切換語言仍保留當次程序的結果。未新增持久化成功狀態或以翻譯完成文字猜測 provider。

驗證：既有三份受影響測試 156 passed；新三語端到端回歸首次因測試誤將 QFrame 當按鈕呼叫 text() 而失敗，修正為實際 header 後聚焦 17 passed、72 deselected（含三語所有摘要、金鑰改變、檢查中及失敗狀態）。證據 `output/luna-status-sync-20261007-focused.xml`。此前嘗試不存在的 tests/test_localization.py 未執行測試，不算通過。此切片未使用真實金鑰呼叫 API，未執行新的 CodeRabbit／MSIX／WACK／認證。
