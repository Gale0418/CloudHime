# Third-Party Notices

CloudHime can optionally download and use the following Japanese OCR components after the user enables the feature. The model files are stored under the user's local application-data directory and are not part of the core MSIX package.

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

These components are used locally through ONNX Runtime on the CPU. CloudHime does not require or communicate with Ollama.