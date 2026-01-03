# ☁️ 雲朵翻譯姬 (CloudHime)
### Windows Native Screen OCR Translator

> "It ain't perfect, but it's honest work." (｀・ω・´)

## 📖 Introduction
這是一個基於 **Windows 原生 OCR** 的螢幕即時翻譯小工具。
寫這個原本只是為了不想裝好幾 GB 的 OCR 軟體，所以直接調用 Windows 內建的 API 來跑。
適合用來啃生肉漫畫或是玩沒有文字 Hook 的日文遊戲。

### (ﾟ∀。) 誠實聲明 (Honest Disclaimer)
請不要對它抱有過高的期待，這不是那種高端的 Hook + GPT 翻譯神器：
1.  **準確度大約 80%**：WinOCR 已經很努力了，但背景複雜或是字體太藝術時，經常會漏字或看錯，這是正常的。
2.  **機翻極限**：背後接的是 Google 翻譯（備用 Argos），所以讀起來就是滿滿的機翻味，能看懂劇情大意就不錯了。
3.  **依賴環境**：因為是用視覺辨識，請確保遊戲/漫畫的字體夠清晰。

## ⚙️ How it Works
1.  **截圖**：抓取螢幕畫面。
2.  **OCR**：丟給 Windows 內建的日文辨識引擎。
3.  **翻譯**：丟給 Google 翻譯 (如果 Google 掛了會切換到 Argos 離線翻譯)。
4.  **顯示**：把翻譯結果貼在螢幕上。

## 🎮 控制面板與防 Ban 須知 (Controls)

為了避免太快被 Google 判定為機器人而封鎖 IP，請務必詳閱以下按鈕功能：

### 1. ⚡ 立即 (Instant)
*   **功能**：單次掃描，按一下掃一次。
*   **注意**：**有 10 秒強制冷卻時間**。
*   **警告**：請不要手賤一直狂點，雖然有冷卻，但頻率太高還是會被 Google 踢出來 (429 Error)。

### 2. 🎲 30s~ (隨機慢速)
*   **功能**：自動每 **25 ~ 40 秒** 隨機掃描一次。
*   **用途**：適合正常看漫畫或是慢慢玩 RPG 的節奏。
*   **安全性**：中，因為時間不固定，比較像人類的操作，大約能用三小時。

### 3. ⭐ 60s~ (隨機掛機)
*   **功能**：自動每 **50 ~ 80 秒** 隨機掃描一次。
*   **用途**：適合掛機或自動播放劇情。
*   **安全性**：高，基本上不會被抓。

> (｀・ω・´)b **小提醒**：這個程式就是去偷偷使用Google翻譯的，短時間手賤連點個一百次會被Google踹出門外的，IP被軟鎖定後最多一天內會被放出來。

## 🚀 Getting Started

### 1. Prerequisites (環境要求)
*   Windows 10 或 Windows 11。
*   **必須安裝「日文」語言套件**：
    *   *設定 > 時間與語言 > 語言與地區 > 新增語言 > 日本語*
    *   (如果不裝這個，Windows OCR 會看不懂日文，直接瞎掉)

### 2. Installation
需安裝 Python 3.10+，然後執行：

    pip install -r requirements.txt

### 3. Launch

    python CloudHime.py

> 第一次啟動時，終端機可能會顯示 `[Argos] 下載模型中...`，這是為了下載備用的離線翻譯模型，請給它一點時間。

---
(｀・ω・´)ゞ Enjoy your slightly-broken-but-readable translations!
