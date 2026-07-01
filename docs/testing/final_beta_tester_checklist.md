# Experimental Local Unlimited-OCR Final Beta Tester Checklist

Use this checklist for controlled beta testers before considering a public
release. This is not production-ready support.

## Setup Flow

- [ ] Start from a clean checkout of Unified PDF Toolkit.
- [ ] Confirm `README (1).md`, private files, model files, caches, and generated
      OCR outputs are not staged.
- [ ] Run the normal app environment with default dependencies.
- [ ] Create or verify the optional OCR runtime with `uv` only:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_unlimited_ocr_runtime.py --dry-run --torch-profile cu128
```

- [ ] Choose a torch profile matching the beta machine before running setup.
- [ ] Configure `HF_HOME` and `HF_MODULES_CACHE` to writable local folders.
- [ ] Confirm the local Baidu Unlimited-OCR model folder exists.
- [ ] Record model id, model revision when known, GPU, driver/CUDA context, and
      optional runtime package versions.

## GUI Launch Flow

Default run:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

Experimental run:

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'
.\.venv\Scripts\python.exe src\app.py
```

- [ ] Without the flag, Experimental Local Unlimited-OCR is hidden.
- [ ] With the flag, Experimental Local Unlimited-OCR is visible and clearly
      labeled beta/experimental.
- [ ] Tesseract remains the default backend.

## Tesseract Smoke

- [ ] Open Document OCR.
- [ ] Select a tiny synthetic image or PDF.
- [ ] Keep `Tesseract OCR (default)` selected.
- [ ] Select TXT and Markdown output.
- [ ] Run OCR.
- [ ] Confirm local output files are created.
- [ ] Confirm no crash and no private content is printed to logs.

## Experimental Unlimited-OCR Smoke

- [ ] Save Advanced Local AI OCR consent in Settings / Recent.
- [ ] Enable local model runtime configuration.
- [ ] Set runtime mode to `worker_process`.
- [ ] Set model id to `baidu/Unlimited-OCR`.
- [ ] Set model revision pin when known.
- [ ] Set local model folder.
- [ ] Set worker Python to `.venv-ocr-runtime\Scripts\python.exe`.
- [ ] Set device to `cuda` for CUDA validation.
- [ ] Run one synthetic one-page image.
- [ ] Run one synthetic two- or three-page PDF.
- [ ] Confirm TXT and Markdown outputs are created locally.
- [ ] Confirm page counts and page markers are plausible without dumping full
      OCR text in reports.

## Expected Success Criteria

- Tesseract is default and works without the experimental flag.
- Experimental Local Unlimited-OCR is hidden without the flag.
- Experimental Local Unlimited-OCR requires consent and explicit runtime/model
  settings.
- Real worker-process OCR completes on local synthetic inputs.
- Cancel and timeout terminate or safely stop the worker process.
- Temporary worker directories are cleaned up.
- No hosted OCR service is contacted.
- No files, rendered pages, OCR text, or generated outputs are uploaded.

## Failure Cases To Check

- [ ] Missing consent.
- [ ] Missing model path.
- [ ] Invalid model path.
- [ ] Missing worker Python.
- [ ] Unsupported input file type.
- [ ] Very short timeout.
- [ ] Cancel during a run.
- [ ] CUDA unavailable or runtime mismatch, if safely reproducible.

Expected failures should be user-safe and actionable. They must not print OCR
text, image bytes/base64, rendered page images, private source paths, or model
cache contents.

## Cleanup

- [ ] Remove only temp folders created for beta validation.
- [ ] Do not delete shared Hugging Face caches unless you intentionally own
      them.
- [ ] Do not commit `.venv-ocr-runtime`.
- [ ] Do not commit model files, cache folders, private inputs, or generated
      OCR outputs.

## Reporting GPU / Runtime / Model Errors

Report:

- app commit hash;
- Windows version;
- GPU name and VRAM;
- NVIDIA driver and CUDA/PyTorch wheel profile;
- optional runtime Python version;
- torch and transformers versions;
- model id and revision when known;
- whether model metadata warnings appeared;
- exact user-facing error text;
- whether cancel/timeout cleaned up the worker.

Do not include private document content, full OCR text, rendered page images, or
source file paths in the report unless separately approved for a private debug
case.

## Known Limitations

- Experimental Local Unlimited-OCR is not production-ready.
- The beta path has been validated on RTX 3060 CUDA, but broader GPU/runtime
  matrix coverage is still pending.
- Model revision checks are warning-only and do not yet enforce checksums.
- Accessibility review is not complete.
- The default installer does not bundle AI runtime packages or model files.
- Batch Queue AI OCR, screen OCR, background OCR, hosted OCR, and automatic
  model download are not supported.
