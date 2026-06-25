# Optional Advanced OCR Runtime Guide

This guide documents the intended packaging and installation boundary for future
advanced local AI OCR runtimes. It is documentation only. Unified PDF Toolkit
does not currently include real Unlimited-OCR inference, model downloads, GPU
runtime packages, or a production AI OCR server.

## Default Install Remains Lightweight

The default app, source install, CI, Windows installer, and portable bundle must
remain usable without optional AI OCR runtimes.

Default installs must not include:

- torch
- transformers
- SGLang or vLLM
- CUDA packages
- GPU-specific runtime packages
- model files or model cache downloads
- local OCR server binaries

Tesseract remains the default OCR Text engine for PDF to Word. Optional advanced
OCR must not replace or regress existing Tesseract behavior.

## Windows Installer Boundary

The Windows installer must not bundle an AI model, CUDA stack, GPU runtime,
Transformers stack, SGLang/vLLM server, or real Unlimited-OCR runtime by
default. If a future release adds optional advanced OCR runtime documentation,
the installer should still install only the lightweight desktop app unless a
later reviewed packaging decision explicitly changes this policy.

## User-Managed Optional Runtime

Any future advanced OCR runtime is expected to be user-managed:

- Users or developers install optional runtime dependencies outside the default
  app dependency set.
- Users explicitly choose and configure the provider/model/backend.
- Users acknowledge model download, custom-code, GPU/VRAM, and temporary image
  risks before execution.
- The app validates readiness and surfaces clear errors, but does not silently
  install model runtimes or download models.
- Removing the optional runtime must not break non-AI PDF tools.

## Supported Future Modes

### Local Endpoint Mode

The current scaffold supports a future local endpoint client. It is intended for
user-managed local OCR servers only.

Expected properties:

- Endpoint URL is loopback-only by default.
- The app does not start or manage the server process.
- The app does not send source file paths to the endpoint.
- Page images are designed to be sent as in-memory payloads.
- Timeouts and user-facing errors are required.
- The endpoint is optional and consent-gated.

See `docs/runtime/local_ocr_endpoint_contract.md` for the scaffolded contract.

### In-Process Runtime Prototype

A future in-process Transformers-style prototype is allowed only after security
approval and must remain opt-in.

Requirements before any prototype:

- Security review gates pass.
- GPU/manual acceptance plan is executed for approved samples.
- Optional dependencies remain outside default installs.
- Heavy imports are lazy and backend-specific.
- `trust_remote_code` or equivalent custom model code risk is explicitly
  documented and consent-gated.
- Startup, Tesseract OCR, and non-OCR tools work without the optional runtime.

## Hardware Expectations

Future real backends may require:

- A compatible local GPU.
- Sufficient VRAM for the chosen model.
- A compatible GPU driver and CUDA/runtime stack.
- Enough system RAM and disk space for model cache and page rendering.

Exact requirements must be documented by the future backend implementation.
Diagnostics should report missing or insufficient hardware as warning/error
states without breaking the rest of the app.

## CUDA and GPU Caveats

- CUDA compatibility depends on GPU, driver, operating system, Python version,
  and runtime package versions.
- GPU memory failures must produce clear user-facing errors.
- CPU fallback, if supported by a future backend, must be explicit and must not
  silently make large jobs appear hung.
- CI must not require GPU, CUDA, model cache, internet access, or AI runtime
  packages.

## Model Download Caveats

Future real backends may require large model files. Before any model download is
enabled or documented:

- The user must explicitly consent.
- Provider/model id and expected cache location must be documented.
- The app must not download models automatically at startup.
- Failed or partial downloads must not break default app workflows.
- Model cache removal and rollback steps must be documented.

## Custom Code and `trust_remote_code` Caveats

Some Unlimited-OCR-style examples rely on custom model code or
`trust_remote_code=True`. Treat this as local execution of third-party code.

Before enabling any such path:

- Pin and review the model repository/revision.
- Explain the custom-code risk in user-facing consent.
- Avoid execution at app startup.
- Keep the runtime opt-in and isolated from default dependencies.
- Provide a rollback path that disables the backend without affecting Tesseract.

## Privacy and Local-First Expectations

Optional advanced OCR must preserve the app's local-first position:

- No external upload by default.
- No screen OCR, automatic capture, global hotkey, background OCR, or ambient
  monitoring.
- No source file paths sent to OCR endpoints.
- No OCR text, rendered image bytes, base64 payloads, or document content in
  logs, diagnostics, or workflow reports by default.
- Temporary rendered page images must be cleaned up after success, failure, and
  cancellation.

## Troubleshooting Checklist

Use this checklist for future optional runtime issues:

- Confirm the default app starts without optional AI runtime packages.
- Confirm advanced OCR consent is valid for the selected provider/model/version.
- Confirm diagnostics show optional dependency status without crashing.
- Confirm endpoint URL is loopback-only when endpoint mode is selected.
- Confirm local server is user-managed and reachable only on loopback, if used.
- Confirm model cache exists only if the selected backend requires it.
- Confirm GPU driver/runtime versions match the future backend documentation.
- Confirm output folder is writable.
- Confirm logs and reports do not contain OCR text or rendered images.
- Confirm Tesseract OCR still works independently.

## Uninstall and Rollback Guidance

Future runtime rollback must support:

- Disabling the experimental backend or dev flag.
- Clearing advanced OCR consent.
- Reverting to Tesseract-only OCR behavior.
- Removing optional runtime packages from the user-managed environment.
- Removing model cache files only when the user explicitly chooses to do so.
- Stopping any user-managed local OCR server outside the app.
- Preserving existing PDF tools and default install behavior.

The app should not manage server lifecycle or delete user-managed model caches
without an explicit future design and user confirmation.
