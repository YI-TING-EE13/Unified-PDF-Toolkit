# Local Model OCR Runtime Design

This document defines the preferred future architecture for advanced OCR:
run an optional AI OCR model on the user's own computer. Unified PDF Toolkit is
not planning a hosted OCR service, cloud OCR upload path, or project-operated
server for user documents.

This document is a design boundary and scaffold reference. Real Baidu
Unlimited-OCR inference is not implemented yet.

## Product Direction

The primary advanced OCR path should be:

- Tesseract remains the default real OCR engine.
- Future AI OCR runs locally on the user's machine.
- Runtime dependencies are optional and isolated from the default install.
- Model download requires explicit user action and consent.
- Custom model code or `trust_remote_code` requires explicit consent and
  documentation.
- No user files, rendered pages, screenshots, or OCR text are uploaded by this
  feature.

The local endpoint backend is not the main product direction. It remains an
advanced/developer loopback option for users who manage their own local runtime
outside the app.

## User-Owned Local Runtime

A future local model runtime may be:

- a separate worker process started and supervised by the app, or
- an in-process runtime enabled only after dependency and security checks pass.

Both modes must be optional. Neither mode may be required for Tesseract OCR,
PDF editing, conversion, compression, or app startup.

## Optional Dependency Strategy

Default dependencies must not include:

- torch
- transformers
- SGLang or vLLM
- CUDA packages
- GPU runtime packages
- model files
- model cache downloads

Future runtime dependencies should be installed into a documented optional
environment or package extra only after a reviewed packaging decision. Heavy AI
libraries must not be imported at app startup.

## Model Download Consent

Before any model download is allowed:

- User chooses the provider/model id.
- User sees expected size and cache location when known.
- User explicitly confirms the download.
- Failed or partial downloads do not break default app behavior.
- Cache removal and rollback are documented.

The app must not download models automatically at startup or when browsing
normal PDF tools.

## Custom Code and `trust_remote_code`

Baidu Unlimited-OCR examples may rely on custom model code. Treat this as local
execution of third-party code.

Before enabling custom code:

- Pin and document the model repository and revision.
- Require explicit user acknowledgement.
- Avoid execution at app startup.
- Keep the runtime disabled unless selected by the user.
- Provide a clear rollback path.

## GPU and VRAM Requirements

Future real local model OCR may require a GPU and substantial VRAM. The app
should report readiness without making GPU checks mandatory for default use.

Readiness should be best-effort:

- Python/runtime version.
- Optional dependency presence.
- CUDA availability only if torch is installed.
- GPU name and VRAM if safely detectable.
- Model cache presence if safely detectable.

Missing GPU/model/runtime should produce clear user-facing errors for the
selected backend, not app startup failures.

## Worker Process vs In-Process Runtime

### Worker Process

Preferred initial real-runtime direction.

Advantages:

- Keeps heavy imports outside the desktop app process.
- Allows clearer startup and shutdown boundaries.
- Reduces impact of model crashes on the GUI.
- Makes it easier to disable or replace the runtime.

Risks:

- Requires process lifecycle management.
- Requires local IPC contract and timeout handling.
- Must ensure no source paths or OCR content are logged unintentionally.

### In-Process Runtime

Allowed only after a separate security and dependency review.

Advantages:

- Simpler call path.
- Fewer IPC moving parts.

Risks:

- Heavy imports can affect startup if not lazy.
- GPU/runtime crashes may affect the GUI process.
- Custom model code runs inside the app process.

## Backend Scaffold

`src/ocr/local_model.py` defines the current scaffold:

- `LocalModelOcrBackend`
- `LocalModelRuntimeConfig`
- provider/model constants for the future Baidu Unlimited-OCR-compatible path

The scaffold:

- fits the existing `OcrBackend` contract,
- requires valid advanced OCR consent,
- imports no heavy AI runtime,
- downloads no model,
- runs no inference,
- reports runtime/model-not-configured errors clearly.

## Failure Handling

Future local model OCR must handle:

- missing runtime
- missing model path
- missing optional dependency
- stale consent
- unsupported runtime mode
- insufficient VRAM
- model load failure
- custom code failure
- timeout
- cancellation
- output write failure

Errors must not include OCR text, image bytes/base64 payloads, document
content, or hidden source paths.

## Privacy Guarantees

Required privacy properties:

- No cloud upload.
- No hosted OCR service.
- No project-operated user OCR server.
- No screen OCR, global hotkey, background OCR, or automatic capture.
- No OCR text or rendered page images in logs/reports by default.
- Temporary rendered page images are cleaned up after success, failure, and
  cancellation.

## Packaging Constraints

Default app packages and CI must remain lightweight.

The Windows installer must not bundle:

- AI model files
- GPU runtime packages
- CUDA stack
- torch or transformers
- SGLang/vLLM
- real Unlimited-OCR runtime

Any optional runtime packaging must be separately reviewed and documented.

## Rollback and Uninstall

Rollback must support:

- disabling advanced OCR features,
- clearing advanced OCR consent,
- reverting to Tesseract-only OCR,
- removing optional runtime dependencies from the user-managed environment,
- removing local model cache only with explicit user action.

Uninstalling the default app must not be responsible for deleting user-managed
model caches unless a future reviewed UI explicitly offers that action.

## Manual Acceptance Tests

Before real local model support is exposed:

- Complete the privacy/security pre-integration checklist.
- Complete fake-backend Document OCR smoke tests.
- Complete manual GPU/model acceptance tests on representative local hardware.
- Confirm Tesseract OCR behavior is unchanged.
- Confirm default install works without optional AI dependencies.
- Confirm startup imports do not load heavy AI runtimes.
- Confirm consent gates model execution and custom code.
- Confirm no file upload or remote endpoint path exists.

Real model tests are manual/non-CI until a future lightweight test strategy is
reviewed.
