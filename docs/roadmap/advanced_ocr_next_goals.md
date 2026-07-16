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
- **Ubuntu 22.04 / dual RTX 4090 24 GiB:** a second physical Linux device passed
  SSH deployment, repository-standard uv/Python 3.12 setup, APP/CLI imports,
  inspection, plan-bound consent, private cu128 runtime/model installation,
  pinned integrity, five-layout real inference, benchmark, cancellation and
  recovery, idempotent setup, and 50-request stability. The worker was bound to
  one selected GPU by UUID and the unselected GPU remained unused.
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
- The current suite passes 249 tests plus 40 subtests with a 53% branch coverage
  result against a 45% gate. CI validates quality/security plus Windows, Ubuntu,
  and macOS source builds; Windows also performs PyInstaller build and packaged
  application smoke testing.

Detailed evidence and device measurements belong in the
[managed validation record](../testing/managed_unlimited_ocr_validation.md).

## 2. Next Highest-Value Work

### P1 — Broaden Supported NVIDIA Evidence

The second supported NVIDIA machine target is complete on the Ubuntu dual-RTX
4090 host for the fixed Transformers/model revision. The next P1 is to avoid
mistaking two successful machines for broad support:

- validate another eligible NVIDIA family and Driver/wheel profile, preferably
  a clean user account that also exercises managed uv bootstrap;
- repeat a longer mixed-document soak and APP shutdown/restart lifecycle from a
  packaged application rather than only the source harness;
- exercise a real interrupted model transfer when it occurs safely, while
  retaining the current deterministic fault-injection coverage;
- preserve device-specific benchmark and quality reporting rather than creating
  a generic Linux/NVIDIA performance promise.

### P2 — Versioned OCR Quality Evaluation

Build a representative, non-sensitive and redistributable evaluation set with
ground truth. Record CER/WER for Chinese and English, field/reading-order checks,
table structure metrics, rotation behavior, latency, and peak resources. Keep
synthetic smoke assets for deterministic regressions, but do not use them as the
only quality claim.

### P2 / Research — Apple Silicon / MPS Feasibility Validation

Follow the phased research and acceptance plan in
[Apple Silicon / macOS MPS Support](#apple-silicon--macos-mps-support). This is
an `EXPERIMENTAL CANDIDATE`, not an implemented backend or support commitment.
It must not delay the P1 NVIDIA hardware-matrix validation or regress the stable
CUDA deployment path.

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

| Platform / hardware | APP | GUI | Basic OCR | Unlimited-OCR backend | Real inference | Overall evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Windows 11, RTX 3060 12 GiB | VERIFIED | VERIFIED | VERIFIED | `transformers_cuda` / SUPPORTED_WITH_CHANGES | VERIFIED | VERIFIED on this device |
| Ubuntu 20.04, GTX 1060 6 GiB | VERIFIED | NOT_TESTED (SSH had no display) | NOT_TESTED (executable absent) | `transformers_cuda` / UNSUPPORTED on device | NOT_TESTED | VERIFIED safe rejection |
| Ubuntu 22.04, dual RTX 4090 24 GiB | VERIFIED | NOT_TESTED_NO_DISPLAY | UNAVAILABLE (executable absent) | `transformers_cuda` / SUPPORTED_WITH_CHANGES | VERIFIED | VERIFIED on this device and revision |
| Linux, supported NVIDIA GPU | SUPPORTED (CI/source; one real eligible host) | NOT_TESTED | NOT_TESTED | `transformers_cuda` / PARTIAL DEVICE EVIDENCE | PARTIAL DEVICE EVIDENCE | P1 broader matrix |
| Windows, second NVIDIA GPU | SUPPORTED (CI/source) | NOT_TESTED | NOT_TESTED | `transformers_cuda` / NOT_TESTED | NOT_TESTED | FUTURE — P1 |
| WSL2 with NVIDIA GPU | EXPERIMENTAL | NOT_TESTED | NOT_TESTED | `transformers_cuda` / EXPERIMENTAL | NOT_TESTED | EXPERIMENTAL |
| Physical multi-GPU | VERIFIED (AI1 source/CLI) | NOT_TESTED_NO_DISPLAY | UNAVAILABLE on AI1 | `transformers_cuda` / VERIFIED single-device binding | VERIFIED on selected GPU | No sharding or automatic failover claim |
| AMD GPU | SUPPORTED (normal APP) | NOT_TESTED | NOT_TESTED | none in current integration | NOT_TESTED | FUTURE research |
| Apple Silicon Mac mini M1 | NOT_TESTED | NOT_TESTED | NOT_TESTED | `transformers_mps` candidate | NOT_TESTED | NOT_TESTED |
| Apple Silicon Mac mini M2 | NOT_TESTED | NOT_TESTED | NOT_TESTED | `transformers_mps` candidate | NOT_TESTED | NOT_TESTED |
| Apple Silicon Mac mini M3 | NOT_TESTED | NOT_TESTED | NOT_TESTED | `transformers_mps` candidate | NOT_TESTED | NOT_TESTED |
| Apple Silicon Mac mini M4 | NOT_TESTED | NOT_TESTED | NOT_TESTED | `transformers_mps` candidate | NOT_TESTED | NOT_TESTED |
| Later Apple Silicon | NOT_TESTED | NOT_TESTED | NOT_TESTED | `transformers_mps` candidate | NOT_TESTED | NOT_TESTED |
| Intel Mac mini | NOT_TESTED | NOT_TESTED | NOT_TESTED | `transformers_cpu` candidate or none | NOT_TESTED | NOT_TESTED |
| Other CPU-only | SUPPORTED (normal APP) | NOT_TESTED | NOT_TESTED | `transformers_cpu` candidate or none | NOT_TESTED | FUTURE feasibility research |

`SUPPORTED (CI/source)` means the normal Python application is exercised by CI;
it is not equivalent to a physical packaged-GUI or model-runtime verification.
The M-series rows track evidence separately; they do not imply per-generation
backend implementations.

## Apple Silicon / macOS MPS Support

Current state: **`EXPERIMENTAL CANDIDATE` / `NOT_TESTED`**. There is no
implemented `transformers_mps` provider, no real Mac model-load or OCR result,
and no Apple Silicon support claim. The current Compatibility Engine safely
rejects this model path because its reviewed automatic backend is NVIDIA CUDA;
that implementation fact is not a permanent conclusion that MPS is impossible.

### Primary-source findings (reviewed 2026-07-15)

- The latest [Unlimited-OCR GitHub revision](https://github.com/baidu/Unlimited-OCR/tree/528fca4e2161e23231d05666a6d35155dcb1957e)
  is still the currently pinned source revision. Its official Transformers
  instructions explicitly describe NVIDIA GPU inference, load BF16 weights,
  and call `model.eval().cuda()`.
- The latest [official Hugging Face model revision](https://huggingface.co/baidu/Unlimited-OCR/tree/ee63731b6461c8afcdcc7b15352e7d2ffecc2ead)
  is still the pinned model/custom-code revision. Static review found 14 active
  `.cuda()` calls and three `torch.autocast("cuda", dtype=torch.bfloat16)`
  contexts in `modeling_unlimitedocr.py`, plus BF16 model configuration. No MPS
  device branch exists.
- The custom model code conditionally references FlashAttention in the language
  model and uses scaled-dot-product attention in the vision encoder. No active
  `torch.ops`, C++ extension loader, Triton, or xFormers invocation was found in
  the reviewed Python files, but every executed operator and BF16 path still
  needs real MPS validation.
- [PyTorch documents MPS](https://docs.pytorch.org/docs/stable/notes/mps) as a
  separate device backend and distinguishes `torch.backends.mps.is_built()`
  from `torch.backends.mps.is_available()`. Moving a generic PyTorch module to
  `mps` does not prove Unlimited-OCR custom code or all its operators are valid.
- [Apple's current PyTorch/Metal guidance](https://developer.apple.com/metal/pytorch/)
  documents Apple Silicon, MPS device creation, and a beta-status backend. Its
  2026-07-15 page lists Apple Silicon, macOS 14+, Python 3.10+, and stable
  PyTorch 2.11.0. Those are current-source inputs, not permanent project
  compatibility thresholds and must be refreshed before implementation.
- Apple Silicon uses unified memory rather than a discrete NVIDIA VRAM pool.
  The NVIDIA VRAM gate must not be reused. Apple exposes
  [`hasUnifiedMemory` and recommended-working-set concepts](https://developer.apple.com/documentation/metal/mtldevice/hasunifiedmemory),
  while PyTorch exposes MPS allocator metrics such as
  [`driver_allocated_memory`](https://docs.pytorch.org/docs/stable/generated/torch.mps.driver_allocated_memory.html)
  and documented allocator limits.

No official MPS/CPU patch is merged in the upstream default branch. Relevant
community work must remain non-authoritative:

- [issue #18](https://github.com/baidu/Unlimited-OCR/issues/18) is open and
  reports empty MPS output caused by the image-embedding `masked_scatter` path;
- [issue #53](https://github.com/baidu/Unlimited-OCR/issues/53) is open and
  reports multi-page output degradation under sustained MPS/CPU inference;
- [PR #19](https://github.com/baidu/Unlimited-OCR/pull/19) was closed without
  merge;
- [PR #49](https://github.com/baidu/Unlimited-OCR/pull/49),
  [PR #56](https://github.com/baidu/Unlimited-OCR/pull/56), and
  [PR #57](https://github.com/baidu/Unlimited-OCR/pull/57) propose macOS,
  MPS, or CPU changes but remain open and unmerged.

These reports make MPS a plausible research target while also providing direct
evidence that model load, lack of exceptions, or `mps.is_available() == true`
cannot be treated as successful OCR support.

### Candidate provider architecture

```text
UnlimitedOCRProvider
├── transformers_cuda       # implemented managed path
├── transformers_mps        # design candidate; not implemented
├── transformers_cpu        # feasibility candidate; not implemented
└── future_quantized_backend # research only
```

Apple Silicon generations share one candidate architecture and capability
model. M1, M2, M3, M4, and later chips remain separate matrix evidence rows so
results are not generalized across hardware without data. Intel Mac is a
different architecture and must be evaluated independently as CPU-only,
another proven backend, or unsupported; it does not inherit an Apple Silicon
MPS conclusion.

### Environment Inspector extension requirements

Before compatibility evaluation, a future read-only inspector must record:

- macOS version and native machine architecture;
- Apple Silicon detection and chip family/model;
- total and available unified memory plus system memory pressure;
- native arm64 versus Rosetta/x86_64 Python and executable paths;
- Python, uv/Conda, and project-runtime compatibility;
- PyTorch version and build provenance;
- `torch.backends.mps.is_built()` and `torch.backends.mps.is_available()`;
- successful creation and a trivial operation on `torch.device("mps")`;
- available disk and writable managed roots;
- custom model-code device, dtype, operator, and fallback compatibility.

The inspector must remain safe when torch is absent and must not load or
download the model. Apple Silicon receives a separate compatibility profile:
minimum/recommended unified memory, acceptable memory pressure, swap behavior,
model-load feasibility, inference feasibility, and performance class are
derived only from real acceptance data. Devices with 16, 24, and 32+ GiB are
useful validation targets, not support thresholds or guarantees.

### Phase A — Static Compatibility Research

- Audit every active `.cuda()` call and replaceability with explicit device
  placement in an isolated prototype, without changing the stable CUDA path.
- Audit CUDA-specific autocast, BF16/FP16/FP32 behavior, CPU fallback, and all
  image/mask tensor placement.
- Audit scaled-dot-product/FlashAttention selection, native/custom extensions,
  unsupported operators, and all trusted custom remote model code.
- Compare the latest GitHub and model revisions with the pinned revisions.
- Re-check upstream issues/PRs and determine whether an MPS/CPU fix has been
  officially merged; community patches are research inputs only.

### Phase B — Environment Inspector Extension

Add Apple Silicon, native/Rosetta Python, unified-memory, MPS build/availability,
MPS smoke-device, and memory-pressure detection with fixtures for M1 through M4
profiles. Existing Windows/Linux NVIDIA reports and decisions must remain green.
This phase performs no model installation or inference.

### Phase C — Experimental MPS Runtime

Only after Phase A demonstrates a technically credible path, prototype
`transformers_mps` behind an explicit experimental gate and private worker.
Device placement, dtype, unsupported-op behavior, CPU fallback policy, output
correctness, memory limits, and cancellation must be explicit. MPS availability
alone must never produce `SUPPORTED` or trigger a model download.

### Phase D — Real Mac Acceptance

At least one physical Apple Silicon Mac must complete all of the following
before any device-specific support claim:

- official repository setup, native arm64 Python selection, and uv reuse or
  verified managed bootstrap;
- private PyTorch MPS environment, model download/resume, inventory, and
  checksum verification;
- actual model load and single-image OCR;
- multi-page OCR where technically applicable and all five existing OCR test
  classes;
- inference benchmark, peak unified memory, memory pressure, and swap
  observation;
- repeated inference, cancellation, worker recovery, unload, cleanup, and
  uninstall;
- proof of no system-wide Python, PATH, Driver, framework, or unrelated runtime
  modification;
- full CUDA/backend regression suite and packaged/source APP checks.

### Evidence Required Before Claiming Apple Silicon Support

1. Native arm64 environment is verified.
2. MPS is built, actually available, and passes device creation/operation.
3. Exact source, model, and custom-code revisions are verified.
4. No unhandled CUDA hardcoding remains in the exercised path.
5. Model load succeeds without silent CPU/device misplacement.
6. Real OCR output succeeds and passes correctness checks.
7. Peak unified memory, memory pressure, and swap are measured.
8. Repeated single- and multi-page inference is stable.
9. Cancellation, timeout, worker recovery, and fallback are verified.
10. Cleanup and uninstall preserve external/system state.
11. Existing CUDA backend and default Tesseract regressions remain green.

### Alternative research routes

- **PyTorch MPS:** primary candidate because the official model is Transformers
  custom code, but not proven compatible.
- **MLX conversion:** Apple-native research only; requires verified architecture,
  tokenizer, vision encoder, custom generation, and quality parity.
- **Quantized model:** consider only with a reproducible conversion, exact
  revision provenance, integrity policy, and measured OCR quality loss.
- **GGUF / llama.cpp:** consider only if the actual multimodal architecture,
  projector, vision preprocessing, and custom generation are verified compatible.
- **Ollama / LM Studio:** consider only if a verified compatible quantization
  and multimodal runtime exist; catalog presence or a community upload is not
  evidence of compatibility.

## 4. Known Limitations

- Successful real Unlimited-OCR inference evidence currently comes from one RTX
  3060 runtime and one pinned model/dependency combination.
- The Acer Nitro proves safe rejection, ordinary Linux APP/CLI setup, and honest
  headless reporting; it does not prove supported-GPU Linux inference.
- The dual-RTX 4090 Linux device proves fixed-revision model load, OCR,
  benchmark, cancellation/recovery, and deterministic single-GPU binding. It
  does not prove sharded inference, automatic failover, every Linux/NVIDIA
  combination, or production-document accuracy.
- The actual managed-uv download/extract path is automated-test evidence only
  because all three real validation devices already had a compatible uv
  installation.
- AMD ROCm, Apple Silicon/MPS, Intel Mac/CPU-only, WSL2 inference, and physical
  multi-GPU inference have no support claim beyond the matrix above. Apple
  Silicon is an experimental candidate, not a permanently rejected platform.
- SGLang automation remains blocked by conflicting upstream dependency pins;
  Docker/vLLM paths are metadata/research candidates only.
- OCR accuracy is currently demonstrated with deterministic synthetic assets,
  not a versioned representative corpus with CER/WER and table metrics.
- Multi-GPU detection selects one eligible highest-VRAM device, uses the lowest
  index as a deterministic equal-VRAM tie-break, and binds its UUID or index to
  the private worker. Inference is not sharded across GPUs.
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
- Apple Silicon PyTorch MPS, MLX conversion, and verified quantized routes under
  the dedicated phased research gate above.
- AMD ROCm acceleration only with upstream-compatible evidence.
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
- Do not permanently classify Apple Silicon as impossible based only on the
  current CUDA-only integration; keep it blocked from installation while its
  evidence status remains `NOT_TESTED` / `EXPERIMENTAL CANDIDATE`.
- Do not reuse NVIDIA VRAM thresholds as Apple unified-memory thresholds or
  treat an unmerged community MPS patch as official upstream support.

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
- PyTorch/Apple MPS requirements, operator support, allocator behavior, or
  official macOS guidance;
- Transformers or custom model-code dependencies;
- selected model inventory, size, license, or checksum;
- managed uv pinned or minimum-compatible version;
- supported Python versions or APP packaging/runtime layout;
- compatibility thresholds for RAM, VRAM, GPU generation, or disk;
- the live metadata audit reports `changed: true` or conflicting sources.
- an Apple Silicon/CPU issue or PR is merged into an official upstream revision.

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
