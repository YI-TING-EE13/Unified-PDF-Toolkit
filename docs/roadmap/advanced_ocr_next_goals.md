# Advanced OCR Roadmap

This is the canonical forward-looking roadmap for optional advanced local OCR.
Use it to decide what to validate or build next and what support claims are
currently justified. It is not a test log or release history.

Document ownership is intentionally separated:

- this roadmap owns priorities, unverified targets, limitations, and research;
- [`CHANGELOG.md`](../../CHANGELOG.md) owns completed release history;
- [the validation record](../testing/managed_unlimited_ocr_validation.md) owns
  detailed commands, measurements, and machine evidence;
- [the managed runtime guide](../runtime/managed_unlimited_ocr.md) owns setup,
  architecture, recovery, and operation;
- [the security review](../security/advanced_ocr_security_review.md) owns threats,
  consent, trust boundaries, and release gates;
- [the maintainer guide](../advanced_ocr_maintainer_guide.md) owns code navigation
  and maintenance procedures.

Tesseract remains the default and fallback OCR provider. Unlimited-OCR is an
optional local provider and is never evidence that every installation or every
NVIDIA GPU is supported.

## 1. Current Stable Baseline

The following baseline exists in code and has the stated evidence. “Stable” here
means the framework and its safety boundaries are regression-tested; it is not a
claim of broad production support for Unlimited-OCR.

### Real hardware evidence

- **Windows 11 / RTX 3060 12 GiB:** consented APP-private installation completed
  without Driver, system CUDA, PATH, global Python, or administrator changes.
  The pinned model loaded successfully and passed plain text, table,
  Chinese/English, two-column, and rotated-image OCR cases.
- The same device passed a real benchmark, persistent-worker health and reuse,
  two unload/reload cycles, active-inference cancellation and recovery, cleanup,
  and 50 consecutive real inference requests without sustained RSS, handle,
  child-process, or session-directory growth.
- **Ubuntu 20.04 / GTX 1060 6 GiB:** a physical Acer Nitro validated source setup,
  Linux environment inspection, Miniforge Python selection, user-local uv reuse
  outside `PATH`, layered compatibility reporting, and safe unsupported-device
  rejection. No AI runtime or model was installed and no inference was attempted.
- The Windows source GUI opened the managed setup dialog and exercised consent
  gating. Both the local and CI Windows PyInstaller bundles passed startup and
  graceful-shutdown smoke tests.

### Implemented and automated evidence

- Environment Inspector covers OS/architecture, CPU, RAM, multiple GPUs/VRAM,
  Driver and Driver CUDA API, CUDA Toolkit, Python candidates, uv/Conda/pyenv,
  PyTorch, disk, Docker, WSL2, GUI/display state, and Tesseract availability.
- Compatibility Engine reports APP/CLI, GUI, Basic OCR, and Unlimited-OCR status
  separately and produces conservative metadata-driven decisions rather than a
  GPU-present boolean.
- The resolver creates argv-only private uv/Conda plans and can add a
  consent-gated, pinned, size- and SHA-256-verified APP-managed uv prerequisite.
  The bootstrap implementation is covered by unit, security, and CI tests; a
  physical machine on which uv is genuinely absent has not yet exercised that
  archive download/extraction path end to end.
- The staged installer supports consent binding, progress, retry, pause,
  cancellation, resume, checksum/inventory validation, model load, real OCR,
  benchmark, registration, uninstall, cache cleanup, corrupt-journal recovery,
  OS-held single-installer locking, and managed-path escape protection.
- The provider abstraction keeps Tesseract available as fallback and runs the
  managed provider in a persistent private worker with bounded protocol and
  output handling.
- The current suite passes 244 tests plus 40 subtests with a 53% branch coverage
  result against a 45% gate. CI validates quality/security plus Windows, Ubuntu,
  and macOS source builds; Windows also performs PyInstaller build and packaged
  application smoke testing.

Detailed evidence and device measurements belong in the
[managed validation record](../testing/managed_unlimited_ocr_validation.md).

## 2. Next Highest-Value Work

### P1 — Second Supported NVIDIA Machine Validation

Validate one additional machine that the Compatibility Engine considers
eligible, preferably a supported Linux NVIDIA device; a different Windows NVIDIA
GPU is the alternative. This increases generalization evidence rather than
repairing a known missing core framework feature.

The run must cover:

- real environment inspection and compatibility decision;
- compatible Python selection and existing uv reuse or actual managed bootstrap;
- isolated runtime creation and dependency installation;
- model download interruption/resume, cache reuse, inventory, and checksum;
- model load and all five real OCR categories;
- benchmark, RAM/VRAM measurement, and controlled OOM behavior;
- cancellation, recovery, APP restart/resume, and repeated inference;
- a 50–100 request resource-stability run;
- provider fallback, cleanup/uninstall, and proof that system Python, Driver,
  CUDA Toolkit, PATH, and unrelated AI environments remain unchanged.

If the device is Linux, this closes the highest-value platform evidence gap. If
it is Windows, Linux supported-GPU inference remains the next P1 target.

### P2 — Versioned OCR Quality Evaluation

Build a representative, non-sensitive and redistributable evaluation set with
ground truth. Record CER/WER for Chinese and English, field/reading-order checks,
table structure metrics, rotation behavior, latency, and peak resources. Keep
synthetic smoke assets for deterministic regressions, but do not use them as the
only quality claim.

### P3 — Product and Packaging Acceptance

- Exercise the managed uv bootstrap on a clean eligible account where uv and
  Conda are genuinely absent.
- Add deeper packaged-GUI automation for the analysis, consent, progress,
  cancellation, recovery, provider selection, and cleanup dialogs.
- Run longer mixed-document sessions and shutdown/restart scenarios from the
  packaged application, not only the source harness.

## 3. Validation Matrix

Status words describe evidence, not aspiration. `NOT_TESTED` is intentionally
different from `UNSUPPORTED`; annotations identify CI- or unit-only evidence.

| Platform / hardware | APP | GUI | Basic OCR | Unlimited-OCR | Real inference | Overall evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Windows 11, RTX 3060 12 GiB | VERIFIED | VERIFIED | VERIFIED | SUPPORTED_WITH_CHANGES | VERIFIED | VERIFIED on this device |
| Ubuntu 20.04, GTX 1060 6 GiB | VERIFIED | NOT_TESTED (SSH had no display) | NOT_TESTED (executable absent) | UNSUPPORTED | NOT_TESTED | VERIFIED safe rejection |
| Linux, supported NVIDIA GPU | SUPPORTED (CI/source) | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | FUTURE — P1 |
| Windows, second NVIDIA GPU | SUPPORTED (CI/source) | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | FUTURE — P1 |
| WSL2 with NVIDIA GPU | EXPERIMENTAL | NOT_TESTED | NOT_TESTED | EXPERIMENTAL | NOT_TESTED | EXPERIMENTAL |
| Physical multi-GPU | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED (selection logic unit-tested) |
| AMD GPU | SUPPORTED (normal APP) | NOT_TESTED | NOT_TESTED | UNSUPPORTED (current backend) | NOT_TESTED | FUTURE research |
| Apple Silicon | SUPPORTED (CI/source) | NOT_TESTED | NOT_TESTED | UNSUPPORTED (current backend) | NOT_TESTED | FUTURE research |
| CPU-only | SUPPORTED (normal APP) | NOT_TESTED | NOT_TESTED | UNSUPPORTED (current integration) | NOT_TESTED | FUTURE feasibility research |

`SUPPORTED (CI/source)` means the normal Python application is exercised by CI;
it is not equivalent to a physical packaged-GUI or model-runtime verification.

## 4. Known Limitations

- Successful real Unlimited-OCR inference evidence currently comes from one RTX
  3060 runtime and one pinned model/dependency combination.
- The Acer Nitro proves safe rejection, ordinary Linux APP/CLI setup, and honest
  headless reporting; it does not prove supported-GPU Linux inference.
- The actual managed-uv download/extract path is automated-test evidence only
  because both real machines already had a compatible uv installation.
- AMD ROCm, Apple Silicon, CPU-only, WSL2 inference, and physical multi-GPU paths
  have no support claim beyond the matrix above.
- SGLang automation remains blocked by conflicting upstream dependency pins;
  Docker/vLLM paths are metadata/research candidates only.
- OCR accuracy is currently demonstrated with deterministic synthetic assets,
  not a versioned representative corpus with CER/WER and table metrics.
- Multi-GPU detection selects one eligible highest-VRAM device; inference is not
  sharded across GPUs.
- Packaged-app process smoke is real, but complete internal managed-setup dialog
  automation is not available because ttk child controls were not exposed to the
  Windows UI Automation attempt.
- Performance, accuracy, and freedom from OOM are not guaranteed for arbitrary
  documents or while other GPU-heavy applications are active.

## 5. Future Product Enhancements

These are optional product ideas, not scheduled commitments:

- policy-driven automatic provider selection with an explicit manual override;
- document-type-aware routing between Tesseract and eligible local providers;
- a low-memory or quantized backend for supported hardware profiles;
- multi-model/version management with update, rollback, and health state;
- model/cache storage inspection, cleanup, relocation, and quota controls;
- benchmark history and compatibility-report comparison after upgrades;
- one-click privacy-safe diagnostic export;
- reviewed compatibility-metadata refresh notifications;
- consent-aware advanced OCR jobs in Batch Queue;
- richer TXT/Markdown/structured output and searchable-PDF workflows;
- quality dashboards using CER/WER, field accuracy, reading order, and table
  structure metrics.

## 6. Research / Experimental Directions

- SGLang after upstream dependency conflicts are resolved and reproducible.
- vLLM or another local serving backend where the model is technically supported.
- Docker/container isolation and WSL2 GPU behavior.
- Quantized and low-VRAM inference with quality/resource comparisons.
- CPU-only feasibility rather than an assumed fallback.
- AMD ROCm and Apple Silicon acceleration only with upstream-compatible evidence.
- Physical multi-GPU selection, isolation, and optional work distribution.
- Alternative local OCR providers behind the existing `OCRProvider` interface.

Research results must not change the validation matrix until the support-evidence
gate below is satisfied.

## 7. Deferred or Rejected Directions

- Do not automatically install or update NVIDIA Driver software.
- Do not overwrite, remove, or globally reconfigure system CUDA installations.
- Do not replace system Python, modify global site-packages, or edit PATH/shell
  profiles as part of advanced OCR setup.
- Do not force model load on an unsupported device such as the GTX 1060 test
  machine merely to produce a failure or OOM result.
- Do not interpret an optional provider failure as failure of the entire APP;
  normal PDF tools and the Tesseract fallback remain independent.
- Do not add torch, Transformers, CUDA runtimes, or model files to the default
  APP dependencies or installer without a separate reviewed product decision.
- Do not operate a project-hosted OCR service or upload user documents by
  default. The local endpoint scaffold remains a developer option.
- Do not add a single consent-bypassing `--yes` switch for managed setup.

## 8. Evidence Required Before Claiming Support

A new platform/hardware/runtime combination may be marked `VERIFIED` only after
all applicable evidence is recorded:

1. real Environment Inspector output and metadata revision;
2. correct compatibility decision and user-visible cost/risk disclosure;
3. isolated dependency setup without unintended system changes;
4. verified model inventory/checksum and actual model load;
5. actual OCR inference, not only import or load success;
6. latency plus peak RAM/VRAM measurement and OOM/error behavior;
7. cancellation, recovery/resume, restart, and provider fallback;
8. repeated inference/resource-stability and worker/session cleanup;
9. uninstall/cache cleanup with proof that external paths are preserved;
10. regression tests, security gates, and relevant packaged/source UI checks.

CI, mocks, fixtures, fault injection, or successful model load alone can justify
an implemented/tested mechanism but cannot justify a physical-device support
claim. Evidence must be linked from the validation record.

## 9. Maintenance Triggers

Re-run metadata review, compatibility resolution, relevant tests, and affected
real-device acceptance when any of these changes:

- Unlimited-OCR upstream source or model revision;
- PyTorch/torchvision major or minor version or published CUDA wheel families;
- NVIDIA Driver/CUDA compatibility policy;
- Transformers or custom model-code dependencies;
- selected model inventory, size, license, or checksum;
- managed uv pinned or minimum-compatible version;
- supported Python versions or APP packaging/runtime layout;
- compatibility thresholds for RAM, VRAM, GPU generation, or disk;
- the live metadata audit reports `changed: true` or conflicting sources.

Conflicting authoritative metadata blocks automatic high-risk changes until a
maintainer records a reviewed resolution.

## 10. Completed Historical Milestones

Keep this section concise; detailed chronology belongs in
[`CHANGELOG.md`](../../CHANGELOG.md).

- `842dc87` — initial managed deployment framework: inspector, compatibility,
  consent, staged setup, provider, GUI/CLI, tests, and documentation.
- `02d6865` / `ea9c902` — adversarial lifecycle, path, locking, journal,
  protocol, cleanup, and cross-platform hardening.
- `44daa19` — final development-machine real OCR and CI validation record.
- `51346e7` / `56d70cd` / `0a9bde7` — cross-device inspection, verified managed
  uv bootstrap, headless GUI, Basic OCR, and blocked-plan corrections.
- `bb12049` — physical Acer Nitro Linux safe-rejection validation and final
  cross-platform CI confirmation.

For exact measurements, test counts, commands, and GitHub Actions links, use the
[managed validation record](../testing/managed_unlimited_ocr_validation.md).
