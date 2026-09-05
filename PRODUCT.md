# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

## Users

主要使用者是在 Windows 電腦閱讀日文漫畫、遊玩日文遊戲或操作外語介面的繁體中文使用者。他們需要在不中斷原本內容與操作節奏的情況下，快速理解螢幕上的文字；必要時也會框選局部區域，或把整張畫面交給多模態模型理解。

## Product Purpose

CloudHime 是 Windows 原生的螢幕 OCR 與即時翻譯輔助工具。它透過擷取、辨識、翻譯與透明覆蓋顯示，讓使用者能繼續留在原本的漫畫、遊戲或應用程式中閱讀。成功代表翻譯結果可理解、等待時間與操作負擔可接受、錯誤與 Provider 狀態透明，且使用者能在本機與線上模型之間自由選擇。

## Positioning

CloudHime 的核心不是獨立翻譯頁面，而是把 Windows 螢幕擷取、可替換 OCR、多 Provider 翻譯、本機 Gemma、多模態看圖與透明翻譯泡泡整合成不中斷原內容的單一工作流。它同時保留 local-first 的隱私與離線路徑，也允許使用者按品質、速度與配額切換線上模型。

## Operating Context

- 主要環境是 Windows 桌面、遊戲全螢幕／視窗、漫畫閱讀器與一般應用程式。
- 核心流程為全螢幕或區域擷取、OCR／直接 Vision、翻譯、透明泡泡或浮離文字顯示。
- 設定與模型資產位於使用者 AppData；發行目標包含 PyInstaller 與 MSIX／Microsoft Store。
- UI 需要支援繁體中文與英文、明暗主題、Windows 高 DPI 與不阻塞主執行緒的背景工作。

## Capabilities and Constraints

- 保留 Windows OCR、可選 OCR backend、本機 Gemma 文字與本機 llama-server 多模態路徑。
- 線上翻譯提供 Online Gemma 與 OpenAI Luna；兩者都需要文字與圖片輸入能力。
- Online Gemma 僅使用一把 Google API key，提供 `gemma-4-26b-a4b-it` 與 `gemma-4-31b-it`；依各模型獨立的 rate／cooldown 狀態選擇與輪替，不把模型變體當成額外 project quota。
- 所有 Gemma request 固定使用 `thinkingLevel=minimal`；Luna request 固定使用 reasoning effort `none`，UI 與一般設定不得覆寫。
- API Key 不得寫入一般設定、原始碼、MissionCenter、測試產物或日誌；Windows 上使用 DPAPI 保護。
- Provider 失敗、取消、逾時、429、認證失敗與內容拒絕必須維持可辨識的語意；模型輪替只允許明確 429／404／503 且尚未產生串流輸出時進行，timeout／URLError 不得重播。
- 框選與畫面擷取屬效能敏感路徑；本次只允許低風險視覺改善，不重寫其幾何、透明度與排程行為。
- 外部專案與官方範例只作 clean-room 架構參考；新增 runtime dependency 或授權義務需另外核准。

## Brand Commitments

- 產品名稱為 CloudHime／雲朵翻譯姬。
- 語氣誠實、親切、略帶 ACG 個性，不把模型輸出包裝成百分之百正確。
- 既有雲朵與翻譯姬意象可以延續，但操作介面首先必須清楚、安靜且可信。

## Evidence on Hand

- `README.md` 記錄產品定位、核心流程、實際畫面與開發入口。
- `cloudhime_ui.py`、`translation_settings_panel.py`、`themes.py` 與 `localization.py` 是現行互動與視覺證據。
- `MissionCenter/settings-fresh-light-real.png` 與 `MissionCenter/settings-fresh-dark-real.png` 是既有設定頁實機截圖。
- `benchmarks/` 與相關 evaluator 提供既有 OCR、翻譯、Vision 與速度驗證契約；任何新 Provider 品質結論仍需獨立實測，不得由 UI 或模型規格推定。

## Product Principles

1. 閱讀不中斷：翻譯工具應留在背景，必要狀態清楚但不搶走內容焦點。
2. 準確度優先、延遲透明：不能用平均值掩蓋單案退步，也不能用漂亮動畫遮住等待。
3. Local-first、雲端可選：本機路徑永遠保留，線上能力是清楚可控的增強。
4. 失敗可理解、可恢復：錯誤要指出可行下一步，取消與降級不得產生幽靈結果。
5. 可驗證演進：介面、Provider、快取與模型行為都必須有小型可重複的驗收證據。

## Accessibility & Inclusion

互動介面必須支援鍵盤操作、可見焦點、清楚的狀態文字與不只依賴色彩的回饋；明暗主題與高 DPI 下都應保持可讀性。動態效果不得干擾即時閱讀或造成不必要的持續動作。
