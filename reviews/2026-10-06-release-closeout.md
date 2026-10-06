# 2026-10-06 發行候選與剩餘門檻

本輪產品來源為 `8792e8ac2b5dc385ffc6701afea755f4dcf377c7`。main `20f7226` 的 source-only 政策修改僅影響文件、CI、批次發行流程與測試，未變動此候選編入的產品內容；候選沒有改標為後續來源。差異清單與綁定見 `output/release-20261006/policy-payload-equivalence.json`。

已通過 457 個影響範圍來源測試、19 檔 CodeRabbit 零 issues；政策切片另外 74 passed、19 deselected，以低風險發行步驟刪除記錄審查 skip。不是全專案測試，也沒有以政策測試取代正式發行驗收。

新凍結候選完成 light/full provenance、375 檔／4,896,211,381 bytes 完整模型包、import、Windows OCR 兩行、CPU 圖像翻譯 technical coverage 1/1，以及 GUI 啟動 20 秒。EXE SHA-256 為 `aab1eb4adcc1b6e87f60dd2fa8e1e39b981c6c4d942e49e9253eefc318806685`。這是主機隔離 smoke，沒有冒稱新乾淨機、真實設定升級、GPU品質或完整人工GUI驗收。`verification-result.json` 保存原始結果。

GitHub 已依主人批准移除 V3.1／V3 的 CloudHime.zip、V2.2／V1.0 的 CloudHime.exe。移除前四份原檔已核對 metadata、大小及 SHA-256，保存在 `output/release-20261006/github-binary-backup/`。公開 API 對帳剩餘 binary assets 為零，版本紀錄與自動原始碼 tar/zip 保留；receipt 為 `github-source-only-receipt.json`。沒有將新 EXE／模型包發布至 GitHub。

Store 草稿 Submission 3 唯讀可見套件 0.1.1.0；0.1.2.0 候選封裝中。主人定案 NT$249 買斷、正式公開可購買後前30天 NT$199，Apache 2.0保留署名且不限制合法再散布。TWD 249已存草稿，首發排程因公開上市日期未定而未設定；私人受眾保留。未上傳本輪候選、未提交認證或公開發布。截圖與回執見 `store-price-249-draft.png`／`store-price-decision.json`。

新增 NOTICE／AUTHORS.md／BRANDING.md，以及 spec、build必要檔案、dist preflight要求；55個相關打包測試通過、12 deselected。測試cache有既有目錄寫入權限warning，沒有影響案例結果。產品Python與既有EXE不變；下一份署名包須以新來源組成、核對所有沿用產品檔案並保留原始EXE建置來源，不把它冒稱重新編譯或沿用未核對的套件結果。

署名資源候選已在 `output/release-20261006-attribution/` 組成：compiled source維持8792e8a，assembly source為297d822，105份產品／資源Git blob一致；原始凍結來源檔與manifest雜湊另核對，文字檔僅明列LF／CRLF等價。NOTICE等三檔以297d822來源加入，EXE不變。378檔／4,896,213,165 bytes完整dist及新告知檔雜湊驗證通過，原EXE功能smoke明列沿用且未重跑。官方MSIX可直接上傳，因此本輪不另產生outer upload ZIP；舊封裝pipeline在完成MSIX後因候選被取代而精確取消冗餘ZIP，回執記為superseded，沒有冒稱完整packaging PASS。

297d822的CI run37475737487有兩個測試環境失敗：msix-contract假資料未加入NOTICE；core的dependency-free provider替身漏了新`_target_language_lock`。後者本機-x重現ImportError後修復；CI foreach告知清單補齊，115個相關測試通過、12 deselected。CI／test fixture改動不影響產品Python、模型、EXE或既有候選來源，不需重新編譯；尚待修正後的CI回傳。不是將不可重現原生崩潰視為新bug，也沒有以重跑掩蓋錯誤。

四份Store清單（zh-tw／zh-hant-tw／en-us／ja-jp）已保存免費原始碼／官方預建包互導、一次性購買、雲端API費用另計、Apache2.0與維護者說明；逐份重新開啟後與保存內容完全相同，原介紹、影像、copyright與開發者欄位保留。回執 `store-copy-draft-receipt.json`，僅草稿，尚未送認證。

CH-E6 已依既有 21 子任務原始證據核對、current passport 及 Rust 逐格轉換完成；詳見 `2026-10-06-e6-closeout.md`。CH-T55 仍 Review，CH-T56／CH-E7／CH-E8 依正式發行結果保留未完成。新 MSIX、安裝／更新／WACK、完整人工 GUI、真實設定升級、正式發行評議及私人預覽認證各自尚待完成，舊候選的通過結果不能替代本輪候選。
