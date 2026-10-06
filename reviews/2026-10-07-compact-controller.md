# 主面板資訊集中

主人提供 `D:/Downloads/2026-10-07 00 56 44.png`，確認上一版均無問題，並要求將上方引擎／資料說明移至中間、移除重複的兩排與切換引擎按鈕。

已移除上方摘要列與切換引擎按鈕，中間進度條改顯示引擎名稱／狀態，資料傳送說明在其正下方顯示一次。設定按鈕與 Ctrl+, 保留既有設定中心入口。主面板初始高度由 360 改為 320，Qt 仍可依字型與內容的最小高度擴張。

進度條填色及暖機動畫保留，文字使用既有 MarqueeLabel：溢出時捲動、hover 暫停及完整 tooltip；下載百分比與使用次數仍顯示，其他進度詳細文字保留在 tooltip。金鑰與原始錯誤內容未加入摘要。文字沿用進度條的對比色，避免深色主題白字落在淺色底。

## 驗證

- 受影響產品操作／設定主題／跑馬燈回歸：111 passed，35.74 秒，`output/compact-controller-20261007-tests.xml`。
- 高度及色彩最後修正後，設定入口、進度／次數／動畫、三語引擎摘要與 Luna 驗證聚焦回歸：18 passed、94 deselected，`output/compact-controller-20261007-focused.xml`。
- 使用假金鑰、隔離設定的真實 Controller offscreen render：淺色／深色／高對比三案通過，三張 PNG 已人工檢視；`output/compact-controller-20261007/` 保存圖片與 visual-probe.py。探針首次因匯入路徑錯誤未收集，改為 tests.test_product_experience 後通過。無 live API 或模型請求，測試 fixture 回收自身 Qt worker。
- 上一版 Luna 摘要同步已由主人這次回報確認；此排版修訂仍待主人實機觀感確認。EXE／MSIX 尚未重建，最終發行閘門不變。
