# Third-Party Notices

CloudHime's full MSIX includes the pinned Gemma model and projector, with their terms and notices in `_internal/models`. The lightweight ZIP excludes these weights and can download them to the user's local application-data directory after the local feature is enabled. CloudHime does not require or communicate with Ollama.

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

The release build resolves these packages from the pinned DDGS dependency graph and must preserve the corresponding wheel license files in the release audit. CloudHime does not install them after Store installation.

## deep-translator Google HTML adapter

- Project: https://github.com/nidhaloff/deep-translator
- Version: 1.11.4
- Adapted component: Google HTML translator parsing and fallback behavior in `google_translation_transport.py`
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
