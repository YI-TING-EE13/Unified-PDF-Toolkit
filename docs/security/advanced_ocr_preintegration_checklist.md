# Advanced OCR Pre-Integration Checklist

Use this checklist before enabling any real advanced local AI OCR,
Unlimited-OCR-compatible backend, local endpoint execution, model download, or
GPU runtime path. Every item must be pass, fail, or explicitly not applicable.

## Data Flow and Privacy

- [ ] No external upload path exists by default.
- [ ] Endpoint mode is loopback-only by default.
- [ ] Non-loopback hosts, public IPs, private LAN IPs, domains, `0.0.0.0`,
      non-HTTP schemes, malformed URLs, missing ports, credentials, query
      strings, and unexpected paths are rejected by default.
- [ ] Source PDF/image file paths are not sent to any backend or endpoint.
- [ ] Page images sent to a local endpoint use in-memory bytes/base64 only.
- [ ] OCR text is not written to logs, diagnostics, workflow reports, or crash
      output by default.
- [ ] Rendered image bytes/base64 and document content are not written to logs,
      diagnostics, workflow reports, or crash output by default.
- [ ] Temporary rendered files are cleaned up after success.
- [ ] Temporary rendered files are cleaned up after failure.
- [ ] Temporary rendered files are cleaned up after cancellation.

## Consent and User Control

- [ ] Advanced OCR consent is required before real backend execution.
- [ ] Consent matches provider, model id, and consent text version.
- [ ] Provider/model/text-version changes invalidate old consent.
- [ ] Consent covers model download risk.
- [ ] Consent covers custom model code or `trust_remote_code` risk.
- [ ] Consent covers GPU/VRAM use.
- [ ] Consent covers temporary rendered page images.
- [ ] Cancelled or declined consent leaves backend unavailable.
- [ ] The user explicitly selects files before OCR execution.
- [ ] No screen OCR, global hotkey, automatic capture, or background OCR is
      enabled.

## Runtime and Packaging

- [ ] torch is not a default dependency.
- [ ] transformers is not a default dependency.
- [ ] SGLang/vLLM/CUDA/model files are not default dependencies or bundled
      installer contents.
- [ ] Heavy AI runtimes are not imported at app startup.
- [ ] Optional runtime imports are lazy and backend-specific.
- [ ] Missing optional runtime produces a clear warning/error without breaking
      normal PDF tools.
- [ ] Tesseract remains the default PDF to Word OCR Text engine.

## Endpoint and Backend Behavior

- [ ] Local endpoint requests use short timeouts.
- [ ] Endpoint reachability checks do not send document content.
- [ ] Endpoint unavailable errors are clear and actionable.
- [ ] Missing model errors are clear and actionable.
- [ ] Missing GPU or insufficient VRAM errors are clear and actionable.
- [ ] Malformed backend responses are handled without leaking OCR payloads.
- [ ] Cancellation stops further page processing.
- [ ] Partial outputs are avoided or clearly marked.
- [ ] Output files are written only to the selected local output folder.
- [ ] Output format and page order are correct for approved sample files.

## Diagnostics and Documentation

- [ ] Diagnostics remain warning/info only for missing optional AI components.
- [ ] Diagnostics do not require internet, GPU, CUDA, models, or servers.
- [ ] Diagnostics do not log OCR text or rendered page images.
- [ ] User-facing documentation states the backend is optional and local-first.
- [ ] User-facing documentation states Tesseract remains the default unless a
      user explicitly opts into advanced OCR.
- [ ] Documentation does not claim production-ready Unlimited-OCR support before
      release gates pass.
- [ ] GPU/manual acceptance test plan was completed on local non-sensitive
      samples.
- [ ] Rollback plan is documented and tested.

## Release Decision

- Reviewer:
- Date:
- Branch/commit:
- Backend/provider/model:
- Decision: pass / fail / needs follow-up
- Blocking issues:
- Required follow-up:
