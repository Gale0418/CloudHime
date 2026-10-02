# CloudHime 推薦體驗驗收（2026-10-02）

本次將推薦定位聚焦於「看懂畫面上的外語，留在原內容裡」，並讓程式內的引擎選擇與失敗恢復支撐這個承諾。延續天宮書房介面，不改 OCR 演算法、模型路由、快取、取消世代或第三方服務設定。

## 交付行為

- README 補上使用情境、第一次翻譯、引擎金鑰需求、資料去向、限制、下載與公開支援入口；歷史測試及下載套件與本次原始碼分開標示。
- 引擎選項說明先試 Google 翻譯、本機模型準備、線上 Gemma 的 Google API 金鑰，以及 Luna 的 OpenAI API 金鑰。移除沒有本輪證據的模型品質、速度與首選排名。
- 設定頁新增三語系資料去向提示，跟隨目前選擇或待設定引擎；取消未完成設定後恢復原引擎說明。本機選項也說明雲端 OCR／遠端端點會送出內容，完整本文可由輔助功能讀取。
- 缺少 OCR、擷取失敗、無可用翻譯文字、翻譯失敗及空結果提供下一步。截圖空結果及失敗使用三語系訊息，不把沒取得文字說成畫面確定沒有文字。
- 首次空掃描即使沒有前次辨識文字，也會發出空結果狀態；明確傳入的狀態訊息及過期掃描防護保留。
- 補齊既有引擎健康摘要與細節的日文，包括準備、下載、進度、CPU／GPU 與錯誤恢復；中英文文案、狀態碼及判定維持原樣。

## 驗證證據

Windows、Python 3.13.11、PySide6 6.10.1、Qt offscreen；未呼叫真實翻譯 API 或模型推論。

```text
python -m pytest -q tests/test_translation_panel_advanced.py tests/test_product_experience.py tests/test_ocr_worker_mode_matrix.py tests/test_cloudhime_ui_smoke.py tests/test_provider_health.py --disable-warnings --maxfail=2
297 passed, 1 warning in 23.76s
```

新增／擴充檢查包含三語系引擎資料提示、待設定選擇及恢復、秘密欄位標示、首次空掃描、明確訊息／過期世代，以及截圖失敗／空結果的語言與未快取後可重試行為。這是指定範圍的測試，不是整個 `tests/` inventory。

日文健康狀態單檔測試為 `42 passed`，已包含在上述合併結果；另以 1,440 組參數比對 Git HEAD 與本次健康判定，中英文輸出的 code／summary／detail／tone 全部相同。日文進度保留百分比與模型名稱，錯誤訊息不回顯原始私人錯誤內容。

Qt 預覽由 `.tmp/preview_recommendation.py` 產生，保存於 gitignored 的 `output/recommendation-20261002/`。共 42 張擷取涵蓋三主題、三語系、四分頁、小尺寸桌面、缺少金鑰與失敗恢復。已檢視明暗／高對比設定頁、中文主窗、小尺寸英文／日文設定與金鑰頁、英文缺少 OCR 及日文截圖失敗；長狀態訊息可換行，底部操作仍可見。預覽隔離設定寫入、秘密讀取與原生快捷鍵，並於完成後清理 Controller 的工作執行緒。

日文健康摘要的翻譯缺口是在最後的版面確認中發現，後續修正以健康狀態及設定頁整合測試確認。上述擷取保留發現問題時的日文摘要，不另外開啟視覺微調迴圈；中文預覽不受此修正影響。

## 發行邊界

2026-10-02 查核 [GitHub Releases](https://github.com/Gale0418/CloudHime/releases)，公開版本標示為 Pre-release。此輪原始碼尚未重新建包；既有 `dist` 及 GitHub 下載包不會自動包含這些改善。

正式發行仍需以本次原始碼跑 Python 3.10 CI、重新建包、乾淨機器安裝／啟動／卸載、實際 OCR 與翻譯流程，並完成既有 Store／簽章相關檢查。offscreen 擷取不代表高 DPI、螢幕閱讀器或全螢幕遊戲的實機驗證。歷史 `1455 passed, 6 skipped` 結果不當成本次完整回歸證據。
