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
## CH-T59 production dependency 與 release gate（2026-08-04）

- production `requirements.txt` 已移除 `llama-cpp-python`；`requirements-llama-dev.txt` 僅保留 retired provider 相容測試的 exact pin。四個 production module 不再 import `LocalGemmaProvider`，`CloudHime.spec` 明確排除 `llama_cpp`／`_llama_cpp`。
- `verify_release_dist.ps1` 會拒絕 `llama_cpp` package、`_llama_cpp*.pyd`，以及 runtime 目錄外的 `llama.dll`／`ggml*.dll`；Windows fixture 同時證明 runtime 內必要 DLL 保持合法。
- TDD 證據：新增測試先得到 `2 failed`，實作後 targeted `2 passed`；不含既有真實 dist 的完整 packaging／CI／provider contract 為 `32 passed, 1 skipped, 1 deselected`；compileall 通過。
- 舊 `dist/CloudHime` 仍因缺 notices marker 失敗，且唯讀盤點確認 `_internal` 根層仍有 `llama.dll`／`ggml*.dll` 重複檔；必須 clean rebuild 後重跑，不能把舊 artifact 宣稱為通過。真實 GPU text／vision paired benchmark 仍未執行，因此 CH-T59 進入 Review 而非 Done。
- CodeRabbit 首輪 `1 major` 已修：release gate 會拒絕 runtime 外第二套 CUDA／managed DLL；第二輪 `1 minor` 已修：fixture cleanup 不再殘留 runtime 外 `llama.dll` 造成假通過；第三輪未發現新的 runtime 邏輯問題，但指出 `MissionCenter/smoke-tests.md` 有 3 個歷史格式瑕疵（字面換行、函式名誤植、黏接表列），均已依原始內容修復。
- Clean build 首輪由新 gate 正確拒絕：PyInstaller 將 build/runtime 的 llama／CUDA 依賴重複收進 _internal 根層。TDD 後在 CloudHime.spec 精確過濾 runtime-source/root-destination TOC，並讓 build_exe.bat 在壓 ZIP 前強制 preflight。重建結果：480 files、1,626,610,433 bytes、ZIP 849,426,988 bytes、0 model files、0 llama_cpp、0 runtime 外受管 DLL；release／MSIX preflight ready，packaged EXE 8 秒 lifecycle smoke 通過且 0 程序殘留。GPU vision 實測 1/1 成功（startup 12.96s、request 1.214s、match 1.0）；GPU text 6/6 成功（startup 9.23s、avg 289.8ms、p95 413.5ms），但鎖定品質分數僅 0.562，交由後續 Translation Orchestrator／Knowledge Pack 改善。CH-T59 完成。
## CH-T60 Scan Pipeline observability contract（2026-08-04）

- 新增 dependency-free scan_pipeline.py：不可變 ScanTrace／ScanTraceEvent、五個 stage、固定 outcome／error code、64-event 上限、耗時與 item count 正規化。
- OCRWorker.run_scan_once() 以 sidecar 方式記錄 capture、exact frame cache、OCR、translation 與 render dispatch；沒有搬動既有掃描／fallback 邏輯，也沒有新增或改動 public Qt signals。
- trace 僅保留固定診斷 token、實際 provider、exception class；OCR 原文、翻譯結果、prompt、API key、URL、圖片 bytes 與 raw exception message 不進 trace。CodeRabbit 找到大寫 OCR token 可能穿透白名單，已移除 case-insensitive matching 並補 regression。
- 實際驗證：targeted contract + mode matrix 67 passed；最終 ocr CI group 174 passed in 5.45s；CI inventory 4 passed；全庫 compileall exit 0，但舊 pytest ACL 目錄留下 Can't list 警告，未宣稱輸出完全乾淨。
- CodeRabbit 兩輪：首輪 3 findings，其中 2 個本階段 worker correctness 已修、1 個既有 MissionCenter smoke ledger 問題未混入；第二輪完整 staged scope 2 privacy-test findings 均已修。
- cancelled outcome 與 scan_cancelled code 已納入契約；實際 scan generation／stale frame 中途取消仍由 CH-T61 FrameGate／Temporal Stabilizer 實作，不在本階段假裝完成。
## CH-T61 FrameGate／stale generation correctness checkpoint（2026-08-04）

- 已完成：scan request generation／FIFO token、capture／OCR retry／refine／rescue／translation／stream／status／render admission stale 防護；模式、區域與渲染設定變更會在 state mutation 前取消舊 generation，auto scan 只在設定變更時重新排程，stop 不 re-arm。
- 已完成：FrameGate 以最多 64x64 immutable sample 進行 thread-safe shadow classification；精確畫面快取仍是唯一可跳過 OCR 的路徑，1px／near frame 一律繼續 OCR，避免速度優化犧牲準確度。
- paired synthetic contract：5 repeats／35 frames；exact hits 10、candidate process calls 25、nonexact false skips 0、single-frame recall 1.0、transition recall 1.0；此數據只證明 correctness／工作量，不宣稱真實 OCR 或 GPU wall-time 加速。
- 實際驗證：targeted 114 passed；OCR CI group 194 passed；benchmark group 52 passed；UI 四檔拆分 27+2+1+8=38 passed；compileall 與 diff-check exit 0。合併 UI group 在 assertion 全部跑完後卡於既有 teardown，已精確終止專屬 pytest，不把行程退出宣稱通過。
- CodeRabbit：1 次 staged review，5 issues（3 major／2 minor）；四項直接修正，stale-completion 建議改以 configuration-time cancellation 實作，避免舊 completion 取消新 scan。
- CH-T61 進入 Review 而非 Done：active near-frame／jitter suppression 仍需 owner-labeled temporal holdout 校準；在資料到位前維持 shadow-only。
