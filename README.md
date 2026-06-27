# ☁️ 雲朵翻譯姬 (CloudHime)
### Windows-native Screen OCR Translator

> 「雖然不完美，但這是我能給你最誠實的輔助了。」 ( ´・ω・`)a

---

## 📖 這是什麼？

**CloudHime** 是一個專為 Windows 打造的螢幕即時翻譯工具。它的誕生不是為了取代專業翻譯，而是為了讓你在面對「生肉」漫畫、遊戲 UI 或日文對話框時，不再感到那麼無助。

### ✨ 核心特色

- **Windows 原生支援**：預設使用 Windows OCR 引擎，輕量、快速且不需要額外安裝龐大的套件。
- **靈活辨識**：支援「全螢幕掃描」與「區域框選」，哪裡不會點哪裡。
- **多樣化翻譯**：內建 Google 翻譯與 Gemini AI 模式，支援繁體中文流暢輸出。
- **按需擴充**：主程式保持極致輕量，只有在你需要時，才會導引安裝 Tesseract, EasyOCR 或 RapidOCR 等進階引擎。

---

## 🖼️ 實際畫面預覽

> (｀・ω・´)σ 總之先看圖，辨識效果好不好，圖片會說話。

**1. 漫畫閱讀 (Manga)**  
![Manga Example](https://pimg.1px.tw/blog/gale/album/101348418/848177067123312065.png)

**2. 遊戲介面 (UI)**  
![Game UI Example](https://pimg.1px.tw/blog/gale/album/101348418/848177072458466684.png)

**3. 遊戲內對話 (Dialogue)**  
![Game Dialogue Example](https://pimg.1px.tw/blog/gale/album/101348418/848177076325617017.png)

---

## ⚠️ 誠實聲明 (ﾟ∀。)

在使用之前，請先讀過這幾點，免得你對它有不切實際的幻想：

1. **辨識率不是 100%**：背景太雜、字體太藝術、或是字太小，OCR 都會擺爛。這不是程式壞了，這是目前的科技瓶頸 (눈_눈)。
2. **機器翻譯僅供參考**：不管是 Google 還是 Gemini，它們有時候會胡說八道，請發揮你的想像力來補足語境。
3. **環境設定很重要**：螢幕縮放比 (DPI)、字體清晰度都會影響辨識。

---

## ⚙️ 運作流程

1. **擷取**：抓取指定區域的畫面。
2. **辨識**：交給 Windows OCR 或你額外安裝的引擎處理。
3. **翻譯**：依目前選用的模型，送往 Google API、Gemini API，或本地 Gemma / 本地多模態服務進行轉換。
4. **顯示**：將結果以透明泡泡的形式貼回螢幕。

> 區域模式底下，系統會依情況自動做閥值掃描、影像放大、多 OCR 比對；若你選的是支援多模態的模型，則會直接以圖片理解流程為主。

---

## 📦 如何開始？

> **📝 目前專案狀態 (2026-06)：**
> 專案正處於架構穩定化與防護網建置階段（已加入 GitHub Actions CI workflow 與基礎測試），部分進階 OCR 功能（如本地端字典修正）仍在整理中。

### 直接執行 (Release)
如果你是下載打包好的版本，請直接執行 `dist/CloudHime/CloudHime.exe`。
> `install.bat` / `install.ps1` 目前主要用來準備本地 Gemma 測試環境與模型，仍偏向開發中的輔助腳本。

### 從原始碼運行 (Source)
1. 確保你有 Python 3.10+ 環境。
2. 安裝依賴：`pip install -r requirements.txt`
3. 若要準備本地 Gemma 模型，可另外執行 `install.bat` 或 `install.ps1`
4. 執行：`python CloudHime.py`

---

## 🛠️ 開發說明

- **打包**：使用 `build_exe.bat` 進行 PyInstaller 打包。
- **擴充**：支援透過 `ocr_backend_installer.py` 動態安裝額外的 OCR 堆疊。
- **隱私**：請勿將你的 `google_api_key` 或個人設定檔推送到公開倉庫。

---

## 📝 小結

CloudHime 是為了讓閱讀更輕鬆而存在的。如果你在使用過程中發現了 Bug，或者有更好的想法，歡迎回饋（雖然開發者可能正在忙著玩遊戲就是了）。

祝你能愉快地啃完那些想看很久的生肉！加油吧！(*´▽`*)

## 最近更新 (Recent Notes)

- 新增截圖模式，流程更接近「直接把圖片交給 AI」的使用體驗。
- 近期實測下，整體翻譯延遲大多受網路 API 影響；本機截圖與前處理通常落在約 0.5 到 1 秒。
- Gemma 4 的翻譯品質雖然有亮點，但速度通常比 Gemma 3 慢一些，屬於目前模型特性。

![UI Example](https://pbs.twimg.com/media/HH-L9b4aQAAy9Mm.jpg)

## 開發者導引 (Developer Guide)

本專案採用模組化架構，主要分為以下幾個核心層級：

- `CloudHime.py`: 應用程式的進入點（Entry Point），負責初始化 QApplication 並掛載主控台介面。
- `cloudhime_core.py`: 核心業務邏輯層。包含獨立的文字處理、語言偵測、OCR 結果整併等不依賴 UI 的純函式與物件。
- `cloudhime_workers.py`: 背景處理層。包含負責重度運算（如 `OCRWorker`）與外部 API 呼叫的 QRunnable / QThread 類別，避免阻塞主執行緒。
- `cloudhime_ui.py`: 介面展示層。所有 PyQt / PySide6 的視覺元件（包含 `Controller`, `OverlayWindow`, `SettingsWindow` 等）皆定義於此。

### 如何執行測試

專案使用 `pytest` 與 `pytest-qt` 進行單元測試與 UI 冒煙測試。目前本地 regression suite 為 `26 passed`，並已加入 GitHub Actions CI workflow。執行方式如下：

1. 確保已安裝測試相依套件：
   ```bash
   pip install pytest pytest-qt
   ```
2. 在專案根目錄下執行測試（CI / 無頭環境請加上 `QT_QPA_PLATFORM=offscreen`）：
   ```bash
   python -m pytest -q tests
   ```
   此指令會自動執行 `tests/` 目錄下的所有測試，確保核心邏輯與 UI 啟動正常。
