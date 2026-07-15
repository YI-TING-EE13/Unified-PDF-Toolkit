# Changelog

## Unreleased

- Reworked the existing Advanced OCR roadmap into the canonical source for the
  verified hardware matrix, next validation priorities, known limitations,
  optional enhancements, research directions, rejected approaches, maintenance
  triggers, and evidence required before expanding support claims.
- Added bounded cross-platform discovery for real Linux CPU model names,
  alternate compatible Python interpreters, uv/Conda/pyenv installations outside
  PATH, headless GUI/display state, and actual Tesseract availability. Managed
  plans now use absolute provisioner paths and separate APP, Basic OCR, and
  Unlimited-OCR compatibility plus provider recommendation.
- Added a consent-gated `UV_BOOTSTRAP` prerequisite for otherwise eligible
  devices with no compatible manager. It pins official uv 0.11.28 archives,
  platform-specific sizes and SHA-256 values, installs only under the managed
  runtime, and includes retry, cancellation, smoke verification, and cleanup
  without sudo, PATH, profile, system Python, Driver, or CUDA changes.
- Fixed blocked plans that exposed an install action, emitted unavailable uv
  commands, selected the first NVIDIA GPU for display, or contradicted a valid
  PyTorch cu128 Driver match. Blocked plans are now explicitly informational.
- Completed a real second-device Ubuntu 20.04 validation on GTX 1060 6 GiB with
  low RAM, old system Python, newer Miniforge Python, user-local uv outside PATH,
  CUDA Toolkit 10.1, and a newer Driver. The normal APP/CLI installation and
  Linux suite passed; Unlimited-OCR remained safely blocked and no AI runtime or
  model was installed.

- Hardened the managed Unlimited-OCR final audit with OS-held single-installer
  locking, corrupt-journal quarantine and recovery, existing environment/model
  reuse, atomic state-write retries, junction/symlink escape prevention, bounded
  worker output, cancellation-safe worker restart, subprocess reaping, and
  structured CLI errors. Explicit full cleanup now removes every managed model
  revision and isolated Hugging Face/Transformers cache.
- Fixed managed-path hardening to distinguish an actual managed-directory
  symlink/junction from benign OS ancestor aliases such as macOS `/tmp` and CI
  runner path normalization, preserving cross-platform setup and tests.
- Added an opt-in real-device validation harness covering five OCR layouts,
  repeated unload/reload, cancellation recovery, 50-request resource stability,
  worker/session cleanup, and benchmark capture without logging OCR contents.
- Repaired the local editable project environment by making pytest an explicit
  development dependency, and made Windows CLI output resilient to Unicode,
  spaces, emoji, long paths, and legacy console encodings.
- Added a consent-gated managed Unlimited-OCR deployment framework with
  cross-platform hardware/software inspection, metadata-driven compatibility
  decisions, exact private uv/Conda runtime plans, resumable staged setup,
  pinned model inventory/SHA-256 verification, progress, retry, pause,
  cancellation, recovery, uninstall, and cache cleanup.
- Added a persistent advanced OCR provider with Tesseract fallback, GUI device
  analysis and informed-consent setup, headless `pdf-toolkit ocr` inspection,
  plan, status, setup, and cleanup commands, and APP shutdown handling for
  installer/worker subprocesses.
- Added deterministic plain-text, table, Chinese/English, complex-layout, and
  rotated OCR acceptance assets plus compatibility, security, failure,
  recovery, cache-integrity, provider, and cross-platform tests.
- Added an allowlisted official-source metadata auditor and documented the
  current pinned Unlimited-OCR/model revisions, PyTorch/CUDA resolver policy,
  upstream conflicts, security boundaries, and consented real-device benchmark.
- Fixed managed benchmark journals that omitted classification and dependency
  versions, added targeted legacy-record refresh, corrected Basic OCR benchmark
  metadata access, and hardened persistent-worker restart/unload queue, thread,
  pipe, log, and temporary-session cleanup. PyInstaller now also bundles the two
  standalone private-runtime entrypoint scripts required after installation.
- Added a headless `pdf-toolkit` CLI for direct compression, PDF-to-image, and
  PDF-to-Word jobs plus reusable JSON batch manifests, explicit conflict
  policies, machine-readable summaries, deterministic exit codes, Ctrl+C
  cancellation, and fail-fast operation.
- Added adversarial and resource-lifecycle coverage for encrypted, damaged,
  blank, zero-page, high-page-count, Unicode/emoji/long-path PDFs; permission,
  disk-full, and locked-output failures; cancellation, repeated execution,
  rename/overwrite/skip behavior; and a 60-document handle, process, and memory
  stress run.
- Upgraded CI and release workflows to current action runtimes and added Ruff,
  Bandit, dependency audit, branch coverage, package build, and packaged GUI
  startup/shutdown gates.
- Updated Pillow and build/test dependencies to remove known dependency
  vulnerabilities, validated the built wheel in an isolated environment, and
  raised the enforced branch-coverage baseline to 45 percent.
- Hardened loopback OCR transport validation, worker subprocess cleanup,
  platform file opening, PDF page-count error handling, and actionable disk-full
  and locked-file diagnostics; Bandit now reports no medium-or-higher findings.
- Added Tesseract installed-language diagnostics, including a clear warning when
  Traditional or Simplified Chinese language data is unavailable.
- Hardened repeated PyInstaller builds by safely clearing read-only prior build
  trees, detecting a still-running packaged app, and smoke-testing graceful GUI
  shutdown after packaging.
- Repaired launcher failures caused by incomplete editable-package metadata in `.venv`, pinned the Windows project environment to the installed uv-managed Python runtime, prevented `uv run` from redundantly synchronizing immediately after a successful `uv sync`, and excluded the optional multi-gigabyte OCR runtime from project packaging scans.
- Fixed virtual-environment repair coverage on macOS and Linux, retained the Windows read-only metadata regression test, and deduplicated case-insensitive `site-packages` aliases on macOS.
- Hardened GUI worker shutdown and PyMuPDF document cleanup so closing the app does not leave background worker processes running and error or cancellation paths do not retain PDF file handles; also cleaned static-analysis findings and added lifecycle regression coverage.
- Added architecture-only scaffolding for optional future advanced local AI OCR, including an ADR, OCR backend abstractions, consent validation structures, a fake Unlimited-OCR test backend, and safe optional-readiness diagnostics.
- Added Settings / Recent consent management for future optional advanced local AI OCR without enabling real model inference.
- Added a localhost-only OCR endpoint backend scaffold for future user-managed OCR servers without adding model inference or AI runtime dependencies.
- Added developer-only Document OCR shell wiring, hidden behind `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`, for local fake-backend UI/workflow testing without real model inference.
- Added a manual, non-CI GPU acceptance test plan and run template for future advanced OCR backend validation.
- Added advanced OCR privacy/security review and pre-integration checklist documentation for future real backend work.
- Added optional advanced OCR runtime packaging/install docs and a local endpoint contract for future user-managed runtimes.
- Added an advanced OCR maintainer guide summarizing architecture status, boundaries, and recommended next work.
- Hardened the local OCR endpoint scaffold with stricter mock-only response validation and sanitized transport errors.
- Added mock-only advanced OCR workflow helpers for backend selection, consent gating, output writing, and user-safe error mapping.
- Added a hidden dev-only Document OCR UI shell for fake-backend workflow testing without real model inference or live endpoint calls.
- Added Document OCR production UI design review and readiness checklist documentation.
- Added Document OCR fake-backend smoke test plan and manual run template documentation.
- Pivoted advanced OCR direction toward a user-owned local model runtime and added a safe local model backend scaffold without real inference or AI runtime dependencies.
- Added safe local model OCR runtime settings, readiness diagnostics, and worker-process contract documentation without enabling real inference.
- Added a developer/test-only fake local model worker subprocess prototype to exercise IPC, timeout, cancellation, and response validation without real OCR inference.
- Added an optional experimental local Unlimited-OCR backend path with lazy torch/transformers imports, local model path validation, and an opt-in manual validation script.
- Added an experimental killable Unlimited-OCR worker-process runtime path with timeout handling, JSON response validation, temp page cleanup, and manual validation support.
- Hardened the experimental Unlimited-OCR worker-process runtime with a default single-worker guard, safe busy errors, structured worker error parsing, and stderr redaction.
- Added a user-facing Document OCR tool with Tesseract as the default backend and a gated experimental Local Unlimited-OCR worker option.
- Hardened Document OCR experimental local-model failure messages for missing model path, missing worker Python, busy worker, timeout, unsupported input, and GPU/CUDA readiness failures.
- Hardened the Document OCR experimental GUI smoke path with a manual Tkinter smoke runner and worker-process cancellation propagation.
- Added controlled-beta setup, smoke checklist, release-gate audit, diagnostics readiness hardening, and beta-check smoke automation for Experimental Local Unlimited-OCR.
- Added a uv-only optional runtime setup helper, beta release-candidate notes, and `trust_remote_code` / model revision policy documentation for Experimental Local Unlimited-OCR.
- Added warning-only Experimental Local Unlimited-OCR model revision safety checks for model id allowlist status, revision pinning, local metadata presence, and custom-code consent diagnostics.
- Improved Document OCR and Settings beta copy, and added final beta tester plus packaging dry-run checklists for Experimental Local Unlimited-OCR.
- Added beta release draft and tag readiness review documentation for a future human-approved Experimental Local Unlimited-OCR beta tag.
- Completed a clean local beta artifact build/inspection pass and documented Windows ZIP, installer, wheel, and source distribution boundaries.
- Aligned beta release metadata toward `v0.6.0-beta.1`, using Python package version `0.6.0b1` and installer display version `0.6.0-beta.1`.
- Verified version-aligned beta artifacts using an isolated uv cache, producing `0.6.0b1` Python artifacts and a `0.6.0-beta.1` installer without bundling optional OCR runtime files.
- Fixed cross-platform CI for the beta release by removing a Windows-only path separator assumption in the Unlimited-OCR worker-process payload test and marking future beta/alpha/rc release tags as GitHub prereleases.
- Prepared `v0.6.0-beta.2` metadata with Python package version `0.6.0b2` and installer display version `0.6.0-beta.2` for a clean controlled beta after holding `v0.6.0-beta.1`.
- Verified `v0.6.0-beta.2` artifacts from a clean source snapshot, confirming `0.6.0b2` Python artifacts, a `0.6.0-beta.2` installer, no bundled optional OCR runtime files, and packaged app launch smoke.
- Hardened beta GUI startup, diagnostics output, manual smoke summaries, and PDF-to-Word upstream conversion logs so Tk/Tcl startup failures and shareable diagnostics avoid raw tracebacks and unnecessary local path disclosure.
- Added beginner tutorials for default Tesseract Document OCR and the gated Experimental Local Unlimited-OCR beta workflow.
- Prepared `v0.6.0-beta.3` metadata with Python package version `0.6.0b3` and installer display version `0.6.0-beta.3` as the recommended controlled beta after beta logging and onboarding hardening.
- Verified `v0.6.0-beta.3` artifacts from a clean source snapshot, confirming `0.6.0b3` Python artifacts, a `0.6.0-beta.3` installer, no bundled optional OCR runtime files, and packaged app launch smoke.

## 0.5.0 - 2026-06-19

- Added a tag-driven GitHub Release workflow for Python packages, Windows ZIP bundles, and optional installer artifacts.
- Added an Inno Setup installer script and release checklist.
- Added Batch Queue for mixed sequential jobs across compression, PDF-to-image, and PDF-to-Word workflows.
- Added Diagnostics view for dependency, Tkinter, Tesseract, settings, and output-folder checks.
- Added OCR cleanup options: None, Grayscale, Auto Contrast, and Threshold.
- Added user-facing error suggestions for common OCR, permission, page-range, encrypted-PDF, and missing-file failures.
- Expanded unit tests for batch queue, diagnostics, OCR cleanup, and error suggestions.

## 0.4.0 - 2026-06-18

- Added drag-and-drop support for shared file lists when native Tk drag-and-drop is available.
- Added Cancel buttons and cancellation handling for long-running workflows.
- Added completion reports for long workflows, now emitted as TXT, CSV, and JSON.
- Added shared output conflict behavior: rename, overwrite, or skip.
- Added Settings / Recent view for output behavior and recent inputs, outputs, and reports.
- Added PDF to Word OCR Text mode with configurable Tesseract language and render DPI.
- Added GitHub Actions CI and Windows PyInstaller smoke packaging.
- Added MIT LICENSE and aligned package metadata with Python 3.10+.
- Expanded workflow tests, including Page Manager edit operations and mocked OCR conversion.

## 0.3.0

- Added PDF to Word conversion with Preserve Layout, Text Only, and Page Images modes.
- Added PDF to Word preview and preflight checks.
- Added merged PDF preview and optional post-merge compression.
- Enlarged the application workspace for preview-heavy workflows.
- Added progress feedback for long-running tools.
