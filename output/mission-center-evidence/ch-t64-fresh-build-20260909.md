# CH-T64 目前工作樹 fresh release build

- 2026-09-09 啟動官方 `build_exe.bat`，base commit `2214b6f0407691cde9e7a16cf10650c02a7f7dfa` 加上目前未提交變更；不是乾淨 commit build。
- Python 3.10.11 x64、PyInstaller／ddgs／lxml／primp／fake_useragent／certifi imports 通過；D: 可用空間約 312 GB。
- 真實 runtime --version：9968，commit 1d1d9a9ed；以此實測值傳入 LLAMA_RUNTIME_COMMIT，沒有捏造 archive provenance。
- 原有 dist/CloudHime 與 dist/CloudHime.zip 已使用 native PowerShell 移到 output/release-backup-20260909 保留；原有 MSIX 不動。來源／目的地已檢查位於專案內，舊產物不是 reparse point。
- 本次建置 handle 42851；啟動不等於成功，尚待終態及 fresh artifact verifier。9/6 WACK PASS 不套用到這次新產物。
- 同一 handle 後續進度：runtime-manifest.json 已產生，server version 9968／1d1d9a9ed、build CUDA／x64。fresh provenance venv hash-lock 安裝成功，pip check 顯示 No broken requirements，dependency contract ok: 54 components，release provenance stage ok。
- 已進入 PyInstaller 6.18.0 Analysis；尚未完成 EXE／ZIP／release preflight。工具另警告管理員執行 PyInstaller 將於 7.0 不再允許，這是目前非阻斷警告，不等於打包失敗。
- 後續同一 handle：PyInstaller EXE／COLLECT completed successfully；release provenance verify ok；release preflight Status=ready、391 files、1,585,172,607 bytes、0 model files。已進入 ZIP 階段，整支 build 尚待 exit code。
- 新 EXE 執行 `packaging/test_clean_machine.ps1 -ExecutablePath ./dist/CloudHime/CloudHime.exe -LaunchWaitSeconds 20`，exit 0，隔離 AppData／PATH 啟動存活 20 秒通過；測試 PID 22980 已回收。這不是乾淨 Windows VM／首次模型下載驗收。
- 2026-09-09 04:57:29 +08:00 current-artifact revalidation：對目前 `dist/CloudHime/CloudHime.exe` 以同一 clean-machine harness 重跑 `-LaunchWaitSeconds 20`，exit 0、PID `31276` 已回收；再次確認隔離 AppData／PATH 啟動存活。此重跑仍不替代乾淨 Windows 首次模型下載／續傳／runtime handoff。
- 本次 fresh provenance 暫存 venv 已確認不存在（清理完成）。
- 官方 build_exe.bat 最終輸出 `Done: dist\CloudHime.zip`，handle 42851 exit 0，完整 EXE／preflight／ZIP 建置成功。後續 MSIX 為另一獨立 gate，不沿用原套件 WACK PASS。
- 新 MSIX 封裝 handle 45761 exit 0，位於 output/msix-fresh-20260909/package/CloudHime-0.1.0.0-x64.msix，原有 dist MSIX 未覆寫。
- 對此新 MSIX 執行隔離副本開發簽章／安裝啟動／WACK。原工具呼叫被使用者中斷，但權威 process 狀態確認仍執行，因此未重啟；appcert 45828 經 aitstatic 與 TE 後完成。
- 新報告 output/wack-b7f5ca8271d943159d0a15bf2bb5fd45.xml，唯一 /REPORT/@OVERALL_RESULT=PASS。這是新套件的實測，不是 9/6 artifact 報告。
- 事後 gate 44776、appcert 45828、TE 28216 均不存在；兩個 cert store 的 CloudHime ephemeral smoke 憑證合計 0，隔離簽章 staging 不存在。原 exec 被中斷故無可回收的 shell exit code，不捏造 exit 0；完成判定取自實際 XML 與清理檢查。
- 仍未完成 Partner Center 認證、正式 Store identity／提交、乾淨 Windows 首次模型下載與人工 holdout；T64 維持 In Progress。

## 2026-09-09 packaged functional smoke follow-up

- Command: `pwsh -NoLogo -NoProfile -File packaging/test_release_smoke.ps1 -DistDir dist/CloudHime -ModelPath <verified managed Gemma 3 4B> -ProjectorPath <verified managed mmproj> -ImagePath example/10001.png -LaunchWaitSeconds 20 -TimeoutSeconds 180 -RequireGpu`.
- Release preflight passed: `391` files, `0` model files, runtime manifest verified.
- Environment-isolated packaged launch passed for `20` seconds; packaged functional vision smoke passed with `status=passed`, `evaluation_mode=technical_coverage`, `1/1` image successful and `1/1` request successful. Both packaged PIDs were cleaned up by the runner.
- This is packaged technical coverage on the current machine, not a clean Windows VM, first-download/resume proof, Partner Center certification, Store submission, or human accuracy holdout.
- 2026-09-09 05:02:01 +08:00 current-artifact rerun: the same release runner completed with release preflight `391` files／`0` model files, isolated packaged launch `20` seconds, GPU functional vision smoke `1/1` request successful, both packaged PIDs cleaned, and final runner `PASS`. This strengthens current packaged runtime handoff evidence only; it does not prove clean Windows first download／resume or Partner Center／Store gates.

## Isolated managed-asset first-download／resume handoff

- 2026-09-09 05:11:56 +08:00 used a new isolated AppData root `output/clean-machine-assets-20260909/LocalAppData`; no user model directory was used.
- First pass started the real Hugging Face managed-asset downloader and was cancelled after the model `.part` reached `83,886,080` bytes; projector `.part` remained empty. The cancellation was caught as `AssetDownloadCancelled`, preserving the partial file.
- Second pass used the same destination and logged the actual requests: model `Range: bytes=83886080-`; projector first request had no Range. Both assets completed with exact sizes `2,489,757,856` and `851,251,104` bytes, and `.verified.json` was written.
- `packaging/test_release_smoke.ps1` then used those isolated, freshly downloaded／resumed assets with the current fresh EXE: preflight `391` files／`0` model files, isolated launch `20` seconds, GPU functional vision `1/1` request successful, both PIDs cleaned, runner `PASS`.
- This is a real local isolated first-download／resume／packaged-handoff gate, not a clean Windows VM or Store／Partner Center certification; the isolated asset directory was removed after evidence capture.

## Packaged product-path download／resume continuation

- A separate current-artifact run loaded `local_multimodal_enabled=true` from an isolated AppData settings file and launched the packaged EXE with system-only `PATH`, isolated `APPDATA`／`LOCALAPPDATA`, and a model `.part` at `83,886,080` bytes while projector was absent.
- The packaged worker itself completed the model to `2,489,757,856` bytes, downloaded the projector to `851,251,104` bytes, wrote the managed receipt, and spawned one newly-owned `llama-server`; the bounded gate reached `product_path_download_and_runtime=PASS`.
- Hidden-window close did not finish in the bounded wait, so the runner force-reaped the exact app PID and exact newly-owned server PID; final audit had no residual CloudHime／llama-server. No graceful exit code is claimed. Full sanitized evidence: `output/mission-center-evidence/ch-t26-product-path-asset-lifecycle-20260909.md`.

## Managed asset contract follow-up

- Targeted command: `python -X utf8 -m pytest -q -p no:cacheprovider tests/test_managed_asset_store.py tests/test_local_vision_assets.py tests/test_model_catalog.py`.
- Result: `44 passed in 1.01s`, covering HTTP Range resume and 200 fallback, oversize/hash/cancel/disk fail-closed behavior, AppData placement, verification receipts, runtime/model catalog identity, and legacy asset fallback boundaries.
- This strengthens the download／resume／handoff contract evidence but does not replace a real clean Windows first-download session.
