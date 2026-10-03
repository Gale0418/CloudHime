# 2026-10-03 OCR 修復、雲朵圖示與發行準備

任務 CH-T117、CH-T55；CH-T56 文件先行準備。主人確認 OCR 修復預覽版一般使用正常，定案純雲朵 logo，並授權依 T117 → T55 → T56 推進、同步 main。

## 修正與圖示

- 補齊 WinRT Foundation／Foundation.Collections 3.2.1 的生產與 CI hash locks、PyInstaller hidden imports 與可用性預檢，修正原生 async completion 因缺件卡住。
- 逐項翻譯失敗保留原文、顯示未完成或限流提示；失敗項不寫入 translation／preferred-text／HUD cache。保留 exact-image cache 的完整 provider guard。
- AI 退回 Google 後的 TooManyRequests 經 orchestrator 包裝，仍辨識為 Google fallback 限流；不用偏好引擎名稱推斷實際失敗來源。新增真實 primary → fallback 路由回歸，未送網路請求。
- 純雲朵來源 `assets/cloudhime_logo_cloud.png` 套入主 PNG 與 44／50／150px 圖示，保留透明度。未採用的人物稿留在本機，不納入版控／發行來源。

## CodeRabbit

CLI 0.7.6 已登入。審查使用獨立 Git 快照，core.autocrlf 與主工作區一致；不傳 Store identity、模型、產物、私人設定或人物稿。

1. 第一次因投影未指定基準分支退出，未完成分析，不列通過。
2. 明確指定 main 後，15 檔審查完成：1 minor issue，AI 偏好引擎退回 Google 時可能漏判限流。查證成立並修復。
3. 2 檔聚焦複審完成：CodeRabbit raised 0 issues.

原始 NDJSON、來源快照與測試日誌保留於 `output/cloud-release-20261003/`，不推送產物或憑證。CLI 的更新提示未作為執行指令；本次審查正常完成。

## 本機驗證

Python 3.13.11、PySide6 6.10.1、offscreen，分批執行，未宣稱完整 3.13 相容性：

- 修復後 OCR worker／orchestrator：136 passed（131 worker＋5 orchestrator）。
- 新圖示下產品互動：38 passed。
- OCR thread safety／dependency／release packaging／functional smoke：64 passed。
- 共 238 個不同案例；pytest cache 有既有 WinError 5 警告。diff-check 通過。
- 固定 Gemma 模型與 projector 的大小／SHA-256 與 manifest 相符，僅本機核對，未下載新模型。

新增 `docs/release-two-track.md` 與 README 連結，說明自簽 sideload、Store identity／版本、unsigned 上傳輸入、清理與恢復。信任位置核對 Microsoft 一手文件及 CI，LocalMachine TrustedPeople 的操作需要系統管理員工作階段；不宣稱已完成本次安裝測試。

## 套件、CI 與未完成項

原始碼與五份雲朵資產已提交並同步 GitHub main：`bff0c4f005b9ebec7d3e00450f4ddfd00b31d53d`。由此 commit 的乾淨 Git archive 建置，306 檔 SHA-256 manifest、archive 與實際 derived spec 均保存於 `output/cloud-release-20261003/`；未採用人物稿不在快照內。僅為依賴對帳將 Git LF／工作檔 CRLF 正規化，其他內容必須一致。

[CI run 37084989820](https://github.com/Gale0418/CloudHime/actions/runs/37084989820) 已完成 success，head SHA 與來源一致；八個必需工作成功，兩個手動 frozen-release 工作依設定 skipped，本輪 frozen gate 由本機另外執行。

新 Python 3.10 雲朵 EXE：`output/cloud-release-20261003/dist/CloudHime/CloudHime.exe`，SHA-256 `810d9751d379afb77baa474fd6099bc59e698641f0e0a34b2f741439719e0028`。環境隔離 frozen Windows OCR 公開圖片辨識兩行、import 與 light dist verifier 通過；40-component provenance 驗證通過。PE 圖示群存在、與先前預覽圖示不同。此環境隔離結果不是全新 Windows VM 驗收。

CodeRabbit 完整與差異審查原始 NDJSON SHA-256 分別為 `7a38bea2788b01f5780d3948e78be49a505ce23acb65810ef0171ad9048c42f9`、`c3a546d20364db80ecdc3dd89434215995e01118b08d2abb2c3090d2f75befd3`；分支錯誤的首次輸出 `55338cda5fc654debacb0009cbc13491c662393985dbe0b7a73e78811433f9a3` 不列通過。

正式 critic_full 尚缺 total／per-seat／tool／wall-clock 明確預算，保留 CH-T117 Review；本機工作階段未提升權限，WACK 與需要權限的自簽安裝驗證尚未執行。Store 準備包不代表 Partner Center 已上傳、認證或發行，CH-T55 Review、CH-T56 Backlog 保留。

## 新產物與完整離線 smoke

- 新 frozen CPU Vision：1 張圖／1 case／1 成功請求，technical_coverage、非空輸出；測試程序與其模型服務已由 PID 樹清理，不代表翻譯準確度或 pristine VM。
- full dist：375 檔、4,896,174,164 bytes、固定兩個模型及四份條款；provenance／完整模型大小與 SHA-256 通過。
- light ZIP 與 development MSIX 均無模型；Store 候選 MSIX 含固定兩模型。兩個 MSIX 的 manifest identity／publisher／x64／0.1.2.0、無 AppxSignature、CRC、Foundation／Collections、主／44／50／150 圖示、EXE 與模型 SHA-256 通過。upload 僅含原 MSIX 且 hash 一致。未以 MakeAppx 解包測試冒稱實際安裝。

| 產物 | Bytes | SHA-256 |
|---|---:|---|
| `output/cloud-release-20261003/dist/CloudHime/CloudHime.exe` | 5502275 | `810d9751d379afb77baa474fd6099bc59e698641f0e0a34b2f741439719e0028` |
| `output/cloud-release-20261003/CloudHime-cloud-light.zip` | 868392382 | `d47446848989e78cc9db1e1737447105de554fc1160ef92b1e689c49fe7183ac` |
| `output/cloud-release-20261003/dev/output/CloudHime-0.1.2.0-x64.msix` | 839206443 | `257544ceb06639904ce7e7c31cbd2d668586b02616984421b4c8fcf57fd6a64e` |
| `output/cloud-release-20261003/store/output/CloudHime-0.1.2.0-x64.msix` | 3942272756 | `b3f51822aa84b01a05895ff1b48f80497442d438a55b1a3d7b9a0dcfbaf88216` |
| `output/cloud-release-20261003/store/output/CloudHime-0.1.2.0-x64.msixupload` | 3940086304 | `1223f02197f7f62fbc42876410efdc9b86e87b3e6ef8c5cb35ef68e0fd2f6dff` |

Store 0.1.2.0 為本機候選號，尚未核對 Partner Center 是否已使用；既有 Store 0.1.1.0 未改。新一般 GUI 已啟動且有回應／CloudHime 視窗 handle；未宣稱看見實際畫面。正式 critic_full、WACK 與新候選安裝仍未執行。

Mission Center sync 與 doctor 通過；doctor 的既有 completion-passport legacy warnings 仍保留，不宣稱警告為零。E6／E8 已做唯讀範圍與依賴對帳，缺口與下一步寫回 tasks.md；不自動將 Epic 改為 Done。本次只補文件、checkpoint 與 SHA-256 清單，發行的程式／圖示來源仍是 bff0c4f。

## 2026-10-03 正式評議與使用者回測補記

使用者已核准 10,000 tokens、20 次工具、15 分鐘的本輪正式評議預算，並明確確認「目前翻譯系統沒問題」。先前缺少核准的紀錄是當時狀態，現已補足授權。

三位独立 Luna 在同一凍結快照檢查成功流程、雲朵圖示與失敗處理，未提出有實證的新缺陷；獨立仲裁結論為 **limited**，CH-T117 維持 **Review**。44／150 像素雲朵已實際檢視；真實工作列是否顯示新圖示尚未確認。主引擎與 Google 同時失敗時的 GUI 原文呈現未直接觀察，不能冒稱實測通過。

本輪未完成正式 contract validator：在席位工具上限內未定位到安裝版的 `critic_contract.py`。已保存三席封存報告及獨立仲裁訊息轉錄，並逐檔重新比對快照清單雜湊；轉錄不等於仲裁者產生的已驗證 contract。證據紀錄：[本輪評議](../output/mission-center-critique/CH-T117-cloud-20261003-102449.json)。

後續由 Codex 完成正式契約／最終收尾；實際工作列圖示仍待可用的本機畫面能力或使用者確認。沒有必要的程式修正，也未重跑既有 238 個案例。WACK、乾淨安裝、Store 版本核對、簽章與上傳仍未完成，本輪不把 CH-T55／CH-T56 關閉。

## 工作列圖示人眼驗收補記

使用者回覆「(｀・ω・´)ゞ是雲朵」，確認目前執行中的翻譯姬工作列已顯示雲朵圖示。連同先前「目前翻譯系統沒問題」的回測，這兩項實機確認均已完成，不再要求使用者重複確認。

這是既有封存評議之後的補充證據，原始評論與快照不覆寫；[圖示確認紀錄](../output/mission-center-critique/CH-T117-cloud-20261003-102449-taskbar-acceptance.json)。CH-T117 仍保留 Review，待 Codex 完成正式契約驗證與最終收尾；本次未新增程式變更或重跑測試，也未完成 Store／WACK。

## 管理員與乾淨 Windows 後續驗收

2026-10-03 使用者授權管理員工作後，development light MSIX 副本的簽章、WACK XML PASS、實際安裝／啟動／移除均通過。全新 Windows Sandbox 的完整 frozen dist import、隨包模型 CPU Vision 1/1 與 GUI 20 秒 liveness 亦通過，本輪 Sandbox 程序已精確關閉。原產品來源與產物沒有重建。以上取代前文當時的「WACK／乾淨 Windows 尚未執行」，不代表完整 Store MSIX 的安裝、認證或更新已完成。

本輪憑證物件／信任／公開CER已清理，但 backing private key 不可由此推論已刪除；公鑰查核不完整，追加唯讀 UAC 啟動取消，沒有刪除私鑰。完整證據及限制見 [管理員與 Sandbox 驗收](2026-10-03-admin-sandbox-acceptance.md)。CH-T55／CH-T117 保留 Review，差異評議額度及實際 Store 發行 gate 仍待完成。
