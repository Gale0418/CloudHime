# Meiki 退場後的 CI 依賴修正

- 失敗來源：commit d17219e，GitHub Actions run 35503865243；core 在 test_msix_packaging.py／test_stabilization_contracts.py 收集階段找不到 yaml。其他四個測試組、dependency-contract、msix-contract、test-inventory 通過；兩個 opt-in 發行 job skipped。
- 根因：PyYAML 原由 Meiki 的依賴樹間接提供；移除後沒有明確列為測試依賴。本機既有安裝掩蓋了此缺口。
- 修正：requirements-ci.txt 明確固定 PyYAML 6.0.3，CI hash lock 恢復相同已知 wheel hash；production requirements／lock 不加入 PyYAML。CI-only graph regression 納入 pyyaml。
- 驗證：tests/test_dependency_contract.py 21 passed in 0.30s；pip 26.2.1 對 CI lock 的 require-hashes dry-run 成功；dependency_contract 46 components PASS。
- CodeRabbit：獨立 snapshot 僅兩個手寫變更檔（requirements-ci.txt、tests/test_dependency_contract.py），排除 lock／圖檔／產物；完成、0 issues、exit 0。
- 後續：推送修正版後確認遠端 CI；不把本機原本已安裝 yaml 當成乾淨環境證據。
