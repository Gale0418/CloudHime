# 2026-10-02 原生 Windows 與新套件驗收

任務：CH-T117。主人授權使用 Computer Use 驗收；既有 Store 0.1.1.0 的 CH-T55 與正式發行閘門仍分開追蹤。

## 已確認問題與修復

Python 3.10.11、PySide6 6.10.1、Windows 平台、隔離的空白使用者設定啟動時，程式在主窗建立前退出，exit code 1。`SelectionOverlay` 設為全螢幕會同步觸發 `resizeEvent`，此時 `selection_hint` 尚未建立，拋出 `AttributeError`。先前 offscreen 測試沒有覆蓋這個原生事件順序。

最小修復：先建立選取狀態與提示標籤，再設定視窗 flags、透明屬性與全螢幕狀態。新增同步 resize 回歸，修復前 1 failed，修復後通過；維持提示位置、父物件與初始隱藏狀態。

## 原生操作與證據邊界

使用 Computer Use 的 `@oai/sky`，以實際列出的 CloudHime 視窗操作；隔離 APPDATA／LOCALAPPDATA，未讀取個人設定或金鑰，未送出真實雲端翻譯。

| 驗收項目 | 觀察 | 結果 |
| --- | --- | --- |
| 原生 Python 3.10 啟動 | 主窗建立、Windows OCR backend 可用、快捷鍵註冊，約 3.7 秒出現主窗 | 通過 |
| 開啟設定 | `Ctrl+,` 後程序視窗標題變為 Settings | 通過開啟行為；未驗證內容與外觀 |
| 關閉設定 | `Esc` 後恢復主窗與可讀控制項 | 通過 |
| 結束程式 | `Alt+F4` 後本次程序退出、日誌記錄解除快捷鍵 | 通過 |
| 新 EXE 開啟／關閉設定與退出 | frozen EXE 可用 `Ctrl+,` 開 Settings、`Esc` 回主窗、`Alt+F4` 退出 | 通過開關行為；內容與外觀未驗 |
| 新 EXE 設定寫出與重啟 | 空白隔離設定在退出後寫出；重啟可讀主窗，再退出前後設定 SHA-256 相同 | 通過正常寫出／重啟；未驗證手動修改設定 |
| 主窗控制項 | accessibility 可讀 Settings、Full Screen、Region、Translate Now、Auto Scan、間隔及停止按鈕 | 通過存在性；不等同視覺驗收 |
| 截圖與滑鼠操作 | capture 回報 `FrameArrived timed out`／`window capture timed out`；刷新目標後仍失敗，點擊回報 `coordinate input geometry is unavailable` | 工具受阻 |
| 可見 pythonw 對照 | 改以可見視窗啟動後，accessibility 仍可讀，capture 仍逾時 | 未解除工具限制 |
| 框選／取消、立即翻譯、自動掃描／停止、設定存檔重啟 | 原生滑鼠操作與設定子視窗讀取受阻 | 尚未完成實機流程驗收 |

本輪沒有把模擬測試、文字控制項或鍵盤開窗視為外觀通過。Store 套件直接執行回報存取被拒，未修改權限、未繞過套件啟動限制；不改寫既有 Store 驗收紀錄。

## 自動驗證與 CodeRabbit

本機 Python 3.13.11、PySide6 6.10.1、offscreen：產品互動測試 36 passed；UI smoke 與 OCR worker mode matrix 188 passed，共 **224 個不同案例通過**。產品測試有 pytest cache 寫入權限警告，不宣稱零警告或完整 Python 3.13 相容。語法與差異檢查通過。

CodeRabbit CLI 0.7.6 已登入，20:00 後本小時第一輪，`review --agent -t uncommitted -c .coderabbit.yaml` 完成，**CodeRabbit raised 0 issues.** 實際 `reviewedFiles` **135 檔**，沒有 error event；未超過每次 150 檔。

Windows Git 僅兩個實作／測試檔有內容差異；WSL Git 未繼承 Windows 的 `core.autocrlf=true`，回報 135 檔差異，因此服務範圍擴大。唯讀對照啟用 autocrlf 後縮為五檔，換行設定能解釋大部分範圍擴大，剩餘三個既有 benchmark JSON 差異未在本輪調查或修改。記錄服務實際範圍，不把這次描述為兩檔審查；未為縮小計數重跑審查。先前 148 檔歷史補審及 20 檔複審保留原始紀錄。

原始測試、啟動與 CodeRabbit NDJSON：`output/acceptance-ui-20261002/`；建置資料：`output/acceptance-20261002-194531/`。這些忽略目錄不推送 GitHub。

## 新套件與未完成項

新 Python 3.10 light 預覽套件已完成：PyInstaller 6.18.0 exit 0；PySide6 6.10.1、NumPy 2.2.6。EXE 路徑為 `output/acceptance-20261002-194531/dist/CloudHime/CloudHime.exe`，SHA-256 `2cfd06b6029eb62c010f10250339ae11a44d435f7ccf3ac32486463c751d975d`。請保留完整 CloudHime 資料夾，不能只複製 EXE。

`verify_release_dist.ps1 -ModelBundle light` 回報 ready，366 檔、1,554,009,653 bytes、ModelFiles 0；frozen import smoke exit 0。Runtime manifest 核對 26 檔，server 回報版本 9968、build ID `1d1d9a9ed`；未提供 runtime source archive metadata，不宣稱完整 runtime 來源封存證據。

輸入為 main `816613bb1de5f80866845c135b9e16d336dfe5a2` 加本次啟動修復，不能宣稱是該乾淨提交的產物。建置前後來源雜湊一致：`cloudhime_ui.py` SHA-256 `809c741ecafcaacc6a7aed9d4ce5e2de9b588c561b3212a4c0405750a610bdf3`；`tests/test_product_experience.py` SHA-256 `16856e7bad6e7e8fdaf4dabf085b4a9609438eb48ea8efbf1a5fbc6597d09967`。

從新 EXE 執行 `CLOUDHIME_PACKAGED_FUNCTIONAL_SMOKE=1`：使用合成公開英文文字圖與已存在的公開 Gemma 模型，CPU 模式 **1 image／1 case／1 successful request**，status passed、exit 0。只保存計數與狀態，未保存模型輸出；不替代翻譯品質評分、完整 UI 或乾淨機驗證。本次 GUI 程序皆已退出，該新 runtime 路徑下存活的 llama-server 為 0。

啟動日誌仍有 optional opencc 未安裝訊息，不宣稱零警告。本輪未改動既有依賴政策，也未建立／安裝新 MSIX 或上傳新 Release 資產。

## main 與 CI 對帳

修復及 README／任務紀錄已直接提交 main [`7c93c15`](https://github.com/Gale0418/CloudHime/commit/7c93c153d345483ae489aae5a5c6dd07ba9abf48)，推送後本地／遠端 SHA 相同，工作目錄乾淨。該提交的 [GitHub CI](https://github.com/Gale0418/CloudHime/actions/runs/37005380465) 為 completed／success：八個必需工作成功，兩個 real frozen release 工作 skipped。本機新 EXE 驗證有獨立證據，未用 skipped CI 代替。

本段與任務中心對帳為後續純文件提交，使用 `[skip ci]`；程式码 CI 證據對應上述來源提交。

CH-T117 保留 Review。正式 critic_full 尚未 dispatch，缺 total／per-seat／tool／wall-clock 明確預算授權；CodeRabbit 與本輪驗收不替代正式評議。未完成的外觀、完整原生流程、新 MSIX／Store、乾淨機與 live API 驗證均不宣稱通過。
