# Changelog

## Unreleased

- Added architecture-only scaffolding for optional future advanced local AI OCR, including an ADR, OCR backend abstractions, consent validation structures, a fake Unlimited-OCR test backend, and safe optional-readiness diagnostics.
- Added Settings / Recent consent management for future optional advanced local AI OCR without enabling real model inference.
- Added a localhost-only OCR endpoint backend scaffold for future user-managed OCR servers without adding model inference or AI runtime dependencies.
- Added developer-only Document OCR shell wiring, hidden behind `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`, for local fake-backend UI/workflow testing without real model inference.
- Added a manual, non-CI GPU acceptance test plan and run template for future advanced OCR backend validation.
- Added advanced OCR privacy/security review and pre-integration checklist documentation for future real backend work.
- Added optional advanced OCR runtime packaging/install docs and a local endpoint contract for future user-managed runtimes.
- Added an advanced OCR maintainer guide summarizing architecture status, boundaries, and recommended next work.
- Hardened the local OCR endpoint scaffold with stricter mock-only response validation and sanitized transport errors.
- Added mock-only advanced OCR workflow helpers for backend selection, consent gating, output writing, and user-safe error mapping.
- Added a hidden dev-only Document OCR UI shell for fake-backend workflow testing without real model inference or live endpoint calls.
- Added Document OCR production UI design review and readiness checklist documentation.
- Added Document OCR fake-backend smoke test plan and manual run template documentation.
- Pivoted advanced OCR direction toward a user-owned local model runtime and added a safe local model backend scaffold without real inference or AI runtime dependencies.
- Added safe local model OCR runtime settings, readiness diagnostics, and worker-process contract documentation without enabling real inference.
- Added a developer/test-only fake local model worker subprocess prototype to exercise IPC, timeout, cancellation, and response validation without real OCR inference.
- Added an optional experimental local Unlimited-OCR backend path with lazy torch/transformers imports, local model path validation, and an opt-in manual validation script.
- Added an experimental killable Unlimited-OCR worker-process runtime path with timeout handling, JSON response validation, temp page cleanup, and manual validation support.
- Hardened the experimental Unlimited-OCR worker-process runtime with a default single-worker guard, safe busy errors, structured worker error parsing, and stderr redaction.
- Added a user-facing Document OCR tool with Tesseract as the default backend and a gated experimental Local Unlimited-OCR worker option.
- Hardened Document OCR experimental local-model failure messages for missing model path, missing worker Python, busy worker, timeout, unsupported input, and GPU/CUDA readiness failures.
- Hardened the Document OCR experimental GUI smoke path with a manual Tkinter smoke runner and worker-process cancellation propagation.
- Added controlled-beta setup, smoke checklist, release-gate audit, diagnostics readiness hardening, and beta-check smoke automation for Experimental Local Unlimited-OCR.
- Added a uv-only optional runtime setup helper, beta release-candidate notes, and `trust_remote_code` / model revision policy documentation for Experimental Local Unlimited-OCR.
- Added warning-only Experimental Local Unlimited-OCR model revision safety checks for model id allowlist status, revision pinning, local metadata presence, and custom-code consent diagnostics.
- Improved Document OCR and Settings beta copy, and added final beta tester plus packaging dry-run checklists for Experimental Local Unlimited-OCR.
- Added beta release draft and tag readiness review documentation for a future human-approved Experimental Local Unlimited-OCR beta tag.
- Completed a clean local beta artifact build/inspection pass and documented Windows ZIP, installer, wheel, and source distribution boundaries.
- Aligned beta release metadata toward `v0.6.0-beta.1`, using Python package version `0.6.0b1` and installer display version `0.6.0-beta.1`.

## 0.5.0 - 2026-06-19

- Added a tag-driven GitHub Release workflow for Python packages, Windows ZIP bundles, and optional installer artifacts.
- Added an Inno Setup installer script and release checklist.
- Added Batch Queue for mixed sequential jobs across compression, PDF-to-image, and PDF-to-Word workflows.
- Added Diagnostics view for dependency, Tkinter, Tesseract, settings, and output-folder checks.
- Added OCR cleanup options: None, Grayscale, Auto Contrast, and Threshold.
- Added user-facing error suggestions for common OCR, permission, page-range, encrypted-PDF, and missing-file failures.
- Expanded unit tests for batch queue, diagnostics, OCR cleanup, and error suggestions.

## 0.4.0 - 2026-06-18

- Added drag-and-drop support for shared file lists when native Tk drag-and-drop is available.
- Added Cancel buttons and cancellation handling for long-running workflows.
- Added completion reports for long workflows, now emitted as TXT, CSV, and JSON.
- Added shared output conflict behavior: rename, overwrite, or skip.
- Added Settings / Recent view for output behavior and recent inputs, outputs, and reports.
- Added PDF to Word OCR Text mode with configurable Tesseract language and render DPI.
- Added GitHub Actions CI and Windows PyInstaller smoke packaging.
- Added MIT LICENSE and aligned package metadata with Python 3.10+.
- Expanded workflow tests, including Page Manager edit operations and mocked OCR conversion.

## 0.3.0

- Added PDF to Word conversion with Preserve Layout, Text Only, and Page Images modes.
- Added PDF to Word preview and preflight checks.
- Added merged PDF preview and optional post-merge compression.
- Enlarged the application workspace for preview-heavy workflows.
- Added progress feedback for long-running tools.
