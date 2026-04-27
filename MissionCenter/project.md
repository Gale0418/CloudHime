# Project

- Name: CloudHime OCR Translation Reliability Sprint
- Goal: Build CloudHime into a Google Lens / LunaTranslator-like screen OCR translator that continuously catches bugs, translates accurately, and stays fast enough for repeated scan workflows.
- Cycle: 2026-04-25 intake and baseline planning
- Labels: ocr, translation, reliability, speed, accuracy, windows, mission-center
- Owner: User + Codex
- Current phase: Intake complete enough for planning; execution should start with bug monitoring and measurable baselines.

## Success Criteria

- The app can repeatedly scan a selected screen region and translate visible text without crashing.
- OCR accuracy is measured with reproducible sample images or manifests instead of vibes.
- Translation quality has a review set for Japanese / Chinese / English UI and dialogue-like text.
- Common paths have a visible latency budget: capture, OCR, translation, and overlay render.
- New bugs are logged, triaged, reproduced, and closed only after a smoke test.

## Reference Notes

- LunaTranslator succeeds by combining multiple extraction paths: hook-based text extraction for visual novels, embedded translation where possible, OCR fallback for arbitrary text, many translation providers, and language-learning helpers.
- CloudHime is currently closer to the OCR fallback / screen translator lane, not the hook-based visual novel lane.
- The practical near-term path is to strengthen OCR, translation provider fallback, speed measurement, and bug triage before attempting hook-style game text extraction.

## Activity Log

- 2026-04-25: MissionCenter scaffold created after intake. Baseline checks passed for OCR benchmark sample, translation cache verification, and Python compile of core modules.

## Open Comments

- Deadline / urgency is not yet specified.
- Non-goals are not yet specified. Recommend treating hook-based visual novel text extraction as out of scope until OCR screen translation is stable.
