# Local Model OCR Worker Contract

This document defines the future worker-process contract for local model OCR on
the user's own computer. The current implementation includes a developer/test
fake worker subprocess only. The app does not run real Baidu Unlimited-OCR
inference, download models, or import heavy AI runtimes.

## Scope

The preferred first real local model integration should use a worker process so
the desktop app can keep heavy AI imports outside the GUI process.

This contract is for:

- future local model OCR worker processes;
- fake/mock worker tests using `src/ocr/workers/fake_local_model_worker.py`;
- manual acceptance planning.

It is not a hosted service contract and must not be used for cloud OCR upload.

## Current Fake Worker Prototype

The current repo-local prototype contains:

- `src/ocr/local_worker.py`: one-shot worker-process controller.
- `src/ocr/workers/fake_local_model_worker.py`: deterministic fake worker
  script.
- `fake_worker` runtime mode in `LocalModelRuntimeConfig`.

This prototype:

- launches a subprocess only when `LocalModelOcrBackend` is explicitly
  configured with `mode="fake_worker"`;
- requires valid advanced OCR consent before backend execution;
- sends sanitized page metadata over stdin as JSON;
- reads a JSON response from stdout;
- enforces timeout and cancellation through process termination;
- validates response shape before creating `OcrResult`;
- redacts worker stderr, payload data, source paths, OCR text, image bytes,
  base64 payloads, and document content from user-facing errors.

It does not:

- run real OCR;
- import torch, transformers, SGLang, CUDA, or model code;
- download models;
- read source PDF/image paths for OCR;
- start on app startup;
- run as a long-lived background worker.

## Request Input

The app should send only the minimum page data needed for OCR.

Allowed future input forms:

- in-memory image bytes encoded in a bounded local IPC payload; or
- temporary rendered page image files created by the app, only when the worker
  contract includes cleanup and path-scoping rules.

Required request fields:

- request id
- provider/model id
- page number
- image format, image payload, or scoped temporary page image reference for a
  future real worker
- page metadata only for the current fake worker
- OCR prompt/options
- timeout budget

Forbidden request data:

- source PDF/image file paths
- output folder paths
- OCR text from prior pages
- full document content
- unrelated user settings
- unbounded logs or debug payload dumps

The current fake worker request intentionally excludes image payloads and source
paths. It sends only request id, provider/model id, runtime mode, prompt,
sanitized options, and page numbers.

## Temporary File Policy

If temporary page image files are used:

- files must be created under an app-controlled temporary folder;
- paths must refer only to rendered page images, not source documents;
- filenames must not include source document names when avoidable;
- cleanup must run after success, failure, timeout, and cancellation;
- worker logs must not include temporary image paths by default.

In-memory image payloads remain preferred when practical.

## Response Shape

A successful worker response should be page-oriented:

```json
{
  "request_id": "opaque-id",
  "pages": [
    {
      "page_number": 1,
      "text": "recognized text",
      "confidence": 0.92,
      "warnings": []
    }
  ],
  "metadata": {
    "provider": "baidu",
    "model_id": "baidu/Unlimited-OCR",
    "runtime": "fake_worker",
    "real_inference": false
  }
}
```

Rules:

- Page count must match the request.
- Page numbers must match the request order.
- `text` must be a string.
- `confidence`, when present, must be numeric.
- Warnings must be strings and must not include OCR text, image bytes, base64,
  or document content.

## Error Shape

Worker errors should be structured:

```json
{
  "request_id": "opaque-id",
  "error": {
    "code": "model_not_loaded",
    "message": "Local OCR model is not loaded.",
    "retryable": false
  }
}
```

Expected error codes include:

- `runtime_not_installed`
- `model_not_configured`
- `model_not_loaded`
- `missing_gpu`
- `insufficient_vram`
- `timeout`
- `cancelled`
- `invalid_request`
- `inference_failed`

Error messages must be user-safe and must not include OCR text, image payloads,
source paths, or document content.

## Timeout and Cancellation

The app should provide a timeout budget per request or per page. The worker must
stop work promptly when cancellation is requested.

Required behavior:

- no background monitoring;
- no processing after user cancellation where avoidable;
- no hidden retry loops that continue after UI cancellation;
- temporary files cleaned up on timeout/cancel;
- user-safe timeout/cancel messages.

## Logging Restrictions

Do not log by default:

- OCR text;
- rendered page image bytes;
- base64 image payloads;
- source document paths;
- output folder paths;
- full request or response bodies;
- document content.

Allowed high-level logs:

- request id;
- backend/runtime mode;
- provider/model id;
- page count;
- elapsed time;
- timeout/cancel/error category.

## Security and Readiness Gates

Before real worker execution is implemented:

- advanced OCR consent must be required;
- runtime path and model path settings must be explicit;
- model download must require explicit user action and consent;
- custom code or `trust_remote_code` must be separately acknowledged;
- dependency imports must stay out of app startup;
- manual GPU/model acceptance tests must pass;
- rollback/hide-feature behavior must be documented.
