# Managed Unlimited-OCR Setup

Unified PDF Toolkit can use [Baidu Unlimited-OCR](https://github.com/baidu/Unlimited-OCR)
as an optional advanced local OCR provider. Tesseract remains the default and
continues to work when the advanced provider is unavailable.

The managed path is opt-in. Device analysis is read-only; no large model,
private AI runtime, Driver, CUDA Toolkit, PATH entry, or global Python package is
changed until the user reviews the generated plan and accepts every consent
item.

## What the APP checks

The Environment Inspector records OS and architecture, CPU and core count,
total/available RAM, all detected GPUs and VRAM, NVIDIA Driver and Driver API
CUDA version, system CUDA Toolkit, Python and package tools, PyTorch CUDA state,
bounded common-location Python/uv/Conda/pyenv discovery, Basic OCR availability,
free disk, APP runtime, GUI/display state, Docker, and WSL2. It uses Python/OS
APIs and NVML first,
then bounded argv-only command probes when an API is unavailable.

The Compatibility Engine returns one of:

- `SUPPORTED`
- `SUPPORTED_WITH_CHANGES`
- `EXPERIMENTAL`
- `CPU_ONLY_IF_AVAILABLE`
- `UNSUPPORTED`
- `UNKNOWN`

It evaluates OS, CPU architecture, NVIDIA GPU generation, VRAM, Driver family,
PyTorch CUDA wheel availability, RAM, disk, Python provisioning, upstream
conflicts, and metadata age. Detecting an NVIDIA GPU alone is never sufficient.
Platforms without a verified upstream path are reported conservatively; the APP
does not claim AMD, Apple Silicon, or CPU-only support for this model.

## Current pinned source evidence

Compatibility metadata lives in
`src/ocr/deployment/resources/unlimited_ocr_compatibility.json`. The current
reviewed snapshot pins:

- Unlimited-OCR source revision
  `528fca4e2161e23231d05666a6d35155dcb1957e`;
- Hugging Face model revision
  `ee63731b6461c8afcdcc7b15352e7d2ffecc2ead`;
- model weight SHA-256
  `2bc48a7a110061ea58fff65d3169367eebe3aee371ca6968dc2219c1b2855fc6`;
- the complete selected file inventory and exact package versions from the
  upstream Transformers instructions.

The upstream README currently says CUDA 12.9, while official PyTorch 2.10
wheels are published for `cu126`, `cu128`, and `cu130`. The APP resolves this
through official wheel/Driver compatibility metadata; it does not install a
fictional `cu129` wheel. SGLang automatic setup remains blocked because the
upstream instructions contain conflicting `kernels` pins.

Refresh auditing is explicit and maintainer-reviewed:

```powershell
python scripts/refresh_unlimited_ocr_metadata.py
python scripts/refresh_unlimited_ocr_metadata.py --json
python scripts/refresh_unlimited_ocr_metadata.py --write-reviewed --acknowledge-conflicts
```

The auditor accepts only allowlisted HTTPS sources, limits response size, and
does not write by default. A source change causes a non-zero audit result until
the candidate is reviewed.

## Installation design

The resolver reuses a compatible uv executable first, including one found in a
bounded user-local location outside `PATH`, and passes its absolute path. It can
reuse a private Conda prefix when uv is unavailable. If neither exists on an
otherwise eligible device, it can plan a pinned APP-managed uv prerequisite.
The bundled bootstrap metadata currently pins uv 0.11.28, requires an existing
uv to be at least 0.9.0, selects an OS/architecture-specific official release
archive, and records its exact size and SHA-256. The bootstrap occurs only after
plan-bound consent, extracts only `uv`/`uvx` into the managed runtime, verifies
the executable, retries safely, and cleans incomplete files. It does not invoke
an internet-fetched shell script, edit a shell profile, or change `PATH`.

The generated plan uses argv
arrays, never a shell string. It installs a compatible official PyTorch wheel
inside the private runtime and normally does not require the system CUDA
Toolkit. It never removes another CUDA installation or overwrites an existing
Python environment.

Default managed locations are under:

```text
%LOCALAPPDATA%\UnifiedPDFToolkit\ocr\
├── runtimes\unlimited-ocr-transformers\environment
├── models\snapshots\<pinned-model-revision>
├── models\hub
├── sessions
└── logs
```

The resumable pipeline is:

```text
PRECHECK -> COMPATIBILITY_ANALYSIS -> USER_CONSENT
-> SNAPSHOT_CURRENT_STATE -> UV_BOOTSTRAP -> CREATE_ISOLATED_ENV
-> INSTALL_DEPENDENCIES -> DOWNLOAD_MODEL
-> VERIFY_CHECKSUM_OR_FILES -> LOAD_MODEL -> RUN_SMOKE_TEST
-> RUN_OCR_TEST -> BENCHMARK -> REGISTER_WITH_APP -> COMPLETE
```

Each journal step has a stable ID, status, progress, human message, error code,
attempt count, retry policy, recovery strategy, timestamps, and structured
details. Package/environment creation retries transient failures. Model download
uses the Hugging Face resumable cache, reports byte progress, and retries up to
three attempts. Cancellation terminates the subprocess tree; a later run resumes
the same pinned plan without repeating completed stages. Terminated command
handles are explicitly reaped so repeated timeout/cancel cycles do not retain
controller-side process resources.

An operating-system-held lock permits only one installer for the managed root.
The lock is released automatically if the APP or computer stops, so a leftover
lock file alone does not block recovery. Invalid or partially written journals
are quarantined as `installation.corrupt-*.json`, then rebuilt with recovery
metadata instead of being trusted or silently overwritten. Atomic state writes
retry bounded transient sharing violations. A valid existing private
environment and a complete pinned model snapshot are reused; the integrity
stage still verifies the complete required-file inventory and weight hash.

## GUI workflow

Open `Settings / Recent`, then choose the managed Unlimited-OCR device analysis
and setup action. On an executable plan the dialog offers:

- install and enable;
- technical details;
- not now.

An unsupported or unknown plan is informational only: install is disabled and
the serialized action list contains only technical details and not now.

All consent boxes start unchecked. The user must acknowledge the large
download, private environment/cache, pinned custom model code, resource use,
local temporary page images, and lack of accuracy/performance/OOM guarantees.
Consent is bound to the exact plan and metadata revision; a changed command,
model revision, hardware plan, or metadata revision requires new consent.

After all validation stages pass, the provider is registered and appears in
Document OCR automatically. A developer can still expose a manually configured
controlled-beta worker with `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.

## CLI workflow

Read-only inspection and plan generation do not install anything:

```powershell
pdf-toolkit ocr inspect --json
pdf-toolkit ocr plan --json
pdf-toolkit ocr status --json
```

Setup requires the current plan ID and all six explicit acknowledgement flags:

```powershell
pdf-toolkit ocr setup `
  --plan-id <reviewed-plan-id> `
  --ack-large-download `
  --ack-private-environment `
  --ack-custom-code `
  --ack-resource-usage `
  --ack-local-processing-and-temporary-files `
  --ack-no-performance-guarantee
```

This deliberately cannot be shortened to a single `--yes` switch.

Cleanup also requires the exact current plan ID:

```powershell
pdf-toolkit ocr uninstall --confirm-plan-id <reviewed-plan-id>
pdf-toolkit ocr uninstall --confirm-plan-id <reviewed-plan-id> --remove-model --clear-download-cache
```

The second form is the explicit full cleanup: it removes every managed pinned
model revision plus the isolated Hugging Face/Transformers download and custom-
module caches. Runtime-only uninstall keeps all model/cache data for reuse.

## Validation and benchmark

Setup verifies the private Python executable, pinned dependency imports,
PyTorch/CUDA visibility, selected GPU, model load, and real inference. The
functional suite contains deterministic synthetic examples for plain text,
tables, Chinese/English text, two-column layout, and 90-degree rotation. It
records inference time, peak RAM/VRAM, output hash/length, expected-term match
ratio, backend, model revision, and dependency versions without putting full OCR
text in the normal setup log.

The benchmark classifies the device as real-time suitable, general OCR
suitable, usable but slow, easily OOM, or not recommended for local use. A model
load alone does not count as successful setup.

Maintainers with an already installed, consented runtime can run the opt-in
real-device harness without installing or downloading again:

```powershell
uv run --no-sync python scripts/validate_managed_unlimited_ocr.py `
  --reload-cycles 2 --stress-iterations 50 --output <report.json>
```

The report records cold-load and per-request timing, mean/median/p95/max
latency, hashes/lengths, output consistency, expected-term matches,
RSS/allocated VRAM, Windows handles or Linux file descriptors, thread/open-file
counts, worker PIDs, cleanup, and dependency versions, but not full OCR text.

## Security and privacy boundaries

- Document pages and OCR text remain on the device.
- Network access is used only for reviewed package/model sources during setup.
- Hugging Face telemetry is disabled in the private runtime.
- Pinned custom model code runs only in the private worker process and loads
  from the verified local snapshot.
- Model inputs and outputs are restricted to APP-managed session paths.
- Cache, runtime, session, and worker-output checks resolve every path and reject
  symlink/junction escapes before reading, executing, or deleting content.
- Worker requests enforce bounded prompt, timeout, option, and aggregate output
  limits. Protocol corruption or response-ID mismatch forces a clean restart.
- Normal logs omit source paths, image data, and OCR text.
- No Driver update, system CUDA change, PATH edit, admin elevation, or global
  Python modification is part of the managed plan.
- Driver or other system changes, if ever necessary, require a separate design
  and separate explicit consent; the current installer stops instead.
- Runtime/model cleanup is restricted to validated APP-managed child paths.

## Failure behavior

User-facing errors use stable codes such as `NO_SUPPORTED_GPU`,
`INSUFFICIENT_VRAM`, `NVIDIA_DRIVER_TOO_OLD`, `PYTORCH_CUDA_MISMATCH`,
`MODEL_DOWNLOAD_FAILED`, `MODEL_INTEGRITY_FAILED`, `CUDA_OOM`,
`PERMISSION_DENIED`, and `NETWORK_ERROR`. Technical details remain available for
export, but a traceback is not the only user message.

If the advanced provider is missing, unhealthy, or fails during recognition,
the provider router preserves the existing Tesseract path. Unlimited-OCR does
not prevent the APP from starting or using its normal PDF tools.

Explicit cancellation is not treated as a provider failure and is never routed
into an unexpected Tesseract retry. The persistent worker is terminated, and a
later request performs an idempotent model reload in a new worker.

## Known limitations

- Each device still requires its own successful install and benchmark; the
  development-computer result is not a portability or performance guarantee.
- The current automatic backend is Transformers/CUDA on verified Windows or
  Linux NVIDIA hardware. WSL2 is experimental.
- AMD GPU, Apple Silicon, and CPU-only execution are not claimed as supported
  by this integration.
- Docker/vLLM and SGLang metadata are retained for future resolvers but are not
  automatically installed while upstream compatibility is ambiguous.
- Multi-GPU inspection is supported; the current plan selects the eligible GPU
  with the most VRAM, breaking equal-VRAM ties by the lowest device index. The
  compatibility and consent reports disclose that device, the plan ID binds its
  stable UUID or index, and the private worker receives `CUDA_VISIBLE_DEVICES`.
  One inference is not split across GPUs.
- A consented Ubuntu dual-RTX 4090 run verified real single-GPU UUID binding,
  model load, OCR, cancellation/recovery, benchmark, and 50-request stability;
  the unselected GPU remained at zero compute utilization during the sampled
  run. This is evidence for that fixed model revision and host, not a general
  Linux/NVIDIA performance guarantee.
