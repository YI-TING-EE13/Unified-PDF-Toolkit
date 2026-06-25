# Document OCR Fake Backend Smoke Test Plan

## Purpose and Scope

This plan defines how a future production Document OCR UI should be smoke-tested
with fake or mocked backends before it is exposed to normal users.

This is a documentation/test-planning milestone only. It does not implement a
production Document OCR UI, expose the current dev-only shell, run real
Unlimited-OCR inference, download models, start servers, call local endpoints,
add AI runtime dependencies, upload files, add screen OCR, add background OCR,
or add Batch Queue integration.

## Relationship to the Dev-Only Document OCR Shell

The current `[Dev] Document OCR Shell` is gated by
`PDF_TOOLKIT_ENABLE_DEV_TOOLS=1` and exercises the reusable advanced OCR
workflow helpers with the deterministic fake Unlimited-OCR backend.

Future production UI smoke tests should reuse the same safety expectations:

- Fake backend only for CI and normal smoke tests.
- Mocked local endpoint transport only when endpoint UI state is tested.
- No live endpoint calls.
- No model downloads.
- No torch, transformers, SGLang, CUDA, GPU, internet, or server requirement.
- No OCR text, image bytes/base64 payloads, or document content in logs or
  workflow reports by default.

## Production UI Assumptions

The future production Document OCR UI is assumed to include:

- Explicit file selection for PDFs and common image files.
- Explicit output folder selection.
- TXT and Markdown output options.
- A backend selection control limited to reviewed choices.
- A visible consent/readiness path before advanced OCR execution.
- Progress and cancel controls.
- User-safe error display.
- A hide or rollback switch if production exposure needs to be disabled.

These assumptions are not an implementation commitment. They are smoke-test
targets for a later reviewed production milestone.

## Fake Backend Test Matrix

| Case | Input | Output | Consent | Expected result |
| --- | --- | --- | --- | --- |
| Single image TXT | PNG, one page | TXT | valid | One TXT output with deterministic fake text |
| Single image Markdown | JPEG, one page | Markdown | valid | One Markdown output with page heading |
| Single image both formats | PNG, one page | TXT + Markdown | valid | Two local outputs |
| Single PDF TXT | PDF, one page | TXT | valid | One TXT output with one page section |
| Multi-page PDF Markdown | PDF, multiple pages | Markdown | valid | One Markdown output preserving page order |
| Unsupported input | Non-PDF/image file | TXT | valid | User-safe unsupported input error |
| Empty selection | No input file | TXT | valid | User-safe validation warning before execution |
| Missing output folder | Valid input | TXT | valid | User-safe validation warning before execution |
| No output format selected | Valid input | none | valid | User-safe validation warning before execution |

## Consent Gate Scenarios

Smoke tests must cover:

- Valid consent allows fake-backend execution.
- Missing consent blocks execution before OCR starts.
- Declined/cancelled consent remains invalid.
- Stale consent from provider/model id mismatch blocks execution.
- Stale consent from consent text version mismatch blocks execution.

Expected behavior:

- The user is told how to review or save consent.
- No output files are written when consent blocks execution.
- No backend call is made when consent is missing or stale.

## Readiness and Diagnostics Scenarios

Smoke tests should verify the UI can guide users to readiness information
without requiring optional AI dependencies.

Required scenarios:

- torch absent: shown as optional/not installed, not an app failure.
- transformers absent: shown as optional/not installed, not an app failure.
- CUDA/GPU absent: shown as unavailable only for backends that would need it.
- Model cache absent: shown as informational or warning, not a default install
  failure.
- Endpoint URL invalid: shown as invalid only when endpoint mode is being
  reviewed.
- Endpoint reachability: not checked unless explicitly requested, and no
  document content is sent.

## TXT and Markdown Output Scenarios

Output smoke tests must verify:

- Output files are written only to the selected output folder.
- TXT output is readable and deterministic.
- Markdown output preserves page boundaries.
- TXT + Markdown selection writes both files.
- Output conflict behavior follows the repo's shared policy where practical.
- Workflow summaries list output paths without embedding OCR text.
- OCR text is not written to logs or diagnostic reports by default.

## Progress and Cancel Scenarios

Required smoke cases:

- Progress starts from idle and reaches completion for a successful fake run.
- Current file/page status is visible where practical.
- Cancel before first file leaves no OCR output.
- Cancel during a multi-file or multi-page fake run stops future work where
  practical.
- Cancellation message is user-safe and does not include OCR text or image
  content.
- Partial output behavior is visible if any output was already written.

## User-Safe Error Scenarios

Smoke tests should exercise user-facing error mapping for:

- Consent required.
- Unsupported input type.
- Output folder missing or not writable.
- Backend unavailable.
- Mocked endpoint timeout.
- Mocked endpoint connection failure.
- Mocked endpoint malformed response.
- Unexpected workflow failure.

Error checks:

- Error text is actionable.
- Error text does not include OCR text.
- Error text does not include image bytes/base64.
- Error text does not include document content.
- Source paths are not included unless already visible in the selected input
  list and necessary for file-level status.

## Rollback and Hide-Feature Scenarios

Before production exposure, smoke testing must verify:

- The production Document OCR entry point can be hidden by a documented switch
  or rollback procedure.
- Hiding the production entry point does not affect existing Tesseract-backed
  PDF to Word OCR Text behavior.
- The dev-only shell remains available only when
  `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`.
- Hiding advanced OCR does not delete consent records or user outputs.

## Non-CI and No-Real-Model Status

Fake-backend smoke tests may run in CI if they require no display or can use
headless-safe UI test hooks.

These are not CI requirements:

- GPU tests.
- CUDA tests.
- Model download tests.
- Real Unlimited-OCR inference tests.
- Live local endpoint server tests.
- SGLang/vLLM/Transformers runtime tests.

Any future real backend smoke test must be documented separately and gated by
manual acceptance instructions.

## Pass Criteria

The fake-backend smoke suite is acceptable when:

- Existing Tesseract OCR behavior is unchanged.
- The production Document OCR entry point remains hidden until intentionally
  enabled.
- Fake backend flows cover file selection, consent, readiness, output,
  progress/cancel, and error display.
- No real model, live endpoint, GPU, internet, or optional AI runtime is
  required.
- No OCR content or image payloads appear in logs/reports by default.
- `README (1).md` or other unrelated local files are not modified or staged.
