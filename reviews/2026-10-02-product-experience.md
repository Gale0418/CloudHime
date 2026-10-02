# CloudHime 產品體驗驗收（2026-10-02）

本次延續「天宮書房」視覺，改善主窗、設定退出、掃描狀態與生命週期。變更已在原始碼；既有 `dist` 尚未重建，不宣稱本次變更通過 Store 或乾淨機器驗證。

## 交付行為

- 主窗使用一致的紫色選取及主要動作，加入操作提示、可見鍵盤焦點、三語系說明與不依賴字型的視窗圖示。
- 冷卻只更新按鈕，不覆寫進度、錯誤或完成訊息；冷卻結束後仍忙碌時繼續停用按鈕，完成後恢復。停止立即解除冷卻。
- 掃描忙碌時拒絕重複手動／排程請求，維持現有世代取消及過期結果防護。自動掃描不再依繁中文字串過濾工作狀態。
- 關閉尚未填好金鑰的新引擎設定時清除待設定選擇，保留原本的實際路線；儲存未設定完的引擎會停留在金鑰頁。
- 「關閉」及設定說明反映既有的即時套用／自動儲存行為，作品名稱仍需按「儲存」啟用。
- 設定窗依主窗所在螢幕可用範圍置中，支援 760×520；寬度小於 980 時收起插畫。底部操作保留，內容可捲動。
- 原生關閉主窗會走既有清理流程；秘密或一般設定儲存失敗會阻止退出並保留工作執行緒，避免無聲遺失資料。
- 主窗：Esc 停止、Ctrl+, 設定。設定窗：Esc 關閉、Ctrl+S 儲存；均受視窗焦點限制。

## 驗證證據

環境為 Windows、Python 3.13.11、PySide6 6.10.1、Qt offscreen。沒有呼叫真實翻譯服務或模型推論；新增測試與畫面擷取隔離秘密讀取及設定寫入。

一次相關回歸合併執行：

```text
python -m pytest -q tests/test_product_experience.py tests/test_cloudhime_ui_smoke.py tests/test_translation_panel_advanced.py tests/test_settings_window_theme_polish.py tests/test_relief_settings.py tests/test_settings_store.py tests/test_provider_health.py --disable-warnings --maxfail=3
187 passed, 1 warning in 30.76s
```

最後追加深色圖示的 CSS rgba 像素檢查，及測試清理／圖示修正後重跑新測試檔：

```text
python -m pytest -q tests/test_product_experience.py --disable-warnings --maxfail=1
21 passed, 1 warning in 13.05s
```

Luna 獨立驗收提出一般設定存檔失敗仍會關閉的 P2；已補上保護及回歸測試，最後執行：

```text
python -m pytest -q tests/test_product_experience.py tests/test_cloudhime_ui_smoke.py --disable-warnings --maxfail=1
83 passed, 1 warning in 19.20s
```

相關範圍共有 189 個不同測試分批通過。驗證及預覽程序均已結束，控制器的 OCR／模型探索執行緒經清理；沒有清理使用者其他 Python 程序。

`git diff --check` 通過。以上是相關測試，沒有執行全部測試，也不能視為既有 Python 3.13 原生相容性問題已解決；正式支援的 Python 3.10 CI 尚需對本次版本另跑。

畫面產物位於 gitignored 的 `output/product-experience-20261002/`，由 `.tmp/preview_product_experience.py` 產生 36 張 Qt 擷取：三主題、三語系主窗、四個設定分頁、小尺寸桌面與缺少金鑰狀態。已檢視主窗總覽、三主題主窗、設定首頁及小尺寸英文設定／金鑰頁；最後深色圖示 rgba 修正以像素測試確認，不另開視覺微調迴圈。這些是 offscreen 版面證據，不是實機高 DPI、螢幕讀取器或全螢幕遊戲測試。

## 發行邊界

發行前仍需以本次原始碼重新建置並驗證正式 Python 3.10 套件、乾淨機器安裝／啟動／卸載與真實 OCR／翻譯流程，並依既有 packaging 流程處理 Store identity、簽章及 Partner Center 認證。歷史套件曾有獨立驗證證據；本次沒有把它沿用為新版本的發行通過紀錄。
