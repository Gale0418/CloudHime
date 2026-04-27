# Decisions

- 2026-04-25: Treat the near-term product lane as screen OCR translation, not hook-based visual novel extraction. LunaTranslator is a useful reference, but its strongest hook/embedded translation features are a different architecture from CloudHime's current screen OCR design.
- 2026-04-25: Prioritize measurable reliability before new feature expansion: bug log triage, smoke loop, OCR benchmark, and latency budget come first.
- 2026-04-25: Keep "translation precision" as a separate workstream from OCR accuracy. Bad OCR and bad translation can look similar to the user, but they need different tests.
- 2026-04-25: Do not mark tasks Done without a smoke-test row.
