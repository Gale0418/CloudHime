# 2026-10-03 管理員與乾淨 Windows 驗收

使用者授權管理員工作後，開發輕量 MSIX 的 WACK／安裝驗收及完整 frozen dist 的全新 Windows Sandbox 驗收已通過。產品來源維持 `bff0c4f005b9ebec7d3e00450f4ddfd00b31d53d`，沒有修改程式、重建套件或重跑既有 238 個案例。CH-T55／CH-T117 保留 Review。

## 開發 MSIX：實際管理員 gate

Windows UAC 核准後，以 Windows PowerShell 5.1 執行已審閱腳本，腳本 SHA-256 `1f64a65ef691bc4d92943b734e3b2c1be77fb44f47592c7a0fb389dbdafed9df`。只簽 development light MSIX 副本，使用一天有效、不可匯出私鑰的開發憑證；原始 unsigned 包 hash `257544ceb06639904ce7e7c31cbd2d668586b02616984421b4c8fcf57fd6a64e`。

- SignTool sign／verify 成功，WACK 真實 XML 的唯一 `OVERALL_RESULT=PASS`；不是只憑程序 exit code。
- 實際安裝 `CloudHime_0.1.2.0_x64__4nvnqyjwyamgj`、從 WindowsApps 啟動並存活 3 秒，接著移除。
- 原始 result.json 記錄 wack／install／cleanup passed、error null、cleanupErrors 空；此 cleanup 僅涵蓋腳本檢查項。
- 獨立查核：開發套件、精確 thumbprint 的 CurrentUser My 憑證、LocalMachine TrustedPeople 信任及公開 CER 均不存在。既有 `WindSheep.CloudHime` 0.1.1.0／Ok／Store 保留。

原始日誌與簽章副本在 `output/task-completion-20261003/admin-dev-0795fa96f39045bba3ad5b4a594645e0/`；未改寫執行過的腳本或轉碼原始混合編碼 transcript。可恢復證據在 `output/mission-center-evidence/admin-cloud-20261003/`，WACK XML SHA-256 `d1730aa6312a17e8ba28c010fe3057c0f8f08776f2a937fca2e7253b73c5fe0c`。

清理腳本沒有 `-DeleteKey`，所以「憑證物件移除」不能證明 backing private key 移除。追加查核只從本輪簽章讀取公鑰比對，不匯出私鑰；managed key lookup 的 `NTE_BAD_KEYSET` 使結果不完整。後續唯讀提升權限啟動被 Windows 回報 UAC 取消；使用者表示沒有看到提示。私鑰殘留保持 **未確認**，沒有執行刪除，也未廣泛清理使用者 key store。未執行的查核不列 Pass。

## 完整 frozen dist：全新 Windows Sandbox

實際啟動時間 2026-10-03 22:01（Asia/Taipei）；guest probe 22:02 至 22:08。Windows 10 Enterprise 10.0.19041 x64，初始 CloudHime profile 不存在。python／python3／py／pip／conda／ollama 的 Get-Command 結果皆空；這不代表整個檔案系統沒有任何相關二進位。

來源是既有完整 dist（375 檔、4,896,174,164 bytes），含 Gemma GGUF、mmproj 與條款。複製到 guest 後核對 EXE SHA-256 `810d9751d379afb77baa474fd6099bc59e698641f0e0a34b2f741439719e0028`，與原發行候選相同。

1. 真實 frozen import functional smoke 通過，PID 2256。
2. 真實 CPU managed runtime／隨包模型／projector，以隨包 `bg_light.png` 測 1 image／1 case，成功請求 1／1，technical_coverage passed，PID 3960。
3. GUI launch liveness 20 秒通過，PID 5060；測試 helper 清理自己的程序樹。

網路、vGPU、剪貼簿及音訊／攝影機／印表機停用；8192 MB RAM。來源與 probe input 唯讀映射，專屬 output 可寫，未映射主機設定或憑證。guest helper 副本加上 TEMP 子目錄與 reparse 安全檢查；產品腳本未改動。已依 PID、名稱、父程序與啟動時間核對，關閉本輪 launcher 9836 與 client 55796，未停止共享 VM 服務或其他程序。

證據在 `output/mission-center-evidence/sandbox-cloud-20261003/`：

| 證據 | SHA-256 |
|---|---|
| `output/result.json` | `b32e7d1cbd0d1307cc901e941b6826e8f08df6395b204e854a944eee884b6756` |
| `output/vision-smoke.json` | `ca5fc228a7ea6669128857f6aa0280d18d5fdfb99a4aad5d8713a154d47d0851` |

`launch.json` 保留 WSB／probe／helper 的執行前 hashes；`cleanup.json` 保留本輪 launcher/client 清理結果。

## 尚未完成

這次證明 development light MSIX 的 WACK／主機安裝，以及完整 frozen dist 的乾淨 Windows CPU 技術覆蓋。未驗證完整 Store MSIX 的 WACK／guest 安裝、GPU、翻譯準確度提升、新 Store 認證或 0.1.2.0 更新。正式差異評議預算仍待核准，Partner Center 未建立更新、未上傳、未提交。T55／T56／E7／E8 依賴維持，不以局部 gate 關閉發行任務。
