# Experimental Local Unlimited-OCR Beta Release Draft

This draft is for a future human-approved beta tag. It is not a published
GitHub Release, does not create a tag, and does not make Experimental Local
Unlimited-OCR production-ready.

## Headline Summary

Unified PDF Toolkit now has a controlled beta path for Experimental Local
Unlimited-OCR in the Document OCR tool. The default OCR behavior remains
Tesseract. The experimental backend is local-only, user-owned, disabled by
default, and visible only when `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`
is set before launching the app.

## Feature Scope

Included in the beta scope:

- Document OCR with Tesseract as the default backend.
- Experimental Local Unlimited-OCR worker-process backend for local model
  testing.
- Advanced OCR consent gate for model download, custom-code /
  `trust_remote_code`, GPU/VRAM, and temporary rendered page risks.
- User-managed optional OCR runtime, expected to be created with `uv`.
- Local model path, model id, optional revision pin, worker Python, device, and
  timeout settings.
- Readiness diagnostics, beta-check scripts, and manual smoke checklists.

Not included:

- Production-ready Unlimited-OCR support.
- Hosted OCR, project-operated OCR server, cloud upload, screen OCR, or
  background OCR.
- Automatic model download or model management.
- Bundled torch, transformers, CUDA, model files, or model caches.
- Batch Queue AI OCR integration.
- Making Unlimited-OCR the default OCR engine.

## What Works

Validated on the current maintainer machine:

- Default Document OCR path remains Tesseract-backed.
- Experimental backend is hidden without the environment gate.
- Real worker-process Unlimited-OCR CUDA validation completed on an NVIDIA RTX
  3060 12GB.
- Synthetic one-page image and three-page PDF worker-process OCR completed.
- TXT and Markdown output were created locally.
- GUI smoke covered Tesseract default behavior, experimental worker-process
  output, cancel, timeout, missing consent, missing model path, invalid model
  path, missing worker Python, and safe error display.
- Smoke scripts summarize status without printing full OCR text, image bytes,
  rendered page images, or private document content.

## What Is Experimental

- GPU/CUDA behavior is expected to vary by driver, PyTorch wheel, model
  revision, and available VRAM.
- Model revision checks are warning-only. They do not yet enforce checksums or
  an immutable reviewed allowlist.
- The optional runtime is not bundled and must be managed by the user.
- The GUI remains beta-gated and should not be treated as stable production
  Unlimited-OCR support.
- Accessibility and broader Windows GPU/runtime matrix coverage are still in
  progress.

## Prerequisites

- Windows desktop session for GUI validation.
- Normal Unified PDF Toolkit app environment.
- `uv` available on PATH.
- Optional runtime such as `.venv-ocr-runtime`, created outside the default app
  dependency set.
- Local Baidu Unlimited-OCR model folder already present on the machine.
- Writable local Hugging Face cache folders.
- GPU/CUDA runtime compatible with the selected PyTorch wheel for practical
  CUDA beta testing.

## uv Runtime Setup

Dry-run the helper first:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --dry-run --torch-profile cu128
```

If the printed commands match the target machine, run the helper explicitly:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --torch-profile cu128
```

The helper uses `uv`, prints the commands it will run, asks for confirmation
unless `--yes` is supplied, does not download model files, and does not modify
default project dependencies.

## Model Path and Cache Setup

Use local cache folders outside the repository:

```powershell
$env:HF_HOME="$env:TEMP\pdf_toolkit_ocr_validation\hf_home"
$env:HF_MODULES_CACHE="$env:TEMP\pdf_toolkit_ocr_validation\hf_modules"
New-Item -ItemType Directory -Force $env:HF_HOME, $env:HF_MODULES_CACHE
```

Configure Settings / Recent:

- enable the local model runtime;
- select `worker_process`;
- set model id to `baidu/Unlimited-OCR`;
- set a model revision pin when a reviewed revision is known;
- choose an existing local model folder;
- set worker Python to `.venv-ocr-runtime\Scripts\python.exe`;
- use `cuda` for CUDA validation or `auto` for readiness checks.

Do not commit model files, caches, private inputs, or generated OCR outputs.

## Experimental Flag and GUI Launch

Default launch:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

Experimental beta launch:

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'
.\.venv\Scripts\python.exe src\app.py
```

The experimental backend must remain hidden without the environment flag.

## Smoke Test

Use `docs/testing/final_beta_tester_checklist.md` as the beta tester flow.
Minimum smoke coverage:

- clean checkout and default launch;
- Document OCR Tesseract TXT/Markdown output;
- experimental flag launch;
- uv optional runtime setup dry-run;
- model path and worker Python configuration;
- real worker-process OCR on synthetic one-page image;
- real worker-process OCR on synthetic two- or three-page PDF;
- cancel and timeout behavior;
- missing consent/model/worker configuration errors;
- cleanup and generated-output exclusion checks.

## Known Limitations

- Not production-ready.
- Validated GPU matrix is still narrow.
- Model revision/checksum enforcement is not implemented.
- Optional runtime setup remains a beta flow for technical users.
- CPU mode may be too slow for normal beta smoke testing.
- Installer artifacts have not yet been inspected from a clean release build
  for this beta tag candidate.

## Privacy and Security Notes

- No hosted OCR service is provided by this project.
- User files, rendered pages, image bytes, and OCR text must not be uploaded.
- OCR text is written only to user-selected local output files.
- `trust_remote_code=True` can execute model-provided Python code inside the
  optional local runtime. This requires explicit consent and must remain
  documented for beta users.
- Default dependencies remain lightweight and do not include AI/GPU packages.

## Rollback and Disable Instructions

To disable the beta path:

1. Launch the app without `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.
2. Keep Document OCR on `Tesseract OCR (default)`.
3. Clear or disable local model runtime settings in Settings / Recent if
   desired.
4. Remove only beta validation temp folders that you created.
5. Do not delete shared model or Hugging Face cache folders unless you own
   them and intentionally want to remove them.
