# Qt 原生崩潰：時間線、查證與修正

日期：2026-10-04，台灣時間 UTC+8。調查基準 main `34b414194e0d4cb21e503153868e7ff5221456a5`；Python 3.10.11／PySide6 6.10.1。隔離 venv 的 `include-system-site-packages=true`，實際 Qt DLL 來自 Python310 的 site-packages；不是一套獨立安裝的 Qt。

**最新反證：07:02:03，來源提交 `0373861710194bf63cd6918774978854f5c2274b` 的 [GitHub CI 37160325279](https://github.com/Gale0418/CloudHime/actions/runs/37160325279) 又發生原生存取違例。現在仍會；不能將下列本機通過結果稱為已根治。** 八個必要工作中七個成功、UI 群組失敗；兩個手動 frozen 工作跳過。設定外觀檔在獨立程序的第 12 案，建立 Controller 的 `setup_worker()`／`QThread()` 時失敗；CI 未產生 native dump，不能由 Python stack 判定為歷史同 RVA。這是在設定頁回呼修正之後、下述快捷鍵修正之前的來源。

後續快捷鍵修正提交 `685fd91fc25fac041516d6b770f94161117c7375` 的 [CI 37161334665](https://github.com/Gale0418/CloudHime/actions/runs/37161334665) **八個必要工作成功、兩個手動 frozen 跳過**。這是新來源未再現的證據；歷史問題具間歇性，一次成功不證明因果或完整根治。再後續設定視窗 ownership 修正的遠端回執另行核對。

最終來源 `eb5ee34eb67bb40c0e5d5dc0d39e951b5d2b7c2d` 已推上 main、遠端 ref 一致；[CI 37161687605](https://github.com/Gale0418/CloudHime/actions/runs/37161687605) **completed／success，八必要工作成功、兩手動 frozen 跳過**。最終 `lifetime-final-ownership` 在 CDB 下完成 **20 輪／1 passed**，JUnit、cycles 與無 native marker 對帳一致；沒有額外保留 filter／method。三個已確認生命週期缺陷已修，最新版來源驗證未再現；**完整歷史 NULL 根因仍未查明，未重建 EXE**。此 checkpoint 不是原生事故根治或產品發行的 Done。後續只修改回執文件的提交使用 `[skip ci]`，CI 對應上述來源 SHA。

## 結論與範圍

找到並修正一個可獨立重現的設定頁生命週期問題：`_ProviderDisclosure.resizeEvent()` 使用沒有 QObject context 的 `QTimer.singleShot(0, bound_method)`。元件刪除後，排隊的高度調整仍會讀取已刪除的 QLabel。修正為由 disclosure 持有的單次 QTimer，接到明確的 `@Slot()`；Qt 刪除元件時同時取消計時器，連續 resize 也只保留一次待執行調整。

修正前，同一 QApplication 中反覆建立 Controller／設定、關閉並確認 native joins、deleteLater／DeferredDelete／GC，會在第 5～6 個 Controller 發生原生 AV。完整保留舊 filter 的對照仍崩潰，故延長 filter 參照不是已驗證修法。新修正後，相同案例 CDB 下 20 輪、一般程序下 40 輪均完整通過。

這證明上述延遲回呼缺陷已修，且本次可重現的原生壓力故障在修正後未再現；**尚未證明所有歷史 `retrieveMetaObject+0x24` 崩潰都由它造成**。新壓力故障的 immediate stack 與舊空指標故障不同。沒有重建或替換 EXE、更新 Store；目前可執行檔仍不包含本次來源修正。先前「未重建 EXE」描述的是來源／Git 同步工作，不能拿來源測試代替 frozen 驗收。

## 實際時間線

從 Windows Application Error 1000 查詢 2026-09-01 起的保留紀錄，按 DLL／例外碼分組。時間代表實際故障事件，dump 寫出通常晚約 3 秒。Python 事件未保留啟動命令時，不推定一定屬於 CloudHime。

| 時間（UTC+8） | 程序與證據 | 故障 |
| --- | --- | --- |
| 9/21 21:09:28 | miniconda Python 3.13；此查詢範圍內最早 PySide 事件 | `0xc0000005`，DLL RVA `0x181cd`；當次專案未知 |
| 9/21 21:14:55 | miniconda Python 3.13；此範圍內最早相同空指標簽章 | `0xc0000005`，DLL RVA `0x1ba6c`；當次專案未知 |
| 9/24 08:26:05 | WindowsApps **CloudHime Store 0.1.0.0 EXE** | `0xc0000005`，DLL RVA `0x1ba6c`；確實曾影響產品 EXE |
| 9/24 19:39:01 | Python 3.13，保留 minidump 可解析 | `SignalManager::retrieveMetaObject+0x24`，RAX=0，讀取 NULL |
| 10/2 17:52:19 | Python 3.13／PySide6 6.10.1 | 同 `0x1ba6c`；非今日介面才引入 |
| 10/4 00:32:06 | GitHub CI 37137115838 Windows UI／Python 3.10.11 | `setup_worker` 建立後續 Controller 時 AV；CI 無 dump，不能映射為同 RVA |
| 10/4 01:25:10、01:25:58 | 本機 Python 3.10，Qt6Core.dll | `0xc0000409`、FAST_FAIL_FATAL_APP_EXIT；01:25:58 dump 的 stack 是 QThread destructor → QMessageLogger::fatal，屬於尚未結束就銷毀的另一類故障 |
| 10/4 03:15:26 | 本機 Python 3.10，PySide DLL | `0xc0000005`、`0x181cd`；dump stack 涉及動態 meta-method／signal connection |
| 10/4 03:19:31、04:36:27 | 本機 Python 3.10／PySide6 6.10.1 | `retrieveMetaObject+0x24`，dump 確認 RAX=0、讀取 NULL；04:36 Python stack 位於 `setup_worker` 的 QThread 建立 |
| 10/4 06:32、06:35 | 現行來源的刻意關閉／刪除／GC 壓力案例 | 原生 event filter override lookup AV；保留 filters 仍失敗 |
| 10/4 07:02:03 | GitHub CI 37160325279、Python 3.10.11／PySide6 6.10.1 | 設定外觀第 12 案 `test_translation_provider_controls_remain_reachable_in_translation_page` 的 `QThread()` 原生 AV；UI 群組失敗 |

Qt thread join／過早釋放的已知問題先前由 `f2e492f` 修正，證據見 `reviews/2026-10-04-hardening.md`；本次沒有將該修正冒充 PySide 空指標根因。

## 原生鑑識

利用既存 Windows minidumps 與已安裝 CDB，查 `.exr -1`、`.ecxr`、native stack／disassembly，未將 dump 上傳。DLL PE timestamp `0x691c8192` 與事件一致；`0x1ba6c` 對應 `PySide::SignalManager::retrieveMetaObject+0x24`，指令 `mov rcx,[rax]`，舊 dump 中 RAX 為 NULL。PySide 6.10.1 對應程式碼在沒有 instance meta-builder 時取 type user data，再未檢查空值便使用它。這定位了 immediate mechanism，但舊 minidump 不含 Python self 所在 heap，無法確認是哪個 wrapper／物件類型導致 type data 缺失。

新的 filter 壓力 full dump 顯示 self 是 `GlobalHotKeyFilter`、查詢 `nativeEventFilter`；Python 屬性查詢拿到的 descriptor 記憶體 type word 是 -1，區塊已重用。它支持 binding／屬性查詢狀態失效，但沒有證明是哪一步首次破壞狀態，也不能與舊 NULL signature 直接併因。單純保留 filters、重新設定方法均未成功。純 Qt filter + QWidget 200 輪、CloudHime filter 單獨 200 輪通過，表示完整 Controller／設定生命週期的交互才是目前重現條件。

## 驗證與失敗保留

- 獨立 disclosure 刪除案例：修正前 `disclosure-red` 1 failed（已刪除 QLabel）；修正後 `disclosure-green` 1 passed。已納入 `tests/test_translation_panel_advanced.py`，驗證排隊後刪除的使用者行為。
- 修正後相關四檔，同一程序：`provider-fix-validation` **207 passed**，含產品、設定外觀、主窗 smoke 與 provider panel 回歸。
- 修正後同一 QApplication 的完整建立／設定／關閉／native join／刪除／GC：`lifetime-after-timer` **20 輪完整／1 passed**；`lifetime-fixed-normal` **40 輪完整／1 passed**。輪數不是 60 個不同測試，也不是完整桌面或 frozen EXE 驗收。
- 前兩個修正後 probe 為觀察方法參照而額外持有 method；再去除該診斷參照的 `lifetime-fixed-unretained` **20 輪完整／1 passed**，無 native AV。此對照保留於紀錄，避免將診斷工具的保活誤認為產品修復。
- 修正前一般產品 80 案、GC 80 案與混合 159 案曾通過；其後新壓力案例仍崩潰，不能用舊通過結果宣稱無風險。
- `lifetime-filter-disabled` 120 秒 timeout，約 60 輪、無 JUnit，不能算通過；縮小的 `lifetime-disabled-20` 雖無 native AV，仍有 deleted-label failure／teardown error。保留這些反證。
- 早期診斷 harness 有 initial-break 配置與錯誤方法名／未設定屬性讀取問題，均不算產品重現或通過；已修正工具。CDB `q` 可能回傳 0，即使剛捕獲 AV，因此以 native marker、完整 JUnit 和 cycles 對帳，不能只看 exit code。
- CodeRabbit 初次指令因臨時 repo 無法判斷 base branch 而在送審前失敗；明確 `--base main` 後 **2 檔、0 issues**。本時段 2 個 CLI 指令、1 次實際審查，未用 credits；payload 只含兩個修改程式檔，排除模型、資產、dump、設定與憑證。NDJSON 與 SHA-256 manifest 同診斷目錄。
- CI 失敗後，本機 `settings-cold-native` 在 CDB 下冷啟相同單檔 **15 passed**；不能抹掉遠端失敗。新假說「worker 配置前完整 GC 是否使 stale wrapper 重用」的 `settings-before-worker-gc` 同樣 **15 passed**，未捕獲原始 NULL signature，不能據此修改 BindingManager 或宣布排除 GC 交互。

## 關閉後快捷鍵重新啟用：另一個已確認缺陷

`Controller.__init__()` 的 `QTimer.singleShot(500, self.enable_hotkey)` 沒有元件 context；`close_app()` 已移除 native filter、取消快捷鍵後，這個排隊回呼仍會重新註冊快捷鍵並讀取視窗。回歸 `test_delayed_hotkey_activation_is_cancelled_when_closing` 在原始碼明確失敗（關閉完成後 registrations 仍有一筆），並非由原生 stack 推測。

修正為 Controller 持有的單次 `_hotkey_activation_timer`、`@Slot()`，關閉時停止；`enable_hotkey()` 也拒絕 shutdown 期間呼叫。新 `hotkey-validation` 的五檔同程序 **214 passed**，含這個回歸。一次指令誤用不存在的 smoke 檔名導致 exit 4、沒有執行案例；更正為已確認存在的檔案後才取得上述通過證據。這個修正尚未被證明解決歷史 NULL fault，不能把普通斷言 red/green 當原生根因。

快捷鍵修改的 `cloudhime_ui.py`／`tests/test_shutdown_lifecycle.py` 另以獨立 projection 送 CodeRabbit，**2 檔、0 issues**；`coderabbit-hotkey.ndjson` 與 `hotkey-review-scope.json` 保存最終 bytes／SHA-256。此時段累計 3 個 CLI 審查指令、2 次實際審查，沒有超過 3 次／150 檔上限。修改的大 UI 檔必須審查，未修改的大檔與所有 dump、settings、models、assets 均排除。

## 設定視窗跨 Controller 殘留：已確認與修正

`SettingsWindowRevamp` 原本沒有 QObject parent，卻強持有 Controller；關閉只隱藏，測試刪除 Controller 後仍留著設定窗。`settings-survivor-observation` 依設定外觀單檔順序觀察到 **6 個隱藏且有效的設定窗**，其 Controller 全部已 invalid；完整 GC 後仍 6 個。這是直接觀察到的生命週期殘留，不是已確認的 NULL producer。

回歸 `test_settings_window_is_destroyed_with_controller` 驗證設定窗關閉後可以重開同一視窗，Controller 被刪除時設定窗也必須刪除；修正前 `settings-owner-red-clean` 明確 **1 failed**。最初診斷曾把手動刪除的 Controller 又交給 qtbot 關閉，產生 teardown error；修正測試所有權後才採用上述 clean red。產品修正只有 `super().__init__(controller)`，保留既有 `Qt.Tool`、獨立視窗與隱藏／重開行為。

修正後 `settings-owner-green` 五檔同程序 **215 passed**；CDB 下 `settings-owned-observation` **15 passed**，每案後設定窗殘留 **0**。第三次實際 CodeRabbit 審查 **2 檔、0 issues**，最終 bytes 由 `ownership-review-scope.json` 核對。此小時共 4 個 CLI 指令，其中第 1 個在 `gitService.getBranchInfo` 前置檢查就失敗、沒有送審；實際審查總數 **3**，各 2 檔。沒有再送第四次實際審查，沒有上傳 dump／憑證。

原始證據與可重跑診斷程式都在 ignored `output/qt-crash-20261004/`。full dump 限本地診斷；未放入 Git 或 CodeRabbit payload。所有本輪測試／debugger 子程序會於結束後核對，僅處理本次擁有的程序。

## 待確認

原始 NULL fault 的首次失效 wrapper／最小原生重現尚未取得。若再次發生，優先保留含 heap 的任務隔離 native dump，查原始 self type 與 BindingManager 對照；不要以隨機改 ownership、全域停 GC、留住所有 filters 或未驗證的 Qt 升級當修法。既有 0.1.2.0 候選 EXE／Store 安裝沒有本次修正；新 frozen 產物及實際桌面驗收需獨立建立證據。

官方對照：[PySide 6.10.1 SignalManager 原始碼](https://github.com/pyside/pyside-setup/blob/v6.10.1/sources/pyside6/libpyside/signalmanager.cpp#L697)、[type user data 原始碼](https://github.com/pyside/pyside-setup/blob/v6.10.1/sources/pyside6/libpyside/pyside.cpp#L453)、[QObject 物件樹與 ownership](https://doc.qt.io/qt-6/objecttrees.html)。公開 Qt Forum 的相似 signature 只有另一位作者的不同物件重現，未用作本程式已確認的根因或修法。

## 08:21 原生寫入監看：event filter 故障鏈已確認

以固定歷史來源 `34b414194e0d4cb21e503153868e7ff5221456a5` 重放完整 Controller／設定窗生命週期。UI 與 provider panel 的 SHA-256 由 manifest 核對；歷史模組僅在隔離診斷子程序中載入，主工作樹未回退。08:21:42 開始的 `native-method-first-release` 在第 2 輪、pytest 尚未結束時捕獲 `GlobalHotKeyFilter.nativeEventFilter` 的引用計數降為 0。硬體資料斷點沒有額外持有 function；以 gate 確認斷點安裝後才允許測試繼續。

直接因果證據：

- `Sbk_GetPyOverride+0x154` 的 `sub qword ptr [rdi],1` 將函式 `0x2ddd0dd5750` 減到 0，斷在 `+0x158`；尚未執行其 deallocator。原生堆疊來自 Qt event dispatcher 的 native filter lookup。
- 當下 Python thread state 的待處理例外是 `RuntimeError: Internal C++ object (PySide6.QtWidgets.QLabel) already deleted.`；traceback 指向歷史 `translation_settings_panel.py` 第 118 行 `_sync_capability_height()` 的 `capability_label.width()`。
- 同一完整 heap 中，`GlobalHotKeyFilter` 的 class dict 仍有 `nativeEventFilter` key，其 value 仍是上述引用計數已歸零的 function。這排除「程式先替換方法，正常釋放」的解釋。
- 官方 6.10.1 `BindingManager::getOverride()` 回傳 `PyMethod_Function(method)` 的借用指標；`Sbk_GetPyOverride()` 的錯誤狀態分支卻執行 `Py_XDECREF(pyOverride)`。本機原生指令與此分支一致。後續 filter lookup 會使用已釋放的函式，解釋先前 `PyObject_GenericGetAttrWithDict` 的失效 descriptor 故障。

因此，這條故障的應用層觸發是缺少 QObject context 的設定頁 timer，底層放大機制是 Shiboken 在錯誤分支減少借用指標的引用。先前已交付的 parent-owned timer／Slot 修正取消刪除後回呼，移除本程式已確認的觸發；本輪沒有修改已安裝 PySide DLL、套用二進位 patch 或新增全域保活措施。

08:26:42 的相同 `native-method-current-compare` 在目前來源完成 **20 輪／1 passed**；`pytest_sessionfinish` 的 exitstatus 為 0，完整 JUnit 存在。首次歸零發生於 `PyDict_Clear → Py_FinalizeEx`，屬 Python 結束時的正常清理。CDB 為保存此證據而中止剩餘 interpreter cleanup，故 debugger exit 0／child 終止碼不作一般程序正常退出的證據；通過範圍以測試、session marker 與完整 20 輪紀錄為準。

官方 6.10.2、6.10.3 與本輪查閱的 `dev` 仍保留相同 borrowed-return／錯誤分支 DECREF。沒有已驗證的官方修復可供直接升級；目前版通過亦不代表底層依賴的此缺陷已不存在。[6.10.1 getOverride](https://github.com/pyside/pyside-setup/blob/v6.10.1/sources/shiboken6/libshiboken/bindingmanager.cpp#L342)、[6.10.1 錯誤分支](https://github.com/pyside/pyside-setup/blob/v6.10.1/sources/shiboken6/libshiboken/basewrapper.cpp#L769)、[6.10.3 對照](https://github.com/pyside/pyside-setup/blob/v6.10.3/sources/shiboken6/libshiboken/basewrapper.cpp)。

證據均限本機 ignored `output/qt-crash-20261004/`：`native-method-first-release-{cdb.log,native.dmp,ready.json,result.json,cycles.jsonl}`、`override-watch-analysis.log`、`pending-error-message.log`、`pending-error-frame.log`、`class-dict-at-zero.log`、`class-dict-method-key.log`、`native-method-current-compare-{cdb.log,result.json,session-finished.json,cycles.jsonl}` 與其 `.xml`。原始 dump、設定與診斷子程序環境未上傳。

## 原始 NULL：確認錯取 wrapper，producer 仍待查

10/4 04:36 的既存 dump 顯示，QThread 建構先註冊 wrapper `R14=0x2e86a5162c0`／C++ pointer `RDI=0x2e86c988500`，緊接著的 generated `metaObject()` 卻把另一 wrapper `RBX=0x2e86ac20ac0` 交給 `retrieveMetaObject()`。9/24 19:39 的獨立歷史 dump 也有相同差異：`R14=0x213f2f0f800`、`RDI=0x213e70b9380`、`RBX=0x213ed2f8c00`。兩份 dump 的 QtCore PE timestamp 均為 `0x691c81a8`，對應相同建構 caller `PyInit_QtCore+0x46e05`。

官方生成器在 QObject `metaObject()` 使用 untyped `retrieveWrapper(this)`，而 BindingManager 用 multimap 容納同址物件，該查找只取第一項；這支持錯取 wrapper 的候選機制。但兩份 minidump 不含舊 wrapper heap，不能確認其類型、map equal-range、失效／刪除順序，也不能認定來源就是 native filter。[生成器](https://github.com/pyside/pyside-setup/blob/v6.10.1/sources/shiboken6/generator/shiboken/cppgenerator.cpp)、[BindingManager](https://github.com/pyside/pyside-setup/blob/v6.10.1/sources/shiboken6/libshiboken/bindingmanager.cpp#L327)。

新診斷先發現 Windows venv 的 python redirector 另起子程序：設在 redirector 的 deferred breakpoint 不會自動套用子程序。改由同一 base Python 3.10 直接啟動、將既有測試套件加入 PYTHONPATH 後，健康檢查確認真正命中 QThread constructor／metaObject；兩者 Qt／Shiboken DLL 相同，但 sys.prefix 不同，保留此診斷限制。先前的子程序例外捕獲仍有效，沒有將未綁定的註冊斷點當成產品反證。

`old-settings-thread-binding` 的 15 案通過、18 次 ctor／meta 成對且 wrapper 一致；`historical-lifetime-thread-binding` 在 event filter 原生 AV 前也有 8 對一致。REG／RELEASE export 歷史未找到 collision candidate，但 compiler-inlined release 可能未被記錄，不能拿這份近似歷史當成 live map 真相。解析器已補辨識實際 `CLOUDHIME_THREAD_META` marker，避免舊摘要錯顯 meta=0。

原始 NULL 未完成；本輪仍沒有重建 EXE、替換 Store 或變更任務 lifecycle。新診斷只增加證據，產品來源仍為先前已驗證的 `eb5ee34`。

14:25 的 `historical-settings-address-reuse-corrected` 在固定來源 0373861 以同一 QApplication 重複四輪設定頁案例，完整 REG／RELEASE 監看超過 180 秒而中止、沒有 JUnit，不算通過。第一次指令誤用不存在的檔名，exit 4／0 個案例；該失敗也保留。縮小監看至 constructor／meta 的 `historical-settings-narrow-reuse` 在 98.07 秒完成 **60 次案例執行／15 個不同案例** 並生成完整 JUnit，未觀察 wrapper mismatch 或 AV，但程序結束仍超過總時限 120 秒，因此整個 probe 為 timeout、不能當完整程序通過。沒有新 producer 證據，不繼續無限制重跑；保留日誌與 XML，收尾檢查只針對本次擁有的 Python／CDB。


## 2026-10-04：translation-final 整合與發行狀態

來源為 `main` `466780b`。整合收據 `second-line/integrated-receipt.json` 記錄 576 passed、31.23 秒；逐項輸出位於 `output/store-release-20261004-translation-final/verification-result.json`、`ci-result.json`、`coderabbit-receipt.json`、`source-text-probe.json`。最新 CI 是 8 required success、2 manual skipped。CodeRabbit 曾回報 2 minor 並已修正；來源 `466780b` 的 4 檔複審為 0 issues，僅涵蓋該次範圍，不能推論整個儲存庫沒有問題。

新 EXE `1015aa86…fda1863` 在 host frozen 環境通過 OCR 兩行、CPU vision 1/1 與 20 秒 GUI 驗證。這不代表完整 GUI OCR journey 已通過：實際 公開測試句的 Gemma 單句與 batch 第 2 行都輸出英文（未使用 Google），已驗證的只有固定來源的模型文字呼叫。使用者 暫停／繼續／重新框選取消 完整操作驗收仍待完成。

全新 sandbox OCR 仍失敗；identity MSIX 已證明成立，但執行仍是 `E_FAIL`。native-first guest stream 可成功 decode BGRA8，`RecognizeAsync` 失敗且 C Windows OCR 回傳空結果。缺少 payload 只是待控制實驗驗證的候選解釋；目前不能宣稱根因已定或全面修復。原始 raw failure 保留。

目前 0.1.2.0 套件封裝 進行中，Store 現行仍為 0.1.1.0，尚未上傳或認證。正式評論 尚未派送，已核准額度維持不變。

### 20:01 OCR 語言資源控制實驗

原始 `sandbox/`、`ocr-identity/` 及 `ocr-native-first/` 的失敗保留。native-first 使用首次成功建立的同一 engine，Store／Flush／解碼均成功（1000×300、BGRA8），到 RecognizeAsync 才失敗，排除探針先丟棄 engine 的疑點。取得 MSIX 身分也未改善。

`ocr-payload-control/` 首次寫入沙箱 Windows OCR 目錄遭拒，該失敗未覆蓋。`ocr-payload-control-v2/sandbox/output/result.json` 在僅限 WDAGUtilityAccount 的拋棄式沙箱補入主機既有 ja／zh OCR 資源後，原生辨識 2 行、同來源 frozen 程式初次與再次辨識均 2 行且 error 為空；owned 程序清理為 0。這確認沙箱語言資源缺失或不可用會造成本次失敗，並非只靠套件身分可修復。沒有變更產品 OCR 來源；未將 Windows 資源打包、上傳或當成正式 Windows capability 安裝。

後續 `sandbox-ocr-prerequisite/` 明示「新沙箱＋診斷用 OCR 前置資源」，不替代原始未修改沙箱的失敗紀錄。啟動時因可用 RAM 未達 6 GiB 被 guard 拒絕；沒有啟動 VM，也沒有清理無關程式。待封裝與記憶體允許後繼續完整 EXE OCR／CPU／GUI，以及 MSIX 安裝／更新／WACK。CH-T55 保持 Review，Smoke NO、Critic NO；原 Store 0.1.1.0 保留。


### 2026-10-04 本機模型準備與 Google 誤路由修正

20:13 實機截圖顯示候選 EXE 停在 Preparing model、charge bar 誤寫 Google、框選中文未翻譯；這次驗收失敗，466780b 的候選 MSIX／upload 已退回且未上傳。封裝診斷確認兩個內附 GGUF 與 runtime 都存在，未選到受管下載路徑。完整來源 Controller 診斷顯示背景在首次 SHA 驗證讀模型；併行封裝 I/O 下未於時限內就緒，這僅解釋診斷中的等待，尚未證明實機失敗的全部根因。

修正明列 local-only provider chain 時的隱性 Google fallback 與舊 Google 快取偷渡；設定頁改讀實際 local_multimodal provider。內附模型驗證增加實際位元組進度及區塊間取消，仍核對 SHA，只有成功驗證才寫 receipt。文字模式保留驗證階段，CPU 文案不再宣稱初始化 GPU；未就緒時按翻譯保留字幕並提示等待，明列 Google 的 fallback 保持可用。

相關回歸 313 passed；CodeRabbit 僅審本輪 9 個程式／測試檔、0 issues，未包含模型、DLL、大型輸出或使用者另留的 logo。證據：output/store-release-20261004-local-warmup/checkpoint-evidence.json、regression.xml、coderabbit-scope.json 與 coderabbit-review.ndjson。新 EXE 完整啟動／翻譯、GUI 操作、沙箱／MSIX／WACK與正式評論仍待完成；Store 仍為 0.1.1.0，CH-T55 保持 Review。


### 2026-10-04T21:21+08:00：本機準備修正版 EXE 與實際 Controller 驗證

固定來源 adf8d39 新 EXE 已重建，SHA 931d24c73099cead2fa016523afc6efb71365cbd0614a5975a2bad88496af846。模型完整性、frozen import、host Windows OCR 兩行、CPU vision 1/1 與正常 GUI 20 秒啟動均通過；GitHub CI 37203714789 八個必要工作成功、兩個手動 frozen 工作跳過。本輪回歸 313 passed、CodeRabbit 九檔零 issues；這些不是全專案或完整 GUI 操作驗收。

另用相同固定來源的實際 Controller、正常設定載入與該 EXE 的內附模型／runtime 做來源診斷：SHA 驗證進度 0→30→55%、模型載入、就緒，約 17.156 秒；「確認連線狀態」以 local_multimodal 翻成 Check Connection Status，未取快取，翻譯等待期間有 70 次 UI event tick。此診斷不是 frozen EXE 的完整人工旅程；offscreen 原生快捷鍵排除，不能推論暫停／繼續／取消框選全部通過。Controller cleanup 完成，自有 llama-server 已終止；其 wrapper exit 1，沒有冒稱正常 exit 0。證據：output/store-release-20261004-local-warmup/verification-result.json、controller-startup/result.json、verified-checkpoint.json。

主人指定文案由 Gemini 撰寫，已透過 Antigravity Bridge 送出；同一 cascade 卡在 filesystem/describe 實際工具授權，已排入不使用工具的純文字後續要求，尚未取得文案，未以 Codex 代寫冒充。20:13 失敗候選維持退回。最新 MSIX／完整人工操作／沙箱前置環境／更新安裝／WACK／正式評論仍待完成，Store 0.1.1.0 保留，CH-T55 Review、Smoke NO、Critic NO；24k 正式評論尚未起算，尚未上傳或認證。
