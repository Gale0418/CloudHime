# CloudHime 雙軌發行手冊

本手冊說明 MSIX 本機開發驗證與 Microsoft Store 發行的界線。開發憑證只供本機 sideload；Store 上傳包使用 Partner Center 指定的 identity，由 Microsoft Store 簽署後發行。兩條流程共用凍結版建置及 payload 驗證，但簽章、信任與發行結果不能互相代替。

## 開始前：建立凍結版

發行工具鎖定 CPython 3.10、Windows x64。先在 Windows PowerShell 7 執行以下命令安裝正式依賴與 PyInstaller 建置工具：

```powershell
py -3.10-64 -m pip install --require-hashes -r requirements-lock-win-amd64-py310.txt
py -3.10-64 -m pip install --require-hashes -r requirements-build-win-amd64-py310.txt
```

`build_exe.bat` 會執行 provenance 準備、PyInstaller、啟動 import smoke、release dist 驗證及 GitHub ZIP 封裝。預設 `CLOUDHIME_RELEASE_FLAVOR=full`，會把固定模型與 projector 放入 MSIX 用的 `dist\CloudHime`；設為 `light` 才不附模型，程式仍可使用受管 AppData 模型路徑。`CLOUDHIME_MODEL_SOURCE` 可指定 full 模型來源，`LLAMA_RUNTIME_COMMIT` 或 `runtime\llama-runtime-commit.txt` 必須提供 runtime commit provenance。

```powershell
& .\build_exe.bat
```

**重建前先保留需要的舊產物。** 此入口會刪除並重建 `dist\CloudHime`、`dist\CloudHime.zip`，也會重建 `build\runtime` 與 `build\provenance`；失敗時只清理它自己的 runtime staging，並不會還原先前的 dist 或 ZIP。每次建置請序列執行，保留原始錯誤輸出；依失敗階段修復後再從本節重跑。缺 runtime provenance、模型大小／雜湊不符、依賴鎖或 dist preflight 失敗時都應停下，不要把部分產物當作可發布版本。

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

## 目前 checkpoint 與恢復順序

截至 2026-10-03，先前已安裝的私人 Store 版本為 `0.1.1.0`，本輪未變更。雲朵來源及 OCR／限流修復已同步 main；乾淨來源 commit `bff0c4f005b9ebec7d3e00450f4ddfd00b31d53d` 的新 EXE 通過 frozen OCR 兩行、import、CPU 單圖 1/1、light/full payload 與 provenance 驗證，238 個相關測試及來源 CI 通過。新 light ZIP、unsigned 開發 MSIX 與完整 Store `0.1.2.0` 候選 MSIX／upload 已在 `output/cloud-release-20261003/` 建立並核對內容與雜湊。`0.1.2.0` 尚未核對 Partner Center 是否已使用；正式評議、本次安裝／WACK、上傳／認證／更新均未完成。完整來源、產物 SHA-256 與限制見 [雲朵版驗收紀錄](../reviews/2026-10-03-ocr-cloud-release.md)。

恢復工作時依序處理：

1. 完成 CH-T117 對本輪程式與雲朵圖示更新的 review，依其驗收條件確認後續工作所需的來源版本。
2. 完成 CH-T55 的 Store 版本／設定頁 review，核實 Partner Center 現行版本與上傳條件。
3. 核對已建置候選與來源／雜湊紀錄；評議若修正程式或資產，才從新核准來源重建並重跑受影響 smoke。需要本機安裝／WACK 時使用獨立測試環境，不把自簽測試包覆蓋既有 Store 安裝。
4. 依目的選軌道 A 或 B。Store 上傳前再核對 identity、版本、`release-two-track` 手冊與 upload 內容；只有實際 Partner Center 結果才能推進為發行完成證據。

CH-T56 正式任務仍為 Backlog 並依賴 CH-T55 Review。本文件是發行操作草稿，不代表 T117、T55 或 T56 已完成，也不會因文件存在而改變 MissionCenter 狀態。
