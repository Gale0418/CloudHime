# 2026-10-23 全面抓蟲與自主驗證

本輪由 `a2a3c6d177549bd53962735ab1e139a02331b63c` 開始，追蹤 CH-E12／CH-T118～CH-T120。主人授權任務優先、不限制本次評論 token、席次工具或時間；採三位獨立評論者與另一位獨立裁決者。無 P0／P1 後停止擴大挑剔，所有已確認的低優先問題仍須修完。本輪已完成來源與本機隔離 EXE 技術驗收，正式評論收斂通過；沒有發布 Store 或上傳二進位附件。

## 已確認問題與修正

- Google 單筆或合併批次超過 4,999 字元會失敗：傳輸層在派送前拒絕超限輸入，provider 依字典處理後長度拆分，保留順序與分隔；整次成功才新增快取。每次請求前後檢查取消，HTTP 限流等傳輸錯誤保留給上層處理。
- 截圖模式將多段字幕合併顯示；暫停時原本會用合併結果覆寫原始位置。現在保留原始 capture boxes，只有可見串流確實不同時才保存新結果。
- 重新框選後取消原本會丟失字幕與掃描狀態。現在取消會恢復原字幕及自動／暫停狀態；確認新範圍仍清除舊字幕。
- 發行來源證明 staging 在複製／驗證失敗時會留下不完整目的地。改成同父目錄暫存、完整驗證、Windows 不覆寫原子改名；失敗清理本次暫存。現在拒絕既有空目的目錄；已查生產呼叫者會先清除舊輸出，未找到依賴舊行為的呼叫。
- 跑馬燈每 30ms 重算全文字寬。改成快取，文字／字體／樣式改變時失效。相同長文字 5,000 次更新、五次測量，median 由 1,017.86ms 降為 23.35ms。這是固定微型測試的更新成本，並非整體翻譯速度或遊戲 FPS。
- 氣泡長譯文與浮雕大字在相鄰框會遮住前一段正文：保留原始擷取座標與字級，增加有限候選的局部碰撞避讓，串流與完成結果走相同路徑。初版修補曾使 60 框搜尋接近 980ms，已改為最多 12 個鄰近衝突、97 個候選及無碰撞快速路徑，分散框量測降至 19.79ms；沒有把修補途中引入的成本包裝成原產品改善。

## 獨立協作與反證

Gemini 3.8 Flash High 經 Antigravity Bridge 同一個 cascade 完成 UI 控制流程稽核，原稿保存在 `output/full-audit-20261023/gemini-ui-audit.md`。三項主張中，取消框選問題經查證成立；「overlay 永久隱藏」由 `update_bubbles` 內恢復可見反證駁回；「setChecked 觸發 toggled 遞迴」由實際連接 `clicked` 反證駁回。未將模型推測直接當缺陷。

## 自主驗證與限制

初始 inventory sweep 涵蓋 core、OCR、runtime、UI、benchmarks：1,939 passed、2 failed、6 skipped。測試修改與 sweep 重疊，因此不冒稱這是不可變最終版本。兩個失敗均保留原始 XML：一個是新加入的截圖暫停重現；另一個是工作目錄舊 `dist/CloudHime` 含現行規則禁止的 Qt addons。沒有放寬白名單或刪除失敗紀錄，改用隔離建置的新 EXE 驗證。

已完成的受影響重驗：Google／worker／scan 六檔 375 passed；UI／marquee 110 passed；來源證明 17 passed、2 skipped（Windows symlink 權限）。這些集合有重疊，不相加當不同測試總數。初始 RED、後續 GREEN、微型量測與封裝證據皆在 `output/full-audit-20261023/`。

最終測試 identity 對帳涵蓋現行 CI 清單全部 1,972 案：1,965 passed、1 failed、6 skipped，沒有缺漏或多算已被參數化取代的案例。唯一失敗是上述舊 root dist，保留原始證據；新隔離包另跑正式 preflight，不把舊失敗改寫為通過。這是初始 inventory 加受影響重驗的去重台帳，並非一次不可變的全套全綠。最新 Google suite 113 passed，字幕幾何 12 passed、三模式控制 29 passed、產品旅程 107 passed，皆已納入去重數字。

自主 UI 矩陣涵蓋繁中／深色／氣泡、英文／淺色／截圖、日文／深色／浮雕三組，透過真實 Qt 控制項訊號驗證字級、位移、開始／暫停／繼續、重新框選取消；不是所有語言與模式的笛卡兒積。可讀 48pt 浮雕修前／修後圖使用產品字型初始化；早期無字型 tofu 圖只作歷史幾何記錄。正式字型密集串流以 1920×1080、每秒 10 次更新、每組 20 次：30／60 框 handler 最慢 42.58／76.94ms，Qt heartbeat 最大間隔 43.04／86.51ms，handler 超過 100ms 均為 0。此合成測量不代表實際遊戲 FPS。

CodeRabbit 三次均遵守每小時最多三次、每次最多 150 檔：11 檔初審一項相容性提示以生產 caller 反證；2 檔第二次提出浮雕與密集串流，前者查證修復、後者量測補齊；最後 2 檔差異複審 0 findings。第二次 runner 歷史 metadata 誤寫 3 檔，已用實際 scope SHA／CLI reviewedFiles 補更正 receipt，沒有多啟動一次審查。

最終隔離 EXE 位於 `output/full-audit-closure-20261023/dist/CloudHime/CloudHime.exe`，SHA-256 `a9030c980323bf1bc0238dd348b276d28da521c08509997a31b90cdfecc9935b`；建置來源 manifest SHA-256 `af0540f61ea4ed8659129fb7a3626c9fc3fbf2290f00a28160646e39e2984d99`。已通過 light preflight、frozen import、真實 Windows OCR（1 圖／2 行）、20 秒啟動存活檢查；full preflight 也通過：1,563 檔、4,831,126,476 bytes、2 個固定雜湊模型；真實 frozen CPU Vision 為 1 圖／1 案成功，technical coverage 不等同翻譯品質基準。測試啟動的 CloudHime／llama 程序已退出。原始碼公開政策與既有 Store gate 不因產生本機技術預覽而改變，未上傳二進位附件。

原生桌面控制工具目前不提供此工作階段的 Qt 視窗操作，因此增加隔離設定、Qt 真實事件與訊號、故障注入、offscreen render、frozen EXE import／OCR／啟動等可自主驗證項目。Mock 翻譯不等於 live 模型品質；offscreen 圖不等於實際遊戲、不同 DPI 或乾淨 Windows 實機通過。既有 Store 驗證／稅務／認證缺口仍由 CH-T55 獨立追蹤。

## 公開作品參考

透過 GitHub 與 Chrome 查閱 [LunaTranslator 原始專案](https://github.com/HIllya51/LunaTranslator) 及其 [OCR 功能文件](https://docs.lunatranslator.org/zh/ocrparam.html)、[OCR 引擎文件](https://docs.lunatranslator.org/zh/useapis/ocrapi.html)。可參考的設計原則包括線上／離線引擎清楚分離、字幕與底層互動互不干擾、避免重複 OCR，以及以頻率／畫面變動控制工作量。CloudHime 已有 frame gate、cache 與背景 worker，本輪用既有測試核對，不為對齊功能清單加入不相關引擎。上游 GPL-3.0；本輪沒有複製其程式碼、素材或新增依賴。

## 獨立評論收斂

三位 Luna 評論員分別負責操作流程、視覺與可讀性、可靠性／成品驗收；獨立第四位裁決員在三份報告封存後才閱讀。初輪實際指出 bubble 正文遮擋 P2，升級理由與原 P3 意見均保留。無 P0/P1 後只清理已確認問題；包含浮雕與修補引入的搜尋成本都已修完，沒有以額度或輪數耗盡當通過。

最終快照 `CH-T120-full-audit-final`／SHA-256 `011c965408a0ec41ea288cec0f9d76f591d75373f1f800ce592bad0885466f4b`，parent 為初輪快照；334 項內容雜湊逐項核對。四席同一 final snapshot 完成，原始碼／影像／XML／EXE 綁定一致。主席完整台帳 12 項：7 fixed、5 具體反證駁回，無未修 P0/P1 或已確認範圍內 P2/P3；Rust critic validator valid。原始 limited 紀錄保留，不改寫歷史。

| 席位 | 封存報告 SHA-256 |
| --- | --- |
| flow | `0a70de9f06b2050c517b8e9086d717e88ac3f5a208e9fdb51e6c7246fbf970ba` |
| visual | `e3f6894dbfff6746aeecc596bd482c4b57b00b39308c94e3db55b71cfc63c0da` |
| reliability | `fe0f3b580d0fb6c27b3068c4ee555f54814bb591ba1785b6d7fc53eacffee11e` |
| arbiter | `3bf215a342a46bae5d729cd55044bf009053f88afc04f58aaf7a5b2b4aeed316` |

報告在 `output/full-audit-20261023/council-reports-final/`；主席機器紀錄為 `output/mission-center-critique/CH-T120-full-audit-final.json`。使用者無額度上限；機器欄位要求正數，故記錄累積配置 96,000 tokens、每席18,000、整合24,000、144次工具／每席36次、120分鐘作本輪記帳配置，並非新使用者上限。工具沒有提供精確 token 用量，未宣稱量測或遵守原先32k建議額度。

## 可重複的自主檢查

`QT_QPA_PLATFORM=offscreen` 執行 `tests/test_product_experience.py`、`tests/test_reading_overlay.py`、`tests/test_render_text_controls.py`，可驗證設定與字幕旅程。設定 `CLOUDHIME_TEST_RENDER_DIR` 可輸出三組 Controller／字幕圖片，供下次視覺複核；完整 inventory 仍由 `ci/test_groups.json` 與 `ci/run_pytest.ps1` 管理。frozen host 使用既有 `packaging/test_clean_machine.ps1` 與本輪 `verify_preview.ps1`／`verify_full.ps1`，不共用使用者設定。未把 native 桌面控制不可用變成停止驗證的理由，也不把 offscreen 等同真遊戲。

## 未完成的獨立發行範圍

CH-T55 的乾淨 Windows OCR、真實設定更新／完整原生 GUI、Store 發行仍由原任務追蹤。本輪沒有產生新 MSIX、修改上傳的 Store 草稿或宣稱正式上架；新 EXE 是完整內附模型的本機技術預覽。遠端 CI 於 main 推送後另以該 commit 的 workflow 結果核對。
