# Experimental Local Unlimited-OCR Beta Notes

These notes describe a controlled beta release candidate for Experimental Local
Unlimited-OCR. They are not a GitHub Release, tag, or production-support
announcement.

## What Is Included

- A user-facing Document OCR tool with Tesseract as the default backend.
- A gated Experimental Local Unlimited-OCR option shown only when
  `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` is set.
- `worker_process` runtime mode for running the local model in a killable
  one-shot subprocess.
- Settings / Recent fields for local model runtime configuration.
- Advanced OCR consent that covers model download risk, custom-code /
  `trust_remote_code` risk, GPU/VRAM use, and temporary local page images.
- Manual readiness, GUI smoke, and beta-check scripts.
- A uv-only optional runtime setup helper:
  `scripts/setup_local_unlimited_ocr_runtime.py`.

## What Is Not Included

- Production-ready Unlimited-OCR support.
- Automatic model download.
- Bundled torch, transformers, CUDA, model files, or model caches.
- Hosted OCR, cloud upload, project-operated OCR server, screen OCR, or
  background OCR.
- Batch Queue AI OCR integration.
- A default-engine change. Tesseract remains the default OCR backend.

## Prerequisites

- Windows desktop session for Tkinter GUI validation.
- Repository checkout with the normal app environment installed.
- `uv` available on PATH.
- A separate optional OCR runtime such as `.venv-ocr-runtime`.
- A local Baidu Unlimited-OCR model directory owned by the user.
- Writable local cache folders for Hugging Face cache and dynamic model code.
- NVIDIA GPU and matching PyTorch CUDA wheel for practical CUDA validation.

CPU validation may be too slow for beta smoke testing. Missing CUDA should
produce a clear backend error and must not break Tesseract or non-OCR tools.

## uv Runtime Setup Summary

Run a dry-run first:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --dry-run --torch-profile cu128
```

Choose the torch profile that matches the target machine. The helper supports
`none`, `cpu`, `cu121`, `cu124`, `cu126`, and `cu128`. It prints the exact `uv`
commands before running them and asks for confirmation unless `--yes` is used.

Actual setup example:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --torch-profile cu128
```

The helper does not download model files and does not change default project
dependencies.

## Model and Cache Setup

Use local cache folders outside the repository:

```powershell
$env:HF_HOME="$env:TEMP\pdf_toolkit_ocr_validation\hf_home"
$env:HF_MODULES_CACHE="$env:TEMP\pdf_toolkit_ocr_validation\hf_modules"
New-Item -ItemType Directory -Force $env:HF_HOME, $env:HF_MODULES_CACHE
```

Configure Settings / Recent with:

- enabled local model runtime;
- runtime mode `worker_process`;
- model id `baidu/Unlimited-OCR`;
- existing local model folder;
- worker Python path such as `.venv-ocr-runtime\Scripts\python.exe`;
- device `cuda` for CUDA beta validation or `auto` for readiness.

If model files are needed, obtain them explicitly into a local cache or local
model directory. Do not commit model files or caches.

## GUI Launch Commands

Default GUI without experimental backend:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

Experimental beta GUI:

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'
.\.venv\Scripts\python.exe src\app.py
```

The experimental backend is hidden without the environment flag.

## Smoke Test Checklist

- Run Document OCR with Tesseract and confirm TXT/Markdown output.
- Enable the experimental flag and confirm Experimental Local Unlimited-OCR is
  visible, clearly labeled experimental, and not selected by default.
- Confirm missing consent, missing model path, missing worker Python, invalid
  model path, timeout, and cancellation produce user-safe messages.
- Run one synthetic one-page image with `worker_process`.
- Run one synthetic two- or three-page PDF with `worker_process`.
- Confirm output files exist and include expected page markers.
- Confirm smoke tools do not print OCR text, image bytes, rendered pages, model
  paths, or document content.
- Confirm temporary worker directories are cleaned after success, timeout, and
  cancel.

## Known Warnings

- CUDA wheel and NVIDIA driver mismatch can make `torch.cuda.is_available()`
  false even when a GPU exists.
- The first run may be slow because the local model and custom code are loaded.
- `trust_remote_code=True` executes model-provided Python code in the optional
  runtime. This remains consent-gated and beta-only.
- Wider GPU/runtime matrix coverage is still required before public release.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Experimental backend is hidden | Set `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` before launching the GUI. |
| Consent required | Save Advanced Local AI OCR consent in Settings / Recent. |
| Runtime disabled | Enable local model runtime settings and select `worker_process`. |
| Model path missing | Choose an existing local Unlimited-OCR model folder. |
| Worker Python missing | Point to the uv-managed optional runtime Python. |
| CUDA unavailable | Check GPU driver, PyTorch wheel profile, and optional runtime package versions. |
| Timeout | Increase timeout or reduce input size for beta validation. |
| Worker busy | Wait for the current run to finish; do not start concurrent GPU OCR jobs. |

## Security and Privacy Notes

- No hosted OCR service is provided.
- User files, rendered pages, and OCR text must not be uploaded.
- OCR text is written only to user-selected local TXT/Markdown output files.
- Default dependencies remain lightweight and do not include AI/GPU packages.
- Model files, runtime folders, cache folders, private inputs, and generated
  OCR outputs must stay uncommitted.

## Remaining Blockers Before Public Release

- Broader GPU/runtime matrix validation.
- Accessibility review of Document OCR UI.
- Beta feedback on setup clarity and CUDA wheel selection.
- Model revision pinning and optional allowlist/checksum review.
- User-facing documentation that is clear enough for non-maintainer beta users.
- Release decision on whether the experimental environment gate remains.
