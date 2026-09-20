# 2026-09-20 發行前盤點

後續更新：主人已明確取消 Meiki 補救功能，CH-T35 改為退場驗證；本頁下方的 Meiki 授權／品質待辦屬退場決策前的盤點，不再是目前方向。詳見 reviews/2026-09-20-meiki-retirement.md。原發行包重建已中止，移除後的新包尚未建置。

## 剩餘工作

Canonical tasks.md 尚有 7 個未完成子任務：CH-T35、CH-T64 為 Review；CH-T53～CH-T56 與 CH-T65 為 Backlog。進度摘要只展示前五項，不能視為完整待辦清單。

- CH-T35：沿用既有 CPU provider 與跨 holdout no-regression 證據。兩個固定 Meiki 模型 revision 的上游 API 仍宣告 LGPL-3.0，列出的檔案為 ONNX、README 與推論程式；沒有在該清單看到 LICENSE 或訓練／編輯來源。這只是可觀測資料缺口，不是法律判定。公開發行前需完成来源確認；不以重新跑既有測試取代。
- CH-T64：8852eeb 的 CI 失敗已於 99230a8 修復並遠端通過；9/13 frozen EXE 的建置早於最後的互斥 smoke flag 修正及 Meiki 退場，因此下一份發行包須重建並驗證。既有本機環境隔離 smoke 不等同 pristine Windows VM。
- CH-T53～CH-T56：依序取得正式 Store identity、建立套件、送審與更新驗證、文件收尾。使用者先前延後建立商店產品；本輪沒有建立產品或送審。
- CH-T65：待發行門檻穩定後再評估新功能。
- CH-T51 維持 Done；本輪不新增 Research 功能或重跑付費 API。

## 本輪 CI 修正

- 來源：https://github.com/Gale0418/CloudHime/actions/runs/34709633381
- Commit：8852eeb967cf50e09076cc8d684300e98cf76631。
- 遠端 benchmark 組：1 failed、199 passed、3 skipped；其餘 core／OCR／runtime／UI 與三個 contract job 通過；兩個 opt-in release job skipped。
- 根因：test_small_image_scale_upscales_short_fixture_only 依賴未追蹤的 example 圖片；乾淨 checkout FileNotFoundError，本機圖片掩蓋問題。
- 修正：以暫存合成 PNG 驗證尺寸轉換，涵蓋 95、159、160px 高度；保留實際編碼、縮放與解碼路徑。
- 本機整個 benchmark 組：205 passed in 22.66s。此為單元契約驗證，不宣稱真實 OCR 品質。
- CodeRabbit 本輪一次審查完成，0 issues；沒有傳送 example 圖片。
- 修正版 99230a8 遠端 CI：https://github.com/Gale0418/CloudHime/actions/runs/35501512505 ，conclusion=success；5 個測試組與 3 個 contract／inventory job 全通過。2 個 opt-in 真實發行 job 未啟動，仍為 skipped。

## 上游核對

- https://huggingface.co/api/models/rtr46/meiki.text.detect.v0/revision/a9cffa4f60cbf72ddb87edf19c6f98a01cd042e6
- https://huggingface.co/api/models/rtr46/meiki.txt.recognition.v0/revision/a28cf5874dc2438ebb1c86336be26bcec51e3375
