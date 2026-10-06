# 第三方授權封裝資料

這裡保存固定上游版本的完整授權文字，`sources.json` 記錄原始網址、大小及 SHA-256。
文字保持原始 bytes，沒有翻譯或改寫授權。

這些副本是封裝補件，不是完整的合規驗收。Qt/PySide6 還需對照實際模組、
第三方告知、對應原始碼與替換／重新連結後執行方式；CUDA 等元件也需核對其實際版本與條款。
生產依賴的 wheel 授權檔應依 installation report 收集，不能靠開發環境的套件列表推測。

本資料夾不修改專案根目錄的 Apache 2.0 `LICENSE`，也不將第三方元件改授權為 Apache 2.0。

## 收集生產 wheel 的授權證據

使用安裝正式依賴的同一個 Python 執行，指定該環境的 production pip report
與全新輸出目錄（已存在的非空目錄會被拒絕，避免混入舊版本）：

```powershell
py -3.10-64 packaging/collect_dependency_licenses.py --report build/provenance/production-pip-report.json --output build/dependency-licenses --supplement-dir packaging/third-party-licenses
```

工具只核對 report 中的套件，不收開發依賴；保存原始授權 bytes、SHA-256、版本與
report 的雜湊。Exit 0 表示 wheel 檔案收集未發現缺漏；exit 1 表示已保存報告，
但存在缺件或 Qt 僅帶 Commercial LicenseRef；exit 2 表示輸入、版本或路徑不合格。
三種結果都不表示完整法律合規；manifest 明列 `legalCompliance: not_assessed`。
補充文字不會自動將套件缺件標成已解決，必須依版本及實際元件另行核對。

目前 spec 自動包含本資料夾的固定補件。wheel 收集結果仍須隨正式候選另行組成與
驗證，不能只看到本資料夾被打包，就宣稱所有第三方告知齊全。
