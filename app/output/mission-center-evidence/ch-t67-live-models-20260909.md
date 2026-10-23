# CH-T67 真實 Google Models API 驗證

- 2026-09-09：主人確認 workspace 外 OWO.TXT 三個非空行依序為 GitHub、OpenAI、Google；僅取最後一行作本輪 Google discovery，其他憑證未使用。
- 經 PowerShell 讀入短生命週期子程序環境，Python 立即移除該環境欄位，呼叫產品 `remote_model_discovery.discover_remote_models` 預設官方 HTTPS endpoint。
- 實際結果：`status=verified`、`verified=true`、`record_count=40`、`error_code` 空；命令 exit 0。
- 不輸出 key、指紋、完整回應或 HTTP headers；未將 key 寫入 repo／settings／證據。父程序環境欄位已於 finally 清除。
- 此結果證明 live models.list 與 generateContent 過濾可用，不證明付費模型生成、翻譯品質、quota 容量或 Store gate。離線快照與 worker contract 仍以既有本機回歸證據驗收。
- 同日 `python -m pytest tests/test_remote_model_discovery.py tests/test_remote_model_availability_worker.py -q -p no:cacheprovider`：20 passed in 2.88s，exit 0。涵蓋分頁、supportedGenerationMethods、同 key 快照、離線／rate limit fail-open、worker thread 與安全錯誤回傳。
