# CloudHime 互動樂趣驗收（2026-10-02）

本次主題為「像拿放大鏡：框到就知道、失手能退一步」。樂趣來自可預期的操作回饋與可恢復的失手，延續天宮書房的小主窗及原生 Qt 控制。

## 交付行為

- 框選期間顯示三語系操作提示、目前尺寸與過小範圍提醒，使用十字游標；提示不攔截滑鼠，輔助功能名稱包含完整提示文字。
- 按 Esc 或拖出不足最小範圍時，保留原本的全螢幕／區域模式與已選範圍，並恢復對應選取按鈕與區域框。成功框選仍使用原本的 QRect 幾何及 20×20 最小判定。
- 重新框選仍停止現有掃描，成功或取消皆不自行重啟；使用者以原有立即翻譯／自動掃描動作繼續。
- 自動掃描按鈕顯示下次掃描倒數及翻譯中；秒數從既有 QTimer 的 remainingTime 向上取整，沿用原排程與更新計時器，不新增背景循環。
- 自動掃描忙碌時，立即翻譯及快捷按鈕同步停用並顯示翻譯中；完成後恢復。倒數及忙碌回饋只更新操作按鈕，不覆寫工作狀態或錯誤。

本輪不更動 OCR、模型請求、快取、框選幾何、透明度、排程算法及秘密儲存。

## 驗證證據

Windows、Python 3.13.11、PySide6 6.10.1、Qt offscreen。測試及擷取隔離設定寫入、秘密讀取、原生快捷鍵；不呼叫真實 OCR／翻譯 API 或模型推論。測試後與預覽完成後清理本次 Controller 工作執行緒。

以獨立程序分批執行以下指定測試，合計 **150 個不同案例通過**：

```text
python -m pytest -q tests/test_product_experience.py -k 'reselection or first_selection or selection_feedback or auto_scan_feedback' --disable-warnings --maxfail=2
11 passed, 22 deselected, 1 warning in 4.33s

python -m pytest -q tests/test_product_experience.py -k 'cooldown or completion or auto_scan_accepts or language_switch or requests or dark_window_icons' --disable-warnings --maxfail=2
11 passed, 22 deselected, 1 warning in 2.05s

python -m pytest -q tests/test_product_experience.py -k 'abandoned or unconfigured or settings_fit or native_close' --disable-warnings --maxfail=2
11 passed, 22 deselected, 1 warning in 8.81s

python -m pytest -q tests/test_cloudhime_ui_smoke.py tests/test_translation_panel_advanced.py tests/test_settings_window_theme_polish.py --disable-warnings --maxfail=2
117 passed, 1 warning in 17.21s
```

新增 11 案例涵蓋：原模式下 Esc／過小框選保留範圍、首次取消、三語系反向拖曳及尺寸一致、真實倒數、錯誤保留、忙碌停用與完成恢復。產品體驗檔的三個子集互不重疊，合計覆蓋該檔 33 案例。

一次四檔合併執行曾在建立 OCRWorker 時發生 Windows 原生 access violation，未完成，不能列為通過。此環境先前也記錄過 Python 3.13／PySide6 原生相容性問題；本輪沒有證明崩潰原因，也不宣稱問題已解決。分批驗證只證明上述操作契約，正式支援的 Python 3.10 CI 仍需另跑。

## 版面確認

`.tmp/preview_delight.py` 產生 `output/delight-20261002/` 的 45 張 Qt 擷取，包含三主題、三語系、框選前／拖曳中／取消及自動等待／忙碌狀態。已檢視中文框選、英文深色框選、高對比日文提示、英文忙碌與中文取消；第一輪發現忙碌時立即翻譯仍顯示可操作，修正後僅再做一次確認，英文忙碌與高對比日文倒數未裁切。

擷取是 offscreen UI 證據，沒有實機高 DPI、多螢幕、螢幕閱讀器或全螢幕遊戲驗證。提示在框選時可見，框選結束即隨選取視窗隱藏，不進入擷取／推論流程。

## 發行邊界

本輪交付原始碼及說明，尚未重建 `dist` 或安裝包。完整測試、Python 3.10 CI、乾淨機器及 Store 發行檢查未執行；既有套件及其他輪次的成功紀錄不沿用為本次發行證據。
