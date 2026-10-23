# Qt 函式庫與原始碼

CloudHime 使用動態連結的 Qt／PySide6／Shiboken 6.10.1，其 LGPLv3 權利與產品的 Apache 2.0 授權分別適用。可為了修改這些函式庫、除錯修改內容而進行 LGPL 所允許的逆向工程；CloudHime 的產品條款不得限制這項權利。

來源版本：

- Qt Core／Gui／Network／OpenGL／Widgets：[qtbase 6.10.1](https://download.qt.io/official_releases/qt/6.10/6.10.1/submodules/qtbase-everywhere-src-6.10.1.tar.xz)
- Qt Svg：[qtsvg 6.10.1](https://download.qt.io/official_releases/qt/6.10/6.10.1/submodules/qtsvg-everywhere-src-6.10.1.tar.xz)
- 其他影像格式外掛：[qtimageformats 6.10.1](https://download.qt.io/official_releases/qt/6.10/6.10.1/submodules/qtimageformats-everywhere-src-6.10.1.tar.xz)
- PySide6／Shiboken：[pyside-setup 6.10.1](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.1-src/pyside-setup-everywhere-src-6.10.1.tar.xz)

原始碼模式可在自有目錄建立 CPython 3.10 x64 環境，依專案的固定版本安裝依賴，再以相同 ABI 的自編 PySide6／Shiboken wheel 取代該環境中的版本，執行 `CloudHime.py`。Qt 本身須使用相容的 MSVC x64 工具鏈；建置步驟請參考該版原始碼內的 README 與 Qt for Python 建置文件。

對 PyInstaller 的可寫入 onedir 副本，函式庫位於 `_internal/PySide6`（Qt DLL、PySide extension 與外掛）及 `_internal/shiboken6`。關閉副本的程式後，以同版本、相容 ABI 的自編產物取代相應檔案，連同需要的外掛、Python extension 與第三方依賴一起更新，再從這份副本啟動 `CloudHime.exe`。修改後的函式庫不需維持原始 SHA-256；CloudHime 的 Qt 載入流程沒有產品自訂的 DLL 雜湊白名單。

不要直接修改 WindowsApps 中的受管理安裝。本文件中的副本替換方式尚待以最終 Store 安裝套件實測，包含複製權限、啟動、設定隔離與修改函式庫的載入。上述 upstream 下載連結及來源模式不是這項實測的替代證據，也不表示商店條款或原始碼供應義務已經驗收。最終發行仍須提供可持續取得的對應原始碼與可實際使用的修改版本執行途徑。
