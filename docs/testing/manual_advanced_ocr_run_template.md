# Manual Advanced OCR Run Template

Use this template for future manual GPU/model/server validation only. Do not use
it as evidence that real Unlimited-OCR inference is currently supported.

## Run Metadata

- Date:
- Reviewer:
- Branch/commit:
- Machine/OS:
- GPU name:
- GPU VRAM:
- Driver version:
- CUDA/runtime version:
- Python version:

## Backend Under Test

- Backend mode: local endpoint / in-process runtime / other reviewed local mode
- Provider:
- Model id:
- Consent text version:
- Optional runtime packages and versions:
- Model cache path:
- Endpoint URL, if applicable:
- Endpoint URL validation result:

## Sample Input

- File type: PDF / PNG / JPG / other
- Page count:
- Image dimensions, if applicable:
- Sensitive data removed: yes / no
- Sample source:

## Execution Summary

- Start time:
- End time:
- First-run setup time:
- Model load time:
- Per-page OCR time:
- Peak GPU memory:
- Peak system memory:
- Cancellation tested: yes / no
- Output format:
- Output folder:
- Result summary:

## Errors and Warnings

- Missing dependency behavior:
- Missing model behavior:
- Missing GPU or insufficient VRAM behavior:
- Endpoint unavailable/timeout behavior:
- Malformed response behavior:
- User-facing error message quality:

## Privacy and Safety Checklist

- [ ] Advanced OCR consent was required before execution.
- [ ] Consent matched provider, model id, and consent text version.
- [ ] No external upload occurred.
- [ ] Endpoint was loopback-only, if endpoint mode was used.
- [ ] No source file paths were sent to an endpoint.
- [ ] No OCR text was written to logs, diagnostics, or reports by default.
- [ ] No rendered image bytes/base64 were written to logs, diagnostics, or
      reports by default.
- [ ] Temporary rendered page images were cleaned up.
- [ ] No screen OCR, background OCR, global hotkey, or automatic capture ran.
- [ ] Tesseract remained the default PDF to Word OCR Text engine.

## Decision

- Pass / Fail / Needs follow-up:
- Blocking issues:
- Non-blocking issues:
- Follow-up owner:
- Notes:
