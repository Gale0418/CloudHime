# 2026-10-26 截圖覆蓋位置與數值輸入

使用者回報截圖模式 X=0、Y=0 時，譯文出現在原選區右方。根因是 `TransBubble.compute_screenshot_layout()` 原本先挑選選區四側的空位，再套用使用者位移；零位移仍保留自動旁置。

截圖模式現在以整個原選區為零位移覆蓋基準，不以個別 OCR 子框取代選區。文字放得下時，字幕外框與選區相同；長文或大字必要時沿選區中心擴大，空間不足時沿用字級適配與螢幕邊界保護。正值 X 向右、正值 Y 向下，靠近畫面邊緣時限制字幕不出框。

三種顯示模式的 X／Y 範圍統一為 -1000～1000 px，設定載入、正規化及 controller 同步擴大上限。X／Y 與選區框透明度改成滑桿搭配原生數值輸入框；鍵入完整值後按 Enter／Tab 或移開焦點才套用，避免輸入負值途中反覆更新。字級也保留直接輸入。透明度仍只控制選區框。

保留既有四分頁、主題、即時儲存與三種顯示模式；沒有新增常駐操作說明。數值框使用現有樣式與標籤的可及性名稱。窄視窗英文版透明度列曾出現 3 px 重疊，改為可伸縮滑桿後已消除。

## 驗證

- 先以新預期重現失敗：零位移旁置、缺少輸入框、新上限未保存，共 6 failed／1 passed。
- 涵蓋字幕、設定、模式路由、閱讀覆蓋、設定主題、設定儲存、UI、關閉與首次操作的十檔回歸，466 passed；最後窄視窗修補後，受影響字幕／設定主題兩檔再驗 53 passed。
- 實際 Qt 鍵盤輸入與 Tab 提交確認數值框、滑桿、controller、保存 payload 一致；涵蓋 ±1000、三模式、零位移貼選區、螢幕邊緣、長文串流與完成位置一致。
- 真實 Qt 控件批次渲染：繁中／淺色、英文／深色、日文／高對比，分別 760×520 與 1422×800，共六組通過。初跑重疊紀錄保留於 `visual-check.log`，複驗為 `visual-confirmation.log`；合成選區 260×414 的零位移字幕使用真實 `OverlayWindow` 渲染，沒有裁改使用者圖片。
- Luna 唯讀幾何及最後差異檢查；未確認剩餘可重現缺陷。CodeRabbit 首次因暫存目錄未指定基準分支而在審查前失敗，補上 main 後七檔審查完成，0 issues；兩次嘗試均記錄，不冒稱第一次通過。
- 原始測試 XML／log、六張設定畫面、合成覆蓋畫面、審查與建置證據放在 `app/output/render-controls-20261026/`。沒有重跑線上模型品質、遊戲負載、多 DPI／多螢幕或 Store 認證。

## 發行狀態

新技術預覽已更新於 `app/dist/CloudHime/CloudHime.exe`，SHA-256 為 `050e3b8c02165f0daf9ee5b3575207fe74820f0690b4a96c1b5c98299f604f60`。舊預覽保留於 `app/output/render-controls-20261026/rollback-preview-20261023/`。

完整初次收集後，最後的窄視窗修補以相同 PyInstaller Analysis／PYZ／EXE 流程重新凍結；1,556 個已收集依賴檔案的身分／大小／時間保持不變，未再複製大型依賴。另從 EXE 直接取出六個修改模組的 PYZ 程式碼物件，僅正規化建置路徑後，與最終來源編譯逐一相同。建置快照 manifest SHA-256 為 `15fbcbb7227ddb64c2b399b7a6332fe24412b9fd79f1f3c312d8fcb9771db0b4`。

新收集依賴的 runtime／Qt／provenance preflight、frozen import、真實 Windows OCR（1 圖／2 行）、20 秒啟動均通過；移回固定入口後，import 與 20 秒啟動再驗通過。自建程序已回收。兩個模型透過硬連結沿用 10/23 已完整雜湊驗證的同一檔案，檔案身分／大小／修改時間均一致；本輪不重新計算模型雜湊，也不重跑 CPU Vision 推論，不把舊推論結果歸給新 EXE。

來源提交 `6e3d9f30cae7e437ab41548432d5b1a0f3667df9` 的 [GitHub CI](https://github.com/Gale0418/CloudHime/actions/runs/40285089274) 八項必要檢查全部 success，兩項手動 frozen 工作按原條件 skipped。證據包括 `exe-refresh-result.json`、`embedded-code.json`、`model-reuse.json`、`preview-verification.json`、`promotion.json` 與 `promoted-*.log`。MSIX／Store 草稿不變更，CH-T55 維持 Review。使用者先前修改的背景圖片與未追蹤 Logo 保留，不列入這次 Git 提交；建置快照如實記錄使用的背景圖片位元組。
