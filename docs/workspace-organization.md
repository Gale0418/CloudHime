# 工作目錄整理與還原指南

2026-10-23 整理；來源基準 `ea51e88d300d4119aaf233c73b168e379dbcaa60`。

## 日常入口

| 位置 | 用途 |
| --- | --- |
| `app/run.bat` | 啟動來源版；需先安裝開發相依套件 |
| `app/dist/CloudHime/CloudHime.exe` | 本機最新技術預覽，含 2026-10-23 連續閱讀流程；不是已發布的 Store 套件 |
| `app/` | 程式、測試、資源、模型、原生元件與封裝工具 |
| `app/output/` | 測試與審查證據、診斷、隔離環境與 Git 還原備份 |
| `app/build/`、`app/dist/` | 編譯中間檔與可執行／安裝產物 |
| `docs/` | 說明、設計、隱私、審查、紀錄與專案技能 |
| `MissionCenter/` | 任務、決策與驗收紀錄 |

從儲存庫根目錄執行一次 `cd app`，再使用原有的 `python CloudHime.py`、`python -m pytest ...`、`build_exe.bat` 或 `packaging/` 指令。`run.bat`、`install.ps1` 與建置入口會依自身位置定位，GitHub Actions 的工作目錄也已設為 `app`。

根目錄由 130 項減為 10 項（包含隱藏項目）：`.git`、`.github`、`.pytest_cache`、`app`、`docs`、`MissionCenter`、`.coderabbit.yaml`、`.gitattributes`、`.gitignore`、`README.md`。`.pytest_cache` 目前被 Windows ACL 拒絕存取，未更改權限；它仍被 Git 忽略。一般產品輸出應寫入 `app/output`，不要再散落根目錄。

## 搬移對照與相容性

- 原根目錄的產品模組、`assets`、`models`、`runtime`、`native`、`packaging`、`tests`、`ci`、`benchmarks`、`example` 及本機產物全部保留內部結構，移到 `app/`。
- 原 `DESIGN.md`、`PRODUCT.md`、`PRIVACY.md`、`reviews/`、`records/`、`skills/` 移到 `docs/`；原 `docs/` 與 `MissionCenter/` 留在原位。
- `LICENSE`、`NOTICE`、`AUTHORS.md`、`BRANDING.md`、`THIRD_PARTY_NOTICES.md` 留在產品根目錄 `app/`，維持封裝與授權檢查的輸入關係。
- 舊報告的 `output/...`、`tests/...` 等是當時位置，現在加上 `app/`；舊 `reviews/...` 與 `records/...` 加上 `docs/`。歷史報告沒有全面改寫，保留當時的事實與提交編號。
- 今日最新預覽原位於 `output/play-flow-20261023/dist/CloudHime`，現集中到 `app/dist/CloudHime`；舊驗證報告中的 EXE SHA-256 仍可用來核對同一份檔案。
- 沒有改成 Python `src` 套件佈局，也沒有修改產品邏輯。這次保留模組的相對關係，避免同時改變匯入、安裝及打包方式。[Python 官方佈局說明](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)

## 移除與保留原則

已移除可重建或被新版本取代的產物：0.1.0.0／0.1.0.1 的 MSIX 與上傳包、舊解包副本、ui-distill／first-value 兩份過期預覽、三次預覽的編譯中間檔、Python bytecode 快取，以及 9 月 24 日的舊 EXE 目錄。舊 EXE 含現行封裝政策不允許的 Qt 附加元件；保留其檔案清單、EXE 雜湊和供應鏈紀錄後，由通過檢查的最新預覽取代。

兩次清理的可用磁碟空間增量合計約 **28.27 GiB**；這是近似實測值，會受到同時寫入、NTFS 壓縮及硬連結影響，不能把所有檔案的邏輯大小直接當成回收空間。

保留 0.1.1.0 發行基準、0.1.2.0 候選套件、最新預覽、模型、runtime、測試／建置環境、原生崩潰診斷、唯一的歷史證據、既有外部 worktree，以及使用者提供的未追蹤圖片。`.env` 與私人紀錄只移動，不讀取內容或加入版本控制。`app/assets/cloudhime_logo_v2.png` 維持未追蹤。

往後清理應先檢查 Git 追蹤狀態、使用中的程序、硬連結／reparse point 與替代產物的驗證結果，再刪除指定產物；不要整包刪掉 `output/`，其中包含不可重建的診斷證據與備份。

## Git 瘦身與還原

遠端儲存庫查詢大小約 28 MiB，沒有需為大型歷史檔案重寫全部提交的證據。採用 Git 一般壓縮，保留分支、標籤、提交編號與 reflog，不 squash／force-push。執行方式為：

```powershell
git -c gc.reflogExpire=never -c gc.reflogExpireUnreachable=never gc --no-prune
```

這能整理物件儲存，不改寫已提交歷史與 refs。沒有使用 `--prune=now`，也沒有把不明 dangling 物件直接當垃圾刪除。[Git GC 官方說明](https://git-scm.com/docs/git-gc)、[GitHub 儲存庫大小建議](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

備份放在本機忽略目錄 `app/output/organization-20261023/`，不隨 Git 上傳：

| 檔案 | 內容與驗證 |
| --- | --- |
| `history-before.bundle` | 24 個 refs；`git bundle verify` 通過，已還原成 bare repo 並成功讀取原 HEAD |
| `git-metadata-before.zip` | 原 `.git` 中繼資料，包含 reflog；ZIP CRC 檢查通過 |
| `backup-verification.json` | 備份雜湊、大小與驗證結果 |
| `move-manifest.json`、`tracked-mapping.json` | 搬移前清單與逐檔對照 |
| `cleanup-plan.json`、`cleanup-result.json`、`preview-promotion.json` | 刪除範圍、結果與最新預覽移動紀錄 |

備份 SHA-256：

```text
history-before.bundle
f8fa2e9c12f87f84d740f96090caa656cdb16fffa452c6853028632adc8b1f7d
git-metadata-before.zip
e2c0820eb8b7074d2242a87960691a7d613b52a8233e0cf92a934eb1c67ac2d0
```

要查看整理前的版本，可從儲存庫根目錄把 bundle 還原到另一個新資料夾：

```powershell
git clone app/output/organization-20261023/history-before.bundle ../CloudHime-history-restore
```

bundle 保存已提交歷史，不含未追蹤檔案、模型或已刪除的編譯產物；原始 `.git` ZIP 供必要時調查中繼資料，勿直接覆蓋使用中的 `.git`。備份仍在同一磁碟，不等同異地災難備援。[Git bundle 官方說明](https://git-scm.com/docs/git-bundle)

## 驗證範圍

搬移對照以 Git blob 核對純搬移內容，封存 benchmark 及授權文字保留原始位元組。實際修改限於路徑設定、CI、測試與文件。

完整五組測試的原始結果、受影響複測、EXE import／Windows OCR／20 秒啟動、兩個內附模型及 Qt 封裝檢查，保存於 `app/output/organization-20261023/`。最終統計見 [Mission Center 冒煙紀錄](../MissionCenter/smoke-tests.md)。初次全套唯一失敗來自舊 `dist/CloudHime`，原失敗紀錄也保留，沒有放寬封裝規則。

Gemini Flash 提供資料歸檔／供應鏈／簡潔操作的研究意見；兩位 Luna 分別檢查 Git 保留及路徑遷移，另以 CodeRabbit 審查實際修改的 11 個檔案。意見由主代理查證整合，這輪是目錄整理驗收，不取代 Store 的完整操作、乾淨 Windows 或認證閘門。
