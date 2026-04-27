# Notes

## Current Project Observations

- `MissionCenter/` did not exist before this intake.
- Existing repository already has modular OCR backends: Windows OCR, Tesseract, EasyOCR, RapidOCR.
- Existing translation providers include Google via `deep_translator` and Gemma through Google Generative Language API.
- Existing settings enable OCR backend chain: windows, easyocr, rapidocr, tesseract.
- `cloudhime_ui_errors.log` contains prior settings sync errors: missing `subtext` and missing `ocr_backend_panel`.
- Existing benchmark tooling works on the bundled sample, but the sample set is too small to prove real-world accuracy.
- Several docs appear corrupted by encoding/mojibake and should be rewritten when the technical baseline is stable.

## Intake Council Snapshot

- Product angle: The desired user value is instant screen understanding: scan visible text and show readable Traditional Chinese quickly.
- Technical angle: Current architecture supports the OCR fallback lane. Hook extraction like LunaTranslator would be a later, separate subsystem.
- Verification angle: Need real screenshot cases and translation review cases; otherwise "accurate" cannot be measured.
- Risk angle: Multimodal Gemma screenshot translation may improve quality but can be slower, rate-limited, and harder to make deterministic.
- Operations angle: Continuous bug checking should be a repeatable smoke loop, not just watching logs after things break.
- Efficiency angle: Start with baselines before swapping OCR engines or adding more AI calls.
- Wild idea angle: Add a "translation flight recorder" later: save anonymized capture/OCR/translation timings for failed scans so bugs can be replayed.

## Open Questions

- What content should be optimized first: manga, visual novels/games, app UI, webpages, or all-purpose desktop text?
- What speed feels acceptable: instant under 1 second, comfortable under 2 seconds, or accuracy-first even if slower?
- Are online APIs acceptable by default, or should offline translation/OCR be prioritized?
