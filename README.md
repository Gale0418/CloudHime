# CloudHime

[![CI](https://github.com/Gale0418/CloudHime/actions/workflows/ci.yml/badge.svg)](https://github.com/Gale0418/CloudHime/actions/workflows/ci.yml)

A Windows desktop OCR/translation application with local-first multimodal translation and optional online providers.

## Overview

CloudHime combines screen capture, OCR, translation, rendering, and local/online model providers in a Windows desktop workflow. The current project emphasizes:

- local-first translation with managed Gemma/llama-server runtime support;
- online Gemma and OpenAI Luna providers;
- screenshot/region multimodal translation;
- bounded diagnostics and fail-closed fallback behavior;
- release packaging and MSIX verification;
- repeatable benchmark and regression evidence.

For product and design context, see [`PRODUCT.md`](PRODUCT.md) and [`DESIGN.md`](DESIGN.md).

## Development

The primary application is Python/PySide6 and targets Windows. Tests are grouped through [`ci/test_groups.json`](ci/test_groups.json).

Typical local checks:

```powershell
python -m compileall -q .
python -m pytest tests/test_cloudhime_core.py
```

The repository also contains release packaging, benchmark, local runtime, and UI regression tooling.

## Mission Center

Project execution state is tracked under [`MissionCenter/`](MissionCenter/). `MissionCenter/tasks.md` is the lifecycle source of truth; derived summaries are secondary views.

## License

See [`LICENSE`](LICENSE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
111
