# CH-T64：乾淨 Windows 驗收交接

## 最新進度（2026-09-20 19:45）

主人已授權啟用 Windows Sandbox 並自行重開機；真正 Sandbox 的 frozen import 與 20 秒啟動已通過，無 Python／pip／Conda／Ollama 命令，沒有既有 CloudHime profile。詳見 `2026-09-20-sandbox-bootstrap.md`。模型首次下載／取消／續傳／handoff 仍未完成；Computer Use 擷取介面不相容，UI 步驟需要人工協助或另行修復工具。以下是啟用前的歷史邊界，不再代表目前沒有 Sandbox。

## 歷史邊界

2026-09-20 主人確認沒有可用的乾淨 Windows 電腦／VM。本機未發現 Windows Sandbox 執行檔或 Hyper-V PowerShell 模組，執行環境不是管理員。未啟用系統功能、未要求重開機、未把環境隔離測試當作乾淨 Windows 驗收。

`packaging/test_clean_machine.ps1` 可清空子程序環境、限定系統 PATH，並使用新的 AppData／TEMP；但仍共用宿主作業系統、驅動、登錄與已安裝系統元件，因此只能提供宿主環境隔離證據。`FunctionalSmoke` 的通過項目取決於注入的 smoke flag，import smoke 並不等於模型推論完成。

## 未來可執行的驗收

1. 準備受支援的全新 Windows VM 或測試電腦，記錄 OS build、架構、GPU／驅動及是否為標準使用者；確認未安裝 Python、pip、Conda、Ollama。不要重設主人目前的工作電腦。
2. 使用本輪最終發行包及其 SHA-256；記錄來源 commit。不要用另一版 EXE 替代同一份 artifact 的測試。
3. 解壓 ZIP，直接啟動 CloudHime；記錄是否需要額外系統元件。不要為了讓測試通過先安裝 Python。
4. 在 UI 首次下載受管模型；下載中取消，確認部分檔保留，重新啟動下載確認續傳，再確認完整性檢查成功。
5. 選取正常向測試畫面執行一次正式翻譯，確認模型 runtime handoff、非空結果及關閉後本次子程序清理。若 VM 無 GPU，明確記錄 CPU 路徑；不能宣稱 GPU 驗收。
6. 記錄程式版本、artifact hash、步驟、預期、實際結果及失敗訊息；遮蔽 API key 和私人畫面。未執行部分標示「未執行」，不要沿用舊版結果。

## 獨立的發布閘門

- 上述 ZIP 驗收不替代 signed-MSIX 安裝／啟動／卸載，也不替代新 artifact 的 WACK。
- 舊版 2026-09-09 WACK PASS 只對應當時套件。
- Store 產品建立與送審仍依主人先前延後決定；本輪沒有建立產品或提交 certification。
- 現階段不購入雲端 VM、不增加付費服務、不啟用本機虛擬化。

## 下一步

先完成新 EXE 的本機環境隔離驗證；保留 CH-T64 Review。未來有乾淨 Windows 環境後執行以上步驟，不以重跑單元測試消除環境缺口。
