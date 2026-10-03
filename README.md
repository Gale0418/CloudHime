# ☁️ 雲朵翻譯姬 (CloudHime)
### 看懂畫面上的外語，留在原內容裡。

在 Windows 上讀日文漫畫、玩日文遊戲或操作外語介面，想看懂畫面文字又不想離開原內容時，可以用 CloudHime 擷取螢幕、辨識並翻譯文字，再以透明泡泡查看結果。第一次使用，先選「框選區域」框住一小段清楚文字，按「立即翻譯」，再看泡泡結果；需要時也能改用全螢幕掃描。Google 翻譯免 API Key；本機與線上 AI 引擎則有各自的準備與金鑰需求。

---

### ✨ 核心特色

- **留在原畫面閱讀**：翻譯結果以透明覆蓋泡泡呈現，支援全螢幕掃描與拖曳框選。
- **辨識方式可調整**：可使用 Windows OCR，並可視需要安裝其他 OCR 引擎；支援的辨識方式依安裝內容而異。
- **翻譯引擎自己選**：從設定頁選 Google 翻譯、本機 Gemma、線上 Gemma 或 Luna，並查看目前設定與可用狀態。
- **本機或雲端皆可**：本機模型在裝置上執行；使用線上引擎前可先了解哪些內容會送往服務供應者。

---

## 🖼️ 實際畫面預覽

以下畫面展示 CloudHime 在漫畫、遊戲介面與對話中的使用方式。實際辨識與翻譯會受文字清晰度、版面和所選引擎影響。

**1. 漫畫閱讀 (Manga)**  
![Manga Example](https://pimg.1px.tw/blog/gale/album/101348418/848177067123312065.png)

**2. 遊戲介面 (UI)**  
![Game UI Example](https://pimg.1px.tw/blog/gale/album/101348418/848177072458466684.png)

**3. 遊戲內對話 (Dialogue)**  
![Game Dialogue Example](https://pimg.1px.tw/blog/gale/album/101348418/848177076325617017.png)

---

## 適合的情境與使用限制

CloudHime 適合快速理解畫面文字，尤其是你想繼續留在原本的遊戲、漫畫閱讀器或應用程式裡時。它是閱讀輔助工具，不能取代專業翻譯或保證每段文字都能正確辨識、翻譯。

字體很小、低對比、背景複雜、特效字或文字排列特殊時，OCR 可能漏字或辨識錯誤；翻譯也可能失去角色語氣、上下文或專有名詞。顯示縮放、擷取範圍和所選引擎都會影響結果。重要內容請回看原文核對。

2026-10-04 已修正設定頁刪除後的延遲回呼、關閉後快捷鍵重新啟用，以及 Controller 刪除後仍殘留的設定窗。最新本機相關 UI 回歸 215 案通過；07:02 的遠端 CI 在較早版本仍發生 QThread 建立時的原生崩潰，後續快捷鍵修正版的必要 CI 工作已全數成功。歷史原生空指標的完整根因仍未確認，通過一次不能視為根治。既有 EXE／Store 安裝不含本次修正，也沒有新 EXE 驗收。時間線、失敗與驗證範圍見 [Qt 原生診斷紀錄](reviews/2026-10-04-qt-native-diagnosis.md)。

---

## ⚙️ 運作方式與資料去向

1. **擷取**：抓取指定區域的畫面。
2. **辨識**：交給 Windows OCR 或你額外安裝的引擎處理。
3. **翻譯**：依你選擇的引擎，在本機處理，或將文字／影像送往相應的線上服務。
4. **顯示**：將結果以透明泡泡的形式貼回螢幕。

區域掃描會依流程進行影像前處理與文字辨識；選用支援圖片輸入的引擎時，也可將擷取畫面交由該服務直接理解。不同引擎的輸入方式不同。

### 翻譯引擎怎麼選？

| 引擎 | 需要金鑰 | 內容處理方式 |
| --- | --- | --- |
| Google 翻譯 | 不需要 | 需網路，將待翻譯文字送往 Google 翻譯服務。 |
| 本機 Gemma | 不需要雲端金鑰 | 在本機使用 Gemma 模型；首次使用時可能需要下載模型檔。 |
| 線上 Gemma | Google API Key | 依功能送出辨識文字或畫面影像至 Google。共用一把金鑰，可在兩個 Gemma 模型間選擇。 |
| Luna | OpenAI API Key | 支援文字與圖片輸入，請求會送往 OpenAI 服務。 |

本機 OCR 與本機模型可在裝置上處理內容；即使選了本機模型，啟用雲端 OCR 或設定其他電腦上的模型端點，仍會送出相應內容。線上翻譯或圖片理解會將相應文字、影像及提示送往所選服務。CloudHime 無法決定第三方服務如何保存或使用請求資料。API 金鑰以 Windows DPAPI 使用者範圍保護後存於本機。詳情請閱讀[隱私權政策](PRIVACY.md)。

---

## 📦 如何開始？

### 第一次翻譯

1. 開啟 CloudHime。Google 翻譯不需要 API Key；若要使用其他引擎，按主窗的「切換引擎」進入「翻譯引擎」，查看各引擎的金鑰需求與狀態。
2. 選「全螢幕」翻譯畫面，或選「框選區域」後拖曳框出文字範圍。框選時會顯示尺寸；按 Esc 或選取太小的範圍會取消，保留原本的模式與範圍。
3. 按「立即翻譯」。主窗會保留擷取進度、翻譯結果與錯誤訊息；按鈕上的秒數只表示再次操作前的等待時間。
4. 需要持續翻譯時，選擇間隔再開啟「自動掃描」。運作中的按鈕會顯示「暫停」及距離下次掃描的倒數，或翻譯中的狀態；倒數不會蓋掉狀態列的錯誤訊息。想慢慢讀完時，按「暫停」會取消目前掃描並保留畫面上已顯示的字幕，再按「繼續自動掃描」按原間隔繼續。暫停期間也能調整間隔或使用「立即翻譯」。按「停止」會取消目前翻譯並清除字幕；主窗有焦點時也可以按 Esc。

### 遇到問題時

- **沒有辨識到文字：** 放大原畫面或重新框選一小段清楚、完整的文字再按「立即翻譯」；也可改試全螢幕掃描。小字、低對比、複雜背景或特殊字體都可能影響辨識。
- **遇到限流：** 先停止連續重試，查看主窗的引擎狀態；供應者恢復可用後再試，或到「設定」切換至狀態可用的引擎。線上引擎的額度由服務供應者管理。
- **模型尚未就緒：** 到「設定」→「翻譯引擎」查看狀態並完成畫面指出的準備；例如補上所需 API Key，或等待首次下載的本機模型完成。若仍無法使用，可先切換到另一個已可用的引擎。

重新框選會先停止掃描。選好範圍後，按「立即翻譯」或重新開啟「自動掃描」即可繼續；取消框選也不會自行重啟掃描。

設定中的引擎選擇會即時套用；需要金鑰的引擎請依畫面提示完成設定。關閉設定不會撤銷已套用的選項；若新引擎尚未完成必要設定，CloudHime 會保留原本的引擎。主窗可用 `Ctrl+,` 開啟設定，設定窗可用 `Ctrl+S` 儲存、`Esc` 關閉。

結束程式時若一般設定無法儲存，可選擇返回重試，或放棄未儲存變更後結束；金鑰儲存失敗時會保留視窗，讓你先處理問題。

> **版本證據（日期採 Asia/Taipei；歷史紀錄，非即時發行狀態）：**
> - **原始碼：** 2026-10-04 三輪累積記錄共 245 個不同案例通過；其中最新連續閱讀輪有 158 個案例經分檔與差異驗證通過。混跑 Qt 測試曾發生 native crash，根因未定。本輪來源差異尚未打包。詳見[產品體驗驗收紀錄](reviews/2026-10-04-sale-readiness.md)。
> - **EXE：** 2026-10-03 記錄的 Python 3.10 本機 EXE 曾通過 frozen OCR、import 與其他列明檢查；這是該次產物的證據，不表示本輪來源已打包。詳見[雲朵版驗收紀錄](reviews/2026-10-03-ocr-cloud-release.md)。
> - **Microsoft Store：** 2026-10-03 記錄中的 Store MSIX 是本機候選，尚無 Partner Center 上傳、認證或發行完成證據。各發行流程與限制見[雙軌發行手冊](docs/release-two-track.md)及上述驗收紀錄。

2026-10-04 的 CodeRabbit 補審涵蓋本次變更與較早的小檔案，共 148 檔；六項建議已逐項查證與修復，處置及複審結果見[產品體驗驗收紀錄](reviews/2026-10-04-sale-readiness.md)。2026-10-02 的歷史範圍另見[原始碼審查紀錄](reviews/2026-10-02-coderabbit-main-sync.md)。

### 下載預覽版本
前往 [GitHub Releases](https://github.com/Gale0418/CloudHime/releases) 查看打包版本；README 的 2026-10-02 紀錄中，公開版本標示為 Pre-release（預覽版），這不是目前線上版本的查核結果。若下載的是打包檔，解壓縮後執行其中的 `CloudHime.exe`；本機原始碼目錄下的 `dist/CloudHime/CloudHime.exe` 僅適用於已建置的版本。
> `install.bat` / `install.ps1` 只用來建立原始碼開發用的 .venv；它們不是 Microsoft Store 安裝器，也不會要求 Ollama 或手動下載模型。

MSIX 的本機開發自簽與 Microsoft Store 正式發行是兩條不同流程；請依[雙軌發行手冊](docs/release-two-track.md)操作。原始碼、預覽包或未簽名的 Store 上傳輸入，都不代表已完成 Store 發行。

### 從原始碼運行 (Source)
1. 建議使用 Python 3.10（Windows CI 與鎖定依賴的已驗證版本）。其他版本尚未列入 CI；本機 Python 3.13 曾在單一程序混跑全部 Qt 測試時發生 PySide6 native crash，請勿將 3.10 的測試結果視為 3.13 相容性保證。
2. 執行 `install.bat` 建立開發環境；本地 Gemma 模型與 projector 會由 CloudHime 在需要時下載、驗證並管理到使用者 AppData。
3. 執行 `run.bat`

---

## 🛠️ 開發說明

- **打包**：使用 `build_exe.bat` 進行 PyInstaller 打包。
- **擴充**：支援透過 `ocr_backend_installer.py` 動態安裝額外的 OCR 堆疊。
- **隱私**：請勿將你的 `google_api_key` 或個人設定檔推送到公開倉庫。

---

有使用回饋或遇到問題，可到[專案支援頁](https://github.com/Gale0418/CloudHime/issues)回報。GitHub issue 是公開的，請勿貼上 API Key、私人畫面或其他個人資料。

## 開發者導引 (Developer Guide)

本專案採用模組化架構，主要分為以下幾個核心層級：

- `CloudHime.py`: 應用程式的進入點（Entry Point），負責初始化 QApplication 並掛載主控台介面。
- `cloudhime_core.py`: 核心業務邏輯層。包含獨立的文字處理、語言偵測、OCR 結果整併等不依賴 UI 的純函式與物件。
- `cloudhime_workers.py`: 背景處理層。包含負責重度運算（如 `OCRWorker`）與外部 API 呼叫的 QRunnable / QThread 類別，避免阻塞主執行緒。
- `cloudhime_ui.py`: 介面展示層。所有 PyQt / PySide6 的視覺元件（包含 `Controller`, `OverlayWindow`, `SettingsWindow` 等）皆定義於此。

### 如何執行測試

專案使用 `pytest` 與 `pytest-qt` 進行單元測試與 UI 冒煙測試，並已加入 GitHub Actions CI workflow。2026-09-09 的完整 inventory 記錄為 `1455 passed, 6 skipped`；這是歷史證據，不是本次原始碼的完整回歸結果。執行方式如下：

1. 確保已安裝測試相依套件：
   ```bash
   pip install pytest pytest-qt
   ```
2. 在專案根目錄下執行測試（CI / 無頭環境請加上 `QT_QPA_PLATFORM=offscreen`）：
   ```bash
   python -m pytest -q tests
   ```
   此指令會執行全部測試；目前單一程序混跑 Qt 案例仍有未定根因的 native crash 紀錄。Windows UI 回歸請沿用 CI 的分檔隔離方式，啟用開發環境後執行：

   ```powershell
   ./ci/run_pytest.ps1 -TestFiles tests/test_product_experience.py,tests/test_cloudhime_ui_smoke.py,tests/test_reading_overlay.py -IsolateUi
   ```

舊開發工具 `download_task5.py` 現在需要固定 runtime tag、ZIP 名稱、預期 SHA-256 與來源 commit；先執行 `python download_task5.py --help` 查看必要參數。它沿用安全 runtime fetcher，驗證整包後才解壓，不再自行抓取 latest；projector 使用既有固定 revision 與雜湊。一般使用者仍依上方的安裝／啟動流程操作。

### Online Provider 驗證邊界

- Online Gemma 使用同一把 API key，UI 只呈現遮罩與兩個模型狀態：`gemma-4-26b-a4b-it`、`gemma-4-31b-it`；Luna 支援文字與圖片請求。
- Provider 只在明確的 404／429／503 且尚未產生串流輸出時輪替；timeout、網路錯誤與已輸出後的失敗不重播，避免重複計費或重複 side effect。
- Live smoke 的憑證只能以暫時程序環境提供，禁止寫入 settings、log、截圖、passport 或 repository；外部 quota、Store／WACK、clean-machine 與 Research 仍是獨立 gate。
- 可追溯證據：`output/mission-center-evidence/ch-t109-luna-vision-20260909.md`、`output/mission-center-evidence/ch-t110-ui-20260909.md`、`output/mission-center-evidence/ch-t112-regression-visual-20260909.md`。

### OCR 準確度基準

- `benchmarks/ocr_accuracy_cases.json` 目前收錄 25 個由 `example/` 截圖整理出的 seed benchmark case，涵蓋英文段落、介面標題、日文 / 中文短句與混合 UI 文本。
- 可用以下指令重跑目前的 OCR 基準：
  ```bash
  python ocr_benchmark.py benchmarks/ocr_accuracy_cases.json
  ```
- 這份 seed dataset 的目的不是宣稱現在全部辨識都正確，而是讓後續 OCR 合併、字典修正與 fallback 微調都有固定對照組。

### 速度基準

- `speed_benchmark.py` 會使用同一份 seed case，分段量測 OCR 後處理、翻譯 prompt / cache 準備，以及氣泡 render layout。
- 可用以下指令重跑目前的本機速度基準：
  ```bash
  python speed_benchmark.py benchmarks/ocr_accuracy_cases.json
  ```
