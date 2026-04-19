# ☁️ 雲朵翻譯姬 (CloudHime)
### Windows Native Screen OCR Translator

> "It ain't perfect, but it's honest work." ( ´・ω・`)a

## 📖 這是什麼

CloudHime 是一個給 Windows 用的螢幕即時翻譯小工具，主打：

- Windows 原生 OCR
- 框選翻譯 / 全螢幕翻譯
- Google 翻譯 / Gemma AI
- 繁體中文輸出

簡單講就是，拿來啃漫畫、遊戲 UI、對話框還算方便啦。  
當然，主人你如果期待它像科幻電影那樣一鍵通靈，那我只能先翻個白眼 (￣▽￣)"

### (ﾟ∀。) 誠實聲明

先講好，這東西不是什麼超高端黑科技翻譯神器，請不要對它抱有不切實際的幻想：

1. **辨識準確度看場合**：背景亂、字很藝術、字體很小的時候，OCR 會開始擺爛，這很正常。
2. **翻譯品質看來源**：Google / Gemma 都是機器翻譯，不是青梅竹馬幫你逐字潤稿。
3. **環境很重要**：Windows OCR、系統語言、顯示縮放、字型清晰度，都會影響結果。

---

## 🖼️ 實際畫面預覽

> (｀・ω・´)σ 先看圖，免得你又說我嘴炮。

**1. 漫畫閱讀**  
![Manga Example](https://pimg.1px.tw/blog/gale/album/101348418/848177067123312065.png)

**2. 遊戲介面 (UI)**  
![Game UI Example](https://pimg.1px.tw/blog/gale/album/101348418/848177072458466684.png)

**3. 遊戲內對話**  
![Game Dialogue Example](https://pimg.1px.tw/blog/gale/album/101348418/848177076325617017.png)

---

## ⚙️ 運作方式

1. **截圖**：抓取螢幕或框選區域。
2. **OCR**：丟給 Windows OCR 或可選外掛引擎。
3. **翻譯**：送去 Google 翻譯或 Gemma AI。
4. **顯示**：把翻譯結果直接貼回畫面。

---

## 🎮 控制面板

### 1. ⚡ 立即

- **功能**：按一下掃一次。
- **注意**：有冷卻時間，別像小孩子亂按，會被系統賞巴掌 (｀・ω・´)

### 2. 🎲 30s~

- **功能**：自動每 25 ~ 40 秒掃一次。
- **用途**：慢慢看、慢慢翻，比較像正常人。

### 3. ⭐ 60s~

- **功能**：自動每 50 ~ 80 秒掃一次。
- **用途**：掛機用，省得你一直盯著。

> (｀・ω・´)b 小提醒：如果你手速跟暴走模式一樣快，Google 很可能會覺得你不是人。

---

## 🚀 使用方法

### 1. 下載

到 GitHub Releases 下載 `CloudHime.zip`，解壓縮後執行：

`dist/CloudHime/CloudHime.exe`

### 2. 第一次啟動

- 如果你只用 Google 翻譯，通常直接開就能用
- 如果你要用 Gemma AI，請先準備 `Google API KEY`
- 也可以用環境變數 `CLOUDHIME_GOOGLE_API_KEY` 提供金鑰

### 3. 日文 OCR

請先確認 Windows 已安裝日文語言套件，不然 OCR 真的會看得很痛苦：

- 設定 > 時間與語言 > 語言與地區
- 新增語言 > 日本語

### 4. 打包成 EXE

如果你要自己打包：

```bat
build_exe.bat
```

打包完成後會產生：

- `dist/CloudHime/`
- `dist/CloudHime.zip`

---

## 🧩 可選 OCR 引擎

這些外掛引擎**不會內建進主程式**，主人要自己另外下載：

- EasyOCR
- RapidOCR
- Tesseract

我知道你想省事，但這些套件都很肥，把它們硬塞進去，EXE 會肥到像喝珍奶喝成球 (눈_눈)

---

## 🔑 API Key

如果你要用 Gemma AI：

- 可以在程式內直接輸入
- 也可以設定環境變數 `CLOUDHIME_GOOGLE_API_KEY`

我沒有把你的 KEY 打包進去，也不會把它推上 GitHub。  
這點我有幫你守住，放心啦，主人。

---

## 📦 發佈建議

### 想要使用者直接下載

建議用：

- `CloudHime.zip`

原因很簡單：  
單一 EXE 很容易超過 GitHub 的檔案限制，ZIP 也比較好管理，還能保留整個執行資料夾。

### 想要雙擊就跑

解壓縮後直接執行：

- `dist/CloudHime/CloudHime.exe`

### 不建議

- 把一堆可選外掛一起塞進主包
- 把本機設定檔或 API Key 推上去

真的，這種事情做一次就夠丟臉了，我不想讓你重演 (￣▽￣)"

---

## 🧰 本機開發

### 安裝

```bat
pip install -r requirements.txt
```

### 執行

```bat
python CloudHime.py
```

### 打包

```bat
build_exe.bat
```

---

## 📝 小結

CloudHime 不是完美工具，但它是認真做給你用的。  
如果哪天翻譯怪怪的，先別急著罵我，先檢查 OCR、語言套件、圖片清晰度和 API 設定。  
真是拿你沒辦法，不過我還是會陪你一起修好它啦 (*´▽`*)
