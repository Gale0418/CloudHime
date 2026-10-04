# Gemini 全介面文案整合與審查 · 2026-10-05

主人指定雲朵翻譯姬所有產品控制的可見文字交由 Gemini 修訂。透過 Antigravity Bridge 同一 cascade `f1a04aa9-2482-405a-a3dc-40217f2b85ad`，完成繁中、英文、日文文案；Codex 負責接線與驗收。短按鈕、品牌、技術名稱採審閱後保留，沒有為了可愛而拉長所有標籤。

範圍涵蓋 624 個既有三語目錄文字（337 個修改）與 497 個內嵌候選，包含主視窗、設定、提供者狀態、研究提示及外觀。新增 ui_copy.py 集中 OCR 固定說明／安裝結果與快速鍵衝突提示；OCR 面板和實際快速鍵錯誤視窗已接入三語。未知的外部工具輸出與例外診斷、模型／provider ID、翻譯 prompt、使用者內容保持原樣；平台產生的標準文字不屬於產品文案重寫。

精確性複核撤回「選定模型即代表就緒」、不實固定耗時、全面離線與未實作 OCR／快速鍵設定等描述。共用初始化文案改為推論環境，CPU 專用及實際 GPU 模式仍有各自提示。格式參數、HTML 與既有連結核對通過。Gemini 先前的工具授權卡點已排除，採純文字 JSON 接線完成，沒有把 Codex 文案冒稱 Gemini 撰寫。

獨立設定／暫存資料、offscreen、無 credentials 的相關回歸最終 428 passed、0 failed、0 errors、0 skipped。首輪 22 個舊文案斷言失敗保留原始證據，由 Luna 查證並更新，未刪除操作驗證；新測試涵蓋 OCR 三語、品牌與重啟提示、快速鍵錯誤碼，以及未知多行診斷完整保留。CodeRabbit 初審 18 個相關檔案提出 2 Minor issues：英文少冠詞、zh/ja 狀態說明黏字，均查證後由 Gemini 補正文案或確認空白串接；兩檔複審 0 issues。排除模型、DLL、建置輸出及無關 logo，沒有刻意湊足 150 檔。兩次臨時審查 repo 的本機前置失敗亦有保留，未當成遠端審查或通過。

證據位於 output/store-release-20261005-gemini-copy：gemini-copy-provenance.json、gemini-minor-repair-receipt.json、regression-receipt.json／regression.xml、coderabbit-scope.json／coderabbit-review.ndjson、coderabbit-recheck-scope.json／coderabbit-recheck.ndjson、verified-copy-checkpoint.json。最終回歸 XML SHA-256：d71adb11682a4fbe7056138853f57a4e83836cb96712cfc4e7aab24a6baad13e。

本紀錄是來源文案與相關回歸驗證，尚未代表含本輪文案的新 EXE、完整人工操作、MSIX 更新／WACK、正式 24k 評議或 Store 上傳／認證通過。舊 adf8d39 EXE 證據仍只適用原來源；20:13 失敗候選不會復用。CH-T55 保持 Review、Smoke NO、Critic NO；Store 仍為 0.1.1.0。

## CI 清單補正

fe88bab 的遠端 CI 37220102524：七個必要工作成功，core 因新 tests/test_ui_copy.py 未加入明確測試清單失敗，兩個手動 frozen 工作 skipped。已將新檔分配至 UI 組，產品程式未變；相關清單與文案測試結果見 output/store-release-20261005-gemini-copy/ci-inventory-fix-receipt.json。這次 CI 失敗紀錄保留，後續 main CI 通過才作為新的驗證證據。CodeRabbit 審查範圍未包含此一行清單補正。

## 含文案候選與商店草稿

固定來源 fe88bab940c02c7e271fefeea557bc004cb9d580 的新 EXE SHA-256 為 cbbcf0b8f755057115888caa3058b889429692a1092026facda1ef9cb694e842。light/full verifier、375 檔 4,896,209,698 bytes 的 provenance、frozen import、host Windows OCR 兩行、CPU vision 1/1、正常 GUI 20 秒啟動均通過，自己的 GUI／model 程序已清理。CPU vision 期間自然主機負載四筆最高 90%、平均 74.75%；沒有人工製造負載，這不是完整忙碌時操作驗收或翻譯準度提升證據。

main fb36dca 的 GitHub CI 37220416100：八項 required success，兩項 manual frozen skipped。fe88bab 到 fb36dca 只改 CI 清單與此紀錄；218 個 shipping inputs 已以 Git blob 核對 byte-identical，EXE 不因清單／文件補正重建。證據：ci-verification.json、build-ci-source-equivalence.json、frozen-verification-checkpoint.json。

完整 Store 候選 0.1.2.0：MSIX 3,942,297,874 bytes／SHA dabffe8fb2a5b94166a9919a0f35bf91dfe344607f5aecb8a5574604d30c3379；upload 3,940,114,354 bytes／SHA cee584dc409ad23374735d31bd8e10ec8d5dfcf4f2c4f6f25b41d77e98e80af7，暫存 stage 已清理。第一次 MakeAppx 平行封裝回報 0x8007000e，保留失敗紀錄；改用 SDK 自身 /np 序列封裝後成功，未改 payload 或略過驗證。平行記憶體壓力是目前支持的假說，不宣稱已證明唯一根因。Microsoft [MakeAppx 官方文件](https://learn.microsoft.com/en-us/windows/msix/package/create-app-package-with-makeappx-tool) 與安裝 SDK pack /? 已核對。package-attempt1-result.json、packaging-memory-diagnosis.json、package-result.json／package-attempt2.log 保存完整狀態。

Gemini 更新說明已存入 Submission 3 的 zh-Hant-TW／zh-TW／en-US／ja-JP 四份清單並重新開頁核對；長提示描述限定主視窗跑馬燈，未誇大到所有設定。store-copy-save-receipt.json、store-copy-proof-binding.json 與四張 saved 圖保存內容及雜湊；這只修改草稿，套件仍沿用 0.1.1.0，未上傳 0.1.2.0 或提交認證。

新增九張三語 source Qt offscreen 版面圖，visual-copy/final/render-receipt.json 逐張綁 SHA；模型 ready 是 presentation fixture，背景服務與 native hotkey 排除，不冒稱實機旅程。首次渲染輸出後 interpreter teardown 未退出，精確回收本次兩個 renderer PID；改為允許程式自身 cleanup thread 並完整 drain 後正常 exit 0，首輪中斷證據保留。前兩份視覺準備僅為 helper 前置／fixture 校正，不是新的產品崩潰證據。

完整人工暫停保留字幕／繼續、框選取消、忙碌時 Settings／Stop 與正常關閉仍待最新 EXE 的實機結果；新候選沙箱更新／WACK、正式 24k 評議與 Store 認證尚未通過。歷史 Qt 原生 invalid wrapper 根因仍未確定，這些局部通過不作全面根因結案。CH-T55 保持 Review、Smoke NO、Critic NO。
