# GitHub 原始碼／Store 付費全包政策

主人在 2026-10-06 明確指定：GitHub 免費提供原始碼，不提供 EXE；Microsoft Store 收費並提供完整 EXE 與離線模型包。售價尚待主人決定，Store 私人免費草稿不能當作付費發行已完成。

## 本地流程

README、雙軌發行手冊與 packaging README 已同步政策並標明歷史驗收快照。`build_exe.bat` 保留完整 dist、固定模型 stage 與驗證，移除 EXE ZIP 的產生及清理步驟。GitHub Actions 保留 runner 內建置／驗證及純報告／SBOM artifact，移除公開可下載的 frozen EXE ZIP 上傳。

政策契約驗證 **74 passed、19 deselected**；19 案為本次未改動的真實舊 dist／MSIX／WACK 等昂貴驗證，沒有宣稱通過。另一次廣泛掃描沒有完成，不作通過證據；沒有再重跑巨大舊 dist。本輪新來源的 frozen 驗證由獨立候選流程執行。

這個切片是既有公開分發步驟移除與文件調整，無 runtime／依賴／Store payload builder 變更，CodeRabbit 額外審查路由為低風險 skip；不能把前一批 19 檔的 0 issues 算成此切片已審查。完整 Store 發行仍保留自己的驗收與評論閘門。

## GitHub 實際附件移除

已將四份舊公開二進位附件備份至 `output/release-20261006/github-binary-backup/`，核對公告大小並保存 SHA-256。總大小 1,011,944,404 bytes；未執行下載的 EXE。

主人明確確認移除後，透過 GitHub 編輯 release 介面刪除 V3.1／V3 的 `CloudHime.zip` 與 V2.2／V1.0 的 `CloudHime.exe`，保留四個 release／tag。返回列表顯示每個版本只有兩個自動原始碼下載；公開 API 再核對四個 release 的附加 assets 都為 0。

證據：`output/release-20261006/github-source-only-receipt.json`、`github-source-only-result.png`、備份 `verified-backups.json`。舊下載連結不再提供附件；既有使用者已下載的檔案不受遠端移除影響。

## 剩餘

Store 售價、最新候選實機 GUI 驗收、套件認證與實際更新仍在 CH-T55。CH-T56／CH-E7／CH-E8 保留其明確依賴，不因政策文件完成而直接標 Done。
