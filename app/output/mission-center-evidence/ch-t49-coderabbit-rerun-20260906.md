# CH-T49 Knowledge work-control review closeout

- Date: 2026-09-06
- Scope: review the Knowledge work-control UI, research builder, pack store, localization, settings persistence, and related tests in an isolated review fixture.
- CodeRabbit: authenticated agent review, free CLI allowance because the isolated fixture has no remote; 10 relevant files reviewed; `0 issues` after fixing the two reported issues.
- Fixes applied: initialize `settings_styles = build_settings_styles(theme)` before the settings spinbox stylesheet is built; construct the model-availability snapshot test path with `os.path.join`.
- Verification: `$env:QT_QPA_PLATFORM='offscreen'; python -B -m pytest -q -p no:cacheprovider --basetemp=.codex-t49-review-fix-20260906 tests/test_settings_window_theme_polish.py tests/test_settings_store.py tests/test_cloudhime_ui_smoke.py` → `89 passed in 6.93s`; targeted Knowledge wave previously recorded `100 passed`; compileall and `git diff --check` pass.
- Boundary: this closes the local code/review contract only; live Search/Jina/Gemma, Store, WACK, and clean-machine certification remain separate gates.
