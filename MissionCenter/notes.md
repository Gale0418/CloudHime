# Notes

## 目前觀察

- `CloudHime.py` 的 `subtext` 設定窗 bug 已修。
- `ocr_benchmark.py` 已能跑 `benchmark_manifest.example.json`，而且會顯示 `category/source/note/timing_ms`。
- `build_exe.bat` 與 `README.md` 已整理成較接近對外版本。
- 目前對外策略可以先視為「繁中優先、英文 fallback」，避免在 demo 與上架文案上臨時改方向。
- MissionCenter HUD 現在改吃 `tasks.md`，任務短標題會變成小人名稱，前 10 個非 `Done` 會先上場。
- `watch_visual_state.py` 會盯著 `project.md`、`progress.md`、`tasks.md`，變更就自動跑同步。
- `Done` 會待在休息區，總可見超過 15 時，最早完成的 `Done` 先退場。
- 多語 UI smoke test 已完成，`English / 繁中` 下拉能同步主視窗與翻譯目標。

## 待補

- 更完整的 OCR / 翻譯代表測試集。
- 乾淨 Windows 機驗證。
- 各通路素材要分開整理：GitHub Releases 的下載說明、Microsoft Store 的商店描述、Steam 的頁面文案。

## 商業化清單

- Demo：功能限制，不做時間鎖。
- 定價：先以單次買斷為預設，之後再看回饋調整。
- 通路：外部直下載 / GitHub Releases -> Microsoft Store -> Steam。
- 素材：截圖、短影片、功能清單、FAQ、隱私說明。
- 語言：`zh-TW` 預設，`en` fallback。

## 進度更新
- CH-T1 已以 python -m py_compile 與現有程式碼狀態確認可收尾
- CH-T2 已以 python ocr_benchmark.py .\\benchmark_manifest.example.json 驗證通過
- CH-T3 已補上 avg / P95 基準與快取、連掃 smoke tests
- MissionCenter HUD 已改成任務驅動，並以 `tasks.md` 生成任務小人、休息區與溢出退場
- 商業化、多語策略與任務 HUD 規則已同步寫入 project / decisions / notes 三份核心文件，之後可直接接著拆 UI 與發佈任務
