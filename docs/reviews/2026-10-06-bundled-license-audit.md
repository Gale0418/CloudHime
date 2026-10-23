# 2026-10-06 第三方授權封裝補件

主人已定案 NT$249 買斷、公開可購買起前 30 天 NT$199；免費完整原始碼與付費官方包透明互導，Apache 2.0 保留署名與合法再散布權利。TWD249 與四語商店文案已保存並重新讀取確認；私人受眾保留，未排首發日期、未上傳新包或送認證。

## 可重現缺漏

297d822 署名候選的 MakeAppx 封裝技術檢查通過，MSIX SHA-256 為 `5883ed35acc68d5d0367ccd9d729b23657504a5e12c9942078384e6012f9cfb6`。之後盤點發現 Qt／PySide6 GNU 授權副本及多數生產 wheel 告知沒有隨包保存；另以 `publication-eligibility.json` 將這份候選標成 superseded。沒有把技術封裝成功改寫成授權驗收通過。

production report 精確核對 40 個已安裝套件。8 個 wheel 缺 upstream license 檔（primp 與 7 個 WinRT 套件）；4 個 Qt/PySide 套件只附 Commercial LicenseRef，不能用它推定持有商業 Qt 授權。報告為 `output/release-20261006/dependency-license-audit-final/license-manifest.json`，exit 1 符合缺件結果。manifest 記錄 report SHA-256、套件版本、授權 bytes／SHA，並明列 `legalCompliance: not_assessed`；不因補充文字存在便自動消除缺件。

保存 Qt v6.10.1 的 LGPLv3／GPLv3、llama commit 1d1d9a9ed 的 MIT、primp v1.3.1 與 PyWinRT v3.2.1 的 MIT 原文；來源與 digest 在 `packaging/third-party-licenses/sources.json`。spec 帶入固定副本，preflight 拒絕漏檔或 digest 不符。`.gitattributes` 避免 Windows 換行轉換破壞驗證。根 LICENSE 與產品 Python／EXE 未改。

## 驗證界線

- 新收集器 11 案通過，涵蓋版本、bytes、非典型 License-File 名稱、缺件、traversal、輸出目錄、重疊及重複套件。
- 打包相關廣泛檢查 66 passed／1 failed／4 deselected。唯一失敗是工作目錄舊 `dist/CloudHime` 缺 NOTICE；原始 JUnit 保留，未刪除舊產物或改測試掩蓋。
- 本輪授權副本漏檔／竄改及 bytes 契約針對驗證 4 passed／41 deselected。CI YAML 解析通過；pytest 有既有 cache 權限 warning。
- 新 MSIX 安裝、更新、WACK 與完整人工 GUI 尚未執行。先前候選 smoke 不代替這些驗證。

## 尚待完成

核對實際 Qt 模組與第三方告知、對應原始碼供應、替換／重新連結及執行方式；實際包含 Qt6VirtualKeyboard.dll／qtvirtualkeyboardplugin.dll，不能籠統認定所有 Qt 元件都是 LGPL。還須確認 CUDA DLL 的精確來源版本及適用文件、LLVM／CPython／native embedded dependencies 的告知覆蓋，再將所有 wheel 文件與補件組成最終候選。完成前不重封大型 MSIX、不送認證，不宣稱完整法律合規。

主要來源：[Qt LGPL 義務](https://www.qt.io/development/open-source-lgpl-obligations)、[Qt for Python 6.10 授權](https://doc.qt.io/qtforpython-6.10/commercial/index.html)、[Qt 6.10.1 原始碼](https://download.qt.io/official_releases/qt/6.10/6.10.1/)、[PySide 6.10.1 原始碼](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.1-src/)。商店另有 [Microsoft 標準應用程式條款](https://www.microsoft.com/en-us/servicesagreement)，其另附條款機制須與實際 listing 一起核對，不能以這條研究結果代替正式發行驗收。

CodeRabbit分兩個明確範圍：原先4份封裝檔0issues；新增收集器與2份測試補審3檔、1minor（Windows大小寫目的路徑碰撞）。先以新增案例重現未拒絕碰撞，再補拒絕guard，12個收集器案與2個固定副本案共14passed，JUnit保留；沒有冒稱修正後再審0issues。服務預算用於一次範圍補審，未追加第三次。
