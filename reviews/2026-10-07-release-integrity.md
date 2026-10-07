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
