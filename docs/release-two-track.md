# CloudHime 雙軌發行手冊

GitHub 免費提供完整原始碼，不提供官方 EXE、runtime 或模型二進位；Microsoft Store 規劃提供付費的完整 EXE、runtime 與模型 MSIX。原始碼依 `LICENSE` 的 Apache License 2.0 發行，任何人都可依該授權合法免費或收費再散布原始碼及衍生作品，並須遵守其中條件；第三方元件與模型仍受各自授權或使用條款約束。詳見 [`NOTICE`](../NOTICE)、[`AUTHORS.md`](../AUTHORS.md)、[`BRANDING.md`](../BRANDING.md) 與 [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。

規劃售價為 NT$249，自正式公開可購買日起前 30 天規劃以 NT$199 首發。目前 [Microsoft Store 頁面](https://apps.microsoft.com/detail/9NH4B9GQ86FL)仍是私人預覽，尚未正式公開可購買；因此尚未開始收費，首發 30 天也尚未起算。實際價格與供應狀態以 Store 頁面為準。原始碼可於 [GitHub 專案](https://github.com/Gale0418/CloudHime)取得。

Microsoft Store 付費套件不包含第三方雲端服務的 API 費用；使用者須自行提供金鑰並依服務供應者的費率及條款付費。Gemma 模型與其他第三方元件各自適用其授權或使用條款，CloudHime 原始碼的 Apache License 2.0 不會取代或擴張那些條款。

本手冊說明 MSIX 本機開發驗證與 Microsoft Store 發行的界線。開發憑證只供本機 sideload；Store 上傳包使用 Partner Center 指定的 identity，由 Microsoft Store 簽署後發行。兩條流程共用凍結版建置及 payload 驗證，但簽章、信任與發行結果不能互相代替。

本文件與 `NOTICE` 僅提供發行及署名資訊，不修改 `LICENSE` 條款。Apache 2.0 第 4 節說明 NOTICE 僅供告知，且不得被解讀為修改授權；第 6 節不授予商標權。這些聲明不限制 Apache 2.0 所授予的合法免費或付費再散布權利。

## 開始前：建立凍結版

發行工具鎖定 CPython 3.10、Windows x64。先在 PowerShell 7（pwsh）建立專用環境，避免既有 OpenCV／OCR 套件覆寫相同 namespace：

```powershell
py -3.10-64 -m venv .venv-release
$env:CLOUDHIME_BUILD_PYTHON = (Resolve-Path '.venv-release/Scripts/python.exe').Path
& $env:CLOUDHIME_BUILD_PYTHON -m pip install --upgrade pip
& $env:CLOUDHIME_BUILD_PYTHON -m pip install --require-hashes -r requirements-lock-win-amd64-py310.txt
& $env:CLOUDHIME_BUILD_PYTHON -m pip install --require-hashes -r requirements-build-win-amd64-py310.txt
```

`build_exe.bat` 會先從 hash lock 下載可信 wheel，核對實際建置環境的 wheel bytes，拒絕 OpenCV 共用 namespace 衝突。Pillow 只用於 PNG 圖示轉換，不納入正式 runtime；生產報告與 SBOM 不包含建置工具。完整性檢查失敗時不刪除既有 dist。

`build_exe.bat` 會執行 provenance 準備、PyInstaller、啟動 import smoke 與 release dist 驗證。預設 `CLOUDHIME_RELEASE_FLAVOR=full`，會把固定模型與 projector 放入供 Microsoft Store/MSIX 使用的 `dist\CloudHime`；設為 `light` 才不附模型，程式仍可使用受管 AppData 模型路徑。一般本機及 GitHub Actions 建置都不會建立 EXE ZIP；CI 只在 runner 上建置及驗證 frozen dist，dependency reports／SBOM 等非二進位報告仍可作為 Actions artifact。`CLOUDHIME_MODEL_SOURCE` 可指定 full 模型來源，`LLAMA_RUNTIME_COMMIT` 或 `runtime\llama-runtime-commit.txt` 必須提供 runtime commit provenance。

```powershell
& .\build_exe.bat
```

**重建前先保留需要的舊產物。** 此入口會刪除並重建 `dist\CloudHime`，也會重建 `build\runtime` 與 `build\provenance`；失敗時只清理它自己的 runtime staging，並不會還原先前的 dist。每次建置請序列執行，保留原始錯誤輸出；依失敗階段修復後再從本節重跑。缺 runtime provenance、模型大小／雜湊不符、依賴鎖或 dist preflight 失敗時都應停下，不要把部分產物當作可發布版本。

要在尚未有 Windows SDK 的機器先驗 dist，可執行：

```powershell
pwsh -File packaging/build_msix.ps1 -DistDir dist/CloudHime -PreflightOnly
```

它會呼叫正式 payload verifier，驗證圖示、provenance、runtime 與模型組合等條件，不產生或簽署 MSIX。Python hash lock 僅適用於 CPython 3.10／Windows x64；更新 Python、平台或相依套件時須重新產生並審查對應鎖檔。

## 軌道 A：本機開發自簽與 sideload

這條軌道用預設 `CN=CloudHime Development` publisher 建立未簽名的 MSIX，再由本機短期開發憑證簽署並安裝測試。它不代表 Store identity、可信任的公開簽章或 Partner Center 驗收。repository 沒有通用的本機憑證管理命令；CI workflow 的 ephemeral certificate 步驟只供 CI runner 參考。

先用唯一版本與專屬輸出目錄產生未簽名套件；例如把 `$run` 換成此次測試的唯一名稱，避免與另一條建置共用暫存目錄或覆寫既有套件：

```powershell
$run = 'build/msix-dev-0.1.2.0'
pwsh -File packaging/build_msix.ps1 `
  -DistDir dist/CloudHime `
  -OutputDir "$run/output" `
  -Publisher 'CN=CloudHime Development' `
  -Version 0.1.2.0
```

需要 SDK 的 `makeappx.exe`。Builder 會先驗證 dist，套用 manifest identity，然後產生未簽名 `.msix`；沒有 `-CreateUpload` 時不建立 `.msixupload`。本機簽署時，建立只供此次開發驗證的程式碼簽署憑證，其 Subject 必須與 manifest 的 publisher 完全一致；只將該憑證公用部分匯入 LocalMachine TrustedPeople（需要系統管理員權限），再以 SDK `signtool.exe` 在 SHA-256 模式簽署剛產生的 MSIX。以下範例不匯出私鑰。憑證信任範圍依 [Microsoft MSIX 簽署指南](https://learn.microsoft.com/en-us/windows/msix/package/sign-msix-package-guide) 與本專案 CI 契約；簽章、安裝或驗證失敗時，也必須執行下方 thumbprint 清理段：

```powershell
$msix = Join-Path $run 'output/CloudHime-0.1.2.0-x64.msix'
$certificate = New-SelfSignedCertificate `
  -Type CodeSigningCert `
  -Subject 'CN=CloudHime Development' `
  -NotAfter (Get-Date).AddDays(1) `
  -KeyExportPolicy NonExportable `
  -CertStoreLocation 'Cert:\CurrentUser\My'
$cer = Join-Path $run 'cloudhime-dev.cer'
Export-Certificate -Cert $certificate -FilePath $cer | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople' | Out-Null

# 執行前將此路徑改為已安裝 Windows SDK 的 x64 signtool.exe。
$signtool = 'C:\Program Files (x86)\Windows Kits\10\bin\<SDK版本>\x64\signtool.exe'
& $signtool sign /fd SHA256 /sha1 $certificate.Thumbprint /s My $msix
if ($LASTEXITCODE -ne 0) { throw 'MSIX signing failed.' }
```

`<SDK版本>` 是佔位文字，執行前須換成已安裝 SDK 的目錄名稱。LocalMachine TrustedPeople 的匯入與清理需要已授權的系統管理員工作階段；不要改動 Root 存放區或重用此憑證作 Store 發行。CI workflow `.github/workflows/ci.yml` 示範了 ephemeral 憑證、套件簽署及依 thumbprint 清理的模式。

安裝／啟動 smoke 使用既有腳本：

```powershell
pwsh -File packaging/test_msix_install.ps1 `
  -PackagePath "$run/output/CloudHime-0.1.2.0-x64.msix" `
  -LaunchWaitSeconds 3
```

此腳本會在呼叫端已有同名套件時拒絕操作，並在 `finally` 中停止它啟動的 PID、移除此次安裝的套件，再確認套件已消失；它不會建立、信任或移除憑證。若安裝或啟動失敗，保留錯誤輸出，先確認測試套件已卸載，再以憑證 thumbprint 精確檢查並移除此次建立的憑證（CurrentUser `My` 與 LocalMachine `TrustedPeople` 存放區）。不要用清空憑證存放區或按程序名稱批次終止的命令。若 cleanup 本身失敗，先處理該次套件／憑證，再開始另一輪測試：

```powershell
$thumbprint = $certificate.Thumbprint
foreach ($store in @('Cert:\CurrentUser\My', 'Cert:\LocalMachine\TrustedPeople')) {
  Get-ChildItem -Path $store |
    Where-Object { $_.Thumbprint -eq $thumbprint } |
    Remove-Item -Force
}
Remove-Item -LiteralPath $cer -Force -ErrorAction SilentlyContinue
```

## 修改 Qt 的獨立 MSIX 路徑

正式 `build_exe.bat` 的 wheel 完整性檢查使用官方 production hash lock，會拒絕不符合該 lock 的自編 PySide6／Shiboken wheel。這個入口的通過結果只適用於正式基線；在原始碼環境替換 wheel 後，不能宣稱仍通過同一組完整性檢查。

修改版可從已驗證的完整 onedir 基線建立獨立可寫副本，再依 [`QT-LIBRARY-REPLACEMENT.md`](../packaging/third-party-licenses/QT-LIBRARY-REPLACEMENT.md) 替換 Qt／PySide6／Shiboken。使用相同版本、Release MSVC x64 與 CPython 3.10 ABI，保存自編來源、工具鏈、替換檔雜湊及相應授權原文；原基線與已安裝 Store 套件均保留。副本中的原始 dependency provenance 描述的是基線，不能當成修改 DLL 的編譯證明。

Windows OCR 的官方支援範圍要求 [MSIX 套件身分](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr)。因此修改版若需使用這項功能，應將副本重新封裝，使用獨立開發 identity；直接啟動可寫 EXE 的有限結果不能替代套件功能驗收。下例的兩個路徑需改為自己這次建立的專屬目錄，`OutputDir` 必須是尚未使用的新目錄：

```powershell
pwsh -File packaging/build_msix.ps1 `
  -DistDir 'build/qt-modified/modified-dist' `
  -OutputDir 'build/qt-modified/msix-output' `
  -IdentityName 'CloudHime.QtModified' `
  -Publisher 'CN=CloudHime Development' `
  -Version 0.1.2.0
```

此流程不使用 `-StoreRelease`，不修改已簽署的 MSIX，也不覆蓋正式 Store identity。Builder 仍會驗證 payload、provenance 與 Qt 模組清單；它沒有要求允許模組的 DLL 維持原始內容雜湊。修改版須另外保存完整檔案清單與來源，不能沿用官方基線的完整性聲稱。

依軌道 A 的開發簽章及 thumbprint 清理步驟處理新 MSIX，再使用 `test_msix_install.ps1 -IdentityName CloudHime.QtModified` 驗證 AUMID 啟動。獨立 identity 會有獨立設定目錄；不要為此移除或改動現有 Store 安裝。完整驗收仍須實際操作修改版 GUI 與套件身分下的 OCR／翻譯，記錄版本、產物雜湊、結果及清理。這是由現有封裝器推導的操作路徑，目前尚無自編 Qt 修改版 MSIX 的完整功能驗收，不作法律合規或已通過的聲稱。

## 軌道 B：Microsoft Store 正式發行

Store 路徑要求 Partner Center 已保留的產品 identity。`-StoreRelease` 必須搭配本機未納入版控的 `packaging/store-identity.local.json`；schema 1 欄位為 `identity_name`、`publisher`、`publisher_display_name` 與 `package_family_name`。檔案不能提交或貼入 issue。Builder 會拒絕 development、CI、test、example、placeholder publisher，以及不符 identity prefix 的 package family name。

版本需為四段數字且各段不超過 65535；Store 的第四段 revision 必須為 `0`。每次上傳使用 Partner Center 尚未使用且高於已發行版本的版本號。例如既有私人群組版本為 `0.1.1.0`，後續版本須依 Partner Center 的實際狀態選更高版本；不可重用已上傳版本，也不要只遞增第四段。

確認 T55 的版本設定／既有 Store 狀態已審核，並已用本輪來源重建且驗證 dist 後，將 `$run` 設為此次唯一建置目錄，執行：

```powershell
$run = 'build/msix-store-0.1.2.0'
pwsh -File packaging/build_msix.ps1 `
  -StoreRelease `
  -StoreIdentityConfigPath packaging/store-identity.local.json `
  -DistDir dist/CloudHime `
  -OutputDir "$run/output" `
  -Version 0.1.2.0 `
  -CreateUpload
```

此命令例使用 `0.1.2.0` 示範四段格式；只有確認它高於 Partner Center 目前版本、且未曾上傳後才可採用。建置需要 Windows SDK `makeappx.exe`。產物為 `.msix` 及手動組成、內含該 MSIX 的 `.msixupload`；Store 路徑輸入是未簽名套件。Builder 不會代替 Microsoft Store 簽署，也不會提交 Partner Center。上傳後的 Microsoft re-signing、認證、發布與安裝更新由 Partner Center／Store 流程完成；未取得該流程證據前，不宣稱已簽署、通過認證或發布。

`build_msix.ps1` 在打包前執行 release dist 驗證；Store identity 或版本 guard、dist preflight、SDK 或打包任一失敗都應視為未完成。它在失敗時會移除此次目標套件／upload 檔與暫存目錄，但不會修復 dist；為避免碰到舊檔，必須為每次執行指定新的專屬 `OutputDir`，不要讓不同建置同時執行。檢查設定、版本與失敗階段後，使用新目錄重跑；不要手動把開發簽章套件改成 Store 輸入。

## 歷史驗收快照與恢復順序

截至 2026-10-07，0.1.2.0 候選的 host frozen import／OCR／CPU vision／GUI 檢查通過；全新 Windows Sandbox 的安裝、合成設定更新保留、副本 import／CPU vision、Qt 載入與 AUMID 啟動亦通過。完整 WACK 總判定 PASS：13 個必要測項全部通過，9 個選用測項通過、2 個選用測項失敗；不代表全部測項或 Windows S 模式相容。沙箱 Windows OCR 尚未通過，獨立原生 MSIX／真正 AUMID 對照亦在辨識階段回傳 E_FAIL，根因未定。最終 GUI 完整操作、真實設定升級、正式評論及 Store 認證仍待完成，候選尚未上傳。完整證據與限制見[本輪驗收紀錄](../reviews/2026-10-07-release-integrity.md)。Microsoft Store 正式現行版本仍為 `0.1.1.0`。

以下內容是截至 2026-10-05 的歷史快照，不代表目前 Store／GitHub 發行狀態。當時主機私人 Store 版仍為 `0.1.1.0`。產品候選固定於來源 `fe88bab940c02c7e271fefeea557bc004cb9d580`，位於 `output/store-release-20261005-gemini-copy/`；10/03 的候選是歷史產物，不用來接續本輪發行。該候選已通過 frozen import、Windows OCR 兩行、CPU Vision 1/1、GUI 啟動存活與 full provenance 驗證；隔離環境的合成 LocalState 更新保留、全新安裝／啟動／移除也已通過。

正式 SDK 隔離環境的完整 WACK 已取得 exit 0、`OVERALL_RESULT=PASS`、`PARTIAL_RUN=FALSE`；13 個 required 測項全 PASS。另有 10 個 optional PASS、1 個 optional FAIL：blocked executable 掃描器回報 `OverflowException`，未定位觸發檔案。這不是全部測項通過或 Windows S 模式相容的證據；[Microsoft 的 Desktop Bridge 規則](https://learn.microsoft.com/en-us/windows/uwp/debug-test-perf/windows-desktop-bridge-app-tests)以 required 測項決定總判定。完整報告、來源／產物雜湊及限制見 [10/05 驗收紀錄](../reviews/2026-10-05-wack-critique.md)。

四席正式評論保留 `limited`：完整 GUI 操作、真實使用設定升級、Partner Center 認證與實際 Store 更新尚未驗收。Submission 3 已保存免費私人預覽草稿；本輪 `0.1.2.0` 尚未上傳，草稿與本機 WACK 不能替代認證結果。

恢復工作時依序處理：

1. 使用固定候選 `dist/CloudHime/CloudHime.exe` 完成完整操作旅程：框選 → OCR／翻譯 → 字幕、取消框選、暫停保留字幕 → 繼續、忙碌時設定／停止、正常關閉。原生工具目前能讀元件名稱，但擷取／點擊失敗；自動化與合成結果不能替代這項實際操作證據。記錄使用引擎、操作步驟與結果；遇到異常先保留可重現步驟。
2. 在獨立測試環境驗證實際使用設定的升級保留；既有合成 LocalState 雜湊相同只證明合成資料保留。不要用自簽測試包覆蓋主機 Store 安裝。
3. 上傳前重新核對 Partner Center 現行 identity、版本是否未用、免費私人預覽範圍及 upload 雜湊。評議若修正產品程式或資產，才從新來源重建並重跑受影響 smoke；只改發行 helper／文件不會改變固定產品候選。
4. 完成私人預覽認證後，保存實際 Partner Center 結果，再驗證 Store 安裝／版本更新與無 SmartScreen 警告。上述操作與正式評論未收斂前，不將 CH-T55 標為 Done，也不進行公開發行。

CH-T56 正式任務仍為 Backlog 並依賴 CH-T55 Review。本文件是發行操作草稿，不代表 T55 或 T56 已完成，也不會因文件存在而改變 MissionCenter 狀態。
