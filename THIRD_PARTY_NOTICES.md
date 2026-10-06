# Third-Party Notices

CloudHime's full MSIX includes the pinned Gemma model and projector, with their terms and notices in `_internal/models`. A locally built lightweight dist excludes these weights and can download them to the user's local application-data directory after the local feature is enabled. GitHub provides source code, not official binary ZIPs. CloudHime does not require or communicate with Ollama.

## Qt / Qt for Python

CloudHime uses PySide6 and Shiboken 6.10.1, with dynamically linked Qt 6.10.1
libraries. Their license terms are separate from CloudHime's Apache 2.0 license.
The GNU LGPL v3 and incorporated GNU GPL v3 texts are preserved verbatim in
`packaging/third-party-licenses/qt-6.10.1/`; `sources.json` records their pinned
upstream URLs and SHA-256 digests. The wheel's `LicenseRef-Qt-Commercial.txt`
alone does not establish a commercial Qt license or satisfy the LGPL path.

Qt and Qt for Python copyright belongs to The Qt Company Ltd. and the respective
contributors. Module and third-party attribution must be checked against the
actual bundled files; not every Qt add-on is available under LGPL.

- Qt obligations: https://www.qt.io/development/open-source-lgpl-obligations
- Qt for Python licensing: https://doc.qt.io/qtforpython-6.10/commercial/index.html
- Qt 6.10.1 corresponding source: https://download.qt.io/official_releases/qt/6.10/6.10.1/
- PySide 6.10.1 corresponding source: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.1-src/

These links identify upstream sources. They are not a claim that a binary release
has satisfied source delivery, library replacement, installation-information,
or Store terms requirements. A release must verify those obligations separately.

## GenSen Rounded UI fonts

- Project: https://github.com/ButTaiwan/gensen-font
- Pinned source commit: `d347d3fffcb45e08857052433a0b432ed4f7ace8`
- Bundled files: `GenSenRounded2TW-R.otf` and `GenSenRounded2JP-R.otf`
- License: SIL Open Font License 1.1; the full license is bundled at `assets/fonts/OFL.txt`.

The Traditional Chinese and English UI use the TW face; the Japanese UI uses the JP face. These fonts are registered only inside the application and are not installed into Windows.

## Gemma 3 4B model and multimodal projector

Gemma is provided under and subject to the Gemma Terms of Use found at https://ai.google.dev/gemma/terms.

- Official GGUF repository: https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF
- Pinned revision: `ab31416aceb30cd095cb34cc27eea120940964e4`
- Model: `gemma-3-4b-it-Q4_K_M.gguf`
- Multimodal projector: `mmproj-model-f16.gguf`
- Gemma prohibited-use restrictions and redistribution obligations apply to these assets.

CloudHime uses the pinned, unmodified model and projector files from the official `ggml-org` repository and verifies their exact sizes and SHA-256 digests before use, whether bundled or downloaded.

## llama.cpp

- Project: https://github.com/ggml-org/llama.cpp
- License: MIT
- Releases: https://github.com/ggml-org/llama.cpp/releases

The currently verified runtime is pinned to commit `1d1d9a9ed` (build 9968).
Its full MIT license, including the ggml authors' copyright line, is preserved at
`packaging/third-party-licenses/llama-1d1d9a9ed/LICENSE` with a hash and source URL
in `packaging/third-party-licenses/sources.json`. This license does not cover
NVIDIA CUDA or other separately licensed runtime libraries.

The llama.cpp runtime executable and its required libraries are application runtime components. They are bundled with the application package rather than downloaded as executable code after installation.

## Knowledge research providers

### DDGS

- Project: https://github.com/deedy5/duckduckgo_search
- Package: `ddgs` 9.14.4
- License: MIT

DDGS is a pinned local package dependency for the Knowledge Research provider, but it is lazy-loaded and used only after the user explicitly starts Knowledge Research. Normal OCR and translation do not call it. Search results are treated as untrusted candidates and are not facts until validated by later extraction and source checks.

### DDGS base runtime dependency inventory

The pinned `ddgs==9.14.4` wheel declares these base runtime dependencies; optional API, MCP and DHT extras are not part of CloudHime:

- `click` — BSD-3-Clause
- `primp` — MIT
- `lxml` — BSD-3-Clause; bundled libxml2 and libxslt components carry MIT notices
- `httpx` / `httpcore` — BSD-3-Clause
- `fake-useragent` — Apache-2.0
- `certifi` — MPL-2.0
- `anyio`, `brotli`, `h11`, `h2`, `hpack`, `hyperframe` — MIT
- `idna` — BSD-3-Clause; `socksio` — see its upstream license file

The pinned `primp` 1.3.1 source license is preserved at
`packaging/third-party-licenses/primp-1.3.1/LICENSE`. The pinned PyWinRT 3.2.1
source license for `winrt-runtime` and its Windows API projection packages is
preserved at `packaging/third-party-licenses/pywinrt-3.2.1/LICENSE`.
Their source URLs and hashes are recorded in the adjacent `sources.json`.
These copies supplement wheel metadata that omits the upstream license file;
embedded native dependencies still require their own attribution inventory.

The release build resolves these packages from the pinned DDGS dependency graph and must preserve the corresponding wheel license files in the release audit. CloudHime does not install them after Store installation.

## deep-translator Google translator adapter

- Project: https://github.com/nidhaloff/deep-translator
- Version: 1.11.4
- Adapted component: Google translator interface and input validation in `google_translation_transport.py`; CloudHime uses its own bounded JSON transport instead of the upstream HTML parser.
- Copyright: Copyright (C) 2020 Nidhal Baccouri
- License: MIT; upstream license: https://github.com/nidhaloff/deep-translator/blob/v1.11.4/LICENSE

MIT License

Copyright (c) 2020 Nidhal Baccouri

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

### lxml (DDGS runtime dependency)

- Project: https://lxml.de/
- License: BSD license; bundled libxml2 and libxslt components carry their own MIT notices

lxml is included in the release bundle because the pinned DDGS base package requires it. The release audit must retain the upstream license files listed by the resolved lxml wheel, including `LICENSES.txt`; see https://github.com/lxml/lxml/blob/master/LICENSES.txt.

### Jina Reader

- Service: https://jina.ai/reader/
- Reader endpoint: `https://r.jina.ai`

Jina Reader is an optional external service, not a bundled runtime dependency. CloudHime sends a selected public URL only after explicit Knowledge Research. Requests are bounded by timeout, response size, and public-URL checks; network failure leaves the existing OCR and translation paths available.
