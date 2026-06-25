# Advanced OCR Next Goals

This roadmap keeps future optional advanced local OCR work reviewable without
depending on chat history. Tesseract remains the default OCR path until a future
milestone explicitly changes user-facing options.

## 1. Consent UI and Settings Persistence

- Status: Implemented for future-use consent management; no real AI OCR execution enabled.
- Goal: Add a clear UI flow that records explicit consent for advanced local AI OCR.
- Non-goals: No model inference, model download, or backend execution.
- Acceptance criteria: Consent stores provider, model id, text version, all required acknowledgements, and timestamp through existing settings helpers.
- Required tests: Unit tests for load/save, invalid consent, and consent invalidation when provider/model/version changes.
- Safety/privacy checks: Consent text must disclose model download risk, custom code risk, GPU/VRAM use, and temporary rendered page images.

## 2. Local Endpoint Client Backend

- Status: Implemented as a localhost-only backend scaffold; no real server is started or required.
- Goal: Add an optional backend client for future Unlimited-OCR-compatible local servers.
- Non-goals: No hosted endpoint defaults, remote upload support, server launcher, or public-network target.
- Acceptance criteria: Endpoint defaults to `127.0.0.1` only and refuses non-loopback addresses unless a later reviewed policy allows them.
- Required tests: Mock HTTP/client tests with no live network dependency.
- Safety/privacy checks: No user files, rendered pages, or OCR text leave localhost by default.

## 3. Developer-Only Fake AI OCR UI Wiring

- Status: Implemented behind `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`; uses only the fake backend and writes local TXT/Markdown test outputs.
- Goal: Wire the fake backend into controlled UI tests so flows can be exercised without a model.
- Non-goals: No user-facing claim that AI OCR is supported.
- Acceptance criteria: Fake backend is clearly labeled and unavailable in release-facing normal workflows unless explicitly enabled for development.
- Required tests: GUI or unit tests proving fake output is deterministic and local.
- Safety/privacy checks: Fake backend must not import torch/transformers, download models, or upload data.

## 4. GPU Acceptance Test Plan

- Status: Implemented as manual, non-CI documentation in `docs/testing/advanced_ocr_gpu_acceptance.md` with a reusable run template.
- Goal: Document manual GPU validation for any future real backend.
- Non-goals: No GPU requirement in CI.
- Acceptance criteria: Test plan covers dependency checks, memory expectations, cancellation, failure messages, and small sample PDFs.
- Required tests: Manual checklist plus optional skipped tests gated behind explicit environment variables.
- Safety/privacy checks: Manual tests must use local sample files and avoid logs containing OCR text or rendered page images.

## 5. In-Process Transformers Prototype

- Goal: Prototype real in-process inference only after security review.
- Non-goals: No default dependency changes, automatic model download, or startup-time heavy imports.
- Acceptance criteria: Prototype is opt-in, consent-gated, lazy-loaded, and isolated from default workflows.
- Required tests: Import-boundary tests, mocked model tests, and manual GPU smoke tests outside CI.
- Safety/privacy checks: Review `trust_remote_code` implications before enabling real model execution.

## 6. AI OCR / Document OCR Sidebar Tool

- Goal: Add an optional tool for document OCR outputs such as text, Markdown, or JSON.
- Non-goals: No screen OCR, global hotkeys, automatic capture, or background OCR.
- Acceptance criteria: The tool requires explicit file selection, visible output paths, and clear experimental labeling.
- Required tests: UI-level smoke tests with fake backend and unit tests for output writing.
- Safety/privacy checks: Reports must not include OCR text or rendered page images by default.

## 7. Batch Queue Integration

- Goal: Add optional batch jobs for approved advanced OCR backends.
- Non-goals: No default AI batch jobs before consent and readiness gates exist.
- Acceptance criteria: Batch jobs reuse the same consent, readiness, cancellation, and report policies as interactive workflows.
- Required tests: Mock/fake backend batch tests with cancellation and failure reporting.
- Safety/privacy checks: Batch reports must avoid OCR text and rendered page images by default.

## 8. Packaging and Install Documentation

- Status: Implemented as optional runtime documentation in `docs/runtime/advanced_ocr_optional_runtime.md` and `docs/runtime/local_ocr_endpoint_contract.md`.
- Goal: Document optional AI runtime setup without bloating default installs.
- Non-goals: No bundling torch, transformers, CUDA, models, SGLang, or vLLM into the default app or installer.
- Acceptance criteria: Docs clearly separate default install from optional advanced OCR runtime setup.
- Required tests: Documentation review and default-install CI checks.
- Safety/privacy checks: Installation docs must mention local-first behavior and model/custom-code risks.

## 9. Privacy and Security Review

- Status: Implemented as pre-integration documentation in `docs/security/advanced_ocr_security_review.md` and `docs/security/advanced_ocr_preintegration_checklist.md`.
- Goal: Complete a formal review before any real model integration is enabled.
- Non-goals: No implementation bypass around consent, dependency, or locality checks.
- Acceptance criteria: Review covers data flow, temp files, logs, reports, endpoint policy, model code execution, and dependency provenance.
- Required tests: Import-boundary, no-upload, no-background-execution, and report-redaction tests.
- Safety/privacy checks: Confirm no screen capture, background OCR, file upload, or OCR text logging by default.

## 10. Final User Documentation and Examples

- Goal: Publish user-facing guidance once real advanced OCR is implemented and reviewed.
- Non-goals: No claims that real Unlimited-OCR inference works before it does.
- Acceptance criteria: README, release notes, and examples accurately explain requirements, limits, privacy, and fallback behavior.
- Required tests: Documentation review against implemented behavior.
- Safety/privacy checks: Examples use local files and clearly explain that Tesseract remains the default unless the user opts into advanced OCR.
