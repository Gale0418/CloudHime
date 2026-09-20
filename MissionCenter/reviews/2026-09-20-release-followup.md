# Meiki 退場後發行驗證續作

## 已確認

- `8893c6b` 的 CI run `35504262766` 完成 success；不包含 opt-in 真實發行 gate。
- fresh build 在 provenance 隔離環境重現 `ModuleNotFoundError: No module named 'packaging'`，exit 1。沒有把此輪視為 EXE／ZIP 通過。
- 根因是驗證腳本依賴 `packaging`，舊 production graph 間接包含它；Meiki 退場後該假設不成立。
- 修正沿用 `ci/requirements-contract.txt` 的 hash-pinned validator tooling，在 production report／pip check 完成後安裝，再執行 contract／SBOM。正式 dependencies 不增添 build-only 套件。
- `python -m pytest tests/test_stabilization_contracts.py tests/test_dependency_contract.py -q -p no:cacheprovider --basetemp .tmp/provenance-tooling-20260920`：31 passed in 1.48s。先前 CPython 3.10 無 pytest 的啟動失敗不算測試執行。
- 修正後真實 `packaging/prepare_release_provenance.ps1`：全新 CPython 3.10 x64 venv、require-hashes 安裝與 pip check、contract 38 components、provenance stage 均成功（exit 0）。另查 report：packaging／meikiocr／onnxruntime 均不存在。
- CodeRabbit 兩檔審查完成：1 minor issue，測試原先對本地 constant 斷言，未核對真正腳本行。已改從 `script.splitlines()` 取實際 install line；複驗 31 passed in 7.65s。未宣稱修正後外部複審，亦未增加掃描次數。

## Completion critic council

- 路線：critic_full，尚未派出；等待修正後本地驗證與適用 CodeRabbit，再凍結實際產物 snapshot。
- 主人於本輪明確批准 Luna/high、無對話歷史，3 位獨立評論者及另 1 位證據裁定者。
- 初輪總上限 16,000 tokens／每席 4,000、16 次工具／每席 4 次、10 分鐘；最多一次差異複核，額外 8,000 tokens／8 次工具／5 分鐘。不自動擴大預算。
- 安裝版 plugin 未附 `scripts/critic_contract.py`；已唯讀核對本機 Mission Center 原始碼，正式 Rust CLI 支援 `critic --input <record.json>`，將使用此入口驗證，不 fallback 或改寫 plugin。

## 邊界

T35 仍為 Review；不生成通過 passport。T64 真正乾淨 Windows、當前新包的管理員 WACK／簽署安裝與正式 Store gate 尚未完成。歷史套件 PASS 不轉移為新包證據。

- 修正 commit `67f7c78` 已推送 main；GitHub Actions run `35504682314` 完成 success。

## 新版 EXE 驗證

- 修正版 PyInstaller 完成，內建 frozen import smoke、release verifier／provenance verify PASS：362 files、1,517,736,105 bytes、0 model files。
- `dist/CloudHime/CloudHime.exe` SHA-256：`3f32e40a332db9542d3278dadceb815051d6d0321565b11552d85e98a0c32d9c`。
- `CArchiveReader` 檢查 EXE 的 `PYZ.pyz`：857 modules，meikiocr／onnxruntime／japanese_ocr_assets／japanese_ocr_runtime／japanese_ocr_rescue 均不存在；dist 遞迴檔名掃描 Meiki／ONNX 為 0。
- `packaging/test_clean_machine.ps1 -ExecutablePath dist/CloudHime/CloudHime.exe -FunctionalSmoke -AdditionalEnvironmentVariables @{CLOUDHIME_PACKAGED_IMPORT_SMOKE='1'}` PASS；20 秒 launch liveness PASS；owned PID 37912／33248 結束。
- 最初透過額外 `pwsh -File` 傳 hashtable 發生參數轉型錯誤，未啟動應用；改由目前 PowerShell 7 直接呼叫 script 後通過。未修改測試工具。
- 以上為 system-only PATH／隔離 AppData 的宿主測試，不是乾淨 Windows VM，也不是 GPU 推論、WACK、Store 驗收。

## ZIP／MSIX 與中斷恢復

- 使用者手滑中斷後，原建置及 MSIX 程序均不再執行；不宣稱原 batch 完整 exit 0。EXE／dist 已完成的驗證仍有效。
- ZIP 可開啟；重新逐一比對所有 362 個 payload 的長度與 SHA-256，與 dist 完全相同。ZIP SHA-256：`e6d17fc8bd7b7c18a864e721f880d5bc638be54f7097d995e9abea6fa1dbed91`，797,057,760 bytes。
- MSIX 留下 0-byte 空檔；確認精確路徑後刪除該空檔，從先前已完成 staging 執行 SDK MakeAppx pack，exit 0／Package creation succeeded。
- `dist/retire-20260920/out/CloudHime-0.1.0.0-x64.msix`：813,897,341 bytes；SHA-256 `16d593b16c2f8f65c1f6ece0bf30ad8741a366ee1bba47c1612a634ce55ff004`。
- MSIX ZIP 結構 365 entries；manifest 為 CloudHime／CN=CloudHime Development／x64；內含 EXE SHA-256 與已驗證 EXE 相同；Meiki／ONNX／GGUF 檔名掃描為 0。未執行完整 MakeAppx unpack 後 verifier、簽署、安裝或 WACK，不將這些標記為 PASS。
