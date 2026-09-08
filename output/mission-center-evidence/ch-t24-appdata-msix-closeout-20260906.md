# CH-T24 AppData／路徑策略收尾證據

- Date: 2026-09-06
- Fresh contract rerun: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q -p no:cacheprovider --basetemp=.tmp-mc-t24-20260906 tests/test_settings_store.py` → `37 passed in 1.65s`.
- Covered behavior: AppData-only atomic writes, legacy installation-file read migration, AppData precedence, corrupt canonical recovery, secret-field scrubbing, model-availability snapshot placement, and no fallback write into the installation directory.
- MSIX boundary: the canonical CH-T64 release note records a real short-lived self-signed MSIX install／launch／uninstall gate with signature verification, AUMID activation, and zero package／certificate／temporary-directory residue. The packaging install script uses the read-only package location and the AppData settings contract above; no package-directory write is accepted by the settings tests.
- Result: local AppData／path／writable-directory contract and the available MSIX onboarding gate are complete for CH-T24.
- Boundary: this does not claim clean Windows VM certification, WACK, Partner Center certification, Store identity, or model-license acceptance; those remain with CH-T26／CH-T64／Store tasks.
