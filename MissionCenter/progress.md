# 進度

- 專案: MissionCenter
- 目標: MissionCenter workspace
- 目前狀態: 46/76 tasks
- 里程碑: CloudHime 產品完成優先；Partner Center 帳號成果已驗收
- 進度條: [######----] 61%
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
## CH-T61 locked temporal holdout closeout（2026-08-04）

- benchmark lock 升級為 `cloudhime-accuracy-speed-temporal-v2`，新增 SHA-256 綁定 `benchmarks/temporal_holdout_cases.json`；runner 只接受 canonical locked manifest，未知 schema 欄位、OCR anchors、ground truth 與非 locked path 均 fail-closed。
- 12 cases／84 frames safe exact-only/shadow policy：event recall 1.0、single-frame recall 1.0、false event skips 0、coverage 1.0、exact hits 48、gate p95 約 0.51ms；hypothetical near-skip：event recall 0.9583、single-frame recall 0.9167、false event skips 2。
- FrameGate exact-hit baseline continuity 已補齊；常見 uint8 fast path 將 synthetic candidate 約由 avg 0.88ms／p95 1.23ms 降至 avg 0.40ms／p95 0.59ms，寬整數與複數精度 regression 保持通過。數字只代表本機 frame-policy microbenchmark。
- 驗證：targeted 87 passed；OCR 195 passed；最終 benchmark＋CI inventory 62 passed；core 223 passed；benchmark lock ok；compileall／diff-check 通過。
- Gemini RPC 完成且 hub-visible；CodeRabbit 2 major 已修。CH-T61 Done，CH-T62 進 Ready。

## CH-T62 Translation Orchestrator closeout（2026-08-04）

- 新增 dependency-free translation_orchestrator.py：只管理文字 primary／fallback chain、實際 provider、requested provider、fallback reason、cache metadata、四個取消邊界與 bounded error token；不持有 provider 或 runtime，不會啟動第二套 llama engine。
- OCRWorker 保留既有 string／tuple 公開介面與 Qt signals，內部改以 TranslationResult 傳遞 metadata；Google cache hit 可保留 from_cache 與 fallback lineage，screenshot provider 結果可保留 requested／actual provider 與 fallback reason 至 scan trace。
- 翻譯相關 status／debug／stream error 不再記 raw exception；remote screenshot debug 只記 model、valid 與 raw／cleaned 長度，不記 OCR hint、prompt、API key 或模型原文。
- 驗證：targeted 156 passed；core 229 passed；OCR 196 passed；runtime 94 passed、2 skipped；UI 四檔隔離 27+2+1+8=38 passed；benchmarks 58 passed；compileall 通過。core 首跑 196 passed／33 setup errors 全為既有 C:\tmp ACL，改用 Windows 使用者 Temp 後通過。
- UI 合併 runner 在 33 個案例後停止輸出，已只終止命令列含 cloudhime-ch-t62-ui 的 pytest PID；四個檔案隔離重跑全部通過，未將合併 runner 宣稱為成功。
- Gemini 3.6 Flash High RPC request 0e58dbeb-a4f8-4197-9425-032a37301cb2／cascade b15697eb-c787-4ef5-9693-eadce11754c0，hub-visible、0 blocking；CodeRabbit uncommitted review 0 findings。CH-T62 Done，CH-T63 可開始。

## CH-T63 Profiles／Knowledge Pack closeout（2026-08-04）

- active work title 維持明確按鈕才 Research；編輯欄位只查本機 pack 狀態。Settings Save 失敗會回滾 runtime work context、保持視窗與 dirty 狀態，已建立的本地 pack 不會因 Cancel／Save 失敗刪除。
- 同作品更新會沿用既有 pack ID 產生新 revision；legacy 同名重複 pack 固定選 catalog 最新項。pack／revision 變更會先取消舊 scan generation，再切換 worker context 與 active catalog。
- Knowledge Builder completion／cancel 具鎖定 commit point；ready progress 阻塞時取消會送 cancelled，completion committed 後 cancel 回傳 false。worker 載入新 pack 失敗時會再清除 context，避免殘留舊 pack。
- 驗證：CodeRabbit 修正 focused 47 passed；最終 core 234 passed；UI 四檔分拆 36+2+1+8=47 passed；本階段先前 OCR 196 passed、runtime 94 passed／2 skipped、benchmark 58 passed；compileall／diff-check 通過。UI 合跑完成部分輸出後未退出，已精確終止專屬命令並以分拆結果為準。
- Gemini 3.6 Flash High RPC request 77e541c1-4999-4e23-bdd6-6a4f0b580c79／cascade 9b127e89-0638-4b6b-a7a6-b813248a9fea，hub-visible、0 blocking。CodeRabbit uncommitted review 2 major，均以紅燈回歸測試重現並修正；未執行第二次遠端 review。
## CH-T66 遠端模型目錄與 capability hardening（2026-08-05）

- 已完成：model catalog 成為 UI／worker／provider 的共同來源；舊 Gemma 3 遠端選項退出可選與可呼叫清單，既有設定一次遷移到 Gemma 4；Gemma 3 1B 明確標記 text-only。
- 已完成：依模型 capability 決定是否送出 sampling 欄位；本地 llama-server translation payload 套用 temperature／repeat penalty，cache key 隨參數隔離；worker／UI attribution 區分 gemma、gemini、local_multimodal。
- 已完成：四個 production 入口不再 import in-process LocalGemmaProvider；開發相容類別與測試暫留，不把本階段誤報為原始碼完全刪除。
- 實際驗證：focused 140 passed；core 243 passed；OCR 197 passed；runtime 94 passed、2 skipped；UI 分檔 47 passed；benchmarks 58 passed；tracked Python compileall 與 CRLF-aware diff-check 通過。
- 未驗證：live Models API、真實 remote endpoint、clean Windows／MSIX／Store、這批設定下的 GPU 品質與延遲。動態 availability 與離線快照留 CH-T67。
- MissionCenter doctor 仍因歷史 smoke ledger 的 16 列欄位數不符與舊 Done 任務缺標準關聯而非零；本次新增任務造成的 progress stale 已修為 46/76、61%，未把歷史帳問題誤報為通過。
## CH-T66 CodeRabbit follow-up（2026-08-05）

- RED：CodeRabbit 首輪指出兩個可重現問題：不可信 list／dict 型 gemma_model 會在 alias lookup 觸發 TypeError；本地 Gemma 生成參數改變時舊 translation／preferred／HUD memory 仍可沿用。
- 修正：非字串 gemma_model 安全正規化為空值；只有 temperature 或 repeat penalty 實際變更時才清理 translation_cache、preferred_text_memory 與 hud_memory，參數不變則保留。
- 驗證：targeted settings／worker 102 passed；model/provider/release 42 passed；core 245 passed；OCR 199 passed；tracked compileall／diff-check 通過。
- CodeRabbit 複審範圍僅 4 個修正檔，結果 0 issues；兩個隔離 review repo 已刪除。CH-T66 可維持 Done。

## CH-T64 runtime manifest checkpoint（2026-08-05）

- Gemini 唯讀盤點確認：既有 release preflight 已拒絕 in-process llama_cpp、runtime 外重複 llama/ggml/CUDA DLL、模型、secrets 與 MSIX 生成檔；主要缺口是 runtime 沒有版本／來源／檔案雜湊 manifest。
- 已新增 packaging/runtime_manifest.py：從 build/runtime 的確切 stage 內容建立 schema 1 manifest，執行 staged llama-server.exe --version，記錄 source commit、backend、architecture、server version，以及每個 staged runtime file 的 size／SHA-256。
- build_exe.bat 現在在 PyInstaller 前產生 manifest；packaging/verify_release_dist.ps1 會 fail-closed 檢查 manifest JSON、metadata、完整檔案集合、size 與 SHA-256。packaging/README.md 已同步說明。
- Regression：新增 tests/test_runtime_manifest.py，並更新 MSIX fixture 覆蓋 manifest 漂移、hash／size 不符、漏檔與多餘檔；加入 ci/test_groups.json core group。
- 實際驗證：release／MSIX／manifest targeted 21 passed, 1 skipped；core CI group 251 passed, 1 skipped；tracked Python compileall exit 0；CRLF-aware diff-check exit 0。
- 1 skipped 是舊本機 dist/CloudHime 尚未含 manifest，明確要求 clean rebuild；未執行也未宣稱 Windows SDK MSIX install、WACK、clean Windows、Store submission 或首次 GPU onboarding。

- CodeRabbit 首輪覆核 8 個小型 release／manifest／測試檔，唯一 finding 是 MSIX fixture 硬編碼還原 bytes；已改為逐案例保存／還原原始 payload，並重跑 targeted／core。複審嘗試被免費 CLI rate limit 擋下（工具回報約 28 分鐘後重置），因此未宣稱複審通過。

## CH-T64 dependency and CI contract checkpoint（2026-08-05）

- 已先以 regression test 重現 CI 與 release contract 的兩個可確定缺口：MSIX dummy fixture 沒有隨新 verifier 產生 `runtime-manifest.json`；production／CI requirements 的四個 WinRT 依賴未 exact pin。
- 修正：CI fixture 現在會依實際 placeholder runtime 檔案產生 schema 1 manifest，並在解包檢查 manifest metadata；`requirements.txt` 與 `requirements-ci.txt` 的 WinRT 套件固定為 `3.2.1`，pytest／pytest-qt 也移入 CI requirements 並固定為 `9.1.1`／`4.5.0`，workflow 不再額外安裝未鎖版本測試工具。
- TDD 證據：先得到 direct pin regression `1 failed, 8 deselected`，修正後 targeted release/MSIX/manifest/CI inventory `26 passed, 1 skipped`；MSIX CI fixture targeted `1 passed, 7 deselected`。
- 完整群組：core `252 passed, 1 skipped`；OCR `199 passed`；runtime `94 passed, 2 skipped`；benchmarks `58 passed`；UI 合併執行器逾時 180 秒，拆分後 `test_cloudhime_ui_smoke.py` `36 passed`、其餘設定／翻譯 UI `11 passed`，未把合併 runner 記為通過。
- tracked Python compileall exit 0；CRLF-aware diff-check exit 0。未宣稱完整 SBOM、transitive wheel hash、license artifact audit、clean-machine、MSIX install／launch／uninstall、WACK、Store 或 GPU onboarding 已完成。
- Gemini bridge 本輪因 Antigravity session database 回報 `attempt to write a readonly database`，兩次唯讀請求均未取得回覆；未把它記成 Gemini 完成審查。CodeRabbit 複審仍受先前免費 CLI cooldown 影響，未宣稱複審通過。

## CH-T64 dependency provenance／SBOM contract checkpoint（2026-08-05）

- 新增 `packaging/dependency_contract.py`：以 pip installation report v1 為輸入，fail-closed 檢查 exact direct requirements、完整 resolved install entries、下載 URL、SHA-256 與 license metadata，並輸出 deterministic CycloneDX 1.6 SBOM；同時可再次驗證 SBOM component／dependency graph 沒有漂移。
- CI 新增 `dependency-contract` job：Windows fresh venv → 實際 `pip install -r requirements-ci.txt --report ...` → `pip check` → contract validate／verify → 上傳 pip report 與 SBOM。README 已明確說明 report 來自被測的實際安裝，不再用另一套 `--dry-run --ignore-installed` resolution。
- TDD／review：新增 contract tests 初始 RED 兩項已修；CodeRabbit 首輪指出 pip install 未立即檢查 exit code，第二輪隔離 5 檔指出 report 與實際安裝脫鉤，兩項均以 regression test 重現後修正。第三次複審受免費 CLI rate limit（約 10 分鐘）阻擋，未宣稱通過。
- 實際驗證：dependency／CI／release／MSIX／runtime targeted `34 passed, 1 skipped`；core `260 passed, 1 skipped`；本機 Python 3.13 resolution smoke 產生並驗證 `53 components`，只作 metadata smoke，不代表 Python 3.10 Windows clean-machine；tracked compileall exit 0、CRLF-aware diff-check exit 0。
- 仍未完成：committed `--require-hashes` transitive lock、逐 wheel license evidence／正式 release bundle SBOM、clean-machine、真實 PyInstaller／MSIX install、WACK、Store 與 GPU onboarding；本 checkpoint 不把 CI placeholder 或本機 3.13 smoke 擴大宣稱。

## CH-T64 Python 3.10 Windows hash-lock checkpoint（2026-08-05）

- 已從 pip installation report 產生並提交 target-specific lock：production resolved 53 components、CI resolved 58 components；每個 distribution 都有 exact version 與 wheel SHA-256，CI Python 3.10／Windows x64 使用 `--require-hashes`。
- `dependency_contract.py` 現在會驗證 lock 的完整 component set、version、selected artifact hash，並另外驗證原始 `requirements.txt`／`requirements-ci.txt` 的 direct intent；不把 lock 誤當成跨 Python／平台通用檔。
- 實際 cross-target smoke：pip `--dry-run --ignore-installed --only-binary=:all: --require-hashes --platform win_amd64 --python-version 3.10 --implementation cp --abi cp310` 接受 CI lock 58 components；contract validate／SBOM verify 均成功。這是解析與 hash 證據，不是 clean-machine install。
- 本輪驗證：受影響 targeted `39 passed, 1 skipped`；core `265 passed, 1 skipped`；tracked Python `compileall`、CI YAML parse、CRLF-aware `diff --check` 均成功。
- 仍未完成：CI runner 實際 clean venv install、逐 wheel license evidence／正式 release bundle SBOM、production build 整合 production lock、clean Windows、MSIX install／WACK／Store、GPU onboarding；CodeRabbit 本階段前兩次 findings 已修，第三次受免費 CLI cooldown 阻擋，未宣稱複審通過。
## CH-T64 production graph／SBOM isolation checkpoint（2026-08-05）

- 已在 CI dependency-contract job 增加獨立 production Python 3.10／Windows x64 fresh venv；production lock、pip report、SBOM 與 CI graph 完全分開，避免 pytest 等測試依賴滲入正式 provenance。
- production path 以 `requirements-lock-win-amd64-py310.txt` 實際安裝、`pip check`、direct `requirements.txt` 驗證、lock 驗證與 CycloneDX 1.6 SBOM verify；CI path 維持原本 58 component contract。兩組 report／SBOM 以不同檔名上傳。
- regression：production／CI lock graph 差異精確鎖為五個 CI-only 套件；workflow 測試涵蓋 production command 的 fail-fast、獨立 venv／report／SBOM／direct intent。
- 實際驗證：targeted dependency／CI／release／MSIX `36 passed, 1 skipped`；production cross-target pip dry-run（清除本機 `PIP_NO_INDEX=1` 並使用官方 PyPI index）接受 53 components；production contract validate／SBOM verify Pass；YAML parse Pass；CodeRabbit 首輪 2 minor 已修，複查 `0 issues`。
- 仍未完成：GitHub runner 真正 production clean venv install、license evidence／正式 release bundle、PyInstaller 真打包、clean Windows、MSIX／WACK／Store／GPU 實機 gate；本輪不把 dry-run 冒充安裝完成。

## CH-T64 PyInstaller clean release artifact checkpoint（2026-08-05）

- 實際執行 `cmd.exe /d /c build_exe.bat` 成功；修正 Windows PowerShell 從外部環境帶入 PowerShell 7 `Microsoft.PowerShell.Utility` module path，避免 Windows PowerShell 5.1 找不到 `Get-FileHash`。
- build 前加入 production spec 明確排除 `pytest`、`pytest-qt`、`pluggy`、`iniconfig`、`pygments`；這些開發依賴不得污染正式包。新增 regression test，targeted `3 passed`。
- 真實 PyInstaller 6.18.0 產物：`480` files、`1,622,390,804` bytes、`0` model files；bundle audit：`pytest=0`、`llama_cpp=0`、GGUF/mmproj=0、runtime 外 llama/ggml/CUDA binary `0`；`verify_release_dist.ps1` 回傳 `Status: ready`；`dist/CloudHime.zip` 已建立。
- 已知環境訊息：HuggingFace Xet log 寫入 `D:\HuggingFaceCache` 被拒，改回 console logging；不影響 build exit `0`。PyInstaller 仍報 `charset_normalizer.md__mypyc` hidden import 與 conda `mkl_rt.dll` optional warning，尚未宣稱 clean-machine runtime。
- 完整 core runner 首次 `222 passed, 48 errors`，重試使用 workspace／使用者專用 basetemp 仍為 pytest session cleanup 的 `WinError 5`；錯誤集中於暫存目錄 ACL，不能視為 assertion failure，也不能把 core 全組宣稱通過。release／MSIX／manifest／dependency targeted 與 compileall 需以獨立命令結果為準。
- 你提供的模型目錄 P0 建議與目前 repo 狀態不完全相同：CH-T66 已移除舊遠端 Gemma 的可選／可呼叫路徑、完成設定遷移、1B text-only capability 與 attribution；仍待 CH-T67 的 live `models.list` availability snapshot，不能把動態 endpoint 可用性宣稱完成。

## CH-T67 PR1 remote model discovery contract（2026-08-05）

- 依 Google 官方 `models.list` API 契約（`GET /v1beta/models`、`nextPageToken`、`supportedGenerationMethods`）新增 dependency-free `remote_model_discovery.py`；只接受含 `generateContent` 的模型，模型名稱正規化並以本地 catalog policy 補上 image capability。
- 新增 schema 1 `ModelAvailabilitySnapshot`：只保存 API key SHA-256 fingerprint、時間、模型 capability 與來源結果，不保存原始 key；同一 key 才能讀回 snapshot，不會跨 key 污染。
- no key 不發網路；401／403 不更新或沿用 snapshot；429／其他暫時錯誤可使用同一 key 的最後 snapshot；無 snapshot 時保留靜態 catalog 作 routing fail-open，dynamic verified 狀態另行表達。
- snapshot 寫入失敗經 CodeRabbit finding 修正為非致命：新抓到的 verified 結果仍回傳，並以 `snapshot_write_failed` 保留可觀測錯誤碼。
- 實際驗證：PR1 targeted `39 passed`；discovery contract 最終 `14 passed`；tracked py_compile 與 diff-check 通過；CI inventory 已納入 `tests/test_remote_model_discovery.py`；CodeRabbit 首輪 1 minor 已以 regression 重現並修正，最終複查 `0 findings`；Gemini 唯讀架構審查 Hub-visible，未修改檔案。
- 尚未完成：PR2 非同步 worker／UI availability wiring、API key 變更與手動 refresh 事件、provider health 顯示與 live API key 實測；輸入文字不觸發網路的 UI gate 留在下一階段。

## CH-T67 PR2 非同步模型可用性 UI wiring checkpoint（2026-08-05）

- 新增 remote_model_availability_worker.py：只接收 API key 與 generation，透過獨立 QThread 呼叫既有 dependency-free discovery；worker 例外只回傳 worker_failed，不把 key 或完整例外送入結果。
- Controller 只有在設定頁明確按下「重新檢查模型」時才 emit 查詢；API key 輸入、模型切換、設定同步與作品名稱輸入都不會觸發網路。
- verified／offline snapshot 結果只過濾設定頁模型顯示；目前已選但未回傳的遠端模型仍保留且標示 tooltip，不呼叫 set_gemma_model()，stale generation 直接丟棄。
- 關閉流程會遞增 generation、停止 discovery thread，network timeout bounded 為 5 秒；既有 OCRWorker、Google／Gemma provider routing 未修改。
- 實際驗證：worker 4 passed；translation panel 10 passed；Controller availability tests 3 passed；discovery／CI inventory 19 passed；UI 排除 3 個主機 tmp ACL 測試後 47 passed、3 deselected；explicit compileall 通過；git diff --check 通過但有既有 LF/CRLF 轉換提示。
- Gemini 透過 Hub-visible local bridge 唯讀審查回覆 0 findings，未修改檔案。CodeRabbit 本小時額度已在前一 checkpoint 用滿，因此本 PR2 checkpoint 不宣稱 CodeRabbit 複審完成。
- 仍待：CodeRabbit cooldown 後 scoped review、實際 API key／live Models API、clean Windows／Store／GPU gate；本 checkpoint 不修改 provider routing，也不把 static／offline 結果宣稱成 live 驗證。

## CH-T67 PR2 review／live availability checkpoint（2026-08-05）

- Gemini 3.6 Flash High 以 Hub-visible local bridge 進行唯讀審查，涵蓋 Controller、QThread、stale generation、provider routing、API key 隱私與 UI gate，回覆 `0 findings`，未修改檔案。
- CodeRabbit scope 先排除 MissionCenter、大型／暫存檔，只建立五檔 production source fixture：`cloudhime_ui.py`、`remote_model_availability_worker.py`、`remote_model_discovery.py`、`translation_settings_panel.py`、`translation_helpers.py`。服務已進入 setup，但回覆 `rate_limit`，免費 CLI 顯示約 9 分鐘後重置；沒有可用 findings，因此不得宣稱通過或 0 issues。
- live Models API smoke 使用既有 DPAPI key 讀取流程，未輸出 key；`GET /v1beta/models` 嘗試結果為 `urllib.error.URLError / WinError 10061`（目標電腦拒絕連線），無 snapshot 寫入。這只能證明目前執行環境無法建立連線，不能判定 key 或 Google API 契約失效。
- 依 Google 官方 Models API，`models.list` 仍以分頁 `nextPageToken` 與 `supportedGenerationMethods=generateContent` 作為 discovery contract；live endpoint 需在可連線環境重跑（https://ai.google.dev/api/models）。
- 本輪由 Codex 建立的四個隔離 review fixture 已精確清除；主工作樹維持乾淨，PR2 commit `4bf70ed` 不變。舊 `.pytest`／`.tmp`／MissionCenter 產物未自動刪除，交由後續清理 checkpoint 逐項確認。
- 下一步：等待 CodeRabbit cooldown 後，以同一五檔 scope 重跑；若有 finding 先補 RED regression 再修；live API 改在可連線 Windows／CI 或主人確認的環境重測。
## CH-T67 disposable cache cleanup（2026-08-05）

- 依唯讀資料夾盤點，只清除位於 CloudHime 根目錄且可再生的 7 個 Python／pytest cache：`__pycache__`、`.pytest_cache`、兩個 `.pytest-runtime-*`、`.pytest-benchmark-lock-*`、`.pytest-tmp-core` 與 `pytest-cache-files-*`。
- 保留 `runtime`、`models`、`build`、`dist`、`scratch`、`records/private`、Knowledge Pack、MissionCenter 追蹤紀錄與歷史 CodeRabbit／review 證據；拒絕存取或用途不明的 `.test-temp-*`、`tmpkzbyv5oz`、`.env` 不自動處理。
- 清理後 Git 仍乾淨（忽略產物不進 commit）；下一輪若要整理歷史 review／pytest 副本，需逐項確認用途後再處理。
## CH-T67 CodeRabbit quota stop（2026-08-06）

- 同一五檔 production source scope 在服務 cooldown 後重試三次；CodeRabbit 分別回報 rate limit，服務倒數由約 9 分鐘、1 分鐘降至 8 秒，均未產生 findings。
- 依每小時最多三次的規則，本輪停止繼續嘗試；沒有 CodeRabbit review 結果，不宣稱 `0 issues`。Gemini 的 `0 findings` 仍是獨立的唯讀第二意見。
- 下一次若要再審查，沿用五檔 scope 並確認 CodeRabbit repository remote／organization 綁定；在 cooldown 前不重試。PR2 production code 沒有因本輪審查而修改。

## CH-T68 Region Vision-first checkpoint（2026-08-06）

- 產品方向已由 Owner 明確確認為 Vision-first。這一階段只切換 Region Bubble／Relief：OCR bbox 與文字是 optional hint，圖片與 model source_text 才是 source of truth；Screenshot 原本已直接送圖，Fullscreen 暫時維持 OCR-first，待 locked holdout 後再切換。
- 新增純 Python vision_region.py：嚴格 regions JSON 契約，拒絕額外文字、重複／越界 ID、空字串、NaN／Infinity、超大 confidence 與不合法 fenced JSON；新測試納入 core CI inventory。
- remote Gemma 與本地 llama-server 共用同一 Region Vision prompt／parser；Knowledge／dictionary evidence 保留，Gemma 3 27B legacy capability 改為 non-structured JSON 並使用 text/plain。
- OCRWorker.run_scan_once() 在 Region Bubble／Relief 可於 0 OCR backend、OCR 空結果或 OCR exception 下以 whole-region hint 接管；Vision 失敗且 OCR 有字時 fail-open 到既有翻譯，trace 保留 provider、fallback 與 bounded exception token。
- 移除無多模態能力的 gemma-3-1b-it catalog entry；settings_store.py 的 legacy alias 保留，舊設定仍遷移至 gemma-4-31b-it，Models API 回傳 1B 也不會重新進入 UI／callable surface。
- 本地回歸：core 313 passed、OCR 205 passed；後續 targeted 64 passed、trace／provider／catalog 79 passed、Region matrix 6 passed、vision parser final 17 passed。tracked compileall 與 diff-check 通過。
- GPU provider smoke：example 2026-07-14 08 10 10.png，runtime ready/gpu，首次 startup 56.112s、request 10.352s；錯誤 OCR hint 下讀出 Marking CH-T23 as Done after research completion，繁中翻譯非空，confidence 0.95，結束 stopped。
- GPU worker product-path smoke：再次 startup 14.113s、Region Bubble request 2.309s；0 OCR backend 仍輸出整區 bbox，last_provider=local_multimodal，source text 由 Vision 提供，trace 為 OCR optional no-text → translation success，結束後 llama-server processes: 0。
- CodeRabbit 隔離 5 檔審查：首輪 1 major（legacy non-JSON MIME）、複輪 1 minor（confidence overflow）、final 1 minor（fenced JSON whitespace），三項皆以 regression 先重現後修正；最後 minor 修後因本小時審查額度已用完，未宣稱 0 issues。Gemini RPC 在 dispatch 前 deadline，交付狀態不確定，未列為審查完成。
- 尚未完成：source-disjoint 漫畫／遊戲 accuracy 與 latency A/B、Fullscreen Vision-first、Game-safe ResourceGovernor／partial offload、clean Windows／Store gate。
