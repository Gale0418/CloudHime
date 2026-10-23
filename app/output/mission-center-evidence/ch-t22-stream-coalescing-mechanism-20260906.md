# CH-T22 stream coalescing mechanism audit

- Date: 2026-09-06
- Scope: measure the bounded render-callback contract without changing production settings or invoking a provider.
- Method: offscreen `Controller` harness; send 120 same-generation stream chunks before the 40 ms flush, then repeat with 120 chunks distributed across 3 item indexes.
- Result: same item `0` callbacks before flush and `1` after flush (99.1667% callback reduction versus one callback per chunk); 3-item case `1` pending callback before flush and `4` total after flush (3 rendered callbacks for 120 chunks, 97.5% reduction versus one callback per chunk).
- Boundary: this proves bounded coalescing and latest-value retention at the controller boundary. It is not a wall-clock user-latency benchmark and does not justify T22 Done by itself.
