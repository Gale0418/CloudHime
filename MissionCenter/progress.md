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