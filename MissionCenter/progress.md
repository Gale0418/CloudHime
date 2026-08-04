# 進度

- 專案: MissionCenter
- 目標: MissionCenter workspace
- 目前狀態: 39/65 tasks
- 里程碑: CloudHime 產品完成優先；Partner Center 帳號成果已驗收
- 進度條: [######----] 60%
- 進行中任務:
  - CH-E6 精準與效能補強 Milestone 2 (In Progress)
  - CH-T34 圖片多模態 OCR smoke 與參數基準 (Review)
  - CH-T35 日文遊戲 OCR rescue 產品化 (In Progress)
  - CH-T32 本地 Gemma3 參數離線調校 (Review)
  - CH-T33 Optuna/TPE 採用評估 (Backlog)
- 阻塞原因:
  - 無
- 下次更新: 任務或 smoke-test 有變動後請重新執行 sync。

## PR1 correctness hardening（2026-08-04）

- 已完成：明確 `requirements-ci.txt`、history JSON schema/export、fallback provider attribution、LocalGemma idempotent close/unload、AppData canonical precedence、明確 boolean coercion、translation registry bounded error code 與 local-model gating。
- 實際驗證：targeted `26 passed`；OCR `158 passed`；UI `30 passed`；runtime `90 passed, 2 skipped`；benchmarks `49 passed`；core tail `51 passed`；translation providers `16 passed`。
- core 完整群組另有 1 個本機既有 `dist/CloudHime` THIRD_PARTY_NOTICES marker 失敗；不把它誤報為 PR1 通過，也未修改該既有 dist artifact。
- 未執行：真實 GPU llama-server／乾淨 Windows／MSIX 安裝卸載與實機 benchmark；PR2 runtime 收斂暫不實作。

## local server-backed routing regression wave（2026-08-04）

- 已完成：local model 的 gemma registry 固定指向 LocalMultimodalProvider；vision runtime 尚未 ready 或啟動失敗時保持 unavailable，不恢復或重新排程 embedded LocalGemmaProvider。
- 已新增 regression tests：server provider before runtime ready、vision failure 不恢復 embedded provider；既有 worker lifecycle expectations 同步更新為「failure 不改寫 registry」。
- 實際驗證：worker 71 passed；Windows QT_QPA_PLATFORM=offscreen 聯合 runtime/provider 143 passed；ci/test_groups.json 完整群組 543 passed, 2 skipped, 1 failed；targeted compileall 成功；隔離 CodeRabbit review findings: 0。
- 已知既有環境失敗：tests/test_msix_packaging.py::test_real_release_dist_preflight_when_available 因本機 dist/CloudHime/THIRD_PARTY_NOTICES.md 缺少 ## Knowledge research providers marker；未修改既有 dist artifact。
- 尚未驗證：真實 GPU llama-server.exe text/vision paired benchmark、乾淨 Windows 安裝、MSIX 與 Microsoft Store、runtime manifest；本輪也未移除 production llama-cpp-python，後續需另立 PR。

## local llama-server text/vision profile slice（2026-08-04）

- 已完成：新增明確 `text` / `vision` runtime profile；文字模式只需要 server/model、啟動命令不帶 `--mmproj`；vision 模式維持 projector；profile 切換先停止本 instance 持有的 server，再啟動新模式。
- 已完成：worker 依 Gemma enabled、local model 與 local multimodal 狀態選擇 profile；停用 Gemma 或切換 remote 時會停止 embedded runtime；`set_profile()` 與 `start()` 使用同一把啟動鎖。
- 已完成：managed/legacy asset receipt 與驗證支援指定 required fields，text warmup 不會要求或下載 projector；保留既有 vision 預設行為。
- 實際驗證：targeted runtime/provider/worker `167 passed`；runtime profile switch `45 passed`；修正後 assets/runtime/worker `139 passed`；compileall 與 `git diff --check` 成功；CodeRabbit 第二輪隔離 review `0 issues`。
- 完整驗證：依 `ci/test_groups.json` 執行 `548 passed, 2 skipped, 1 failed`。
- 已知既有環境失敗：`tests/test_msix_packaging.py::test_real_release_dist_preflight_when_available` 因本機 `dist/CloudHime/THIRD_PARTY_NOTICES.md` 缺少 `## Knowledge research providers` marker；本輪未修改 dist artifact，也未將它宣稱為通過。
- 尚未驗證：真實 GPU llama-server.exe text/vision paired benchmark、乾淨 Windows 安裝、MSIX／Microsoft Store、runtime manifest；production `llama-cpp-python` 仍保留，後續另立 PR。
## repository hygiene 與下一階段順序（2026-08-04）

- 主人採納新順序：先整理資料夾與鎖 benchmark，再收斂單一 llama runtime、Scan Pipeline、FrameGate／Temporal Stabilizer、Translation Orchestrator、Profiles／Knowledge Pack，最後才做 release clean-machine gate 與漫畫／插件／自動 Research。
- 已完成第一輪安全清理：33 個私有人工標註／研究 probe 移至 `records/private/`；刪除 8 個根目錄舊 log／壓測輸出／測試截圖；刪除本輪已完成的兩個 CodeRabbit 隔離副本與 `__pycache__`；未刪除 `build/`、`dist/`、`models/`、`runtime/`、`benchmarks/`、`example/`。
- 已新增 `.gitignore` disposable-artifact 規則與 `records/README.md`；尚待主人確認的清理候選包含舊歷史 CodeRabbit／pytest 暫存副本與 `build/` 中繼產物，不能用模糊 pattern 直接大批刪除。
- 下一個實作 gate：先建立 benchmark lock contract，將 accuracy、latency、coverage、fallback、GPU/CPU mode 與 source-disjoint split 固定，之後才繼續雙 llama runtime 消滅。
## 精準清理與 benchmark lock（2026-08-04）

- 已由三個只讀專家分區檢查 root source、tests、benchmarks、example、docs、MissionCenter、assets、models、runtime、build、dist、packaging 與暫存目錄；`tests/` 的 51 個測試檔皆受 `ci/test_groups.json` 引用。
- 已精準移除 69 個明確未被 Git/CI 引用的舊 pytest／測試輸出目錄（共 834 檔、約 0.001 GB）；未用模糊 pattern 刪除大範圍資料。`build/`、`dist/`、`models/`、`runtime/`、近期 PR／review／Knowledge Pack 證據保留。
- 已建立 `benchmark_lock.py` 與 `benchmarks/benchmark_lock.json`：SHA-256 鎖定三份 manifest，固定 source-disjoint、accuracy、latency stages、coverage、fallback、GPU/CPU mode 與 paired repeat policy；`tests/test_benchmark_lock.py` 已加入 core CI group。
- 實際驗證：`python benchmark_lock.py` 回傳 `ok=true`；benchmark lock + CI inventory `8 passed`；core group `218 passed, 1 failed`，唯一失敗為既有本機 `dist/CloudHime/THIRD_PARTY_NOTICES.md` 缺 `## Knowledge research providers` marker；compileall 通過，未把舊 dist 失敗宣稱為通過。
- 待逐項確認：`download_task5.py`、`fix_providers.py`、3 張沒有引用的 example 圖片、舊 CodeRabbit 副本、`build/`；因目前仍有 Python 程序且部分目錄 ACL 拒絕，先不刪除或搬移。
## CH-T59 worker ownership 收斂（2026-08-04）

- production `OCRWorker` 不再建立或清理 `LocalGemmaProvider`，並移除第二組 local-model executor／future／cancel event 與無 caller 的 embedded loader API；local text／vision 統一由 `LocalMultimodalProvider` + `LocalVisionRuntime` profile 管理。
- text profile 的 server `starting`／`progress` 會正規化為既有 `local_model_status=loading`，避免 UI 在正常下載／暖身時誤顯示失敗；Knowledge Pack 只同步實際 production providers。
- 實際驗證：`tests/test_cloudhime_workers.py`、`tests/test_local_vision_runtime.py`、`tests/test_local_multimodal_provider.py`、`tests/test_translation_providers.py`、`tests/test_knowledge_prompt_integration.py` 合計 `145 passed`。
- 尚未完成：`requirements.txt` 仍含 `llama-cpp-python`，`CloudHime.spec` 與 release preflight 尚未拒絕 in-process binding；真實 GPU paired benchmark 未執行，不宣稱完成 CH-T59。
