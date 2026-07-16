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

## Physical Ubuntu second-device validation

This was a real SSH validation on a separate Acer Nitro laptop, not a fixture or
mock. The isolated checkout used branch `codex/unlimited-ocr-deployment` under a
user-writable `<home>/projects/` directory. Machine-specific JSON stayed in an
ignored validation-results directory and was not committed.

| Item | Windows development computer | Ubuntu second device |
| --- | --- | --- |
| OS | Windows 11 build 26200 | Ubuntu 20.04.6 LTS, kernel 5.15 |
| CPU | Intel Core i5-13600K | Intel Core i7-8750H |
| RAM | 63.8 GiB | 7.6 GiB |
| GPU | RTX 3060 | GTX 1060 |
| VRAM | 12 GiB | 6 GiB |
| Driver / Driver CUDA API | 610.47 / 13.3 | 570.133.07 / 12.8 |
| CUDA Toolkit | 12.2 | 10.1 |
| Compute capability | 8.6 | 6.1 |
| Project Python | 3.12.12 | Miniforge CPython 3.12.11 |
| APP PyTorch | intentionally absent | absent |
| Basic OCR | Tesseract available | Tesseract executable absent |
| Advanced compatibility | `SUPPORTED_WITH_CHANGES` | `UNSUPPORTED` |
| Confidence / risk | 0.90 / `MEDIUM` | 0.90 / `BLOCKED` |
| Recommended backend | Transformers | none |
| Setup allowed | yes after consent | no |

The Ubuntu system Python was 3.8.10 and therefore unsuitable for the project's
`>=3.10` requirement. A bounded probe found both Miniforge Python 3.12.11 and
Conda outside PATH. It also found an existing user-local uv 0.9.25 at the normal
`~/.local/bin` location; no new uv installation was necessary. The final source
setup followed the repository workflow exactly:

```bash
<home>/.local/bin/uv sync --dev --python <home>/miniforge3/bin/python3.12
<home>/.local/bin/uv run --no-sync pdf-toolkit --version
<home>/.local/bin/uv run --no-sync python verify_install.py
<home>/.local/bin/uv run --no-sync pytest -q
<home>/.local/bin/uv run --no-sync ruff check .
```

The sync created only the ignored project `.venv` and uv cache content. It did
not change PATH or shell profiles, modify Miniforge base packages, use sudo, or
touch system Python, Driver, CUDA Toolkit, or global site-packages. The ordinary
APP dependencies and every tool class loaded; CLI/version/compile checks passed.
Tkinter was importable, but source GUI construction was not claimed because the
SSH session had no display. Tesseract was not installed, so the report correctly
recommended installing Tesseract for Basic OCR while confirming non-OCR APP/CLI
features remained usable.

The first real inspection exposed five cross-device defects: Linux CPU model
was reported as architecture; Miniforge/uv outside a non-login PATH were missed;
a blocked plan still offered install; an unresolved manager emitted unusable uv
argv; and a blocked reason contradicted the detected cu128-compatible Driver.
Review also found first-GPU display selection and headless/Tesseract messaging
assumptions. Production fixes now use `/proc/cpuinfo` fallback, bounded common
locations, absolute tool argv, explicit `BLOCKED_INFORMATIONAL` plans, consistent
wheel decisions, highest-VRAM NVIDIA display selection, and layered APP/GUI,
Basic OCR, and Unlimited-OCR status.

Final Ubuntu compatibility was `UNSUPPORTED`, confidence `0.90`, risk
`BLOCKED`. Requirements met included eligible 64-bit Linux, 40.9 GiB free disk,
Driver 570.133.07 support for the cu128 wheel family, active Python 3.12.11, and
the absolute user-local uv. Missing requirements were exactly 6 GiB VRAM versus
the 10 GiB minimum, compute capability 6.1 versus the BF16 Ampere-class gate,
and 7.6 GiB RAM versus the 16 GiB minimum. The plan was informational,
`executable: false`, recommended backend `none`, and exposed only technical
details / not-now actions. `ocr plan` returned the documented exit code 3.

Before and after structured reports proved that no managed runtime, model
snapshot, journal, benchmark, or provider registration existed. Final status
was provider `NOT_INSTALLED`, model `exists: false`, journal absent, and the
isolated managed root remained absent. No torch, Transformers, AI runtime, model,
Driver, CUDA, PATH, profile, global Python, or administrator change occurred.
The final Ubuntu real-machine run on commit `bb12049` passed 244 tests plus 40
subtests, including the minimum-uv-version regression. No Unlimited-OCR
inference success is claimed on Linux.

## Physical Ubuntu dual-RTX 4090 pre-consent validation

On 2026-07-16, a second real Linux device was reached through SSH and the branch
`codex/unlimited-ocr-deployment` was cloned into an isolated
`<home>/projects/Unified-PDF-Toolkit` checkout. Machine-specific structured JSON
remained under the ignored `.remote-validation-results/` directory. No hostname,
address, username, key path, or absolute home path was committed.

- Ubuntu 22.04, kernel 6.5, native Linux x86_64.
- AMD Ryzen Threadripper 1920X, 12 physical / 24 logical cores.
- 110.0 GiB RAM total, 105.2 GiB available during inspection, and 313.0 GiB free
  project-home disk space.
- Two NVIDIA GeForce RTX 4090 devices, each with 24,564 MiB VRAM and compute
  capability 8.9.
- NVIDIA Driver 560.35.05 with CUDA Driver API 12.6; the separate system CUDA
  Toolkit was 11.5 and was detected but not selected or modified.
- Docker was present; the host was not WSL and the SSH session had no `DISPLAY`.
- Existing user-local uv 0.9.18 was reused by absolute path. No uv reinstall,
  `PATH`, shell-profile, Conda, system Python, sudo, Driver, or CUDA change was
  made.

The first candidate `/usr/bin/python3` was CPython 3.10.12 and satisfied the
package's broad `>=3.10` metadata, but it lacked Tkinter and conflicted with the
repository's `.python-version` 3.12 workflow. The final project `.venv` therefore
used uv-managed CPython 3.12.12 with Tk 8.6. Two consecutive `uv sync --dev`
runs were idempotent. APP/CLI imports, every tool-class load, CLI version/help,
managed OCR command help, and compileall passed. GUI construction was correctly
classified `NOT_TESTED_NO_DISPLAY`; the Tesseract executable was absent, so Basic
OCR remained an optional dependency rather than an APP failure. The normal APP
environment contained neither torch nor Transformers.

The real Inspector enumerated both GPUs, and the Compatibility Engine returned
`SUPPORTED_WITH_CHANGES`, confidence `0.90`, risk `MEDIUM`, with the Transformers
backend and a private uv CPython 3.12 / torch 2.10.0 cu128 worker plan. It
estimated 12,051,866,116 download bytes, 20 GiB installed disk, and a 12 GiB VRAM
target. The provider remained `NOT_INSTALLED`; model snapshot, journal, and
managed runtime were absent.

The first physical multi-GPU report exposed a cross-device defect: compatibility
used the highest-VRAM device internally but did not serialize the selected GPU,
bind the plan ID to it, or restrict the future worker. The generic fix now uses
highest total VRAM and lowest index as a deterministic tie-break, reports the
selected device, prefers its stable NVIDIA UUID for `CUDA_VISIBLE_DEVICES`, and
binds that value into the consent plan ID. Unit regressions cover unequal and
equal VRAM, consent disclosure, worker environment isolation, and plan-ID
invalidation. This is single-GPU selection on a multi-GPU host, not sharded or
distributed inference.

The post-fix rerun used commit
`fc4c8bef5e4fa73e97cc4aa5e5d6ee917a1987e7`. It selected GPU index 0 under the
equal-VRAM tie policy, used the selected device's UUID as the private-worker
binding, and produced plan `a9638f35740915cf`. Inspect, plan, status, and consent
reported the same selected device and compatibility state. The Linux checkout
then passed 246 tests plus 40 subtests, Ruff, Bandit, pip-audit, compileall,
install verification, 53% branch coverage, and wheel/source-distribution build.
The no-display GUI warning remained informational.

The pre-consent phase intentionally stopped without installing an AI runtime or
model. The later device- and plan-specific consent retained the same plan ID,
model revision, selected GPU UUID, runtime path, and dependencies; its results
are recorded below.

## AI1 consented installation and Linux real inference

Plan `a9638f35740915cf` was revalidated immediately before setup. The selected
GPU was idle apart from desktop graphics work, and the second RTX 4090 was not
substituted. The repository orchestrator then completed all 15 stages from
`PRECHECK` through `COMPLETE`, each with status `SUCCEEDED` and one attempt.
Initial setup took 292 seconds; dependency installation took about 59 seconds
and the model-download task took 74.448 seconds.

- The verified snapshot contained 13 selected files and 6,683,158,546 bytes.
  The weight SHA-256 was
  `2bc48a7a110061ea58fff65d3169367eebe3aee371ca6968dc2219c1b2855fc6`.
  The private runtime used 7,532,310,308 bytes and the managed model/cache root
  used 6,683,813,434 bytes.
- The private worker used CPython 3.12.12, torch 2.10.0+cu128, torchvision
  0.25.0+cu128, transformers 4.57.1, Pillow 12.1.1, PyMuPDF 1.27.2.2, bundled
  CUDA 12.8, and cuDNN 9.10. The APP `.venv` still contained neither torch nor
  Transformers.
- The worker saw exactly one logical RTX 4090 with compute capability 8.9, and
  its NVIDIA UUID matched the selected physical GPU. External sampling recorded
  a 10,193 MiB maximum on that GPU and 0% compute utilization on the unselected
  GPU. The system CUDA Toolkit 11.5 was neither used nor modified.
- Cold worker/model load was 7.305 seconds. Plain text, table, mixed Chinese and
  English, complex two-column, and rotation cases completed in 4.054, 2.831,
  3.105, 9.203, and 2.171 seconds. Expected-token hits were 3/3, 4/4, 4/4,
  4/4, and 1/2. The rotated content was recognized, but the synthetic
  `ROTATE-0090` identifier was missed; this is a recorded quality limitation,
  not a 100% accuracy claim. Peak recorded worker RAM was 2,023,325,696 bytes;
  rotation reached 8,085,965,824 allocated VRAM bytes, while the other cases
  used 7,565,848,064 bytes.
- The final benchmark classified this fixed synthetic case as
  `REAL_TIME_SUITABLE`: 3.062 seconds inference, 2,059,022,336 peak RSS bytes,
  and 7,565,848,064 peak allocated VRAM bytes. This classification is not a
  latency or quality promise for arbitrary documents.
- Fifty consecutive persistent-worker requests succeeded with one PID and one
  output hash. Mean/median/p95/max latency was 3.083/3.085/3.124/3.142 seconds.
  RSS rose 36,569,088 bytes during allocator warm-up and then remained exactly
  constant for requests 27 through 50. Allocated VRAM, Linux file descriptors,
  threads, and open files had zero start-to-finish growth (6,779,908,096 bytes,
  43, 63, and 1 respectively). Final unload reaped the worker and left no child
  process or managed session directory.
- A real inference cancellation returned structured `CANCELLED`, terminated and
  reaped the old worker, left provider state `READY`, and did not use Basic OCR.
  The next request created a new PID, retained the selected-GPU binding,
  recognized all three plain-text terms, and reported `HEALTHY` before final
  unload. No stale response or child/session residue was observed.
- Rerunning the exact setup completed in one second. Its JSON was byte-for-byte
  identical to the first result, every stage remained at one attempt, and the
  model-inventory-state hash was unchanged. No dependency, download, provider,
  runtime, cache, or worker duplicate was created.
- Bounded fault-injection tests passed for CUDA/RAM OOM classification,
  cancellation journal recovery, completed-stage resume, complete-snapshot
  network bypass, corrupt-cache rejection, and managed-root cleanup. A real GPU
  exhaustion test was intentionally not applicable on the shared host. The
  first real download had no network interruption, so a physical partial-transfer
  resume is not claimed; the resume contract is covered by the isolated tests.
- Destructive uninstall/cleanup tests used temporary managed roots only. The
  final AI1 runtime, verified snapshot, registration, journal, and benchmark
  remained installed. Tesseract was not present, so this host had no working
  Basic OCR fallback even though the provider fallback architecture remained.

Before/after hashes and probes showed no change to `.bashrc`, `.profile`, PATH,
system Python, Conda, NVIDIA Driver 560.35.05, CUDA Driver API 12.6, CUDA Toolkit
11.5, or `/usr/local/cuda`. No sudo or global package installation was used.
Machine-specific JSON, full OCR output for manual review, GPU samples, and local
paths remain in the ignored remote evidence directory and are not committed.

The first post-install AI1 full-suite run exposed two tests that assumed no
persisted provider registration. Production behavior was correct; the tests
cleared only the environment gate and accidentally read AI1's real successful
registration. Commit `e79818e` made those cases inject an explicitly disabled
runtime config. Windows, Acer Nitro, and AI1 then each passed all 249 tests, and
AI1 also passed Ruff, Bandit, pip-audit, 53% branch coverage, compileall,
install verification, and wheel/source-distribution build while the installed
provider remained `READY` with a complete model and complete journal. Final
merge review added one CLI regression and strengthened the existing direct
orchestrator regression: a blocked informational plan is rejected even when all
six acknowledgements are supplied, and its managed state directory remains
absent. The resulting suite contains 250 tests plus 40 subtests.

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

- Full suite: 250 pytest tests and 40 subtests passed. New regressions cover
  Linux CPU/architecture separation, alternate Python discovery, user-local
  uv/Conda/pyenv detection, uv version gating and managed bootstrap, blocked
  action/argv consistency, blocked-setup no-write enforcement, multi-GPU
  display selection, headless GUI state,
  Basic OCR availability, plus the earlier
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
- Coverage: 53% branch coverage; the configured gate is 45%.
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

Final implementation-baseline CI run
[`29397624967`](https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/actions/runs/29397624967)
passed on commit `bb12049`: quality/security, Ubuntu, macOS, Windows, and the
dependent Windows PyInstaller build, packaged-app smoke, and artifact upload all
succeeded.

The measurements apply only to this device and synthetic suite. They do not
guarantee OCR accuracy, latency, or OOM behavior for arbitrary documents or
when other GPU-heavy applications are active.
