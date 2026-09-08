# CH-T22 text-only stream render A/B audit

- Date: 2026-09-06
- Scope: compare the current bounded stream-render path with the legacy direct-per-chunk render behavior using the real `OverlayWindow.update_translation_stream` offscreen path.
- Method: same-generation text payload, one item, 120 chunks, identical geometry, 5 repeats; current path coalesces before one flush, legacy path calls the overlay directly for every chunk.
- Measurements: current coalesced render times `18.068, 1.950, 1.314, 1.271, 2.356 ms` (median `1.950 ms`); legacy direct render times `130.232, 170.613, 184.982, 184.565, 212.015 ms` (median `184.565 ms`); median render-path speedup `94.66x`.
- Render count: current `1` actual render callback for 120 chunks; legacy `120` callbacks.
- Result: the bounded text-only redraw path materially reduces render work and preserves the latest chunk; full UI smoke remains green at `45 passed`.
- Boundary: this is a controlled UI render-path A/B, not a provider, network, OCR, or full scan wall-clock latency claim.
