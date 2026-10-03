# Python 支援邊界

CloudHime 正式建置與發行的驗證基準是 Windows x64／CPython 3.10。正式依賴鎖、建置工具與 Windows CI 依此版本驗證；本輪調查沒有更新產品依賴或提升 Python 版本。

Python 3.13.11／PySide6 6.10.1 尚未建立完整相容性。歷史單程序 pytest 曾在 `pyside6.abi3.dll` 發生 `0xc0000005`，另有合併測試在建立 OCRWorker 時原生崩潰。現有證據不足以確定是 ABI、Qt 物件生命週期或測試順序造成，因此不以換版本或重構執行緒猜測修復。

2026-10-03 在獨立 AppData／Temp、Qt offscreen、移除常見憑證環境變數的子程序中，OCR backend 執行緒安全測試 `5 passed in 2.24s`。這是聚焦測試結果，不代表整套 3.13 通過，也未重現或修復歷史崩潰。此隔離方式不是網路沙箱。

如果未來要支援 Python 3.13，應在可丟棄、無憑證且網路受限的 Windows 環境重現混跑問題，保存 dump、最後 pytest node、故障模組及載入的 Python／Qt DLL 版本；取得可重現的最小案例後，才決定生命週期修復或獨立的 3.13 依賴鎖。本任務以「明確且有證據的支援邊界」完成調查，沒有宣稱原生崩潰已修復。

歷史來源：[E9 收尾](../reviews/2026-09-24-e9-closeout.md)、[互動驗收](../reviews/2026-10-02-interaction-delight.md)。本輪原始結果保存在 `output/task-completion-20261003/python-compat/t116-python-compat-3o9rv5zq/result.json` 及同目錄 pytest.log。
