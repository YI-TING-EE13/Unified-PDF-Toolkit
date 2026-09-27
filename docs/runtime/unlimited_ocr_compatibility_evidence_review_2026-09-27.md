# Unlimited-OCR compatibility evidence review

- **Checked:** 2026-09-27 03:53:26 UTC
- **Repository HEAD:** `30d255ef6bc2f4f0531962998d06fb5680feb15e`
- **Scope:** Evidence review for the managed Transformers runtime compatibility record. The canonical metadata was refreshed through its reviewed-write path after the evidence review; no application code changed.

## Executive findings

- The prior compatibility JSON pinned Unlimited-OCR source `528fca4e2161e23231d05666a6d35155dcb1957e` and HF model `ee63731b6461c8afcdcc7b15352e7d2ffecc2ead`. The reviewed metadata now pins current GitHub `main` SHA `d49ff64afffc1f47ab563dc1c589bc2f78808fa4` and HF `main` SHA `07dea832e22aefee32ad281d4b80551282e1c168`.
- The upstream changes between the prior reviewed source revision and the inspected source `main` tip are README-only. HF's commits after the prior reviewed model revision are also README-only. Fixed-revision README fetches show a 1,564-byte model-card increase; the weight and required download inventory are unchanged.
- Upstream still reports testing on Python 3.12.3 and CUDA 12.9. PyTorch does not publish a `cu129` index in its current wheel profiles: compatible candidate profiles are `cu126`, `cu128`, and `cu130`. The latter are wheel-build profiles, not statements about the installed system CUDA Toolkit.
- A no-install `uv pip compile` qualification on Python 3.12.3 resolved the pinned Transformers candidate dependency set for Windows x86-64 and Linux x86-64 with each of those three PyTorch indexes (six successful resolutions). This demonstrates package-resolution availability at the checked time; it is not an install, import, GPU, or OCR execution test.
- NVIDIA's published minor-version-compatibility floors support the current profile map: CUDA 12.x: Linux `525.60.13`, Windows `528.33`; CUDA 13.x: `580` on both OSes. These are MVS floors and can have feature/PTX caveats; they are not the driver versions bundled with each Toolkit release.
- The pinned uv 0.11.28 release and all six corresponding asset names, exact byte sizes, and SHA-256 digests match the official GitHub release API. At review time uv 0.12.19 was the latest release. The existing pin remains valid and is not upgraded just because a newer release exists.

## Upstream source revision and README changes

The fixed upstream sources are [Unlimited-OCR at `d49ff64afffc1f47ab563dc1c589bc2f78808fa4`](https://github.com/baidu/Unlimited-OCR/tree/d49ff64afffc1f47ab563dc1c589bc2f78808fa4) and its [README at that revision](https://github.com/baidu/Unlimited-OCR/blob/d49ff64afffc1f47ab563dc1c589bc2f78808fa4/README.md). The pre-refresh metadata pinned source `528fca4e2161e23231d05666a6d35155dcb1957e` ([previously pinned README](https://github.com/baidu/Unlimited-OCR/blob/528fca4e2161e23231d05666a6d35155dcb1957e/README.md)). GitHub's commit diffs between those points report four README-only commits: `1ab6b46b989ebf26328a968d87ce583a9650ab90` (+1 line, ms-swift training announcement), `026090f09db8424eb861317dc1398c552c48dfd0` (+3 lines, Trendshift badge), `4ba2ea3eb384757710bc7f7678922b0b61045448` (+30 lines, OmniDocBench post-processing helper), and `d49ff64afffc1f47ab563dc1c589bc2f78808fa4` (+2 lines, the helper's `DET_RE` pattern and blank line). The aggregate diff is +36 lines and no deletions; these commits do not change the model/runtime implementation files. See the [upstream commit history](https://github.com/baidu/Unlimited-OCR/commits/main/) for the README-only update sequence.

The source README was reviewed at both fixed revisions and its upstream history reports only the four README commits listed above (+36/-0 lines). Exact source README byte size and SHA-256 were not needed by the metadata contract and were not recorded. The model README has independently fetched exact fixed-revision bytes and hashes below.

At the fixed current README revision, upstream says its requirements were tested with Python 3.12.3 and CUDA 12.9. It documents Transformers inference with custom model code, BF16 and CUDA, and PDF-to-image conversion using PyMuPDF. Its candidate package pins currently recorded in the compatibility JSON are: `torch==2.10.0`, `torchvision==0.25.0`, `transformers==4.57.1`, `Pillow==12.1.1`, `matplotlib==3.10.8`, `einops==0.8.2`, `addict==2.4.0`, `easydict==1.13`, `pymupdf==1.27.2.2`, and `psutil==7.2.2`. The README's tested Python version is evidence of a tested configuration, not a published minimum/maximum Python support range.

The README still contains a SGLang install conflict: prose says `kernels==0.9.0`, while its command installs `kernels==0.11.7`. Keep automated SGLang setup blocked until upstream clarifies it. Its separate vLLM Docker guidance labels the default image CUDA 13.0 and the Hopper image CUDA 12.9; those container profiles are not the managed Transformers wheel profile.

## Hugging Face model snapshot and hash fields

The current HF snapshot inspected is [`07dea832e22aefee32ad281d4b80551282e1c168`](https://huggingface.co/baidu/Unlimited-OCR/tree/07dea832e22aefee32ad281d4b80551282e1c168); the previously pinned revision was `ee63731b6461c8afcdcc7b15352e7d2ffecc2ead`. HF's intervening commit history is README-only, including the current tip's `+2/-0` README update. Fixed-revision raw README fetches from [`ee63731...`](https://huggingface.co/baidu/Unlimited-OCR/resolve/ee63731b6461c8afcdcc7b15352e7d2ffecc2ead/README.md) and [`07dea832...`](https://huggingface.co/baidu/Unlimited-OCR/resolve/07dea832e22aefee32ad281d4b80551282e1c168/README.md) measured 9,544 bytes / SHA-256 `d6673d0d06627aa042c312de075f27fe72705406d16e2bd42165c5edad5a54dd` and 11,108 bytes / SHA-256 `4f573db255db5262bfe2ea92e459bfc11635a456f210e3a96289bb9605077a55`, respectively: +1,564 bytes. The HF model API's `?revision=` query returned the current `sha` even when an older revision was requested, so that response was not used as historical evidence; the raw README checks used revision-qualified paths. The current revision includes all 13 files required by metadata: `LICENSE`, `config.json`, `configuration_deepseek_v2.py`, `conversation.py`, `deepencoder.py`, `model-00001-of-000001.safetensors`, `model.safetensors.index.json`, `modeling_deepseekv2.py`, `modeling_unlimitedocr.py`, `processor_config.json`, `special_tokens_map.json`, `tokenizer.json`, and `tokenizer_config.json` ([fixed-revision file tree](https://huggingface.co/baidu/Unlimited-OCR/tree/07dea832e22aefee32ad281d4b80551282e1c168), [HF commit history](https://huggingface.co/baidu/Unlimited-OCR/commits/main)).

The model card's Transformers examples require `trust_remote_code=True`; the model repository includes Python implementation files. The production path therefore needs to preserve the managed worker's isolation boundary. The existing resolver already warns that custom Python code runs only in the private worker environment ([`resolver.py`](../../src/ocr/deployment/resolver.py)).

The current weight page reports `model-00001-of-000001.safetensors` size `6,672,547,120` bytes, SHA-256 `2bc48a7a110061ea58fff65d3169367eebe3aee371ca6968dc2219c1b2855fc6`, and Xet hash `56e1945a78f43c9777337ff08075d280552b25791889d4a4ccc85ee82386a517` ([HF file page](https://huggingface.co/baidu/Unlimited-OCR/blob/main/model-00001-of-000001.safetensors)). Those match the current metadata's `weight_bytes` and `weight_sha256`. The generator's `weight_blob_sha` is sourced from the HF API's `blobId` field (`2e629fa069397ca38770f289f36f80af207401ba`); it is a distinct API field, not the file SHA-256 or the Xet hash. The model API still reports that same `blobId` for the current weight. The intervening HF commits are README-only, so no model or required custom-code file changed across the reviewed revision range.

## PyTorch wheels and no-install resolution evidence

PyTorch's [2.10.0 installation matrix](https://pytorch.org/get-started/previous-versions/) lists CUDA wheel indexes for 12.6, 12.8, and 13.0; the corresponding official indexes are [cu126](https://download.pytorch.org/whl/cu126/), [cu128](https://download.pytorch.org/whl/cu128/), and [cu130](https://download.pytorch.org/whl/cu130/). The no-install resolutions below selected CPython 3.12 wheels for Windows x86-64 and Linux x86-64 with matching `+cu126`, `+cu128`, and `+cu130` builds. The upstream CUDA 12.9 test statement must not be converted into a PyTorch `cu129` build; a `cu128` or `cu130` wheel build is a separate runtime choice.

Resolution evidence was produced on 2026-09-27 with `uv 0.9.18`, Python target `3.12.3`, `--only-binary :all:`, `--no-cache`, and `--native-tls`. The available build interpreter was Python 3.12.12 because 3.12.3 was not installed; the requested target remained 3.12.3 and binary-only mode prevented source builds. Each temporary profile project used `requires-python = ">=3.12.3,<3.13"`, an explicit index named `pytorch` at `https://download.pytorch.org/whl/cu126`, `.../cu128`, or `.../cu130`, and explicit source mapping `torch = { index = "pytorch" }`, `torchvision = { index = "pytorch" }`; all other dependencies used uv's default PyPI index. The resolver command template was:

```text
uv pip compile --python-version 3.12.3 --python-platform x86_64-pc-windows-msvc|x86_64-unknown-linux-gnu --only-binary :all: --no-cache --native-tls --no-header --no-annotate --output-file <temp>/<profile>/requirements.txt <temp>/<profile>/pyproject.toml
```

Each target platform was resolved against all three CUDA indexes:

| OS | Profile | Python target / resolver interpreter | Package result | Classification |
| --- | --- | --- | --- | --- |
| Windows x86-64 | cu126 | 3.12.3 / 3.12.12 | 41 wheels; `torch==2.10.0+cu126`, `torchvision==0.25.0+cu126` | `RESOLVES` |
| Windows x86-64 | cu128 | 3.12.3 / 3.12.12 | 41 wheels; `torch==2.10.0+cu128`, `torchvision==0.25.0+cu128` | `RESOLVES` |
| Windows x86-64 | cu130 | 3.12.3 / 3.12.12 | 41 wheels; `torch==2.10.0+cu130`, `torchvision==0.25.0+cu130` | `RESOLVES` |
| Linux x86-64 | cu126 | 3.12.3 / 3.12.12 | 58 wheels; `torch==2.10.0+cu126`, `torchvision==0.25.0+cu126` | `RESOLVES` |
| Linux x86-64 | cu128 | 3.12.3 / 3.12.12 | 58 wheels; `torch==2.10.0+cu128`, `torchvision==0.25.0+cu128` | `RESOLVES` |
| Linux x86-64 | cu130 | 3.12.3 / 3.12.12 | 58 wheels; `torch==2.10.0+cu130`, `torchvision==0.25.0+cu130` | `RESOLVES` |

All six runs resolved `torch==2.10.0`, `torchvision==0.25.0`, and the remaining pins listed above. This is a report of the coordinator's actual no-install resolver runs; it does not establish installation success, imports, execution, numerical behavior, or GPU compatibility. Managed production installs torch + torchvision from the selected CUDA index and the other pinned packages separately; `torchaudio` appears only in the separate legacy/manual setup script and is outside the managed production set ([resolver](../../src/ocr/deployment/resolver.py), [manual setup](../../scripts/setup_local_unlimited_ocr_runtime.py)).

## NVIDIA driver minimums

NVIDIA's [minor-version compatibility guide](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) gives CUDA 12.x a family MVS floor of `>=525` and CUDA 13.x `>=580`; it explicitly warns about limited feature support and PTX on older drivers. The versioned CUDA 12.6 release notes provide exact x86-64 floors `Linux >=525.60.13`, `Windows >=528.33` ([Table 2](https://docs.nvidia.com/cuda/archive/12.6.3/cuda-toolkit-release-notes/index.html)). The CUDA 13.0 release notes likewise give CUDA 13.x `>=580` ([Table 2](https://docs.nvidia.com/cuda/archive/13.0.1/cuda-toolkit-release-notes/index.html)). The local profile mapping is therefore consistent:

| PyTorch profile | CUDA family | Windows MVS minimum | Linux MVS minimum |
| --- | --- | ---: | ---: |
| cu126 | 12.x | 528.33 | 525.60.13 |
| cu128 | 12.x | 528.33 | 525.60.13 |
| cu130 | 13.x | 580 | 580 |

These are documented minor-version-compatibility floors, not the driver versions bundled with a Toolkit release and not a guarantee that every CUDA feature works at the floor. No physical GPU execution was part of this research.

The current Windows review host reports NVIDIA Driver `616.92`, GeForce RTX 3060, 12,288 MiB VRAM from `nvidia-smi`; this is a host observation, not cross-platform runtime qualification.

## uv release and bootstrap assets

The metadata pins uv `0.11.28` with minimum-compatible version `0.9.0`. The [0.11.28 release](https://github.com/astral-sh/uv/releases/tag/0.11.28) still lists the matching Windows, Linux, and macOS assets. The [official GitHub release API](https://api.github.com/repos/astral-sh/uv/releases/tags/0.11.28)'s asset URLs, names, sizes, and SHA-256 digests all match canonical metadata. The [current releases page](https://github.com/astral-sh/uv/releases) showed uv `0.12.19` as latest (released 2026-09-24) at the checked time.

| Platform | Asset | Size (bytes) | Published SHA-256 |
| --- | --- | ---: | --- |
| Windows x86-64 | `uv-x86_64-pc-windows-msvc.zip` | 25,568,726 | [`0a23463216d09c6a72ff80ef5dc5a795f07dc1575cb84d24596c2f124a441b7b`](https://releases.astral.sh/github/uv/releases/download/0.11.28/uv-x86_64-pc-windows-msvc.zip.sha256) |
| Windows ARM64 | `uv-aarch64-pc-windows-msvc.zip` | 23,878,916 | [`3248109afad3ec59baad299d324ff53de17e2d9a3b3e21580ffd26744b11e036`](https://releases.astral.sh/github/uv/releases/download/0.11.28/uv-aarch64-pc-windows-msvc.zip.sha256) |
| Linux x86-64 | `uv-x86_64-unknown-linux-gnu.tar.gz` | 26,411,870 | [`e490a6464492183c5d4534a5527fb4440f7f2bb2f228162ad7e4afe076dc0224`](https://releases.astral.sh/github/uv/releases/download/0.11.28/uv-x86_64-unknown-linux-gnu.tar.gz.sha256) |
| Linux ARM64 | `uv-aarch64-unknown-linux-gnu.tar.gz` | 24,689,886 | [`03e9fe0a81b0718d0bc84625de3885df6cc3f89a8b6af6121d6b9f6113fb6533`](https://releases.astral.sh/github/uv/releases/download/0.11.28/uv-aarch64-unknown-linux-gnu.tar.gz.sha256) |
| macOS x86-64 | `uv-x86_64-apple-darwin.tar.gz` | 24,355,900 | [`2ad79983127ffca7d77b77ce6a24278d7e4f7b817a1acf72fea5f8124b4aac5e`](https://releases.astral.sh/github/uv/releases/download/0.11.28/uv-x86_64-apple-darwin.tar.gz.sha256) |
| macOS ARM64 | `uv-aarch64-apple-darwin.tar.gz` | 22,568,053 | [`33540eb7c883ab857eff79bd5ac2aa31fe27b595abecb4a9c003a2c998447232`](https://releases.astral.sh/github/uv/releases/download/0.11.28/uv-aarch64-apple-darwin.tar.gz.sha256) |

This confirms release, exact sizes, and checksums for all six recorded bootstrap assets. It does not establish that uv archives imply OCR model support for those platforms. No version bump is warranted by the newer release alone.

## Evidence decisions

| Claim | Prior reviewed value | Current authoritative evidence | Final value | Disposition |
| --- | --- | --- | --- | --- |
| Unlimited-OCR source revision | `528fca4e2161e23231d05666a6d35155dcb1957e` | Official GitHub `main` is `d49ff64afffc1f47ab563dc1c589bc2f78808fa4`; four intervening commits are README-only (+36/-0 lines). | `d49ff64afffc1f47ab563dc1c589bc2f78808fa4` | Adopt current revision and fixed README URL; runtime implementation unchanged. |
| HF model revision | `ee63731b6461c8afcdcc7b15352e7d2ffecc2ead` | Official HF `main` is `07dea832e22aefee32ad281d4b80551282e1c168`; intervening commits are README-only. Fixed README bytes are +1,564; required files are unchanged. | `07dea832e22aefee32ad281d4b80551282e1c168` | Adopt current revision and fixed tree URL; no binary/custom-code change evidenced. |
| Python/CUDA recipe | Python `3.12.3`, CUDA `12.9` | Current fixed upstream README retains the same tested Python/CUDA statement and Transformers requirements. | Python `3.12.3`, CUDA `12.9` | Retain as an upstream-tested configuration; do not infer cu129 wheels. |
| Transformers package pins | Existing ten exact pins | Current fixed README requirements parse to the same ten pins; six wheel-only environment resolutions succeeded. | Same ten exact pins listed above | Retain unchanged. |
| PyTorch wheel profiles | `cu126`, `cu128`, `cu130` | Official PyTorch 2.10.0 page provides all three profiles and no `cu129`; six target/profile resolutions pass. | `cu126`, `cu128`, `cu130` | Retain unchanged; no cu129 profile added. |
| NVIDIA driver floors | cu126/cu128 Windows `528.33`, Linux `525.60.13`; cu130 both `580` | NVIDIA CUDA 12.x MVS tables give exact Windows/Linux floors; CUDA 13.x MVS floor is `580`. | Same exact schema-2.0 platform maps | Retain unchanged. |
| Required model files and weight | 13 required files; weight `6,672,547,120` bytes, SHA-256 `2bc48a...55fc6` | Current fixed tree has the same inventory; README-only history; current weight API reports same size, `blobId`, and SHA-256. | Same 13 files, size, `blobId`, SHA-256, and Xet hash | Retain inventory and hashes; keep API `blobId` distinct from file digests. |
| Reported total model size | `6,778,368,088` bytes | Current HF API reports `6,778,369,652`; fixed README grew by exactly 1,564 bytes. Required download size remains `6,683,156,996`. | `6,778,369,652` bytes; required download `6,683,156,996` bytes | Update total by +1,564 bytes. |
| uv bootstrap assets | uv `0.11.28`, six recorded archives | Official release API confirms version, each platform/architecture URL, exact size, and SHA-256. | Same six uv `0.11.28` assets | Retain all fields; no upgrade based solely on newer uv `0.12.19`. |
| Resource estimates | RAM/VRAM/disk/compute values labeled conservative project estimate | No upstream guarantee was found; metadata already labels the values as project estimates. | 16/32 GiB RAM, 10/12 GiB VRAM, 5 GiB runtime download, 20 GiB installed, 25 GiB free disk, CC 8.0 | Retain with the conservative project-estimate label. |
| Backend conflicts | CUDA 12.9/cu profile mismatch; SGLang kernels `0.9.0` vs `0.11.7` | Both conflicts remain in current upstream/PyTorch sources. vLLM container guidance remains separately documented. | Same conflicts; SGLang remains `documented_with_conflict`; vLLM image names unchanged | Retain conflicts; automatic SGLang remains blocked. |
| Platform policy | Windows/Linux NVIDIA candidate; WSL2 experimental; macOS/non-NVIDIA unsupported; uv preferred; private Conda fallback | The current documented Transformers recipe remains CUDA/NVIDIA-oriented; existing product compatibility code and tests preserve conservative support states and consent gates. | Same policy: Windows/Linux NVIDIA evaluable; WSL2 experimental; macOS/non-NVIDIA unsupported; uv preferred; managed uv consent-gated; private Conda fallback | Retain product policy and fail-closed setup behavior. |

## Candidate semantic diff

The generator candidate produced immediately before the reviewed write changes only the following semantic fields relative to the pre-refresh bundled JSON at the accepted baseline:

| Field | Prior | Candidate | Classification | Reason |
| --- | --- | --- | --- | --- |
| `checked_at` | `2026-07-14T13:59:31.474861Z` | `2026-09-27T03:53:26.941105Z` | `UPDATED_FROM_NEW_EVIDENCE` | Reviewed-write candidate generated after source, package, driver, asset, artifact, and semantic diff review completed. |
| `source_revision` | `528fca4e2161e23231d05666a6d35155dcb1957e` | `d49ff64afffc1f47ab563dc1c589bc2f78808fa4` | `UPDATED_FROM_NEW_EVIDENCE` | Current README-only upstream tip. |
| `sources.repository_readme` | URL pinned to `528fca4...` | URL pinned to `d49ff64...` | `UPDATED_FROM_NEW_EVIDENCE` | Keep provenance URL aligned with reviewed source revision. |
| `model_revision` | `ee63731b6461c8afcdcc7b15352e7d2ffecc2ead` | `07dea832e22aefee32ad281d4b80551282e1c168` | `UPDATED_FROM_NEW_EVIDENCE` | Current README-only HF tip. |
| `sources.model` | Tree URL pinned to `ee63731...` | Tree URL pinned to `07dea832...` | `UPDATED_FROM_NEW_EVIDENCE` | Keep provenance URL aligned with reviewed model revision. |
| `model_artifacts.reported_total_bytes` | `6,778,368,088` | `6,778,369,652` | `UPDATED_FROM_NEW_EVIDENCE` | +1,564-byte README; model weight and required-download bytes unchanged. |
| All other fields | Existing values | Same values | `UNCHANGED_AND_REVERIFIED` | Package pins, precise driver maps, profiles, required files and hashes, resource estimates, backend/platform policy, conflicts, and all uv assets were checked. |

No field was removed as unverified and no new field was added. The candidate passes the schema-2.0 validator, retains exactly `windows` and `linux` driver keys per profile, and contains neither obsolete threshold form (`minimum_driver_major`, `driver_families`).

## Evidence limits and follow-up

- Exact source README byte delta/hash was not recorded; source review relies on fixed revisions and commit diffs. HF historical API calls with `?revision=` returned the current model `sha`, so fixed-revision README contents were fetched through revision-qualified raw paths instead.
- Runtime install/import, GPU execution, OCR output, full model download, and behavior on actual Windows/Linux hosts were not exercised. Resolver success is package-availability evidence only.
- The canonical JSON was written only after the source, package, driver, asset, artifact, and candidate semantic reviews completed, using `python scripts/refresh_unlimited_ocr_metadata.py --write-reviewed --acknowledge-conflicts`; see [`unlimited_ocr_compatibility.json`](../../src/ocr/deployment/resources/unlimited_ocr_compatibility.json).
