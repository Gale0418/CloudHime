# CH-T64 目前工作樹 fresh release build

- 2026-09-09 啟動官方 `build_exe.bat`，base commit `2214b6f0407691cde9e7a16cf10650c02a7f7dfa` 加上目前未提交變更；不是乾淨 commit build。
- Python 3.10.11 x64、PyInstaller／ddgs／lxml／primp／fake_useragent／certifi imports 通過；D: 可用空間約 312 GB。
- 真實 runtime --version：9968，commit 1d1d9a9ed；以此實測值傳入 LLAMA_RUNTIME_COMMIT，沒有捏造 archive provenance。
- 原有 dist/CloudHime 與 dist/CloudHime.zip 已使用 native PowerShell 移到 output/release-backup-20260909 保留；原有 MSIX 不動。來源／目的地已檢查位於專案內，舊產物不是 reparse point。
- 本次建置 handle 42851；啟動不等於成功，尚待終態及 fresh artifact verifier。9/6 WACK PASS 不套用到這次新產物。
- 同一 handle 後續進度：runtime-manifest.json 已產生，server version 9968／1d1d9a9ed、build CUDA／x64。fresh provenance venv hash-lock 安裝成功，pip check 顯示 No broken requirements，dependency contract ok: 54 components，release provenance stage ok。
- 已進入 PyInstaller 6.18.0 Analysis；尚未完成 EXE／ZIP／release preflight。工具另警告管理員執行 PyInstaller 將於 7.0 不再允許，這是目前非阻斷警告，不等於打包失敗。
- 後續同一 handle：PyInstaller EXE／COLLECT completed successfully；release provenance verify ok；release preflight Status=ready、391 files、1,585,172,607 bytes、0 model files。已進入 ZIP 階段，整支 build 尚待 exit code。
- 新 EXE 執行 `packaging/test_clean_machine.ps1 -ExecutablePath ./dist/CloudHime/CloudHime.exe -LaunchWaitSeconds 20`，exit 0，隔離 AppData／PATH 啟動存活 20 秒通過；測試 PID 22980 已回收。這不是乾淨 Windows VM／首次模型下載驗收。
- 本次 fresh provenance 暫存 venv 已確認不存在（清理完成）。
- 官方 build_exe.bat 最終輸出 `Done: dist\CloudHime.zip`，handle 42851 exit 0，完整 EXE／preflight／ZIP 建置成功。後續 MSIX 為另一獨立 gate，不沿用原套件 WACK PASS。
- 新 MSIX 封裝 handle 45761 exit 0，位於 output/msix-fresh-20260909/package/CloudHime-0.1.0.0-x64.msix，原有 dist MSIX 未覆寫。
- 對此新 MSIX 執行隔離副本開發簽章／安裝啟動／WACK。原工具呼叫被使用者中斷，但權威 process 狀態確認仍執行，因此未重啟；appcert 45828 經 aitstatic 與 TE 後完成。
- 新報告 output/wack-b7f5ca8271d943159d0a15bf2bb5fd45.xml，唯一 /REPORT/@OVERALL_RESULT=PASS。這是新套件的實測，不是 9/6 artifact 報告。
- 事後 gate 44776、appcert 45828、TE 28216 均不存在；兩個 cert store 的 CloudHime ephemeral smoke 憑證合計 0，隔離簽章 staging 不存在。原 exec 被中斷故無可回收的 shell exit code，不捏造 exit 0；完成判定取自實際 XML 與清理檢查。
- 仍未完成 Partner Center 認證、正式 Store identity／提交、乾淨 Windows 首次模型下載與人工 holdout；T64 維持 In Progress。
