主人，以下是本席獨立唯讀初評；沒有修改檔案、派代理、外部審查或讀取其他專案。Snapshot SHA256 已核對一致。未執行測試或 native 視覺驗證。

## 檢查範圍／限制

檢查 revision `6d232c99e80935add7f07e6f912220dc487a6745` 相對 `d17219e^` 的：

- `settings_store.py`
- `translation_settings_panel.py`
- `cloudhime_ui.py`
- `translation_helpers.py`
- 相關設定、UI smoke／panel tests

聚焦使用者設定遷移、控制器/UI 連線與操作失敗狀態。未評估 runtime 內部、供應鏈、GPU、準度、乾淨 Windows、Store 認證或實際視覺行為。

## 具體缺陷

### 缺陷 1

- severity：P2
- category：設定遷移／資料清理
- observation：`normalize_settings_payload()` 只在記憶體中 `pop("japanese_ocr_rescue_enabled")`；`Controller.load_settings()` 完成載入後，只有 AppData 搬遷或 legacy API key 條件成立時才呼叫 `save_settings()`。已存在且為 canonical AppData 的設定檔，若沒有其他觸發條件，退役欄位會永久留在磁碟。
- locator：
  - `settings_store.py:299`
  - `cloudhime_ui.py:3874-3890`
  - `cloudhime_ui.py:3891-4179`，尤其 `4176-4179`
  - `tests/test_settings_store.py:40-46` 僅驗證 normalization 結果，未驗證檔案被重寫
- repro：在 canonical AppData 設定檔加入 `{"japanese_ocr_rescue_enabled": true}`，啟動並載入；目前 runtime/UI 不再看到該欄位，但若未觸發 AppData migration 或 legacy key migration，原 JSON 仍保留該欄位。重新啟動後相同情況重現。此為靜態程式路徑判讀，未宣稱實際執行。
- impact：不符合「移除舊設定」的完整遷移語意；殘留設定可能造成支援診斷、設定檔稽核或後續 migration 判斷混淆。
- confidence：高
- unknown：未確認產品是否把「只從 runtime 丟棄、等使用者下次修改設定才覆寫」定義為可接受策略。
- recommendation：若要求啟動後完成退役欄位清理，偵測 normalized payload 與 raw payload 有差異時，對 canonical AppData 做一次安全重寫；或在 `load_settings_data` 層明確 scrub 後原子保存。
- proposedDisposition：`needs-fix`；補一個「載入含退役欄位後檔案不再含該欄位」的 regression test。

## 無缺陷／未見問題

- UI checkbox、翻譯文字、signal handler 與 controller callback 的 Meiki/OCR rescue 引用，在指定 lane 中已成對移除；目前剩餘的 `ocr_rescue` 引用屬 Windows／其他 OCR rescue，沒有證據顯示被誤刪。
- Gemma、本地多模態設定的 controller→worker 連線仍保留，未見因退場而斷線。
- Meiki 專用失敗狀態 handler 被移除，但未見因此吞掉 Gemma 或其他 OCR 的通用失敗狀態；未使用 native 視覺能力，故不對實際 UI 呈現下結論。
