# Third-Party Notices

CloudHime can optionally download model assets after the user enables the corresponding local feature. Downloaded model files are stored under the user's local application-data directory and are not part of the core MSIX package. CloudHime does not require or communicate with Ollama.

## Gemma 3 4B model and multimodal projector

Gemma is provided under and subject to the Gemma Terms of Use found at https://ai.google.dev/gemma/terms.

- Official GGUF repository: https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF
- Pinned revision: `ab31416aceb30cd095cb34cc27eea120940964e4`
- Model: `gemma-3-4b-it-Q4_K_M.gguf`
- Multimodal projector: `mmproj-model-f16.gguf`
- Gemma prohibited-use restrictions and redistribution obligations apply to these assets.

CloudHime downloads the pinned, unmodified model and projector files from the official `ggml-org` repository and verifies their exact sizes and SHA-256 digests before use.

## llama.cpp

- Project: https://github.com/ggml-org/llama.cpp
- License: MIT
- Releases: https://github.com/ggml-org/llama.cpp/releases

The llama.cpp runtime executable and its required libraries are application runtime components. They are bundled with the application package rather than downloaded as executable code after installation.

## meikiocr

- Project: https://github.com/rtr46/meikiocr
- Package version: 0.3.1
- Package license: Apache License 2.0

## Meiki OCR model weights

- Detection model: https://huggingface.co/rtr46/meiki.text.detect.v0
- Recognition models: https://huggingface.co/rtr46/meiki.txt.recognition.v0
- Model license declared by the model cards: GNU Lesser General Public License v3.0
- License text: https://www.gnu.org/licenses/lgpl-3.0.html

CloudHime downloads pinned, unmodified ONNX files from the publishers' Hugging Face repositories and verifies their exact sizes and SHA-256 digests before use. Corresponding model sources and revision history remain available at the repository links above.

These components are used locally through ONNX Runtime on the CPU.
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

### lxml (DDGS runtime dependency)

- Project: https://lxml.de/
- License: BSD license; bundled libxml2 and libxslt components carry their own MIT notices

lxml is included in the release bundle because the pinned DDGS base package requires it. The release audit must retain the upstream license files listed by the resolved lxml wheel, including `LICENSES.txt`; see https://github.com/lxml/lxml/blob/master/LICENSES.txt.

### Jina Reader

- Service: https://jina.ai/reader/
- Reader endpoint: `https://r.jina.ai`

Jina Reader is an optional external service, not a bundled runtime dependency. CloudHime sends a selected public URL only after explicit Knowledge Research. Requests are bounded by timeout, response size, and public-URL checks; network failure leaves the existing OCR and translation paths available.
