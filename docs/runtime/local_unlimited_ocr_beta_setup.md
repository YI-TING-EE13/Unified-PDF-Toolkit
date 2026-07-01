# Experimental Local Unlimited-OCR Beta Setup

This guide is for controlled beta validation of Experimental Local
Unlimited-OCR in Unified PDF Toolkit. It keeps the default app lightweight:
Tesseract remains the default OCR backend, and no torch, transformers, CUDA
runtime, model files, or model caches are added to default dependencies.

## Scope

This beta path:

- runs on the user's own Windows machine;
- requires `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`;
- requires saved Advanced Local AI OCR consent in Settings / Recent;
- requires a user-managed local model folder;
- requires a uv-managed optional OCR runtime such as `.venv-ocr-runtime`;
- writes OCR output only to user-selected local TXT/Markdown files.

This beta path does not provide hosted OCR, cloud upload, screen OCR,
background OCR, Batch Queue AI OCR, automatic model download, or production-ready
Unlimited-OCR support.

## Prerequisites

- A source checkout of this repository.
- `uv` available on PATH.
- A working desktop session for the Tkinter GUI.
- Tesseract installed if you want to compare the default OCR path.
- NVIDIA GPU/CUDA runtime for CUDA validation. CPU mode may be too slow for
  practical beta checks.
- A local Baidu Unlimited-OCR model directory owned by the user.
- Writable local folders for Hugging Face caches and custom-code modules.

## Optional Runtime Creation

Create a separate optional runtime. Do not install AI packages into the default
project environment.

Recommended dry-run helper:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --dry-run --torch-profile cu128
```

The helper prints the exact `uv` commands, does not download model files, and
asks for confirmation before making changes unless `--yes` is supplied. Select
the torch profile that matches the beta machine. Use `--torch-profile none` to
create/update the runtime without installing torch.

Actual helper run example:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --torch-profile cu128
```

Manual equivalent:

```powershell
uv venv .venv-ocr-runtime --python 3.12
```

Install optional runtime packages with `uv` only. Select the PyTorch CUDA wheel
that matches the machine's driver/CUDA support.

Example for a CUDA 12.8-style runtime:

```powershell
uv pip install --python .\.venv-ocr-runtime\Scripts\python.exe --index-url https://download.pytorch.org/whl/cu128 torch torchvision torchaudio
uv pip install --python .\.venv-ocr-runtime\Scripts\python.exe transformers accelerate pillow pymupdf
```

If the CUDA wheel does not match the installed driver, torch may install but
`torch.cuda.is_available()` can be false. Use the runtime readiness checks below
before running real OCR.

## Cache Paths

Use explicit local cache folders during beta validation so model files and
custom model code stay outside the repository.

```powershell
$env:HF_HOME="$env:TEMP\pdf_toolkit_ocr_validation\hf_home"
$env:HF_MODULES_CACHE="$env:TEMP\pdf_toolkit_ocr_validation\hf_modules"
New-Item -ItemType Directory -Force $env:HF_HOME, $env:HF_MODULES_CACHE
```

The app does not download the model automatically. If a model download is
needed, perform it explicitly into a local cache or local model directory and do
not commit the model or cache files.

## Runtime Settings

In the app:

1. Open `Settings / Recent`.
2. Review and save Advanced Local AI OCR consent.
3. Enable experimental local model runtime configuration.
4. Set runtime mode to `worker_process`.
5. Set model id to `baidu/Unlimited-OCR`.
6. Set model revision pin when you know the reviewed local model revision.
   Leaving it blank is allowed during early beta, but diagnostics will warn.
7. Set local model folder to the existing local model directory.
8. Set worker Python path to:

```text
.\.venv-ocr-runtime\Scripts\python.exe
```

9. Leave worker script path blank unless testing a specific script.
10. Set device to `cuda` for CUDA validation or `auto` for general readiness.

## Launch Commands

Default GUI, without experimental backend:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

Experimental beta GUI:

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'
.\.venv\Scripts\python.exe src\app.py
```

The experimental backend remains hidden unless the environment flag is set.

## Readiness Check

Run readiness with the uv-managed OCR runtime:

```powershell
$env:HF_HOME="$env:TEMP\pdf_toolkit_ocr_validation\hf_home"
$env:HF_MODULES_CACHE="$env:TEMP\pdf_toolkit_ocr_validation\hf_modules"
uv run --python .\.venv-ocr-runtime\Scripts\python.exe --no-project python scripts\manual_unlimited_ocr_local_check.py --model-path "$env:TEMP\pdf_toolkit_ocr_validation\Unlimited-OCR"
```

Expected readiness output includes:

- Python version.
- torch installed.
- transformers installed.
- model path configured.
- model path exists.
- OCR not run unless `--run` is provided.

## Smoke Checks

Use non-sensitive synthetic inputs only. Do not use private documents for beta
setup validation.

1-page image GUI smoke:

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'
$runtimePython=(Resolve-Path '.\.venv-ocr-runtime\Scripts\python.exe').Path
.\.venv\Scripts\python.exe scripts\manual_document_ocr_gui_smoke.py --mode experimental --model-path "$env:TEMP\pdf_toolkit_ocr_validation\Unlimited-OCR" --worker-python $runtimePython --timeout-seconds 180 --wait-seconds 300
```

3-page PDF GUI smoke:

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'
$runtimePython=(Resolve-Path '.\.venv-ocr-runtime\Scripts\python.exe').Path
.\.venv\Scripts\python.exe scripts\manual_document_ocr_gui_smoke.py --mode experimental --input "$env:TEMP\pdf_toolkit_ocr_validation\multi_page_sample.pdf" --model-path "$env:TEMP\pdf_toolkit_ocr_validation\Unlimited-OCR" --worker-python $runtimePython --timeout-seconds 240 --wait-seconds 420
```

Combined beta check:

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'
$runtimePython=(Resolve-Path '.\.venv-ocr-runtime\Scripts\python.exe').Path
.\.venv\Scripts\python.exe scripts\manual_document_ocr_gui_smoke.py --mode beta-check --model-path "$env:TEMP\pdf_toolkit_ocr_validation\Unlimited-OCR" --worker-python $runtimePython --timeout-seconds 180 --wait-seconds 300
```

The smoke runner prints only status, message summaries, output counts, file
sizes, page-marker counts, and worker temp directory counts. It does not print
OCR text, image bytes, rendered page images, or document content.

## Expected Outputs

- Tesseract remains the default backend.
- Experimental Local Unlimited-OCR appears only with the environment flag.
- TXT and Markdown files are created in the selected local output folder.
- Cancellation reports `Document OCR cancelled.` and writes no output for the
  cancelled run.
- Timeout reports `The selected OCR backend timed out.`
- Worker temp directories are cleaned up after success, cancellation, and
  timeout.

## Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Experimental option is hidden | Environment flag not set | Set `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` before launching the GUI. |
| Consent warning appears | Advanced OCR consent is missing or stale | Review and save consent in Settings / Recent. |
| Model path not configured | Runtime settings missing | Set the local model folder in Settings / Recent. |
| Model path not found | Folder typo or missing model | Choose an existing local model directory. |
| Worker Python not found | Runtime path typo | Point to the uv-managed `.venv-ocr-runtime\Scripts\python.exe`. |
| CUDA unavailable | Torch wheel/driver mismatch or no GPU | Check the selected PyTorch CUDA wheel and NVIDIA driver. |
| Worker is busy | A GPU worker is already running or stale lock exists | Wait for the current job; inspect temp lock only after confirming no worker is running. |
| Timeout | Model load or OCR exceeded budget | Increase timeout for beta testing or reduce input size. |

## Cleanup

Do not commit generated runtime or validation artifacts. Remove only local temp
and cache folders you intentionally created:

```powershell
Remove-Item -Recurse -Force "$env:TEMP\pdf_toolkit_gui_smoke" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:TEMP\pdf_toolkit_ocr_validation" -ErrorAction SilentlyContinue
```

Do not remove shared Hugging Face caches unless you intentionally own them.

## Related Release-Candidate Notes

- `docs/releases/experimental_local_unlimited_ocr_beta_notes.md`
- `docs/security/unlimited_ocr_trust_remote_code_policy.md`
