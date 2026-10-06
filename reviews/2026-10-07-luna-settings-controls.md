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
