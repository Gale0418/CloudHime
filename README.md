# CloudHime

Windows 原生螢幕 OCR 翻譯工具。

## 特色

- 支援 Windows OCR
- 支援框選翻譯與全螢幕翻譯
- 支援 Google 翻譯與 Gemma AI
- 支援繁體中文輸出
- 可用按鈕切換可選 OCR 引擎，但預設不內建外掛引擎

## 下載與使用

如果你只是想直接使用，請下載 GitHub Release 提供的 `CloudHime.zip`，解壓縮後執行：

`dist/CloudHime/CloudHime.exe`

第一次使用時，建議先：

1. 開啟程式
2. 到翻譯設定輸入 `Google API KEY` 或改用 Google 翻譯模式
3. 需要 AI 翻譯時，再切換 Gemma 模式

## 設定

- `CLOUDHIME_GOOGLE_API_KEY`：可用環境變數提供 Google API KEY
- 程式內也可以手動輸入 API KEY
- 設定檔會儲存在本機，不會自動推上 GitHub

## 建置

如果你要自己打包：

```bat
build_exe.bat
```

打包完成後會得到：

- `dist\CloudHime\`：可直接執行的資料夾
- `dist\CloudHime.zip`：方便上傳與發佈的壓縮檔

## 可選 OCR 引擎

這些外掛引擎不會內建進主程式，使用者需要自己另外安裝：

- EasyOCR
- RapidOCR
- Tesseract

你可以在程式的 OCR 設定中開啟它們，或自己用 `pip` 安裝。

## 注意

- 這個專案的目標是「可直接執行」與「可發佈」
- 盡量保留主程式輕量化，避免把不必要的大型套件打進發佈包
- 如果你看到某些功能沒裝，通常是可選引擎沒有安裝，不是程式壞掉
