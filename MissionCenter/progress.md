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