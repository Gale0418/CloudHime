# CH-T112：獨立嚴格審查提詞

> 不要相信前一輪結論，重新從正確性、回歸風險、效能、安全、資源使用與可維護性挑毛病，按照Mission Center標出待修優先度，只有真的沒有值得修的 P2 以上問題才准通過。

你必須是沒有參與本次實作的獨立審查者；實作者的分析、模擬角色及單元測試不算獨立審查。
讀取目前 main、`MissionCenter/tasks.md`、這次 closeout 與實際 diff。舊報告只是待查主張。

檢查重點：

1. Rust 1.98.1 真實編譯、fmt、Clippy、Rust tests 與 Python/native 差異測試；未執行不得算通過。
2. FFI 指標生命週期、immutable snapshots、通道分組、長度／輸出界限、ABI／DLL 搜尋面。
3. Python bool、複數、uint64、非連續陣列、空軸、呼叫者修改原圖、並發；`skip_ocr` 永遠 False。
4. Qt 測試保護在跨測試延遲 callback 中仍有效，純核心測試不偷偷載入 GUI。
5. 外部 corpus 的 skip 僅限具名測試；`--require-external-corpora` 必須 fail closed，資料缺失不能算品質證據。
6. benchmark lock 的 bytes 不被改寫；Windows checkout 不得因 CRLF 偽造 drift。
7. dependency/MSIX tooling 使用已安裝依賴的 Python；不得刪除既有 release 閘門或放寬 hash 驗證。
8. 重新檢查 CH-T115 的 337px overflow、CH-T114 argv credential 與完整 Windows inventory，不能忽略既有 P2+。

每個 issue 輸出：P0/P1/P2/P3、對應既有 Mission Center task、檔案／行號、重現、影響、最小修復、驗證命令。
修復後重新讀最新 diff 並重跑受影響測試。只有沒有值得修的 P0/P1/P2，且必需的驗證沒有缺口，才回覆 PASS。
缺少平台、工具鏈或獨立執行權限，回覆 BLOCKED 並列出缺口；不得降級成「零 issues」。

禁止觸發 GitHub Actions、使用付費 API、讀取或外傳使用者金鑰，以及新增遠端分支。
