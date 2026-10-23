# 本輪 main 發布前 CodeRabbit 審查

- 主人明確授權程式碼送審，限制每小時最多 3 次、每次 150 檔；本輪啟動 2 次，未購買 credits。
- CodeRabbit CLI 0.7.6，authenticated。Windows shim 轉交 WSL Ubuntu 執行。
- 第 1 次在本機 gitService.getFileChanges 失敗：Windows shared clone 的 alternate object path 不適用 WSL。未取得審查結果，不記為通過。
- 只修隔離 fixture 的 objects alternate path 與 core.autocrlf，WSL 確認 7 檔、79 additions／17 deletions；不修改主 repo Git 設定。
- 第 2 次 `coderabbit review --agent --uncommitted` 完成，exit 0，review_completed，findings=0。未連接付費 organization，使用 free CLI allowance。
- reviewedFiles：cloudhime_ui.py、packaging/test_wack.ps1、tests/test_msix_packaging.py、tests/test_settings_store.py、tests/test_translation_panel_advanced.py、tests/test_translation_providers.py、translation_settings_panel.py。
- 排除大型 generated artifact、模型、憑證、完整 MissionCenter 歷史；保留相關原始碼上下文。沒有為了隱藏問題而縮小 diff。
- 本地驗證：QT_QPA_PLATFORM=offscreen，pytest 上述四個受影響測試檔（settings_store、translation_panel_advanced、translation_providers、msix_packaging），145 passed in 319.87s，exit 0。
- CodeRabbit raised 0 issues；沒有審查驅動的產品修改，因此不消耗第 3 次複審。
