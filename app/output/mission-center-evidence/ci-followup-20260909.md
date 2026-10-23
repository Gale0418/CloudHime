# CI 後續修正（2026-09-09）

## Summary
5a35d77 已上傳，但 CI 34258500520 的 core／benchmarks／MSIX contract 失敗；本輪修正兩個根因，未放寬產品驗收。

## Completed
- manga_cover_cases.json 本機 CRLF 符合既有 SHA256，index 卻為 LF。依既有 -text 規則重新加入原始 bytes，沒有改寫 lock；忽略行尾差異後 diff 為空。
- 新增 Git index bytes regression，避免本機檔案通過掩蓋 checkout 不一致。
- 保留嚴格環境隔離探針；MSIX 改用獨立的十秒存活探針，不再要求 AUMID 環境具有隔離用 PATH／AppData。
- 依主人最新指示，10 張既有 tracked example PNG 只移除 Git 追蹤，本機逐一確認保留；既有 example/ ignore 已生效。沒有重寫 Git 歷史，歷史圖片仍存在。

## Unfinished
- 修正 commit 的 GitHub CI 尚待 push 後驗證。
- 既有完整 holdout／乾淨 Windows／正式 Store／31b image API 阻塞不變，任務狀態未冒進。

## Risks
- 結構探針不是 CloudHime 真實功能測試；既有 fresh WACK 證據不等於本輪遠端 CI。
- 排除實驗圖片後，需要實際 corpus 的測試依既有外部 corpus policy 處理，不能把 skip 當品質證據。

## Smoke tests
- python -m pytest tests/test_benchmark_lock.py tests/test_frame_gate_benchmark.py -q：17 passed。
- python -m pytest tests/test_msix_packaging.py -q：33 passed，269.90s；包含實際 C# 編譯、三秒存活及程序回收。
- git diff --check 通過；manga dataset --ignore-space-at-eol diff 空。
- CodeRabbit review --agent --uncommitted：exit 0，review_completed，5 檔，0 issues。只有本次 CI YAML、C#、兩個測試檔與 JSON；沒有圖片或大型建置產物。前輪2次加本次1次，未超過每小時3次限制，未使用credits。

## Retro
本地 byte hash 與 Git blob 必須同時驗證；不同啟動契約應使用不同探針，不能將隔離環境假設套入 Windows AUMID activation。
