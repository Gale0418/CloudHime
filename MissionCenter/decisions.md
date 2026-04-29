# Decisions

| Date | Decision | Reason | Impact |
| --- | --- | --- | --- |
| 2026-04-29 | MissionCenter 以繁中為預設 UI 語言，商業化時保留英文 fallback | 產品要跟著使用者語言走，但上架與國際化仍需要英文底座 | 所有 UI、TASK、smoke test、HUD 文案都要可本地化 |
| 2026-04-29 | CloudHime 正式介面預設 `zh-TW`，`en` 作為唯一公開 fallback | 目前主要使用者與展示情境都以繁中為先，但英文是上架與國際溝通必要底座 | 字串、錯誤訊息、README、商店頁都要維持雙語可展開 |
| 2026-04-29 | 字串 fallback 採 `zh-TW -> en -> 安全技術預設` | 不能讓缺字串直接炸畫面，也不能讓使用者看到空白或半成品 | UI 缺字時可退回英文；若英文也缺，改顯示穩定的 placeholder 或技術提示 |
| 2026-04-29 | 上架通路優先順序為 `外部直下載 / GitHub Releases -> Microsoft Store -> Steam` | 先用最低摩擦驗證需求，再進入審核與費用較高的通路 | 商業化節奏會先偏向快速發佈與回饋收集，Steam 延後到需求與包裝更成熟時 |
| 2026-04-29 | Demo 限制先採功能限制，不做時間鎖；正式版先以單次買斷為預設 | 這樣最容易讓使用者快速理解差異，也不用先硬塞帳號或訂閱流程 | `CH-T5` 可以直接往素材與通路執行，不必再卡在方案模型上 |
| 2026-04-29 | HUD 舊 roster 規則退役，改由 `MissionCenter/tasks.md` 驅動 | 小人應該代表任務生命週期，不應再代表 active roster | 之後 HUD、同步器與 smoke test 都要以任務排序為主 |
| 2026-04-29 | `Blocked` / `Review` / `Done` 成為任務 HUD 的核心區域 | 要把流程卡點與完成狀態直接顯示在板上 | `Blocked` 代表下一步 smoke test，`Review` 代表下一步 review，`Done` 進休息區 |
| 2026-04-29 | HUD 改為任務驅動，來源改為 `MissionCenter/tasks.md` | 每個任務都要對應一個小人，並依任務生命週期顯示 | `command-center.html`、`sync_visual_state.py`、`watch_visual_state.py` 都要改成任務板規則 |
| 2026-04-29 | 背景監控器負責偵測來源檔變更並自動重跑同步 | 不想手動點 sync，HUD 要像活的一樣自己更新 | `watch_visual_state.py` 成為 MissionCenter 的常駐同步入口 |
| 2026-04-29 | CH-T1 / CH-T2 可收尾 | python -m py_compile 與 benchmark example 已通過 | 任務表可往 Done 推進 |
| 2026-04-29 | CH-T3 速度基準以 `benchmark_manifest.example.json` 為重跑基線，且輸出 `avg_timing_ms` / `p95_timing_ms` | 速度不能只看平均，要把尾端延遲也列進觀察 | 之後所有效能變更都能用同一份 manifest 比對平均值與 P95，避免只憑感覺判斷快慢 |
