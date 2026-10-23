# CH-T65：漫畫新模式、插件與自動 Research 再評估

**決策日期：2026-10-03｜範圍：唯讀評估；完成評估但不新增功能**

## 決策

目前三個候選均**不採用／不進 release**，保留現有 opt-in 漫畫能力及 Knowledge／Research。原因是沒有本輪具體的新使用需求或核准的額外延遲／外連預算；漫畫候選已有明確延遲退化證據，插件會擴大程式與發行供應鏈面，自動 Research 將改變現行需明確動作的外連界線；缺少需求與預算前不採用，若日後有明確授權可另行設計同意與撤銷機制。CH-T64 雖已 Done，本次 Store 候選的 WACK／上傳仍待驗；先完成 T117／T55 發行核對，不把新功能混入候選包。

## 目前已有能力與證據

- **漫畫 OCR／精修：** 有全螢幕 OCR、bounded region-aware multimodal crop、2×3 grid recovery 與 paired benchmark/evaluator。crop context 與 grid 都維持 opt-in；grid 不覆寫 baseline OCR item，錯誤時回退。決策記錄要求新增能力先守住 mapping、面積上限及 fail-open。見 `MissionCenter/decisions.md`（2026-07-24 Manga grid／region-aware crop 決策；T43 後續決策）及 `fullscreen_manga_benchmark.py`（`--grid-recovery` opt-in）。
- **漫畫品質邊界：** 固定 15 張標註頁的 5-repeat grid 結果為 5 improved／10 equal／0 regressed，但平均約多 2.44 秒、p95 約多 5.26 秒；此為獨立記錄的另一組結果。可明確追溯的公開 6 張 Windows OCR paired run（2026-08-14）中，baseline/grid 都是 0/6 anchor recall；平均延遲 2,362.352→13,768.007 ms，p95 6,594.127→57,605.568 ms，grid accepted 2/6（不是 anchor 改善）。因此該輪沒有可宣稱的準確度提升。**結論：保留探索 opt-in，不升成預設或自動掃描。** 私人標註未讀取；數字取自已提交的任務決策紀錄。見 `MissionCenter/decisions.md:902`、`MissionCenter/tasks.md:60`（CH-T43）。
- **Knowledge／Research：** 有本機 pack、來源追溯、結構化抽取／衝突與信心處理、相關檢索與 revision/cache 隔離、背景 builder 進度／取消；一般翻譯不觸網。Research 是明確使用者動作，候選經使用者確認才存成非 active pack，Settings Save 才啟用。DDGS/Jina 搜尋為 best-effort，失敗不得拖累翻譯。見 `MissionCenter/tasks.md:61-68`（CH-E8／T44-T50）、`output/mission-center-evidence/ch-t51-research-flow-20260913.md`、`MissionCenter/decisions.md:137-140,386,465-467`。
- **插件現況：** 在程式／文件範圍搜尋未發現產品插件 API／外掛載入契約；目前可用的 provider 與 builder 是產品內建路徑。故插件系統屬新架構，需額外定義信任、權限、隔離、相容性與封裝政策，不能視為低成本接線。此為本次 repo 搜尋的判讀，不代表對所有未追蹤／外部元件做稽核。

## 三個候選與採用必要條件

| 候選 | 本次 | 重新評估的必要條件 | 主要成本／風險 |
|---|---|---|---|
| 新漫畫模式（含提高 grid/crop 自動化） | 不採用；既有 opt-in 保留 | 先有明確使用情境與同一批鎖定案例；paired repeated-run 完整、任何 case 不退化並有可驗證語意收益；**預設路徑額外成本 0 ms**。使用者主動開啟的模式需有可配置且明示的 per-page 延遲上限；暫定評估上限為 p95 ≤ baseline 2× 且 ≤ 10 秒／頁，超限即不升級。 | 重試增加 OCR／模型時間、耗電與尾延遲；新分割／區域邏輯會增加座標錯配及回歸風險。現有公開 Windows OCR grid p95 約 8.7× baseline，超出暫定上限。 |
| 插件／外掛系統 | 不採用 | 有具名、可量化且內建方式無法滿足的整合需求；先定義最小 API/versioning、權限與資料出界規則、簽章／來源信任、隔離與卸載；背景閒置成本 0、安裝／呼叫成本有界；完成 frozen package、license／notice、惡意／故障外掛隔離及相容性驗收後才另立任務。 | loader、插件 ABI、攻擊面、相依套件／notice、支援矩陣與每次 release 驗證持續增加；目前沒有需求證據抵銷維護成本。 |
| 自動／排程 Research | 不採用；現行手動 Research 保留 | 僅在使用者明確啟用每作品排程、可隨時暫停／撤銷後評估；顯示並記錄查詢範圍／來源／時間，提供每次確認或使用者設定的候選自動採納規則；設每日請求／費用上限、逾時／退避、刪除與保留政策；一般翻譯仍零搜尋、離線與 provider 失敗均 fail-open；來源授權及模型政策逐項核實。 | 背景外連會洩漏作品／查詢興趣並產生流量／API 成本；來源變動、錯誤抽取、prompt injection 與政策拒絕需要持續治理。現有流程已能由使用者按需更新，尚無自動化需求證據。 |

上表延遲數字是本次重啟時可用的**暫定篩選門檻**，不是已核准的產品 SLA；若產品需求不接受此上限，需先提供明確預算再重開評估，不能在實作後補門檻。

## 重啟 trigger 與驗收

滿足以下條件才重開各自獨立任務：① 使用者提出可驗證的新情境／頻率與受益對象；② 明訂每頁 latency、背景 CPU／記憶體、網路請求／費用上限；③ 寫清楚資料種類、目的、外送對象、同意／撤銷、保留與來源授權；④ 列出新增相依、封裝／license notices、升級及支援成本；⑤ 以對應 holdout／凍結產品路徑證據證明效益且 release gate 可承受。缺任一項維持不採用；不得把既有 opt-in 或已完成的本地 Knowledge contract 誤報成新功能已核准。

## 本次限制與定位

本次只讀 `MissionCenter/tasks.md`、相關 decisions／evidence／benchmark 程式與 release 文件；未執行模型、GPU、API、測試或全回歸，也未讀 `records/private` 影像／標註或金鑰。發行狀態依本輪任務上下文：T64 已 Done，但本次 Store 候選 WACK／上傳待驗；`docs/release-two-track.md` 亦記明 0.1.2.0 Partner Center 版本核對、安裝／WACK 與上傳／認證未完成。此報告只完成 CH-T65 的採用決策，不推進發行狀態。
