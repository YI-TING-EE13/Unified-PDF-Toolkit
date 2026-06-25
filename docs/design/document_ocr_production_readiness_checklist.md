# Document OCR Production Readiness Checklist

Use this checklist before exposing any Document OCR tool outside
`PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`.

This checklist is a release gate. Passing it does not by itself approve real
Unlimited-OCR inference, model download, GPU runtime bundling, remote endpoint
support, screen OCR, background OCR, file upload, or Batch Queue integration.
The intended AI OCR direction is local model execution on the user's computer,
not a hosted OCR service.

## Feature Exposure

- [ ] Production entry point is intentionally enabled by a reviewed product
  decision.
- [ ] The dev-only shell remains hidden unless
  `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1` is set.
- [ ] The production tool is clearly labeled experimental if advanced OCR is
  not yet stable.
- [ ] A rollback or hide-feature switch is documented and tested.
- [ ] Fake-backend UI smoke testing is completed before production exposure.

## Consent Gate

- [ ] Execution is blocked until valid consent exists for the selected
  provider/model id and consent text version.
- [ ] Consent text discloses model download risk.
- [ ] Consent text discloses custom-code or `trust_remote_code` risk.
- [ ] Consent text discloses GPU/VRAM use.
- [ ] Consent text discloses temporary rendered page images.
- [ ] Cancelled or declined consent leaves consent invalid.
- [ ] Provider/model id changes invalidate prior consent.
- [ ] Consent text version changes invalidate prior consent.
- [ ] Consent records do not store OCR text, image payloads, source paths,
  output contents, or document content.

## Local-Only Guarantee

- [ ] User files and OCR text are not uploaded by this feature.
- [ ] No external service endpoint is configured by default.
- [ ] No remote endpoint toggle exists unless separately reviewed.
- [ ] No screen capture, screen OCR, global hotkey, or background OCR is
  exposed.
- [ ] Any endpoint mode is explicitly local and loopback-only.
- [ ] No hosted OCR service or project-operated user OCR server is presented as
  an option.

## Local Model Runtime Direction

- [ ] The primary future AI OCR path is local model execution on the user's own
  computer.
- [ ] Local model runtime dependencies remain optional and outside the default
  install.
- [ ] Model downloads require explicit user action and consent.
- [ ] Custom model code or `trust_remote_code` requires explicit acknowledgement.
- [ ] Missing local runtime, missing model path, missing GPU, or insufficient
  VRAM produce user-safe errors.
- [ ] Heavy AI libraries are not imported at app startup.

## Endpoint Loopback Enforcement

If local endpoint mode is exposed:

- [ ] Default endpoint is `http://127.0.0.1:<port>`.
- [ ] `http://localhost:<port>` resolves only to loopback before use.
- [ ] IPv6 loopback is allowed only if validation remains strict.
- [ ] Non-http schemes are rejected.
- [ ] Missing ports are rejected.
- [ ] `0.0.0.0` is rejected.
- [ ] Private LAN IPs are rejected.
- [ ] Public IPs and domains are rejected.
- [ ] Credentials, query strings, fragments, and arbitrary paths are rejected.
- [ ] No unsafe remote override exists.

## Payload and Path Safety

- [ ] Backend payloads include in-memory page images only.
- [ ] Source PDF/image file paths are not sent to backends.
- [ ] Image bytes/base64 are not logged.
- [ ] OCR text is not logged.
- [ ] OCR text is not included in workflow reports by default.
- [ ] Document content is not included in diagnostics.
- [ ] Temporary rendered page images are cleaned up after success, failure, and
  cancellation.

## Diagnostics Readiness

- [ ] Diagnostics never require GPU, CUDA, internet, model download, OCR
  server, torch, transformers, or SGLang.
- [ ] torch is detected with safe optional import behavior.
- [ ] transformers is detected with safe optional import behavior.
- [ ] CUDA availability is checked only when torch is installed.
- [ ] GPU name/VRAM is best-effort and failure-safe.
- [ ] Model cache presence is best-effort and failure-safe.
- [ ] Endpoint URL validity is reported without sending document content.
- [ ] Endpoint reachability, if checked, is explicit and short-timeout.

## Output Correctness

- [ ] User chooses output folder before execution.
- [ ] TXT output is deterministic and readable.
- [ ] Markdown output preserves page boundaries.
- [ ] Output conflict behavior follows the repo's shared policy where
  practical.
- [ ] Output file errors produce actionable, user-safe messages.
- [ ] Workflow summaries list output paths without embedding OCR text.

## Progress and Cancellation

- [ ] Progress shows current file/page or equivalent useful status.
- [ ] Cancel is available for long-running work.
- [ ] Cancellation stops future pages/files where possible.
- [ ] Partial output behavior is documented in UI copy or result messages.
- [ ] Temporary files are cleaned up on cancellation.
- [ ] Cancel reports avoid OCR text and image content.

## Error Message Quality

- [ ] Missing consent message tells the user how to review/save consent.
- [ ] Missing dependency message names the selected backend requirement without
  making it a default dependency.
- [ ] Endpoint timeout message is clear and sanitized.
- [ ] Endpoint connection failure message is clear and sanitized.
- [ ] Malformed endpoint response message is clear and sanitized.
- [ ] Unsupported input type message is actionable.
- [ ] Errors do not leak OCR text, image bytes/base64, or document content.

## Accessibility and Basic UX

- [ ] Controls have visible text labels.
- [ ] Backend and output format controls are keyboard reachable.
- [ ] Experimental status is visible without relying on color alone.
- [ ] Consent action, diagnostics action, start, and cancel controls are
  clearly separated.
- [ ] Long warning text wraps and does not clip in the default window size.
- [ ] Empty, running, cancelled, failed, and completed states are visible.

## Test Coverage

- [ ] Unit tests cover backend selection.
- [ ] Unit tests cover consent allowed/denied/stale behavior.
- [ ] Unit tests cover TXT and Markdown output writing.
- [ ] Unit tests cover unsupported input handling.
- [ ] Unit tests cover cancellation behavior where practical.
- [ ] Unit tests cover user-safe error mapping.
- [ ] Import-boundary tests confirm no heavy AI runtime import at app startup.
- [ ] UI smoke tests use fake backend only.
- [ ] UI smoke tests cover file selection, output folder selection, output
  format selection, consent blocking, readiness messaging, progress,
  cancellation, output actions, and user-safe errors.
- [ ] Local endpoint tests use mocked transport only.
- [ ] CI requires no internet, GPU, CUDA, model download, OCR server, torch,
  transformers, or SGLang.

## Manual Acceptance

- [ ] Manual fake-backend UI smoke run completed using
  `docs/testing/document_ocr_fake_backend_smoke_plan.md`.
- [ ] Manual smoke run details recorded with
  `docs/testing/manual_document_ocr_smoke_template.md`.
- [ ] Manual local endpoint run completed only if endpoint production mode is
  being reviewed.
- [ ] Manual GPU acceptance completed only if a real GPU backend is being
  reviewed.
- [ ] Privacy checklist completed with representative PDF and image samples.
- [ ] Rollback/hide-feature procedure verified.

## Documentation

- [ ] README states the implemented behavior accurately.
- [ ] User docs do not claim real Unlimited-OCR inference unless implemented.
- [ ] User docs do not claim GPU OCR unless implemented.
- [ ] User docs do not claim bundled AI models or GPU runtime.
- [ ] User docs do not claim endpoint OCR is production-ready until this
  checklist passes.
- [ ] Maintainer guide and roadmap are updated with current status.
