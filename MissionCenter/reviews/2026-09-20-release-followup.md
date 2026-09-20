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
- 安裝版 plugin 未附 `scripts/critic_contract.py`；正式評論紀錄的 schema 驗證能力仍須釐清，不能虛報已驗證。

## 邊界

T35 仍為 Review；不生成通過 passport。T64 真正乾淨 Windows、當前新包的管理員 WACK／簽署安裝與正式 Store gate 尚未完成。歷史套件 PASS 不轉移為新包證據。
