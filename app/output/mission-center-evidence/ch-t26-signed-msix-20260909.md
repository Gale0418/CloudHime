# CH-T26 signed MSIX 實機驗證

- 日期：2026-09-09（Asia/Taipei）。
- 執行：Windows PowerShell 5.1，既有管理員 session；`output/signed-msix-gate.ps1`。
- 對 `dist/CloudHime-0.1.0.0-x64.msix` 的隔離副本建立一天有效的開發簽章，短暫信任於 LocalMachine TrustedPeople。
- SignTool SHA256 signing 與 `/pa /all` verification 成功。
- 既有 `packaging/test_msix_install.ps1` 成功安裝並透過 AUMID 啟動 `CloudHime_4nvnqyjwyamgj!CloudHime`，10 秒 liveness 通過，隨後卸載。
- 最終輸出：`CLEANUP package_count=0 stage_exists=False source_unchanged=True`、`RESULT=PASS`，程序 exit 0。
- 限制：此為目前 Windows 上的簽章、安裝、啟動及卸載驗證；尚未證明全新 Windows 的首次模型下載、續傳與 runtime handoff。CH-T26 維持 Review；未執行 WACK 或 Store certification。
