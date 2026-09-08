# CH-T114 Windows 程序命令列實機稽核

- 2026-09-09 執行 `python -u output/t114_live_audit.py`，exit 0。
- 使用真實 LocalVisionRuntime、既有模型與 llama-server；以 psutil 查詢該子程序的實際 Windows command line，僅輸出布林值，不輸出 secret 或完整 argv。
- `live_argv_secret_absent=true`、`api_key_flag_absent=true`。
- Runtime `state=ready`、`state_secret_absent=true`。
- finally 呼叫 runtime.stop() 後 `key_cleared=true`、`owned_process_cleared=true`。
- 本切片補足先前缺失的 live process listing 證據；既有錯誤／log redaction 測試證據仍需於正式收尾一併核對，尚未變更 lifecycle。

## 正式收尾核對

- 2026-09-09：`python -m pytest tests/test_local_vision_runtime.py tests/test_runtime_hardening.py -q -p no:cacheprovider`，exit 0，`73 passed in 0.90s`。
- 核對 `runtime_security.py` 與 `local_vision_runtime.py`：每次啟動 key 僅傳入子程序環境；移除繼承的 LLAMA override；stdout 丟棄，stderr 在保留／狀態呈現之前使用該次 launch key 遮蔽，超長行整行丟棄。
- 回歸涵蓋 spawn 錯誤在 stop 清除可變 key 後仍遮蔽、正常錯誤保留與 bounded stderr、CPU retry、停止回收與 key 清除；搭配上方真實程序稽核，支持此任務驗收。
- 限制：環境傳遞不防範具權限的本機 debugger 讀取程序環境／記憶體；不宣稱線上 Provider、Store 或整體發行完成。
