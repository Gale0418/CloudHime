# 2026-10-04 新版 Store 發行 checkpoint

更新時間：2026-10-04T15:26:27+08:00。任務 CH-T55，狀態維持 Review；CH-T56 等實際商店更新結果，不提前 Closeout。

本次從 Git 來源 `014e0e77458022116e74ca9a6609c47d64f26405` 的獨立快照重建；產品程式與 `eb5ee34` 相同，後續差異為診斷文件。建置使用 Python 3.10.11、PyInstaller 6.18.0，40 個 production 相依版本符合 provenance。建置完成於 14:55:07 +08:00，候選 EXE SHA-256 `19df640299d1c6502b5e2ee93ed0833571cdf3c63838bb67fb113ef6629ccdba`。輸出位於 ignored `output/store-release-20261004/`，不含主人既有設定、金鑰或未追蹤新 logo。

本機驗證：light/full payload 與 provenance 通過；完整包 375 檔／4,896,195,318 bytes、兩個固定 SHA 模型及四份授權文件。frozen import 通過；Windows OCR 固定文字圖 1 張／2 行通過；純 CPU Vision 技術功能呼叫 1/1 通過；隔離 GUI 啟動存活 20 秒通過，測試程序及其 helper 由 harness 收回。這不代表辨識／翻譯準度 promotion，也不代表正常 GUI 的框選→OCR→多模態→泡泡流程已驗收。

首次完整包檢查失敗於模型授權文件的位元組差異；四檔內容在換行正規化後完全相同，改用本次 immutable source 的原始位元組後重新驗證通過。首次 OCR smoke 誤用沒有文字的品牌背景圖而失敗；改用固定英文／日文 fixture 後通過。兩次失敗均保留本機回執，不刪除或計入通過。

CodeRabbit：本輪一次送審，35 個從前一 frozen 來源到本次來源的程式／測試檔，約 1 MB；未上傳模型、runtime、dump、個人設定、憑證或歷史大文件。CLI exit 0、complete event `findings: 0`，reviewedFiles 與 scope 相同，0 issues。每小時 3 次／每次 150 檔限制仍適用。

商店：2026-10-04 從 Partner Center 現行套件頁確認 Submission 2 為 x64 0.1.1.0。已依新版發行授權建立 Submission 3（ID `1152921505702037522`）草稿；沿用免費／240 市場／CloudHime Private Preview 私人對象，未改公開範圍。新版 0.1.2.0 正在以受控 Store 身分封裝；目前尚未上傳新套件、送認證或發布。

GUI 能力限制：新 EXE 的空白隔離 profile 已啟動，日誌確認 Windows OCR 可用，AX 可讀主介面；Windows Computer Use 畫面擷取回報 `FrameArrived timed out`／`window capture timed out`，點擊無有效 geometry。恢復仍失敗，已清理本輪 PID 52820；不把 source audit、AX 可讀或 frozen smoke 當成完整操作通過。原 Store 安裝與主人設定未動。

正式評論額度：主人本輪明確採用 CH-T55 total 24,000 tokens、三名 Luna critic 與獨立 arbiter 各 4,000、integrator 8,000、每席 8 次工具／合計 32、評論階段 30 分鐘，含必要修正複核，converge。待成品與證據固定後派送，不沿用其他任務預算。評論、完整 Store package install/update/WACK、Microsoft 認證與實際 Store 更新結果尚未完成。

原 Qt retrieveMetaObject NULL 最初失效物件仍未確定；已確認的 event-filter 借用引用釋放鏈與三項生命週期修正見 `reviews/2026-10-04-qt-native-diagnosis.md`。新版 frozen 檢查通過不等於全部歷史原生崩潰根治。

本機證據：`build-result.json`、`source-manifest.json`、`verification-result.json`、`verification-initial-model-terms-failed.json`、`verification-wrong-fixture-failed.json`、`windows-ocr.json`、`cpu-vision.json`、`gui-result.json`、`coderabbit-scope.json`、`coderabbit-review.ndjson`、`coderabbit-receipt.json`、`store-draft.jpg`。沙箱與封裝進行中的紀錄另存其子目錄，待完成再追加。

## 2026-10-04T16:08:19+08:00：乾淨沙箱 OCR 失敗與候選撤換

來源014e0e7候選已完成封裝，MSIX SHA-256 `ca50072a169497914635c0607c03e572b071831b2b8d69105049de757768752e`，upload SHA-256 `ff86073c678353b5affaa623b835893728573b16d644d8472e9ef588376ad6cb`，stage 已清理；但這份候選因以下失敗撤換，未上傳，不能作為最終發行產物。

全新斷網 Windows Sandbox 初始無 CloudHime profile、無 Python／python3／py／pip／Conda／Ollama。相同 EXE SHA 的 frozen import 通過；Windows OCR smoke exit2，因此 CPU Vision 與 GUI 存活未執行。失敗證據保留於 sandbox/output/result.json 與 windows-ocr.json。owned client21552／launcher51528 收回，沒有動原 Store0.1.1.0。

第二個不複製產品 payload 的2GiB沙箱直接查原生 OcrEngine：AvailableRecognizerLanguages只有en-US；en-US supported／engineCreated=true，ja-JP與zh-TW=false；TryCreateFromUserProfileLanguages=false。Get-WindowsCapability inventory回報path not found，不能宣稱語言功能清單已成功盤點。probe任務status passed只表示診斷完成，不是產品smoke passed。owned client16972／launcher53628已結束、remaining0。

讀取來源確認：日文不支援時只嘗試profile語言；profile無引擎時直接回空OCRResult，worker接著呈現NO_TEXT。新fake測試已證明三項原始失敗：已安裝英文引擎未被選到、全部引擎None未回錯誤、初始化例外被吞掉。最小修正與worker錯誤傳遞測試仍在執行；完成後會固定新來源、重建EXE／MSIX並補審，不能將本機兩行OCR通過抵替這項乾淨環境缺陷。Microsoft API也明訂無可對應profile OCR語言時回null：[官方契約](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine.trycreatefromuserprofilelanguages?view=winrt-26100)。

正常GUI旅程仍未完成。正式評論尚未派送，保留主人已批准的24k／32工具／30分鐘額度；尚未開始計時，不以這次修正充作正式critic。CH-T55維持Review並將當前Smoke改NO，CH-T56不Closeout。商店草稿更新說明同步中，未送認證／發布。

## 2026-10-04T16:19:36+08:00：OCR 最小修正與來源驗證

已完成已安裝OCR語言後援、初始化錯誤傳遞、三語前置條件提示與正常空辨識保留；任一後端／候選有正常空結果時仍為NO_TEXT，成功文字後援仍優先。只在全部OCR嘗試失敗且均為Windows引擎初始化錯誤時顯示Windows語言提示，其他錯誤顯示一般辨識錯誤。引擎初始化在背景辨識與既有lock內進行；成功引擎沿用，失敗不永久快取，讓環境修好後可再試。

Luna初始修正15案通過，其回執為stdout轉錄而非原始JUnit。主代理整合另先重現2案：generic故障仍顯示沒有引擎、初始化失敗快取妨礙後續語言支援恢復。第一個byte guard因預期CRLF與實際LF不符而拒絕寫入；當時再驗證仍2failed，該失敗保留、未計入通過。改用逐行位元組保護完成最小修正後，17案最終通過，actual JUnit與stdout保存為ocr-main-green-final.xml／.log，來源SHA記於receipt。git diff --check通過。未重跑未受影響的215 UI案例，也未以這17案聲稱正常GUI、frozen EXE或Sandbox已驗收。

下一步固定這份來源，5個程式／測試檔focused CodeRabbit，再重建候選至output/store-release-20261004-ocr-fixed/。兩個大型模型只以同磁碟hardlink帶入新候選，完整verifier仍重新檢查固定模型SHA及授權原始bytes；避免再拷貝相同3.3GB模型。正式評論仍未派送／起算。

## 2026-10-04T16:45:54+08:00：CH-T55 新候選本機反證與 GUI 實測進度

新來源 `2ee51b9999e5462b9f2acdaca650ae0699855d7f` 已推送 main；GitHub push CI `37189052512` 為 success：8 個必要工作成功，2 個手動 frozen 工作 skipped，不能計為實際 frozen pass。5 個 OCR 程式／測試檔 focused CodeRabbit 16:23:05至16:24:25完成，0 findings；scope SHA 與不可變來源完全相符，回執 `review-binding.json`。

新 EXE SHA-256 `cdd66015fbe7f568e6af7cbf446eaece2dec6e633af82c6a989432d694f9c099`，16:29:57重建完成。light/full verifier、40-component provenance、固定模型 hash、frozen import、Windows OCR兩行與獨立20秒GUI存活通過。CPU Vision exit2，故整體 `verification-result.json` 為 failed／stage cpu-vision；固定模型與runtime相同不足以證明只是資源問題。目前 generic smoke 輸出吞掉根因、原harness清除隔離profile；已準備 source diagnostic 保存redacted bounded stderr／階段耗時，不能把來源diagnostic替代frozen驗收。未在GUI模型操作同時跑VM或另一模型。

一般GUI仍由主人操作驗證。16:42:53截圖顯示已框選測試圖、當前Google Translate，UI顯示rate limited；不能據此證明實際Google帳號配額用完或翻譯成功。已引導切換Local Gemma、開啟本機多模態與CPU-only。第一次隔離GUI PID51480正常退出code0；主人要求重開後，同一獨立profile PID1436再啟動，完整設定／翻譯／暫停旅程待回覆，不宣稱通過。

Submission3 四語更新說明已按Save並返回overview；zh-tw與en-us重新開頁確認持久化，ja-jp與zh-hant-tw仍待重讀。沒有上傳新package、送認證或發布；私人／免費設定保留。正式評論尚未派送／起算，使用主人核准24k tokens、各席4k、整合8k、各席8工具／合計32、30分鐘。CH-T55 Review／Smoke NO／Critic NO；CH-T56不Closeout。

證據：`output/store-release-20261004-ocr-fixed/` 的 build-result、ci-result、review-binding、verification-result、windows-ocr、cpu-vision、gui-liveness、manual-gui-result、manual-gui-reopen-result、vision-triage；主人截圖 `D:/Downloads/2026-10-04 16 42 53.png`。新MSIX尚未封裝／驗證，不使用前一撤換候選。

## 2026-10-04T17:03:17+08:00：主人實測發現目標語言缺陷，候選再次撤換

主人16:48:36截圖：英文UI、Local Gemma model ready；英文句被譯為中文、日文保留原文。isolated profile為ui_language=en／use_gemma_translation=true／provider_chain local_multimodal／local_multimodal_enabled=false，實際走本機純文字模式。正常關閉pid1436 exit0，沒有完成自動掃描暫停／繼續完整旅程。主代理起初口頭說UI與目標語言分開，與source不符，已向主人更正；localization契約en→en、ja→ja、zh-TW→zh-TW。

已查證兩個單句provider呼叫漏傳worker.translation_target_lang；provider方法預設zh-TW覆蓋registry已設en。Google與Gemma兩處明傳target_lang；新增en／ja兩provider四例RED全失敗，GREEN及目標快取隔離5案通過。主代理整份worker matrix141案通過（actual JUnit／log／SHA）。UI rate indicator將本機純文字模式誤標Google也已RED重現；修正顯示Local Gemma3並保留loading／ready／failed既有進度。4案focused與完整UI smoke67案通過。共208個不同worker／UI案例通過；不表示fresh EXE／Sandbox／Store gate通過。

原2ee51b9 EXE因上述GUI缺陷撤換，不上傳。日文特定句為何保留仍須新EXE實測，不以舊Google TooManyRequests warning直接歸因該張圖。本機Vision源碼診斷（相同固定runtime／模型、不是frozen驗收）在90秒health deadline失敗，redacted stderr停在模型載入；原production上限240秒，因此獨立240秒診斷正在執行，保留90秒反證，不宣稱根因已完全確定。

四份Store更新說明（zh-tw88、en-us4、ja-jp17、zh-hant-tw480）均重新開頁確認持久化；仍只是Submission3草稿，未上傳／認證／發布。package sandbox helper及source-derived hardlink staging wrapper已準備但未運行安裝閘門；只在guest副本做自簽、update與WACK，不動原Store。新產物將另存output/store-release-20261004-target-fixed/，固定新source、4檔CodeRabbit、重新建EXE及受影響gates。

CH-T55保持Review／Smoke NO／Critic NO。正式24k／32工具／30分鐘評論尚未派送／起算。證據：target-routing-red／green.junit.xml、target-routing-fix-receipt、worker-regression.xml／log／receipt、local-indicator-red／green及receipt、manual-gui-reopen-result、vision-diagnostic/result、vision-diagnostic-240/，均在output/store-release-20261004-ocr-fixed/；主人截圖D:/Downloads/2026-10-04 16 48 36.png。

## 2026-10-04T17:15:32+08:00：CodeRabbit minor 修正、測試替身與真實 CPU 壓力條件

來源b10d3e5的4檔CodeRabbit17:05:52至17:07:01完成，提出1個minor：本機Vision未ready時indicator錯讀local_model_state覆蓋starting/progress。讀source與RED兩案確認有效，已共用local runtime state選擇，與engine summary一致；focused6案及full UI smoke69案通過。先前4檔0-finding binding assertion拒絕這1-finding結果，沒有生成passed binding，不把提出問題的審查說成0問題。修正需新來源，原b10 EXE收集階段已終止owned PyInstaller27496／parent25568正常保存非零build-result；build-cancelled.json記原因，產物不宣稱建置成功。

GitHub b10 push CI37190933923為failure（7 required成功／OCR組失敗／2manual skipped）：tests/test_cloudhime_workers.py兩個__new__替身未建立translation_target_lang，fake translate也漏keyword。只補兩替身初始化與keyword契約並驗明收到en，保留原模型／provider attribution驗證；產品初始化已具target_lang，沒有修改正常流程迎合stub。完整CI OCR九檔295案通過，JUnit／原始log／workerSHA保存；加最新UI69，共364不同案例。這次main commit仍須新CI確認。

主人指出其他使用者會同時玩遊戲，明確要求以當前忙碌CPU當壓力條件。17:12左右aggregate CPU讀值100%，freeRAM約8.97GiB；只有單次取樣，不能歸因某程序或代表整段負載。將在fresh frozen功能驗證期間採集aggregate CPU與freeRAM；不額外飽和CPU，不停止其他工作。240秒source診斷成功：startup158.761秒、request14.528秒、CPU image1/1。這支持90秒閘門太短；尚非新EXE／乾淨Sandbox驗收。下一次建置採BelowNormal優先權，產品測試保留正常priority／原production240秒啟動契約，重型gate排隊。

Mission Center0.5.2本地未包附critic_contract.py；從插件作者官方repo取得相同immutable094c367556b56de1b6e9541ac782552978df4c8c的純JSON唯讀validator（預設分支與該commit內容相同、import僅stdlib、無network/subprocess/write），存ignored critic_contract.upstream.py。這是advisory record驗證補件，非Rust生命週期fallback／插件安裝，尚未宣稱正式critic contract通過。

新候選將存output/store-release-20261004-final/；尚未上傳、認證或發布。CH-T55 Review／Smoke NO／Critic NO；正式24k／32tools／30min尚未開始。Evidence：output/store-release-20261004-target-fixed/coderabbit-review.ndjson、local-indicator-delta*.xml／stdout／receipt、ocr-group-fixture-regression.xml／log／receipt、ci-ocr-failed-excerpt.log、build-cancelled.json；source diagnostic在ocr-fixed/vision-diagnostic-240/result.json。
