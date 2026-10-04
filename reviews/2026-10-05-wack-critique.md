# WACK 發行檢查與獨立評論 · 2026-10-05

CH-T55 維持 Review。產品候選仍為 fe88bab／EXE SHA-256 cbbcf0b8f755057115888caa3058b889429692a1092026facda1ef9cb694e842；本輪未改產品程式或重建產品。Store 未上傳或提交認證。WACK helper 修正已提交並同步 main：1e94a8944f5e8cf8853f6e4c2fc0d463ea3edb91；GitHub CI run 37242636061 completed／success，兩項 opt-in frozen job skipped，不算通過。

發行 helper 的最小修正：`packaging/test_wack.ps1` 現在要求報告明確包含 `PARTIAL_RUN=FALSE`。原 wrapper 只要求 OVERALL_RESULT=PASS，會接受部分執行、缺少完成欄位或未知完成欄位的報告。五個執行實際 PowerShell validation 區塊的反例先得到 3 failed／2 passed；修正後相關 WACK 回歸 11 passed。另跑既有跑馬燈五案，5 passed。沒有重跑完整 inventory；首個 Python 入口缺 pytest 後改用已驗證的既有 test venv，未安裝新依賴。

CodeRabbit 0.7.6 已登入，本輪一次實際審查、兩檔，complete event 0 issues，CLI exit 0。獨立 review projection 僅含上述 helper 與 tests/test_msix_packaging.py；未傳送產品、模型、個人設定、憑證、dump 或原有未追蹤 logo。scope SHA、原始 NDJSON 與 receipt 見 `output/wack-diagnosis-20261005/`。

已使用主人先前核准的 CH-T55 評論額度（總量 24k、三席與獨立仲裁各 4k、整合 8k、各席八次工具／合計 32、30 分鐘）。三名 Luna 初評互相盲評，再由另一名 Luna 仲裁；四席均已回覆。API 未提供精確各席 token 使用量，因此不宣稱已由可計量數據證明 token 額度遵守。三席原始觀察的主持轉錄、反證 manifest 與仲裁均保存；不是來源測試或 smoke 的替代證據。

仲裁結果 `limited`：原生完整操作旅程、真實設定升級、完整 WACK、Partner Center 認證與實際 Store 更新仍未知。靜態截圖的「永久截斷」主張由實際 MarqueeLabel 捲動、完整 tooltip／accessible name 與五案回歸反證；「~」是有 tooltip 與名稱的快捷鍵顯示，原生焦點／讀屏仍未驗收。最初評論包漏附模型個別雜湊與來源收據，已補上 pinned revision／來源 URL／兩個固定 SHA 與 full verifier 收據；不能將證據包漏附當成模型實際沒有來源。WACK 沒報告是認證覆蓋未知，沒有證據定為 High 產品故障。沒有再開無限制找碴輪次。

`output/mission-center-critique/CH-T55-20261005-initial.json` 已由安裝的 Rust `mission-center critic --record` 驗證 valid=true。初次紀錄契約錯誤經具體回報修正；原命令執行歷程保留。正式包沒有 `scripts/critic_contract.py`，使用原生契約驗證，不安裝 Python fallback。驗證結構有效不代表結果 passed，未生成假的最終 closure。pulse CLI 本輪回報 argument_error，未聲稱已更新 ledger；以 canonical tasks.md 與本 checkpoint 接續。

WACK 工具探針使用斷網、獨立 Windows Sandbox，未掛產品包。修正探針程序 exit code 擷取及原生 CP950 輸出解碼後，reset／querytestids exit 0；help／刻意缺檔 exit -1、沒有本輪 appcert CLR 事件。SDK registry 不存在但這些命令仍能執行，不能把缺 SDK registry 宣稱為既有 CLR 崩潰的確定根因。第一輪 null exitCode 收據保留、不當成功證據。程序回收第一個守衛因 JSON datetime 轉換拒絕，改以原始 RFC3339 與實際 StartTime 比對後才精確回收本輪 sandbox。

Microsoft [WACK CLI 文件](https://learn.microsoft.com/en-us/windows/uwp/debug-test-perf/windows-app-certification-kit) 及已安裝 appcert help 已核對。單項資訊清單探針首次誤用 `-testid 31`，CLI 回報格式錯誤、exit -1、無報告；實際尚未開始測試。已改為 help 指定的 `-testid [31]`，另一次 guest 副本診斷保留 stdout、stderr、時間窗內事件及報告。此項只是隔離診斷，不作完整認證 PASS。原 Sandbox 的 0xE0434352 無報告反證仍保留。

修正格式後的 guest 已完成來源雜湊、副本簽署與 reset exit0，22:47:27Z 進入資訊清單測試；超過 300 秒階段上限後仍無最終 guest receipt、stdout、stderr 或 XML。已保留 `manifest-last-observation.json`，依實際 PID／路徑／父程序／原始 RFC3339 StartTime 核對後回收本輪 client／launcher。這是診斷未完成，不是產品失敗、工具 CLR 根因或認證 PASS；guest 最終憑證清理收據不存在，短效非匯出憑證／key 與副本隨一次性 VM 銷毀，host 安裝未動。詳見 `package-disposal2.json`。

本地 ignored 診斷 helper 的輸出 drain 原先沒有上限，可能拖住 final receipt；尚未有 guest 程序證據確認本次正是此原因。已將未來 helper 改成先保存 exit／timeout 事實，stdout／stderr 各最多五秒 drain；本輪未重跑修正版，不宣稱此 harness 改善已通過。沒有重複送出相同原始測試或把不存在的 exit code 補成成功。下一次應使用有正式 SDK／WACK 安裝的隔離 VM，或先驗證有上限的診斷收據流程，再取得完整 WACK 報告；產品完整人工操作與 Microsoft 認證仍待驗收。

追加正式 SDK 診斷：Microsoft 簽署的 10.1.26100.8876 bootstrap 離線 layout 成功；44 檔雜湊在 Windows PowerShell 5.1 核對。隔離、斷網 guest 正式安裝 WACK／SigningTools exit 0，SDK registry 與 WACK 10.0.26100.8876 可見；這只證明測試環境安裝成功。第一次安裝前的 JSON 列舉錯誤已修；第二次 guest 在候選本機副本 hash 核對後，最小 SigningTools 回報 MSIX 格式無法辨識、exit 1，尚未進入 WACK。已清理該 guest；第三次沿用原成功簽章的 Microsoft 完整 x64 工具目錄，逐檔 SHA 核對，WACK 仍使用正式安裝版，結果另記。探針的 stdout／stderr drain 與所有程序等待均有期限；實際 Windows PS5.1 自測涵蓋 exit 7、逾時回收、子程序持有 pipe 三種情況。

原生介面追加：Computer Use 的路徑啟動先解析到既有 Store 0.1.1.0，已正常關閉，不算候選測試。後以固定完整路徑啟動候選，實際 PID／ExecutablePath 已核對；原生可存取性樹可讀到完整 Google 傳送提示、框選／快捷鍵／自動掃描／停止及清字幕名稱。畫面擷取兩種逾時，click 回報 coordinate input geometry is unavailable；停止這條無新證據的重試。Alt+F4 正常退出候選。可讀元件名稱不能替代完整 OCR／翻譯／暫停／設定與升級旅程。證據與正式 SDK 探針收據位於 output/wack-sdk-20261005/。

正式安裝 SDK 的第三次 guest：完整 x64 SigningTools 雜湊核對後 sign exit 0／60.4 秒、reset exit 0／1.9 秒，完整 WACK 於 2026-10-04T23:23:28Z 開始。原始 CP950 stdout 顯示 Centennial 類型偵測成功，正在擷取套件；所有測試結果尚待實際結束碼與完整 XML。最小 SigningTools 與完整工具鏈的差異已觀察到，但未逐一隔離 DLL，因此不宣稱某一 DLL 是確定根因。

完整 WACK 最終結果：779768 ms，exit 0，stdout／stderr drained，report SHA-256 9e37742410fd834536c1800654a9cab8d09ef135fc288fb677090801d7aca390。XML 的 OVERALL_RESULT=PASS、PARTIAL_RUN=FALSE；APP_NAME WindSheep.CloudHime、APP_VERSION 0.1.2.0、APP_TYPE Centennial、WACK 10.0.26100.8876、guest Windows 10 Enterprise 19041。24 個 TEST 中 13 required PASS、10 optional PASS、1 optional FAIL。

INDEX 88 blocked executables 包含 Python／Qt／llama 已封裝元件的 CreateProcess／ShellExecute API 參照，以及 Microsoft.Windows.SoftwareLogo.Shared.TextByteReader.ReadToEnd 的 System.OverflowException（Array dimensions exceeded supported range）；報告未指出觸發例外的檔案，不將特定模型或記憶體不足猜成確定原因。Microsoft [Desktop Bridge 測試文件](https://learn.microsoft.com/en-us/windows/uwp/debug-test-perf/windows-desktop-bridge-app-tests) 明確以 required 測試決定 Store onboarding；optional 屬資訊性，仍建議調查。因此本輪完整 WACK 總判定通過，不能宣稱所有測項通過或 S 模式相容。沒有刪模型、停用測項或重建產品；本機 WACK 不代表 Partner Center 已認證。

guest remainingPackages=0、cleanupErrors=[]，Application 1026／1000／1001 事件輸出空；exact launcher 43664／client 13676 經路徑、StartTime、ParentPID 查核後清理，host 確認兩 PID 不存在。host Store 保持 0.1.1.0，未上傳。CH-T55 維持 Review／Smoke NO／Critic NO，後續仍需完整 GUI／真實設定升級及私人預覽認證；四席歷史 limited 裁定不改寫為 passed。本段新證據優先於前段與舊 ledger 的歷史待驗描述。
