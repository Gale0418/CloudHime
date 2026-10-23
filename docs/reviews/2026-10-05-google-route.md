# Google 翻譯入口診斷（2026-10-05）

使用者回報候選版持續顯示 Google 翻譯流量限制。本次有可重現證據，與先前未重現的 CI 原生錯誤分開處理。

## 實測結果

- 主機 Chrome 開啟正常 `https://translate.google.com/`，以公開測試字串 `Hello world` 翻譯為繁體中文，成功顯示「你好世界」。
- 同一 Chrome 開啟程式使用的 `https://translate.google.com/m?sl=en&tl=zh-TW&q=Hello%20world`，轉到 Google 的異常流量頁並要求 reCAPTCHA。未操作驗證碼，也未改動網路設定。
- 主機 Python 對相同 `/m` 入口做單次有逾時限制的請求，收到 HTTP 429、無 `Retry-After`，回應含 CAPTCHA。已停止後續線上探測。
- 當日 10:20–10:21 的應用程式紀錄有多次 `TooManyRequests`；既有 transport 僅在 HTTP 429 時產生這個例外。

結論：程式入口確實遭到 Google 限制；正常翻譯網頁仍可使用。這些證據不能判定每日額度用完、Google 全面故障，或確定觸發封鎖的流量來源。

## 修正方向與限制

既有 worker 在批次失敗後會再逐段 fallback，429 仍可引發後續 HTTP 請求。以 transport 共用冷卻狀態停止這些請求，保留既有成功快取與原文 fallback。冷卻是本機保護政策，不能保證 Google 在期限到達時解除限制。

此修正不替換入口、不繞過 CAPTCHA、不輪替代理。現有 frozen EXE／MSIX 仍是先前候選，需重建才會包含新修正。

已完成跨 translator instance 的 thread-safe monotonic 冷卻，不 sleep、不持鎖進行 HTTP；429 後至少暫停 60 秒，合法且更長的 `Retry-After` 優先。冷卻到期後才允許下次正常請求。503 不誤觸發冷卻，既有同語言捷徑與成功快取可繼續使用，失敗不寫入快取。極端超出浮點範圍的合法 Retry-After 秒數會在本次 process 保持冷卻，需重啟解除。

CPython 3.10 測試：transport／helpers／orchestrator 共 42 passed；worker 原文 fallback 與 Google 限流狀態共 5 passed（136 deselected）；`git diff --check` 通過。測試均使用 mock，沒有持續探測被限制入口。尚未重建 EXE、未驗證 Google 已恢復，也未將歷史 WACK 視為新程式驗收。

## GitHub 解法查核

- [PR #231](https://github.com/nidhaloff/deep-translator/pull/231) 提議加瀏覽器 User-Agent，仍 open；維護者要求說明與測試，不能視為已核准的修正。
- [2026/08 Issue #307](https://github.com/nidhaloff/deep-translator/issues/307) 回報換 User-Agent 仍反覆出現 HTTP 500。與本次 429 不同，僅說明這個方法不保證穩定。
- [Issue #154](https://github.com/nidhaloff/deep-translator/issues/154) 說明上游 `translate_batch` 仍逐項送請求，不能消除限流。CloudHime 的 helper 已將同語言段落串接為一個請求，沒有照搬上游逐項 batching；本次新增保護針對失敗後重試放大。
- [googletrans](https://github.com/ssut/py-googletrans) 採 Ajax／HTTP2 的不同實作，但作者明確聲明非官方且不保證穩定；可作獨立候選研究，未安裝、未實測、未替換正式入口。
- [Google 官方 Python SDK](https://github.com/googleapis/google-cloud-python/tree/main/packages/google-cloud-translate) 可避開 HTML 解析依賴，但須另外設定 Google Cloud 專案、憑證及計費，不在本次自動遷移。

## 來源

- [deep-translator v1.11.4 Google adapter](https://github.com/nidhaloff/deep-translator/blob/v1.11.4/deep_translator/google.py)：429 對應 `TooManyRequests`，以 HTML selector 取得譯文。
- [上游入口常數](https://github.com/nidhaloff/deep-translator/blob/v1.11.4/deep_translator/constants.py)：Google adapter 使用 `/m`。
- [Google 異常流量說明](https://support.google.com/websearch/answer/86640)：這類提示涉及自動化或共用網路流量判定；此頁說明 Google Search，不能當作翻譯服務的固定額度或解除時間承諾。

## 2026-10-06：Shinkansen 對照取得可行入口

使用者提供 [Shinkansen](https://github.com/jimmysu0309/shinkansen)，並回報其 Google 插件在相同環境可翻譯。查核 GitHub Contents API 當下最新的 `shinkansen/lib/google-translate.js`，確認其直接 GET `https://translate.googleapis.com/translate_a/single`，參數為 `client=gtx`、`sl`、`tl`、`dt=t`、`q`，解析 JSON 的 `data[0]` 譯文片段。網頁索引的 raw source 較舊，入口一致，最新源碼另外包含逾時與批次防護。

同日單次 Python 請求以公開測試字串 `Hello world`、`sl=auto`、`tl=zh-TW` 呼叫這個入口，實測 HTTP 200、譯文「你好世界」。原 `/m` 在本次稍早重試仍為 429。這證明 Python 可以使用成功的 Google 入口；不證明 IP 永遠不會被限制，也不證明非官方入口具有長期服務保證。

因此將 CloudHime 的 Google transport 改為上述 JSON 入口，保留既有 source/target validation、背景 worker、快取、逾時、1 MiB 回應上限、response 清理與 429 冷卻。JSON 必須通過結構驗證，不能把破損／空回應當成功結果。沒有將被攔截的 `/m` 當自動 fallback。

僅參考可觀察的協定與入口，自行實作 Python transport；未複製 Shinkansen 的批次、分隔符、重試或 JavaScript 程式碼。其 [Google source](https://github.com/jimmysu0309/shinkansen/blob/main/shinkansen/lib/google-translate.js) 也明確註記這是非官方入口，Google 可能變更。

最終驗證：新 transport／helpers／orchestrator 組合 51 passed；worker 限流／原文 fallback 5 passed。之後僅補空白譯文拒絕並增加一案，final transport 33 passed；本輪合計 57 個不同案例通過，`git diff --check` 通過。經實際 helper 一次批次請求，`Hello world`／`Good morning` 取得「你好世界」／「早安」，兩行順序與行數正確。這是 source runtime 實測，EXE／MSIX 尚未重建，沒有宣稱更新後 frozen smoke 或 WACK 通過。
