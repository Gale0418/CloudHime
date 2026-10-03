# Qt 原生崩潰：時間線、查證與修正

日期：2026-10-04，台灣時間 UTC+8。調查基準 main `34b414194e0d4cb21e503153868e7ff5221456a5`；Python 3.10.11／PySide6 6.10.1。隔離 venv 的 `include-system-site-packages=true`，實際 Qt DLL 來自 Python310 的 site-packages；不是一套獨立安裝的 Qt。

**最新反證：07:02:03，來源提交 `0373861710194bf63cd6918774978854f5c2274b` 的 [GitHub CI 37160325279](https://github.com/Gale0418/CloudHime/actions/runs/37160325279) 又發生原生存取違例。現在仍會；不能將下列本機通過結果稱為已根治。** 八個必要工作中七個成功、UI 群組失敗；兩個手動 frozen 工作跳過。設定外觀檔在獨立程序的第 12 案，建立 Controller 的 `setup_worker()`／`QThread()` 時失敗；CI 未產生 native dump，不能由 Python stack 判定為歷史同 RVA。這是在設定頁回呼修正之後、下述快捷鍵修正之前的來源。

後續快捷鍵修正提交 `685fd91fc25fac041516d6b770f94161117c7375` 的 [CI 37161334665](https://github.com/Gale0418/CloudHime/actions/runs/37161334665) **八個必要工作成功、兩個手動 frozen 跳過**。這是新來源未再現的證據；歷史問題具間歇性，一次成功不證明因果或完整根治。再後續設定視窗 ownership 修正的遠端回執另行核對。

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
