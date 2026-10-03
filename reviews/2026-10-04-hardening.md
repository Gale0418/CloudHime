# 2026-10-04 CloudHime 程式檢查與修復

本輪修復已完成來源驗證，正式多專家評議為 **limited**，CH-T117 保留 Review。這份紀錄不代表新的 frozen EXE、Store 套件或上架驗收通過。

## 已修復

- Google HTML 翻譯使用獨立 transport：連線／讀取逾時 5／20 秒、HTML 1 MiB 上限、讀取時檢查 30 秒經過時間；成功、429、HTTP 錯誤、讀取例外都釋放 response。這不是 DNS／整次請求的絕對 30 秒截止時間。純標點原文相同時回傳文字，避免落成 None；保留原重試與例外類型。三條既有 Google 路徑改用 adapter，MIT 改作署名已加入第三方聲明。
- 共享本地模型的租約 release，在同一把鎖內檢查與標記，避免同一租約並行釋放兩次而提早關掉別人的模型。
- 持久翻譯快取限制單筆 64 KiB、總量 2 MiB、載入 4 MiB。以 compact UTF-8 和逐筆編碼資料計算容量；淘汰不反覆序列化整份資料，並保留更新後的 LRU 落盤／重載順序。schema、原子替換與失敗時不中斷翻譯的行為維持。
- 關閉先拒絕新掃描、取消舊 generation，再等待 OCR 結束，於背景釋放 provider／模型；遠端查詢完成也是關閉門檻。保留 Qt 執行緒生命週期、忽略過期字幕、顯示三語等待提示並停用操作。儲存失敗的退出否決不改變原介面狀態。
- 新測試已納入 CI 清單。保留使用者確認正常的翻譯流程與純雲朵圖示。

## 驗證

隔離 Python 3.10.11、PySide6 6.10.1；pytest 套件依 CI hash lock 安裝。來源測試清單共 1,629 案：**1,623 通過、6 跳過、0 失敗／錯誤**；另排除 1 項本機既有 frozen 套件 preflight，原檢查超過 300 秒上限。逾時證據保留，僅回收本次啟動的兩個 preflight helper，不更動舊套件。跳過與排除都不算通過。

成功與雙 provider 失敗的受控 harness 實際執行 Worker → Controller → Qt QLabel／paint；分別顯示「你好／translation complete」與原文 Hello／限流原因。失敗時持久快取 lookup miss、remember 0、檔案未建立。OCR／provider 是 mock，非 live Google、實體桌面點擊或新版 EXE。關閉測試另驗證阻塞 OCR／遠端 slot、慢清理時 GUI 心跳、重複關閉及過期結果。

CodeRabbit 首審 13 檔、2 issues：標點空值已修；逾時直接退出且不等待 QThread 的建議因物件／模型生命週期風險拒絕，阻塞 slot 測試提供反證，另補等待 UI。修正審查實際列出 12 檔、0 issues；不再重複上傳。

快取微基準只描述本機結果：同一 512 筆資料、compact JSON、48 KiB 測試容量下，反覆整份編碼與逐筆編碼皆保留 150 筆。它不是正式產品效能保證。

## 多專家評議與未完成項目

使用者核准總 12,000 tokens、每席 2,000／8 tools、主席 4,000、總 48 tools／30 分鐘。三位真實 Luna 評論與另一位仲裁已執行，工具額度不按輪次重置。快照 219 項雜湊由主席重算；flow final／arbiter 報告雜湊吻合，Rust critic validator valid=true。

仲裁判定五項歷史 finding 有支持關閉的證據，controlled Qt／圖示／既有工作列確認可成立。resources 席只完成宣告及片段檢查，cache／lease／knowledge 實作覆蓋仍 partial／unknown；兩席用完工具額度前未成功寫檔，主席以明確標示的 receipt 保存實際 final 回覆，未冒稱其有完整封存報告。**沒有零問題即通過的推論，也沒有 Done／passport／正式發布。**

要完成正式評議，仍需額外授權的獨立 resources 覆蓋與最終證據裁定。依 [Mission Center 評議規則](C:/Users/USER/.codex/plugins/cache/mission-center-local/mission-center/0.5.2/skills/mission-center/references/completion-critic-council.md)，「Resource budgets and platform limits still apply and are not reset per wave.」原席次工具上限已用完，不能自行加額。

本地原始紀錄：`output/audit-hardening-20261003/`；正式紀錄：`output/mission-center-critique/CH-T117-hardening-20261004.json` 與同名資料夾。舊紀錄與套件保留。

## 另外的憑證事件

Antigravity 本輪只獲授權讀工作區，卻讀取工作區外 MCP 設定，GitHub personal access token 出現在工具輸出。已送出停止指令；停止完成尚未確認，未再委派。原始 trajectory 已從本輪暫存丟棄，token 值不寫入專案／審查／提交。

**仍需帳號擁有者撤銷該 token、替換連接設定中的憑證，並確認 Antigravity 當次工作停止。** 這是實際憑證事件，與程式來源測試分開，尚未宣稱解除。GitHub 的[處理已外洩憑證指引](https://docs.github.com/en/code-security/how-tos/manage-security-alerts/manage-secret-scanning-alerts/resolving-alerts)建議撤銷外洩憑證；不要將原 token 再貼到對話或紀錄。
