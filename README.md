# CloudHime 雲姬 ☁️

[![CI](https://github.com/Gale0418/CloudHime/actions/workflows/ci.yml/badge.svg)](https://github.com/Gale0418/CloudHime/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4.svg?logo=windows)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)

CloudHime is a Windows desktop OCR and translation assistant designed for fast, local-first screen translation workflows. It combines Windows capture, OCR, local multimodal inference, optional online translation providers, and overlay rendering in one desktop app.

> Project status: active development. Release packaging, local runtime verification, provider hardening, and Windows Store readiness are still being validated.

## ✨ Highlights

- **Local-first translation** with managed `llama-server` runtime support.
- **Screenshot and region translation** for text-heavy apps, games, manga, and desktop workflows.
- **Multiple OCR paths** with Windows OCR, Japanese OCR rescue, and local multimodal Vision fallback.
- **Online provider support** for Gemma and OpenAI-compatible translation paths.
- **Provider health and fallback logic** with bounded retry/cooldown behavior.
- **Translation overlays** rendered directly over captured screen regions.
- **Persistent translation cache** to avoid unnecessary repeated work.
- **Knowledge-pack support** for retrieval-assisted translation context.
- **MSIX packaging and release validation** tooling for Windows distribution.
- **Evidence-backed regression suite** covering OCR, runtime, UI, packaging, and benchmarks.

## 🧭 Current Architecture

CloudHime is intentionally split into narrow modules around the runtime and translation pipeline:

```text
Screen Capture
    ↓
OCR / Region Detection
    ↓
Translation Orchestrator
    ├── Local Gemma / llama-server
    ├── Online Gemma provider
    └── OpenAI provider
    ↓
Translation Cache / Knowledge Context
    ↓
Overlay Rendering
```

Important implementation areas include:

- `cloudhime_ui.py` — desktop controller and UI shell.
- `cloudhime_workers.py` — capture/OCR/translation worker paths.
- `translation_providers.py` — translation provider implementations.
- `translation_registry.py` — provider registration and capability routing.
- `provider_runtime.py` — provider health, cooldown, and runtime state.
- `local_vision_runtime.py` — managed local `llama-server` lifecycle.
- `exact_image_cache.py` / `persistent_translation_cache.py` — reuse and persistence layers.
- `packaging/` — release, provenance, MSIX, and clean-machine validation.

See [`DESIGN.md`](DESIGN.md) for the current UI design system and [`PRODUCT.md`](PRODUCT.md) for product-level decisions.

## 🛠 Requirements

CloudHime targets **Windows x64** and currently uses Python 3.10 for the validated dependency locks.

Development dependencies are pinned in:

- `requirements-ci-lock-win-amd64-py310.txt`
- `requirements-lock-win-amd64-py310.txt`
- `requirements-build-win-amd64-py310.txt`

Install the CI/development environment with:

```powershell
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements-ci-lock-win-amd64-py310.txt
```

## ▶️ Running from Source

From a configured Windows development environment:

```powershell
python CloudHime.py
```

Some features require additional runtime/model assets. CloudHime validates managed runtime assets before attempting to launch local Vision inference.

## 🧪 Testing

The canonical test inventory lives in [`ci/test_groups.json`](ci/test_groups.json). It separates the suite into:

- `core`
- `ocr`
- `runtime`
- `ui`
- `benchmarks`

Basic local syntax validation:

```powershell
python -m compileall -q -x '(^|[\\/])(\.venv|build|dist)([\\/]|$)' .
```

Example targeted test:

```powershell
python -m pytest -q tests/test_translation_providers.py
```

UI tests should normally run with the Qt offscreen backend:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q tests/test_cloudhime_ui_smoke.py
```

Benchmark locks intentionally fail closed if a locked dataset, artifact, or evaluation condition changes without an explicit review.

## 📦 Packaging

CloudHime includes tooling for frozen Windows builds and MSIX packaging.

Relevant scripts include:

- `build_exe.bat`
- `packaging/build_msix.ps1`
- `packaging/verify_release_dist.ps1`
- `packaging/test_clean_machine.ps1`
- `packaging/test_msix_install.ps1`

Release packaging uses pinned dependency/runtime provenance and explicit validation gates. Synthetic fixtures and structural smokes are not treated as proof of production GPU or Store behavior.

## 🔐 Security Notes

CloudHime attempts to keep credentials out of ordinary settings, logs, and diagnostic traces. Online provider secrets are handled separately from normal settings state, and diagnostic contracts intentionally retain bounded tokens rather than raw OCR text, prompts, image payloads, or credential values.

The project is still undergoing security hardening, including local runtime credential handling and release-distribution validation.

## 📁 Mission Center

Long-running engineering work is tracked under [`MissionCenter/`](MissionCenter/). The canonical task lifecycle source is:

```text
MissionCenter/tasks.md
```

Mission Center records task status, verification evidence, decisions, and remaining release risks. A task is not considered complete solely because an implementation exists; validation evidence must also be recorded.

## 📄 License

CloudHime is licensed under the [Apache License 2.0](LICENSE).

Third-party components and notices are documented in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
111
