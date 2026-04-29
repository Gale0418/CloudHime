# CloudHime

CloudHime is a Windows-native screen OCR translator. It captures text from the screen, runs OCR, and sends the result into the translation flow used by the app.

This release is intentionally lightweight: the packaged build ships with Windows OCR as the default backend, while optional OCR engines can be installed later from inside the app.

---

## What it does

- Screen and region OCR
- Live translation workflow
- Automatic rescanning for dynamic content
- Optional Google API key support for Google OCR refine and Gemini-based translation modes
- Optional OCR backend switching from the Settings panel

## Packaged build

The release build created by `build_exe.bat` is a PyInstaller `--onedir --windowed` package for Windows.

It includes:

- the CloudHime application entry point
- the WinRT imports required by Windows OCR
- a zip archive of the final `dist\CloudHime` folder

It does not bundle the optional OCR stacks, because the app already installs and manages them on demand:

- Tesseract
- EasyOCR
- RapidOCR

## OCR backends

### Built in

- **Windows OCR**: the default backend and the one used by the release bundle

### Optional

- **Tesseract**: requires the `pytesseract` Python package and a local `tesseract.exe`
- **EasyOCR**: requires `easyocr`, `torch`, and `torchvision`
- **RapidOCR**: requires `rapidocr-onnxruntime`

If an optional backend is not installed, CloudHime still works with Windows OCR.

## Requirements

- Windows 10 or Windows 11
- Python 3.10+ for running from source
- The Windows OCR component available on the system
- `pip` access to install the Python dependencies listed in `requirements.txt`

Optional features:

- Google API key for Google OCR refine or Gemini multimodal translation
- Optional OCR backends if you want to use anything beyond Windows OCR

## Quick start from source

```bash
pip install -r requirements.txt
python CloudHime.py
```

## Build a release

Before building, install the runtime dependencies plus PyInstaller:

```bash
python -m pip install pyinstaller -r requirements.txt
```

Then run:

```bat
build_exe.bat
```

The script will:

1. remove any previous `dist\CloudHime` folder and `dist\CloudHime.zip`
2. build a fresh Windows release with PyInstaller
3. compress the release folder into `dist\CloudHime.zip`

## Notes for users

- The app starts with Windows OCR because it is the smallest and most reliable packaging target.
- Optional OCR engines can be enabled later in Settings after installation.
- Google OCR is an extra refinement path, not a requirement for the core OCR flow.
