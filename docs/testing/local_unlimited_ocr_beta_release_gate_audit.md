# Local Unlimited-OCR Beta Release-Gate Audit

Date: 2026-07-01

This audit records the controlled-beta readiness boundary for Experimental
Local Unlimited-OCR. It does not approve public production support.

## Claims Audit

Reviewed areas:

- `README.md`
- `CHANGELOG.md`
- `docs/runtime/`
- `docs/releases/experimental_local_unlimited_ocr_beta_notes.md`
- `docs/security/unlimited_ocr_trust_remote_code_policy.md`
- `docs/advanced_ocr_maintainer_guide.md`
- `docs/testing/unlimited_ocr_autonomous_validation_report.md`
- `src/tools/document_ocr/tool.py`
- `src/tools/settings/tool.py`
- `src/ui/advanced_ocr_consent.py`
- `src/utils/diagnostics.py`

Required wording is present or was tightened:

- Experimental Local Unlimited-OCR is experimental.
- It runs locally on the user's own computer.
- The project does not provide hosted OCR or a project-operated OCR server.
- Files, rendered pages, and OCR text are not uploaded by this feature.
- Tesseract remains the default OCR backend.
- The experimental backend is gated by
  `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.
- The runtime/model are user-managed and optional.
- The preferred beta runtime is a uv-managed optional OCR runtime such as
  `.venv-ocr-runtime`.
- Optional runtime setup is helper-assisted through `uv` only and remains
  separate from default dependencies.
- Real local Unlimited-OCR remains disabled by default and not
  production-ready.

## Release Gates

Controlled beta may proceed only while all of these remain true:

- [x] Default dependencies do not include torch, transformers, SGLang, CUDA, or
      model files.
- [x] Unlimited-OCR is not the default backend.
- [x] Tesseract remains the default Document OCR backend.
- [x] Experimental Local Unlimited-OCR remains hidden without the environment
      gate.
- [x] Saved consent is required before experimental backend execution.
- [x] `worker_process` is the GUI-exposed real local model runtime mode.
- [x] Worker timeout and cancel terminate the worker process.
- [x] Worker stderr is not surfaced to users by default.
- [x] OCR text and image bytes are not printed by the smoke tools.
- [x] Synthetic validation inputs and generated OCR outputs are not committed.
- [x] Beta release-candidate notes state no hosted OCR, no upload, not default,
      and experimental gate required.
- [x] `trust_remote_code` and model revision risks are documented before any
      broader release.

## Not Approved For Public Release

The following are still not approved:

- Removing the experimental environment gate.
- Making Unlimited-OCR the default OCR backend.
- Bundling torch, transformers, CUDA, models, or model caches in default
  packages or installers.
- Adding automatic model download.
- Adding hosted OCR, cloud upload, screen OCR, background OCR, or Batch Queue AI
  OCR.
- Claiming production-ready Unlimited-OCR support.

## Remaining Public-Release Blockers

- Broader GPU/runtime matrix testing beyond the current RTX 3060 CUDA setup.
- Accessibility review of the Document OCR UI.
- Wider maintainer review of the optional OCR runtime setup helper across more
  Windows machines.
- Enforced allowlist/checksum policy for reviewed model revisions.
- More user-facing troubleshooting examples from beta feedback.
