# Decisions

| 日期 | 決策 | 原因 |
| --- | --- | --- |
| 2026-04-29 | 設定頁採用寬版三欄 | 更接近 image2 mockup，也比 2x2 卡片更像商業化設定面板 |
| 2026-04-29 | 頂部只保留 Theme / UI Language chip | 使用者指定放在顏色模式旁邊，且不讓文字標籤擠壞排版 |
| 2026-04-29 | 只搬 UI，不重寫功能 | 現有 controller、signal、設定儲存已可用，重寫風險高 |
| 2026-04-29 | MissionCenter 主表清掉舊任務 | HUD 由 tasks.md 驅動，舊 Done 任務會干擾新任務生命週期 |
| 2026-06-22 | logging 修法採最小退化策略 | 使用者先要完成第 1 項，因此只在 `FileHandler` 建立失敗時退化為 console-only，不同步重寫成 lazy logger |
| 2026-06-22 | UI smoke 執行期卡住拆成下一個 Ready 任務 | 這是新發現的獨立缺口，先避免擴大本輪 logging collection 修復範圍 |
| 2026-06-23 | UI smoke 測試採副作用隔離策略 | 這支 smoke test 的目的是驗證 UI 建立與收尾；將 host settings / hotkey 讀寫隔離後，才能穩定驗證 lifecycle 而不依賴主機環境 |
| 2026-06-23 | 先做本地多模態實機驗證與最小接線 | 目前自動化 routing regression 已綠燈，但真正風險落在本機服務、模型與截圖 / OCR refine 串接；先補可驗證的最小設定接線與真機 smoke，比直接擴成完整 UI 大改更能降低不確定性 |
| 2026-06-23 | 產品北極星改為「翻譯準確優先、翻譯快速第二、Microsoft Store 為最終目標」 | 使用者已明確拍板優先順序；若先做包裝或花俏功能，會放大尚未被量測與驗證的品質問題 |
| 2026-06-23 | 本地多模態 Sprint 3 降為 Backlog，先切產品化 Milestone 1 | 目前最缺的是基準、量測與字典修正工作流；沒有這些前置，後續效能或商店化工作都缺乏驗收標尺 |
| 2026-06-23 | 設定頁上架前 polish 採最小整理，不重做骨架 | 最新實機截圖與 Gemini review 都支持保留三欄；真正值得動的是可讀性、進階參數收納與資訊層級，而不是整套重設計 |
| 2026-08-04 | MSIX 發佈採「開發自簽＋Microsoft Store 正式代簽」雙軌 | 自簽免費且適合本機／CI，但不能要求一般使用者手動信任憑證；Store 可免費代簽並提供受信任安裝與更新。開發 Publisher 固定 `CN=CloudHime Development`，正式 Identity／Publisher 必須從 Partner Center 原樣複製；Azure Artifact Signing／OV 不在目前範圍 |
| 2026-08-04 | Partner Center 僅先完成個人帳號，不建立 CloudHime 產品 | CloudHime 尚未達到 release candidate；已唯讀確認帳號為個人、狀態使用中、公開 Publisher=WindSheep、產品數 0，詳細資料驗證仍處理中。新產品、名稱保留、Product identity、套件上傳與送審全部延後 |

| 2026-06-28 | 準確度 benchmark 先以 25 個 seed case 起步，而不是硬追 50 張圖片 | 目前最重要的是先建立可重複跑的 ground truth 與分類方式；一張圖可拆成多個 case，先求案例品質與覆蓋面，再逐步擴充數量 |
| 2026-07-01 | 速度 benchmark 先採本機 deterministic 三段量測，不呼叫外部翻譯 API 或本地模型 | CH-T17 的目標是建立穩定可重跑的耗時尺；真機 API / 模型延遲容易受網路、冷啟動與硬體狀態污染，後續可再以同格式追加實機量測 |
| 2026-07-02 | 字典修正採共用 helper 加 provider 接線，不先做大型 UI | CH-T18 的驗收重點是專有名詞能穩定覆蓋；先讓 Google / Gemma / Local Gemma / Local multimodal 共同使用同一份字典，再把 UI 與真機截圖體感留到後續任務 |
| 2026-07-02 | 本地多模態設定採既有 Translation 進階區最小接線 | CH-T13 只新增可操作欄位與既有保存 / 載入 / worker 套用流程，不新增獨立設定頁；URL / model 改用 editingFinished 套用以降低高頻刷新風險 |
| 2026-07-10 | CH-E6 Hybrid Search 第一刀採 local-first 離線基準，不先引入 Optuna | 使用者明確要求準確度優先、速度第二，且線上 Gemma4 太慢；先用現有 seed 圖片與 Windows OCR 量化 OCR 前處理/threshold 改善空間，避免過早新增依賴或改 runtime 路由 |
| 2026-07-10 | 本地模型採內嵌 GGUF + llama-cpp-python；Ollama 明確排除於產品需求之外 | 使用者不應被要求安裝外部模型服務；CloudHime 直接載入隨程式提供的 `models/gemma-3-4b-it.Q4_K_M.gguf`，實機驗證也以此路徑為準 |

| 2026-07-13 | 多模態實機採內嵌 llama-server + Gemma 3 GGUF + mmproj，啟動策略為 GPU 優先、載入訊號明確的 health timeout 才單次 CPU fallback | 真機已在 GPU ready 並完成 example 圖片翻譯；不要求使用者安裝 Ollama，並避免一般 timeout 被誤判為可降級 |
| 2026-07-13 | 多模態 smoke 固定使用 example/2026-07-10 00 37 20.png 並檢查「模型」視覺內容 | 該例圖有清楚可驗證文字；較細長的 617x95 圖片曾產生無法通過清理器的亂碼，不適合作為穩定 smoke fixture |
| 2026-07-13 | 圖片 OCR smoke 以 line-match 為主指標、相似度為 fallback | 一張圖片的 OCR 常含多行，而 manifest expected 是逐行 case；直接比較整張輸出會錯誤懲罰正確的額外行。line-match 先驗證 expected 行是否出現，再用 match score 量化漏字 / 誤字。 |
| 2026-07-13 | context size 先保留 4096，不因併行 GPU 資源衝突直接改成 2048 | `-c 2048` 在目前既有 llama-server 佔 VRAM 的狀態仍未通過 GPU health；沒有隔離條件就無法證明是品質或速度改善，先記為待重跑 A/B。 |

| 2026-07-13 | CH-T34 Hybrid OCR hint A/B | 保留 Windows OCR hint 作為多模態弱提示，不改原圖、不把 hint 當答案 | 4 unique images / 5 cases：average_match 0.9714 -> 0.9867；日文 0.8571 -> 0.9333；平均延遲 15.94s -> 15.97s，符合準確度優先、速度第二 |
| 2026-07-13 | CH-T34 prompt / scale 淘汰 | 不採用 strict OCR、日文專用 prompt 或 3x 小圖放大 | strict=0.963、日文 prompt=0.960、3x 與 baseline 同分且略慢；避免把無效變因帶入正式路徑 |
| 2026-07-14 | CH-T34 GPU-only benchmark 閘門與分段計時 | 保留 GPU 優先，但 benchmark 不能把 CPU fallback 或 -ngl 0 當成 GPU 成功；新增 --require-gpu、--gpu-layers，並量測 hint / encode / model request / postprocess | 目前外部 Dreamsprite llama-server 佔用 VRAM，-ngl 20/1 與 context 512 仍 health timeout；先保留 4096 預設，不在資源未隔離前宣稱 GPU A/B 完成 |
| 2026-07-14 | CloudHime 發布目標固定為 Microsoft Store，採 MSIX-first 評估 | 現有 install.ps1 / install.bat / build_exe.bat 是開發者 bootstrap / PyInstaller 流程，不等於商店交付；MSIX 能提供 Store 發布、安裝與更新整合 | 先做 CH-T23 / CH-T24 / CH-T26 的 research 與路徑收斂，不在核心品質基準尚未收斂前直接製作商店包；模型資產約 3.34 GB raw，需另決策 |
| 2026-07-14 | 模型分發採核心 MSIX + app-managed model asset download | 讓只用 Google / Windows OCR 的使用者不用先下載約 3.34 GB；需要本地 Gemma 時仍由 CloudHime 自己管理模型，不引入 Conda、pip 或 Ollama | 模型資產放使用者可寫 AppData，必須有版本、SHA-256、續傳、取消、進度與磁碟空間檢查；Store optional package 留作後續評估，第一版不依賴 |
## 2026-07-15：日文 OCR 採選擇性專用 rescue，不全面灌入 OCR hint

- 決策：保留 Gemma 3 baseline prompt 作主要 OCR；strict prompt 與全面 Windows OCR hint 均淘汰。
- 採用：只在高假名比例（>=0.25）且寬高比（>=3.0）的圖片，才評估 meiki 字元 confidence；候選平均 confidence >=0.75、低信心比例 >0 且 <=0.25 且與 Gemma 分歧時，最多追加一次原圖驗證。
- 防退化：第二次結果只有在對 meiki 高信心字元的相似度嚴格提升時才採用。
- 產品邊界：目前只加入 benchmark；正式接線移至 CH-T35，先處理 LGPL-3.0、AppData 下載、SHA-256、進度與背景 CPU 暖身。
- 原因：25-case 從 0.9892 提升到 0.9949，失敗日文達完全正確；其他六張未觸發，維持原輸出與速度路徑。

## 2026-07-15：CH-T35 正式路由與模型配送

- 第一版採使用者明確勾選後，由 CloudHime 下載未修改的 meiki ONNX 到 %LOCALAPPDATA%\CloudHime\models\japanese-ocr；核心 MSIX 不綁約 44 MiB 權重，也不採 Store optional package。
- 資產固定版本、revision、大小與 SHA-256，支援 .part 續傳；驗證成功後才以原子取代啟用。套件固定 meikiocr==0.3.1，執行使用 CPUExecutionProvider，不占 Gemma GPU。
- rescue 僅在「本地多模態已啟用 + 日文 rescue 已啟用 + 高假名寬字幕 gate 通過」時執行；任何下載、初始化、OCR 或驗證錯誤都保留原始 Gemma 結果。
- UI 的啟用、下載、暖身、完成與失敗狀態同時提供繁中與英文；本流程直接使用程式內模型與本機 CPU，與 Ollama 無關。
- meikiocr 程式碼為 Apache-2.0，官方 detection / recognition 模型卡標示 LGPL-3.0；已加入 THIRD_PARTY_NOTICES.md 與來源連結。Microsoft Store 送審前仍需做一次正式授權審查。

## 2026-07-16：CH-T36 翻譯文字採系統 UI 字體與 Qt fallback

- 採用 QFontDatabase 的系統 GeneralFont 作全域 UI 字體，保留 Windows 預設 hinting；翻譯泡泡從 parent widget 複製同一個 QFont，排版量測、浮雕單行寬度與實際繪製不再分裂。
- 不打包 Microsoft JhengHei 等商用系統字體，也不在第一版內建 Noto / Source Han CJK；避免授權風險與核心 MSIX 增加數十 MiB。
- 暫不提供任意系統字體下拉選單，避免使用者選到缺少繁中或符號 glyph 的字體。未來只有在實際需求成立時，才做具字元覆蓋驗證的進階選擇或可選 OFL 字體資產。
- 此決策同時適用繁中與英文 UI，並依賴 Qt / Windows 的逐字元 fallback 處理混合拉丁字、繁中與日文符號。

## 2026-07-16：CH-T26 Gemma 受管資產與 Store 邊界

- 模型與 projector 固定使用官方 `ggml-org/gemma-3-4b-it-GGUF` revision `ab31416aceb30cd095cb34cc27eea120940964e4`，並鎖定 exact size / SHA-256；不再依賴 mutable `main` 或 `latest` 作產品執行路徑。
- GGUF / mmproj 放 `%LOCALAPPDATA%\CloudHime\models\gemma-3-4b-it`；`llama-server.exe` 與 DLL 視為核心套件 runtime，不在安裝後下載可執行碼，降低 Microsoft Store 審查風險。
- 保留現有 app-root `models/` 的 exact-size 相容路徑，讓開發機與既有安裝不必重新下載；新安裝使用 AppData 受管路徑。
- 首次下載支援 `.part` Range 續傳、取消、磁碟空間檢查、SHA-256 與原子 promote；完整驗證後寫入 revision / size / mtime 收據，後續啟動不重算 3.34 GB hash。
- Gemma Terms notice 已加入 THIRD_PARTY_NOTICES；正式 Store 送審前仍須在乾淨 Windows/MSIX onboarding smoke 一併確認條款呈現與接受流程。
## 2026-07-16：聯合專家審查收斂方向

- Store / 供應鏈與 UX 兩席一致把 AppData 唯讀邊界列為立即風險，CH-T24 已先修正並進入 Review。
- ML / OCR 席指出目前速度與 vision benchmark 會高估端到端品質，先建立 CH-T37，再做 Hybrid / Gemma 參數搜尋。
- 準度優先的下一個 correctness gate 是 CH-T38：target language 與 prompt 必須隔離所有翻譯記憶。
- 保留一個可行的新點子：只對完全相同影像做 OCR 前置短路；近似 MSE / perceptual hash 未經動態遊戲資料集驗證前不得上線，以免漏字幕。
- 發布 release gate 固定為無 Python / Conda / pip / Ollama 的乾淨 Windows + MSIX smoke。

## 2026-07-16：CH-T37 / CH-T38 correctness gate 與漫畫 holdout

- 端到端評估採 source group 與 image 雙重 split-disjoint；case id、image、語言、reference、prediction id 與 stage 名先正規化，空白 model output 視為 missing 並對品質聚合貢獻零分。
- 準確度仍優先於速度：品質權重固定為翻譯字元分數 0.65、必要術語召回 0.20、OCR 字元相似度 0.15；速度分開記錄 capture / OCR / encode / runtime / model / fallback / total 的 avg、p95 與 coverage。
- Google、Gemma、Local Gemma、Local multimodal 與 screenshot output validation 的有效 target language 必須一致；cache key 同時隔離 target、prompt/model 與 local endpoint，設定切換會清除 worker translation memories。
- 漫畫封面只作未調參的 test holdout。六張素材皆由 Wikimedia Commons 提供公版標記與來源頁；保留原始影像，不做銳化或二值化後再當 ground truth，以免把前處理偏好洩漏進基準。
- CodeRabbit 只審 code、tests 與 manifests，不上傳 GGUF、圖片與 runtime binary；本次兩輪有效審查由 18 項收斂至 3 項，再由聚焦與整合測試驗證，不追加第三輪額度。
## 2026-07-16 CH-T19 OCR 分列權威實作

- 決策：normalize、內容過濾、CJK join 與水平分列只保留 ocr_quality.py 一份權威實作；舊模組維持相容轉送。
- 決策：混合高度候選可用垂直重疊進入同列，但必須與列內每個既有成員相容，禁止高 bbox 成為上下列橋樑。
- 非目標：本階段不推測垂直漫畫閱讀順序、不調 provider fallback、不新增 OCR 依賴。

## 2026-07-16 CH-T20 fallback 品質契約

- 決策：fallback 只由可解釋原因碼觸發，不再以單行字數比例覆蓋正確短譯。
- 決策：繁中目標下平假名視為未翻句子；片假名專名可與中文共存。英文目標下，沒有英文字母的漢字或假名輸出視為來源字系殘留。
- 決策：多模態分段結果只修可疑段；fallback 自身仍不合格時保留原圖片結果，避免二次錯譯。screenshot 空結果只由外層執行一次文字 fallback，並保存實際 provider attribution。

## 2026-07-16 CH-T25 provider 健檢與 onboarding 契約

- Google 基本翻譯可直接使用；只有遠端 AI 模型需要 Google API key，設定完成不等同已連線，真正連線檢查留到翻譯開始時。
- 本地 Gemma 由 CloudHime 管理下載、驗證、載入與暖身；使用者不需安裝 Ollama、Python、Conda 或 pip。CPU ready 必須明示可用但較慢，GPU ready 才是建議主路徑。
- 錯誤提示以可行動分類呈現，不直接顯示原始 stderr：timeout/CUDA/記憶體、資產/雜湊、runtime/server、port 與一般失敗各自提供修復方向。
- 本地純文字模型即使 vision runtime 缺失仍可使用；只有啟用本地多模態時，才把 embedded runtime 缺失視為修復項目。
## 2026-07-18：CH-T40 採碰撞安全、記憶體有界的精確畫面快取

- 決策：使用 `CRC32 + shape/dtype/context` 作快速索引，但任何命中都必須再以 `np.array_equal` 比對不可變快照；不採 perceptual hash 或 OCR-text-only shortcut，準確度優先。
- 決策：容量同時限制 4 entries 與 32 MiB retained bytes，並涵蓋 metadata 深層物件；新快照配置前先淘汰舊 entry，避免 4K 動態畫面同時保留兩份快照。
- 決策：只快取所有段落都有可信 provider 的成功翻譯；exception、空結果、來源文字 fallback 不快取，避免一次暫時失敗變成持久空白或錯譯。
- 決策：快取上下文納入 threshold 與 Japanese rescue readiness；閾值自動校正或 rescue runtime ready 後，同一圖片仍會重新 OCR／翻譯。
- 決策：移除僅依 OCR 合併文字重用 `last_results` 的捷徑，並把 multimodal fallback cache 加入影像 digest，避免同文字不同畫面誤用舊翻譯。
- 不採用：Gemini 建議全面停用 fullscreen cache。實測 4K miss 約 8.07ms、hit 約 19.53ms，相對 15 秒級模型流程很小；改採預先淘汰降低配置峰值，保留靜態全螢幕場景的巨大收益。

## 2026-07-18：CH-T41 慢碟與 rescue 仲裁決策

- 本機多模態 cold start health 預算採 240 秒，依據 D 槽 mmproj 851 MiB 冷讀實測 86.54 秒；前提是背景執行、stderr 分段進度可見、stop() 可立即取消且不得在取消後 CPU fallback。
- benchmark 必須使用正式 JapaneseOCRRuntime、受管資產與 preferred vision assets；--require-complete 將部分成功視為失敗，避免把缺案例的結果當成最佳解。
- 2026-07-18 正式路徑未重現舊版 rescue 採納：Meiki 候選較 baseline 接近 ground truth，但二次 Gemma 驗證拒絕。不得為單一歌詞直接採納候選；下一輪以漫畫 holdout 與更多日文字幕做穩健仲裁評估。
- .part 在取消後刻意保留供 Range 續傳；只有 size / SHA-256 驗證成功才原子 promote，這是可恢復下載策略，不視為資源洩漏。
## 2026-07-18 CH-T42 漫畫 OCR 路由決策

- 決策：Windows OCR 保留為快速主路徑；目前 Gemma 3 4B 全圖 OCR 與 OCR hint A/B 均未勝過傳統 OCR，不升格為主要辨識器。
- 決策：多模態只在可信漫畫頁且 OCR 明確不可靠時保底；任意直式 Latin 畫面不得觸發，模型截斷、重複退化或例外皆保留原 OCR。
- 決策：局部漫畫頁只傳 page crop，不把整個多螢幕截圖送入模型；輸出座標仍映回原螢幕。
- 下一方向：先做文字區域／分格候選與閱讀順序，再用人工 holdout 評估；不以這 15 張反覆調 prompt 或 threshold。

## 2026-07-18 CH-T43 有界漫畫精修決策

- 不採固定 2x3 tiles 作一般預設：15 張 aggregate anchor recall 完全不變，平均延遲超過兩倍，OCR 呼叫由 3 增至 21。
- 採 OCR-first bounded refinement：只處理已有 CJK 且至少兩段文字的全螢幕漫畫頁；候選由粗掃描 bbox 產生，最多 4 區。
- 直框只試 90/270，其他框只試 0 度；沿用粗掃描 threshold，不展開三閾值搜尋。全方向與三閾值實測皆更慢且曾造成頁面退步。
- 原始框與加 padding 後的最終框都不得超過頁面 30%；候選局部分數必須至少高 5，否則保留 baseline。任何精修例外 fail-open。
- 私人圖片、anchor manifest 與逐頁輸出不進版控；MissionCenter 只保存 aggregate 指標。
## 2026-07-23 CH-T43 coverage 與 deadline 修正

- 候選幾何覆蓋由 35% 收緊為 80%，避免只辨識到半個 baseline 框就覆蓋可信原文；候選必須覆蓋該區域全部 baseline items，否則整區保留 baseline。
- 增加 normalize 後 SequenceMatcher 文字一致性 0.20；這只作保守仲裁，不宣稱語意正確性，因 OCR score 仍不是 ground truth。
- 精修期限以 monotonic deadline 傳入 OCR scheduling 與 future collection；到期取消未開始 future、放棄逾時結果，但不強行終止正在使用 Windows OCR engine 的執行緒。
- 最新 15 張 A/B 只有 1 個 anchor 淨收益，故不把 threshold／Hybrid Search 繼續放寬；下一個高價值方向是局部多模態 crop 與文字區域／分格偵測。
## 2026-07-23：Knowledge Pack 未來工作邊界

- DDGS 是 CloudHime 發行包內建依賴；開發者負責安裝與打包，一般 EXE／Microsoft Store 使用者不得被要求執行 pip。
- 搜尋是 optional、best-effort／experimental 能力；DDGS import、backend、rate limit 或 upstream 變更只可讓 Research 顯示不可用或失敗，不得影響既有 OCR／翻譯啟動。
- DDGS 只負責取得候選 URL，正文固定交由無 API Key 的 Jina Reader 讀取；SearchProvider 必須抽象化，以便未來替換 backend。
- 設定頁頂部採可編輯 `QComboBox`：下拉列出既有 packs，也允許輸入新作品；控制區與 Theme／Language 同列並沿用既有 styling。此項取代 2026-04-29「頂部只保留 Theme / UI Language chip」的舊範圍。
- Research／Update 是明確的立即資料操作；建立完成的 pack 獨立保存，但只有按 Save 才切換 runtime active pack。
- Cancel 只放棄尚未儲存的 active work title／pack 選擇，不刪除已建立 pack。
- 第一版不提供刪除 UI、不新增 Knowledge Card，也不因輸入或切換作品文字而自動連網。
- DDGS 授權與 attribution 必須保留；不得宣稱 DDGS 搜尋具有商業 SLA 或官方搜尋引擎授權。

## 2026-07-24：Local Vision GPU offload 參數

- 實機在目前 Windows WDDM／VRAM 使用狀態下，預設 operator offload 搭配 Gemma 3 mmproj 會長時間停在 `load_tensors`；單純 text GGUF 可約 8 秒 ready。
- `--no-op-offload` 保留 `-ngl 999` 的 GPU 權重載入，但避開 operator offload stall；實機約 9.6 秒 ready，request 可取得 HTTP 200。
- 第一版先固定此參數，不做裝置遙測或高階顯卡 A/B；準確度需以同一批漫畫與 holdout 實測，不能由啟動成功推論品質不變。
## 2026-07-24：Local multimodal 分批與 JSON 容錯

- local Gemma 多模態一次最多送 4 段 OCR source text；超過就沿用同一組圖片 context 分批，避免 8～15 段造成截斷或錯誤 JSON。
- JSON response 的 extra out-of-range segment 只忽略本批以外 index；缺段／重複／非法 index 仍 fail，避免把幻覺結果當完整翻譯。
- llama-server 的 400 只有明確 response-format／JSON 類錯誤才改用 text；`exceed_context_size_error` 等 400 不重試，減少無效等待。
- 實機 A/B 顯示 crop 對整頁截斷頁有救援價值，但 4 頁 crop 平均較慢且沒有 ground-truth 足以證明語意提升；先維持 opt-in。
## 2026-07-24：Local crop bounded grouping

- local multimodal crop 專用分組器最多輸出 4 個 region；合併依鄰近距離與 union 面積排序，單一 region 不得超過頁面 30%。
- 所有 item center 無法被 bounded regions 覆蓋、item 尺寸超界、crop 編碼失敗或 provider 未 ready 時，一律 fail-open 回整頁 context。
- 15 張正式漫畫幾何 gate 為 14/15；剩餘頁面若要提高覆蓋率需引入文字區域／分格偵測或局部切片，不直接放寬面積上限。
- 新分組不接到既有 OCR adaptive refinement，避免影響 threshold、OCR bbox、閱讀順序與目前已驗證的 29/83 -> 30/83 結果。
## 2026-07-24：Manga grid recovery gate

- grid recovery 不覆蓋既有 OCR item；它只在 baseline item 數 2～6 時以 2x3 overlap tiles 做候選重試。
- 接受條件是候選仍有至少 2 個 CJK item 且 score >= baseline + 3；否則保留 baseline。既有 <=1 item tile fallback 設旗標，避免重跑同一輪。
- 15 張實機單輪結果顯示 35/83 -> 38/83，但 Windows OCR 有非決定性；這是探索結果，不是 release claim。
- CLOUDHIME_MANGA_GRID_RECOVERY 預設關閉；若 repeated-run canonical evaluator 無法證明零 regression，不能直接開啟。

## 2026-07-24 CH-T43 repeated-run evaluator 與 grid 決策

- 決策：以獨立 manga_repeated_run_evaluator.py 保存 paired baseline／grid 摘要；同一 manifest、相同圖片順序、交錯 condition order、每頁 SHA-256，避免把單次 Windows OCR 波動當成準度提升。
- 決策：同時報 pooled anchor recall 與 page macro recall，並列出 improved／equal／regressed pages；沒有 anchors 的 holdout 只報 nonempty、錯誤與 latency，recall 必須是 null。
- 決策：目前 15 張一次 run 雖有 +6 anchors、0 regressions，但平均延遲增加約 2.38 秒；5 張 holdout 也顯示 grid 約慢 7.48 秒，所以不改產品預設。
- 限制：這一版 repeated run 在同一 Python process 內以每個 condition 新建 OCRWorker；正式 release gate 仍需固定 5 repeats，必要時再升級成 subprocess isolation。
## 2026-07-24 CH-T43 per-repeat paired comparison

- 決策：任何多輪 benchmark 必須以 (case_id, repeat) 對齊 baseline／variant；跨 repeat 平均只作 page-level summary，不得代替 per-repeat stability。
- 決策：先保存 evaluator 統計修正，再跑 5-repeat；subprocess isolation 保留為波動／順序效應出現後的下一級驗證，不提前擴大範圍。
- CodeRabbit：本輪 staged evaluator review 回報 0 findings，但 reviewed context 超出兩個變更檔；未來需要獨立審查時採 isolated review directory 或 --base-commit。
## 2026-07-24 CH-T43 oversized fullscreen OCR decision

- 決策：全螢幕超大圖片先做 bounded resize，再進既有 OCR pipeline；只改變超過 2400px 長邊的輸入，正常螢幕保持 3x 行為。
- 決策：FULLSCREEN_OCR_MAX_DIM=4096、FULLSCREEN_OCR_MIN_SCALE=1.5 是資源安全上限，不是準度調參；公開 holdout anchor 0/6，因此不以它宣稱品質提升。
- 決策：grid recovery 只作明確 opt-in 的探索工具；公開 6 張一次 run 的平均延遲約 2.22s -> 12.66s，p95 約 6.25s -> 52.85s，暫不進入自動閾值或預設掃描路徑。
## 2026-07-24 CH-T43 region-aware crop decision

- 決策：下一階段先採用 region-aware crop mapping，再考慮新的文字區域偵測或 lazy grid；目前的主要缺口是多模態 context 與 source text 對不上，而不是再增加昂貴 OCR 重試。
- 決策：CLOUDHIME_MANGA_CROP_CONTEXT 與 CLOUDHIME_MANGA_GRID_RECOVERY 仍預設關閉；本 lane 只改善 opt-in 路徑，不改一般掃描速度或 OCR geometry。
- 決策：crop 的準度收益尚未被 holdout 語意 ground truth 證明；進入產品預設前仍需固定 GPU runtime、4 張 crop-enabled A/B、5-repeat paired evidence，且不得有 regression。
## 2026-07-24 CH-T43 multimodal rescue gate 收斂

- 決策：多模態仍以準度優先，但只有 OCR 輸出呈現低資訊碎片、極小候選區域或明確重複退化時才自動 rescue；合理的長段 CJK 直接保留，避免把正常頁面變成昂貴的全頁重試。
- 決策：候選重複字／重複短單位視為退化輸出，拒絕其覆蓋 baseline；rescue、編碼失敗、provider 未 ready 與例外都維持 fail-open。
- 實機 GPU probe 顯示 Gemma 3 4B 純 `japanese_ocr` 6 張公版封面皆非空但 anchor 僅 2/6，strict prompt 與 OCR hint 更差；因此本輪不把 local multimodal 宣稱為 OCR 替代，也不打開全局預設。
- 速度基線：暖 GPU 的多模態 request 約 1.675s 平均、p95 2.391s；這是模型 request latency，不包含首次模型／mmproj 載入，不能冒充完整冷啟動速度。
- CodeRabbit 本輪隔離審查受 free CLI rate limit 阻擋，未取得有效 findings；在額度恢復前維持人工檢查與 focused regression，不能記成 clean review。
## 2026-07-24 CH-T43 evaluator barrier 與 5-repeat 收斂

- 決策：產品掃描保留 bounded adaptive refinement deadline；只有 paired evaluator 透過 `drain_deadline_futures=True` 等待已啟動 OCR future，避免下一個 condition 與上一個 timeout 工作重疊。
- 決策：evaluator 的總 latency 與 nonempty rate 將 error／timeout 頁納入分母，另保留 successful-only latency，避免失敗 variant 看起來更快。
- Current HEAD 5-repeat 已證明 grid 在固定 15 張 annotated pages 上 5 improved、10 equal、0 regressed，5 repeats 無 regression；但平均延遲約增加 2.44 秒、p95 增加約 5.26 秒，grid 仍只能 opt-in。
- Gemini 的臨時 manga_cover prompt probe 沒有超過既有 japanese_ocr；不以單次 3/6 類似 anchor 或輸出幻覺作產品升格依據。
- 下一步優先做低成本文字區域／分格候選 proposal，另建 multimodal translation quality evaluator；不再用 OCR-only anchor 結果直接宣稱 local Gemma 已能取代 OCR。
## 2026-07-24：CH-T43 evaluator barrier CodeRabbit review

- 決策：保留 evaluator-only drain_deadline_futures=True；產品掃描仍維持 bounded、非等待的 deadline 行為。
- 決策：總 latency 納入 error／timeout 頁，並另報 successful-only latency；避免失敗 variant 看似更快。
- 審查：隔離 repo 僅含 5 個 staged 檔案，CodeRabbit review completed，findings=0；無需追加修正。

## 2026-07-24：漫畫多模態品質評估器

- 決策：vision smoke evaluator 同時接受既有 sample_source／expected 與漫畫 holdout 的 image／visible_text_anchors，不複製第二套 GPU runtime。
- 決策：dense-region detector 的離線 probe 對目前封面／漫畫頁召回不穩定，不接入預設 OCR；先以可重現的多模態品質數據引導下一輪裁切／prompt 實驗。
- GPU evidence：6/6 成功，anchor 2/6，average_match=0.497，平均 request=1.758s，p95=2.674s。

- 審查：本階段 CodeRabbit 隔離 review reviewedFiles=7，findings=0；未發現需要修正的問題。

- A/B 結論：在相同 6 張公版封面、Gemma 3 4B GPU、context=4096 下，japanese_ocr 同時優於 baseline／strict_ocr 的非空率、anchor 命中與相似度；後兩者也沒有速度優勢。
- 下一步：優先研究直排／裝飾標題的局部 crop 與 orientation hint，仍須以 holdout evaluator 驗證，不用 prompt 堆疊替代測量。

- 方向策略決策：OCR bbox 的 vertical aspect ratio 只能描述候選框形狀，不能證明視覺模型需要旋轉；原圖可能已包含正確閱讀方向或混合內容。暫不加入自動旋轉。

- 多視角結論：原圖＋灰階或 tight crop 在小樣本上只持平、明顯變慢，且仍有退化輸出；目前最穩定的視覺輸入仍是單一原圖。
- 全頁結論：15 張 fixed annotated pages 上 local Gemma direct OCR 低於 Windows OCR（28/83 vs 31/83），因此不擴大全頁 rescue。
- 下一個品質方向：把 local multimodal 當 translation context，另外建立 shadow evaluator／候選採用 gate；不改既有 OCR text 與 bbox contract。

## 2026-07-24：Multimodal translation fail-open

- 決策：local multimodal segmented translation 若 provider request 或 parser 失敗，必須退回既有 text provider route；多模態成功路徑行為與 request 次數不變。
- CodeRabbit：隔離 v6 review 提出 1 個 minor 測試缺口（parser exception）；已補測並通過，沒有需要追加的產品修正。


## 2026-07-24：Multimodal segmented translation repetition gate

- 決策：只攔截「來源至少半數不同、結果至少 75% 重複且最多兩種譯文」的退化分段結果，避免模型把多段內容複製成同一句。
- 保護：來源本身重複時不啟用這個 gate；provider 觸發 ValueError 後由既有 worker fail-open 回到文字翻譯 provider。
- 審查狀態：CodeRabbit 本時段已使用 3/3，未對本 stage 宣稱通過；Git checkpoint 等待 review。


## 2026-07-24：Move multimodal degeneration gate to worker

- Gemini review：原本「75% 完全相同譯文」會把 Oh／Oh?／Oh... 等合理短句誤判為退化；provider 不應承擔漫畫語義業務規則。
- 決策：gate 移至 OCRWorker，並限制為長譯文、來源足夠多樣、至少半數來源為長句；同一來源重複與短語氣詞直接放行。
- 降級：worker 觸發後沿用既有 text provider fail-open，不增加成功路徑推論次數。
- 審查狀態：Gemini 已完成只讀設計 review；CodeRabbit 本時段仍 3/3，待下一時段 isolated review 後才提交。


## 2026-07-24：CodeRabbit v7 checkpoint

- Gemini follow-up：不要用譯文長度單獨豁免；長來源本身已能排除短語氣詞，卻能捕捉全部輸出「無／空白」的短退化。
- CodeRabbit：隔離 repo coderabbit-worker-gate-v7，只審查 cloudhime_workers.py 與 tests/test_cloudhime_workers.py，findings=0；因無 Git remote 使用 CLI free allowance。
- Git：0933313，僅包含 worker gate 與 regression tests。

## 2026-07-24：Release packaging readiness

- 決策：封裝採單一 onedir bundle；assets、dictionary.json 與必要 runtime 檔案由 build_exe.bat 明確納入，模型仍由既有 AppData managed asset 流程下載，不把大型 GGUF 直接塞進安裝包。
- 修正：UI 背景資源統一經 _resource_path() 解析，stylesheet URL 加引號，讓 PyInstaller 路徑與含空白路徑可用。
- 保護：runtime staging 只複製必要 llama/cuda DLL 與 ggml-cpu-*.dll；所有 staging、PyInstaller、壓縮失敗都走共同 cleanup，避免殘留半成品。
- 審查狀態：CodeRabbit v8 初審 2 個 minor 已修正；修正版重審受 rate limit 阻擋，未宣稱 clean，Git checkpoint 等待重審。

## 2026-07-24：Source bootstrap boundary

- 決策：install.ps1 / run.bat 明確定位為原始碼開發腳本，不作為 Store 安裝器；使用專案 .venv，禁止把 Miniconda、舊模型下載或外部模型服務列為使用者前置條件。
- 模型邊界：source-dev 與 release 都由 CloudHime 的 managed asset flow 處理 Gemma model/projector；正式包裝仍使用 MSIX/PyInstaller 方向。

## 2026-07-24：CodeRabbit v8 packaging checkpoint

- CodeRabbit 初審 2 個 minor：run.bat 錯誤訊息應指向 install.ps1；install.ps1 應驗證 Python 3.10+。兩項均已修正。
- CodeRabbit 修正版重審：findings=0，檢查 build_exe.bat、cloudhime_ui.py、install.ps1、run.bat、tests/test_release_packaging.py 與既有 UI smoke 檔。
- 本 checkpoint 不包含模型檔、runtime binary、私有漫畫 probe 或 MissionCenter 以外的暫存資料。

## 2026-07-24：Packaging and source bootstrap checkpoint

- Git checkpoint：46d351e fix: align release and dev bootstrap。
- 保留未完成項：實際 PyInstaller build 沒有在本工作區執行，因 runtime staging 約 GB 級且需要發行／GPU 環境；MSIX 與 Store submission 也不以本地靜態測試宣稱完成。

## 2026-07-24：MSIX-first release skeleton

- 決策：採 MSIX-first，而非先做自製安裝器；build_msix.ps1 以 Windows SDK makeappx.exe 產出 unsigned MSIX，Publisher、Identity、Version、Architecture 由參數注入。
- 資產：新增 CloudHime logo；PyInstaller bundle 保留 assets、LICENSE、THIRD_PARTY_NOTICES.md，模型與 projector 仍留在 AppData managed asset flow。
- 邊界：本機未安裝 Windows SDK，不能把 manifest 靜態驗證當成真實 MSIX／乾淨 Windows smoke；下一步需在 Windows SDK runner 執行 makeappx、安裝／啟動／唯讀 package 測試。
- 官方依據：Microsoft 建議 Store 上傳 msixupload；MSIX Store 發布由 Store 處理重新簽章；Partner Center identity／listing／submission 仍需帳號與實際流程。

## 2026-07-24：CI MSIX contract

- 決策：runtime/ 是本機 release artifact，乾淨 CI 不下載或提交 GB 級 CUDA DLL；test_release_packaging 在 runtime 缺失時 skip，MSIX contract job 以 dummy onedir 驗證 makeappx 流程。
- 限制：dummy package 只證明 manifest／makeappx staging 可工作，不代表真正 CloudHime.exe、GPU runtime 或 WACK 通過。
- 審查狀態：msix-v1 已 findings=0；msix-v2 含 CI 變更的重審受 rate limit 阻擋。

## 2026-07-24：MSIX builder hardening after CodeRabbit

- Version 只接受四段 0-65535 數字，先於輸出路徑建立前驗證，避免 malformed path。
- 建立 packagingSucceeded 狀態；makeappx、upload archive 任何失敗都清除 package/upload/暫存 zip，成功 artifact 才保留。
- CI dummy dist 模擬現代 PyInstaller _internal layout，解壓 MSIX 後逐項檢查 13 個必要 runtime 檔案；這仍是 contract，不等於真實 GPU binary smoke。

## 2026-07-24：MSIX hardening checkpoint

- CodeRabbit 初審 3 major 已修：四段 Version 安全驗證、failure artifact cleanup、CI 解壓後逐檔檢查 13 個 runtime 檔案。
- CodeRabbit 修正版：reviewedFiles=5、findings=0。
- MSIX upload：CreateUpload 以 MSIX 壓成手動 msixupload；依官方文件，public symbols 可省略但會失去 Partner Center crash analytics，尚未納入。

## 2026-07-24：MSIX CI hardening checkpoint

- Commits：06b755d、d36a2a3。
- d36a2a3 補上 manifest logo layout 與 packagingSucceeded regression assertions；內容已在 CodeRabbit msix-v2 五檔 review 中檢查。
- 不把本機完整 pytest timeout 解讀成通過；CI runner 的 bounded smoke 與真正 Windows/GPU gate 分開追蹤。

## 2026-07-29：CH-T35 仲裁 shadow 不升格為產品 fallback

- 三輪固定 25-case GPU A/B 都證明現有二次 Gemma 仲裁可穩定採納同一個改善案例，且零退化。
- 「仲裁拒絕時直接採 Meiki candidate」在三輪真實資料中從未被觸發，無法證明跨樣本穩健性；因此僅保留為 benchmark 診斷，不接入產品決策。
- 正式路由維持 fail-open 與既有 provider 呼叫數；新增日誌只記 outcome 與兩個 similarity，不記 OCR／翻譯原文。

## 2026-08-01：CH-T44 Knowledge Pack 本地底座

- Pack 與 catalog 一律放在 AppData 的 `CloudHime/knowledge_packs`，不寫安裝目錄；這讓未來 MSIX 唯讀 package 與使用者資料生命週期分離。
- 每個 pack 使用版本化 envelope 與 `pack_id`／`revision`；更新先寫新 revision，不能自動切換 active，讓未來設定頁的 Save／Cancel 語意保持清楚。
- catalog 的 read-modify-write 由跨程序 lock 保護，pack／catalog JSON 都以同目錄暫存檔加 fsync／replace 原子 promote；讀取遇到缺檔、壞檔或不相容 schema 時 fail-open。
- revision 檔名同時保留原始 ID 的 lower-case 與 SHA-256 指紋，避免 Windows 大小寫不敏感檔案系統把 `Alpha` 與 `alpha` 撞成同一檔案。
- 本階段不引入 DDGS、Jina、Gemma、網路請求或 UI；先讓 `example/転生重騎士` 成為未來 Builder／retrieval 的可重現 fixture。

## 2026-08-01：MSIX 前置資產閘門

- 決策：`build_msix.ps1` 先呼叫共用 `verify_release_dist.ps1`；`-PreflightOnly` 不解析或執行 `makeappx.exe`，讓缺 SDK 的開發機仍能驗證真實 bundle。
- 發行規則：CloudHime.exe、logo、dictionary、LICENSE、THIRD_PARTY_NOTICES.md 與 13 項 embedded llama/ggml runtime 必須存在；GGUF、mmproj、`.pfx`、`.p12`、`.key`、`.cer`、`.env` 與已生成的 Appx 檔案不得進 dist。
- 邊界：此 gate 只證明 PyInstaller dist 可進入下一階段，不替代 Windows SDK 建包、簽章、WACK、MSIX install/uninstall 或首次 AppData 模型／GPU 暖身。模型與 projector 維持由 CloudHime 管理到 AppData。

## 2026-08-01：真實 MSIX 與 AppX 宿主邊界

- Windows SDK 10.0.26100.8876 的 x64 MakeAppx／SignTool 可用；真實 CloudHime dist 已完成 build 與 unpack contract，這部分不再是 dummy-only 證據。
- `test_msix_install.ps1` 保留 Appx cmdlet 的 Windows PowerShell 5.1 bridge，避免本機 PowerShell 7 module load failure；此 bridge 不改產品執行檔，只改善 release smoke tooling。
- 本機開發 cert 的信任鏈不可當 Store signing：CurrentUser TrustedPeople 會被 deployment 以 `0x800B0109` 拒絕；本機測試不可擅自保留 Root trust。CI 仍使用明確的 ephemeral cert cleanup，正式 Store 仍待 Store identity／publisher。
- 真實 install/launch/uninstall 目前維持 Partial；需要可完成 AppX deployment 的乾淨 Windows／管理員環境重跑，且 WACK、AppData 模型下載與 GPU ready 仍是獨立 gate。

## 2026-08-01：Release preflight signing-material 邊界

- .pem 等副檔名不能一律視為私密簽章材料，因 PyInstaller dist 會包含 certifi\cacert.pem 公開 CA bundle；validator 只對該精確公開路徑放行，其餘 .pfx、.p12、.key、.pem、.priv、.pvk、.ppk、.cer、.crt 與 .env* 仍拒絕。
- 空的 llama／ggml runtime 檔案視為缺失；這避免「檔名存在但無法執行」的假綠燈。
- 本次 release preflight 只驗證 dist 檔案邊界，不能取代真實 AppX deployment、WACK、Store identity／正式簽章與首次 AppData GPU onboarding。
## 2026-08-01：Gemma 3 GPU 啟動參數修正

- 保留 Windows mmap：同一台 RTX 3060／D 槽 A/B 中，--no-mmap 超過 240 秒仍未 ready；移除後約 44.5 秒 ready，暖機後 startup 約 4.1 秒。
- --no-op-offload 繼續保留，因為它仍是先前已驗證的 WDDM／operator offload 穩定化參數；本次只移除被新證據否定的 --no-mmap。
- 5-case strict OCR GPU smoke 只代表固定 manifest 的現況，不外推成 113 張 example 全部正確；下一個準確度工作仍需分層漫畫／日文 holdout。
## 2026-08-01：MSIX WACK 圖示尺寸與驗證邊界

- MSIX 不再把單張大圖重用於 Store Logo、44x44、150x150；manifest 使用 50x50、44x44、150x150 三張獨立 PNG，builder 與 CI fixture 必須同步提供。
- release preflight 不接受只看檔名或 PNG header 的假資產：先拒絕 204800 bytes 以上檔案，再驗證 signature、chunk 長度、CRC、IHDR、IDAT 與 IEND。
- WACK 初次報告的 DPI warning 與 blocked-executable heuristic 不在本次 logo checkpoint 內；前者應在 PyInstaller EXE manifest／啟動 API 處理，後者需先盤點真正必要的第三方 runtime，不能為掃描綠燈移除 llama／CUDA。
## 2026-08-01：DPI manifest 與 MSIX 簽章根因

- DPI 採 PyInstaller --manifest 嵌入 EXE，manifest 同時提供 dpiAware=true/pm 舊版 fallback 與 dpiAwareness=PerMonitorV2；保留現有 Qt scaling environment variables，待實機多螢幕 smoke 再決定是否調整。
- 不採 Python 啟動時 SetProcessDpiAwarenessContext 作為第一方案；官方建議 manifest，且 API 必須早於依賴 DPI 的 UI 建立，與 manifest 同時存在時容易變成失敗／重複設定。
- 0x8007000B 已由 matching-subject 實測釐清為 Publisher／certificate Subject 不一致；正式 Store signing 必須使用 Store identity，測試自簽只作本機 package gate。
- 不為 WACK blocked-executable heuristic 直接刪 llama/CUDA；先完成 DPI／signing gate，再另開 runtime dependency graph 與重複 DLL 瘦身任務。

## 2026-08-01：WACK DPI follow-up 結論

- 完整 PyInstaller rebuild 後，WACK 對新版 signed MSIX 回報 `OVERALL_RESULT=PASS`；`Application resources` 與 `DPIAwarenessValidation` 均 PASS，圖示尺寸與 EXE `PerMonitorV2` 修正已取得實際驗證。
- `封鎖的可執行檔` 是 optional static heuristic FAIL，列出 Qt/Python/llama/CUDA 的必要 DLL 與處理序 API 參考；不為此刪除本地 Gemma／CUDA／OCR runtime。後續以 dependency graph、最小 runtime 分層與 Store 審查說明處理。
- WACK 使用的簽章只允許一次性測試憑證，已精確清除 PFX、憑證與報告暫存；正式 Microsoft Store 發布仍需 Store identity／正式 signing。

## 2026-08-01：AppX sideload 信任鏈邊界

- 本機 `0x800B0109` 不是 Publisher mismatch 新問題，而是自簽 leaf certificate 未被目標機器信任。官方可靠做法是把實際簽章所用的公開 `.cer` 匯入 `Cert:\LocalMachine\TrustedPeople`，不把 leaf cert 當成 Trusted Root。
- 目前 Codex 執行環境只有 Medium Mandatory Level；寫入 LocalMachine certificate store 回 `E_ACCESSDENIED`。因此不再用 CurrentUser store 假裝完成乾淨機安裝 gate，也不在沒有真正管理員 token 時重跑 1.27GB staging。
- 短命測試憑證、PFX 與暫存目錄已精確清除。下一次實機 gate 必須由真正系統管理員／乾淨 Windows 執行，並以 thumbprint 清理信任材料。

## 2026-08-01：Local Gemma tuning 前的 cache 邊界

- Generation parameters 是翻譯結果語意的一部分；`temperature` 與 `repeat_penalty` 必須同時進入 Local Gemma cache key，參數實際改變時清除既有 translation cache 與 context buffer。
- 不把目前少量 vision／漫畫案例直接拿來調 temperature、repeat penalty 或 context；先完成 source-disjoint 日文字幕 holdout 與固定 5-repeat paired A/B，避免把 cache 或隨機輸出誤認成品質提升。
- CH-E6 優先順序暫定 CH-T35 → CH-T43 → CH-T32：先驗證已有 rescue 訊號，再處理漫畫 region context，最後才做 Gemma generation parameter search。
## 2026-08-01：CH-T45 SearchProvider boundary

- Research 是明確立即操作；正常 OCR／翻譯路徑不建立 provider、不觸網。
- DDGS 只回傳候選 URL／摘要；Jina Reader 只讀通過 public URL 與 DNS 檢查的正文，所有結果仍是不可信輸入。
- provider 以 lazy import、timeout、max results、max bytes、transport error 與 fail-open error boundary 隔離；真正 Gemma extraction、source confidence、worker、UI 與 PyInstaller hidden imports 留在後續 CH-T46～CH-T50。
- 研究依據：[DDGS PyPI](https://pypi.org/project/ddgs/)、[DDGS source](https://github.com/deedy5/duckduckgo_search)、[Jina Reader](https://jina.ai/en-US/reader/)。
## 2026-08-03：GPT 多模態日文字幕標註邊界

- `example` 目前 113 張圖片仍只是素材池；模型自身 OCR／視覺輸出不得直接當 ground truth。
- GPT 多模態視覺初判先建立 3 張 `轉生重騎士` 候選：001、002、003；檔案 `.private_japanese_subtitle_candidate_annotations.json` 明確標為 `draft_requires_owner_confirmation` 與 `ground_truth_eligible=false`，不進版控。
- 只有主人逐張確認文字、閱讀順序與是否納入後，才能另行提升為正式 source-disjoint 日文字幕 holdout；長段落低於高信心門檻者只作候選，不計入準確率。

## 2026-08-03：Knowledge Research Draft 不可自動啟用

- 研究草稿採獨立 schema，狀態固定為 draft，entries 必須為空，owner_confirmed 固定為 false；DDGS／Jina／模型輸出只能留下候選證據，不能直接寫入或 activate Knowledge Pack。
- 每個來源保留 canonical URL、source id、查詢結果 metadata、擷取時間、內容 SHA-256 與 bounded content；單一來源讀取失敗或內容過大只標記該來源，不中止整份研究草稿。
- catalog 損壞時只從通過 schema 驗證且檔名 canonical 的本機 pack JSON 重建非 active 索引；不恢復 active revision，避免竄改檔案被默認採用。
## 2026-08-03：視覺標註不能自證 ground truth

- GPT 多模態可以協助讀圖與整理候選 anchors，但它與本地 OCR 一樣不能替自己產生的文字背書。
- 正式日文字幕 benchmark 必須採「GPT 候選 → 主人逐項確認 → source-disjoint manifest → evaluator eligibility gate」四段流程；未確認資料只可作 smoke／候選，不可調參或宣稱準確率。
## 2026-08-03：PR-1 hardening 採最小安全變更

- 模型政策繼續由 `model_catalog.py` 統一；為保留既有 UI／worker 行為，registry default 對齊既有 `gemma-3-27b-it`，不趁 hardening 偷換成更慢模型。
- API key 新寫入只走 Windows DPAPI；legacy `.env`／settings 僅在沒有 migration tombstone 時讀取。使用者清空 key 會先寫 tombstone 再刪 DPAPI，避免重啟復活；明確 process environment 仍可作外部注入。
- Gemini 提出的 DirectML、ZipSlip、GPU 三階 fallback 屬後續研究候選；除非有現行程式路徑與測試證據，不直接加入本波次。
- CodeRabbit 最終隔離複審為 7 個小檔案、0 issues；大型 UI、模型、example 與 dist 不送審。
## 2026-08-03：Packaged OCR 安裝邊界

- `build_exe.bat` 將 optional OCR Python stacks 排除在 release bundle 外，因此 frozen／MSIX runtime 不應嘗試 `sys.executable -m pip install`；Tesseract 的 `winget` 也不應由 Store app 代辦。
- `ocr_backend_installer.install_backend_packages()` 與 `install_tesseract_runtime()` 在 `sys.frozen` 下 fail-closed，回傳可觀測訊息；source mode 的既有安裝流程不改。
- 這只保證不會從 packaged app 觸發動態安裝，不代表 optional OCR 已包含在 Store 包，也不取代乾淨 Windows、WACK、Store identity 或實機 UI gate。
- CodeRabbit 本輪因免費 CLI rate limit 未完成；不能把本地測試結果當成外部審查結果。

## 2026-08-03：DDGS 只收核心，不使用 collect-all

- DDGS 9.14.4 透過 `ddgs.engines` 的 `pkgutil.iter_modules` 動態建立 engine registry，因此只收 `ddgs.engines` submodules；lazy `ddgs.ddgs`、lxml、primp、fake-useragent data 與 certifi data 明確列入。
- 不使用 `collect_all("ddgs")`：隔離 probe 實際觸發 optional DHT/API 與環境 Qt hook，造成 Qt binding conflict／不必要分析鏈；DHT 在 Windows 本來就不是 CloudHime 需求。
- `CloudHime.spec` 現在是 packaging source of truth，並以 force-add 納入 Git；`build_exe.bat` 只保留 runtime staging、dependency preflight、spec build 與 zip。
- Root notice 已列出 DDGS base dependency license inventory；正式 Store 送審前仍須依實際 resolved wheels 保留完整 license files／BOM，不能只以文字契約代替。

## 2026-08-03：完整 CloudHime dist checkpoint

- `CloudHime.spec` 成功以 explicit DDGS engine/runtime 收集策略建立完整 dist；這證明 CH-T50 不只停留在 isolated probe，但不等於 MSIX 或 Store ready。
- release preflight 確認產物沒有模型檔，且 EXE 啟動 8 秒未立即退出；實機 GPU／離線翻譯品質仍需獨立 gate，不能由「能啟動」推論完成。
- PyInstaller 出現 `charset_normalizer.md__mypyc` 與 mkl optional DLL warnings；暫不擴大 scope，先在 clean Windows／實際功能 smoke 驗證是否影響產品路徑。
- 下一個 release gate 是 MSIX bundle/import、離線 normal translation、optional OCR fail-open 與 resolved-wheel license files／SBOM；在這些證據齊全前不宣稱 Microsoft Store ready。
## 2026-08-03：MSIX 大型封裝工具選擇

- `Resolve-MakeAppx` 必須優先選 SDK `x64\makeappx.exe`；目前 CloudHime 會帶入約 2.2 GB 的 CUDA/runtime payload，x86 工具實測在封裝時回 `0x8007000e`。
- 保留沒有 x64 SDK 時的 fallback，讓開發機能得到可觀測的後續錯誤；不在 resolver 內偷偷下載 SDK。
- full MSIX build + unpack 證明封裝內容與 manifest 正確，但 unsigned package 仍不能當成安裝成功；signed clean-Windows install／launch／uninstall 是下一個 gate。
## 2026-08-03：signed MSIX gate 的環境邊界

- Microsoft 官方規則要求 MSIX 具備有效簽章，且安裝裝置必須信任簽章鏈；CurrentUser TrustedPeople 不足以通過本機 AppX trust check，LocalMachine TrustedPeople 需要管理權限。
- CloudHime 的 Store 路徑不應要求使用者安裝自簽憑證；Store submission 由 Microsoft 重新簽章，本地自簽只保留給 CI／開發 smoke。
- CI 與 local builder 都優先使用 x64 工具，避免 2.2 GB CUDA runtime payload 被 32-bit 工具處理時 OOM；找不到 x64 時才 fallback 並保留可觀測錯誤。
- Gemini bridge 本輪 discovery 後仍回 `unable to open database file`，沒有取得審查回覆；未把它記成 Gemini Pass，改以本地測試與官方 Microsoft 文件作決策證據。
## 2026-08-04：CloudHime 開發順序重整

- 決策：先做 repository hygiene 與 benchmark lock，再做 runtime／pipeline 收斂；漫畫模式、插件與自動 Research 延後。
- 固定順序：
  1. 清理過時暫存，保留 source、tests、benchmarks、人工標註記錄、models、runtime、dist、packaging 與 MissionCenter。
  2. 鎖定 source-disjoint accuracy、latency、coverage、fallback 與 GPU/CPU 條件，任何優化都必須留下可重跑證據。
  3. 消滅雙 llama runtime，production 最終只保留單一 llama-server engine；先完成 lifecycle 與 paired regression，再移除 production `llama-cpp-python`。
  4. 抽出 Scan Pipeline，加入 FrameGate 與 Temporal Stabilizer，避免每幀重複 OCR／翻譯。
  5. 收斂 Translation Orchestrator，統一 provider routing、fallback attribution、cache 與錯誤證據。
  6. 完成 Profiles／Knowledge Pack，再做發行供應鏈與 clean-machine gate。
  7. 最後才評估漫畫模式、插件與自動 Research。
- 理由：目前主要風險不是功能不足，而是模型生命週期、工作排隊與錯誤證據不一致；先建立秩序才能保證準確度優先、速度第二。
- 邊界：不因清理而刪除模型、llama runtime、發行 dist、benchmark manifests 或主人確認的人工標註；任何大型刪除先盤點、列出路徑並取得明確確認。

## 2026-08-04：CH-T61 只允許 exact-only hard skip

- 決策：production 只有 `ExactImageCache` 的完整影像＋完整 context 相等可跳過 OCR／翻譯；`FrameGate` 的 `identical`／`near` 分類只作 shadow telemetry，不成為 active skip 條件。
- 證據：鎖定 temporal v2 holdout 使用 10 張主人確認漫畫頁、1 張主人提供的小字圖片與 1 個不含文字 ground truth 的極小局部內容反例，共 12 cases／84 frames。safe policy event recall 1.0、single-frame recall 1.0、false event skips 0；hypothetical near-skip event recall 0.9583、single-frame recall 0.9167、false event skips 2。
- 理由：64x64 bounded sample 無法保證捕捉 1080p／4K 的所有細筆畫或單幀小字；經驗閾值可以改善平均速度，不能證明零漏失。準確度優先時，重複反例足以否決 active near skip。
- telemetry 連續性：每次成功 capture 都更新 FrameGate baseline，包括 exact cache hit；常見 uint8 使用向量化 float64 delta，寬整數／超寬 dtype 保留精度安全分支。
- 邊界：此 holdout 是 frame-policy benchmark，不是 OCR、翻譯或模型品質 benchmark；不把 source identity、合成狀態或模型輸出冒充文字 ground truth。
- 外部複核：Gemini 3.6 Flash High RPC request `b76df69a-c99a-49a2-8c96-8c5fb04bc521`／cascade `9242a30e-a257-4432-a88e-ea0f48497b8c` 同意 exact-only；CodeRabbit staged review 2 major，均已修正 manifest-lock binding 與 schema allowlist。

## 2026-08-04：CH-T62 採薄 Translation Orchestrator

- 決策：本階段不搬動 provider prompt、HTTP client、模型取樣或 public Qt signals；新增無狀態 orchestrator，只收斂文字 provider chain、fallback attribution、取消邊界與安全錯誤碼。
- fallback 結果的 provider 必須是實際執行者；requested_provider 與 fallback_reason 保存路由 lineage，model、raw_text 與 from_cache 不得因包裝而遺失。
- 取消只能在同步 provider 呼叫前後生效；不宣稱可中斷已進入的 urllib／GoogleTranslator／llama-server HTTP request。更細粒度的 socket cancellation 留待 provider transport 明確支援後再做。
- 錯誤證據只允許 bounded code 與 exception class；status、trace、debug log 不保存 raw exception message、OCR 原文、prompt、API key 或模型原始輸出。
- batch／multimodal／stream 的完整 result 型別收斂留給後續漸進工作；本階段保留既有行為，避免一次大改造成準確度 regression。

## 2026-08-04：CH-T63 將 active work 視為可回滾設定 context

- 作品名稱輸入不觸發網路；只有明確 Research 操作可建立或更新 pack。pack 本地資料的持久化獨立於 Settings Save／Cancel，active work title 則遵守 Save／Cancel。
- pack identity 使用 `(pack_id, revision)`；identity 改變時先使舊 scan generation 失效，再安裝 worker context，避免舊 frame 在新作品知識下完成。
- 同作品 Research 更新沿用 pack ID；legacy 同名 pack 以 catalog 最新項為準。一般翻譯不得依賴 Research 成功或網路可用。
- builder completion commit 是 cancel 邊界：commit 前取消必須發布 cancelled，commit 後取消回傳 false；runtime setter 失敗必須清空 worker context 與 active catalog，不可保留上一部作品。

## 2026-08-05：模型 catalog 分為離線政策與線上 availability

- 決策：model_catalog.py 是可版本控管的離線 capability／migration 政策；生命週期為 legacy 的遠端型號不可出現在 UI 或 provider callable 清單。
- 決策：Gemma／Gemini／本地 llama-server 的 provider attribution 必須表示實際執行家族，不能再以字串前綴推測。
- 決策：Models API 動態探測另立 CH-T67；不得在輸入設定或開啟設定頁時偷偷上網，失敗時沿用最後有效快照並保留 local-first 路由。
- 邊界：本階段不實作 Vision-first、ResourceGovernor、idle unload 或完整 dev provider 刪除，也不宣稱未跑過的 API／GPU／clean-machine benchmark。

## 2026-08-06：CH-T68 採 Region-first 的 Vision-first 收斂

- 產品終態：Vision 負責從圖片判斷原文與翻譯；OCR 只負責 optional geometry 與可能錯誤的 hint，不得再因 OCR backend 缺失、空結果或例外直接阻止 Region 翻譯。
- 漸進邊界：先切 Region Bubble／Relief，沿用 Screenshot image-first；Fullscreen 與漫畫頁仍需 source-disjoint holdout 通過後才能切換，不做一次性大重寫。
- 結果契約：只接受 bounded、strict regions JSON；model source_text、translation 與 confidence 必須通過 schema，輸出 ID 只能對應 caller 提供的 bbox，無 bbox 時只建立一個 whole-region ID。
- 失敗策略：Vision 成功即為主要結果；Vision 失敗且 OCR 有字才回退既有 OCR-first translation；兩者皆無時安全失敗並保留 bounded trace，不記 prompt、OCR 原文、raw model output 或 API key。
- 模型政策：Vision-first selectable／callable surface 不保留 text-only Gemma 3 1B；只保留 legacy settings alias 以保護升級。
- ResourceGovernor 不與本 PR 混做。gpu_layers=999/0、partial offload、VRAM budget、idle TTL 與 buffer lifecycle 另立後續里程碑，避免把路由 correctness 與資源政策綁成大爆炸修改。

## 2026-08-09：CH-T68 先鎖 paired promotion gate，再切 Fullscreen

- promotion 只接受 `locked_test`／`public_audit`，development／example 調參資料不得進發版分數；若沒有 Owner 確認 ground truth 的 locked case，evaluator 必須拒絕執行。
- baseline 與 candidate 必須同模型、runtime、prompt、target、sampling、context 與 GPU 條件，固定 5 次 paired repeats；唯一允許的核心差異是 route identity。
- 準確度是硬閘門：aggregate 與逐 case 皆不得退化，nonempty／coverage 不得下降；只有品質先通過才輸出 latency 比較，速度不能抵銷品質。
- GPU 與 lifecycle 不接受 condition 自報：每筆 record 必須明示 runtime mode 與 residual process count；CPU fallback 不算 GPU 成功，缺證據不得默認為 0 residual。
- benchmark report 採欄位 allowlist，不輸出 OCR、翻譯、prompt、圖片 bytes、raw model output、憑證或任意未知欄位；provider／fallback reason 僅接受 bounded safe token。
- Vision partial IDs 不可靜默成功；目前 Region 採整批 OCR fallback。Fullscreen 在 product-path collector 與 locked holdout 通過前維持 OCR-first。
## 2026-08-09：Owner Review 與 product-path collector 不得繞過人工／生命週期證據

- 模型交叉判讀只能產生 `candidate_requires_owner_confirmation`；promotion API 必須重新驗證 workspace containment、實際 image SHA-256、blocked source family／hash、Owner provenance 與明確 confirmed source／translation，不能相信呼叫端先驗證過。
- source family 以作品、原影片／遊戲、生成 lineage 或 capture session 為單位；同作品不同頁不得假裝 source-disjoint，每 family 的 deterministic review selection 最多一張。
- product-path collector 以固定圖片覆寫每個隔離 `OCRWorker` instance 的 capture，仍呼叫正式 `run_scan_once()`；raw source／translation 只在記憶體交給 evaluator，對外只回傳 allowlist／redacted report。
- Fullscreen 在 Owner 確認 locked manifest、固定 GPU runtime 與 5-repeat paired accuracy-first gate 通過前維持 OCR-first；本階段沒有跑真 GPU，也不宣稱 latency 改善。
## 2026-08-09：CH-T68 condition-scoped benchmark 必須隔離預熱與路徑差異

- paired product-path benchmark 以 condition-scoped bundled llama-server 執行：baseline=text＋Windows OCR，candidate=vision＋0 OCR；固定 n_ctx=4096、temperature=0、repeat_penalty=1.15、zh-TW，差異僅限路徑條件。
- 每 repeat 清除 provider cache；cold start 與 cleanup 不納入 scan wall time。latency 順序固定 baseline_then_candidate，並明示 latency_order_balanced=false，不得把它解讀為平衡交錯設計。
- preflight 不啟 GPU；正式 record 必須逐筆驗證實際 runtime context、GPU layers、offloaded X/Y、owned process、127.0.0.1 loopback、server SHA、0 cache 與 fallback，不能以設定值或自報取代。
- 真 GPU A/B 只在 Owner 確認 4 張並建立 locked manifest、且 GPU 已空閒後執行。外部 Ollama 不屬 CloudHime 管轄；不得觸碰或終止它。報告僅留 aggregate，不保存私人原文。

## 2026-08-13：CodeRabbit evidence-date findings disposition

- CodeRabbit uncommitted review completed at local Windows time `2026-08-13 06:26 +08:00`; it returned two minor findings about future-dated evidence.
- Finding verified as false positive: all referenced execution, test, replay, and audit commands ran on local date 2026-08-13, and the rows already use that date. No measurement or evidence claim was moved earlier.
- The findings are not code defects; no product code change was needed. Remaining `Partial` statuses accurately represent pending owner ground truth, full CI, clean Windows/Store, and GPU paired promotion.

## 2026-08-13：CH-T34 基準差異定位為 sampling drift

- 以鎖定不變的 `benchmarks/ocr_accuracy_cases.json`（SHA-256 `5fc1f7073c3099a9b6fb60b23a5cceb88835962beab79becdff63384ca4898f`）、同一 Gemma 3 4B、同一 llama-server GPU、`-ngl 999`、`n_ctx=4096` 與 baseline prompt 重播。
- 現行 provider 預設 `temperature=0.2`、`repeat_penalty=1.15` 得到 avg match `0.9492087912`、avg latency `1788.176ms`；不應與舊紀錄的 `0.9892` 直接比較。
- 將 sampling 改為歷史 `temperature=0.1` 並省略 `repeat_penalty`，實機得到 `0.9892087912`／`1697.840ms`；改成現行 payload 可表達的 `temperature=0.1`／`repeat_penalty=1.0`，再次得到 `0.9892087912`／`1706.875ms`。兩次均 7/7 images、25/25 cases、line `22/25`、GPU。
- 結論：舊基準差異已由 sampling drift 重現並定位，不是 manifest 漂移；先不直接把參數 promotion 到所有翻譯路徑，需另做 source-disjoint local text translation paired regression，並確認 cache／翻譯品質後才改產品預設。


## 2026-08-13：CH-T64 同機短命自簽 MSIX gate

- 以目前 frozen dist/CloudHime-0.1.0.0-x64.msix 的隔離副本執行管理員互動 session gate；短命 CN=CloudHime Development 憑證只在驗證期間存在，結束後從 LocalMachine Root、CurrentUser My 與 CurrentUser TrustedPeople 移除。
- x64 SignTool /pa /all 驗章、Add-AppxPackage、AUMID CloudHime_4nvnqyjwyamgj!CloudHime 啟動、3 秒 liveness、卸載與 package/certificate cleanup 全部成功；正式 dist 未覆寫。
- 這證明本機開發自簽 sideload lifecycle 可重跑，不代表 Store 代簽、Store certification、clean Windows VM 或 GPU onboarding 已完成。


## 2026-08-13：CH-T64 WACK wrapper invocation incomplete

- 一次性簽署副本的 x64 SignTool /pa /all 驗章成功，但從管理員 Windows PowerShell bridge 呼叫 packaging/test_wack.ps1 時收到 Parameter set cannot be resolved using the specified named parameters，未產生 XML，故不得宣稱 WACK Pass。
- gate finally 已清除短命憑證、暫存 MSIX 與報告目錄；同機簽章／安裝／AUMID 啟動／卸載 gate 的 Pass 證據不受影響。
- CH-T64 維持 In Progress；後續需先建立可重現的 wrapper parameter-set regression，再修正並重新執行 appcert，仍不等同 clean Windows VM 或 Store certification。


## 2026-08-13：CH-T64 鎖定 WACK bridge 單一 parameter set

- 新增行為 regression，透過 PowerShell 7 入口呼叫 packaging/test_wack.ps1，只傳 -PackageFullName 與 -ReportOutputPath，確認 core bridge 只重新送出選定的 mode，不會把互斥的 -AppxPackagePath 一起帶入。
- 提升環境 targeted 4 passed；完整 MSIX／release packaging 37 passed。測試在 WACK 前置檢查前停止，不啟動 appcert，也不產生 XML；因此它只證明 parameter forwarding contract，不代表 WACK Pass。
- 官方 appcert CLI 仍要求先 `reset`，再以 `test -appxpackagepath` 或 `test -packagefullname` 搭配 `-reportoutputpath` 執行；下一次實機 gate 必須重新取得 XML 與唯一 `OVERALL_RESULT`。


## 2026-08-13：CH-T64 將環境隔離 smoke 接入 Windows CI

- msix-contract fixture preparation 後新增 environment-isolated release executable smoke；它呼叫 packaging/test_clean_machine.ps1，只驗證清空繼承環境、GUI liveness 與 exact PID cleanup。
- TDD：CI contract 先以 1 failed 證明 workflow 尚未接線，再接入 step 後 1 passed；完整 MSIX/release packaging 37 passed。
- 這是 CI contract 與 dummy executable smoke，不是 frozen CloudHime payload、clean Windows VM、Store certification 或 GPU onboarding 證據。


## 2026-08-13：CodeRabbit WACK bridge evidence disposition

- 本輪 CodeRabbit uncommitted review 回傳 2 個 minor findings：一項確認 appcert 指令文件含控制字元，已修正為可複製的 `reset`／`test`；另一項要求確認日期。
- 日期 finding 判定為 false positive：本機時間與本輪執行日期均為 2026-08-13，未把實際工作標成未來完成；所有未完成的 WACK／clean Windows／Store／GPU gate 仍維持明確 incomplete 或 pending。
- 本輪沒有產品程式 finding；下一步仍需重新執行真正 appcert WACK，取得 XML 與唯一 `OVERALL_RESULT`。


## 2026-08-13：CH-T64 direct appcert WACK gate 通過

- 以一次性短命 CN=CloudHime Development 憑證簽署隔離 MSIX 副本；x64 SignTool /pa /all 驗章成功。依 Microsoft 官方順序直接執行 appcert.exe reset 與 appcert.exe test -appxpackagepath ... -reportoutputpath ...，繞過前次 wrapper bridge 的異常引數向量。
- appcert reset／test 均 exit 0；XML report 3,105,016 bytes，/REPORT/@OVERALL_RESULT 恰好一個且為 PASS；短命憑證、MSIX 副本與 report 目錄均清除，正式 dist 未修改。
- 這只完成同機 direct WACK/appcert optional gate；test_wack.ps1 前次 bridge incomplete 仍保留為歷史 evidence，clean Windows VM、Store certification、GPU onboarding 仍未完成。


## 2026-08-13：CodeRabbit final review 與控制字元 regression checkpoint

- 上一輪 Major 指出 direct WACK evidence 內的 C0 控制字元；先新增 test_missioncenter_decisions_reject_c0_control_characters，RED 為 3 個 BEL，修正後 GREEN。
- 修正後 targeted WACK／CI 3 passed；完整 MSIX／release／CI inventory 43 passed in 45.30s；compileall、diff-check、MissionCenter doctor 均通過。
- 這段紀錄保留測試與修正證據；最後一次控制字元清理後的 CodeRabbit uncommitted review 已完成，findings=0。direct WACK 同機 PASS、clean Windows VM／Store／GPU 未完成狀態均維持不變。

## 2026-08-13：CH-E9 單一 llama runtime lifecycle／CUDA duplicate hardening

- 唯讀盤點確認目前 production worker 主路徑是單一 LocalVisionRuntime 加 llama-server HTTP provider；LocalGemmaProvider 的 llama_cpp in-process 路徑仍保留作 legacy/dev 相容碼，本輪不刪除，避免把 PR2 migration 與 lifecycle correctness 混成大重構。
- TDD 先重現 cleanup 漏掉 local vision executor 的 1 failed，再修正為停止 owned server 後以 cancel_futures=True 關閉 executor；不支援該參數的舊 executor/test double 仍有 wait-only fallback。
- 發行 verifier 新增 cudart/cublas、nvrtc、nvJitLink、cufft、curand、cusolver、cusparse 的 runtime 外 duplicate pattern；runtime 內仍由 runtime-manifest 精確檔案集合控管。
- 目前只證明 lifecycle／release contract；沒有宣稱移除 llama_cpp、clean Windows VM、Store certification 或 GPU paired promotion。
## 2026-08-13：CH-E9 hardening CodeRabbit final review

- CodeRabbit uncommitted review 覆蓋目前 CloudHime working tree scope，先前指出的 heading boundary 已修正；本次複審回傳 findings=0。
- 本結果只代表本階段 6 檔 hardening diff 的靜態 review；不升格為 clean Windows、Store certification、GPU paired promotion 或 legacy llama_cpp migration 完成。
## 2026-08-13：CH-E9 production LocalGemma in-process boundary isolation

- TDD 先加入 release boundary regression；RED：`dev_local_gemma_provider.py` 不存在且 `translation_providers.py` 仍含 `LocalGemmaProvider`／`llama_cpp`。
- 將 `LocalGemmaProvider` 原樣移至 `dev_local_gemma_provider.py`，明確標為 development-only；production `translation_providers.py` 不再匯出該類別，也不再含 in-process `llama_cpp` import；未改 LocalMultimodalProvider 的 HTTP／server 行為。
- 三個 dev compatibility tests 改由 dev module 匯入；fallback monkeypatch 只改到 dev module；`requirements.txt`／CI production 仍不含 llama-cpp-python，依賴保留在 `requirements-llama-dev.txt`。
- 驗證：targeted `53 passed, 1 skipped`；core elevated isolated `378 passed`；OCR `228 passed`；runtime `147 passed, 2 skipped`；benchmarks `178 passed`；compileall／diff-check 通過。
- UI test group 兩次在 5 分鐘內無摘要並 timeout；不得宣稱 UI group 通過。CodeRabbit CLI 安裝未完成：PowerShell 官方 URL TLS ProtocolVersion 失敗，WSL 官方腳本 124 秒 timeout；未宣稱 CodeRabbit review 完成，故本 checkpoint 暫不提交 Git。
- 未完成：實機 GPU／本地模型 paired benchmark、CLOUDHIME_RUN_LOCAL_MODEL=1 的真 GGUF 測試、clean Windows／Store gate；後續仍需在 CodeRabbit 可用後重新審查最後 diff。
## 2026-08-13：CH-E9 UI group timeout disposition

- 前次四檔 UI 合併命令曾因測試環境／收尾狀態在 5 分鐘內沒有摘要；未將其判為通過，也未修改 UI 產品碼。
- 以管理員權限、QT_QPA_PLATFORM=offscreen、每檔獨立 basetemp 逐檔重跑：39 passed、2 passed、1 passed、10 passed；再以新的合併 basetemp 重跑四檔，結果 `52 passed in 2.02s`。
- 因此前次 timeout 判定為可重現性不足的測試 harness／ACL 環境干擾，不是目前 UI assertion failure；完整 test group 證據已補齊。
## 2026-08-13：CH-E9 CodeRabbit findings disposition

- 使用既有 `/root/.local/bin/coderabbit`（version `0.7.2`，帳號 `Gale0418`，authenticated）審查 staged 變更，並確認新加入的 `dev_local_gemma_provider.py` 已列入 reviewedFiles。
- CodeRabbit 回報 3 個 findings：省略 `target_lang` 未回落至 provider 設定（major）、stream fallback cache 遺失 provider attribution（minor）、stream 先吐出未驗證候選（major）。
- 修正：`translate`／`translate_stream` 的 target default 改為 `None`；stream 與 synchronous fallback 都 cache 完整 `TranslationResult`；stream 先收集並驗證完整候選，失敗時只輸出 Google fallback。
- 修正後 targeted regression `56 passed, 1 skipped`；compileall／diff-check 通過。因本小時已使用 3 次 CodeRabbit allowance，修正後 review 尚未重跑，故本 checkpoint 不提交 Git，待冷卻後將同一批變更重新送審。
## 2026-08-13：CH-E9 MissionCenter evidence review disposition

- CodeRabbit final code review 已確認 `dev_local_gemma_provider.py` 的 3 個 findings 均已修正；後續文件修正針對 smoke evidence 的 host path、歷史回填標記與 intentional RED status。
- 文件修正後的下一次 CodeRabbit 呼叫回傳 rate limit，等待 `42 minutes`；不把 rate limit 當作 review 通過，也不重試消耗額度。
- 依既定流程先提交目前已驗證的 staged checkpoint；冷卻後以 commit 加上後續變更重新送 CodeRabbit，維持 `MissionCenter` 證據可追溯。
## 2026-08-13：CH-E9 application-scoped single llama runtime coordinator

- TDD 先新增 	ests/test_local_runtime_coordinator.py；初始 RED：ModuleNotFoundError: No module named 'local_runtime_coordinator'，再加入 coordinator 與 global single-runtime conflict contract。
- Controller 現在持有一個 LocalVisionRuntimeCoordinator 並注入 OCRWorker；相同資產共用 reference-counted lease，不同資產或 text/vision profile conflict 直接回報，不再 spawn 第二個本地 llama-server。
- worker 的 registry stop、取消 race、profile switch、GPU reconfigure、shutdown 與 cleanup 都改走 ownership-aware stop；最後一個 lease 才會停止 server，explicit stop + release 不 double-stop。
- 驗證：compileall Pass；ownership/worker targeted 83 passed；CI inventory + UI smoke 51 passed；完整受影響 OCR/runtime groups 375 passed, 2 skipped。Windows runtime suite 使用管理員隔離 basetemp；未宣稱真實 GGUF paired accuracy、clean Windows、Store certification 或 GPU hardware gate。
- 本 stage 已精確暫存 5 個檔案；CodeRabbit 仍在先前 rate limit 冷卻期，尚未對本 stage 宣稱 review 通過，待冷卻後與文件 follow-up 一起送審。

## 2026-08-13：CH-E9 local endpoint ownership gate

- TDD 先加入 registry／worker regression；RED：`3 failed, 5 passed, 103 deselected`，重現未擁有 server process 的 ready state、未驗證外部 endpoint 仍被當成 local provider ready，以及 local routing 忽略 provider availability。
- 修正：worker 只有在 ready state、owned process 仍存活、endpoint 為 `http://127.0.0.1:<port>/v1` 且 profile 相符時才宣告 local runtime ready；沒有 embedded runtime 時不再把設定檔 endpoint 當作活著的 server。registry builder 另要求明確 `local_runtime_validated` 與 loopback endpoint。
- 驗證：targeted `8 passed, 103 deselected, 1 warning in 1.13s`；受影響完整套件 `289 passed in 7.67s`；`ci/test_groups.json` 全部測試 `994 passed, 2 skipped in 86.82s`；compileall exit 0；Git whitespace check 以 `--ignore-space-at-eol` 檢查後僅包含預期新增邏輯。
- 本階段沒有啟動真實 GGUF／GPU／llama-server paired benchmark；CodeRabbit 仍在已知冷卻期，未宣稱 review 通過，待恢復後與後續變更一併送審。

## 2026-08-13：CH-E9 LocalMultimodal public API availability gate

- 唯讀盤點發現 LocalMultimodalProvider.translate_multimodal()、interpret_regions()、transcribe_screenshot()、translate_screenshot() 沒有像 translate() 一樣檢查 available()；worker 正常路徑雖有 provider selection，public API 在 runtime stop／設定切換 race 期間仍可直接送 HTTP。
- TDD RED：availability parameterized regression 4 failed, 35 deselected；修正後四個 API 在組 prompt／發 request 前統一回報 ValueError("local_multimodal_unavailable")。
- 驗證：targeted 4 passed, 35 deselected in 0.86s；provider/runtime/OCR/vision affected suite 182 passed in 6.96s；ci/test_groups.json 全量 998 passed, 2 skipped in 85.39s；compileall exit 0。
- 本階段沒有啟動真實 GGUF／GPU／llama-server；CodeRabbit 仍在已知冷卻期，未宣稱 review 通過，待恢復後與後續變更一併送審。

## 2026-08-13：CH-E9 stale local vision callback generation gate

- TDD 先重現 shutdown 後 late-ready callback：RED 1 failed, 78 deselected；修正後 stale callback 會停止 late-created runtime、清空 provider 並阻止 registry refresh。
- 追加 superseded-future regression：RED 1 failed, 1 passed, 78 deselected；修正以每個 future 綁定 lifecycle generation，且只有仍是 current future 才能清理；舊 future 完成時不會停止新 runtime。
- 驗證：兩個 lifecycle targeted 2 passed, 78 deselected in 0.97s；worker/runtime/OCR/coordinator affected suite 224 passed, 1 skipped in 6.48s；ci/test_groups.json 全量 1000 passed, 2 skipped in 77.65s；compileall exit 0。
- 本階段沒有啟動真實 GGUF／GPU／llama-server；CodeRabbit 仍在已知冷卻期，未宣稱 review 通過，待恢復後與後續變更一併送審。

## 2026-08-13：CH-E9 local multimodal empty-image fail-closed gate

- 唯讀盤點發現三個 local image API 在 runtime ready 但 image_parts 為空時仍會建立純文字 request：translate_multimodal、transcribe_screenshot、translate_screenshot；這可能讓模型依 prompt／OCR hint 猜出看似成功的結果。
- TDD RED：parameterized regression 3 failed, 39 deselected；修正後三個 API 在 request 前統一回報 ValueError("missing_image_context")，不改正常 non-empty image payload。
- 驗證：targeted 3 passed, 39 deselected in 0.74s；affected provider/runtime/OCR/vision suite 185 passed in 5.13s；ci/test_groups.json 全量 1003 passed, 2 skipped in 72.95s；compileall exit 0。
- 本階段沒有啟動真實 GGUF／GPU／llama-server；CodeRabbit 仍在已知冷卻期，未宣稱 review 通過，待恢復後與後續變更一併送審。
## 2026-08-13：CH-E9 CodeRabbit review for four hardening checkpoints

- 使用既有已登入 CodeRabbit CLI 0.7.2／Gale0418，審查 base commit c1207c2 之後的已提交差異；審查範圍限於 8 個小檔案，未納入未追蹤 .tmp。
- 實際 receipt：reviewType=committed、baseCommit=c1207c2、reviewedFiles=8、findings=0；未將 review 結果擴大解釋為 GPU、clean-machine 或 Store 驗證。
- 本次 review 覆蓋 owned runtime gate、provider availability gate、stale callback generation gate 與 empty-image fail-closed gate；後續若改動這些檔案，需重新做 targeted regression 與增量 review。

## 2026-08-13：Persisted boolean settings normalization gate

- TDD 先擴充 `normalize_settings_payload()` regression，覆蓋 `use_gemma_translation`、`auto_threshold_enabled`、`google_ocr_enabled`、`gemma_auto_switch_enabled`、`local_multimodal_enabled`、`local_multimodal_cpu_only`、`japanese_ocr_rescue_enabled`、`region_pass_through`、`is_dark_mode` 的 bool、0/1、true/false、yes/no、on/off 與 unknown。
- RED：`9 failed, 2 passed, 22 deselected in 2.05s`；修正後 targeted `11 passed, 22 deselected in 0.77s`。原設定入口在 `cloudhime_ui.py` 仍保留 `bool(settings.get(...))`，因此 canonical normalization 必須先把字串轉成真正 bool，避免 `bool("false") == True`。
- 驗證：拆分受影響 suite 分別為 settings `33 passed in 3.36s`、UI smoke `39 passed in 1.14s`、theme `1 passed in 1.39s`、translation panel `10 passed in 0.97s`；四檔合併命令曾超過 120 秒未完成，未視為通過；`compileall` exit 0；`ci/test_groups.json` 全量 `1003 passed, 2 skipped in 75.62s`；`git diff --check` 僅有既有 LF/CRLF warning，無 whitespace error。
- 本階段沒有啟動真實 GGUF／GPU／llama-server paired benchmark；未宣稱 clean Windows、Store certification 或 hardware gate；CodeRabbit 尚未審查本次新增 commit。
## 2026-08-13：CodeRabbit review for persisted boolean settings gate

- 使用既有 `/root/.local/bin/coderabbit` CLI 0.7.2，未安裝或下載套件；審查已提交差異 `c994029..b7b7b9f`。
- 實際 receipt：`reviewType=committed`、`baseCommit=c994029`、`reviewedFiles=4`（`MissionCenter/decisions.md`、`MissionCenter/smoke-tests.md`、`settings_store.py`、`tests/test_settings_store.py`）、`findings=0`。
- 本結果只代表本次 code/document review；不代表真實 GGUF／GPU accuracy、clean-machine、Store certification 或硬體 gate 通過。
## 2026-08-13：LocalGemma streaming fallback attribution gate

- TDD 先加入 LocalGemma stream provenance 與 OCRWorker 最終 provider regression；RED：worker regression `1 failed, 1 passed, 120 deselected`，重現 stream fallback 文字被回報為 requested `gemma` 而非實際 `google`。
- 修正：dev-only `LocalGemmaProvider.translate_stream()` 在 cache、正常完成與 fallback 完成時保存 `last_stream_result`；OCRWorker 只讀 optional result metadata，返回實際 provider，既有 chunk 格式與 stream signals 不變。
- 驗證：targeted `2 passed, 120 deselected in 1.16s`；provider + OCR mode matrix `122 passed in 5.00s`；`ci/test_groups.json` 全量 `1004 passed, 2 skipped in 76.15s`；compileall exit 0；diff-check 無 error。
- 本階段未啟動真實 GGUF／GPU／llama-server paired benchmark；未宣稱 clean Windows、Store certification 或 hardware gate；待提交後再做 CodeRabbit 增量 review。
## 2026-08-13：CodeRabbit stream cache finding disposition

- 本輪 CodeRabbit committed review：base `7d0af76`、reviewedFiles `6`、初始 `findings=1`；finding 指出 cached `TranslationResult` 直接掛到 `last_stream_result` 時未標 `from_cache=True`。
- TDD RED：新增 cache-hit assertion `1 failed, 41 deselected`；修正後 targeted `2 passed, 120 deselected in 0.92s`，affected provider/OCR suite `122 passed in 4.67s`；compileall exit 0；diff-check 無 error。
- 修正以新 `TranslationResult` 複製 cached text/provider/model/raw/fallback provenance 並設定 `from_cache=True`，不改變 cache 內原物件。
- 本輪 full CI `1004 passed, 2 skipped in 76.15s` 是 finding 修正前的 checkpoint；finding 修正後已跑 affected suite，未宣稱 post-fix full CI。CodeRabbit 初始 review 已有 1 finding，修正後未重新取得 second review receipt。
## 2026-08-13：Corrupt AppData canonical repair gate

- 唯讀審計發現：AppData 設定檔存在但 JSON 損毀、且沒有可用 legacy 檔時，`load_settings_data()` 回傳預設值與 `loaded_from=None`，舊 `should_migrate_to_appdata()` 卻因檔案存在而拒絕重建 canonical 檔。
- 修正：`loaded_from_path is None` 視為需要建立／重建 AppData canonical settings；有效 AppData 仍優先於較新的 legacy 檔；使用既有 atomic `save_settings_data()` 寫回。
- 驗證：新增 corrupt AppData test `1 passed, 33 deselected in 0.83s`；settings + UI affected `73 passed in 1.21s`；compileall exit 0；diff-check 無 error。合併 full CI 命令超過 300 秒且無 failure summary，未算通過；拆分五群組結果 core `396 passed`、OCR `232 passed`、runtime `147 passed, 2 skipped`、UI `52 passed`、benchmarks `178 passed`，合計 `1005 passed, 2 skipped`。
- 這個新增案例是在實作後才執行，未捕捉 pre-fix RED，不能宣稱 TDD RED；本階段未做真實 GGUF／GPU／llama-server paired benchmark、clean Windows 或 Store certification。
## 2026-08-13：CodeRabbit post-fix cooldown receipt

- 修正 stream cache provenance 後嘗試以 base `7157e5f` 進行增量複審；CodeRabbit 實際回報 `rate_limit`，`waitTime=16 minutes`，沒有產生 post-fix review result。
- 因此 `cda9254` 只宣稱 affected tests 通過與 initial finding 已修正，不宣稱複審 0 findings；待 cooldown 後可將後續累積變更一起送審。
## 2026-08-13：Retired Gemma 3 1B UI metadata removal

- 唯讀盤點發現 `model_catalog.py` 與 catalog tests 已排除 `gemma-3-1b-it`，但 `translation_settings_panel.py` 仍保留「快速純文字模型、截圖回退 OCR」提示。
- TDD RED：新增面板 contract `1 failed, 10 deselected`，現行 1B note 仍可被直接查出；修正後 panel suite `11 passed in 0.88s`，compileall exit 0、diff-check 無 error。
- UI 受影響測試合併執行 180 秒 timeout、無 failure summary，未算通過；逐檔 smoke `39 passed in 1.05s`、relief `2 passed in 0.09s`、theme `1 passed in 1.24s`，加 panel suite 共 `53 passed`。
- 本階段只移除已淘汰模型的 UI metadata，未改模型 catalog／remote provider behavior；未做真實 GPU／GGUF、clean Windows 或 Store certification；CodeRabbit 因冷卻尚未覆蓋本次 commit。
## 2026-08-13：History export nested-key collision gate

- 唯讀審計發現 `_json_safe_history_value()` 將 nested dict key 全部 `str()`，`{1: "A", "1": "B"}` 會靜默覆蓋一筆值；這違反 schema export 不得無聲遺失資料。
- TDD RED：新增 collision regression `1 failed`，重現沒有拒絕碰撞；修正後遇到一次未提交的 regex newline 語法錯誤（collection SyntaxError），立即修正並重新驗證。
- 修正：nested dict 轉換時偵測 string key collision，明確拋出 `TypeError("translation_history_not_serializable")`；不改既有 schema_version/list-of-records 格式。
- 驗證：history targeted `6 passed, 34 deselected in 0.83s`；完整 `tests/test_cloudhime_ui_smoke.py` `40 passed in 1.01s`；compileall exit 0；diff-check 無 error。
- 本階段未做真實 GGUF／GPU／llama-server paired benchmark、clean Windows 或 Store certification；CodeRabbit 仍在 rate limit 冷卻。

## 2026-08-13：MissionCenter 0.3.1 工作區契約採用

- 沿用並重新開啟 `CH-E10`，不建立重複的現代化 Epic；新增 `CH-T88`～`CH-T91` 承接 0.3.1 遷移、canonical 正規化、managed summaries 與 execution checkpoint 驗證。
- 採用 bounded Resume、`working-set.md`、`critical-lessons.md` 與 `incidents/`；`focus.md` 降為相容檢視，只保留一個遷移週期。
- 舊 `project.md`／`progress.md` 將以一次性 `--rewrite-summaries` 正式納入 managed summaries；往後不得手動維護衍生統計。
- tasks 與 smoke 原始內容先封存，再轉成 0.3.1 嚴格表格。舊結果只有明確成功才映射為 `Pass`，其餘保守映射為 `Fail`；不以遷移名義捏造測試成功。
- 不建立 `legacy-done-audit.json`：既有 Done 任務的 passing evidence 可由修復後的 canonical smoke table 重建，額外 waiver 沒有必要。
- 既有 snapshot 以 legacy archive 保留，最終 checkpoint 只從 canonical tasks／project／Git 狀態重建；不沿用舊版 fact-like flags。
- 此工作是本機、確定性的文件／狀態遷移，不涉及 UI 感知決策、外部 prior art、GPU 效能聲明或產品程式碼，因此不啟動 CACC、外部研究或 CodeRabbit。

## 2026-08-14：OCR retry 與 fallback observability hardening gate

- Gemini local loopback readonly review（cascade 2ce7881e-dfd0-44c9-956c-6fcbed3267d9，visibility=hub_visible、delivery_state=DELIVERED）指出 fullscreen manga tile retry 失敗會清空已成功的 baseline OCR items；同時指出 Google OCR prefetch 與逐筆翻譯 fallback 的 silent exception。
- 修正：tile retry exception 保留 baseline items 並只記錄 exception type；Google OCR timeout／一般 exception 均 bounded logging；逐筆翻譯 fallback 記錄 index 與 exception type，不記錄 API key、prompt 或 OCR 原文。
- 回歸測試：先重現 manga retry 1 failed, 80 deselected；修正後 targeted 4 passed, 78 deselected in 1.41s（涵蓋 manga retry、Google timeout、Google exception、translation fallback warning）；OCR mode matrix 82 passed in 5.40s；OCR CI group 234 passed in 6.20s；compileall exit 0、diff-check 無 error。
- core／runtime／UI／benchmarks 五群組命令已實際執行，但部分測試在 pytest setup 或 session cleanup 遇到既有 Windows temp ACL WinError 5；未取得這四組的完整通過結果，故不宣稱全量 CI 通過。未做 GPU、真實 GGUF、clean Windows、Store 或 WACK 驗證。
- CodeRabbit formal committed review：base b496e0f、reviewedFiles=2（cloudhime_workers.py、tests/test_ocr_worker_mode_matrix.py）、findings=0；CLI 0.7.2、帳號 Gale0418 authenticated。此 receipt 只涵蓋本輪兩個程式／測試檔，不涵蓋硬體、發行或 MissionCenter 文件。
## 2026-08-14：Bounded Hybrid OCR rescue 接線

- Gemini local loopback readonly review（cascade 10acc8bd-2cfc-491f-84b3-4973a68b486d，visibility=hub_visible、delivery_state=DELIVERED）與本地盤點確認：hybrid_search_benchmark.py 原先只有離線 84 策略 benchmark，production OCR 仍是單一 binary-invert fast path。
- 採用 accuracy-first 最小接法：fast path 命中不增加呼叫；只有 OCR 無文字時才進 bounded rescue；rescue 固定兩個 preprocess（adaptive_invert、clahe_otsu_invert），不把完整搜尋空間帶入每幀；新 registry 對未知策略與超過 budget fail-closed。benchmark 與 production 共用 ocr_preprocess.py。
- TDD RED：新增 rescue contract 後先得到 2 failed（module 尚不存在）；接線初版再由既有 threshold tests 抓到 task tuple 舊解包造成的 silent fail-open，已修正。最終 targeted：worker threshold/rescue 3 passed, 78 deselected；mode matrix 3 passed, 82 deselected；Hybrid benchmark 5 passed；OCR group 238 passed in 5.76s；packaging/inventory/Hybrid 28 passed；benchmark_lock ok=true；compileall／diff-check Pass。
- CodeRabbit：第一次 uncommitted review 回報 MissionCenter 遷移註記位置問題，已將註記移到 canonical smoke table 最後並拆開黏連的兩筆 evidence，文件 checkpoint ecbb17f；精準 committed review base 139ea56 覆蓋本輪 6 files、findings=1（rescue test 未驗證結果消費），已補 last_combined_text／last_results assertion，checkpoint 09589c5。本輪最後一次複審實際回報 rate_limit、waitTime=38 minutes，未宣稱 post-fix review 通過。
- 未執行真實 GPU／GGUF／llama-server latency benchmark、clean Windows、Store 或 WACK；rescue 尚未以速度 promotion，只有在 no-text 路徑使用。
## 2026-08-14：Coordinator stopped-runtime rejection hardening

- Root cause：`LocalVisionRuntimeCoordinator.acquire()` 只檢查 asset/profile，未檢查既有 entry 的 `stopped` 狀態；唯一 lease 呼叫 stop 後，下一個 consumer 可能取得未重新啟動的 stale runtime。
- 修正：entry 已 stopped 時 fail-closed 回報 `shared_runtime_stopped`；必須先 release 舊 lease，才會建立新的 runtime entry，維持單一 engine ownership。
- TDD：先新增 regression 得到 `1 failed, 6 deselected`；修正後 coordinator suite `7 passed in 0.12s`，受影響 worker/runtime selection `30 passed, 58 deselected in 1.35s`；compileall 與 diff-check Pass。
- 本輪沒有實機 llama-server、GPU、GGUF、clean-machine、Store/WACK 驗證；CodeRabbit 仍在上一輪 rate limit 冷卻，未送本輪 review。
## 2026-08-14：Coordinator stop 冪等性收斂

- 同一個 active lease 重複呼叫 stop 時，現在只會觸發一次底層 runtime.stop()；後續呼叫回傳既有 state，不重複操作 process。
- TDD：新增 idempotence regression 先得到 `1 failed, 7 deselected`（stop_calls=2）；修正後 coordinator suite `8 passed in 0.12s`，compileall／diff-check Pass。
- 此為 source-level lifecycle hardening；未做真實 llama-server、GPU、GGUF、clean-machine、Store/WACK 驗證；CodeRabbit 仍在上一輪冷卻，未送本輪 review。
## 2026-08-14：Local multimodal close readiness hardening

- Root cause：`LocalMultimodalProvider.close()` 原先只關閉 request scheduler、cache 與 metrics，沒有撤銷 `enabled`／`_runtime_ready`；cleanup 後 `available()` 仍可回傳 true，造成上層誤把已停止的 Vision provider 當成可用。
- 修正：close 對 provider instance 採 terminal semantics，先清除 enabled／runtime-ready，再關閉 scheduler 並清空本地狀態；不改正常 ready、HTTP payload、FIFO 或 fallback 行為。
- TDD：新增 close readiness regression 先得到 `1 failed, 21 deselected`；修正後 provider suite `22 passed in 0.82s`，受影響 worker cleanup/runtime `28 passed, 53 deselected in 1.25s`；compileall／diff-check Pass。
- Gemini bridge 本輪唯讀請求實際兩次均回報 `attempt to write a readonly database`，未宣稱 Gemini review 成功；本輪未執行 GPU／GGUF／clean-machine／Store/WACK 驗證。
## 2026-08-14：Local multimodal close CodeRabbit receipt

- CodeRabbit CLI 0.7.2 與 Gale0418 authentication 均確認成功；精準 committed scope 為 base `8660ef4` 到 `e45fb56`，預期只涵蓋本輪 4 個小檔案。
- 實際 review service 回報 `rate_limit`、`waitTime=24 minutes`；因此本輪沒有 CodeRabbit findings result，也不宣稱 review 通過。等待冷卻期間先繼續本地驗證。

## 2026-08-14：Local multimodal terminal reactivation hardening

- Root cause：cleanup 後 provider 的 scheduler 已關閉，但設定重刷仍可能把 enabled 設回 true，再以 update_runtime(ready=True) 造成錯誤的可用狀態。
- 修正：LocalMultimodalProvider 增加 terminal _closed state；available() 與 update_runtime() 都 fail-closed，close() 後不允許同一 instance 重新活化。正常首次初始化與 ready runtime 行為不變。
- TDD：先加入「close 後重新設定不得 re-activate」regression，RED 1 failed, 22 passed；修正後 provider 23 passed in 0.79s；受影響 provider／worker／vision 29 passed, 1 skipped in 1.15s；compileall／diff-check 最終 Pass。
- 本輪未送 CodeRabbit（既有 rate limit 冷卻中）；未執行真實 GPU／GGUF／llama-server latency、clean-machine、Store 或 WACK。


## 2026-08-14：Stale scan status generation fence

- Lorentz 唯讀盤點指出：結果／stream 已有 generation fence，但 legacy status_msg 仍會無條件發出 stale scan 的進度或錯誤；scan_status_msg 雖由 UI 過濾，外部 legacy consumer 仍可能誤判目前狀態。
- 修正：OCRWorker._emit_scan_status() 在送出兩種訊號前檢查 _active_scan_is_current()；stale request 回傳 False 且不發任何 status，current request 保留既有 legacy／generation-tagged 行為。
- TDD：新增 stale status regression，RED 1 failed, 1 passed, 84 deselected；修正後 targeted 2 passed, 84 deselected in 1.15s；compileall／diff-check Pass。完整 mode matrix 為 85 passed, 1 failed in 5.06s，單獨重跑同一既有 exact_cache_hit_refreshes_frame_gate_consecutive_baseline 仍失敗（預期 Recovered、實際 Hello），與本次 status fence 不相交，未擴大修正。
- 未執行真實 GPU／GGUF／llama-server latency、clean-machine、Store 或 WACK；CodeRabbit 仍在 rate limit 冷卻，未送本輪 review。


## 2026-08-14：Explicit llama runtime provenance gate

- Root cause：build_exe.bat 原先以 git rev-parse HEAD 產生 RUNTIME_COMMIT；那是 CloudHime 專案 commit，不是 bundled llama.cpp／llama-server build provenance。runtime 目錄也沒有可讀的 commit metadata。
- 修正：release build 只接受明確的 LLAMA_RUNTIME_COMMIT，或 runtime/llama-runtime-commit.txt；兩者皆缺少時 fail-closed，不再把專案 HEAD 冒充 runtime commit。packaging README 已同步說明。
- TDD：新增 release contract regression 先 RED 1 failed, 17 deselected；修正後 1 passed, 17 deselected；compileall／diff-check Pass。實際 runtime/llama-server.exe --version 嘗試由外層 30 秒 timeout，未取得 version output，未宣稱 frozen build／manifest／GPU gate 通過。
- 本輪未執行 CodeRabbit（rate limit 冷卻中）；未執行 clean-machine、Store 或 WACK。


## 2026-08-14：Hybrid rescue assertion placement correction

- Root cause：前一輪為了驗證 rescue consumption，新增的 Recovered assertion 被誤插到 exact-cache／FrameGate 測試；該測試的 OCR fixture 固定回傳 Hello，因此造成 85 passed, 1 failed，並非 FrameGate production regression。
- 修正：將 exact-cache 測試中的兩個錯誤 Recovered／你好 assertion 改為 fixture 真正產生的 Hello／Nihao；保留真正 no-text hybrid rescue 測試的 Recovered／你好 assertion。未修改 production code。
- 驗證：完整 tests/test_ocr_worker_mode_matrix.py 86 passed in 4.84s；hybrid rescue subset 2 passed, 84 deselected in 0.95s；compileall／diff-check Pass。

## 2026-08-14：Vision runtime terminate failure cleanup

- Root cause：`LocalVisionRuntime._cleanup_process()` 原先把 `terminate()`、`wait()` 與 `kill()` 包在同一層 try；若 Windows process handle 的 `terminate()` 直接拋例外，會提前跳出並留下仍可能持有模型的 process。
- 修正：`terminate()` 失敗時立即對同一個 owned handle 做 best-effort `kill()`；正常 terminate timeout 的既有 kill 路徑維持不變；不依名稱掃殺、不改外部 process。
- TDD：新增 terminate-raises regression；直接呼叫 regression harness、既有 stop／timeout／health-timeout／GPU→CPU／profile-switch 回歸均 Pass；`compileall` 與 `git diff --check` Pass。pytest target 因 Windows temp ACL `WinError 5` 在 setup／收尾失敗，未宣稱 pytest suite 通過。
- 本輪未送 CodeRabbit（冷卻中）；未執行真實 GPU／GGUF／llama-server latency、clean-machine、Store 或 WACK。
## 2026-08-14：Vision runtime state publication race hardening

- Root cause：`stop()` 可在 `start()` 健康檢查回報 ready 後、終態發布前插入；舊流程可能讓 caller 收到 ready，但 owned process 已被停止，形成假 ready／殘留狀態不一致。
- 修正：加入短生命週期 state lock；stop 先原子標記 stopped、摘除 owned handle，再清理 process；ready、CPU fallback 與 failed terminal state 發布前重新檢查取消訊號。未改 UI、HTTP payload、profile 或 fallback policy。
- TDD：race regression 先由手動 harness RED；修正後 race、慢冷啟動取消、ready／starting idempotence、health timeout、GPU→CPU、stop timeout／terminate exception、profile switch targeted calls 均 Pass；`compileall` 與 `git diff --check` Pass。pytest target 仍受 Windows temp ACL `WinError 5` setup／收尾限制，未宣稱 suite 通過。
- 本輪未送 CodeRabbit（冷卻中）；未執行真實 GPU／GGUF／llama-server latency、clean-machine、Store 或 WACK。
## 2026-08-14：CodeRabbit cumulative lifecycle review disposition

- 審查範圍：base `8660ef4` 到 `471dfe0`；實際 reviewedFiles=11，未包含 models、dist、runtime DLL 或大型 artifact。
- Major 日期 findings 判定為 false positive：本機 Taipei clock 為 `2026-08-14 +08:00`，本輪 commits `55f435d`、`52a6a5b`、`e70fd38`、`471dfe0` 的 Git timestamp 也為 2026-08-14；不得為迎合錯誤推論改寫真實執行日期。
- Minor 表格位置 finding 判定為有效：兩列新 smoke evidence 原先位於 0.3.1 migration note 後，已移回 canonical smoke table 結尾、保留欄位內容。
- CodeRabbit 實際回報 3 issues（2 major false positive、1 minor corrected）；production code 未發現需修正的 finding。修正文件位置後，後續複審仍需以最新 HEAD 判定，不把本次初輪結果當成 post-fix 0 issues。
## 2026-08-14：CodeRabbit post-fix review attempt

- 初輪 committed review 實際完成：base `8660ef4`、reviewedFiles=11、回報 3 issues；2 個日期 major 經本機 clock／Git timestamp 查證為 false positive，1 個 smoke table placement minor 已修正。
- 修正後第一次複審回報 `rate_limit`、`waitTime=3 seconds`；等待 5 秒重試時 WSL bridge 回 `E_ACCESSDENIED`，未取得 post-fix findings result。
- 因此本輪不能宣稱 CodeRabbit post-fix 0 issues；production code 沒有初輪 finding，MissionCenter 文件 finding 已修正，待 bridge／免費額度恢復後再做最後複審。
## 2026-08-14：Affected lifecycle／OCR／release suite rerun

- 首次合併命令因錯誤設定 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 導致 `qtbot` fixture 缺失，結果 `99 passed, 83 errors`，判定為 test command configuration failure，不作產品結論。
- 以提升權限、`QT_QPA_PLATFORM=offscreen`、保留 pytest-qt 與隔離 basetemp 重跑：`tests/test_local_vision_runtime.py`、`tests/test_local_multimodal_provider.py`、`tests/test_ocr_worker_mode_matrix.py`、`tests/test_release_packaging.py` 合計 `182 passed in 5.64s`。
- 本結果只證明受影響自動化回歸與 release contract；未宣稱真實 GPU／GGUF latency、clean-machine、Store 或 WACK gate。
## 2026-08-14：Release contract rerun after lifecycle hardening

- 以提升權限、offscreen、隔離 basetemp 重跑 `tests/test_release_packaging.py`、`tests/test_msix_packaging.py`、`tests/test_ci_test_inventory.py`：`45 passed in 174.10s`。
- 此為 packaging／MSIX／CI inventory contract evidence；不推導真實 Store submission、WACK XML、clean-machine 或 GPU onboarding 已通過。
## 2026-08-14：Fresh frozen release、clean-machine 與 GPU vision smoke

- 使用現有 runtime manifest 的可信 llama source commit `de9b028e08d5b52bf424ac88df7702f3e15c3d6e` 執行 `LLAMA_RUNTIME_COMMIT=... build_exe.bat`；完整 build exit 0，內建 release preflight 通過。
- fresh `dist\\CloudHime` preflight：provenance verify ok、384 files、1,530,297,643 bytes、ModelFiles=0；runtime manifest version `9968 (1d1d9a9ed)`、backend=cuda、architecture=x64；未包含第二套 Python llama binding。
- fresh packaged launch：`test_clean_machine.ps1 -LaunchWaitSeconds 5` PASS，PID=40204；結束後 CloudHime／llama-server 均不存在。
- 真實 GPU local vision smoke：直接 Windows console 執行 `vision_smoke_benchmark.py --max-cases 1 --require-gpu --timeout 120 --startup-timeout 240 --json` PASS；runtime_mode=gpu、require_gpu=true、1/1 successful、line_match=1/1、match_score=1.0、startup=12229.9ms、average latency=1130.3ms；無 residual process。
- 同一 smoke 首次因 cp950 無法輸出日文 JSON 暴露 CLI Unicode bug；新增 stdout UTF-8 reconfigure 與 regression，完整 benchmark tests `20 passed`，修正後不設定 PYTHONIOENCODING 的直接 GPU smoke 也 PASS。
- 以上是 fresh artifact／單 case GPU smoke 證據；不推導完整 4-case／25-case accuracy、Store submission、WACK 或 clean-machine VM 已完成。
## 2026-08-14：Vision smoke Unicode CodeRabbit disposition

- 本階段 committed review：base `e818e99`、reviewedFiles=4，實際回報 1 個日期 major。
- 查證為 false positive：本機 Taipei clock 為 `2026-08-14 +08:00`，fresh frozen build、clean-machine、GPU smoke 與 benchmark tests 均在 2026-08-14 執行；smoke rows 保留真實完成日期，不改寫成 8/13，也不把已完成證據改成 planned。
- production `vision_smoke_benchmark.py`／regression test 未收到 CodeRabbit finding；本階段 review 結果為 1 個文件日期 false positive，非 0 issues。
## 2026-08-14：Fresh MSIX optional WACK elevation boundary

- fresh unsigned MSIX：`artifacts\post-change-msix-20260814\CloudHime-0.1.0.0-x64.msix`；本輪未覆寫正式 `dist`。
- 一般 terminal 與原生 Windows PowerShell 5.1 都因目前 session `Administrator=False` 被 `packaging\test_wack.ps1` 正確拒絕；沒有 XML，也沒有 `OVERALL_RESULT`。
- `Start-Process -Verb RunAs -Wait` 嘗試取得真正 UAC token，但目前桌面回報「操作被使用者取消」；因此本 fresh artifact 的 WACK 結果是 incomplete，不是 PASS，也不是產品 FAIL。
- 不改寫先前 2026-08-13 另一份 signed artifact 的 direct appcert PASS；下一次需在能接受 UAC 的真正互動式管理員桌面重跑，並只採信唯一 `/REPORT/@OVERALL_RESULT=PASS`。
## 2026-08-14：Japanese OCR rescue full-candidate arbitration

- Root cause：`decide_rescue_text()` 原先只比較第二次 VLM 結果與移除低信心字元後的 `trusted_text`；只要可信片段更接近，即可能採納漏掉其他候選內容的結果。
- 修正：新增完整 `candidate.text` 的 baseline／second similarity gate；第二結果必須改善 trusted similarity，且完整候選 similarity 不低於 baseline 才能採納。保留原有 `first_similarity`／`second_similarity` log 欄位，另加入 bounded candidate 分數。
- TDD：RED 新 regression `1 failed, 5 passed`；GREEN rescue／integration `10 passed`；含 Japanese runtime 與 OCR mode matrix 的受影響集合 `99 passed in 4.85s`；compileall／git diff --check Pass。
- CodeRabbit uncommitted review 實際回報 2 個文件日期 issues；依本機 2026-08-14 clock 與實際執行時間查證為 false positive，未改寫真實日期；本輪沒有 production code／test finding。未宣稱完整漫畫 holdout、GPU 或 Store 通過。
## 2026-08-14：Translation E2E evaluator benchmark lock hardening

- Root cause：`translation_e2e_benchmark.py` 定義 accuracy evaluator 的權重與空輸出規則，但 `benchmark_lock.py` 只要求 dataset 與 scheduling harness；評分器語意變更可能不改 lock ID 卻破壞歷史可比性。
- 修正：新增 required artifact `translation_e2e_evaluator`，鎖定 `translation_e2e_benchmark.py` SHA-256 `19170a974e7d42222f9ada809b8e918d905a880c3d9aa46e5ffb2bca7da3936f`，並將 lock ID 升為 `cloudhime-accuracy-speed-temporal-v4`；補 missing-artifact 與 mutation regression。
- TDD：提升環境 GREEN `33 passed in 1.55s`；`python benchmark_lock.py` 回傳 `ok=true`、4 datasets、2 artifacts；compileall／git diff --check Pass。
- CodeRabbit 本輪 review 實際回報 2 個日期 issues，與本機 clock／實際執行時間不符，查證為 false positive；未改寫已完成證據，也未宣稱 CodeRabbit 0 issues。
## 2026-08-14：Local translation cancellation propagation

- Root cause：LocalRequestCancelled 繼承 RuntimeError，一般 multimodal、screenshot、stream、batch 與逐項補翻的既有 except Exception 會把 shutdown／stale request 當成普通 provider failure，繼續走文字 fallback，可能產生錯誤結果與 cache side effect。
- 修正：在既有 fallback 邊界加入明確的 except LocalRequestCancelled: raise；run_scan_once() 沿用 Region Vision 的 generation fence，只有 stale cancellation 直接返回，非 stale cancellation 重新拋出，不改 public UI signals 或正常 provider error fallback。
- TDD：RED 1 failed, 86 deselected；GREEN cancellation targeted 2 passed, 86 deselected；受影響 OCR／Vision／Japanese 四檔 101 passed in 4.96s；compileall 與 git diff --check Pass；commit 91cefaf。
- CodeRabbit 實際嘗試 committed review（base cacbeed）回報 rate_limit、waitTime=20 minutes，沒有 findings result，因此不宣稱 review 通過。未執行真實 GPU／GGUF latency、完整漫畫 holdout、Store、WACK 或 clean-machine gate。
## 2026-08-14：Hybrid Search bounded cost boundary

- 實驗：以 Windows OCR backend 對 25 個 locked OCR cases、84 個 preprocess／threshold／scale 策略執行全量 screening；不啟動 Gemma、llama-server 或 GPU。
- 結果：命令達到 180.034 秒 bounded timeout、exit 124，未產生可用結果檔；早先 5-case screening 可完成，但最佳策略只有 1/5 hit，不能推導全域最佳或品質改善。
- 決策：不把全量 Hybrid Search 放進每次線上掃描。後續若要產品化，先做固定少量候選的 coarse-to-fine、策略 fingerprint／cache 與明確時間 budget；品質必須以人工標註 holdout 重新驗證。
## 2026-08-14：Hybrid benchmark source deduplication and complete-result gate

- Root cause：25 個 target case 只引用 7 張 unique 圖片；舊 evaluator 對每個 strategy／case 重複 OCR，同一張圖最多重跑多次。舊 TrialResult 也沒有 complete 語意，partial/pruned trial 可能參與 winner 排名。
- 修正：依 sample_source 分組，每 strategy 對每張圖只呼叫一次 backend，再以該圖的 filtered OCR lines 計算各 target 命中；新增 complete、evaluated_sources，winner／summary／best-hit 更新只接受完整結果；新增 deterministic --max-strategies offline budget，預設不改既有完整 strategy space。
- TDD／驗證：RED 去重與 complete contract 2 failed；GREEN tests/test_hybrid_search_benchmark.py 10 passed；受影響 benchmark suite 27 passed in 1.67s；compileall／git diff --check Pass。實測 25 targets／7 sources／84 strategies full screening 約 32.2s，14 個完整策略，最佳完整結果 14/25；24 strategies 約 10.1s，4 個完整。這是 evaluator／screening 證據，不是 production OCR 品質提升。
- 審查：CodeRabbit auth 成功，但本輪 committed review 回報 rate_limit、waitTime=4 minutes，無 findings result，不宣稱 review 通過。Gemini bridge discover 成功，但 prompt 兩次回報 attempt to write a readonly database，無 Gemini 意見可引用。
## 2026-08-14：Single local runtime profile-transition ownership

- Root cause：LocalVisionRuntimeCoordinator.set_profile() 會先停止既有 process 並標記 entry stopped；worker 後續若直接呼叫 runtime.start()，實際 process 已重新 ready，但 coordinator 不知道這次啟動，後續 consumer 可能錯誤收到 shared_runtime_stopped。這也讓跨層「先停後啟、最多一個 live server」缺少可觀測 contract。
- 修正：LocalVisionRuntimeLease 新增受 coordinator 保護的 start()；成功回傳 ready／starting 時同步清除 stopped 狀態。OCRWorker._prepare_and_start_local_vision() 改由 lease（無 lease 時仍由 runtime）啟動，保留既有 cancel event、profile、HTTP、UI signal 行為。
- TDD：先加入真實 LocalVisionRuntime fake process regression；RED 為 lease 缺少受控 start 的 1 failure。修正後 targeted 1 passed in 1.03s；受影響 runtime／worker／vision suite 262 passed, 1 skipped in 12.04s；release／MSIX／manifest／dependency contract 85 passed, 2 skipped in 273.39s；compileall 與 git diff --check Pass。
- 邊界：本輪未執行真實 GPU／GGUF latency、完整漫畫 holdout、clean-machine、Store submission、WACK；CodeRabbit review 尚待本輪實際結果，不預先宣稱通過。
## 2026-08-14：CodeRabbit shared runtime startup disposition

- 初輪 committed review：base 581d8a6、2 findings。日期 major 指出 decisions.md 的 2026-08-14 證據像是 future-dated；查證本機 clock 為 2026-08-14T05:34:37+08:00，commit 5f03146 為 2026-08-14T05:31:48+08:00，測試也在同一日期完成，因此是 false positive，不改寫歷史日期。
- 啟動鎖定 finding 有效：原本 LocalVisionRuntimeLease.start() 持有 coordinator lock 直到模型暖身完成，暖身中的 stop 無法及時取消。修正為 lock 外呼叫 runtime.start()，entry 以 starting 計數保護，完成時重新確認 entry／lease；acquire 在 startup 中 fail-closed，release 與 stop 保留清理責任。新增 blocked-start regression，修正提交 107ba10。
- 驗證：受影響 runtime／worker／vision suite 263 passed, 1 skipped in 7.30s；compileall 與 git diff --check Pass。post-fix CodeRabbit 實際回報 rate_limit、waitTime=4 minutes，沒有 findings result，不能宣稱 review 通過。
- 邊界：未執行真實 GPU／GGUF latency、完整漫畫 holdout、clean-machine、Store submission、WACK；CodeRabbit 需待免費額度恢復後再複審。
## 2026-08-14：CH-T34/T35 locked GPU Vision paired benchmark

- 資料 gate：使用 records/private/.private_vision_owner_review_locked.json 的 4 個主人已確認案例；immutable preflight 與 benchmark lock 均通過。pending packet 另有 4 案但 owner_expected 填寫數為 0，因此沒有拿它做 ground truth 或 promotion evidence。
- 條件固定：baseline=text、candidate=vision；manifest、model/runtime hash、prompt、sampling、context、GPU mode 與 target 相同；各條件 20 records（4 cases × 5 repeats），先跑 baseline_then_candidate，再跑 candidate_then_baseline。
- 結果：兩種順序的 quality 都是 baseline 0.239488、candidate 0.271208；4/4 個案無 regression，coverage/nonempty=1.0、GPU/local provider、residual=0，quality promotion gate=true。兩種順序合併平均 total：baseline 958.142ms、candidate 6220.130ms，candidate 約 6.492x 慢；candidate decode 平均約 4502.604ms，確認瓶頸在 Vision generation/decode 而不是 OCR。
- 決策：Vision-first 目前是品質候選，但速度 gate 不成立，不改 production default、不宣稱全域最佳。下一個受控實驗只研究 decode/request budget 或真正多請求排程，必須沿用同一 quality／case-regression gate；不再用 OCR threshold 猜測解法。
- 實機收尾：GPU 回到 0%／約 1812 MiB used，沒有 CloudHime 或 llama-server residual。未完成 Store/WACK，亦未把 pending owner annotation 自動填入。
## 2026-08-14：CodeRabbit release-during-start finding disposition

- 初輪 review：base 5f03146，CodeRabbit 回報 2 findings。release race major 與測試 coverage minor 均有效：release 在 startup 阻塞時會讓 entry 留在 zero leases／stopped 狀態，後續 acquire 永久收到 shared_runtime_stopped。
- TDD：新增 release-during-blocked-start regression，RED 為 1 failed；修正 _finish_start 在 zero leases 且 startup 結束時即使 entry 已 stopped 也必須移除，保留 release 的立即 cancellation；lifecycle targeted 3 passed，受影響 QT_QPA_PLATFORM=offscreen suite 264 passed、1 skipped in 6.07s；compileall／git diff --check Pass；commit 5dce3fe。
- Post-fix review：以 d29e5bc 為 base 的 CodeRabbit review_completed、findings=0，涵蓋 local_runtime_coordinator.py 與 tests/test_local_vision_runtime.py 及 repository contract context。
- 邊界：未由此 review 宣稱 GPU quality／latency、Store、WACK 或 clean-machine；Vision paired benchmark 的速度 promotion 仍維持拒絕。

## 2026-08-14：Full CI test-group rerun after runtime hardening

- 驗證環境：QT_QPA_PLATFORM=offscreen、Windows 管理員程序、每組獨立 basetemp；沒有刪除既有 .tmp／.pytest 目錄。
- 結果：core 404 passed, 2 skipped in 113.19s；OCR 242 passed in 16.62s；runtime 153 passed, 2 skipped in 6.79s；UI 54 passed in 2.34s；benchmarks 179 passed in 7.74s；compileall 與 git diff --check 通過。
- 判定：本輪 CI 宣告的五組測試均通過；先前並行普通權限執行的 WinError 5 是 pytest basetemp 清理環境問題，不能拿來當產品失敗或成功證據。這次結果仍不涵蓋新的 GPU 品質／延遲 benchmark、GGUF 下載、clean-machine、Store submission 或 WACK。

## 2026-08-14：CI clean-machine environment probe hardening

- Root cause：packaging/test_clean_machine.ps1 已經用 ProcessStartInfo.EnvironmentVariables.Clear() 建立隔離環境，但 GitHub MSIX fixture 只是編譯 sleeper；它沒有讀取環境，因此無法證明 Python／Conda／Ollama 等污染變數沒有洩漏。另發現 workflow 傳入 -LaunchWaitSeconds 3，與 script 的 [ValidateRange(5, 120)] 不相容，會在啟動前直接失敗。
- 修正：將 .github/workflows/ci.yml fixture 改為自驗證 C# probe，檢查 SystemRoot、WINDIR、精確 PATH，並拒絕 PYTHONHOME、PYTHONPATH、VIRTUAL_ENV、CONDA_PREFIX、OLLAMA_HOST；將 clean-machine smoke 呼叫改為 5 秒，保留 MSIX install smoke 原本的 3 秒。tests/test_msix_packaging.py 改為鎖定 probe contract。
- TDD／驗證：新增 regression 先 RED（1 failed）；修正後 targeted 1 passed。中途 YAML indentation 造成 workflow parser RED（1 failed），修正後 CI fixture 原始 block 實際編譯、啟動與清理通過，父程序刻意帶入污染環境仍通過；release／MSIX／CI inventory 45 passed in 58.27s；compileall／git diff --check 通過。
- 邊界：這是 CI fixture／契約 hardening，不等於真實乾淨 Windows、MSIX install／uninstall、GPU onboarding、Store submission 或 WACK 已完成；CH-T64 維持 In Progress。

## 2026-08-14：Japanese OCR worker full-candidate arbitration regression

- 缺口：japanese_ocr_rescue.py 的 pure decision 已保護「不得用可信前綴改善換掉完整候選」，但 worker integration 原本沒有同型案例；未來接線改動可能繞過這個準確度護欄。
- 修正：tests/test_japanese_ocr_worker_integration.py 新增 fake runtime full Meiki candidate 情境，讓 VLM 輸出更接近 trusted prefix、卻丟掉候選尾段；OCRWorker.rescue_japanese_text() 必須保留完整 baseline。
- 驗證：worker integration 5 passed in 1.00s；Japanese rescue/runtime/OCR mode matrix 102 passed in 7.04s；未執行 GPU、完整漫畫 holdout、LGPL 授權審查、Store 或 WACK，因此 CH-T35 維持 In Progress。

## 2026-08-14：CodeRabbit clean-machine probe review disposition

- 初輪 review：base e946a4e，review_completed，3 findings。兩個 major 指稱 2026-08-14 證據像是未來日期；本機日期、命令執行與 commit 時間均為 2026-08-14，查證為 false positive，不改寫 decisions 或 smoke ledger。唯一有效 finding 是 tests/test_msix_packaging.py 未鎖定 SystemRoot／WINDIR／PATH rejection branches。
- 修正：新增三個 exact guard assertions，commit dd32d77。targeted probe／YAML tests 2 passed；受影響 CI inventory／release／MSIX suite 45 passed in 57.81s。
- 複審：以 1363397 為 base 的 CodeRabbit review_completed，僅剩 1 個同型日期 false positive；沒有新的 production 或 test finding。這不代表 GPU、Store、WACK 或真實 clean-machine onboarding 完成。

## 2026-08-14：Public manga holdout evaluator contract and fresh baseline

- 修正前缺口：公開漫畫 manifest 雖已具備 6 張圖片與 visible text anchors，但 evaluator contract 沒有 regression 保證它仍能完整載入、逐頁配對比較，且 report 不應回傳 OCR 原文。
- 修正：新增 `test_public_manga_holdout_manifest_is_evaluator_ready`，固定檢查 6 cases／anchors、6 頁 page regression comparison，以及 records 不含 `joined_text`；使用 fake benchmark 驗證 schema/privacy，不把 fake 結果當品質證據。
- 實際一次 Windows OCR baseline/grid paired run：`python manga_repeated_run_evaluator.py benchmarks\\manga_cover_cases.json --backend windows --repeats 1 --base-threshold 100 --output artifacts\\manga-cover-public-20260814.json`；兩條件皆 6/6 nonempty、0/6 anchor recall。baseline 平均 `2362.352 ms`、p95 `6594.127 ms`；grid 平均 `13768.007 ms`、p95 `57605.568 ms`，grid accepted `2/6`，但沒有 anchor 改善。
- 判定：這個 checkpoint 只證明公開 holdout evaluator 可重跑且目前 OCR baseline 的真實表現可觀測；不代表漫畫辨識已達標。grid recovery 維持 opt-in，不能作為線上速度解法；CH-T43 仍在 Review，下一個真正的品質工作是以 owner-confirmed ground truth 做 vision/crop A/B，並同時守住 paired regression 與 latency budget。
- 邊界：本次使用 Windows OCR、`multimodal_enabled=false`，未執行 GPU／GGUF／local vision、15-page private holdout、Store、WACK 或 clean-machine VM onboarding；沒有把這次結果宣稱為全域最佳。

## 2026-08-14：Fullscreen Vision fallback closes the OCR-empty path

- Root cause：`OCRWorker.run_scan_once()` 原本只讓 Region Vision 在 OCR backend 缺失或 OCR 失敗時接管；全螢幕多模態即使已啟用，只要 OCR 沒有任何 item 就會在 bounded rescue 後走 `handle_empty()`，整張畫面不會送進 Vision。這讓 OCR 的「找不到字」直接變成 Vision 不可用。
- 修正：新增 `is_fullscreen_vision_fallback`。全螢幕多模態允許 OCR optional；沒有 backend 時跳過 OCR 與 rescue，OCR 結果為空時以既有 screenshot Vision provider 讀整張圖，成功後輸出單一整頁矩形並記錄 `translation_fullscreen_vision_completed`。OCR 有結果時仍保留原本 bbox hint／局部翻譯流程。
- TDD：先加入無 OCR backend 的 fullscreen regression，現況 RED `1 failed`；修正後 targeted `1 passed in 1.22s`；`tests/test_cloudhime_workers.py` `81 passed in 1.33s`；OCR／local multimodal／scan pipeline／integration 集合 `127 passed, 1 skipped in 5.90s`；compileall／git diff --check Pass。
- 邊界：這是可重現的 product-path correctness 修正，不等於 Vision 已在所有圖片上準確或快速。尚未以真實 GPU/GGUF 做此新 fallback 的 quality／latency promotion，也未宣稱 public manga anchor 或 Store/WACK gate 完成。
