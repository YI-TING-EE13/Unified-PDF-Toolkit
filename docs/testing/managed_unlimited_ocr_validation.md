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

- Managed deployment and metadata tests: 58 tests passed after adding
  benchmark-journal, typed Basic benchmark, and persistent-worker lifecycle
  regressions plus a packaged-runtime entrypoint assertion.
- Full unittest suite: 207 tests passed.
- Ruff: passed.
- Bandit medium/high gate: passed after adding the explicit revision to local
  `from_pretrained` calls.
- `verify_install.py`: all tool classes loaded; this shell reported the existing
  Tk/Tcl runtime warning rather than a product traceback.
- `compileall`: passed.
- Consent-negative physical CLI test: exit code `2`; all six missing
  acknowledgements were listed; managed data root was absent before and after.
- PyInstaller bundle build: passed in an isolated workspace output path; the
  bundled compatibility JSON was present under
  `_internal/src/ocr/deployment/resources` with the expected size.
- Coverage: 48% branch coverage; the configured gate is 45%.
- `pip-audit`: initially found vulnerable `pytest 8.4.2`, which was not in
  `pyproject.toml` or `uv.lock` and was a stale local-environment package. The
  scoped pytest/pytest-cov/plugin residue was removed, `uv sync --dev` became
  idempotent, and the final audit reported no known vulnerabilities.
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
Chinese/English, complex two-column layout, and 90-degree rotation. The PDFs
were rendered and visually inspected for clipping, missing glyphs, overlap, and
rotation correctness.

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
- Functional OCR: every expected term matched in all five cases. Inference
  times were 3.923 seconds (plain text), 3.399 (table), 3.921
  (Chinese/English), 21.047 (complex two-column), and 5.378 (rotation).
- Functional peak process RAM was about 1.82-1.87 GiB; peak VRAM was about
  7.04 GiB for four cases and 7.53 GiB for the rotated case.
- Benchmark after the schema-completeness fix: `GENERAL_OCR_SUITABLE`, 8.055
  seconds inference, 1,951,903,744 peak RAM bytes, and 7,564,874,752 peak VRAM
  bytes out of 12,884,377,600 detected bytes.
- Provider integration: a live persistent worker reported `HEALTHY`, loaded the
  pinned revision, recognized all three expected plain-text terms in 8.4
  seconds, wrote real Document OCR TXT and Markdown outputs, and unloaded
  cleanly.
- Persistent-worker repetition: two consecutive real inferences on one loaded
  worker completed in 8.205 and 7.378 seconds, both matched every expected term,
  health remained `HEALTHY`, and no request temporary directories remained
  after unload.
- Resume/migration: rerunning the same setup skipped environment creation,
  dependency installation, model download, checksum, and OCR stages. It reran
  only the legacy benchmark record that lacked classification and dependency
  versions, completing in about 26 seconds.

The first real run revealed that the installation benchmark journal omitted the
classification and dependency-version fields even though the persistent
provider benchmark had them. The runtime task and resume validator were fixed;
the journal now records the complete result, and regression tests cover the
targeted migration. Code review also found and fixed typed-result access in the
Basic provider benchmark plus stale response/file-handle cleanup across worker
restart and unload.

## Final acceptance gate

The local full test, coverage, lint, security, install verification, compile,
package, PyInstaller, packaged GUI smoke, and official metadata-audit gates all
passed. The live source audit reported `changed: false`.

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
