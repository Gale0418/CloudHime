# 主席查證：固定版本 6d232c99e80935add7f07e6f912220dc487a6745

## 設定欄位

初稿正確指出載入本身不一定立刻重寫 canonical JSON，但「永久留在磁碟」不符合正常退出路徑：`cloudhime_ui.py:5136` 的 `close_app()` 明確呼叫 `save_settings()`；`:3874` 先取得 `get_settings_payload()`，`:3868` 正規化後回傳；`settings_store.py:299` 丟棄 `japanese_ocr_rescue_enabled`。因此它在載入後立即失效，正常保存／關閉即清掉，不會還原 runtime 選項。非正常終止、磁碟寫入失敗時舊 JSON 可能留存，但下次載入仍忽略；未承諾啟動即破壞性重寫原設定。本輪不新增啟動寫入。

## Notice 內容

實際讀取 ZIP／MSIX 內唯一 `THIRD_PARTY_NOTICES.md` 並计算 SHA-256，兩者均與來源相同：`6a5307f15fe5d8f0f8628c2743b6b7446e84b9351128bec0c4964a111beeebda`。來源掃描 meiki／onnxruntime 為 0。ZIP entry 分隔符需先將反斜線正規化；第一次仅匹配正斜線未找到 entry，不算通過，修正查核命令後兩份均通過。

驗證器沒有禁止歷史 notice 的字串黑名單，屬實；但本輪固定產物沒有該殘留。通用的來源與產物 notice 一致性防護可列後續加固，不把假想舊包混入視為當前已觀察到的缺陷。

## 程序與暫存

本輪 archive／MakeAppx 程序已結束。驗證後欲清除 `build/runtime` 與 `dist/retire-20260920/CloudHime-msix-stage`，已先限定絕對路徑與 reparse 檢查，但整個清理命令被執行政策拒絕；未繞過，未宣稱 staging 已移除。正式 EXE／ZIP／MSIX 保留。
