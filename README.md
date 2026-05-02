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
3. **翻譯**：送往 Google API 或 Gemini AI 進行轉換。
4. **顯示**：將結果以透明泡泡的形式貼回螢幕。

---

## 📦 如何開始？

### 直接執行 (Release)
如果你是下載打包好的版本，請直接執行 `dist/CloudHime/CloudHime.exe`。

### 從原始碼運行 (Source)
1. 確保你有 Python 3.10+ 環境。
2. 安裝依賴：`pip install -r requirements.txt`
3. 執行：`python CloudHime.py`

---

## 🛠️ 開發說明

- **打包**：使用 `build_exe.bat` 進行 PyInstaller 打包。
- **擴充**：支援透過 `ocr_backend_installer.py` 動態安裝額外的 OCR 堆疊。
- **隱私**：請勿將你的 `google_api_key` 或個人設定檔推送到公開倉庫。

---

## 📝 小結

CloudHime 是為了讓閱讀更輕鬆而存在的。如果你在使用過程中發現了 Bug，或者有更好的想法，歡迎回饋（雖然開發者可能正在忙著玩遊戲就是了）。

祝你能愉快地啃完那些想看很久的生肉！加油吧！(*´▽`*)
