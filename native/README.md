# CloudHime Rust 核心：第一階段（Rust 1.98.1）

這是既有 Windows/PySide6 程式的**可選運算核心**，不是整個 CloudHime 已改寫成 Rust。
目前交付 Rust 原始碼、C ABI、Python 轉接器與差異測試；本輪環境沒有 Rust 工具鏈，
因此不能宣稱 Rust 已編譯、Windows 已驗收或原生效能已提升。預設仍走 NumPy。

## 邊界

- 純 Rust/std、零第三方 crate；固定 `rust-toolchain.toml` 與 Cargo MSRV `1.98.1`。
- 單次走訪 uint8 像素，回傳「變動像素數」及「絕對差值總和」，不做 OCR 跳幀決策。
- C ABI 限制 16 MiB、檢查長度乘法溢位、空指標及輸出對齊；panic 不跨 ABI。
- Python 以有界的 immutable bytes 保護外部讀取，不把可能有可寫別名的 NumPy view 借給 Rust。
- 動態庫僅從本專案 `native/target/release/` 的固定檔名載入；不搜尋 PATH/CWD、不接受任意 DLL 路徑。
- 不自動下載、編譯或在啟動時安裝依賴。錯誤／不相容／缺少動態庫回到既有 NumPy 路徑。
- 不加入 WebView、Tauri、PyO3 或新的 Windows 截圖、全域熱鍵與模型執行環境。

## 已安裝工具鏈後，執行本地閘門

```powershell
python native/verify.py
```

此命令用 `rustup run 1.98.1`，沒有 `--install`；依序確認精確 compiler version、
`cargo fmt --check`、Rust tests、Clippy、release build，最後執行真正動態庫對 NumPy 的差異測試。
Cargo 的 test/build/clippy 使用 `--locked --offline`。工具鏈或組件缺少就明確失敗，不暗中補裝。
第一次取得 Rust/rustfmt/clippy 是獨立的使用者環境設定，不包含在這個離線閘門中。

通過後可在**新的來源碼程序**明確啟用：

```powershell
$env:CLOUDHIME_NATIVE_FRAME_METRICS = '1'
python CloudHime.py
```

取消環境變數即可回到 NumPy。載入結果會在程序內快取；補建或更換動態庫後要重啟。
目前沒有把 native binary 納入 frozen/MSIX 供應鏈；不要把 source opt-in 當成 release 支援。

## 便宜的 Python 回歸

```powershell
python -m pytest -q tests/test_frame_gate.py tests/test_frame_metrics.py tests/test_native_frame_metrics.py
```

未啟用 native 時，實際 Rust 動態庫測試會顯示 skipped；這**不是** Rust 通過證據。
模擬 C ABI 的測試只能驗證 Python 邊界，不替代 Rust 編譯或原生 ABI 實測。

## 原則

NumPy 原本就使用原生程式碼，尋樣本經 FFI 不一定比較快。Rust 是否成為預設，必須比較
同一輸入、兩種執行順序、正確性及記憶體／延遲；不能用語言名稱宣布加速。
本輪預設路徑的改善是 uint8 使用 int16 差值及移除重複 sample copy，不是 Rust 實測成果。
