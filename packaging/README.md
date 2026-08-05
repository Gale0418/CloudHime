# CloudHime MSIX

這是 Microsoft Store 的 MSIX-first 發行入口。先執行 build_exe.bat 產生 dist/CloudHime，再在裝有 Windows SDK 的 Windows 環境執行：

    pwsh -File packaging/build_msix.ps1 -Version 0.1.0.0 -Publisher "CN=CloudHime Development" -CreateUpload

makeappx.exe 由 Windows SDK 提供。預設開發 Publisher 只適合本機驗證；送 Partner Center 前必須使用已保留的 Store identity／publisher 參數。Store MSIX 上傳與 Microsoft re-signing 仍需在 Partner Center 完成。此 Builder 目前只產生 x64 套件，因為發行 runtime 內含 x64 的 llama/ggml/CUDA 二進位檔；未來新增其他架構時，必須先提供對應 runtime 與 CI 契約。

模型與 projector 不放進 MSIX；CloudHime 會將受管模型下載到使用者 AppData，並驗證版本與 SHA-256。THIRD_PARTY_NOTICES.md 與 LICENSE 會由 PyInstaller release bundle 隨包提供。

CreateUpload also produces a manually assembled .msixupload archive containing the MSIX. Public symbols are optional and are not included by this builder yet.

## Release dist preflight

在尚未安裝 Windows SDK 的開發機上，可以先驗證真正會被放入 MSIX 的 PyInstaller bundle：

    pwsh -File packaging/build_msix.ps1 -DistDir dist/CloudHime -PreflightOnly

這個檢查會確認啟動檔、主 logo、44x44 / 50x50 / 150x150 MSIX 圖示、字典、授權 notices、llama/ggml runtime 與敏感檔案規則，也會拒絕把 GGUF、projector、簽章材料或已生成的 MSIX 檔案帶進套件。它不會修改 dist，不取代 makeappx、簽章、WACK 或乾淨 Windows 安裝測試。

## Runtime manifest

build_exe.bat stages only the release llama-server files, then runs
packaging/runtime_manifest.py. The tool executes the staged
llama-server.exe --version command and writes runtime-manifest.json beside
the runtime. The manifest records the source commit, backend, architecture,
server version, and the size/SHA-256 of every staged runtime file.
verify_release_dist.ps1 fails closed when the manifest is missing or the
runtime file set, size, or digest differs.

## Local MSIX install smoke

`packaging/test_msix_install.ps1` 會在 `pwsh` 呼叫時自動轉交 Windows PowerShell 5.1，因為部分 Windows 的 Appx cmdlet 無法由 PowerShell 7 載入。開發測試憑證只能用於本機 sideload；Store identity、publisher 與正式簽章仍必須由 Partner Center／正式憑證處理。
