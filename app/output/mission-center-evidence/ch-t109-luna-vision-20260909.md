# CH-T109 Luna 與圖片產品路徑 live smoke

- 2026-09-09 使用主人確認的服務對應，憑證僅經子程序環境讀入記憶體，未匯入應用 DPAPI／settings；未使用 GitHub key。
- `python -u output/t109_vision_live.py`：固定合成文字 Good morning. 與記憶體產生的同文字 PNG；無私人截圖或本機文件上傳。
- Luna 文字：1 筆 nonempty，provider=openai、model=gpt-5.6-luna。
- Luna 圖片：1 筆 nonempty，provider=openai、model=gpt-5.6-luna。
- Gemma 26b 圖片：1 筆 nonempty，provider=gemma、model=gemma-4-26b-a4b-it。
- Gemma 31b 圖片：1 筆 nonempty，provider=gemma、model=gemma-4-31b-it。
- 追加 bounded 31b-only probe：可用 Google token 的第一次與第二次呼叫皆成功；另一個外部 token 兩次皆為 `400 INVALID_ARGUMENT`，未再用它重試完整矩陣。
- Helper exit 0 僅代表已收集結果；本次四個 live case 均以 `nonempty=true` 通過。
- 本機 targeted：`python -m pytest tests/test_translation_registry_online.py tests/test_translation_providers.py tests/test_openai_translation_provider.py tests/test_translation_orchestrator.py -q -p no:cacheprovider`：87 passed in 1.56s。
- OpenAI Docs 核對模型具有圖片輸入與 reasoning none；未據文件推定帳戶可用性，以以上實際產品回應為準：https://developers.openai.com/api/docs/models/gpt-5.6-luna
- PRODUCT.md 要求兩線上 Provider 的文字／圖片能力；本次已補足兩個 Gemma 圖片模型與 Luna 文字／圖片的 live 成功證據，T109 仍依 lifecycle 維持 Review，不直接標 Done。
- 先前的 HTTP 500 證據保留為歷史診斷；本次未保存 message、headers 或完整 response。修正 image-before-text payload 後，31b 兩次 bounded 呼叫均成功。
- 新增圖片 HTTP500 不重播／不輪替 regression，即使 auto_switch_enabled=True 也僅呼叫一次並保留例外；minimal thinking 不變。`python -m pytest tests/test_translation_providers.py -k 'http500 or 429 or timeout' -q -p no:cacheprovider`：4 passed, 51 deselected in 0.87s；diff-check PASS。沒有放寬只允許明確 429／404／503 的輪替政策。
- 追加 404／503 的 REST 輪替、404／429／503 的 SSE 無輸出輪替，以及 SSE 已輸出後禁止重播 regression；受影響 suite `python -X utf8 -m pytest -q -p no:cacheprovider tests/test_translation_registry_online.py tests/test_translation_providers.py tests/test_openai_translation_provider.py tests/test_translation_orchestrator.py`：`96 passed`；新增局部契約測試 `11 passed`。live 31b 圖片已成功，T109 可進入 Review。
- 完整 tracked `tests/` inventory：`python -X utf8 -m pytest -q -p no:cacheprovider tests --basetemp .pytest-full-20260909-t109`，`1458 passed, 3 skipped in 313.52s`；未把 ignored `output/` 舊測試樹納入宣稱。
