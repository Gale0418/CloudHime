# CloudHime MSIX

這是 Microsoft Store 的 MSIX-first 發行入口。先執行 build_exe.bat 產生 dist/CloudHime，再在裝有 Windows SDK 的 Windows 環境執行：

    pwsh -File packaging/build_msix.ps1 -Version 0.1.0.0 -Publisher "CN=CloudHime Development" -CreateUpload

makeappx.exe 由 Windows SDK 提供。預設開發 Publisher 只適合本機驗證；送 Partner Center 前必須使用已保留的 Store identity／publisher 參數。Store MSIX 上傳與 Microsoft re-signing 仍需在 Partner Center 完成。此 Builder 目前只產生 x64 套件，因為發行 runtime 內含 x64 的 llama/ggml/CUDA 二進位檔；未來新增其他架構時，必須先提供對應 runtime 與 CI 契約。

模型與 projector 不放進 MSIX；CloudHime 會將受管模型下載到使用者 AppData，並驗證版本與 SHA-256。THIRD_PARTY_NOTICES.md 與 LICENSE 會由 PyInstaller release bundle 隨包提供。

CreateUpload also produces a manually assembled .msixupload archive containing the MSIX. Public symbols are optional and are not included by this builder yet.

## Store release identity guard

本機開發套件仍可使用 `CN=CloudHime Development`；但正式 Store 路徑必須明確使用 Partner Center 提供的 identity data。`-StoreRelease` 會要求 `-StoreIdentityConfigPath`，並從未納入版控的 `packaging/store-identity.local.json` 讀取 schema 1：`identity_name`、`publisher`、`publisher_display_name` 與 `package_family_name`。development、CI、test、example 或 placeholder publisher 會在 dist preflight 前 fail-closed。

    pwsh -File packaging/build_msix.ps1 -StoreRelease -StoreIdentityConfigPath packaging/store-identity.local.json -Version 0.1.0.0 -CreateUpload

這個 guard 不會建立、猜測或替代 Partner Center product identity；缺少正式 identity 時應保持未執行，不可用開發 publisher 偽裝成 Store release。`store-identity.local.json` 已加入 `.gitignore`，不可提交身分資料。
## Release dist preflight

在尚未安裝 Windows SDK 的開發機上，可以先驗證真正會被放入 MSIX 的 PyInstaller bundle：

    pwsh -File packaging/build_msix.ps1 -DistDir dist/CloudHime -PreflightOnly

這個檢查會確認啟動檔、主 logo、44x44 / 50x50 / 150x150 MSIX 圖示、字典、授權 notices、llama/ggml runtime 與敏感檔案規則，也會拒絕把 GGUF、projector、簽章材料或已生成的 MSIX 檔案帶進套件。它不會修改 dist，不取代 makeappx、簽章、WACK 或乾淨 Windows 安裝測試。

MakeAppx 解包後，請只對已解包根目錄使用 `verify_release_dist.ps1 -UnpackedMsix`。此模式仍驗證 payload provenance，且僅容許根目錄的 `AppxManifest.xml`／`AppxBlockMap.xml`；預設 manifest 必須是 CloudHime、具 `CN=` publisher 並為 x64。可用 `-ExpectedIdentityName`、`-ExpectedPublisher` 與 `-ExpectedArchitecture` 覆寫這些期望值；提供 `-ExpectedPublisher` 時，會與 manifest publisher 做大小寫敏感的精確比對，未提供時則只要求 publisher 以 `CN=` 開頭。其他位置的 metadata、額外 `.msix`／`.appx` 與任何簽章材料仍會 fail-closed。

## Runtime manifest

build_exe.bat stages only the release llama-server files, then runs
packaging/runtime_manifest.py. The tool executes the staged
llama-server.exe --version command and writes runtime-manifest.json beside
the runtime. The manifest records the explicitly supplied llama runtime commit (from LLAMA_RUNTIME_COMMIT or runtime/llama-runtime-commit.txt), backend, architecture,
server version, and the size/SHA-256 of every staged runtime file.
verify_release_dist.ps1 fails closed when the manifest is missing or the
runtime file set, size, or digest differs.
The release verifier computes every manifest SHA-256 with a 1 MiB sequential stream, so it keeps full integrity coverage without loading runtime binaries into memory. The local real-dist preflight test has a bounded 600-second default timeout for slow disks; a timeout is an incomplete verification, never a pass.

## Local MSIX install smoke

`packaging/test_msix_install.ps1` 會在 `pwsh` 呼叫時自動轉交 Windows PowerShell 5.1，因為部分 Windows 的 Appx cmdlet 無法由 PowerShell 7 載入。開發測試憑證只能用於本機 sideload；Store identity、publisher 與正式簽章仍必須由 Partner Center／正式憑證處理。

## Dependency provenance and SBOM

CI 的 dependency-contract job 會在兩個互相隔離的 Python 3.10 Windows x64 fresh venv 驗證套件圖：

- CI graph：以 `requirements-ci-lock-win-amd64-py310.txt` 安裝 pytest 等測試依賴，產生 CI report／SBOM。
- Production graph：以 `requirements-lock-win-amd64-py310.txt` 安裝正式依賴，產生獨立 production report／SBOM。

兩條路徑都執行 `pip check`、direct requirements 驗證、target-specific hash lock 驗證與 deterministic CycloneDX 1.6 SBOM verify。`packaging/dependency_contract.py` 會 fail-closed 檢查 resolved distributions、下載 URL、SHA-256、license metadata、component set、版本與 selected artifact hash。

pip report 是 provenance 證據；hash lock 才是安裝約束，但只適用於 Python 3.10／Windows x64。CI 會上傳兩組 report／SBOM，後續再把 license evidence 與正式 release bundle 綁定。這些 contract 不等同於 clean-machine、PyInstaller、MSIX、WACK 或 Store 實機通過。

## Python 3.10 Windows hash locks

`requirements-lock-win-amd64-py310.txt` 是 production graph，`requirements-ci-lock-win-amd64-py310.txt`
則另外包含 pytest／pytest-qt。兩份檔案由 Python 3.10、Windows x64 的 pip report 產生，包含
所有 resolved distribution 的版本與 wheel SHA-256；CI 以 `--require-hashes` 安裝，並用原始
`requirements.txt`／`requirements-ci.txt` 驗證 direct intent。更新 direct dependency 或 Python／平台
版本時，必須重新解析並重新驗證 lock；它們不是可套用到任意 Python 版本的通用 lock。
## Frozen release build tooling

`requirements-build-win-amd64-py310.txt` is a separate, hash-pinned build-tool lock for
CPython 3.10／Windows x64. It contains PyInstaller and its build-only dependencies;
it is intentionally excluded from the production runtime lock and from the packaged
application dependency provenance. Before running `build_exe.bat`, install both the
production lock and this build lock into the same Python 3.10 x64 environment:

    py -3.10-64 -m pip install --require-hashes -r requirements-lock-win-amd64-py310.txt
    py -3.10-64 -m pip install --require-hashes -r requirements-build-win-amd64-py310.txt

CI's opt-in real release job follows the same separation. When the pinned runtime fetch produced `runtime-source.json`, `build_exe.bat` carries it into the staged runtime so the final runtime manifest retains the archive SHA-256 evidence. The lock is target-specific
and must be regenerated when the Python, Windows architecture, or PyInstaller version
changes.
## Release artifact dependency provenance

正式 ZIP／MSIX 內的 `_internal/provenance/` 由 `prepare_release_provenance.ps1` 以 CPython 3.10、Windows x64 的 fresh venv 產生，並由 `release_provenance.py verify` 在 release preflight 與 MSIX unpack 後 fail-closed 驗證。它固定包含 production pip report、CycloneDX SBOM、direct requirements、hash lock 與 schema 1 manifest；manifest 驗證相對路徑、精確檔案集合、大小與 SHA-256，並從 pip report 實際 environment 驗證 CPython 3.10／Windows／AMD64。

這是「宣告的 production Python dependency provenance」，不是完整 PyInstaller payload SBOM，也不是 OS／CUDA／runtime binary SBOM；不應將它冒充為後兩者。clean-machine、Store、WACK 與 GPU 實機驗證仍未由此流程覆蓋。


## Optional local WACK check

Microsoft has deprecated WACK. This wrapper is only an optional local pre-submission check; Partner Center certification is the final gate.

Run it only from an elevated Administrator PowerShell in an active interactive user session (never Session 0). The wrapper accepts exactly one mode and requires a new report path whose parent directory already exists and is writable:

    pwsh -File packaging/test_wack.ps1 -AppxPackagePath .\artifacts\CloudHime.msix -ReportOutputPath .\artifacts\wack-report.xml
    pwsh -File packaging/test_wack.ps1 -PackageFullName "CloudHime_1.0.0.0_x64__publisherid" -ReportOutputPath .\artifacts\wack-report.xml

These correspond to the Microsoft CLI forms appcert.exe reset followed by appcert.exe test -appxpackagepath <path> -reportoutputpath <path> or appcert.exe test -packagefullname <full-name> -reportoutputpath <path>.

Installed mode does not install or clean up packages. The caller must keep the installation and cleanup try/finally flow from packaging/test_msix_install.ps1; WACK itself requires admin and an active session.

## Environment-isolated packaged launch smoke

After building the frozen release directory, run the optional launch gate with a scrubbed child-process environment:

    pwsh -File packaging/test_clean_machine.ps1 -ExecutablePath .\dist\CloudHime\CloudHime.exe -LaunchWaitSeconds 20

The gate creates a unique `cloudhime-clean-machine-*` sandbox for TEMP/TMP/APPDATA/LOCALAPPDATA, keeps only required Windows variables, removes inherited developer PATH entries, verifies GUI liveness, and cleans up the exact packaged PID plus its owned descendant tree. This is environment-isolated packaged evidence, not proof from a clean Windows VM or Store certification.

## Optional real release CI gate

一般 push/PR 的 msix-contract 仍是 dummy structural fixture，只驗證 MSIX schema、解包、簽章與安裝契約，不代表真正 PyInstaller 或 Vision 通過。CI 另提供手動 workflow_dispatch 的 real-release-smoke job；只有勾選 run_real_release 且使用標籤為 self-hosted/windows/x64/cloudhime-gpu 的 runner 才會執行。

啟用前，請在 repository variables 設定：

- CLOUDHIME_RELEASE_DIST_DIR
- CLOUDHIME_RELEASE_MODEL_PATH
- CLOUDHIME_RELEASE_PROJECTOR_PATH
- CLOUDHIME_RELEASE_IMAGE_PATH

這些路徑必須指向真實 frozen dist、Gemma GGUF、mmproj 與 smoke image；job 會拒絕 cloudhime-dummy-dist，並要求 _internal/runtime/runtime-manifest.json。它只執行 packaging/test_release_smoke.ps1 的 real GPU gate，不會把 CPU 或 dummy 結果冒充 GPU；Partner Center、WACK 與 clean Windows VM 仍是獨立 gate。

另有獨立的 `run_real_release_build` workflow_dispatch gate，使用標籤為 self-hosted/windows/x64/cloudhime-release 的 runner。啟用前需設定：

- CLOUDHIME_RELEASE_RUNTIME_URL（HTTPS）
- CLOUDHIME_RELEASE_RUNTIME_SHA256
- CLOUDHIME_RELEASE_RUNTIME_COMMIT

它會先以 `packaging/fetch_runtime_assets.ps1` 驗證 archive hash、zip path safety、唯一 `llama-server.exe` 與 commit，再呼叫 `build_exe.bat`，並在上傳前執行 environment-isolated packaged launch smoke。這個 job 目前只是可重現建置入口；沒有配置 runner／repository variables 時不會執行，也不代表 Store、WACK、clean VM 或 GPU accuracy gate 已通過。

## Release smoke orchestrator

For a real frozen directory with an external managed model, run the fail-closed
three-stage gate:

    pwsh -File packaging/test_release_smoke.ps1 -DistDir .\dist\CloudHime -ModelPath "$env:LOCALAPPDATA\CloudHime\models\gemma-3-4b-it\ggml-org-ab31416a\gemma-3-4b-it.Q4_K_M.gguf" -ProjectorPath "$env:LOCALAPPDATA\CloudHime\models\gemma-3-4b-it\ggml-org-ab31416a\mmproj-model-f16.gguf" -ImagePath ".\example\smoke.png" -RequireGpu

The stages are: release dist/provenance preflight, explicit model/projector/image
validation, environment-isolated packaged launch, and functional Vision coverage.
The command requires an interactive desktop session and never starts an elevation
prompt. Exit codes are 20 for structural preflight, 30 for packaged launch, 40
for functional coverage, and 70 for execution-context errors. A passing run proves
packaged launch and non-empty local Vision requests; it does not prove OCR or
translation accuracy, clean Windows VM behavior, WACK, or Store certification.

## Packaged functional smoke boundary

The final functional stage of `packaging/test_release_smoke.ps1` now runs inside the frozen `CloudHime.exe` through an opt-in environment-controlled self-test. Host Python is still used for deterministic input validation, but it is no longer the authority for the final functional result. The packaged mode writes a redacted machine-readable result and returns a non-zero exit code on failure.

This proves the release orchestrator is wired to the packaged entrypoint only when a valid frozen build exists. It does not replace a real GPU run, a clean Windows machine, WACK/Partner Center certification, or Store submission. The current runtime must first pass `llama-server.exe --version` and produce a valid runtime manifest.
## Latest frozen GPU smoke evidence

On 2026-08-24 a fresh local frozen build completed with 26 runtime files and a valid runtime manifest. The packaged release smoke then used the new `dist\CloudHime` with a local Gemma 3 4B GGUF, its mmproj, and one example image under `-RequireGpu`; the final functional stage ran inside `CloudHime.exe` and passed. Post-run executable-path cleanup found no CloudHime-owned `llama-server.exe` process.

This is a real local GPU wiring smoke for one image, not an accuracy benchmark or Store/WACK/clean-VM certification. The local runtime lacked archived source metadata, so the build supplied `LLAMA_RUNTIME_COMMIT` from the server's reported build identifier. Release CI should continue to require the fetched runtime archive URL/hash/commit provenance.
## Unsigned MSIX packaging boundary

With the x64 Windows SDK `makeappx.exe`, `packaging\build_msix.ps1` can build an unsigned development package from the verified frozen dist. The package was unpacked and its `AppxManifest.xml`, runtime manifest, model exclusion, and sensitive-material boundary were checked successfully on 2026-08-24.

This package uses the development publisher `CN=CloudHime Development` and is not installable as a trusted Store package until the separate development-signing gate is run. Creating a short-lived certificate, signing, installing, activating, and uninstalling it requires explicit owner authorization and elevated Windows operations. Store identity and Partner Center certification remain separate gates.