# Independent strict-review handoff

Status: **NOT RUN / BLOCKED**. This file is a prompt, not a review result.

## User's exact instruction

> 不要相信前一輪結論，重新從正確性、回歸風險、效能、安全、資源使用與可維護性挑毛病，按照Mission Center標出待修優先度，只有真的沒有值得修的 P2 以上問題才准通過。

## Required evidence

Start from the current GitHub `main`, not the partial reconstruction or prior summary. Read `MissionCenter/tasks.md` as the lifecycle source and inspect the actual diff from `8d5a7753dfdb06dd818ba789f946af1294aeabe0`. Challenge all claims in the checkpoint.

For each issue provide priority, exact file/line, reproducible input or test, user impact, and a concrete repair. Separate confirmed defects from unexecuted platform gates. Include the still-open Qt overflow, dictionary replacement escapes, actual llama-server authentication and native ABI checks.

Use a real independent reviewer. The implementation agent's self-checks and deterministic pytest results are not an independent opinion. Do not return PASS while known worthwhile P0/P1/P2 work or required verification remains open. After a repair, rerun affected tests and independently review the new revision.

Do not run CI, create branches, invoke live paid APIs without approval, leak credentials, or change ground truth to improve scores. Preserve the existing Windows interface. Keep Rust pinned to 1.98.1 and native execution opt-in until real compiled validation passes.
