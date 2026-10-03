# 2026-10-04 CloudHime 程式檢查與修復

本輪來源修復仍在收尾，正式多專家評議為 **limited**，CH-T117 保留 Review。提交 e3dae59 的 GitHub CI 發現 UI 原生存取違規；後續 f2e492f 已通過 UI 群組，但完整 runtime 群組揭露取消契約回歸，現已補修並重新驗證，待新提交 CI 與獨立最終裁定。這份紀錄不代表新的 frozen EXE、Store 套件或上架驗收通過。

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

使用者已核准精簡收尾額度 4,000 tokens／12 tools／10 分鐘，並明確授權本任務持續修復、評議至沒有 P0／P1，不再重複詢問同一授權。原席次及追加用量分別累計，不把上一輪 limited 改稱通過；獨立 resources 覆蓋與最終證據裁定繼續進行。

## CI 與關閉生命週期後續

來源 e3dae59 的 [CI 37137115838](https://github.com/Gale0418/CloudHime/actions/runs/37137115838) 七個必需群組成功，UI 群組失敗：建立後續 Controller 的 QThread 時 Windows 原生 access violation。先前 1,623 個本機成功案例是當時的來源基線，不能替代這次失敗，也不是後續修復的最終驗證。

補查發現 QThread.finished 不能代替原生執行緒完整 join；OCR、背景清理及遠端查詢須 wait(0) 確認後才放掉強參照。新增回歸已證明舊清理 callback 會提早標記完成。候選修復的四檔合併 UI 診斷仍在設定取消後的 teardown 卡住，180 秒後只回收本次啟動的測試程序樹，保留 stack／timeout 紀錄；目前正在查證訊號執行緒及關閉事件，不宣稱此候選已修好 CI。

後續實際 Controller 回呼探針全部在 GUI 執行緒，未支持「缺少 Slot 就是根因」的假說，未因此重寫訊號路由。移除探針後四檔合併 119 項通過（27.78 秒），仍以後續最終來源與遠端 CI 為驗收準據。

獨立資源席另提出啟動／停止競態與清理持鎖兩項 P2，正以阻塞 runtime 重現；知識包席提出關閉只等 daemon worker 2 秒的生命週期缺口，修復席正在補實際終止門檻與阻塞研究回歸。

知識服務取消屬合作式，已進入的同步 provider 呼叫先返回，再拒絕後續階段，沒有宣稱 DNS 或整次呼叫的硬截止時間。評論中「取消可能仍等 8×15 秒來源讀取」已有反證：新回歸在第一筆讀取阻塞時取消，八個網址只 dispatch 一次，不呼叫模型，服務／builder 共 21 項通過。原評論報告保留，最終仲裁會核對此處置。

最終獨立逐檔驗證再現產品測試關閉卡住，180 秒後按本次 Popen 程序樹回收，來源前後雜湊相同。既有 Windows SDK CDB 非侵入診斷取得原生 stack：GUI 等在 Qt QObject connect mutex，另一個 QThread 等 Python GIL；動態訊號連接／回呼生命週期的互鎖正在查證。記錄在 `native-hang-cdb.log`、`final-verification/summary.json`，這次驗證結果為 fail，不因之前一次合併成功而結案。

本地原始紀錄：`output/audit-hardening-20261003/`；正式紀錄：`output/mission-center-critique/CH-T117-hardening-20261004.json` 與同名資料夾。舊紀錄與套件保留。

## 定稿修復與本機重驗（2026-10-04）

第二份非侵入 CDB stack 另定位 GUI 處理 DeferredDelete 的 QWidget 子物件析構與背景 QObject 析構同時等待 Qt mutex／Python GIL；不宣稱已證明特定 upstream bug 或 mutex instance。production 改用建構期預連接的 Slot／timer 輪詢，QThread wait(0) 確認真正 join 後才放掉強參照；測試 teardown 先完成所有 shutdown gates，再明確 flush DeferredDelete，逾時與 close veto 都 fail-closed。

知識研究取消後改於背景等 wait_for_all 真正完成，關閉期間拒絕新研究。模型 stop 在 start 尚未進入 runtime 的交錯已於舊版重現 stopped 預期落成 ready；新版記住 stop-after-start，完成後補 stop，失敗保留重試路徑。正常 stop／profile 的持鎖是單一 runtime fail-closed 序列化，阻塞測試證明 acquire 不會建立第二台 server；交由獨立資源席判斷，不用偏好直接擴大重構。

`final-verification-stable/summary.json`：七份 UI 檔依 CI 逐檔隔離，加上租約／快取／知識服務／builder／inventory，**229 passed、0 skipped／failure／error、exit 0、sourceUnchanged=true**。前一輪 deferred 驗證各程序雖 exit 0，但 conftest 在途中新增 fail-closed guards，整體 sourceUnchanged=false／fail；紀錄保留，不算定稿成功。

新 `ch-t117-final-success-20261004`／`ch-t117-final-failure-20261004` harness 皆 exit 0：正式 Worker→Controller→Qt paint 成功字幕與 provider 失敗原文，失敗不寫持久快取，實際 timer 關閉完成並確認 OCR native join。兩者均 mock OCR／provider、offscreen；source-binding.json 綁定目前來源與純雲朵資產，沒有 live 或新版 frozen 產物聲稱。CodeRabbit 本輪外部額度已耗完，後續 Qt／資源修復未再跑外部審查，改由授權範圍內的獨立專家驗證；這不等同 CodeRabbit 新版 clean。

## 完整 CI 揭露的取消相容性回歸

[CI 37143016536](https://github.com/Gale0418/CloudHime/actions/runs/37143016536) UI 與其餘六個必需工作成功；runtime 一項失敗，191 passed／2 skipped：`test_coordinator_stop_can_cancel_blocked_start` 預期 stopped，實際 failed。完整失敗紀錄保留，未只重跑 CI 來掩蓋。

已新增 `LocalVisionRuntime.request_stop()` 的非阻塞取消通知；coordinator 在啟動中立即設取消事件，同時保留 stop-after-start，涵蓋尚未進入 runtime 的啟動交錯。既有 stopped 期待不改弱。root 依真正 CI JSON 的九份 runtime 檔加上 coordinator 重跑，**207 passed／2 skipped／0 errors、exit0、sourceUnchanged=true**，見 `runtime-final-root/summary.json`／`result.xml`。代理的 124 passed 屬受影響 runtime 相關檔，並非完整 CI inventory，兩者區分記錄。

先前 229 pass 對應 f2e492f 定稿階段；後續 runtime 變更以上述 207 pass 與新 CI 驗證，UI 只有修正過時註解，沒有行為差異。`ch-t117-closure-success-20261004`／`ch-t117-closure-failure-20261004` 已在最新來源各自重跑 exit0，更新實際 Qt paint／native join 與 source-binding。CodeRabbit 額度不重置。

## 另外的憑證事件

Antigravity 本輪只獲授權讀工作區，卻讀取工作區外 MCP 設定，GitHub personal access token 出現在工具輸出。已送出停止指令；停止完成尚未確認，未再委派。原始 trajectory 已從本輪暫存丟棄，token 值不寫入專案／審查／提交。

**仍需帳號擁有者撤銷該 token、替換連接設定中的憑證，並確認 Antigravity 當次工作停止。** 這是實際憑證事件，與程式來源測試分開，尚未宣稱解除。GitHub 的[處理已外洩憑證指引](https://docs.github.com/en/code-security/how-tos/manage-security-alerts/manage-secret-scanning-alerts/resolving-alerts)建議撤銷外洩憑證；不要將原 token 再貼到對話或紀錄。
