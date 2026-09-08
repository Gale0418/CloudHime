# CH-T50 bundled DDGS／授權 notices 收尾證據

- Date: 2026-09-06
- Fresh focused contract: `python -m pytest -q -p no:cacheprovider --basetemp=.tmp-mc-t50-20260906 tests/test_release_packaging.py tests/test_msix_packaging.py -k "knowledge or ddgs or notice or dependency"` → `8 passed, 50 deselected in 12.20s`.
- Fresh frozen-dist preflight: `pwsh -NoLogo -NoProfile -File packaging/verify_release_dist.ps1 -DistDir .\\dist\\CloudHime -ExpectedArchitecture x64` → provenance verify `ok`, preflight `ready`, 391 files, 1,585,172,394 bytes, 0 model files.
- Same-day packaged evidence in `MissionCenter/smoke-tests.md` records frozen EXE DDGS import smoke exit 0, unsigned x64 MSIX unpacked DDGS import smoke exit 0, notices present, root ICU collision count 0, and environment-isolated packaged liveness for 20 seconds with exact cleanup.
- Acceptance mapping: DDGS is bundled and importable in EXE／MSIX; the packaged launch path does not depend on inherited Python／pip tooling; search failure remains fail-open by the existing Knowledge contract; `THIRD_PARTY_NOTICES.md` and preserved upstream license files make attribution inspectable.
- Result: CH-T50 local packaging／DDGS／notice contract is complete.
- Boundary: this does not claim a clean Windows VM, package signing, WACK, Partner Center certification, Store submission, or live Search／Jina availability.
