# Advanced OCR GPU Acceptance Test Plan

This document defines a manual acceptance plan for future advanced local AI OCR
or Unlimited-OCR-compatible backends. It is documentation only. The current app
does not run real Unlimited-OCR inference, download models, start OCR servers,
or add GPU runtime dependencies.

## Purpose and Scope

Use this plan before enabling any real GPU/model/server OCR path in Unified PDF
Toolkit. The plan validates privacy boundaries, consent behavior, local-only
networking, diagnostics, cancellation, output correctness, and failure handling.

This plan is not part of CI. Run it only on a developer or reviewer machine that
has intentionally installed the optional AI runtime outside the default app
dependencies.

## Required Hardware and Software

- A local test machine with an explicitly approved GPU for manual validation.
- GPU driver and CUDA/runtime versions required by the future backend under
  review.
- Optional AI OCR runtime installed manually outside the default project
  dependencies.
- Local model files or a user-managed local OCR server, if the future backend
  requires them.
- Unified PDF Toolkit source checkout with normal test suite passing.
- Small local sample files that do not contain sensitive or regulated data.

Do not add torch, transformers, SGLang, CUDA, model files, or server packages to
the default dependency set as part of this acceptance run.

## Privacy and Security Pre-Checks

Confirm these before running any real OCR request:

- No external file upload is configured or possible in the tested path.
- Endpoint mode, if used, accepts only loopback URLs such as
  `http://127.0.0.1:<port>` or an explicitly reviewed IPv6 loopback URL.
- Non-loopback hosts, public IPs, private LAN IPs, `0.0.0.0`, domains, and
  non-HTTP schemes are rejected by default.
- Source PDF/image file paths are not sent to any OCR endpoint.
- Page images, if sent to a local endpoint, are sent as in-memory bytes or
  base64 payloads only.
- OCR text, image bytes, base64 payloads, and document content are not written
  to logs, diagnostics, or workflow reports by default.
- Temporary rendered page images are stored only in a local temporary location
  and are cleaned up after success, failure, and cancellation.
- No screen capture, screen OCR, global hotkey, background OCR, or ambient
  monitoring is enabled.

## Consent Pre-Checks

- Confirm advanced OCR consent is required before execution.
- Confirm consent text discloses model download risk, custom model code or
  `trust_remote_code` risk, GPU/VRAM use, and temporary rendered page images.
- Confirm consent stores only provider, model id, consent text version,
  acknowledgements, and timestamp.
- Confirm changing provider, model id, or consent text version invalidates old
  consent.
- Confirm cancelling or declining consent leaves the backend unavailable.

## Local-Only Networking Expectations

Endpoint validation must pass before any manual endpoint run:

- Allowed: `http://127.0.0.1:<port>`.
- Allowed after review: `http://localhost:<port>` only when it resolves to
  loopback addresses.
- Allowed after review: `http://[::1]:<port>` if IPv6 loopback is supported.
- Rejected: `https://...`, `http://0.0.0.0:<port>`, private LAN IPs, public IPs,
  domains, file paths, malformed URLs, missing ports, credentials, query
  strings, and unexpected URL paths.

Reachability checks must use a short timeout and must not send document content.

## Model and Runtime Setup Placeholders

Future backend documentation must fill in these items before this plan can be
executed:

- Backend mode under test: local endpoint, in-process runtime, or another
  reviewed local-only mode.
- Model provider and model id.
- Expected model cache location.
- Runtime packages and exact versions.
- GPU driver, CUDA/runtime, and minimum VRAM expectations.
- Whether custom model code or `trust_remote_code` is involved.
- How to start and stop any user-managed local server, if applicable.

## Local Endpoint Validation Checklist

Use this checklist only for a future local endpoint backend. Do not start or
call a real server as part of documentation-only changes.

- The app refuses unsafe endpoint URLs before any request is sent.
- The request payload does not include source file paths.
- The request payload includes only the minimum page image data and OCR options
  needed for local processing.
- Timeout is short and user-facing.
- Server unavailable, timeout, malformed response, and invalid JSON produce
  clear user-facing errors.
- No OCR text or image payload is echoed into logs or diagnostics.
- Cancelled requests stop further pages from being sent.
- Output files are not created or are clearly marked partial when cancellation
  happens mid-run.

## Sample Input Recommendations

Use local, non-sensitive samples:

- One one-page scanned PDF.
- One three-to-five-page scanned PDF.
- One mixed PDF with both embedded text and scanned pages.
- One small PNG or JPEG document image.
- One intentionally unsupported or damaged file for error handling.

Avoid personal documents, medical/legal/financial records, private customer
data, screenshots, or production files.

## Execution Checklist

1. Run the normal automated validation suite first.
2. Record machine, GPU, driver/runtime, backend, model id, and endpoint URL in
   the manual run template.
3. Confirm consent is missing and the backend refuses to run.
4. Save valid consent and confirm the backend becomes available.
5. Run one small sample and verify output text/Markdown/JSON is created only in
   the selected local output folder.
6. Confirm logs, diagnostics, and workflow reports do not contain OCR text,
   image bytes, base64 payloads, or document content.
7. Run cancellation during rendering and during OCR processing, if both phases
   exist.
8. Simulate missing model, missing GPU, insufficient VRAM, server unavailable,
   timeout, and malformed response.
9. Confirm temporary files are cleaned after success, failure, and cancellation.
10. Confirm Tesseract OCR remains the default PDF to Word OCR Text engine.

## Expected Output Checks

- Output files are written to the user-selected local output folder only.
- Output content matches the chosen format contract.
- Multi-page outputs preserve page order and page labels.
- Partial outputs are either avoided or clearly marked when cancellation occurs.
- File conflict behavior follows existing output conflict settings.
- User-facing success messages do not imply real Unlimited-OCR support unless
  that backend is actually implemented and reviewed.

## Performance Observations to Record

Record observations, not pass/fail gates, unless a future backend defines
explicit limits:

- First-run setup time.
- Model load time.
- Per-page OCR time.
- Peak GPU memory usage.
- Peak system memory usage.
- GPU name and driver/runtime version.
- CPU fallback behavior, if any.
- Output size and page count.
- Cancellation response time.

## Failure Modes and Rollback Steps

Validate these failure paths:

- Missing consent.
- Missing optional runtime dependency.
- Missing model cache.
- Model custom-code trust not acknowledged.
- No compatible GPU.
- Insufficient VRAM.
- Local endpoint not reachable.
- Local endpoint rejects request.
- Timeout.
- Malformed OCR response.
- Disk permission failure in output folder.
- Cancellation during render or OCR.

Rollback expectations:

- Disable the experimental backend or dev flag.
- Clear advanced OCR consent if needed.
- Restore Tesseract-only default behavior.
- Remove optional runtime packages from the manual test environment if they were
  installed only for validation.
- Delete local model cache only when the reviewer explicitly confirms it is no
  longer needed.
- Preserve logs that contain no document content for debugging.

## Acceptance Checklist

- [ ] No external upload occurred.
- [ ] Endpoint, if used, was loopback-only.
- [ ] No source file paths were sent to the endpoint.
- [ ] No OCR text, image bytes, base64 payloads, or document content appeared
      in logs, diagnostics, or reports.
- [ ] Temporary rendered images were cleaned up.
- [ ] Consent was required before execution.
- [ ] Consent invalidation worked for provider/model/version changes.
- [ ] Missing GPU/model/server produced clear errors.
- [ ] Cancellation stopped further work and left output state understandable.
- [ ] Output files were correct for the selected format.
- [ ] Diagnostics stayed informational and did not fail the app.
- [ ] Tesseract remained the default PDF to Word OCR Text engine.

## Non-CI Status

This plan is manual by design. CI must continue to pass without GPU, CUDA,
torch, transformers, SGLang, model downloads, internet access, OCR servers, or
real Unlimited-OCR inference.
