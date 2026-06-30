# Local Model OCR Runtime Design

This document defines the preferred future architecture for advanced OCR:
run an optional AI OCR model on the user's own computer. Unified PDF Toolkit is
not planning a hosted OCR service, cloud OCR upload path, or project-operated
server for user documents.

This document is a design boundary and scaffold reference. An experimental real
Baidu Unlimited-OCR local backend path exists, but it is disabled by default,
requires user-managed optional runtime/model files, and is not production-ready.

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
- load/save/clear helpers for safe runtime configuration

The scaffold:

- fits the existing `OcrBackend` contract,
- requires valid advanced OCR consent,
- imports no heavy AI runtime at app startup,
- downloads no model automatically,
- can run experimental local Unlimited-OCR directly or through a one-shot worker
  process only when explicitly configured,
- reports runtime/model-not-configured errors clearly.

## Runtime Configuration

The current settings record stores only safe local runtime hints:

- enabled flag
- runtime mode: `disabled`, `fake_worker`, `local_unlimited_ocr`,
  `worker_process`, or `in_process_future`
- provider/model id
- local model folder path
- device preference: `auto`, `cuda`, or `cpu`
- optional Python executable path for worker-process mode
- optional worker script path

Defaults keep local model OCR disabled. The settings record must not store OCR
text, document content, source file paths, image bytes/base64, rendered page
paths, or output contents.

Settings / Recent may expose these fields for future readiness planning, but it
must not provide a model download button, server start button, or "run model"
action until real inference is separately reviewed.

## Fake Worker Prototype

`fake_worker` mode is a developer/test-only subprocess prototype for local
model IPC. It is not production AI OCR and does not run Baidu Unlimited-OCR.

Current components:

- `src/ocr/local_worker.py` builds sanitized worker payloads, launches a
  one-shot subprocess, enforces timeout/cancellation, parses JSON, and maps
  worker failures to user-safe OCR exceptions.
- `src/ocr/workers/fake_local_model_worker.py` reads JSON from stdin and writes
  deterministic fake OCR results to stdout.

The fake worker request contains page metadata only. It does not include source
paths, OCR text, image bytes/base64, rendered page paths, or document content.
The worker returns deterministic placeholder text so process lifecycle,
timeout, cancellation, malformed response handling, and payload redaction can
be tested without AI dependencies.

The fake worker is launched only when local model OCR is explicitly configured
with `mode="fake_worker"` and valid advanced OCR consent is present. It is not
started on app startup and is not a long-running background worker.

## Experimental Local Unlimited-OCR Backend

`local_unlimited_ocr` mode is an experimental real local backend path for
user-owned Baidu Unlimited-OCR-compatible model directories.

Current behavior:

- requires valid advanced OCR consent;
- requires an explicit existing local model path;
- lazily imports `torch` and `transformers` only when the backend is invoked;
- uses `trust_remote_code=True` because the reference model requires custom
  model code;
- defaults to local files only and does not download model files silently;
- writes rendered page images only to an internal temporary directory and
  removes them when the call returns or fails;
- returns normal `OcrResult` / `OcrPageResult` objects;
- splits upstream `<PAGE>` markers from multi-page inference so page metadata is
  preserved when the model returns page-marked output;
- converts missing dependencies, missing CUDA, missing model path, malformed
  model output, and runtime failures into OCR exceptions with user-safe text.

The implementation follows the upstream Transformers pattern documented by
Baidu/Hugging Face: `AutoTokenizer.from_pretrained(...)`,
`AutoModel.from_pretrained(..., trust_remote_code=True, use_safetensors=True)`,
then `model.infer(...)` for a single image or `model.infer_multi(...)` for
multiple pages. This project does not bundle those optional dependencies or
model files.

Manual validation helper:

```powershell
.\.venv\Scripts\python.exe scripts\manual_unlimited_ocr_local_check.py
```

That command prints readiness only. To run real OCR, maintainers must provide a
local model directory, a small local image/PDF, and explicit acknowledgement:

If Hugging Face dynamic module cache is not writable on the machine, set
`HF_HOME` and `HF_MODULES_CACHE` to a user-writable local directory before the
real run. Those cache locations must remain outside the repo and must not be
committed.

```powershell
$env:HF_HOME = "$env:TEMP\pdf_toolkit_ocr_validation\hf_home"
$env:HF_MODULES_CACHE = "$env:TEMP\pdf_toolkit_ocr_validation\hf_modules"
.\.venv\Scripts\python.exe scripts\manual_unlimited_ocr_local_check.py `
  --model-path C:\path\to\Unlimited-OCR `
  --input C:\path\to\sample.png `
  --device auto `
  --run `
  --acknowledge-experimental-consent
```

To validate the killable worker-process boundary, add
`--runtime-mode worker_process`. The script uses the current Python executable
as the configured worker Python and requires a timeout budget:

```powershell
uv run --no-cache --python .\.venv-ocr-runtime\Scripts\python.exe --no-project `
  python scripts\manual_unlimited_ocr_local_check.py `
  --runtime-mode worker_process `
  --model-path C:\path\to\Unlimited-OCR `
  --input C:\path\to\sample.pdf `
  --device cuda `
  --timeout-seconds 180 `
  --run `
  --acknowledge-experimental-consent
```

The helper does not install dependencies, download models, upload files, print
OCR text, or run in CI.

## Experimental Unlimited-OCR Worker Process

`worker_process` mode runs real local Unlimited-OCR through a one-shot
subprocess instead of inside the app process.

Current behavior:

- requires valid advanced OCR consent;
- requires an explicit existing local model path;
- requires an explicit worker Python executable, normally an optional
  user-managed OCR runtime such as `.venv-ocr-runtime`;
- launches no worker on app startup;
- allows only one active experimental Unlimited-OCR worker by default and
  returns a user-safe busy message for accidental concurrent requests;
- writes temporary controller-owned page PNGs and removes them on success,
  failure, timeout, and cancellation;
- terminates the worker process on timeout/cancellation;
- discards worker stderr, parses structured worker error JSON when available,
  and maps worker failures to user-safe OCR exceptions;
- keeps OCR text, image bytes, source paths, and model paths out of logs and
  user-facing errors by default.

This mode is the preferred experimental path for future safe local inference
because it provides a killable boundary that direct in-process inference does
not have. It is still not production-ready.

Current limitation: in-process `local_unlimited_ocr` inference does not provide
a safe hard timeout or cancellation boundary. If the model hangs inside
Transformers/CUDA execution, prefer `worker_process` mode for experimental
manual validation because it can terminate the subprocess. Do not expose
production cancel semantics for the direct in-process path.

## Readiness Diagnostics

Diagnostics may report:

- whether local model runtime config is disabled or enabled;
- whether the configured local model path exists;
- whether the configured worker Python path exists;
- whether the configured worker script path exists;
- whether experimental local Unlimited-OCR mode has a configured local model
  path and selected device preference;
- optional torch/transformers presence through safe detection only.

Missing model/runtime paths are warning/info states for the optional backend,
not app startup failures. Diagnostics must not download models or start worker
processes.

## Worker Contract

The future worker-process IPC contract is documented in
`docs/runtime/local_model_worker_contract.md`. It defines request payload
limits, temporary file policy, response shape, error shape, timeout/cancel
expectations, and logging restrictions.

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
