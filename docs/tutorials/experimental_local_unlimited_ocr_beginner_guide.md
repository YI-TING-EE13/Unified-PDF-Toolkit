# Experimental Local Unlimited-OCR Beginner Guide

> This guide describes the older manually configured controlled-beta workflow.
> Normal users should use `Settings / Recent` and the managed device analysis
> described in
> [Managed Unlimited-OCR Setup](../runtime/managed_unlimited_ocr.md). The APP
> still requires explicit consent before any large download or runtime change.

This guide is for controlled beta users who want to try the optional local
Unlimited-OCR backend in the Document OCR tool.

Experimental Local Unlimited-OCR is disabled by default. It is not production
ready. Tesseract remains the default OCR backend.

## What It Is

Experimental Local Unlimited-OCR is a local AI OCR backend inspired by Baidu
Unlimited-OCR. It can run through a one-shot worker process so the app can stop
the worker on timeout or cancellation.

It is intended for controlled local testing only:

- no hosted OCR service is provided by this project;
- no files are uploaded by Unified PDF Toolkit;
- model files and runtime packages are managed by the user;
- model code may run inside the optional local runtime when
  `trust_remote_code=True` is used.

## Why It Is Experimental

This beta path depends on local GPU drivers, PyTorch wheels, optional packages,
model files, model revisions, cache folders, and available VRAM. Those pieces
vary from machine to machine.

The current checks are warning-oriented. They help beta users notice risky
configuration, but they do not make the feature production ready.

## Hardware Expectations

For practical testing, use a Windows desktop with an NVIDIA GPU and enough VRAM
for the selected model and PyTorch wheel. CPU mode may work for readiness checks,
but it can be too slow for normal OCR smoke testing.

If CUDA is unavailable or VRAM is insufficient, fall back to Tesseract.

## uv Runtime Setup

Use `uv` for the optional OCR runtime. Do not use raw `pip` or `conda` for this
project workflow.

Dry-run first:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --dry-run --torch-profile cu128
```

Choose a torch profile that matches the beta machine. Then run the helper
explicitly only after reviewing the printed commands:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --torch-profile cu128
```

The helper creates or updates `.venv-ocr-runtime`, does not download model files,
and does not modify default project dependencies.

## Model Folder Setup

Prepare an existing local model folder outside the repository. Do not commit
model files or model caches.

Recommended cache folders for a manual beta session:

```powershell
$env:HF_HOME="$env:TEMP\pdf_toolkit_ocr_validation\hf_home"
$env:HF_MODULES_CACHE="$env:TEMP\pdf_toolkit_ocr_validation\hf_modules"
New-Item -ItemType Directory -Force $env:HF_HOME, $env:HF_MODULES_CACHE
```

In `Settings / Recent`, configure:

- local model runtime enabled;
- runtime mode: `worker_process`;
- model id: `baidu/Unlimited-OCR`;
- model revision pin when known;
- local model folder;
- worker Python: `.venv-ocr-runtime\Scripts\python.exe`;
- device: `cuda` for CUDA validation, or `auto` for readiness checks.

## Enable The Experimental Backend

Set the gate before launching the GUI:

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'
.\.venv\Scripts\python.exe src\app.py
```

Without this environment variable, the experimental option should not appear.

## Save Consent

Open `Settings / Recent` and review the Advanced Local AI OCR consent. Save
consent only if you understand the model download/cache, custom model code,
GPU/VRAM, no-upload, and temporary page image risks.

## Run The GUI Flow

1. Open `Document OCR`.
2. Select a small synthetic PDF or image.
3. Choose TXT, Markdown, or both.
4. Select `Experimental Local Unlimited-OCR (worker process)`.
5. Confirm the output folder is local and writable.
6. Click `Run Document OCR`.

Start with a one-page file. After it succeeds, try a small three-page PDF.

## Run Manual Smoke Checks

One-page smoke:

```powershell
$env:HF_HOME="$env:TEMP\pdf_toolkit_ocr_validation\hf_home"
$env:HF_MODULES_CACHE="$env:TEMP\pdf_toolkit_ocr_validation\hf_modules"
.\.venv-ocr-runtime\Scripts\python.exe scripts\manual_unlimited_ocr_local_check.py --model-path "$env:TEMP\pdf_toolkit_ocr_validation\Unlimited-OCR" --input "$env:TEMP\pdf_toolkit_ocr_validation\sample.png" --runtime-mode worker_process --device cuda --timeout-seconds 180 --run --acknowledge-experimental-consent
```

Three-page smoke:

```powershell
$env:HF_HOME="$env:TEMP\pdf_toolkit_ocr_validation\hf_home"
$env:HF_MODULES_CACHE="$env:TEMP\pdf_toolkit_ocr_validation\hf_modules"
.\.venv-ocr-runtime\Scripts\python.exe scripts\manual_unlimited_ocr_local_check.py --model-path "$env:TEMP\pdf_toolkit_ocr_validation\Unlimited-OCR" --input "$env:TEMP\pdf_toolkit_ocr_validation\multi_page_sample.pdf" --runtime-mode worker_process --device cuda --timeout-seconds 240 --run --acknowledge-experimental-consent
```

Successful smoke output should summarize status, OCR page count, runtime, and
device. It should not print full OCR text.

## What Success Looks Like

- Tesseract remains the default backend.
- The experimental backend appears only when the gate is enabled.
- Consent and explicit runtime settings are required.
- Worker-process OCR completes on small local synthetic inputs.
- TXT or Markdown output files are created locally.
- Console summaries do not dump OCR text, image bytes, rendered page images, or
  private source paths.
- Temporary worker folders are cleaned up after success, timeout, or cancel.

## What Failure Looks Like

Expected beta failures should be short and actionable, for example:

- model path is not configured;
- configured model path was not found;
- worker Python executable is not configured;
- configured worker Python executable was not found;
- selected OCR backend timed out;
- local OCR worker is busy;
- local AI OCR runtime could not use the requested GPU/CUDA device.

The default UI and smoke summaries should not show tracebacks, OCR text, image
bytes, rendered page images, model cache paths, or private source paths.

## Troubleshooting

| Problem | Likely cause | What to do |
| --- | --- | --- |
| Experimental option not visible | Environment gate is not set | Set `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` before launching the GUI. |
| `torch` or `transformers` missing | Optional OCR runtime is incomplete | Re-run the uv setup helper with the correct torch profile. |
| Model path missing | Runtime settings do not point to a model folder | Choose an existing local model folder in Settings / Recent. |
| Worker Python missing | Runtime settings do not point to the optional runtime Python | Set worker Python to `.venv-ocr-runtime\Scripts\python.exe`. |
| CUDA unavailable | Driver, CUDA wheel, or GPU availability mismatch | Use a matching PyTorch wheel, choose `auto`, or fall back to Tesseract. |
| VRAM insufficient | Model needs more GPU memory than available | Use smaller inputs, close other GPU workloads, or fall back to Tesseract. |
| Timeout | Model load or OCR exceeded the time budget | Increase timeout or test with a one-page synthetic input. |
| Cancel | User cancelled the run | Confirm the app returns to an idle state and no partial output is needed. |
| `trust_remote_code` warning | Model code may execute inside the local runtime | Continue only after reviewing and saving consent for trusted local model code. |
| Hugging Face cache not writable | `HF_HOME` or `HF_MODULES_CACHE` is missing or read-only | Set both to writable local folders outside the repository. |
| App starts but OCR fails | Runtime, model, device, or consent is incomplete | Run Diagnostics and the manual readiness helper. |
| Outputs not created | Failure, cancellation, unsupported input, or unwritable output folder | Check the user-facing error and try a writable output folder. |
| Logs look noisy | Upstream runtime warnings may appear during setup or manual experiments | Share only sanitized summaries. Do not paste private OCR text or local paths. |

## Disable The Experimental Backend

To return to the default safe path:

1. Close the app.
2. Launch without `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.
3. Keep Document OCR on `Tesseract OCR (default)`.
4. Optionally disable or clear local model runtime settings in Settings / Recent.

## Clean Temporary Runtime Or Cache Files

Only remove folders you intentionally created for beta validation, such as a
temporary `pdf_toolkit_ocr_validation` folder. Do not delete shared Hugging Face
cache folders, model folders, or runtime folders unless you own them and intend
to remove them.

Do not commit:

- `.venv-ocr-runtime`;
- model folders;
- Hugging Face cache folders;
- private inputs;
- generated OCR outputs;
- raw logs containing OCR text or local paths.

## When To Fall Back To Tesseract

Use Tesseract when:

- you need the default supported OCR path;
- the machine does not have a suitable GPU/runtime;
- model setup is incomplete;
- privacy review for model code is not complete;
- the document is small and Tesseract quality is acceptable;
- beta warnings are unclear.

Tesseract remains the default and should be the first recommendation for normal
users.
