# Advanced OCR Next Goals

This roadmap keeps future optional advanced local OCR work reviewable without
depending on chat history. Tesseract remains the default OCR path until a future
milestone explicitly changes user-facing options.

Maintainer entry point: `docs/advanced_ocr_maintainer_guide.md`.

Primary future direction: optional local AI OCR should run on the user's own
computer. This project does not plan a hosted OCR service, cloud upload path, or
project-operated server for user documents. The local endpoint scaffold remains
an advanced/developer loopback option, not the main product path.

## 1. Consent UI and Settings Persistence

- Status: Implemented for future-use consent management; no real AI OCR execution enabled.
- Goal: Add a clear UI flow that records explicit consent for advanced local AI OCR.
- Non-goals: No model inference, model download, or backend execution.
- Acceptance criteria: Consent stores provider, model id, text version, all required acknowledgements, and timestamp through existing settings helpers.
- Required tests: Unit tests for load/save, invalid consent, and consent invalidation when provider/model/version changes.
- Safety/privacy checks: Consent text must disclose model download risk, custom code risk, GPU/VRAM use, and temporary rendered page images.

## 2. Local Endpoint Client Backend

- Status: Implemented as a localhost-only backend scaffold and hardened with mock-only request/response validation; retained as an advanced/developer loopback option, not the primary product direction.
- Goal: Add an optional backend client for future Unlimited-OCR-compatible local servers.
- Non-goals: No hosted endpoint defaults, remote upload support, server launcher, or public-network target.
- Acceptance criteria: Endpoint defaults to `127.0.0.1` only and refuses non-loopback addresses unless a later reviewed policy allows them.
- Required tests: Mock HTTP/client tests with no live network dependency.
- Safety/privacy checks: No user files, rendered pages, or OCR text leave localhost by default.

## Supporting Milestone: Local Model Runtime Direction and Scaffold

- Status: Implemented as a safe scaffold in `src/ocr/local_model.py` with runtime design documentation in `docs/runtime/local_model_ocr_runtime.md`; runtime settings, readiness diagnostics, fake worker, and an experimental local Unlimited-OCR path are implemented, but production readiness is still future work.
- Goal: Make user-owned local model execution the primary future advanced OCR path.
- Non-goals: No real Unlimited-OCR inference, model download, AI runtime dependency, server process, endpoint call, hosted OCR service, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: Backend scaffold fits `OcrBackend`, requires valid advanced OCR consent, imports no heavy AI runtime, downloads no model, and reports runtime/model-not-configured errors clearly.
- Required tests: Unit tests for consent gating, clean unavailable errors, workflow selection, and no torch/transformers/SGLang imports.
- Safety/privacy checks: Future local model execution must stay on the user's computer, require explicit consent for model download/custom code/GPU use, and avoid OCR content in logs/reports.

## Supporting Milestone: Local Model Runtime Settings and Readiness

- Status: Implemented as safe configuration, Settings / Recent affordances, diagnostics readiness checks, and worker-process contract documentation.
- Goal: Make the local model runtime path concrete and testable without real model inference.
- Non-goals: No model download, real Unlimited-OCR inference, worker process execution, server management, endpoint call, heavy dependency import, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: Defaults keep runtime disabled; settings store only safe runtime fields; Settings UI states that real inference is future work; diagnostics report disabled/configured/path readiness as warning/info; backend returns clear disabled/not-configured errors.
- Required tests: Config defaults/load/save/clear, forbidden-content exclusion from config, diagnostics disabled/missing/configured paths, backend consent/unavailable behavior, settings save/reset, and no heavy imports.
- Safety/privacy checks: Settings do not store OCR text, source paths, document content, rendered page paths, image bytes/base64, or output contents.

## Supporting Milestone: Fake Local Model Worker Prototype

- Status: Implemented as a developer/test-only subprocess prototype using `src/ocr/local_worker.py` and `src/ocr/workers/fake_local_model_worker.py`.
- Goal: Exercise the future user-owned local model worker-process architecture without real OCR inference.
- Non-goals: No real Unlimited-OCR inference, model download, AI runtime dependency, GPU/CUDA use, long-running background worker, app-startup worker launch, server management, endpoint call, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: `fake_worker` mode is explicit and disabled by default; backend requires valid advanced OCR consent; worker payload excludes source paths, OCR text, image bytes/base64, and document content; timeout, cancellation, malformed JSON, non-zero exit, and response-shape failures surface as user-safe OCR errors.
- Required tests: Deterministic fake worker success, timeout, cancellation, malformed JSON, non-zero exit, payload redaction, backend consent gating, explicit fake-worker configuration, and no heavy imports.
- Safety/privacy checks: Fake worker uses only the Python standard library, reads only sanitized JSON metadata from stdin, writes JSON to stdout, logs no OCR/document/image content, and is not presented as real OCR support.

## Supporting Milestone: Experimental Local Unlimited-OCR Backend

- Status: Implemented as optional `local_unlimited_ocr` direct mode plus `worker_process` subprocess mode with lazy Transformers/torch imports and manual validation script support.
- Goal: Allow a user-owned local Baidu Unlimited-OCR-compatible model directory to run experimental OCR when optional dependencies and consent are already in place.
- Non-goals: No production AI OCR exposure, default-engine change, bundled AI runtime, automatic model download, app-startup import, hosted OCR service, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: Backend requires valid advanced OCR consent, explicit enabled runtime config, existing local model path, lazy optional dependencies, local temporary page images with cleanup, user-safe OCR exceptions, and normal `OcrResult` / `OcrPageResult` output.
- Required tests: Missing consent/config/dependency paths, mocked successful Transformers inference, lazy import/no heavy startup import, settings device preference, diagnostics readiness, and existing workflow tests with no GPU/model/internet requirement.
- Safety/privacy checks: No upload, no OCR text/image bytes/document content in diagnostics or errors, no silent model download, `trust_remote_code=True` remains consent-gated and documented.

## Supporting Milestone: Killable Unlimited-OCR Worker Runtime

- Status: Implemented as an experimental one-shot worker-process path in `src/ocr/local_worker.py` and `src/ocr/workers/unlimited_ocr_worker.py`.
- Goal: Provide a killable local process boundary for real user-owned Unlimited-OCR inference so timeout, cancellation, and worker crashes do not require killing the desktop app process.
- Non-goals: No production UI exposure, default-engine change, model download, bundled AI runtime, hosted OCR service, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: `worker_process` requires valid advanced OCR consent, explicit local model path, explicit worker Python executable, and disabled-by-default runtime config; worker stdout is JSON; worker stderr and payload details are not surfaced to users; timeout/cancel terminates the subprocess; temp page images are cleaned up.
- Required tests: Worker success with mocked subprocess response, timeout, malformed JSON, non-zero exit, backend dispatch only when configured, consent gating, payload redaction, and no heavy imports at app startup.
- Safety/privacy checks: Controller-created temporary page image paths are scoped to a temp directory; source file paths, OCR text, image bytes/base64, model paths, and document content are not logged or included in user-facing errors by default.

## Supporting Milestone: Unlimited-OCR Worker Runtime Safety Hardening

- Status: Implemented with a default single-worker guard, busy error handling, structured worker error parsing, stderr redaction, and cleanup tests.
- Goal: Reduce risk before any broader UI exposure by preventing accidental concurrent GPU workers and keeping worker failures user-safe.
- Non-goals: No production AI OCR exposure, default-engine change, model download, bundled AI runtime, hosted OCR service, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: `worker_process` allows only one active Unlimited-OCR worker by default; concurrent attempts return a safe busy message; timeout/cancel paths remove the worker lock; worker stderr is discarded; structured worker errors are parsed only when safe.
- Required tests: Busy guard, timeout cleanup, structured safe error propagation, unsafe error redaction, malformed JSON, non-zero exit, and no heavy imports at app startup.
- Safety/privacy checks: Busy/errors must not expose source paths, OCR text, image bytes/base64, model paths, or document content.

## 3. Developer-Only Document OCR UI Wiring

- Status: Implemented behind `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`; evolved into a dev-only Document OCR shell that uses reusable mock-only workflow helpers for backend selection, consent gating, output writing, and error mapping.
- Goal: Wire the fake backend into controlled UI tests so flows can be exercised without a model.
- Non-goals: No user-facing claim that AI OCR is supported.
- Acceptance criteria: Fake backend is clearly labeled and unavailable in release-facing normal workflows unless explicitly enabled for development.
- Required tests: GUI or unit tests proving fake output is deterministic and local.
- Safety/privacy checks: Fake backend must not import torch/transformers, download models, or upload data.

## Supporting Milestone: Dev-Only Document OCR UI Shell

- Status: Implemented as a hidden developer-only shell exposed only when `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`.
- Goal: Prepare future Document OCR UI integration with file selection, output folder selection, TXT/Markdown output options, backend selection, consent gating, progress/cancel handling, output actions, and user-safe error display.
- Non-goals: No production AI OCR sidebar, live local endpoint calls, real model inference, server execution, model download, AI runtime dependency, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: The shell is clearly labeled developer/testing-only, exposes only the fake backend in the UI, and keeps local endpoint behavior mock-only in tests.
- Required tests: Registration is env-gated, fake backend selection works, unknown backend selections are rejected, fake workflow output remains deterministic, consent denial remains blocking, cancellation works, and no heavy AI runtime is imported.
- Safety/privacy checks: OCR text is written only to selected local outputs; workflow reports and errors must not include document content, image bytes/base64, or source paths.

## Supporting Milestone: Mock-Only Workflow Selection Foundation

- Status: Implemented in `src/ocr/workflow.py`; supports fake backend and mocked local endpoint selection only.
- Goal: Prepare future Document OCR UI work with shared backend selection, consent gating, local output writing, and user-safe error mapping.
- Non-goals: No production endpoint OCR, real model inference, server execution, model download, or normal-user AI OCR sidebar.
- Acceptance criteria: Unit tests cover backend selection, consent allowed/denied behavior, TXT/Markdown output writing, mocked endpoint workflow, and error message mapping.
- Required tests: Mock-only tests with no live network, GPU, model, or optional AI runtime dependency.
- Safety/privacy checks: OCR text is written only to selected local outputs; errors must not leak document content, image bytes, base64 payloads, or source paths.

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

- Status: Partially implemented as a user-facing `Document OCR` tool with Tesseract as the default backend and a gated experimental Local Unlimited-OCR worker option; production-ready AI OCR remains future work.
- Goal: Provide document OCR outputs such as text, Markdown, or JSON while keeping Tesseract as the default and any AI backend explicitly experimental.
- Non-goals: No screen OCR, global hotkeys, automatic capture, or background OCR.
- Acceptance criteria: The tool requires explicit file selection, visible output paths, clear experimental labeling, Tesseract default behavior, and an env-gated Local Unlimited-OCR option that requires consent plus `worker_process` runtime settings.
- Required tests: Registration/default backend tests, experimental gate tests, unit tests for output writing, user-safe errors, and no heavy AI startup imports.
- Safety/privacy checks: Reports must not include OCR text or rendered page images by default.

## Supporting Milestone: Experimental Local Unlimited-OCR Document OCR UI Exposure

- Status: Implemented as a gated option in the user-facing `Document OCR` tool.
- Goal: Let maintainers validate the future local model OCR workflow from the real Document OCR surface without making AI OCR the default or production-ready.
- Non-goals: No model download, bundled AI runtime, in-process mode exposure, hosted OCR service, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: Tesseract is the default; `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` is required to show Local Unlimited-OCR; `worker_process` runtime settings and saved advanced OCR consent are required before execution.
- Required tests: Tool registration, gate off/on behavior, Tesseract output path, invalid local runtime config, source-path exclusion for local model requests, and no torch/transformers/SGLang imports at startup.
- Safety/privacy checks: OCR text is written only to selected local outputs; source paths are not sent to the local model backend; errors and reports do not include OCR text, image bytes/base64, or document content.

## Supporting Milestone: Experimental Local OCR Failure Handling

- Status: Implemented for the Document OCR workflow error mapper and manually checked with local failure scenarios.
- Goal: Ensure the experimental local worker path fails clearly before broader exposure.
- Non-goals: No production readiness claim, model download, bundled AI runtime, hosted OCR service, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: Missing model path, invalid model path, missing worker Python, missing consent, busy worker, unsupported input, short timeout, and CUDA/GPU failures map to user-safe messages.
- Required tests: Unit tests for error mapping plus workflow/tool tests with mocked or local-safe failure scenarios.
- Safety/privacy checks: Failure messages must not include source paths, OCR text, image bytes/base64, model cache paths, or document content.

## Supporting Milestone: Experimental Local Unlimited-OCR Beta Readiness

- Status: Implemented for controlled beta only; public production support remains future work.
- Goal: Prepare maintainers and beta testers to validate the gated local worker-process path without changing default dependencies or default OCR behavior.
- Non-goals: No public production claim, model bundling, automatic model download, hosted OCR service, screen OCR, background OCR, file upload, Batch Queue integration, or removal of the experimental env gate.
- Acceptance criteria: Setup guide covers uv-managed optional runtime, local model folder, Hugging Face cache/module cache paths, GUI launch commands, readiness checks, smoke commands, cleanup, and troubleshooting; beta checklist covers Tesseract, experimental worker_process, diagnostics, failure paths, cancel/timeout, and privacy checks; release-gate audit confirms Tesseract default, local-only behavior, and no dependency bloat.
- Required tests: Diagnostics unit tests for optional dependency/cache/runtime checks, Document OCR cancellation tests, full default test suite, compileall, readiness check, and feasible GUI smoke runs with synthetic inputs.
- Safety/privacy checks: Smoke tools do not print OCR text/image bytes/document content; generated outputs, model/cache files, and optional runtime folders remain untracked; `README (1).md` remains excluded in this workspace.

## Supporting Milestone: Production Document OCR UI Design Review

- Status: Implemented as documentation/review only in `docs/design/`.
- Goal: Define production UX requirements, release gates, safety requirements, and promotion criteria for any future user-facing Document OCR tool.
- Non-goals: No production tool exposure, real Unlimited-OCR inference, model download, AI runtime dependency, server execution, live endpoint calls, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: Review covers current dev-only shell status, intended value, supported inputs, output formats, backend choices, consent UX, diagnostics/readiness UX, error handling, progress/cancel behavior, privacy messaging, experimental labeling, hidden/dev-only boundaries, and release gates.
- Required tests: Documentation review plus future implementation tests listed in the production readiness checklist.
- Safety/privacy checks: Checklist gates consent, local-only behavior, loopback endpoint enforcement, no source path leakage, no OCR content in logs/reports, diagnostics, output correctness, cancellation, error quality, accessibility, manual acceptance, and rollback.

## Supporting Milestone: Production Document OCR Fake-Backend Smoke Plan

- Status: Implemented as documentation/test planning only in `docs/testing/document_ocr_fake_backend_smoke_plan.md` and `docs/testing/manual_document_ocr_smoke_template.md`.
- Goal: Define how a future production Document OCR UI should be smoke-tested with fake/mock backends before exposure to normal users.
- Non-goals: No production UI implementation, dev-shell promotion, real Unlimited-OCR inference, model download, AI runtime dependency, server execution, live endpoint calls, screen OCR, background OCR, file upload, or Batch Queue integration.
- Acceptance criteria: Plan covers current dev-only shell relationship, production UI assumptions, fake backend matrix, consent scenarios, diagnostics/readiness scenarios, TXT/Markdown outputs, progress/cancel behavior, user-safe errors, rollback/hide-feature behavior, and no-real-model/non-CI boundaries.
- Required tests: Future smoke tests must use fake backend or mocked transport only and must not require internet, GPU, CUDA, model download, OCR server, torch, transformers, or SGLang.
- Safety/privacy checks: Manual template avoids OCR text, image bytes/base64 payloads, source file paths, and document content; production readiness checklist requires fake-backend smoke completion before exposure.

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

- Status: Implemented and updated for the gated experimental local worker path in `docs/security/advanced_ocr_security_review.md` and `docs/security/advanced_ocr_preintegration_checklist.md`.
- Goal: Maintain formal privacy/security gates before any broader model integration or production exposure.
- Non-goals: No implementation bypass around consent, dependency, or locality checks.
- Acceptance criteria: Review covers data flow, temp files, logs, reports, endpoint policy, model code execution, and dependency provenance.
- Required tests: Import-boundary, no-upload, no-background-execution, and report-redaction tests.
- Safety/privacy checks: Confirm no screen capture, background OCR, file upload, or OCR text logging by default.

## 10. Final User Documentation and Examples

- Goal: Publish user-facing guidance once advanced OCR is ready for public beta or production exposure.
- Non-goals: No claims that Unlimited-OCR is production-ready before release gates pass.
- Acceptance criteria: README, release notes, and examples accurately explain requirements, limits, privacy, and fallback behavior.
- Required tests: Documentation review against implemented behavior.
- Safety/privacy checks: Examples use local files and clearly explain that Tesseract remains the default unless the user opts into advanced OCR.
