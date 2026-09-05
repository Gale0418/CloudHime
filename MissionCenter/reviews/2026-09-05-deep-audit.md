# CloudHime deep-audit checkpoint — 2026-09-05

Base: `8d5a7753dfdb06dd818ba789f946af1294aeabe0`.

**Whole-project gate: BLOCKED. This is a tested repair checkpoint, not a full-repository or independent-review approval.**

`tasks.md` remains the lifecycle source. The IDs below map findings to existing work; no task was marked Done by this audit. The progress summary now exposes the missing gates instead of reporting no blockers. Mission Center CLI and Impeccable detector were not executed.

## Reproduced issues and repairs

| Review ID | Priority | Mission Center mapping | Repair / evidence |
|---|---|---|---|
| AUD-01 | P1 | CH-T114 | Move per-launch llama-server credential from argv to `LLAMA_API_KEY` in a child-only environment; remove inherited `LLAMA_*` configuration. Keep OS/CUDA variables. Invalid keys fail before spawn. No persistent key file or parent-environment mutation. |
| AUD-02 | P2 | CH-T112 | Cached ready state now checks the owned process is still alive. Preserve idempotency for a starting snapshot and for a live ready process. |
| AUD-03 | P2 | CH-T112 | Terminate/wait/kill now includes a bounded post-kill wait. The stderr reader owns pipe closure, avoiding a shutdown thread waiting on a blocked TextIO read lock. |
| AUD-04 | P2 | CH-T112 | Bound stderr reads and retained lines; redact with the launch-local key before retention. Omit oversized lines rather than retain possible credential fragments. Do not expose raw spawn exception messages. |
| AUD-05 | P2 | CH-T112 | Remove generic `vram`, successful `ggml_cuda_init`, and generic model-load text from CUDA fallback triggers. A bad GGUF with a normal CUDA startup line no longer causes a pointless second CPU load; explicit CUDA failures retain one retry. |
| AUD-06 | P1 | CH-T109 / CH-T112 | Reject explicit incomplete/failed/refused Responses output before accepting a compact `output_text`. Validate item metadata as well as top-level metadata. Compact legacy adapters without status remain compatible; this is not proof of remote completion. |
| AUD-07 | P2 | CH-T109 | No-schema structured output now uses JSON-object mode, not an invalid unconstrained strict schema. Reject NaN, Infinity and overflowing JSON exponents. Preserve caller-provided schemas. |
| AUD-08 | P2 | CH-T109 | All five translation entry points inherit the configured target language unless explicitly overridden. Previously a provider configured for English still defaulted to zh-TW. Five failing default-language cases now pass; explicit overrides remain covered. |
| AUD-09 | P2 | CH-T112 | Normalize non-finite/oversized timeout and diagnostic numbers. Close HTTPError streams; check cancellation between response chunks. Diagnostics reject nontext/oversized values without arbitrary coercion. Trace history stays bounded for finite iterables while the normal immutable-tuple path is retained. |
| AUD-10 | P2 | CH-T112 | Reject inconsistent native frame totals, including zero changed pixels with positive delta. Fall back to NumPy; do not change `skip_ocr=False` or enable native code by default. |
| AUD-11 | P2 | CH-T112 | Own an asset HTTP response before parsing status or invoking progress callbacks, so exceptions close the stream. Existing size/hash verification and atomic promotion remain unchanged. |

Architecture changes are intentionally narrow: process-boundary helpers live in `runtime_security.py`; Responses-envelope/JSON validation lives in `responses_contract.py`. No GUI framework rewrite, model replacement, benchmark-ground-truth edit, or quality-for-speed trade was made.

## Verification

The final selected command and file fingerprints are recorded in `2026-09-05-deep-audit-evidence.json`.

- Selected local pytest suite: **234 passed, 2 skipped**. These are not the full five inventory groups.
- Existing runtime regressions plus new runtime-policy tests: **72 passed, 1 skipped** on an earlier targeted run, using the real reconstructed asset validator and coordinator.
- Responses hardening: **43 passed** after fixing five default-language failures. These tests inject unrelated OCR/format helpers and do not measure translation quality.
- Baseline counterexamples: diagnostic/native boundary tests **17 failed / 2 passed**; runtime policy **10 failed / 2 passed**; Responses boundary tests **23 failed / 6 passed**; asset lifetime tests **2 failed / 4 passed**. New regressions and compatibility checks were then added before the final combined run.
- Python syntax compilation and `git diff --check`: pass.
- Skips: the compiled Rust-library differential test and the Windows-only process-creation flag test.
- Rust verification script: BLOCKED because rustup / Rust 1.98.1 are absent; it did not download anything. The native path remains opt-in.
- No real model, GPU, API, Windows UI, frozen executable, MSIX, or Store validation was run. No performance-speedup percentage is claimed.

The existing runtime tests were retained with three assertions updated for the intentional credential/reaping contract changes. The existing OpenAI multimodal fixture was corrected to make `output` an array; a new negative test explicitly rejects the formerly malformed envelope. No failing production path was hidden by deleting tests or loosening benchmark gates.

## Scope and open P2-or-higher work

Fully inspected here: local runtime and ownership coordinator, asset validation/download paths, OpenAI provider, scan diagnostics, frame metrics/native adapter and Rust-core boundary, the related regressions and selected workflow/corpus contracts. Sources reconstructed locally were checked against their GitHub blob hashes before editing.

The local workspace is a selected-source reconstruction, **not a complete checkout**. `translation_settings_panel.py` and `translation_helpers.py` received partial source review. The large `cloudhime_ui.py` / `cloudhime_workers.py`, other providers and their full interactions have **not** received a complete line-by-line or Windows execution review in this pass. Do not extrapolate the selected test result into global correctness.

| Priority | Mapping | Remaining work |
|---|---|---|
| P1 | CH-T112 | Independent strict review has not run. CodeRabbit is absent and its installer failed DNS resolution; there is no independent agent dispatcher in this environment. Self-checks are not approval. |
| P1 | CH-T112 / CH-T114 | Run real pinned llama-server on Windows and verify authenticated requests, startup/cancellation/teardown and log redaction with the shipped binary. Child environment is not secret from a privileged debugger; do not claim otherwise. |
| P1 | CH-T112 | Rust 1.98.1 build, rustfmt, Clippy and compiled-library differential tests remain unexecuted. Do not ship or auto-enable an unverified native binary. |
| P2 | CH-T115 | Existing Windows narrow-column overflow (previous runner: 423px content in a 337px viewport) remains unresolved. Verify a real Qt layout and DPI matrix before claiming a UI fix. |
| P2 | CH-T112 follow-up | `translation_helpers.apply_dictionary_pre_translation` passes dictionary values directly as `re.sub` replacement strings. Literal backslashes such as `C:\Users\example` can be interpreted as regex escapes and raise. Equivalent underlying-call reproduction is recorded in evidence; this helper has not been patched. Add a real helper regression and use a callable replacement, then check overlapping dictionary terms. |
| P1 | CH-T115 / release | Background-asset redistribution permission remains unconfirmed. |
| P1 | CH-T112 | Complete the still-unreviewed large GUI/worker and remaining-provider paths, then rerun the full local inventory in the Windows environment. |

## Upstream references

Reviewed as implementation guidance, not copied as third-party source:

- llama.cpp server credential contract: https://github.com/ggml-org/llama.cpp/blob/6a1a922d269908a29cbd4b49c27e6a8e7fd10fae/tools/server/README.md (`LLAMA_API_KEY`).
- OpenAI structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs (strict schemas, JSON mode, incomplete/refusal handling).
- OpenAI response metadata: https://developers.openai.com/api/reference/cli/resources/responses/methods/retrieve.
- Qt scroll sizing: https://doc.qt.io/qt-6/qscrollarea.html. This is design guidance, not evidence that the Windows overflow is repaired.
- Mission Center: https://github.com/Gale0418/Codex-Mission-Center.
- Impeccable: https://github.com/pbakaus/impeccable. Preserve the incumbent native visual world; do not replace it during a correctness fix.

Publication policy: one atomic commit on `main`, no new branch, `[skip ci]`. After updating the ref, read back the commit/tree and verify the Actions run count separately. Publication is not independent-review approval.
