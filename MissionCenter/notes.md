# Notes

## Intake Council

- Product: 使用者想要的是「不用複製文字也能看懂畫面」；最強場景是遊戲、VN、漫畫、影片字幕、軟體 UI。
- Technical: 目前有 Windows OCR、多 OCR 後端設定、Gemma/Google 翻譯、區域掃描、打包腳本，但主程式仍很大，需小心改動。
- Verification: 已確認主要 Python 檔可語法編譯；後續要補 GUI 啟動、設定視窗、掃描、翻譯、打包版 smoke tests。
- Risk: Hotkey 失敗、設定視窗舊錯誤、README 亂碼、打包後 OCR 後端落差，都是商業化前要解掉的信任問題。
- Operations: 需要可回報 bug 的 log 位置、版本號、診斷步驟；不然賣出去後支援會很痛。
- Efficiency: 先建立測試集與 baseline，再優化速度與品質，避免盲修。
- Wild idea: 可以把 CloudHime 定位成「給遊戲/VN/漫畫玩家的桌面鏡頭」，不要硬碰 Google Lens 全場景。

## Current Observations

- `MissionCenter/` 已重建為乾淨工作區。
- `README.md` 有亂碼問題，應列為 P1 前置信任修復。
- `_launch_stdout.txt` 曾出現 `[Hotkey] Registration failed (Error: 1409)`。
- `cloudhime_ui_errors.log` 有舊設定視窗錯誤，需確認是否已被主人近期修復。
- `build_exe.bat` 排除 easyocr/rapidocr/tesseract，但設定檔 OCR chain 包含 rapidocr/tesseract，需確認打包版行為。

## Candidate Positioning

CloudHime: Windows screen OCR translator for games, manga, videos, and hard-to-copy UI text.

核心賣點應該是：

- 打開就能掃描指定區域。
- 翻譯直接出現在畫面附近。
- 低干擾、可長時間掛著。
- 支援本機 OCR，雲端 AI 作為可選精修。
- 有 Demo 可試，不強迫使用者一開始就掏錢。
