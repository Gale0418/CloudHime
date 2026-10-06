# 2026-10-07 發行補件與環境完整性

CH-T55 維持 Review；CH-T56 尚未完成。主人已驗收來源版的 Luna、Gemma、設定與精簡介面；來源驗收不能替代最終 EXE／MSIX、WACK 或 Microsoft Store 認證。

## 授權與來源補件

- 只保留產品用到的 Qt 模組；spec 移除 VirtualKeyboard、QML／Quick、PDF，preflight 拒絕未審核 Qt6 DLL。原始 GPL／Commercial VirtualKeyboard 候選已撤換。
- 固定副本 manifest 現有 595 筆原文／告知，全部有來源與 SHA-256。來源副本是對應來源樹的告知集合，不表示每個來源元件皆被連結。
- Qtbase、QtSvg、Qtimageformats、PySide6 6.10.1 的官方來源封存與 Metalink SHA 已核對；可重建／替換說明隨包保存。可寫入 onedir DLL 替換探針已有歷史證據，但新候選及 Store 安裝後副本仍須獨立驗證。
- CUDA DLL 與 NVIDIA 官方 redistributable 檔案逐一核對：cuBLAS 12.4.5.8、cudart 12.4.127；最初比對 cudart 12.4.99 不符的證據保留。另保存 LLVM／OpenMP、CPython、Mesa／LLVM-MESA 告知。
- primp 1.3.1 的 normal Windows dependency tree 共 203 項，對應 365 份授權副本。這是標籤來源／Cargo.lock 的 normal graph，不能用它聲稱 wheel 精確編譯 attestation 或 build-only graph 全數覆蓋。
- wheel 原始授權 evidence 與補充原文分開保留；缺原始 wheel license 檔不會因補件存在而從 collector 報告消失。法律合規未作專業認定。

詳見 `packaging/third-party-licenses/QT-LIBRARY-REPLACEMENT.md`、`NATIVE-RUNTIME-NOTICES.md`、`sources.json`。

## 實際建置阻礙與修正

既有 Python 3.10 同時安裝 `opencv-python` 與 `opencv-python-headless`；metadata 宣稱 headless 4.13.0.92，但 cv2 實際為 5.0.0，pyd 與 headless RECORD 不符。第一個 EXE 雖通過有限啟動／OCR 探針，仍標記 superseded，不可發布。未修改主人的全域 Python。

改以專用 venv 按 production hash lock 實際安裝 40 套件。舊 pip 22 的 report 缺少新格式授權 metadata，升級隔離環境內 pip 後重新安裝並保存原始與新報告。第二次編譯在 PNG 圖示轉換階段因缺 Pillow 停下；原始 build log 與失敗收據保留。Pillow 12.3.0 已依 PyPI 官方 Windows CPython 3.10 wheel SHA 加入 build-only lock，產品 spec 排除 PIL。

建置入口新增指定隔離 Python 的變數與實際環境完整性 guard；完整性失敗時保留原 dist。guard 已綁定鎖定 wheel 的 URL／SHA、可信 RECORD 與實際 payload，拒絕未雜湊原始檔、被改寫的 installed RECORD 及多個 OpenCV variants；僅允許 pip 產生的 metadata／entry point、明確的 cache 和 script shebang 改寫。13 fixtures 與實際 40 套件／6,188 原始檔通過。

## 本輪已取得驗證

- Qt／授權／provenance／MSIX 聚焦回歸：89 passed、2 skipped、17 deselected；不包含舊工作目錄大型 dist preflight。
- 新來源原文資源：25 passed。
- provenance 路徑末尾分隔符修正：14 passed、2 skipped；3 種實際輸入路徑皆得到正確 sibling 位置。
- 安裝 RECORD 初版 guard 6 案通過；乾淨環境 40 套件／6,302 hashed files 核對通過，舊全域環境實際拒絕。
- Pillow 建置契約：25 passed、1 deselected。
- CodeRabbit 原 Qt／授權封裝 8 檔及後續 3 檔各 0 issues。初版 guard 呼叫單檔 0 issues；後續完整 guard 3 檔有 3 major issues，均查證修正；第一次複審遇 rate limit，依服務指定等候窗恢復後，7 檔修正版複審 0 issues。

具體 JUnit、原始工具輸出與失敗收據位於 `output/release-20261007/` 與 `output/release-20261007-clean/`。

## 發行界線與下一步

固定新候選的 source manifest／EXE／原生 bytes，重跑 import、Windows OCR、GUI、CPU Vision、full payload 檢查及安裝／更新／完整 WACK，再按已核准的 24k 評論額度進行正式三席與獨立 arbiter。

正式評論、Store 條款核對、上傳／認證與實際 Store 更新仍未完成。先前 WACK required PASS 不能代替這次新候選。原 Store 0.1.1.0、主人設定及原始 `assets/cloudhime_logo_v2.png` 保留。

## 新候選已完成的有限驗收

- 乾淨環境重建成功：source manifest SHA `225e37b9ec779edaa1ca11fd8e3ad84582f68458d597bc26adbd205db76e9299`，EXE SHA `7cffe59b3e2aa62eb8ea839a50553f43a85ca417fa3922636a23af83f517c888`。
- frozen cv2.pyd SHA `90034927004e4a4ebf29360480d609c8a8d2ca07c93f8b89dff86399e8534b2a` 與 hash-lock 安裝檔一致；無 ffmpeg500 額外檔，PIL 未打包。
- light preflight、frozen import、Windows OCR 2 行、GUI 20 秒均通過；新可寫入 onedir 副本的 altered Qt6Core 載入探針 exit 0，原 DLL 未改動。不作自編 Qt／Store 安裝後替換聲稱。
- full 模型／CPU Vision、MSIX、安裝／更新／WACK 仍在後續流程，未外推已通過。
- Partner Center 此次只讀核對：Submission 3、私人群組、TWD249，未排公開日期／銷售定價；四個實際 listing locale 是 zh-tw、ja-jp、en-us、zh-hant-tw，兩個繁中標籤。zh-tw 與 ja-jp 的 additional license terms 空白，日文 keyword 有 AI 說明文字。四語系 terms 草稿在 docs/store-third-party-terms.json，尚未保存至外部服務。
