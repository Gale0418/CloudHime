# Smoke Tests

| Date | Linked task ID | What was tested | How it was tested | Expected result | Observed result | Pass / fail | Run type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-04-25 | CH-T3 | OCR benchmark sample | `python .\ocr_benchmark.py .\DOCS\ocr-benchmark-sample.json` | Sample manifest runs and reports pass rate | 3/3 passed, 100.0% pass rate, average score 13.67 | Pass | automated |
| 2026-04-25 | CH-T7 | Translation cache behavior | `python .\DOCS\spd_02_translation_cache_check.py` | Repeated translation uses cache and only calls fake translator once | Helper and provider cache checks passed | Pass | automated |
| 2026-04-25 | CH-T1 | Core Python syntax/import compile | `python -m py_compile .\CloudHime.py .\ocr_backends.py .\ocr_quality.py .\translation_providers.py .\translation_helpers.py .\translation_registry.py` | Core files compile without syntax errors | Command completed successfully | Pass | automated |
