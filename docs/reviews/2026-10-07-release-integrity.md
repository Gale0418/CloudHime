# 2026-10-07 發行補件與環境完整性

CH-T55 維持 Review；CH-T56 尚未完成。主人已驗收來源版的 Luna、Gemma、設定與精簡介面；來源驗收不能替代最終 EXE／MSIX、WACK 或 Microsoft Store 認證。

## 授權與來源補件

- 只保留產品用到的 Qt 模組；spec 移除 VirtualKeyboard、QML／Quick、PDF，preflight 拒絕未審核 Qt6 DLL。原始 GPL／Commercial VirtualKeyboard 候選已撤換。
- 固定副本 manifest 現有 595 筆原文／告知，全部有來源與 SHA-256。來源副本是對應來源樹的告知集合，不表示每個來源元件皆被連結。
- Qtbase、QtSvg、Qtimageformats、PySide6 6.10.1 的官方來源封存與 Metalink SHA 已核對；可重建／替換說明隨包保存。可寫入 onedir DLL 替換探針已有歷史證據，但新候選及 Store 安裝後副本仍須獨立驗證。
- CUDA DLL 與 NVIDIA 官方 redistributable 檔案逐一核對：cuBLAS 12.4.5.8、cudart 12.4.127；最初比對 cudart 12.4.99 不符的證據保留。另保存 LLVM／OpenMP、CPython、Mesa／LLVM-MESA 告知。
- primp 1.3.1 的 normal Windows dependency tree 共 203 項，對應 365 份授權副本。這是標籤來源／Cargo.lock 的 normal graph，不能用它聲稱 wheel 精確編譯 attestation 或 build-only graph 全數覆蓋。
- wheel 原始授權 evidence 與補充原文分開保留；缺原始 wheel license 檔不會因補件存在而從 collector 報告消失。法律合規未作專業認定。

詳見 `packaging/third-party-licenses/QT-LIBRARY-REPLACEMENT.md`、`NATIVE-RUNTIME-NOTICES.md`、`sources.json`。

## 實際建置阻礙與修正

既有 Python 3.10 同時安裝 `opencv-python` 與 `opencv-python-headless`；metadata 宣稱 headless 4.13.0.92，但 cv2 實際為 5.0.0，pyd 與 headless RECORD 不符。第一個 EXE 雖通過有限啟動／OCR 探針，仍標記 superseded，不可發布。未修改主人的全域 Python。

改以專用 venv 按 production hash lock 實際安裝 40 套件。舊 pip 22 的 report 缺少新格式授權 metadata，升級隔離環境內 pip 後重新安裝並保存原始與新報告。第二次編譯在 PNG 圖示轉換階段因缺 Pillow 停下；原始 build log 與失敗收據保留。Pillow 12.3.0 已依 PyPI 官方 Windows CPython 3.10 wheel SHA 加入 build-only lock，產品 spec 排除 PIL。

建置入口新增指定隔離 Python 的變數與實際環境完整性 guard；完整性失敗時保留原 dist。guard 已綁定鎖定 wheel 的 URL／SHA、可信 RECORD 與實際 payload，拒絕未雜湊原始檔、被改寫的 installed RECORD 及多個 OpenCV variants；僅允許 pip 產生的 metadata／entry point、明確的 cache 和 script shebang 改寫。13 fixtures 與實際 40 套件／6,188 原始檔通過。

## 本輪已取得驗證

- Qt／授權／provenance／MSIX 聚焦回歸：89 passed、2 skipped、17 deselected；不包含舊工作目錄大型 dist preflight。
- 新來源原文資源：25 passed。
- provenance 路徑末尾分隔符修正：14 passed、2 skipped；3 種實際輸入路徑皆得到正確 sibling 位置。
- 安裝 RECORD 初版 guard 6 案通過；乾淨環境 40 套件／6,302 hashed files 核對通過，舊全域環境實際拒絕。
- Pillow 建置契約：25 passed、1 deselected。
- CodeRabbit 原 Qt／授權封裝 8 檔及後續 3 檔各 0 issues。初版 guard 呼叫單檔 0 issues；後續完整 guard 3 檔有 3 major issues，均查證修正；第一次複審遇 rate limit，依服務指定等候窗恢復後，7 檔修正版複審 0 issues。

具體 JUnit、原始工具輸出與失敗收據位於 `output/release-20261007/` 與 `output/release-20261007-clean/`。

## 發行界線與下一步

固定新候選的 source manifest／EXE／原生 bytes，重跑 import、Windows OCR、GUI、CPU Vision、full payload 檢查及安裝／更新／完整 WACK，再按已核准的 24k 評論額度進行正式三席與獨立 arbiter。

正式評論、Store 條款核對、上傳／認證與實際 Store 更新仍未完成。先前 WACK required PASS 不能代替這次新候選。原 Store 0.1.1.0、主人設定及原始 `assets/cloudhime_logo_v2.png` 保留。

## 新候選已完成的有限驗收

- 乾淨環境重建成功：source manifest SHA `225e37b9ec779edaa1ca11fd8e3ad84582f68458d597bc26adbd205db76e9299`，EXE SHA `7cffe59b3e2aa62eb8ea839a50553f43a85ca417fa3922636a23af83f517c888`。
- frozen cv2.pyd SHA `90034927004e4a4ebf29360480d609c8a8d2ca07c93f8b89dff86399e8534b2a` 與 hash-lock 安裝檔一致；無 ffmpeg500 額外檔，PIL 未打包。
- light preflight、frozen import、Windows OCR 2 行、GUI 20 秒均通過；新可寫入 onedir 副本的 altered Qt6Core 載入探針 exit 0，原 DLL 未改動。不作自編 Qt／Store 安裝後替換聲稱。
- full 模型／CPU Vision、MSIX、安裝／更新／WACK 仍在後續流程，未外推已通過。
- Partner Center 此次只讀核對：Submission 3、私人群組、TWD249，未排公開日期／銷售定價；四個實際 listing locale 是 zh-tw、ja-jp、en-us、zh-hant-tw，兩個繁中標籤。zh-tw 與 ja-jp 的 additional license terms 空白，日文關鍵字控制項顯示 AI 建議說明文字，深入 DOM 查證 value 空白、七個建議均未選取，不能說成已儲存關鍵字污染。四語系 terms 草稿在 docs/store-third-party-terms.json，尚未保存至外部服務。

## 後續查證

- CI inventory 補入五個既有測試檔；本地 inventory 與受影響測試 63 passed。GitHub CI run 136（commit `3c0070c`）整體 Success，五組測試與依賴／MSIX契約通過；可選 frozen release jobs 未執行，不算通過。證據：https://github.com/Gale0418/CloudHime/actions/runs/37511529428。
- 新 full preflight 的固定模型／projector 雜湊通過後，拒絕舊包複製來的 `NOTICE.txt` bytes。保留失敗 log／JSON 及四份舊告知檔，換成固定 source manifest 內的模型原文，重新驗證；詳細差異見 `output/release-20261007-clean/model-terms-correction.json`。這不是更改模型，也未覆蓋舊包。
- 非系統管理員實際讀取現有 Store 0.1.1.0 的 Qt6Core.dll、複製到可寫入位置並修改成功，原 DLL 雜湊不變。證據 `store-read-copy-proof.json`；不代表整個 Store 程式已複製並以修改後 DLL 執行。


### 2026-10-07 歷史小檔審查與成品驗證更正

CodeRabbit 歷史小檔 fixture 的149份程式／文件（另有 unchanged config）完成審查，8 issues 已查證修補；其中2份小檔是 upstream Qt license Python，未提出問題、未修改原文。151 service-count 失敗預檢也保守計入3次／小時，本小時只留一次修正版複審。新修正涉及高對比文字、建置Python路徑、環境變數、中文OCR路徑、主模型下載及測試隔離／回收；最終EXE／MSIX需在存Git、兔子複審、push main後重建。先前候選full CPU Vision 1/1及MSIX製作完成；新Sandbox update PFN／synthetic LocalState通過，但直接 Process.Start WindowsApps EXE Access denied，import/OCR/WACK未執行，不算PASS。guest package／certificate清理完成、owned VM已關閉，失敗證據保留。Gemini經Antigravity Bridge完成四locale活潑顏文字草稿，互導免費GitHub及商店方便安裝；獨立Unicode／UTF16限额檢查通過，英文短文269單位。未存Partner Center、未上傳新候選、未認證，CH-T55仍Review／SmokeNO／CriticNO。

修補驗證：focused六檔 pytest 119 passed；唯一失敗是test_real_release_dist_preflight_when_available讀到舊root dist並正確拒絕未審Qt模組，不代表本輪隔離成品。新加main資產準備測試後download_task5再驗18 passed。正式OpenCV4.13真實中文路徑解碼／高對比checked色／BAT正式Python解析探針通過；探針發現for/f巢狀CMD引號不穩，改為唯一暫存收據讀取，成功／失敗均回收，2案建置與隔離契約再驗通過。OCR後端單元測試為mock，不宣稱Windows原生OCR。新成品仍須重新執行完整閘門。


### 最終 V4 來源與商店文案 checkpoint

15 檔修正版 CodeRabbit 複審 0 issues，來源 `6f695771da890feeee2e606c397683c12d06a75f` 已 push main；CI run 138／37580547583 Success，8 項 required jobs 成功、2 項手動 frozen jobs skipped。此來源的 immutable source manifest SHA `03bca5f2a244c14f0e847627fec7344932528882f856ec659ec4918529e86e63` 重建成功；EXE SHA `b511deb81889f98c61e2c47203488f5be1512489d34d1d280c1932439a6299d8`，light preflight、import、原生 Windows OCR 2 行及 GUI 20 秒通過。新 cv2.pyd 與可信 wheel 雜湊一致，無 ffmpeg500、PIL 或禁用 Qt 模組。full CPU／MSIX／fresh Sandbox／完整 WACK 尚待驗證。

Gemini 透過 Antigravity Bridge 撰寫的四語顏文字文案已保存至 Partner Center Submission 3 草稿；官方 UI 匯出回應比對四 locale 的說明、版本更新、短文及每語7個關鍵字全部一致，其他 metadata／圖片／產品／授權欄位維持原值。原始帶資產網址的後台匯出僅保留於 ignored output，不公開；sanitized snapshot 與查核收據位於 `output/release-20261007-final/`。商店稅務／支付警示及 disabled 認證按鈕已實際觀察，尚未調整金融資料、上傳新 MSIX、認證或發布。額外授權條款仍待正式評論與保存。文案 saved 狀態變更不修改 Gemini 的顧客文字，也不改已固定的 V4 建置來源。

06:50 UTC：V4 full preflight 1,563 files／4,831,122,202 bytes／2 models 通過；強制 CPU 的 frozen technical coverage 1 case／1 image request success，完整收據 status passed，EXE SHA 與 preview 一致。owned MSIX wrapper 首次因誤指向 final/venv 提前失敗，失敗 log／JSON 保留；修正為既有 clean/venv 後 AST 與封裝前檢查通過，正在 MakeAppx 製作候選。這是 output orchestration 修正，不修改正式程式或既有 immutable source。


## V4 全新環境 OCR 診斷 checkpoint（2026-10-07）

- 來源仍為已推送 `6f695771da890feeee2e606c397683c12d06a75f`；文件 main `e497c39fdd28b5d5001b5961241c60cf0695b55e` 的 CI139：八項必要工作成功、兩項手動工作略過。未因診斷修改正式程式碼。
- V4 unsigned MSIX 0.1.2.0 已建立，SHA-256 `2d1294081ea926dc124937bd89487c5a6185d3e7337adb7f556978c5e840da06`；host full CPU／import／OCR／GUI 結果不代表 fresh Sandbox 通過。
- fresh Sandbox SDK 安裝、guest-only 簽章、0.1.1.0→0.1.2.0 更新與合成 LocalState 保留、完整 installed package 可寫副本、無外部 Python 的副本 import 通過。副本 Windows OCR 以 exit2 失敗；後續副本 CPU／Qt 修改、AUMID、完整 WACK 都未執行。Guest package／憑證清理無錯，VM 也已核對身分後關閉。
- 獨立原生 WinRT 探針有 en-US 且能建立引擎；相同候選 DLL 的 frozen 診斷工具卻取得空語言清單。繼承／隔離環境、清除 DLL 搜尋目錄、預載 Qt／MSVCP、明確 STA／MTA，以及預載系統 OCR DLL，均未恢復辨識。Python 與 PowerShell 實際都載入 System32 的 Windows.Media.Ocr.dll；native ABI 對照亦回報空語言清單，所有 HRESULT 為 S_OK，並非 Python 介面獨有現象。Microsoft 的 namespace 文件明確限定桌面程式須具套件身分；目前用未修改 V4 MSIX 測試套件 debug context，另保留真正 AUMID 啟動驗證，尚未取得通過結果，不能把 debug token 宣稱等同正式 AppId token。
- 以上診斷皆為 output 內獨立工具，不作候選 release acceptance。證據：`output/release-20261007-final/sandbox-gate/wack/output/result.json`、`ocr-bundle-diagnosis/guest/output/result.json`、`ocr-bundle-diagnosis/variants/guest/output/result.json`、`ocr-bundle-diagnosis/apartment/guest/output/result.json` 與各 guest-disposal.json。
- CH-T55 保持 Review／Smoke NO／Critic NO；CH-T56 保持 Backlog。Gemini 四語文案与七個關鍵字已實際保存並逐欄確認；本次候選未上傳、未送認證、未發布。Partner Center 稅務與支付警告仍未處理。

## 套件身分與實際原生辨識更正（08:31 UTC）

未修改 V4 候選的 package debug context 已完成測試：wrapper 的 Package Family 為 `WindSheep.CloudHime_2dn16emh70smw`，候選 OCR 仍以 exit2 失敗。這是 debug context，不代表真正 AppId token 的完整驗收；guest package／憑證清理無錯、remaining packages 0，owned VM 已精確關閉。證據：`sandbox-gate/identity-wack/output/result.json`、`identity-ocr-context.json` 與 guest-disposal.json。

原生探針的「能建立英文引擎」不是圖片辨識通過。獨立 CLR-first PowerShell 程序可列出 en-US 並建立引擎；修正根整合者加入的 PowerShell Type 參數語法後，讀取 guest-local 圖片、開檔、BitmapDecoder 與 SoftwareBitmap 均完成，但 `RecognizeAsync` 回傳 `COMException / E_FAIL / 0x80004005`。下一個獨立 CLR 程序取得空語言清單。Native MTA-first 曾有一次引擎可建立，但後續呼叫變空；System32 與 TestOutput CWD 的獨立 C++ 程序皆取得空清單。這些是初始化／環境狀態差異，尚未定位根因，不將其歸咎 Python 或據此改正式程式。

原始 harness 的型別轉換失敗、第二版較粗略錯誤與第三版精確階段／HRESULT 都保留，三個 owned guest 已清理。證據位於 `ocr-clr-native-diagnosis/guest/output/`、`ocr-init-order-diagnosis/guest/output/`、`ocr-clr-recognition-v2/guest/output/` 與 `ocr-clr-recognition-v3/guest/output/`，各目錄的 `guest-disposal.json` 確認本輪 VM 已關閉；complete 僅代表診斷資料收集。

`sandbox-gate/remaining-v4` 已核對同一候選 MSIX／EXE 雜湊並啟動獨立剩餘技術閘門：新包直接安裝、package debug context 內的 native CLR 真實圖片辨識、可寫副本 import／CPU Vision／Qt 載入、真正 AUMID 與完整 WACK。升級已通過的歷史證據保留，不重跑舊包；診斷不會中止其餘技術閘門，`allReleaseGatesPassed=false` 固定保留。08:31 UTC 尚在 copy／verify／sign，後續結果未取得。生成器最初引用舊候選的 prior evidence 路徑已於啟動前校正，最終六份 guest PowerShell 腳本經 Windows PowerShell 5.1 AST 檢查通過。

修改版 Qt 的技術稽核確認：正式 wheel 完整性 guard 會拒絕不符 production lock 的自編 wheel，但既有 MSIX builder 不對允許的 Qt DLL 執行內容 hash 白名單。`docs/release-two-track.md` 補充獨立開發 identity 的修改副本重封路徑與來源／雜湊紀錄要求；相關工具在來源 `6f69577` 與文件 HEAD `284cfd3` 間無差異。尚未實測自編 Qt 修改版 MSIX 完整功能，不宣稱法律合規或修改版已驗收。正式 24k 評論仍未開始。

GitHub CI140／37590083622 已重新確認 overall Success。四語 Gemini 活潑顏文字與關鍵字已保存；本次候選仍未上傳 Store，未認證／發布。Partner Center 稅務／支付問題已詢問主人，尚無回覆。


## V4 剩餘技術閘門結果與真正 AUMID OCR 對照（09:16 UTC）

來源與正式產物仍固定於 `6f695771da890feeee2e606c397683c12d06a75f`，未因診斷改動產品。上述 08:31 UTC 的進行中紀錄已由以下結果更新；不將歷史候選或其他來源的通過結果混入本次驗收。

- `sandbox-gate/remaining-v4/output/result.json`：同一 V4 MSIX 雜湊已核對；SDK 隔離沙箱中的直接安裝、副本 import、CPU vision 1 case／1 image、append-trailer 修改 Qt6Core 副本載入 20 秒、真正 CloudHime AUMID 啟動均通過。未修改原 installed DLL，這不是自編 Qt 修改版完整功能驗收。
- 完整 WACK：SDK `10.0.26100.8876`、exit 0、`OVERALL_RESULT=PASS`、`PARTIAL_RUN=FALSE`；13 required PASS、9 optional PASS、2 optional FAIL。XML SHA-256 `70f739a10d46db0752b88ff8d1d8ba9e77d3f6781528dca12111622afe2378ba`，定位 `sandbox-gate/remaining-v4/output/wack.xml`。
- 選用 SignedFilesTest 回報 PathTooLongException；選用 DetectBlockedExes 有 14 個 native DLL／EXE 的 process-launch API 引用及相同例外。XML 未定位實際過長檔名，不把所有錯誤歸因長路徑，也不把 API 引用當成實際執行封鎖程式。依安裝前綴估算，51 個上游授權補充文件路徑超過 260 字元、最長 301；原生 payload 沒有超長路徑。這只是候選關聯，不能代替 SDK 例外根因或 Windows S 模式驗收；原授權原文與路徑證據保留，未盲目刪除或縮寫授權。
- `remainingTechnicalGatesPassed=true` 只涵蓋該腳本列明的剩餘技術項目；`allReleaseGatesPassed=false`。先前同 V4 的 0.1.1.0→0.1.2.0 合成 LocalState 更新保留證據延用，未重跑、未稱真實主人設定升級。

獨立標準 C++／WinRT 程式封裝為開發用 `CloudHime.OcrDiagnostic` MSIX，在全新沙箱透過真正 `IApplicationActivationManager`／AUMID 啟動。探針自身核對 Package Family 與 AppUserModelId 的 API result 均為 0，取得 en-US、建立引擎、讀取圖片及轉為 BGRA8 bitmap 均完成，`RecognizeAsync` 仍回傳 `E_FAIL / 0x80004005`、辨識 0 行。相同探針在 host 成功辨識 2 行。這排除「只能由 CloudHime／Python 特有問題解釋」的假設，但不證明 OS 根因、不替代乾淨 Windows 上候選 OCR 的通過結果。

證據：`ocr-native-aumid-diagnosis/build-record.json`、`guest-v2/output/result.json` 與原生結果檔；`actualIdentityVerified=true`、`actualRecognitionSucceeded=false`、`notCandidateAcceptance=true`。開發探針未納入正式產物。所有 owned 沙箱均依 PID、執行檔與 start time 核對後關閉；remaining-v4 disposal 為 08:46:35 UTC，native AUMID 對照 disposal 為 09:13:13 UTC；兩者 guest packages 0、cleanup errors 空。沒有改動主人現行 Store 0.1.1.0、設定或主機憑證。

文件 main `da9c14fc8e41e8796e7e7b040fa4fe89e268d3cf` 的 CI141／37594920193 overall Success：8 required 成功、2 手動 frozen jobs skipped。正式評論尚未開始。四語 Gemini 行銷文案已保存；額外授權條款仍為未保存草稿，同一 Gemini 任務因 runtime `filesystem/foo` permission 等待而停滯，Bridge 回報 `may_handoff_write=false`、視窗可見性未驗證。未建立替代 writer 或虛構 Gemini 完成結果。

CH-T55 保持 Review／Smoke NO／Critic NO，CH-T56 保持 Backlog。尚缺最終 frozen GUI 完整操作、真實設定升級、乾淨 Windows OCR、正式評論、額外條款保存、Partner Center 認證及 Store 安裝／更新。稅務支付警告與價格／公開日待主人處理或決定；本次候選未上傳、未認證、未發布。


## 本輪最新 checkpoint：Gemini 條款保存與正式仲裁（2026-10-07）

同一 Antigravity Bridge request `cloudhime-store-terms-20261007-v1` 已回報 COMPLETED，Gemini 完成四語額外條款；先前 runtime permission 等待已結束，未另建 writer。原始 Gemini 文案 SHA-256 `5145c69aa9b6181d0c0765b1666fe499f4d40ee5553cc4e3e63b0ea56fe0197d`，繁中兩欄各 812、英文 1833、日文 1088 UTF-16 單位；JSON／實際換行／各語低於 30000 單位通過。Partner Center Submission 3 的四個其他授權條款已逐頁保存、重開並與 Gemini 原文全等核對。`docs/store-third-party-terms.json` 僅追加 saved-draft 來源 metadata，未改 Gemini 的顧客文字。先前四語行銷文案與七關鍵字已保存；本次只是草稿保存，沒有新增上傳、認證或發布。收據：`output/release-20261007-final/store-terms-save-verification.json`，完整保存畫面 `store-terms-saved-full.png`。Windows OCR 的 MSIX 身分要求仍依 Microsoft 官方文件；文案沒有保證自編修改版完整實測或整體法律合規。

三席 Luna（流程、視覺／文案、失敗／發行完整性）互相盲評，之後由獨立 arbiter 核對報告與固定快照。初始流程席 11、視覺席 12 工具超出各席 8 的額度，受限仲裁只有 1 工具，未完成全部核對；這段歷史保留，不能算原額度內完成。主人後續明確指示「不用管額度 任務能完成即可」，才恢復同一仲裁並實際核對全部三份報告、來源 render、底層 WACK／OCR 證據；另完成 Gemini terms 的唯讀差異檢查與獨立仲裁。沒有擅自重設 CodeRabbit 的服務限額。

本輪未查證出可定位、應修補的產品程式碼缺陷。正式仲裁結果 blocked：最終 frozen 完整 GUI 操作、真實使用者設定升級、乾淨 Windows OCR acceptance、實際 Store 認證及安裝更新仍缺證據。三主題圖片為 source render，不能替代 final frozen UI；早期沙箱 OCR 的 failed 不代表最新 WACK failed；required PASS 也不能把 optional FAIL、法律適用或 Store 門檻洗成通過。兩項 High 為所需驗收缺口，保留 deferred 只表示未完成，不是主人接受風險或允許發布。

正式機器紀錄：`output/mission-center-critique/CH-T55-20261007-v4.json`，SHA-256 `31a7f4a72c197bce712b48cad88e7dbaa9c77d550b57bf0d3b409f66e66d9db5`；6 份封存報告與 57 個 manifest entries 的 SHA 已由根整合者核對，實際 EXE／MSIX 雜湊延用已固定的 build／remaining-v4 證據，沒有假稱此步重新串流驗大檔。官方 `mission-center.ps1 critic` 回報 valid，但驗證器只確認格式，不能替代實際測試或改變生命週期。

文件來源 `36ba4cdd7c6406d0104e21239edc89f815aaba28` 已存 Git、經 CodeRabbit 四檔檢查後 push main；CI142／37600128553 Success。兔子提出一個「CPU OCR」措辭問題，但任務列不存在該字串，且 CPU1/1 與候選 OCR 失敗分開記錄，已保存 rejected-with-counterevidence 收據；未為不存在的問題改程式。現在任務列進一步明寫 CPU Vision1/1。

最終產物仍綁定來源 `6f69577`，正式程式、模型、DLL、MSIX 未因文案與評論重建或修改。隔離人工入口 `output/release-20261007-final/OpenFinalCandidate.cmd` 已準備，PowerShell AST 與 EXE hash 檢查通過、尚未啟動；執行時使用全新空白 APPDATA／LOCALAPPDATA／USERPROFILE 與 system-only PATH，不承接主人設定或金鑰。這個入口不等於人工驗收，也不證明乾淨 Windows OCR。稅務／支付資料由主人親自處理，售價／發行範圍待回覆；新候選仍未上傳，CH-T55 保持 Review／Smoke NO／Critic NO，CH-T56 保持 Backlog。


## 最新 checkpoint：候選套件草稿已保存（10:06 UTC）

文件來源 `e1f4d316795a7df982cb31326013ad1e9fad4ef8` 已存 Git，CodeRabbit 五檔複審 0 issues 後 push main；GitHub CI143／37603288446 completed Success，八項必需成功、兩項手動 frozen 工作 skipped。這次 CI 不替代已固定候選的實際驗收。

固定來源 `6f69577` 的 unsigned `CloudHime-0.1.2.0-x64.msix` 已透過 Partner Center 檔案選擇器上傳，後台完成套件解析，保存至產品 `9NH4B9GQ86FL`／Submission 3 `1152921505702037522`。從概觀的「套件已更新」重新開啟，版本 `0.1.2.0`、x64、Windows.Desktop 最低 `10.0.17763.0` 與本機 manifest 一致。套件 SHA-256 延用固定建置／remaining-v4 收據 `2d1294081ea926dc124937bd89487c5a6185d3e7337adb7f556978c5e840da06`，沒有假稱本 UI 步驟重新串流驗 3.9 GB。保存收據 `output/release-20261007-final/store-msix-save-verification.json`，畫面 `store-msix-saved.png`。

Partner Center 在草稿保存時自動以相同支援範圍的高版本套件取代舊 `0.1.1.0` 草稿套件；目前已發布的 Submission 2 與正式 Store `0.1.1.0` 未修改。後台仍顯示 `runFullTrust` restricted-capability approval 警告；概觀明確提示必須更新稅務與支付資訊才能收費，提交認證按鈕 disabled。上傳／解析／保存不表示能力審核、認證或發布已通過，沒有移除 runFullTrust 以規避審核。金融資料由主人親自處理，價格與發行範圍尚待回覆。

OCR 補充對照只變更沙箱 requested vGPU 為 Enable，記憶體仍 4096 MiB、網路與剪貼簿關閉；相同原生探針 MSIX 與 fixture 的 SHA 已核對。真正 AUMID 啟動並確認 package identity，en-US 支援與 BGRA8 bitmap 解碼通過，但辨識仍回 `0x80004005`／零行。辨識後列舉的控制器為 Microsoft Remote Display Adapter；不能將 requested Enable 推論為某個實體 GPU 或驅動已獲驗證，也沒有證據判定產品程式根因。此結果不能當候選 acceptance PASS。Guest packages 0、cleanup errors 空；owned VM 已於 09:59:04 UTC 核對 PID／執行檔／start time 後回收。證據 `ocr-native-aumid-diagnosis/guest-vgpu/output/result.json`、`guest-disposal.json` 與 `ocr-vgpu-comparison.json`。

這次只補文件與外部草稿對帳，正式 EXE／DLL／模型／MSIX 位元組不變，不另做無關重建。三席與獨立仲裁的封存結論仍 blocked，這份補記沒有覆寫報告或假稱新一次正式評論通過。最終 frozen GUI 全旅程、真實設定升級、乾淨 Windows OCR 與 Store 認證／安裝更新仍待完成。CH-T55 保持 Review／Smoke NO／Critic NO，CH-T56 保持 Backlog。


## 定價待確認誤記更正（2026-10-07）

主人指出定價早已決定，回查 `reviews/2026-10-06-release-closeout.md` 與 `output/release-20261006/store-price-decision.json` 確認：NT$249 一次買斷、正式公開可購買後前 30 天 NT$199，NT$249 已保存至 Submission 3。GitHub 免費完整原始碼、Store 付費完整包與原私人預覽受眾保留的政策也已有紀錄。前述「售價／發行範圍待回覆」混淆了已定案政策與尚未設定的首發排程，予以撤回，不再重複要求主人確認定價。

目前只保留實際狀態：首發優惠尚未排程，須按正式公開可購買的起算日落實，私人預覽不啟動 30 天計時；沒有冒稱已保存 NT$199 排程或已正式收費。稅務／支付資料與既有最終驗收、認證／Store 更新閘門仍待完成。這次僅修正文檔與續接 metadata，不修改商店設定、產物或封存評論，也不改寫舊歷史證據。


## 小本本特色與 API 內容政策文案補齊（2026-10-07）

依主人補充，Antigravity Bridge 的 Gemini 已完成四個 locale 的介紹與短文，將作品專屬小本本列為主要特色：搜尋公開資料整理角色、專名及背景，候選經確認後保存本機、自選啟用，供支援的 AI 翻譯參考；公開資料研究需要網路。功能核對 `knowledge_research_service.py`、`knowledge_pack_store.py` 與 `knowledge_prompt_context.py`，沒有把小本本描述為模型訓練或宣稱所有流程離線。線上 API 可能依供應商內容政策拒絕部分或敏感內容，使用者可選本機翻譯，輸出仍取決於模型能力。

同一 Gemini actor 修正初稿 JSON 並交付 V2 完成標記；根整合者獨立標準 JSON／UTF-16 驗證通過，不採用 Gemini 未執行的估計計數。繁中兩 locale 的短文／介紹各為 168／1331 UTF-16 單位，英文 266／3715、日文 184／1850，皆在欄位限制內。Gemini 原稿 SHA-256 `88d57db017a7d32892ada5ec36e1168aadf63d4e0f3a6ef7897f047eb16f8a1e`，獨立驗證見 `output/release-20261007-final/store-notebook-copy-validation.json`。

Submission 3 的四語八個欄位已實際保存並重新開啟，逐字符合 Gemini V2；版本說明、額外授權條款、產品功能、著作權與開發者欄位均與操作前一致。保存收據 `output/release-20261007-final/store-notebook-copy-save-verification.json`，畫面 `store-notebook-copy-saved.png`。公共 `docs/store-copy-gemini-draft.json` 同步新介紹，舊匯出雜湊僅保留為歷史核對，未拿來證明新文案。README 與 Mission Center 同步特色及限制。

此切片僅更新說明與商店草稿，保留既有版本更新項目，EXE／模型／DLL／MSIX 位元組不變。售價照已定案 NT$249 買斷、公開可購買後前30天 NT$199；未送認證、未發布。CH-T55 仍 Review／Smoke NO／Critic NO，CH-T56 仍 Backlog；最終 GUI／真實設定升級／乾淨 Windows OCR 與 Store 驗收門檻仍須實際證據。

## 小本本文案提交的 CI 紅燈處理

`18b923f` 的四份文件已存 Git、CodeRabbit 審查 0 issues、push main 並核對遠端提交。CI146／`37627935271` 的 UI 分組出現 1 failed／89 passed：日文 `test_cooldown_preserves_progress_and_terminal_status` 預期5秒、當次得到6秒，其餘7項必要檢查成功。這次提交未改冷卻實作。獨立唯讀核對與本機原三語案例3 passed，確認測試硬斷言依賴即時 `monotonic`；日文單次讀值的精確成因仍不明，不把它宣稱為已定位產品回歸。

只修改該測試，替換 UI 模組的 clock 綁定、保留原 `perf_counter`／`strftime`，避免污染共用時鐘與 fixture 關閉期限。固定初始時間驗證5秒，明確推進1.25秒後驗證4秒、25%進度與錯誤訊息保留；真正 QTimer active 與結束後按鈕恢復斷言仍保留。完整受影響檔案90 passed，收據 `output/release-20261007-final/ci-cooldown-before.log`／`ci-cooldown-after.log`。正式程式與已保存 MSIX 不變，不以重跑掩蓋原始紅燈。新提交與 CI 結果另存 closeout 收據，尚未據此變更發行門檻。
