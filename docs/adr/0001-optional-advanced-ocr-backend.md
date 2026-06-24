# ADR 0001: Optional Advanced Local OCR Backend

## Status

Accepted for architecture-only MVP.

## Product Goal

Unified PDF Toolkit should be able to grow toward optional advanced local AI OCR
inspired by Baidu Unlimited-OCR while preserving the app's current local-first,
lightweight desktop-tool positioning. The existing PDF to Word OCR Text workflow
remains Tesseract-backed by default and must not regress.

Baidu Unlimited-OCR is treated as a future optional backend, not a replacement
for Tesseract. This MVP creates the architecture, consent model, diagnostics,
and test wiring only. It does not run the real model.

## Privacy and Security Boundaries

- User files, rendered page images, screenshots, and OCR text must not be
  uploaded by default.
- No automatic screen capture, screen OCR, global hotkeys, background OCR, or
  ambient monitoring.
- OCR text and rendered page images must not be written to logs or workflow
  reports by default.
- Optional AI OCR must require explicit user consent before any future real
  model use.
- Future real Unlimited-OCR integration must disclose model download size/risk,
  `trust_remote_code=True` or equivalent custom-code risk, GPU/VRAM use, and
  temporary rendered page images.

## Non-Goals

- No real Baidu Unlimited-OCR inference in this MVP.
- No model download.
- No Transformers, SGLang, vLLM, torch, CUDA, or model dependencies in the
  default install.
- No AI OCR sidebar tool or Batch Queue AI OCR jobs in this MVP.
- No Windows installer bundling of AI runtime.

## Current MVP Scope

- Repo-level ADR and roadmap documentation for advanced local OCR work.
- A reusable OCR backend abstraction with request/result models, backend
  exceptions, a lightweight registry, Tesseract wrapper, fake Unlimited-OCR
  backend, and explicit consent data structures.
- Minimal PDF to Word OCR Text refactor so existing Tesseract behavior flows
  through the new backend abstraction.
- Diagnostics that report optional advanced OCR readiness without requiring
  torch, transformers, CUDA, GPU access, internet, or model downloads.
- Unit tests for Tesseract backend wiring, fake backend behavior, consent
  invalidation, and optional-dependency-safe diagnostics.

## Architecture

- Add a reusable `src/ocr/` package with typed request/result models,
  backend exceptions, a backend protocol, a lightweight registry, a Tesseract
  backend, a fake Unlimited-OCR backend for tests/dev wiring, and consent
  validation helpers.
- Refactor the existing PDF to Word OCR Text path to call the registry's
  Tesseract backend while preserving the current public behavior.
- Keep heavy optional AI imports out of app startup and out of default
  dependencies.
- Extend diagnostics with optional advanced OCR readiness checks that never
  require GPU, CUDA, model cache, torch, transformers, internet, or model
  downloads.

## Future Phases

1. Add a real consent UI and settings persistence for advanced local AI OCR.
2. Add optional installation documentation for the selected AI runtime.
3. Add a real backend behind the same `OcrBackend` contract only after consent,
   dependency, and GPU readiness gates are implemented.
4. Add GPU/manual acceptance tests outside CI.
5. Consider a separate AI OCR tool or Batch Queue jobs only after the backend is
   stable and clearly marked experimental.

## Implemented Follow-Up: Consent Settings UI

- Settings / Recent now exposes a reusable consent dialog entry point and reset
  action for future advanced local AI OCR.
- Consent records are stored through the existing JSON settings helper and
  contain only provider/model id, consent text version, acknowledgements, and a
  timestamp.
- Cancelled or incomplete consent is not saved, and changing provider/model id
  or consent text version invalidates stored consent.
- This UI does not enable real Unlimited-OCR inference, model downloads, GPU
  execution, file upload, screen OCR, or background OCR.

## Implemented Follow-Up: Local Endpoint Backend Scaffold

- A localhost-only endpoint backend scaffold now supports future user-managed
  OCR servers through the shared `OcrBackend` contract.
- The default endpoint is `http://127.0.0.1:<port>` style, and validation
  rejects non-http schemes, missing ports, non-loopback hosts, `0.0.0.0`,
  private LAN IPs, public IPs/domains, credentials, query strings, and malformed
  URLs.
- The scaffold requires valid advanced OCR consent before use, sends in-memory
  page image payloads rather than source file paths, uses short timeouts, and
  has mockable transport tests.
- The app still does not start servers, run real Unlimited-OCR inference,
  download models, add AI runtime dependencies, upload files, or add AI OCR
  sidebar/batch workflows.

## Acceptance Criteria

- Existing Tesseract OCR remains the default PDF to Word OCR behavior.
- The default dependency set remains lightweight and unchanged for AI runtimes.
- CI and unit tests require no GPU, CUDA, torch, transformers, model download,
  or internet access.
- Missing optional AI dependencies are diagnostics warnings/info, not failures.
- Consent validation invalidates prior consent when provider/model id or consent
  text version changes.
- The fake Unlimited-OCR backend is deterministic and cannot download models or
  import heavy AI runtimes.
