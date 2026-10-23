# CH-T117：原始碼審查與 main 同步

## Summary

2026-10-02 整合主窗、設定引擎導覽、框選回饋與自動掃描倒數修整。主人明確授權將本次程式碼傳給 CodeRabbit，更新 README／Mission Center，並直接提交、同步 GitHub `main`，不建立分支。

## Completed

- CodeRabbit CLI 0.7.6 已安裝、已登入。每小時最多三次、每次最多 150 檔；本輪三次嘗試，沒有使用付費 credits。
- 第一次投影的 Git 差異為 150 檔，服務回報 `too_many_files`、`actualFiles: 152`，沒有完成審查。額外計數來源未確認；不將失敗記為通過。
- 第二次移除兩個純歷史補審檔，完成 **148 檔**：18 個本輪差異、130 個歷史檔完整補審。CodeRabbit raised **12 issues：5 major、7 minor、0 critical**。
- 逐項查證、補回歸測試、最小修復；第三次對 **20 檔修正差異**聚焦複審，`review_completed`，CodeRabbit raised **0 issues**。
- 新增 `tests/test_product_experience.py` 的 CI inventory 項目，避免新測試未被矩陣執行。
- README 更新使用步驟、金鑰與資料去向、存檔失敗的退出方式，以及原始碼／既有套件的版本邊界。

- 原始碼提交 [`2a80230`](https://github.com/Gale0418/CloudHime/commit/2a802305ee91d05e9e9bfc8f5053dfab61f7297f) 已直接推送 main，本地／遠端 SHA 一致，工作目錄乾淨。
- [GitHub CI](https://github.com/Gale0418/CloudHime/actions/runs/36997658191) 已 `completed / success`，八個必需工作通過；兩個真實 frozen release 工作依既有條件 skipped，不算新套件驗證。CI 使用正式 Python 3.10。

### 問題處置

| 嚴重度 | 檔案／問題 | 查證與處置 |
| --- | --- | --- |
| major | `themes.py` 氣泡 QSS 多餘右括號 | 成立；一般／浮雕規則各保留一個右括號，三種主題共六個回歸案例。 |
| major | `translation_providers.py` 串流省略目標語言 | 成立；省略時使用 provider 設定，明確語言仍覆寫；保留 `None`／空字串的既有 fallback 與快取行為。 |
| major | `cloudhime_ui.py` 一般存檔失敗無法結束 | 成立；預設取消，可明確選擇不儲存並正常清理後退出。金鑰儲存失敗仍拒絕退出，不可繞過。 |
| major | `cloudhime_workers.py` 非預期退出未送完成訊號 | 成立；當前 generation 的例外／取消會釋放忙碌狀態，正常路徑只送一次；過期 generation 仍抑制結果。 |
| major | `local_vision_assets.py` 收據覆蓋既有資產 | 成立；只合併可讀且同 revision 的資產 mapping，新核驗值優先；無效或舊 revision 仍依原行為處理。 |
| minor | `vision_product_path_local_adapter.py` `None` endpoint | 成立；`None` 視為未設定，其他非空 endpoint 仍拒絕。 |
| minor | 同檔 endpoint 字串切割 | 部分成立；原本已拒絕 userinfo，保留此保護。修正 IPv6 與 query 解析，依 parsed hostname 驗證 loopback、回傳 netloc。 |
| minor | `vision_product_path_collector.py` probe 遮蔽錯誤 | 成立；維持 scan、cleanup、probe 錯誤優先序，單獨 probe 失敗仍傳出。 |
| minor | `translation_providers.py` 關閉後請求型別 | 成立；scheduler 改拋 `LocalRequestCancelled`，走既有取消路徑。 |
| minor | `ocr_backends.py` 每張圖重複版本探測 | 成立；每 backend instance 以鎖快取版本探測，停用狀態仍為 false。 |
| minor | `provider_runtime.py` 未知 exception 被分類成功 | 成立；無有效整數 status 的錯誤回 `provider_error`，保留 timeout／整數 status 分類。 |
| minor | 同檔 cooldown 被回報零等待 | 成立；記錄 credential backoff 後跳過該 credential，保留其他 quota 邏輯。 |

### 本地驗證

Windows、本機 Python **3.13.11**、PySide6 **6.10.1**、`QT_QPA_PLATFORM=offscreen`；沒有真實 API／模型請求。受影響測試分批執行，共 **531 個不同案例通過**：

| 測試範圍 | 結果 |
| --- | --- |
| OCR mode matrix、settings theme polish | 142 passed |
| Product experience：選取／倒數、狀態／忙碌、設定／退出，三批 | 11 + 11 + 13 = 35 passed |
| UI smoke、translation panel、provider health、CI inventory | 159 passed |
| Translation providers、provider runtime | 79 passed |
| Product path adapter、collector | 88 passed |
| Local vision assets、OCR backend thread safety | 28 passed |

有效問題在修復前已有失敗回歸案例；修復後上述受影響驗證通過。額外的串流空值／快取相容性案例通過。語法檢查與 `git diff --check` 通過；警告不代表零警告測試。CI inventory 原先漏列新檔，確認失敗後已修正。

可公開追溯的審查範圍與輸入雜湊見 [scope manifest](2026-10-02-coderabbit-scope.json)。完整原始 NDJSON、本地測試紀錄與投影放在忽略目錄 `output/mission-center-evidence/`、`.tmp/`；不把暫存投影或機密推送到 GitHub。

## Unfinished

- 正式 completion critic council 尚未 dispatch：`critic_full` 需要 total／per-seat／tool／wall-clock 明確預算授權，目前缺少此授權，因此 CH-T117 保留 **Review**。CodeRabbit 複審完成不替代正式評議。
- 新原始碼未重建 `dist`／MSIX；CH-T55 Store 外觀確認、CH-T116 Python 3.13 原生崩潰調查維持原狀。

## Risks

- 正式 Windows CI 使用 Python 3.10；本機 3.13 的分批測試不能宣稱完整相容性。此前混跑 Qt 測試曾發生 native access violation，見互動體驗驗收，未宣稱根因已修復。
- 排除大型資產、模型、產物、機密、vendor／lock／generated 與不相關歷史大檔；排除不代表已證明無缺陷。有修改的核心大檔保留完整上下文。
- 148 檔是來源差異的實際 completed reviewedFiles 數；不把未審的兩個補審候選算進完成覆蓋，也不宣稱整個 repository 已全面審查。

## Smoke tests

指定回歸、語法與 CI inventory 已通過；Mission Center 使用已安裝 Rust CLI `sync`／`doctor` 核對 canonical tasks。外部 CI、Store、clean-machine 與 live API 各自保留證據邊界。

## Retro

隔離投影可讓本輪差異與歷史小檔共用一次審查，但服務計數可能包含 Git 差異以外的項目；此次由實際錯誤縮小範圍，沒有盲目重試。先查證再修，保留安全取消、秘密儲存與 generation 保護，聚焦複審後停止加開掃描。
