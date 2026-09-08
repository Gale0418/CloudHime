# CH-T109 Luna 與圖片產品路徑 live smoke

- 2026-09-09 使用主人確認的服務對應，憑證僅經子程序環境讀入記憶體，未匯入應用 DPAPI／settings；未使用 GitHub key。
- `python -u output/t109_vision_live.py`：固定合成文字 Good morning. 與記憶體產生的同文字 PNG；無私人截圖或本機文件上傳。
- Luna 文字：1 筆 nonempty，provider=openai、model=gpt-5.6-luna。
- Luna 圖片：1 筆 nonempty，provider=openai、model=gpt-5.6-luna。
- Gemma 26b 圖片：1 筆 nonempty，provider=gemma、model=gemma-4-26b-a4b-it。
- Gemma 31b 圖片：HTTP 500；未自動重播，沒有完成圖片成功驗收。這不是 Google key invalid 的證據；原因仍待診斷。
- Helper exit 0 只代表已收集所有結果，不代表全數請求成功。
- 本機 targeted：`python -m pytest tests/test_translation_registry_online.py tests/test_translation_providers.py tests/test_openai_translation_provider.py tests/test_translation_orchestrator.py -q -p no:cacheprovider`：87 passed in 1.56s。
- OpenAI Docs 核對模型具有圖片輸入與 reasoning none；未據文件推定帳戶可用性，以以上實際產品回應為準：https://developers.openai.com/api/docs/models/gpt-5.6-luna
- PRODUCT.md 要求兩線上 Provider 的文字／圖片能力；31b 圖片仍有未解失敗，T109 不標 Done，也不替換指定模型。
- 同日單次 bounded 診斷仍得到 HTTP 500，Google JSON 的 allowlisted status=INTERNAL；不保存 message、headers 或完整 response。這確認 API 回傳內部錯誤，不足以定位供應商內部根因，也不是憑證缺失。
- 新增圖片 HTTP500 不重播／不輪替 regression，即使 auto_switch_enabled=True 也僅呼叫一次並保留例外；minimal thinking 不變。`python -m pytest tests/test_translation_providers.py -k 'http500 or 429 or timeout' -q -p no:cacheprovider`：4 passed, 51 deselected in 0.87s；diff-check PASS。沒有放寬只允許明確 429／404／503 的輪替政策。
