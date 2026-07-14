# Stability and Resilience Test Matrix

This matrix defines the P0-P2 quality gates for desktop, headless, and release
work. Automated cases are designed to be deterministic and safe on Windows,
macOS, Linux, and CI; hazardous operating-system failures are injected rather
than filling a real disk or changing machine-wide permissions.

## P0: release-blocking safety

| Risk | Automated evidence | Release evidence |
| --- | --- | --- |
| Known dependency vulnerability | `pip-audit --skip-editable` | CI quality job must report no known vulnerability. |
| Encrypted, damaged, or zero-page PDF | `AdversarialPdfTests` | Error must be actionable and contain no traceback. |
| Permission denied, disk full, or locked output | `IoFailureTests` injects `EACCES`/`ENOSPC` and a sharing violation | GUI checklist repeats on a disposable output location. |
| File/document handles retained after failure | `ResourceLifecycleTests` and `IoFailureTests` | Existing outputs must be deletable after failure. |
| Packaged app cannot start or close | `smoke_packaged_app.ps1` plus launcher tests | Build and smoke twice on the same path. |
| Stale read-only package tree blocks rebuild | launcher static regression plus repeated physical build | Wrapper clears only verified build children and refuses unsafe cleanup paths. |
| Security regression | Ruff, Bandit `-ll`, loopback endpoint tests | CI quality job must pass before packaging. |
| Incorrect prerelease metadata | Release workflow prerelease expression | Beta/alpha/rc releases must never be marked latest. |

## P1: workflow resilience

| Risk | Automated evidence |
| --- | --- |
| Blank or image-only PDF | blank-page preflight test |
| Very large page count | synthetic 1,000-page PDF preflight with sparse page selection |
| Chinese, spaces, Emoji, and long filenames | Unicode PDF-to-DOCX round-trip |
| Rename, overwrite, and skip conflicts | deterministic conflict policy test |
| Cancellation during a queue or final job | GUI batch cancellation and headless final-job cancellation tests |
| Repeated execution | three consecutive merge outputs plus repeated PyInstaller build |
| 50-100 document resource growth | 60-file merge with RSS, open-file, handle/FD, and child-process assertions |
| Headless operation without Tk | CLI import subprocess asserts `tkinter` is not loaded |
| Invalid manifest or command values | JSON shape, conflict type, operation, DPI, and exit-code tests |

## P2: maintainability and diagnostics

| Goal | Gate |
| --- | --- |
| Branch coverage | `coverage report` with `fail_under = 45`; current suite remains above the gate. |
| OCR readiness | Diagnostics lists installed Tesseract languages and warns when `chi_tra`/`chi_sim` is absent. |
| Reproducible automation | JSON manifests resolve relative paths from their own folder and emit machine-readable reports. |
| Package integrity | Build wheel/sdist and run `uv tool run --from <wheel> pdf-toolkit --version`. |
| Cross-platform support | Unit, install, compile, and package builds run on Windows, macOS, and Ubuntu. |

## Safe manual follow-up

- Use a small disposable volume or quota-limited test directory for a real
  disk-full scenario; never fill the system drive.
- Use a disposable folder with deliberately restricted ACLs for a real
  permission test, then restore or delete it.
- Hold only a generated output copy open in another program for the file-lock
  check; do not use irreplaceable documents.
- For memory testing, use synthetic documents with no private content and retain
  the report plus process measurements rather than the source files.
- On each supported desktop OS, close the GUI during an active multi-file job
  and confirm no PDF Toolkit, Python, OCR worker, or child process remains.
