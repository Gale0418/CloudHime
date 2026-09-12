# CH-T51 Research 流程與 frozen product-path 證據（2026-09-13）

## 結論

CH-T51 的剩餘產品門檻已完成：Research 可在 fresh frozen CloudHime.exe 中以網址留白自動搜尋或明確來源執行，無需 Python／pip；候選結果必須由主人確認後才保存，並維持 Settings Save 才啟用的既有兩階段生命週期。

## 本輪變更

- 來源模式分為 `search` 與 `explicit`，記錄來源 provenance、讀取狀態與是否截斷。
- 明確網址先做 URL 正規化、去重與數量限制；搜尋與讀取內容皆有界。
- Jina Reader 限制 token、移除 header／nav／footer／aside 並不保留頁面連結，避免把廣告、導覽與推薦清單當作品內容。
- Research 模型可選 Gemma 4 或 `gpt-5.6-luna`；憑證只從既有 SecretStore／單次 smoke 環境注入，不進命令列、版控、result 或 log。
- Model output 採既有 strict JSON schema、source-id allowlist 與 confidence／conflict merge contract。
- UI 不再自動 promote：完成抽取後顯示來源／條目／衝突／拒絕數，主人選擇確認或捨棄；確認只保存非 active pack，Settings Save 才啟用。
- normal translation path 仍不會觸發 Research 搜尋。

## 真實來源與政策邊界

- 舊 DLsite 商品頁／社團頁經 Jina page-chrome 移除後，約由 90,681 chars／549 links 降至 10,207 chars／14 links（商品頁）；大頁面改為有界截斷而非整頁拒絕。
- Google Gemma 對該舊成人向證據回傳 `PROHIBITED_CONTENT`。本輪不繞過政策、不把它誤報為程式故障，並提供 Luna 作為使用者明確選擇的另一條 provider 路徑。
- `閃刀姬 攻略` 查詢可命中巴哈姆特；萌娘百科可作為明確正常向來源。網址留白的 frozen 自動搜尋亦成功，不依賴 DLsite。

## 驗證

- Targeted：`92 passed in 5.07s`。
- Fresh build：`LLAMA_RUNTIME_COMMIT=1d1d9a9ed`，build exit 0；release provenance verify ok；preflight `ready`；391 files；1,585,177,325 bytes；0 model files；fresh ZIP 完成。
- Frozen explicit smoke：新 `dist/CloudHime/CloudHime.exe` exit 0；2 sources／1 readable／0 aliases／1 entry；`source_mode=explicit`；model `gpt-5.6-luna`。
- Frozen search smoke：同一新 EXE exit 0；8 sources／3 readable／3 aliases／20 entries；`source_mode=search`；model `gpt-5.6-luna`。
- 兩個 frozen result 只保存 schema、status、mode、model 與統計值；未保存 key、來源原文或模型原文。
- 完整 tracked inventory：`1469 passed, 6 skipped in 124.49s`。
- CodeRabbit 修正後 packaged smoke suite：`11 passed in 1.13s`。
- `py_compile` 與 `git diff --check` 通過。

## 審查與設計判斷

- Antigravity／Gemini read-only review 同意補齊 source provenance、bounded fetch、模型選擇與 owner gate；其建議的 candidate owner gate 已落實。
- 保留 CloudHime 既有兩階段語意：owner confirmation 保存 candidate pack，Settings Save 才切換 active pack，避免確認對話框意外改變執行中翻譯。
- CodeRabbit 第二輪的雙 smoke flag 靜默跳過問題已改為 fail-closed 並補回歸；第三輪的 model／key wiring assertion 已補。其「2026-09-13 為未來日期」判斷以本機 `Asia/Taipei` 當日日期與本輪即時 build／test evidence 駁回。
- Impeccable 本輪只用於 Research 控制項的資訊層級、文案、keyboard／disabled state 與 confirmation flow 檢查；skill 本身要求讀取版本資訊的同一工作回合不可自動更新，因此 4.1.1 → 4.3.1 更新延至後續獨立回合。

## 外部來源

- OpenAI GPT-5.6 Luna model：`https://developers.openai.com/api/docs/models/gpt-5.6-luna`
- OpenAI Responses API structured output：`https://developers.openai.com/api/reference/cli/resources/responses/methods/create`
- Gemini structured output：`https://ai.google.dev/gemini-api/docs/structured-output?lang=rest`
- Jina Reader：`https://github.com/jina-ai/reader`
- OWASP SSRF Prevention：`https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html`
- W3C PROV-O：`https://www.w3.org/TR/prov-o/`
