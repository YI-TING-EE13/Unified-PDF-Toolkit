# Document OCR Production UI Review

## Scope

This review defines the gates and user experience requirements for eventually
promoting the hidden developer-only Document OCR shell into a production
user-facing Document OCR tool.

This is documentation only. It does not expose production AI OCR, add real
Unlimited-OCR inference, download models, start servers, call endpoints, add AI
runtime dependencies, add screen OCR, add background OCR, upload files, or add
Batch Queue integration.

The intended future AI OCR product direction is local model execution on the
user's own computer. Unified PDF Toolkit should not become a hosted OCR service
and does not plan to operate a server for user documents.

## Current Dev-Only Status

The current Document OCR shell is hidden unless
`PDF_TOOLKIT_ENABLE_DEV_TOOLS=1` is set. It is for developer/testing use only.

Current behavior:

- Uses only the deterministic fake Unlimited-OCR backend.
- Exercises file selection, output folder selection, TXT/Markdown output
  options, backend selection, consent gating, progress/cancel behavior, output
  actions, and user-safe error display.
- Does not call the local endpoint backend from the UI.
- Does not run real model inference, download models, import AI runtimes, start
  servers, upload files, perform screen OCR, or run background OCR.

## Intended Production User Value

A future production Document OCR tool should help users extract structured text
from PDFs and images when the existing Tesseract-backed PDF to Word OCR Text
mode is insufficient.

The production value should be:

- Explicit file-based document OCR, not ambient capture.
- Local-first processing with clear user control.
- Clear fallback to existing Tesseract OCR where appropriate.
- User-visible output files that can be inspected, moved, or deleted normally.
- Transparent readiness and consent requirements before advanced OCR runs.

## Supported Inputs

Initial production scope should be explicit user-selected files only:

- PDF files.
- Common image files: PNG, JPEG, TIFF, BMP.

Out of scope for first production exposure:

- Screen OCR.
- Clipboard OCR.
- Camera capture.
- Folder watching.
- Background OCR.
- Automatic OCR of recent files.
- Batch Queue integration.

## Output Formats

The first production UI should keep outputs simple and local:

- TXT for plain OCR text.
- Markdown for page-structured text.

Potential later formats:

- JSON with page metadata.
- DOCX only after formatting expectations are reviewed.

Output requirements:

- User chooses an output folder before execution.
- Existing output conflict behavior should follow the repo's shared output
  policy where practical.
- Workflow reports must not include OCR text by default.
- Logs must not include OCR text, image bytes, base64 payloads, or source
  document content.

## Backend Choices

Production UI must present only reviewed backends.

Possible future choices:

- Tesseract fallback or existing Tesseract OCR path.
- Local model backend running on the user's own computer.
- Worker-process local model runtime as the preferred first real AI path.
- In-process Transformers backend only after separate security approval.
- Local endpoint backend only as an advanced/developer loopback option for a
  user-managed local OCR runtime.

Do not expose yet:

- Real Baidu Unlimited-OCR inference.
- GPU OCR claims.
- Remote endpoint targets.
- Private LAN endpoint targets.
- Public internet endpoint targets.
- SGLang/vLLM/Transformers server launchers.
- Unreviewed local endpoint calls.
- Hosted OCR service choices.

The local endpoint option, if added, must:

- Default to `http://127.0.0.1:<port>`.
- Reject non-loopback hosts.
- Reject `0.0.0.0`, public IPs, private LAN IPs, domains, file paths, missing
  ports, and non-http schemes.
- Send in-memory image payloads only.
- Never send source PDF/image paths.
- Use short timeouts and user-safe errors.

## Consent UX

Advanced OCR must be blocked until valid consent exists for the selected
provider/model pair and consent text version.

The production UI must make these acknowledgements explicit:

- Advanced local AI OCR is experimental.
- Current app builds may not include real Unlimited-OCR inference.
- Future model use may require a large model download.
- Future model use may execute model custom code or `trust_remote_code`.
- Future model use may require GPU/VRAM.
- PDFs may be rendered into temporary local page images.
- Files and OCR text must not be uploaded by this feature.

Consent requirements:

- Cancel or decline leaves consent invalid.
- Provider/model id changes require renewed consent.
- Consent text version changes require renewed consent.
- Consent records must not store OCR text, rendered page images, source file
  paths, output contents, or document content.

## Diagnostics and Readiness UX

Production UI must surface readiness before execution without making optional
dependencies mandatory.

Readiness should cover:

- Python/runtime baseline.
- Optional torch importability only if installed.
- Optional transformers importability only if installed.
- CUDA availability only when torch is installed.
- GPU name and VRAM if safely detectable.
- Local model cache presence if detectable.
- Endpoint URL validity.
- Endpoint reachability only through explicit short-timeout checks that send no
  document content.

Missing optional AI pieces should be warnings or blocking messages for the
selected backend, not app startup failures.

## Error Handling UX

Errors must be user-safe, actionable, and content-free.

Required error categories:

- Consent missing or stale.
- Backend unavailable.
- Missing optional dependency.
- Local endpoint timeout.
- Local endpoint connection failure.
- Malformed endpoint response.
- Unsupported input type.
- Output folder permission or conflict failure.
- User cancellation.

Error messages must not include:

- OCR text.
- Document content.
- Rendered image bytes.
- Base64 payloads.
- Source file paths unless already visible in the user's selected file list and
  necessary for basic file-level status.

## Progress and Cancel UX

Production UI should show:

- Current file.
- Page preparation progress.
- OCR progress when available.
- Output writing progress.
- Cancel button for long-running work.

Cancellation requirements:

- Cancelling must stop future pages/files where possible.
- Partial output behavior must be clear.
- Temporary files/images must be cleaned up.
- Cancellation reports must not include OCR text or rendered image content.

## Local-First and Privacy Messaging

Production UI copy should clearly state:

- Processing is local-first.
- The app does not upload files or OCR text for this feature.
- Future AI OCR is intended to run on the user's own computer.
- The project does not operate a hosted OCR server for users.
- Local endpoint mode, if enabled, is loopback-only.
- User-managed model runtimes are optional and not bundled in the default app.
- Tesseract remains the default existing OCR path unless the user opts into an
  advanced OCR feature.

Avoid claims that are not implemented:

- Do not claim real Unlimited-OCR inference is supported.
- Do not claim GPU OCR is supported.
- Do not claim endpoint OCR is production-ready before release gates pass.
- Do not claim the app bundles AI models or GPU runtime.
- Do not claim screen OCR exists.
- Do not claim Batch Queue supports AI OCR.

## Experimental Labeling

Before a stable release, production UI should use restrained labeling:

- "Experimental local Document OCR"
- "Optional advanced OCR"
- "Requires explicit consent"

Do not use labels that imply cloud service behavior, automatic capture, or
guaranteed model availability.

## What Must Remain Hidden or Dev-Only

Keep these hidden until separately approved:

- Developer-only fake backend selector details.
- Mock local endpoint transport controls.
- Debug payload inspection.
- Raw OCR request/response dumps.
- GPU/model/server test hooks.
- Any option that would permit non-loopback endpoints.
- Any screen OCR or background OCR affordance.

## Release Gates Before Production Exposure

A production Document OCR tool must not be exposed until all gates pass:

- Product approval for experimental user-facing advanced OCR.
- Consent UX reviewed and tested.
- Local-first privacy review completed for the chosen backend.
- Security checklist completed for model/runtime/backend path.
- Endpoint loopback policy verified if endpoint mode is exposed.
- No source path leakage to backend payloads.
- No OCR text, image bytes, base64 payloads, or document content in logs or
  workflow reports by default.
- Diagnostics/readiness UX reviewed.
- Unit tests for backend selection, consent, output writing, cancellation, and
  error mapping.
- UI smoke tests using fake backend.
- Manual GPU or endpoint acceptance completed for any real backend path.
- Rollback or feature-hide switch documented.
- User-facing docs updated without overstating support.
