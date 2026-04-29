# Decisions

| Date | Decision | Reason | Impact |
| --- | --- | --- | --- |
| 2026-04-29 | 重建 MissionCenter，不沿用舊版內容 | 舊版任務中心已被主人判定有 bug，且目前 git 顯示舊檔刪除 | 以乾淨任務樹重新追蹤 CloudHime 上架前工作 |
| 2026-04-29 | 短期先做 Demo Readiness，不直接衝 Steam | 目前仍需穩定性、品質基準、打包驗證與商店資料 | 降低上架後負評風險 |
| 2026-04-29 | 品質判斷必須建立測試集 | OCR/翻譯工具不能只靠主觀感覺判斷「準」 | 建立可重複驗收與優化依據 |
| 2026-04-29 | 通路暫定優先順序為 Itch/Gumroad/Ko-fi -> Microsoft Store -> Steam | 先低成本驗證付費意願，再進入較正式通路 | 減少初期審核與費用壓力 |

## Open Decisions

- Demo 限制策略：每日次數、進階功能限制、時間限制，或完全免費測試期。
- 第一版定價：候選值可從 1.99 USD、2.99 USD、4.99 USD 比較。
- 是否提供離線模型模式作為付費主賣點。
- 是否保留 Gemma/OpenRouter 類雲端模型為進階功能。
