# 2026-10-20 商店上架收尾 checkpoint

## Summary

CH-T55 維持 Review／Smoke NO／Review NO，CH-T56 維持 Backlog。此輪完成來源 CI 與商店草稿對帳、客服補件紀錄及剩餘驗收整理；不是正式發行結案。

## Completed

- GitHub 來源 `2463eae99d02232b2e0aa36dfebab3c414f67130` 的 [CI147／37629082572](https://github.com/Gale0418/CloudHime/actions/runs/37629082572) completed/success。GitHub API 與 connector jobs 核對八項必要工作成功、兩項手動 frozen 工作 skipped。這補齊先前倒數時鐘測試修正的遠端回執，不把 CI146 的失敗抹除，也不替代固定候選驗收。
- Chrome 重新核對產品 `9NH4B9GQ86FL` 的 Submission 3：更新處於草稿，`CloudHime-0.1.2.0-x64.msix` 為 Validated；目前發行仍指向 Submission 2。提交認證按鈕 disabled，後台仍提示需更新稅務與支付資訊。Validated 只代表後台套件驗證，不是認證通過。
- 提交選項已有 `runFullTrust` 用途說明：使用者擷取畫面、桌面覆蓋、Windows OCR、內附 llama-server 子程序；現有說明沒有要求管理員權限或安裝背景服務。本輪唯讀核對，未送出功能核准要求。發布選項仍是認證後立即或按已設定排程發布，未改動。
- 四語 Gemini 行銷文案、作品小本本特色、第三方條款與 GitHub 免費原始碼互導，延用 10/7 的逐欄重開核對收據；本輪文件複核未發現具體缺陷，沒有重寫已保存文案。定價仍為 NT$249 買斷；正式公開可購買後前 30 天 NT$199，首發優惠尚未排程。
- 依主人提供的資料完成 Business Profile，完整郵碼經中華郵政官方查證後通過並進入下一頁。台灣個人稅籍仍被僅收八碼 Uniform numbers 的欄位阻擋；錯誤畫面已遮蔽個人識別碼，補充說明與截圖上傳原 Microsoft 客服案件，兩檔皆顯示傳輸完成／上傳成功。先前含去敏感 HAR 與六張步驟圖的診斷包亦已成功上傳。等待微軟回覆，未完成或送出稅務表單。

## Unfinished

| 項目 | 現有證據與下一個動作 |
| --- | --- |
| Microsoft 稅務／支付 | 等待原客服案件處理台灣個人稅號格式；通知信的 tax profile updated 不代表表單已完成或通過審核。 |
| 最終 frozen GUI 完整旅程 | 10/7 隔離入口已備，尚缺實際框選、翻譯泡泡、暫停／繼續／停止及設定重開的完整操作證據。入口 ready 不等於 Pass。 |
| 真實設定升級 | 既有證據僅為合成 LocalState 保留；需在隔離副本驗證實際設定遷移，避免覆蓋原設定或外傳金鑰。 |
| 乾淨 Windows OCR | 原生 MSIX／真正 AUMID 對照仍曾回傳 E_FAIL；根因未定。既有 host OCR、CPU Vision 或 WACK 通過不能替代此項。沒有新假說，不重複相同沙箱診斷。 |
| 認證補充說明 | 「其他測試資訊」頁面曾提示 session 過期，更新後仍顯示未解析的資源名稱與空白內容，未寫入或點 Review and publish。新增 Gemini 說明請求回報 quota reached，無成功交付；不可假稱已完成。 |
| Store 外部驗收 | 尚待 runFullTrust 審查、Store 認證及實際安裝／更新；公開可購買日確定後再落實 30 天首發價。 |

## Risks

- 最終候選仍綁定來源 `6f69577`；此後已知變更是文件與計時測試，沒有因客服補件或本輪核對重建 EXE／MSIX。候選產物、歷史 WACK 選用失敗與正式仲裁 blocked 結論，仍依 [10/7 紀錄](2026-10-07-release-integrity.md)保留。
- 後台公告的 [Microsoft Store Policies 7.20](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies-and-code-of-conduct) 於 2026-10-22 生效；本輪僅記錄版本與生效日，沒有完成全條款差異稽核或宣稱合規。正式送審前須核對當時適用版本。
- 個人資料來源檔、身分證、住址、信箱、HAR、tokenized 上傳連結及原始截圖不納入 Git／CodeRabbit。客服收據只保留本機 ignored 證據；本紀錄不公開客服存取資訊。

## Smoke tests

- CI147 八必要成功／兩手動 skipped；本輪只讀對帳，未重新執行 frozen／GPU／沙箱／WACK。
- 商店概觀與提交選項實際可見；其他測試資訊載入不完整，不能推定空白欄位就是後端沒有保存內容。清單匯出未取得可驗證的 download event，不宣稱匯出成功。
- 去敏感客服附件的上傳完成由實際 portal 狀態確認。最新本機對帳檔位於 `output/store-closeout-20261020/`，未納入公開 repository。
- 文件與任務中心 sync、diff-check、CodeRabbit 與 Git 回執另於本輪完成後核對；沒有把文件檢查當產品驗收。

## Retro

先沿用固定候選和已保存草稿的可核對證據，僅更新目前狀態與可執行下一步。外部頁面失效、模型服務額度與實際驗收缺口分開記錄；不因等待客服而重建未變更的產品，也不以重跑或改寫歷史消除缺口。
