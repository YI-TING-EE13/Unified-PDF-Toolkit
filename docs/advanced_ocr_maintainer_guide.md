# Advanced OCR Maintainer Guide

This guide is the maintainer entry point for Unified PDF Toolkit's optional
advanced local OCR work. It summarizes what is implemented, what is scaffolded,
what is fake/developer-only, what is documentation-only, and what must not be
claimed yet.

## Current Status Summary

Update for 2026-07-15: the preferred path is now the consent-gated managed
deployment framework in `src/ocr/deployment/`. It implements environment
inspection, official-metadata compatibility analysis, exact private uv/Conda
plans, resumable model/runtime setup, integrity validation, a persistent worker,
real OCR/benchmark gates, cleanup, GUI/CLI control, and Tesseract fallback. The
framework is implemented and adversarially validated. The development computer
completed the consented private install, five-layout real OCR suite, unload/load
cycles, cancellation recovery, 50-request resource run, and benchmark. This is
device-specific evidence, not broad platform support. See
`docs/runtime/managed_unlimited_ocr.md` and
`docs/testing/managed_unlimited_ocr_validation.md`.

A second physical Ubuntu 20.04 laptop now validates the source bootstrap and
blocked-device path: user-local uv outside PATH and a Miniforge Python 3.12 were
discovered without scanning the disk, the repository synced through its normal
uv workflow, and GTX 1060 / 7.6 GiB RAM produced a consistent `UNSUPPORTED`
informational plan without AI downloads or system changes. This is real SSH
hardware evidence, not a mock and not a Linux inference-success claim.

Advanced OCR support is architecture-first and local-first. The production OCR
behavior remains unchanged: PDF to Word -> OCR Text still uses Tesseract by
default.

Implemented today:

- Managed Unlimited-OCR Environment Inspector, Compatibility Engine,
  Environment Resolver, consent model, Setup Orchestrator, cache manager,
  provider abstraction, persistent private worker, GUI setup, and headless CLI.
- Official-source metadata auditor with pinned source/model revisions, complete
  selected file inventory, weight SHA-256, PyTorch wheel profiles, NVIDIA Driver
  families, stale-metadata blocking, and recorded upstream conflicts.

- OCR backend abstraction and result/request models.
- Tesseract backend wrapper used by the existing PDF to Word OCR Text path.
- Fake Unlimited-OCR backend for tests and developer-only workflow wiring.
- Consent records, settings persistence, and Settings / Recent consent UI.
- Local model backend scaffold for future user-owned Baidu Unlimited-OCR-
  compatible runtime.
- Safe local model runtime settings and readiness diagnostics. These settings
  are disabled by default and do not execute a model.
- Developer/test-only fake local model worker subprocess prototype for IPC,
  timeout, cancellation, and response validation.
- Experimental real local Unlimited-OCR backend path for manually configured
  user-owned model/runtime environments.
- Local endpoint backend scaffold with loopback-only URL validation.
- User-facing Document OCR tool with Tesseract as the default backend and a
  gated experimental Local Unlimited-OCR worker option.
- Developer-only Document OCR UI shell gated by
  `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`.
- Optional advanced OCR diagnostics/readiness checks.
- Manual GPU acceptance test plan and run template.
- Privacy/security review and pre-integration checklist.
- Optional runtime packaging/install docs and local endpoint contract.
- Production Document OCR UI design review and readiness checklist.
- Fake-backend Document OCR smoke test plan and manual run template.
- Controlled-beta setup guide, beta smoke checklist, release-gate audit, and
  manual GUI beta-check runner for Experimental Local Unlimited-OCR.
- Beta release-candidate notes, uv-only optional runtime setup helper, and
  `trust_remote_code` / model revision policy for controlled beta reviewers.
- Warning-only model revision safety checks for model id allowlist status,
  revision pin status, local metadata presence, and `trust_remote_code` consent
  readiness.

Not completed or not supported today:

- Broad production-ready Baidu Unlimited-OCR support across a hardware matrix.
- Consent-gated real install/OCR/benchmark evidence for every target device.
- Bundled GPU OCR runtime.
- Unattended or consent-free model download.
- Production local OCR server.
- In-process Transformers runtime.
- Hosted OCR service or project-operated OCR server.
- Production-ready AI OCR, default AI OCR, or production-ready Unlimited-OCR UI.
- Batch Queue AI OCR jobs.
- Screen OCR, background OCR, global hotkeys, or automatic capture.

## Implemented Milestones

- Architecture scaffold: `src/ocr/`, Tesseract wrapper, fake backend, backend
  exceptions, and lightweight registry.
- Existing OCR preservation: PDF to Word OCR Text still renders pages and uses
  Tesseract as before.
- Consent persistence and UI: consent records can be reviewed, saved, and reset
  through Settings / Recent.
- Local endpoint scaffold: validates loopback-only endpoints and supports
  mockable request/response tests with strict response-shape validation.
- Local model scaffold: represents the preferred future local AI OCR runtime
  path without importing AI runtimes, downloading models, or running inference.
- Local model runtime settings: Settings / Recent can store disabled-by-default
  runtime hints and diagnostics can report path readiness without starting a
  worker or importing AI libraries.
- Fake local model worker prototype: `fake_worker` mode can launch the
  repo-local deterministic fake worker only when explicitly configured and
  consent-gated.
- Experimental local Unlimited-OCR backend: `local_unlimited_ocr` mode can run
  a manually configured local model path through lazy Transformers imports.
- Experimental Unlimited-OCR worker runtime: `worker_process` mode can run the
  same local model through a one-shot subprocess with timeout/cancel kill
  behavior, default single-worker concurrency, and user-safe structured error
  handling when explicitly configured.
- Document OCR tool: user-facing local OCR outputs are available with Tesseract
  as the default backend; the experimental Local Unlimited-OCR option is hidden
  behind `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` and requires
  `worker_process` runtime settings plus consent.
- Developer Document OCR shell: hidden dev tool exercises file selection,
  backend selection, consent gating, progress, cancellation, local TXT/Markdown
  output, user-safe errors, and output actions using only the fake backend.
- Documentation gates: GPU acceptance, security review, optional runtime guide,
  endpoint contract, production UI review, and fake-backend smoke test plan.
- Beta readiness gates: setup/runbook, manual smoke checklist, release-gate
  audit, diagnostics cache/runtime checks, and GUI beta-check automation.
- Beta release-candidate package: uv-only setup helper, beta notes, and
  `trust_remote_code` / model revision policy documentation.

## Key Files and Responsibilities

- `src/ocr/deployment/environment.py`: read-only cross-platform hardware,
  Driver, CUDA, Python, PyTorch, storage, Docker, and WSL inspection.
- `src/ocr/deployment/compatibility.py`: conservative metadata-driven support
  decision; unknown evidence never becomes supported.
- `src/ocr/deployment/resolver.py`: exact argv-only private uv/Conda plan; no
  Driver, system CUDA, PATH, admin, or global Python change.
- `src/ocr/deployment/orchestrator.py`: journaled staged install, retry,
  progress, cancellation, resume, registration, and path-bound cleanup.
- `src/ocr/deployment/providers.py`: provider abstraction, persistent worker,
  health/benchmark lifecycle, and Tesseract fallback.
- `scripts/refresh_unlimited_ocr_metadata.py`: allowlisted read-only upstream
  audit and explicitly reviewed metadata refresh.
- `scripts/validate_managed_unlimited_ocr.py`: opt-in installed-runtime OCR,
  reload, benchmark, and resource-stability validation. It never installs or
  downloads and does not write raw OCR text to its report.

- `src/ocr/models.py`: OCR engine enum and typed request/result models.
- `src/ocr/base.py`: backend protocol.
- `src/ocr/exceptions.py`: OCR-specific error types.
- `src/ocr/registry.py`: lightweight backend registry. Keep heavy imports out
  of module import time.
- `src/ocr/tesseract.py`: Tesseract backend wrapper. Import `pytesseract` only
  when the backend is used.
- `src/ocr/unlimited_fake.py`: deterministic fake backend for tests/dev wiring.
  It must not import AI runtimes or download models.
- `src/ocr/consent.py`: consent model, validation, load/save/reset helpers.
- `src/ocr/local_model.py`: preferred future local model backend scaffold and
  safe runtime settings helpers. It must not import AI runtimes, download
  models, or start worker processes at app startup. The current `fake_worker`
  path is developer/test-only and returns deterministic fake text. The current
  `local_unlimited_ocr` path is experimental real local inference only when
  explicitly configured.
- `src/ocr/model_policy.py`: warning-only beta policy checks for recommended
  model id, optional allowed model id list, revision pin hints, and local model
  metadata presence. It must not access the internet or download models.
- `src/ocr/unlimited_ocr_local.py`: lazy experimental Transformers runner for
  local Baidu Unlimited-OCR model directories. Keep torch/transformers imports
  inside the invoked runtime path only.
- `src/ocr/local_worker.py`: one-shot fake worker controller for sanitized IPC,
  timeout, cancellation, response validation, and user-safe errors for fake and
  experimental Unlimited-OCR worker paths. The real Unlimited-OCR worker path
  uses a default single-worker guard so accidental concurrent GPU jobs fail
  with a busy message instead of starting another model process.
- `src/ocr/workers/fake_local_model_worker.py`: standard-library fake worker
  subprocess target. It must not import AI runtimes or read source documents.
- `src/ocr/workers/unlimited_ocr_worker.py`: experimental one-shot real local
  Unlimited-OCR worker target. It must stay opt-in and must not run at startup.
- `src/ocr/local_endpoint.py`: localhost-only endpoint client scaffold.
- `src/ocr/workflow.py`: mock-only advanced OCR workflow helpers for backend
  selection, consent gating, input loading, TXT/Markdown output writing, and
  user-safe error mapping.
- `src/ui/advanced_ocr_consent.py`: reusable consent dialog.
- `src/tools/settings/tool.py`: Settings / Recent consent UI and future local
  model runtime settings integration.
- `src/tools/ai_ocr_test/tool.py`: developer-only fake AI OCR test workflow
  that uses `src/ocr/workflow.py`.
- `src/tools/pdf2word/tool.py`: existing production PDF to Word OCR path.
- `src/utils/diagnostics.py`: optional advanced OCR readiness diagnostics.
- `scripts/manual_document_ocr_gui_smoke.py`: manual Tkinter smoke runner for
  Tesseract and gated Experimental Local Unlimited-OCR, including beta-check
  summary mode. It must not print OCR text or generated page images.
- `scripts/setup_local_unlimited_ocr_runtime.py`: opt-in uv-only helper for
  creating/updating the optional `.venv-ocr-runtime`. It prints exact commands,
  asks for confirmation unless `--yes` is passed, supports dry-run, and does
  not download model files or modify default dependencies.
- `docs/adr/0001-optional-advanced-ocr-backend.md`: design record.
- `docs/roadmap/advanced_ocr_next_goals.md`: milestone status and future work.
- `docs/testing/advanced_ocr_gpu_acceptance.md`: manual GPU acceptance plan.
- `docs/security/advanced_ocr_security_review.md`: threat model and release
  gates.
- `docs/runtime/advanced_ocr_optional_runtime.md`: optional runtime boundary.
- `docs/runtime/local_model_ocr_runtime.md`: primary future local model runtime
  architecture.
- `docs/runtime/local_model_worker_contract.md`: future worker-process request,
  response, cancellation, timeout, and logging contract.
- `docs/runtime/local_unlimited_ocr_beta_setup.md`: controlled beta setup for
  uv-managed optional runtime, local model path, cache paths, launch commands,
  readiness checks, and cleanup guidance.
- `docs/runtime/local_ocr_endpoint_contract.md`: future endpoint contract.
- `docs/design/document_ocr_ui_review.md`: production Document OCR UX and
  release-gate review.
- `docs/design/document_ocr_production_readiness_checklist.md`: checklist for
  exposing any Document OCR tool outside dev mode.
- `docs/testing/document_ocr_fake_backend_smoke_plan.md`: fake/mock-only smoke
  test plan for a future production Document OCR UI.
- `docs/testing/manual_document_ocr_smoke_template.md`: manual smoke run record
  template that avoids OCR text, image payloads, and document content.
- `docs/testing/document_ocr_beta_smoke_checklist.md`: controlled beta checklist
  for Tesseract, Experimental Local Unlimited-OCR, diagnostics, failure paths,
  cancellation, timeout, and privacy checks.
- `docs/testing/local_unlimited_ocr_beta_release_gate_audit.md`: claims and
  release-gate audit for controlled beta readiness.
- `docs/releases/experimental_local_unlimited_ocr_beta_notes.md`: beta
  release-candidate notes for reviewers and controlled beta users.
- `docs/security/unlimited_ocr_trust_remote_code_policy.md`: custom model-code
  and model revision policy for Experimental Local Unlimited-OCR.

## Behavior Categories

| Category | Current state |
| --- | --- |
| Production behavior | Tesseract-backed PDF to Word OCR Text and Document OCR remain the stable real OCR paths. |
| Managed advanced local | Consent-gated installer/provider framework implemented; each device still requires successful real OCR and benchmark acceptance. |
| Scaffold | OCR backend abstraction, consent model, diagnostics, local model backend/settings, local endpoint client. |
| Fake/dev-only | Fake Unlimited-OCR backend and hidden Document OCR shell. |
| Fake worker/dev-only | Local model `fake_worker` subprocess path for IPC lifecycle tests. |
| Experimental real local | `local_unlimited_ocr` direct mode and gated `worker_process` one-shot subprocess mode for user-managed local model/runtime environments. |
| Documentation-only | GPU acceptance, security review, optional runtime guide, endpoint contract, production UI review, fake-backend smoke plan. |
| Not supported | Production Unlimited-OCR support, bundled GPU OCR runtime, automatic model download, hosted OCR service, production endpoint OCR, screen OCR, Batch Queue AI OCR. |

## Tesseract Remains the Default

PDF to Word -> OCR Text and the Document OCR tool must continue to default to
Tesseract. Future advanced OCR work must not change default OCR behavior unless
a separate product decision and migration plan explicitly approve it.

## User-Facing Document OCR Tool

`src/tools/document_ocr/tool.py` exposes a normal Document OCR tool for local
TXT/Markdown outputs. It is safe to show because the default backend is
Tesseract.

The experimental Local Unlimited-OCR option is visible only when:

- `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` is set;
- Settings / Recent contains valid advanced OCR consent;
- local model runtime settings are enabled with `mode="worker_process"`;
- local model path and worker Python are explicitly configured by the user.

The tool must not expose the direct in-process mode, download models, start
workers at app startup, upload files, or make AI OCR the default.

The shared workflow maps missing model path, missing worker Python, missing
consent, busy worker, timeout, unsupported input, and GPU/CUDA failures to
user-safe messages without printing source paths, OCR text, image payloads,
model cache paths, or document content.

Preserve these existing behaviors:

- User-selected PDF files.
- Page range handling.
- Render DPI handling.
- `prepare_ocr_image` preprocessing behavior.
- DOCX output behavior.
- User-facing Tesseract dependency/error semantics.

## Consent Settings

Consent records are stored through existing JSON settings helpers and include:

- provider
- model id
- consent text version
- acknowledgement of model download risk
- acknowledgement of custom-code or `trust_remote_code` risk
- acknowledgement of GPU/VRAM use
- acknowledgement of temporary rendered page images
- timestamp

Changing provider, model id, or consent text version invalidates prior consent.
Consent records must not store OCR text, rendered page images, source file
paths, output contents, or document content.

## Developer-Only Document OCR Shell

The Document OCR shell is hidden by default. To expose it in a development
session, set:

```powershell
$env:PDF_TOOLKIT_ENABLE_DEV_TOOLS = "1"
```

Then launch the app normally. The sidebar should include:

```text
[Dev] Document OCR Shell
```

This tool:

- Uses only `FakeUnlimitedOcrBackend`.
- Shows a backend selection control, but exposes only the fake backend.
- Keeps local endpoint mode out of the UI; endpoint coverage remains
  unit-test/mock-only until a later reviewed milestone.
- Requires valid advanced OCR consent.
- Writes deterministic local TXT/Markdown placeholder outputs.
- Supports progress and cancellation.
- Displays OCR failures through `user_safe_ocr_error_message()`.
- Does not run real inference.
- Does not call the local endpoint backend.
- Does not import torch, transformers, SGLang, CUDA, or model runtimes.
- Does not upload files or OCR text.

## Mock-Only Workflow Helpers

`src/ocr/workflow.py` contains reusable pieces for future UI integration:

- `AdvancedOcrBackendSelection` and `AdvancedOcrBackendChoice` model safe
  backend choices.
- `fake_backend_selection()` selects the fake backend for developer tests.
- `local_endpoint_mock_selection()` requires an injected transport so tests can
  exercise the endpoint path without live network calls.
- `require_consent_for_selection()` validates consent before backend creation.
- `run_advanced_ocr_workflow()` loads selected local PDFs/images, creates an OCR
  request, runs the selected mock-safe backend, and writes local outputs.
- `write_ocr_outputs()` writes TXT/Markdown output files without putting OCR
  text into workflow reports.
- `user_safe_ocr_error_message()` maps consent, backend, malformed response,
  timeout, transport, and unsupported-file failures to user-safe text.

This helper layer is not a production Document OCR feature. It is intended to
let future UI work share backend selection, consent, output, and error handling
without adding real inference or live endpoint calls.

## Local Model Runtime Direction

The preferred future advanced OCR path is local model execution on the user's
own computer. Unified PDF Toolkit should not become a hosted OCR service, and
the project does not plan to operate a server for users.

`src/ocr/local_model.py` currently provides only a scaffold:

- `LocalModelOcrBackend`
- `LocalModelRuntimeConfig`
- provider/model constants for the future Baidu Unlimited-OCR-compatible path
- load/save/clear helpers for disabled-by-default runtime configuration

The scaffold requires advanced OCR consent and then reports disabled,
unsupported-mode, or missing-runtime configuration errors. It does not import
torch, transformers, SGLang, CUDA, or model code; it does not download models,
start a worker process, or run inference.

Settings / Recent can store safe runtime planning fields:

- enabled flag
- runtime mode: `disabled`, `fake_worker`, `local_unlimited_ocr`,
  `worker_process`, or `in_process_future`
- provider/model id
- optional model revision pin
- local model folder path
- device preference: `auto`, `cuda`, or `cpu`
- optional future worker Python executable path
- optional future worker script path

These settings must not store OCR text, document content, source paths, image
bytes/base64, rendered page paths, or output contents. Saving them does not
make it the default OCR engine.

Future real local model support should prefer a worker process first. An
in-process runtime is allowed only after security, dependency, packaging, and
manual GPU acceptance review.

### Fake Local Model Worker

`src/ocr/local_worker.py` and `src/ocr/workers/fake_local_model_worker.py`
implement a developer/test-only subprocess prototype.

It does:

- launch a one-shot fake worker only when `mode="fake_worker"` is explicitly
  configured;
- require valid advanced OCR consent through `LocalModelOcrBackend`;
- send sanitized JSON over stdin;
- parse JSON from stdout;
- enforce timeout and cancellation by terminating the subprocess;
- validate response shape before returning `OcrResult`;
- return deterministic placeholder page text.

It does not:

- run real Unlimited-OCR inference;
- download models;
- import torch, transformers, SGLang, CUDA, or model code;
- read source PDF/image paths for OCR;
- start on app startup;
- run as a background worker.

### Experimental Local Unlimited-OCR Backend

`local_unlimited_ocr` mode is the first real local model backend path. It is
still experimental and disabled by default.

It does:

- require valid advanced OCR consent;
- require explicit local runtime configuration and an existing local model path;
- lazy-import torch and transformers only when invoked;
- load the model with `trust_remote_code=True` for the configured local model
  directory;
- run `model.infer(...)` for one page or `model.infer_multi(...)` for multiple
  pages when the model exposes those APIs;
- write temporary page PNGs under an internal temporary directory and clean them
  up automatically;
- return `OcrResult` / `OcrPageResult` values;
- keep OCR text out of diagnostics and workflow reports by default.

It does not:

- install torch, transformers, CUDA, SGLang, or model packages;
- download model files silently;
- run on app startup;
- upload files or OCR text;
- make advanced OCR the default engine;
- claim production readiness.

Manual readiness and optional real-model validation live in
`scripts/manual_unlimited_ocr_local_check.py`.

### Experimental Unlimited-OCR Worker Process

`worker_process` mode is the preferred experimental boundary for future local
model inference because it can terminate the subprocess on timeout or
cancellation.

It does:

- require valid advanced OCR consent;
- require explicit local model path and worker Python executable settings;
- use the repo-local `src/ocr/workers/unlimited_ocr_worker.py` by default;
- allow one active worker by default and return a safe busy error for
  concurrent attempts;
- write temporary controller-owned page PNGs and clean them up;
- lazy-load torch/transformers inside the worker process only;
- return normalized `OcrResult` page results through JSON stdout;
- discard worker stderr, parse safe structured worker error JSON, and surface
  user-safe errors for timeout, invalid JSON, non-zero exit, missing model path,
  busy worker state, and runtime failures.

It does not:

- download models;
- run on app startup;
- run as a long-lived background worker;
- expose production AI OCR UI;
- change the default Tesseract OCR path.

## Production Document OCR UI Review

Production-ready AI OCR in Document OCR is still future work. The release-gate
design review is documented in `docs/design/document_ocr_ui_review.md`, with the
checklist in `docs/design/document_ocr_production_readiness_checklist.md`.

Before the experimental Local Unlimited-OCR option is promoted beyond a gated
experimental path, maintainers must verify:

- Consent UX is reviewed and blocks stale/missing consent.
- Local-only guarantees are visible and test-backed.
- Endpoint mode, if exposed, remains loopback-only and sends no source paths.
- OCR text, image bytes/base64 payloads, and document content stay out of logs,
  diagnostics, and reports by default.
- Diagnostics/readiness UX is clear without making optional AI dependencies
  mandatory.
- Progress, cancellation, output correctness, accessibility basics, and
  user-safe error handling are tested.
- Fake-backend smoke testing is completed with the documented smoke plan and
  manual template.
- Manual acceptance and rollback/hide-feature procedures are complete.

The design review does not approve real model integration, GPU OCR, endpoint
productionization, screen OCR, background OCR, file upload, or Batch Queue AI
OCR.

## Local Endpoint Backend Scaffold

The local endpoint backend is a client scaffold for future user-managed local
OCR servers. It is not production OCR support and is not the primary advanced
OCR product direction.

It does:

- Validate endpoint URLs as loopback-only by default.
- Require valid advanced OCR consent.
- Use in-memory image payload expectations.
- Avoid sending source file paths.
- Support mockable tests with no live server dependency.
- Validate response page count, required fields, page-number order, confidence
  type, warning shape, and metadata shape.
- Surface timeout/backend errors through sanitized OCR exceptions.

It does not:

- Start or manage a server.
- Download models.
- Call a real server by default.
- Support remote/public/private-LAN endpoints.
- Provide a production OCR server implementation.
- Make endpoint OCR available in normal user workflows.

## Diagnostics Coverage

Diagnostics may report:

- Python/runtime information.
- torch importability only if installed.
- transformers importability only if installed.
- CUDA availability only when torch is installed.
- GPU name/VRAM if safely detectable.
- model cache path presence if detectable.
- local endpoint URL validity.
- local model runtime disabled/enabled status and configured path readiness.
- fake worker mode status as developer/test-only readiness.
- experimental local Unlimited-OCR mode status, local model path readiness, and
  device preference.

Diagnostics must not require GPU, CUDA, internet, model download, OCR server,
torch, transformers, or SGLang. Missing optional AI pieces are warning/info
states, not app startup failures.

For enabled local Unlimited-OCR settings, diagnostics also report warning-only
model policy status: allowed model id, revision pin, local metadata presence,
and valid `trust_remote_code` consent for the configured model id.

## Privacy and Security Boundaries

Keep these boundaries intact:

- No external upload by default.
- No hosted OCR service or project-operated user OCR server.
- No source file paths sent to OCR endpoints.
- No OCR text, rendered image bytes, base64 payloads, or document content in
  logs, diagnostics, or workflow reports by default.
- No screen OCR, global hotkey, automatic capture, or background OCR.
- No model download or custom code execution without explicit consent and
  documentation.
- No heavy AI runtime imports at app startup.
- No torch, transformers, SGLang, CUDA, model files, or server runtimes in
  default dependencies or default installer.
- Temporary rendered page images must be cleaned up in every real backend path.

## Validation Commands

Preferred validation:

```powershell
uv sync --dev
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python verify_install.py
uv run --no-sync python -m compileall -q src tests verify_install.py scripts
uv run --no-sync python scripts/validate_managed_unlimited_ocr.py `
  --reload-cycles 2 --stress-iterations 50 --output <report.json>
```

For a final source-checkout gate, bootstrap uv from its official instructions
and run the repository's documented `uv sync --dev --python <compatible-python>`
workflow. A temporary `python -m venv` may be used only for diagnosis and must
not be described as the repository's final installation result. If an already
synced repo-local environment must be used for offline diagnosis, the equivalent
commands are:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe verify_install.py
.\.venv\Scripts\python.exe -m compileall -q src tests verify_install.py scripts
```

Always run:

```powershell
git status --short
git diff --stat
git diff --check
```

`README (1).md` is an existing untracked local file in this workspace. Do not
modify, stage, commit, delete, rename, or push it unless the user explicitly
changes that instruction.

## Do Not Claim Yet

Do not claim:

- Real Unlimited-OCR inference is broadly production-ready.
- GPU OCR is supported beyond the specifically validated device/runtime matrix.
- The app bundles AI models or a GPU runtime.
- Endpoint OCR is production-ready.
- A production local OCR server is included.
- The project operates an OCR server for users.
- Screen OCR exists.
- Background OCR exists.
- Batch Queue supports AI OCR.
- The default installer includes torch, transformers, SGLang, CUDA, or models.
- Saving consent enables real AI OCR in the current app.
- Saving local runtime settings makes AI OCR the default engine.

## Future Work Decision Table

| Future item | Prerequisites | Main risks | Recommended order |
| --- | --- | --- | --- |
| Mock-only Document OCR UI shell | Existing workflow helpers, fake backend, mocked local endpoint transport, consent tests | User confusion if exposed as production, output/report leakage | 1 |
| Local model fake worker UI smoke path | Fake worker prototype, workflow helpers, consent tests, fake smoke template | User confusion if mistaken for real OCR, output/report leakage | 2 |
| Experimental local Unlimited-OCR manual validation | Local model backend, optional runtime docs, manual script, local model files, GPU/runtime access | GPU/runtime mismatch, custom-code execution risk, model output drift | 3 |
| Worker-process production hardening | Experimental worker process, runtime settings, worker contract, security checklist, manual acceptance plan | Process lifecycle bugs, payload leakage, dependency bloat, model download risk, custom-code execution risk | 4 |
| Promote Document OCR AI option | Stable backend selection, consent gate, output writer tests, fake/backend real workflow smoke, runtime readiness UX | User confusion, OCR text in reports, partial output handling | 5 |
| Local endpoint productionization | Security checklist, endpoint contract, fake UI tests, short-timeout error handling | Data leakage to non-loopback hosts, payload logging, server compatibility drift | 5 |
| Batch Queue integration | Interactive workflow stable, cancellation/report-redaction tests, consent reuse | Background-like expectations, report leakage, large-job cancellation | 6 |
| In-process Transformers prototype | Security approval, pinned model review, optional runtime docs, manual GPU acceptance | `trust_remote_code`, dependency bloat, GPU instability, startup imports | 7 |
| User-facing docs/examples | Real backend implemented and reviewed, privacy checks passed, rollback documented | Overclaiming support, unclear hardware/runtime expectations | 8 |

Recommended next milestone: repeat the managed install and validation on at
least one different Windows NVIDIA GPU and one Linux NVIDIA system, then add
versioned OCR-quality evaluation with representative documents before widening
the current controlled device/runtime support claim.
