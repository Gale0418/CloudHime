# 專案

- 專案：CloudHime 設定面板視覺大改造
- 日期：2026-04-29
- 目標：把目前的設定頁改成接近 image2 mockup 的漂亮商業化面板，並維持既有翻譯、OCR、渲染、語言切換與設定儲存功能。
- 負責：Owner / Codex
- 優先級：P0
- 狀態：Done

## 成功標準

- 設定頁採用寬版三欄：Translation、OCR、Rendering。
- Header 顯示 CloudHime 品牌、頁面副標、關閉按鈕。
- 顏色模式與 UI 語言以下拉 chip 放在 header 下方。
- OCR backend、Google OCR、滑鼠穿透、自動掃描、閥值刷新集中在 OCR 欄。
- Translation 欄保留 Google / Gemma AI、API key、模型、prompt 控制。
- Rendering 欄保留 Bubble / Relief / Screenshot、截圖提示詞、浮離細節控制。
- 英文與繁中切換後主要可見文字都正確。
- PySide6 smoke test 可建立視窗並檢查主要控制項。

## 非目標

- 不重寫翻譯/OCR 核心邏輯。
- 不新增第三語言。
- 不改 MissionCenter HUD 規則，只更新任務內容。

## 主要風險

- PySide6 固定尺寸過小導致三欄擠壓。
- 重排 widget 時破壞既有 signal 或 controller 同步。
- Translation panel 的 AI 進階區展開後高度不夠。
- 雙語切換只切到部分文字。
