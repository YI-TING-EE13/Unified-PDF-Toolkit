# Advanced OCR Maintainer Guide

This guide is the maintainer entry point for Unified PDF Toolkit's optional
advanced local OCR work. It summarizes what is implemented, what is scaffolded,
what is fake/developer-only, what is documentation-only, and what must not be
claimed yet.

## Current Status Summary

Advanced OCR support is architecture-first and local-first. The production OCR
behavior remains unchanged: PDF to Word -> OCR Text still uses Tesseract by
default.

Implemented today:

- OCR backend abstraction and result/request models.
- Tesseract backend wrapper used by the existing PDF to Word OCR Text path.
- Fake Unlimited-OCR backend for tests and developer-only workflow wiring.
- Consent records, settings persistence, and Settings / Recent consent UI.
- Local endpoint backend scaffold with loopback-only URL validation.
- Developer-only fake AI OCR workflow gated by
  `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`.
- Optional advanced OCR diagnostics/readiness checks.
- Manual GPU acceptance test plan and run template.
- Privacy/security review and pre-integration checklist.
- Optional runtime packaging/install docs and local endpoint contract.

Not implemented today:

- Real Baidu Unlimited-OCR inference.
- GPU OCR.
- Model download.
- Production local OCR server.
- In-process Transformers runtime.
- AI OCR / Document OCR production sidebar tool.
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
- Developer fake workflow: hidden dev tool exercises file selection, progress,
  cancellation, local TXT/Markdown output, and output actions using only the
  fake backend.
- Documentation gates: GPU acceptance, security review, optional runtime guide,
  and endpoint contract.

## Key Files and Responsibilities

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
- `src/ocr/local_endpoint.py`: localhost-only endpoint client scaffold.
- `src/ui/advanced_ocr_consent.py`: reusable consent dialog.
- `src/tools/settings/tool.py`: Settings / Recent consent UI integration.
- `src/tools/ai_ocr_test/tool.py`: developer-only fake AI OCR test workflow.
- `src/tools/pdf2word/tool.py`: existing production PDF to Word OCR path.
- `src/utils/diagnostics.py`: optional advanced OCR readiness diagnostics.
- `docs/adr/0001-optional-advanced-ocr-backend.md`: design record.
- `docs/roadmap/advanced_ocr_next_goals.md`: milestone status and future work.
- `docs/testing/advanced_ocr_gpu_acceptance.md`: manual GPU acceptance plan.
- `docs/security/advanced_ocr_security_review.md`: threat model and release
  gates.
- `docs/runtime/advanced_ocr_optional_runtime.md`: optional runtime boundary.
- `docs/runtime/local_ocr_endpoint_contract.md`: future endpoint contract.

## Behavior Categories

| Category | Current state |
| --- | --- |
| Production behavior | Tesseract-backed PDF to Word OCR Text remains the only real OCR path. |
| Scaffold | OCR backend abstraction, consent model, diagnostics, local endpoint client. |
| Fake/dev-only | Fake Unlimited-OCR backend and hidden fake AI OCR workflow. |
| Documentation-only | GPU acceptance, security review, optional runtime guide, endpoint contract. |
| Not supported | Real Unlimited-OCR inference, GPU OCR, model download, production endpoint OCR, screen OCR, Batch Queue AI OCR. |

## Tesseract Remains the Default

PDF to Word -> OCR Text must continue to default to Tesseract. Future advanced
OCR work must not change default OCR behavior unless a separate product decision
and migration plan explicitly approve it.

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

## Developer-Only Fake AI OCR Tool

The fake AI OCR workflow is hidden by default. To expose it in a development
session, set:

```powershell
$env:PDF_TOOLKIT_ENABLE_DEV_TOOLS = "1"
```

Then launch the app normally. The sidebar should include:

```text
[Dev] Fake AI OCR Test
```

This tool:

- Uses only `FakeUnlimitedOcrBackend`.
- Requires valid advanced OCR consent.
- Writes deterministic local TXT/Markdown placeholder outputs.
- Supports progress and cancellation.
- Does not run real inference.
- Does not call the local endpoint backend.
- Does not import torch, transformers, SGLang, CUDA, or model runtimes.
- Does not upload files or OCR text.

## Local Endpoint Backend Scaffold

The local endpoint backend is a client scaffold for future user-managed local
OCR servers. It is not production OCR support.

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

Diagnostics must not require GPU, CUDA, internet, model download, OCR server,
torch, transformers, or SGLang. Missing optional AI pieces are warning/info
states, not app startup failures.

## Privacy and Security Boundaries

Keep these boundaries intact:

- No external upload by default.
- No source file paths sent to OCR endpoints.
- No OCR text, rendered image bytes, base64 payloads, or document content in
  logs, diagnostics, or workflow reports by default.
- No screen OCR, global hotkey, automatic capture, or background OCR.
- No model download or custom code execution without explicit consent and
  documentation.
- No heavy AI runtime imports at app startup.
- No torch, transformers, SGLang, CUDA, model files, or server runtimes in
  default dependencies or default installer.
- Temporary rendered page images must be cleaned up in any future real backend.

## Validation Commands

Preferred validation:

```powershell
uv run python -m unittest discover -s tests -v
uv run python verify_install.py
uv run python -m compileall -q src tests verify_install.py scripts
```

In this local checkout, if `uv` or the requested `..venv` path is unavailable,
use the repo-local venv equivalent:

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

- Real Unlimited-OCR inference is supported.
- GPU OCR is supported.
- The app bundles AI models or a GPU runtime.
- Endpoint OCR is production-ready.
- A production local OCR server is included.
- Screen OCR exists.
- Background OCR exists.
- Batch Queue supports AI OCR.
- The default installer includes torch, transformers, SGLang, CUDA, or models.
- Saving consent enables real AI OCR in the current app.

## Future Work Decision Table

| Future item | Prerequisites | Main risks | Recommended order |
| --- | --- | --- | --- |
| Local endpoint productionization | Security checklist, endpoint contract, fake UI tests, short-timeout error handling | Data leakage to non-loopback hosts, payload logging, server compatibility drift | 1 |
| AI OCR / Document OCR sidebar tool | Stable backend selection, consent gate, output writer tests, fake backend UI smoke | User confusion, OCR text in reports, partial output handling | 2 |
| Batch Queue integration | Interactive workflow stable, cancellation/report-redaction tests, consent reuse | Background-like expectations, report leakage, large-job cancellation | 3 |
| In-process Transformers prototype | Security approval, pinned model review, optional runtime docs, manual GPU acceptance | `trust_remote_code`, dependency bloat, GPU instability, startup imports | 4 |
| User-facing docs/examples | Real backend implemented and reviewed, privacy checks passed, rollback documented | Overclaiming support, unclear hardware/runtime expectations | 5 |

Recommended next milestone: productionize the local endpoint path only as a
fake/mocked integration first, then add a user-facing Document OCR tool using
fake/local mock backends before any real model runtime is introduced.
