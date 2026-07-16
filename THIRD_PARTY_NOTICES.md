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