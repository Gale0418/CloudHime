# T64：本地入口與完整離線包

## 範圍與決策

主人核准以 Gemma **3 4B IT Q4_K_M** 完整離線包為主要發行方式，並確認模型散布條款；線上 Gemma 4 不變，不進行本地模型升級。模型加 projector 共 3,341,008,960 bytes，不進 Git。

乾淨 Sandbox 的使用者截圖重現：預設雲端模型無 Key 時，Gemma AI 按鈕切回 Google Translate；Local Gemma 狀態卡也誤顯示雲端 Key 提示。修正為獨立的本地選用按鈕與本地 health 評估，不取消雲端 Key 檢查。

## 多角度檢查與研究

- UX：本地入口不應藏在 Online Gemma 內；保留單一 canonical 模型選擇狀態，明確按鈕先選本地再啟用。
- Runtime：沿用 `resolve_preferred_vision_assets` 的隨包路徑與 SHA 驗證，不增加另一套 runtime／模型快取，不把隨包權重再複製到 AppData。
- 發行：新增 flavor-aware 模型 gate；full 要求兩個固定資產與條款，light 拒絕模型，auto 仍驗證任何出現的模型。ZIP 改用標準庫 ZIP64，無新依賴。
- 更新：模型未變可保留同一路徑；尚未實作／宣稱自動差異更新器。
- 授權：依 https://ai.google.dev/gemma/terms 第 3 節，附官方條款／政策副本、Notice、使用限制。官方 HTML 快照取得日 2026-09-20；不得用 CloudHime 原始碼授權取代模型條款。
- 標準庫依據：https://docs.python.org/3/library/zipfile.html ，並透過 GitHub connector 查閱 python/cpython 的 `Doc/library/zipfile.rst`；採用 ZIP64 公開介面，不複製實作。
- 平台限制：https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases ：單一 release asset 必須小於 2 GiB。主人進一步明確指定 GitHub 不上傳模型、只有 MSIX 內含模型，因此 ZIP 固定 light，封裝後才 stage full dist；不做分卷。

這是 Codex 的跨領域檢查，不是虛構專家投票。Antigravity 唯讀委派 request `ch-offline-ui-review-20260920` 因 RPC session unavailable、agy 缺少模型 effort 而失敗，未取得審查結果，未宣稱 Gemini 驗證。

## 本輪證據

- `python -m pytest tests/test_release_archive.py tests/test_translation_panel_advanced.py tests/test_provider_health.py -q -p no:cacheprovider`：41 passed（5.50 秒）；QT_QPA_PLATFORM=offscreen。
- 新增測試涵蓋雲端預設／無 Key 切本地、本地狀態隔離、缺模型、損壞 hash、缺條款、多餘模型、ZIP64 與既有 ZIP 不覆寫。
- CodeRabbit 首輪 1 minor：README 舊模型排除說明與新政策矛盾，已修；首輪未覆蓋新模組，因此另以 9 檔隔離目錄補查。
- 隔離審查初次因 base branch 未指定而失敗；明確 `--base main` 後完成 9 檔審查，0 issues。本小時已呼叫三次，不再追加。後續 MSIX CreateUpload 的 ZIP64 連帶修正未受此輪 CodeRabbit 覆蓋，另以單元／builder 契約與 PowerShell parser 驗證。
- 發行／MSIX／資產／UI／health 回歸：122 passed in 534.82s；後續依主人要求調整 ZIP-before-model-stage 順序，需再驗證受影響建置契約。
- ZIP-before-stage 變更後：release packaging／archive 31 passed；加入 MSIX upload ZIP64 後同組 32 passed；settings theme/layout 7 passed；MSIX builder 2 passed，PowerShell parser PASS。
- 新 frozen build 完成（PyInstaller exit 0）：EXE SHA256 `531f7e845abaf40b120777d1110f511b1f15f9e3a0a58bfd0c0c4151847d891b`；light preflight 362 files／1,517,736,550 bytes／0 model files，frozen import smoke PASS（PID 15280，helper 已結束）。這不是實際模型推論。
- CI 新測試 inventory 已補登；CI inventory＋release packaging 35 passed。第三方總說明更新為 full MSIX／light ZIP 的政策；封裝目錄的外部 notice 同步更新，EXE 不變。初版 light ZIP 因包含舊說明而不作最終產物，另建立 `CloudHime-light-final.zip`。
- 完整模型 stage exit 0；full preflight PASS：368 files／4,859,025,587 bytes／2 model files；兩個模型 exact size／SHA 與條款副本一致性通過。最終 light ZIP `python -m zipfile -t` PASS，無模型內容由 light staging／flavor gate 控制。
- GitHub real-release-build 明確設定 `CLOUDHIME_RELEASE_FLAVOR: light`，preflight 也要求 light；CI／builder 11 passed。GitHub connector combined status 回傳空清單，不能當成最新 CI PASS；本機 gh 尚未登入，但 git push 已成功，不為此讀取外部金鑰。
- 首版完整 MSIX：MakeAppx exit 0，3,916,963,934 bytes／371 entries；兩個模型 entry 大小正確，EXE SHA 與 notices 一致。工具提示 GGUF 超過建議的 2GB（warning，不是失敗）。建置 staging 已清理。未簽章，未宣稱安裝／WACK／Store PASS。
- 首輪斷網 Sandbox：fresh profile、外部 Python／pip／Conda／Ollama 均不存在；EXE SHA 正確，但 functional smoke exit 2，故 FAIL。程式沒有進入正常 UI；結果保留於 `.tmp/sandbox-offline-20260920/output`。
- 後續 TDD 重現驗收程式在唯讀 installation root 建立暫存 manifest 會 PermissionError；改用隔離 TEMP，release functional／orchestrator 14 passed。此修正需新 frozen EXE 重測；不能把首輪 VM 失敗直接改判 PASS，也不能把首版 MSIX 當成已包含後續修正。
- T64 保持 Review；沒有建立 completion passport 或宣稱 Store／WACK 完成。
- R2 斷網 Sandbox 仍 exit 2；進一步確認 `CLOUDHIME_PACKAGED_SMOKE_GPU_LAYERS=0` 被正整數 parser 拒絕。僅 GPU 層數改為允許 0，負數仍拒絕；timeout 的 0 仍拒絕。functional／orchestrator 14 passed（1.38 秒）。此為驗收入口修正，不代表模型已完成推論。
- R3 EXE 重建 exit 0，SHA256 `5816ccd65e0eec0481ab7b2625393b0c8bd2d970502d305b394e5dc93f4ba68f`；未改變的 runtime／模型／資料使用硬連結組裝，EXE 獨立複製，舊版產物未覆寫。最新純 CPU／斷網驗收進行中，證據目錄 `.tmp/sandbox-offline-20260920-r3/output`。R1 MSIX 不含 R2／R3 的 smoke 修正，不當作最新最終包。
- R3 最終 FAIL，且 helper 回報 descendant cleanup 失敗；依重試閘門停止封裝、轉低成本原生啟動診斷。R3 ZIP 可讀、362 entries／0 model files／EXE SHA 正確，但不是功能驗收通過的發行包。
- 全新斷網 VM 直接執行同一份 `llama-server --version`：system-only PATH exit `-1073741515`（0xC0000135）；加入包內 `_internal/PySide6` 與 `_internal` 後 exit 0，回報 9968／1d1d9a9ed。證據 `.tmp/sandbox-dll-diagnostic/output/diagnosis.json`，無模型推論、無 API Key。PE imports 確認 MSVCP140 相依，而該 DLL 在 PySide6 子目錄。
- 修正 owned helper 的 child PATH，在 Windows frozen 環境加入包內 PySide6 CRT 路徑，不修改父程序／系統 PATH，也不使用 process-wide SetDllDirectory。參考 PyInstaller 官方 https://pyinstaller.org/en/latest/common-issues-and-pitfalls.html 。runtime hardening／local runtime／functional smoke 86 passed（1.95 秒）；尚待 R4 frozen 驗證，未宣稱完整離線翻譯通過。
- R4 fresh offline Sandbox 功能 PASS（2026-09-20T14:08:31Z）：EXE SHA256 `005daa941e6aa6df54ebd28798a6317af2e3c763c5fdff2674d58266d95cb891`；CPU／technical_coverage／image_count=1／request_success_images=1／successful_images=1。無外部 Python／pip／Conda／Ollama、初始 CloudHime profile 不存在、網路與 vGPU 關閉、沒有注入遠端 API Key。helper 正常退出並清理測試程序，另啟正常 UI PID 820 等主人操作確認。本地 frozen import smoke 也 PASS（PID 15192）。
- 這是隨包資產的圖片功能呼叫與程序清理通過，不是翻譯品質 ground truth、正常 UI provider 切換、MSIX 安裝／簽章或 Store certification 通過；T64 仍 Review。R4 ZIP／MSIX 封裝中，尚未發布。
- 22:11 後補做 CodeRabbit：獨立 7 檔、相對 `f70c5d8` baseline、無模型／圖片／條款快照；review completed，0 issues，覆蓋 CI、MSIX builder、兩個 functional smoke 模組、runtime_security 與對應測試。未在同一小時超過三次呼叫。
- R4 light ZIP `python -m zipfile -t` PASS；362 entries、842,854,923 bytes，無 models／GGUF，內含 EXE SHA 與 R4 相同。先前 R1～R3 產物保留供追溯，但不是本輪最終版。
- R4 MakeAppx exit 0、`Package creation succeeded`；本機 unsigned development MSIX `dist/offline-20260920-r4/msix/CloudHime-0.1.0.0-x64.msix` 為 3,916,964,264 bytes。沒有上傳 GitHub／Store，沒有聲稱簽章或安裝 gate 通過。
- MSIX 內容後驗證 PASS：371 entries；直接解壓串流核對 EXE、Gemma GGUF、projector SHA256 全部一致，四份模型條款／Notice 與來源 byte-for-byte 一致；無 AppxSignature.p7x。MSIX staging 硬連結目錄的清理命令被執行政策拒絕，未繞過，故 staging 也保留；EXE、完整 dist、ZIP、MSIX 與失敗診斷證據均保留。
- 主人 22:16 截圖顯示 `gldriverquery.exe` 缺 `SDL2.dll` 的 Windows 彈窗；CloudHime 主視窗在其後方。本輪 dist 內無該 EXE／SDL2，程式碼無直接呼叫，尚未取得 guest 程序路徑／父程序，因此不可把彈窗歸因為 CloudHime，也不能宣稱正常 UI gate 通過。已詢問彈窗是否跟隨 CloudHime 自動啟動或另開 Steam／遊戲；不要求下載不明 DLL，不關閉主人的沙箱。
