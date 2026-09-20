# CH-T64：真正 Windows Sandbox 啟動驗收

## 摘要

主人同意啟用 Sandbox、禁止自動重開機；啟用回報 RestartNeeded=true，未自動重啟。主人重新開機後於 2026-09-20 繼續；唯讀確認宿主最近開機 19:20:16（台灣時間），目前程序為管理員且 WindowsSandbox.exe 存在。這更新先前「沒有乾淨 Windows 環境」的限制，不改寫歷史紀錄。

## 已完成與驗證

- 19:39:09～19:44:57，在新 Windows Sandbox 執行 guest probe，最終 status=passed／stage=complete。
- Guest：Windows 10 Enterprise x64，build 19041。python／python3／py／pip／conda／ollama 均無可解析命令；初始 LOCALAPPDATA/CloudHime 不存在。過程未安裝以上軟體。
- 唯讀分享已驗證 dist 與測試腳本；僅專屬結果目錄可寫。網路、vGPU、剪貼簿、麥克風、鏡頭及印表機轉送全部關閉，配置 8192 MB RAM；未映射原始碼、OWO.txt、API key、宿主 AppData 或模型。
- 發行檔先複製到 guest `C:\CloudHime` 再執行，不是使用宿主 Python 或在宿主跑隔離程序。
- EXE SHA-256 與 T35 固定版本一致：`3f32e40a332db9542d3278dadceb815051d6d0321565b11552d85e98a0c32d9c`。
- `test_clean_machine.ps1 -FunctionalSmoke` 搭配 `CLOUDHIME_PACKAGED_IMPORT_SMOKE=1` PASS，guest PID 1624；20 秒 launch liveness PASS，PID 1908；helper finally 完成本次程序樹及隔離 profile 清理後 probe 才回報通過。
- probe PowerShell 與 WSB XML 在宿主解析通過；未修改產品程式，也未重跑無關測試。

## 證據

`output/mission-center-evidence/sandbox-20260920/result.json` 是 guest 結果的結構化副本；同目錄保留 `probe.ps1`、`smoke.wsb`。原始執行檔案位於 `.tmp/sandbox-20260920/`；執行用 helper 為本 repo `packaging/test_clean_machine.ps1`，SHA-256 `1328ebc933c3f358a4ad8399d49feebfec4bb9ea3933ed43fa597912a1cc85ea`。重跑需按 WSB 位置準備 input helper 與 output 目錄。

設定方式依 Microsoft 文件：https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file 。

## 未完成與限制

- 只驗證乾淨 Windows 的 frozen import 與啟動存活；不代表渲染視覺、Windows OCR 實際辨識、模型首次下載／取消／Range 續傳、runtime handoff、推論或 GPU 通過。
- 沒有簽署、MSIX 安裝、WACK 或 Store submission。T64 仍為 Review，不建立 Done passport。
- Computer Use 技能的官方 sky 視窗擷取回報 `SetIsBorderRequired failed: 不支援此種介面 (0x80004002)`；重新選取視窗再試一次仍失敗。改用無截圖 accessibility 可讀外框，但只有 RDP Input Capture／Output Painter 與外框按鈕，沒有 guest 內部控制項；未盲點座標、未使用自製截圖／輸入替代協定。
- 後續 UI 下載／取消／續傳需要主人協助操作，或先修復電腦操作工具的視窗擷取相容性；本輪不擴大修改該工具。

## 清理與回顧

保存結果後，以精確 PID、父 PID、程序名稱與開始時間核對，只終止本次 WindowsSandboxClient／WindowsSandbox（20336／20928）；沒有終止其他 WSL 或 vmmem。Guest 測試工作階段已結束；宿主證據與發行產物保留。

停止 client 後 parent 自行退出，隨後 Stop-Process 回報 PID 20928 已不存在；唯讀複查兩個 owned PID 殘留數為 0，不重試終止其他程序。

將 bootstrap 與有網路／大型模型的 onboarding 分開，先證明未安裝 Python 的環境能啟動，再處理下載和推論，避免把啟動 PASS 擴張成完整產品驗收。
