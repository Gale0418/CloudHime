# 任務

| 編號 | 標題 | 類型 | 上層 | 優先級 | 狀態 | 負責人 | 依賴 | 下一步 | 驗證 | 預估 | 標籤 | 備註 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CH-E1 | CloudHime demo 籌備與商業化 | Epic |  | P0 | Done | Owner / Codex |  | 依序安排穩定性、品質、速度、打包與市場任務 | P0/P1 任務都有 smoke test | 34h | product, release | 重點是讓產品能賣，不只是功能多 |
| CH-P0 | 重建 MissionCenter | Task | CH-E1 | P0 | Done | Codex |  | 建立 project/progress/tasks/smoke-tests/decisions/notes/snapshot | 標準檔案存在且可讀 | 1h | planning | 舊版 MissionCenter 是有 bug 的草稿 |
| CH-T1 | 錯誤與啟動健康檢查 | Task | CH-E1 | P0 | Done | Codex | CH-P0 | 重新檢查啟動、設定視窗、熱鍵與 UI log | `python -m py_compile ...` 通過且沒有新的 traceback | 4h | stability, bug | 已知問題：熱鍵 Error 1409 |
| CH-S1.1 | 檢查熱鍵衝突與備援操作 | Subtask | CH-T1 | P0 | Done | Codex | CH-T1 | 檢查 `RegisterHotKey` 失敗時的行為與備援控制 | 即使熱鍵失敗，App 仍然可用 | 1h | hotkey, ux | 不能只靠一個快捷鍵活著 |
| CH-S1.2 | 檢查設定視窗與 OCR 後端面板 | Subtask | CH-T1 | P0 | Done | Codex | CH-T1 | 打開/關閉設定，確認後端面板同步不再報錯 | `cloudhime_ui_errors.log` 不再新增設定 traceback | 1h | ui, settings | 舊 log 裡有 `ocr_backend_panel` 問題 |
| CH-S1.3 | 乾淨重寫 README | Subtask | CH-T1 | P1 | Done | Codex | CH-T1 | 把亂碼 README 換成可用的安裝與使用說明 | README 可讀且內容正確 | 2h | docs, trust | 這會直接影響第一印象 |
| CH-T2 | OCR 與翻譯品質測試集 | Task | CH-E1 | P0 | Done | Owner / Codex | CH-P0 | 收集 20-50 張具代表性的圖片與期望翻譯 | `ocr_benchmark.py` 能回報命中率與失敗案例 | 8h | quality, ocr, translation | 沒有測試集，所謂「準」只是感覺 |
| CH-S2.1 | 收集測試素材類別 | Subtask | CH-T2 | P0 | Done | Owner | CH-T2 | 蒐集遊戲對話、漫畫、字幕、UI 文字與低對比範例 | 每個類別至少有 4 筆案例 | 2h | dataset | 以真實使用情境為主 |
| CH-S2.2 | 定義品質指標 | Subtask | CH-T2 | P0 | Done | Codex | CH-S2.1 | 定義 OCR 命中率、翻譯品質、漏譯率與失敗註記 | `notes.md` 有可重複使用的評分規則 | 2h | metrics | 保持簡單，才有辦法常常重跑 |
| CH-S2.3 | 建立基準測試清單 | Subtask | CH-T2 | P1 | Done | Codex | CH-S2.2 | 建立 JSON 清單與範例資料 | Benchmark 可以載入清單並輸出摘要 | 4h | benchmark | 可沿用 `ocr_benchmark.py` |
| CH-T3 | 速度與 UX 基準 | Task | CH-E1 | P0 | Done | Codex | CH-P0 | 量測掃描、OCR、翻譯與顯示耗時 | 有平均值與 P95 的基準表 | 6h | performance | 先量測，再優化 |
| CH-S3.1 | 定義速度目標 | Subtask | CH-T3 | P0 | Done | Codex | CH-T3 | 設定區域掃描與備援路徑的延遲目標 | `decisions.md` 有速度門檻 | 1h | performance | 掃描區域要夠快，才好用 |
| CH-S3.2 | 檢查快取與重複翻譯處理 | Subtask | CH-T3 | P1 | Done | Codex | CH-S3.1 | 檢查翻譯快取與文字未變更時的跳過機制 | 重複文字不會再打 API | 3h | cache, api | 可降低成本與 rate limit 壓力 |
| CH-S3.3 | 檢查低負載連續掃描模式 | Subtask | CH-T3 | P1 | Done | Codex | CH-S3.1 | 檢查隨機掃描、抖動與自動暫停設定 | 長時間掃描時 CPU 與 API 使用可控 | 2h | cpu, ux | 對遊戲與視覺小說很實用 |
| CH-T4 | 打包與乾淨機驗證 | Task | CH-E1 | P0 | Done | Codex | CH-T1, CH-T2 | 驗證 PyInstaller 打包與實際 OCR 後端行為 | 乾淨的 Windows 機器可以啟動並使用 App | 6h | packaging, windows | 打包設定可能和執行環境不一致 |
| CH-S4.1 | 檢查 exe 與開發環境後端差異 | Subtask | CH-T4 | P0 | Done | Codex | CH-T4 | 比對 `requirements.txt`、`build_exe.bat` 與後端鏈 | 打包版不會宣稱自己有缺失的後端 | 2h | packaging, ocr | 對釋出誠實很重要 |
| CH-S4.2 | 乾淨 Windows 煙測 | Subtask | CH-T4 | P0 | Done | Owner | CH-S4.1 | 在乾淨機器上打開打包版並嘗試掃描/翻譯 | `smoke-tests.md` 有觀察結果 | 3h | release | 這最接近真實使用者 |
| CH-S4.3 | 錯誤回報文件 | Subtask | CH-T4 | P1 | Done | Codex | CH-S4.1 | 說明版本、log 與回報 bug 的方式 | README 有清楚的回報入口 | 1h | support | 可降低支援摩擦 |
| CH-V1 | 視覺指揮中心 v1 | Task | CH-E1 | P1 | Done | Codex | CH-P0 | 恢復 helper roster 與基地底圖 HUD | 打開本機 HTML 並確認 2 人視圖 | 4h | visual, dashboard | 第一版 HUD 太偏客製，這版回到技能一致的設計 |
| CH-T5 | 商業化與發佈路線 | Task | CH-E1 | P1 | Done | Owner / Codex | CH-T2, CH-T4 | 決定 demo 限制、定價、管道與商店文案 | `decisions.md` 有明確建議 | 5h | monetization, store | 先從 Itch/Gumroad 開始，再到 Microsoft Store，最後再考慮 Steam |
| CH-S5.1 | Demo 限制策略 | Subtask | CH-T5 | P1 | Done | Owner | CH-T5 | 決定時間限制、使用次數限制或功能限制 | demo 規則清楚且不惹人厭 | 1h | pricing | 第一版保持簡單 |
| CH-S5.2 | 商店素材清單 | Subtask | CH-T5 | P1 | Done | Codex | CH-T5 | 列出截圖、短影片、功能清單、FAQ 與隱私說明 | 素材清單可以直接執行 | 2h | store, marketing | 不要宣傳還沒做完的功能 |
| CH-S5.3 | 比較 Steam / Microsoft Store / Itch | Subtask | CH-T5 | P1 | Done | Codex | CH-T5 | 比較成本、審核時間、受眾與付款方式 | `decisions.md` 有清楚的推薦順序 | 2h | channel | 先走最便宜又合理的路 |
| CH-S5.4 | 多語介面與英文底座 | Subtask | CH-T5 | P1 | Done | Codex | CH-T5 | 讓 UI、商店素材與錯誤文字支援使用者語言，至少包含繁中與英文 | 介面會跟著系統語言或手動設定切換 | 2h | localization, ui, release | 商業化至少要有英文 fallback |
| CH-S5.4.1 | UI 語言下拉與儲存 | Subtask | CH-S5.4 | P1 | Done | Codex | CH-S5.4 | 在設定頁顏色模式旁加 `English / 繁中` 下拉，儲存到 settings，啟動時可還原 | 語言值可保存並跟隨設定檔 | 2h | localization, settings | 先把入口做出來 |
| CH-S5.4.2 | 集中式字串中心 | Subtask | CH-S5.4 | P1 | Done | Codex | CH-S5.4.1 | 將主要視窗、設定頁、錯誤提示改成集中式字串 key，避免 UI 文案散落 | UI 能以單一語言來源渲染 | 4h | localization, ui | 先支援主流程與設定頁 |
| CH-S5.4.3 | 翻譯輸出語言對齊 | Subtask | CH-S5.4 | P1 | Done | Codex | CH-S5.4.2 | 讓 OCR/翻譯輸出預設跟隨 UI 語言，維持 Google 與 AI 模式一致 | 掃描結果與按鈕行為同語言規則 | 2h | localization, translation | 不把介面語言和內容目標混在一起 |
| CH-S5.4.4 | 多語 UI smoke test | Subtask | CH-S5.4 | P1 | Done | Owner | CH-S5.4.3 | 切換 `English / 繁中` 後檢查設定頁、主視窗、錯誤提示與翻譯目標是否一致 | `smoke-tests.md` 新增語言切換驗證 | 1h | verification | 先驗設定頁和主視窗 |
| CH-T6 | 發佈候選收尾 | Task | CH-E1 | P2 | Done | Codex | CH-T1, CH-T2, CH-T3, CH-T4, CH-T5, CH-V1 | 彙整測試結果與發佈準備度 | `snapshot.md` 有 RC 結論 | 4h | closeout | 只有走完這步，才適合談商業化 |
| CH-T7 | 隞餃?撽? HUD ?? | Task | CH-E1 | P1 | Done | Codex | CH-T5, CH-T6 | 霈?HUD ?湔霈 `tasks.md` 銝虫誑隞餃???望?憿舐內 | `command-center.html` ?＊蝷箔遙??鈭箝??臬??滯?粹??| 6h | visual, workflow | 1 鈭?= 1 隞餃?嚗? 10 ??Done嚗one ?脖??臬? |
| CH-S7.1 | 任務資料流改造 | Subtask | CH-T7 | P1 | Done | Codex | CH-T7 | `sync_visual_state.py` 改成 tasks 驅動並保留完成時間 | `visual-state.json` 有任務 agents 與 completedAtByTaskId | 3h | data, workflow | 直接讀 tasks.md |
| CH-S7.2 | HUD 渲染與溢出 | Subtask | CH-T7 | P1 | Done | Codex | CH-S7.1 | `command-center.html` 依前 10 非 Done / 15 上限渲染 | 休息區與溢出退場規則可見 | 2h | visual, ui | Done 不算前十 |
| CH-S7.3 | 隞餃? HUD smoke test | Subtask | CH-T7 | P1 | Done | Owner | CH-S7.2 | 撽??????臬???top-to-bottom ?? | `smoke-tests.md` ??遙???葫閰?| 1h | verification | ?閬汗?函Ⅱ隤?|
