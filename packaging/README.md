# CloudHime MSIX

這是 Microsoft Store 的 MSIX-first 發行入口。先執行 build_exe.bat 產生 dist/CloudHime，再在裝有 Windows SDK 的 Windows 環境執行：

    pwsh -File packaging/build_msix.ps1 -Version 0.1.0.0 -Publisher "CN=CloudHime Development" -CreateUpload

makeappx.exe 由 Windows SDK 提供。預設開發 Publisher 只適合本機驗證；送 Partner Center 前必須使用已保留的 Store identity／publisher 參數。Store MSIX 上傳與 Microsoft re-signing 仍需在 Partner Center 完成。

模型與 projector 不放進 MSIX；CloudHime 會將受管模型下載到使用者 AppData，並驗證版本與 SHA-256。THIRD_PARTY_NOTICES.md 與 LICENSE 會由 PyInstaller release bundle 隨包提供。

CreateUpload also produces a manually assembled .msixupload archive containing the MSIX. Public symbols are optional and are not included by this builder yet.
