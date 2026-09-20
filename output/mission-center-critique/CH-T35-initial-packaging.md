主人，獨立唯讀初評完成。結論：發現 1 個 P2 缺陷，建議修正後再放行；其餘退場項目未見明確問題。

### 檢查範圍／限制

檢查 revision `6d232c99e80935add7f07e6f912220dc487a6745` 相對 `d17219e^` 的：

- `CloudHime.spec`
- requirements／lock 檔
- `prepare_release_provenance.ps1`
- `verify_release_dist.ps1`
- `THIRD_PARTY_NOTICES.md`
- 相關 packaging tests
- 指定 snapshot JSON

未修改檔案、未執行測試、未跑外部審查，也未重算大型 archive hash。Snapshot SHA256 與指定值一致，base revision 亦正確解析為 `d17219e^`。

### 缺陷

**Severity：P2（中）**  
**Category：封裝／授權殘留驗證**

**Observation：**  
release dist 驗證器只檢查必要授權 marker 存在，沒有檢查已退場的 Meiki OCR 授權與模型 notice 必須不存在。

**Locator：**

- `packaging/verify_release_dist.ps1:259-270`
- `tests/test_release_packaging.py:324-353`

目前 `requiredNoticeMarkers` 已移除 Meiki marker，但沒有負向斷言，例如：

- `## meikiocr`
- `Meiki OCR model weights`
- `github.com/rtr46/meikiocr`
- `meiki.text.detect.v0`
- `meiki.txt.recognition.v0`

**Repro：**  
未實際執行；靜態可知若 dist 中保留舊版 `THIRD_PARTY_NOTICES.md`，但仍包含現有必要 marker，該驗證器可能照樣通過。

**Impact：**  
過期的 Meiki 套件、模型來源或授權資訊可能殘留在最終 release artifact，違反本輪「授權殘留移除」目標。

**Confidence：高**

**Unknown：**  
目前無證據證明實際產出的 ZIP/MSIX 已含殘留；問題是 release gate 沒有阻止此情況。

**Recommendation：**  
在 `verify_release_dist.ps1` 加入退場 marker 的負向檢查，並在 packaging test 覆蓋 dist notice，而不只檢查 repository 來源檔。

**Proposed disposition：**  
`request_changes`／修正後重跑 release verification。

除上述驗證缺口外，本次檢查確認 `meikiocr` 已從 production requirements、lock、spec hidden imports 與 notices 移除；未發現其他具體退場／依賴／授權缺陷。
