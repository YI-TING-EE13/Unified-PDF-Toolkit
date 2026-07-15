# Managed Unlimited-OCR Validation Record

Date: 2026-07-15

## Scope and current gate

This record covers implementation, non-destructive framework validation, and a
consented end-to-end installation on the development computer. The user accepted
all six plan-bound disclosures before setup. The APP installed only under its
private `%LOCALAPPDATA%` root; no Driver, system CUDA, PATH, global Python, or
administrator-level change was made.

## Development computer detection

- OS: Windows 11, build 26200, AMD64.
- CPU: Intel Core i5-13600K family, 14 physical / 20 logical cores.
- RAM: 63.8 GiB total.
- GPU: NVIDIA GeForce RTX 3060, 12 GiB VRAM, compute capability 8.6.
- NVIDIA Driver: 610.47; CUDA Driver API: 13.3.
- System CUDA Toolkit: 12.2; detected but not selected or modified.
- APP Python: CPython 3.12.12 in the project `.venv`.
- Provisioners: uv 0.9.18 and Conda 25.3.1 available.
- APP runtime PyTorch: not installed; this is intentional.
- Docker: unavailable; WSL2: available.
- Free disk before installation: approximately 112 GiB; after installation and
  validation: approximately 103 GiB.

Compatibility result: `SUPPORTED_WITH_CHANGES`, confidence `0.90`, risk
`MEDIUM`. Recommended runtime: private uv CPython 3.12, PyTorch 2.10 `cu130`
worker. The plan requires no admin privilege and includes no Driver, system
CUDA, PATH, or global Python change.

Estimated costs before consent:

- download: 12,051,866,116 bytes (about 11.2 GiB), including the model and
  conservative runtime estimate;
- installed disk: about 20 GiB;
- reserved free-disk gate: 25 GiB;
- recommended VRAM: 12 GiB.

## Official metadata audit

- Unlimited-OCR source revision:
  `528fca4e2161e23231d05666a6d35155dcb1957e`.
- Model revision: `ee63731b6461c8afcdcc7b15352e7d2ffecc2ead`.
- Required model payload: 6,683,156,996 bytes.
- Weight payload: 6,672,547,120 bytes.
- Weight SHA-256:
  `2bc48a7a110061ea58fff65d3169367eebe3aee371ca6968dc2219c1b2855fc6`.
- Second live audit result after reviewed metadata update: `changed: false`.
- Recorded conflicts: upstream CUDA 12.9 versus published PyTorch wheel
  profiles; conflicting SGLang `kernels` pins. SGLang automation is blocked.

## Automated results

- Full suite: 229 unittest tests passed; the equivalent pytest run passed 229
  tests and 40 subtests. New regressions cover
  artifact traversal, real Windows junction substitution, cleanup escape,
  corrupt/incomplete journal recovery, actual OS setup locking, stale lock-file
  recovery, environment/model reuse, transient atomic-write sharing violations,
  real subprocess timeout, worker cancellation, protocol mismatch, bounded
  worker input/output, provider reload, and structured CLI errors.
- The focused managed-deployment/CLI set passed three consecutive runs during
  race and file-sharing review before the final full-suite pass.
- Ruff: passed.
- Bandit medium/high gate: passed.
- `verify_install.py`: all tool classes loaded; this shell reported the existing
  Tk/Tcl runtime warning rather than a product traceback.
- `compileall`: passed.
- Consent-negative physical CLI test: exit code `2`; all six missing
  acknowledgements were listed; managed data root was absent before and after.
- PyInstaller bundle build: passed in an isolated workspace output path; the
  bundled compatibility JSON was present under
  `_internal/src/ocr/deployment/resources` with the expected size.
- Coverage: 51% branch coverage; the configured gate is 45%.
- `pytest` is now an explicit locked development dependency. Repairing the
  project `.venv` removed four stale editable `pdf_toolkit` metadata directories
  without `RECORD`; the final environment contains one current editable install
  with a valid `RECORD`, and `uv sync --all-groups` is idempotent.
- `pip-audit`: no known vulnerabilities. The editable project distribution is
  intentionally skipped because it is local source rather than an index
  artifact.
- `uv build`: passed; wheel and source distribution were created.
- PyInstaller packaged GUI: rebuilt successfully and passed the startup plus
  graceful-shutdown smoke test. The final bundle was inspected and contained
  `runtime_tasks.py`, `provider_worker.py`, and the compatibility metadata at
  the physical paths required by the private Python worker.

The existing P0-P2 suite also covers encrypted, damaged, blank, zero-page,
high-page-count, Unicode/space/emoji/long-path inputs; permission, disk-full,
locked output; cancellation, repeated runs, conflict policies; and a 60-file
resource stress run.

## Synthetic OCR assets

Five deterministic PDF/PNG cases were generated for plain text, table,
Chinese/English, complex two-column layout, and 90-degree rotation. PyMuPDF
rendered each page and every PNG was visually inspected at original detail for
clipping, missing glyphs, overlap, background color, and rotation correctness.
The bundled local `pdftoppm.cmd` override was also attempted but has a broken
external path on this computer, so no Poppler result is claimed; this did not
affect the independent PyMuPDF render or real OCR inference.

## Consented installation and real inference

Plan `a02d56a445a16280` completed every stage from `PRECHECK` through
`COMPLETE`. Initial setup took about 246 seconds on the development computer.
Dependency installation took about 41 seconds; the pinned 6.2 GiB model
snapshot downloaded in about 61 seconds and then passed the recorded SHA-256
check. Managed storage after testing was 9,775,654,398 bytes: 3,092,068,945
bytes for the private runtime and 6,683,583,739 bytes for model/cache content.

- Private runtime: Python 3.12.11, torch 2.10.0+cu130, torchvision
  0.25.0+cu130, transformers 4.57.1, Pillow 12.1.1, and PyMuPDF 1.27.2.2.
- CUDA smoke: passed on NVIDIA GeForce RTX 3060; torch CUDA 13.0 and cuDNN
  9.12 were visible inside the private runtime.
- Model load: 10.025 seconds with 6,770,339,840 peak VRAM bytes.
- Final five-case OCR harness: every expected term matched. Inference times were
  3.640 seconds (plain text), 2.664 (table), 2.978 (Chinese/English), 8.439
  (complex two-column), and 2.296 (rotation). Peak VRAM was 7,564,874,752 bytes
  for four cases and 8,083,605,504 bytes for rotation.
- Final benchmark: `REAL_TIME_SUITABLE`, 3.112 seconds inference,
  1,955,713,024 peak RAM bytes, and 7,564,874,752 peak VRAM bytes out of
  12,884,377,600 detected bytes. This synthetic classification is not a promise
  for arbitrary production documents.
- Provider integration: a live persistent worker reported `HEALTHY`, loaded the
  pinned revision, recognized all three expected plain-text terms in 8.4
  seconds, wrote real Document OCR TXT and Markdown outputs, and unloaded
  cleanly.
- Persistent-worker repetition: two consecutive real inferences on one loaded
  worker completed in 8.205 and 7.378 seconds, both matched every expected term,
  health remained `HEALTHY`, and no request temporary directories remained
  after unload.
- Final lifecycle run: two unload/reload cycles created new worker PIDs, both old
  workers exited, and both new workers recognized the expected terms in 3.764
  and 3.894 seconds. A cancellation during active inference returned
  `CANCELLED`, terminated the worker, left provider health `READY`, and the next
  explicit request automatically loaded a new worker and succeeded in 3.666
  seconds.
- Fifty consecutive real inferences all succeeded with exactly one worker PID.
  Worker RSS changed from 1,911,431,168 to 1,911,181,312 bytes (-249,856), and
  handle count changed from 433 to 425 (-8); peaks were 1,911,463,936 bytes and
  433 handles. Average latency was 3.088 seconds and maximum latency was 3.343.
  Final unload terminated the worker, left no child process, and left zero
  managed session directories.
- After the final junction/TOCTOU changes, a fresh full SHA-256 verification
  still reported the pinned snapshot complete (6,683,158,594 bytes). A final
  no-download recheck again passed all five cases, one worker reload, benchmark
  (`REAL_TIME_SUITABLE`, 3.095 seconds), worker exit, child-process cleanup, and
  zero session leftovers.
- Resume/migration: rerunning the same setup skipped environment creation,
  dependency installation, model download, checksum, and OCR stages. It reran
  only the legacy benchmark record that lacked classification and dependency
  versions, completing in about 26 seconds.

The final adversarial review found and fixed additional defects: cleanup could
follow a substituted Windows junction outside the managed root; corrupt journals
were not recoverable; lock-file-only setup exclusion was race-prone; transient
Windows sharing violations could break atomic state writes; a cancelled worker
did not automatically reload for the next request; response-ID/protocol errors
 did not always invalidate the worker; and a CP950 console could turn successful
emoji-path JSON output into exit code 2. The gate also exposed a terminated but
unreaped timeout-process handle; it is now explicitly waited and passes with
`ResourceWarning` promoted to an error. Each fix has a regression test.

Actual CLI checks covered inspect/plan/status, repeat setup with all six
acknowledgements, and a Chinese/space/emoji output path. Repeat setup reused the
existing environment and verified snapshot; model-download attempts remained
at one. Isolated temporary data roots covered status, uninstall, second
idempotent uninstall, and cleanup without touching the real 6.2 GiB snapshot.
The APP `.venv` still has no torch or transformers; the private runtime retained
torch 2.10.0+cu130 and CUDA availability, and system `CUDA_PATH` remained 12.2.
Destructive full-cleanup tests used isolated temporary roots only: they removed
multiple valid model revisions and every managed Hugging Face/Transformers cache,
remained idempotent, rejected root/runtime junction substitution, and preserved
external markers. The real installed snapshot was never removed.

The first post-hardening CI run exposed a cross-platform false positive: comparing
resolved and textual paths treated macOS `/tmp` and Windows runner path aliases
as if the managed directory itself were a junction. Detection now checks the
managed entry's own symlink/junction/reparse metadata while canonicalizing legal
ancestor aliases. A regression covers an accepted regular cache below an aliased
ancestor alongside the rejected managed-root junction cases.

## Final acceptance gate

The source GUI was exercised with a real Tk event loop: Settings / Recent opened
the managed setup dialog, completed device analysis, displayed
`SUPPORTED_WITH_CHANGES`, kept install disabled until acknowledgements, and
closed cleanly. The Windows PyInstaller bundle was rebuilt and passed actual
startup plus graceful-shutdown smoke. Internal packaged Tk child navigation
could not be driven through Windows UI Automation because ttk descendants were
not exposed, so that specific packaged-dialog click path remains unverified;
the source dialog and packaged process lifecycle are real tests, not mocks.

The local full test, coverage, lint, security, install verification, compile,
package, PyInstaller, packaged GUI smoke, real provider, official metadata
audit, and isolated cleanup gates passed. The live source audit reported
`changed: false`.

Clean-runner CI run
[`29386808473`](https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/actions/runs/29386808473)
passed on commit `842dc87`: quality/security, Ubuntu, macOS, Windows, and the
dependent Windows PyInstaller build, packaged-app smoke, and artifact upload all
succeeded. GitHub emitted one non-failing setup-uv cache-reservation annotation
because parallel Ubuntu jobs attempted to create the same cache key; it did not
skip or fail a product gate.

The measurements apply only to this device and synthetic suite. They do not
guarantee OCR accuracy, latency, or OOM behavior for arbitrary documents or
when other GPU-heavy applications are active.
