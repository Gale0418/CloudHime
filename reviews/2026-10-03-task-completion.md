# 2026-10-03 任務收尾 checkpoint

本輪依使用者最新授權恢復剩餘任務，維持已驗收的翻譯與純雲朵。產品來源仍是 `bff0c4f005b9ebec7d3e00450f4ddfd00b31d53d`；沒有新功能、依賴或素材變更，未重建未改動的套件，也未重跑已通過的 238 個案例。未採用的人物稿不列入提交。

## 已完成

- **CH-T116 相容性調查 Done**：歷史 Qt 原生崩潰尚未修復；正式版本維持 Python 3.10。Python 3.13 的隔離 OCR thread-safety 本次 5 passed in 2.24s，不外推完整相容性。明確支援邊界見 [python-support](../docs/python-support.md)。有效 completion passport 經 Rust Review→Done 驗證。
- **CH-T65 採用評估 Done**：三個新候選暫不採用，既有 opt-in 漫畫、Knowledge 與手動 Research 保留。Luna 的真實唯讀評估經 Codex 核對；修正 grid accepted 與 anchor recall 混用後，保存 [需求、效能、隱私／授權與維護成本決策](2026-10-03-feature-decisions.md)。沒有執行模型／GPU／外部 API，也沒有宣稱產品測試通過；本次驗證是文件與來源核對。
- **CH-T43 舊證據對帳**：原 passport 的任務摘要與舊列一致；補回已存在的 2026-09-06 owner product-path paired GPU report，更新摘要並核對 doctor。固定 4 cases × 5 repeats 的 accuracy/stability gate 通過；candidate p95 20.81 秒，baseline 5.44 秒，所以不宣稱速度提升、不開啟新預設。舊 8/24 中止紀錄保留。
- **T117 契約入口恢復**：安裝版已將 validator 遷移至 Rust，實際可用命令為 `mission-center critic --root . --record <path>`。正規化舊評議的 limited record 已得到 `valid=true, errors=[]`，這不等於 passed closure。sealed flow report 的 Worker SHA 填錯已定位；保留原報告，不回溯覆寫。
- **雲朵資產來源綁定**：兩個現有 MSIX 各五份 PNG 逐檔與凍結來源比較一致，補齊 package→source 證據。只讀取 PNG entries，未重算數 GB 套件整體 hash；既有整體 hash 見 [發行紀錄](2026-10-03-ocr-cloud-release.md)。

T116/T65 僅為低風險、非感知的調查／決策文件，本輪未選 Full/Lite；各自記錄 skip 理由並經原生 validator 驗證，沒有降級已選 Full 的 T117。

另外完成一次受控失敗顯示驗收：primary mock ValueError 與 Google mock TooManyRequests 各呼叫一次，真實 `OCRWorker.run_scan_once` → controller generation slot → `OverlayWindow.update_bubbles` 建立的 `TransBubble` QLabel 顯示原文 `Hello`，並繪製成 96×42 PNG；狀態為 rate-limited，非 done。使用真正的隔離 persistent cache，production lookup miss、remember 呼叫 0 次、檔案未建立，preferred/HUD memory 也未寫入。初版 harness 的固定空值查詢不能證明 cache 未污染，Codex 查出後已改成真實 cache 與寫入 spy，只重跑這一必要案例。

這是 Python 3.10.11 的 mock provider／deterministic OCR／offscreen Qt 驗收，沒有 live Google、實際網路失敗或 Windows 實體桌面觀察；不取代使用者的實機成功流程驗收。六份涉及 source/test 檔只做 CRLF→LF 後，working／frozen／Git bff0c4f 內容一致。封存證據位於 `output/mission-center-evidence/ch-t117-delta-20261003/`，delta-snapshot SHA-256 `1766cd491457a9c23d8c0d3c935f395260ccd8e87ff1bd82b761afc15fa2728e`；沒有改產品程式。後補證據等待正式差異評議，尚未回溯改寫 sealed findings。

## 發行與待完成項

Chrome 使用既有登入工作階段唯讀核對 Partner Center。CloudHime 的現行 Submission 2 套件為 `CloudHime-0.1.1.0-x64.msixupload`、x64 `0.1.1.0`，未見正在編輯的 submission。這不證明所有歷史上傳都沒有使用 `0.1.2.0`；本輪未建立更新、未上傳、未發布。既有 Store 安裝為 `WindSheep.CloudHime`、0.1.1.0、Store 簽章及 Status Ok；新預覽的使用者驗收不冒充新 Store 版本驗收。

使用者授權管理員驗收後，經 Windows UAC 執行原始 `output/task-completion-20261003/run-admin-development-gate.ps1`，SHA-256 `1f64a65ef691bc4d92943b734e3b2c1be77fb44f47592c7a0fb389dbdafed9df`，執行後沒有改寫。development light MSIX 只簽副本；簽章驗證、WACK XML `OVERALL_RESULT=PASS`、實際安裝與啟動、移除均通過。原始 unsigned 與 Store 候選不納入此次簽章操作。Windows Appx 驗收使用原生 Windows PowerShell 5.1。

獨立查核確認本輪開發 package、CurrentUser My 憑證、LocalMachine TrustedPeople 信任與公開 CER 已移除，既有 Store `WindSheep.CloudHime` 0.1.1.0／Ok／Store 保留。原清理腳本未使用 `-DeleteKey`，因此不能由憑證已移除推論 backing private key 也已刪除。公鑰比對查核遇到 managed lookup `NTE_BAD_KEYSET`，結果不完整；追加唯讀管理員啟動由 Windows 回報 UAC 取消，使用者表示沒有看到提示。沒有執行私鑰刪除，也未重複要求 UAC。證據：[管理員與 Sandbox 驗收](2026-10-03-admin-sandbox-acceptance.md)。

全新 Windows Sandbox 的完整 frozen dist 驗收亦通過：Windows 10 Enterprise 19041、初始沒有 CloudHime profile；python／python3／py／pip／conda／ollama 指令均未找到。相同 EXE SHA-256 經核對，真實 frozen import、隨包模型與 projector 的 CPU Vision 1 image／1 case／1 success，以及 20 秒 GUI liveness 全部通過。使用隨包公開美術 fixture；網路、vGPU 與剪貼簿停用，沒有映射主機憑證或使用者設定。測試程序及本輪 Sandbox launcher/client 已精確清理。這是完整 frozen dist 的乾淨 Windows 技術覆蓋驗收，不是 GPU、準確度提升或 Store MSIX 安裝／認證證據。

T117 追加差異評議封包已準備，僅核對錯誤 SHA 引用、後補人眼驗收、資產綁定與失敗處理證據，沒有新一輪全面找問題。預算請求為總 4,000 tokens／每席 800／整合 800、總 20 工具／每席 3、10 分鐘；核准尚未收到，因此未派送四席正式 closure。原評議的三個未收斂項保留，limited 不寫成 Done。依安裝版 Mission Center `references/completion-critic-council.md`「Resource budgets and platform limits still apply and are not reset per wave.」，額度不會按新 wave 自動重置。

CH-E6 的 21 個子任務均 Done，已更正 T43 舊狀態；Epic 尚待範圍收尾紀錄。CH-T55 保留 Review，CH-T56 的雙軌手冊已準備，但它與 CH-E7／CH-E8 仍受實際發行 gate 與依賴限制；不以文件完成代替 Store 更新驗收。

## Antigravity 協作限制

使用穩定 request `cloudhime-task-completion-crossaudit-20261003-1045`／cascade `0226b383-ada9-424b-b1ed-8fdb1f0e9e59` 送出只讀跨領域核對。fresh health probe 成功，但該 cascade 的 trajectory 仍 HTTP 500；receipt 為 DELIVERY_UNKNOWN，`may_handoff_read=true`、`may_handoff_write=false`、`remote_may_resume=true`。沒有可驗收的 Gemini 結論；保留其獨有 `gemini-audit.md` 寫入權，不重送新 ID、不重啟共享服務、不把超時當完成。Codex/Luna 的其他證據工作使用各自檔案。

## 恢復順序

先讀本 checkpoint、管理員與 Sandbox 驗收紀錄及 `output/task-completion-20261003/closure-review-packet.md`。development WACK／安裝與完整 frozen dist 乾淨 Windows gate 已完成，不重跑；私鑰查核維持未確認，不以廣泛掃描或刪除補洞。正式差異評議仍須等待明確額度核准，再處理 T55 完整 Store 候選的 package gate、版本核對與具體上傳確認。最後完成 T56 及 E7/E8 的依賴收尾。原產物與測試日誌均保留，不需要重新建置未變更的來源。
