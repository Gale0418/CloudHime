# CH-T109 Google 雙模型實際翻譯切片

- 2026-09-09 使用主人確認的 Google credential，僅在子程序記憶體傳遞；未匯入應用設定或保存 key。
- `output/t109_google_live.py` 透過產品 GemmaTranslationProvider，單一 Google key、auto_switch_enabled=False、合成公開文字 Good morning.、目標 zh-TW。
- gemma-4-26b-a4b-it：回傳 provider=gemma、actual_model 與要求一致、nonempty=true。
- gemma-4-31b-it：HTTPError。本次 helper 未保存 HTTP status，不能判定是 quota、權限或模型不存在；需補 bounded status 診斷，不能宣稱雙模型皆可用。
- 未測 Luna、圖片或真實串流切換；T109 不具備 Done 證據。
- 加入 HTTP status-only 診斷後，僅重試 31b 一次：provider=gemma、actual_model=gemma-4-31b-it、nonempty=true，exit 0。原始 HTTPError 原因仍未知，不歸因 key／quota；兩模型現皆取得產品路徑文字成功證據，不表示錯誤已永久消除。
