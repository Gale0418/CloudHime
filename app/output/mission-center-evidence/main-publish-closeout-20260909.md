# 本輪 main 提交收尾

## Summary｜摘要
依主人要求直接提交 main；未建立工作分支。保留所有實測邊界，不將整體產品標為完成。

## Completed｜已完成
- UI settings_styles 初始化、AppData／Gemma 條款呈現、跨平台 path test、WACK PS5.1 相容性修正及 HTTP500 不重播回歸。
- 145 項相關回歸通過，CodeRabbit 審查 7 個變更檔並完成，0 issues。
- fresh EXE／ZIP／MSIX、release preflight、隔離啟動及新 WACK PASS。
- 新 WACK XML SHA256：2125782A91620AB3F1324A2CA44C04B2776583399BB0A831652CA70E25BC580A。gate／appcert／TE 均結束，測試憑證0、AppX套件0、隔離簽章staging不存在。
- 新增本輪 Done 任務的小型 passport／證據，避免只提交 tasks.md 狀態。

## Unfinished｜未完成
- 31b 圖片仍 HTTP500／INTERNAL；T109 及下游任務未宣稱 Done。
- 乾淨 Windows 首次模型下載／續傳／handoff、完整人工 holdout、正式 Partner Center／Store gate 仍未完成。

## Risks｜限制
- 此次建置包含提交前工作樹變更；不是當時 HEAD 的純淨 commit build。
- CodeRabbit 第一次在本機 fixture alternate path 失敗，第二次修正後成功；本小時啟動2次，未使用credits。
- 環境政策拒絕刪除 output/coderabbit-publish-20260909，忽略的臨時審查目錄留在本機、不提交；舊release備份保留。
- 大型EXE／ZIP／MSIX／完整WACK XML不納入此code commit；沒有上傳實際API key。

## Smoke tests｜驗證
參見 MissionCenter/smoke-tests.md、coderabbit-publish-20260909.md、ch-t64-fresh-build-20260909.md 與各task passport。

## Retro｜回顧
先核對遠端main／憑證服務對應，WSL審查fixture需先檢查alternate path與換行設定；不能把未核對憑證或缺觀察結果寫成主人阻塞。
