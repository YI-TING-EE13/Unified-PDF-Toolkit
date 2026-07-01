# Document OCR Beta Smoke Checklist

Use this checklist before any controlled beta build that exposes Experimental
Local Unlimited-OCR behind `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.

This is a manual/local checklist. It is not CI, does not download models
automatically, and must use non-sensitive synthetic inputs.

## Environment Record

- Date:
- Commit:
- Platform:
- Python:
- Optional OCR runtime path:
- uv version:
- GPU:
- GPU VRAM:
- NVIDIA driver:
- torch version:
- transformers version:
- Model source: local path / local cache / other
- Model revision, if known:
- `HF_HOME`:
- `HF_MODULES_CACHE`:

## Gate And Default Behavior

- [ ] `git status --short` shows no tracked generated outputs.
- [ ] `README (1).md` remains untracked and out of scope.
- [ ] Default dependencies are unchanged.
- [ ] Launching without `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` shows
      `Document OCR`.
- [ ] Tesseract is the default backend.
- [ ] Experimental Local Unlimited-OCR is hidden without the flag.
- [ ] No torch/transformers import is required at app startup.

## Consent And Settings

- [ ] Settings / Recent shows Experimental Advanced Local AI OCR Consent.
- [ ] Consent explains model download, custom-code / `trust_remote_code`,
      GPU/VRAM, and temporary page-image risks.
- [ ] Declining consent leaves Experimental Local Unlimited-OCR blocked.
- [ ] Runtime mode is `worker_process`.
- [ ] Local model folder exists.
- [ ] Worker Python points to a uv-managed OCR runtime.
- [ ] Worker script path is blank or points to the repo-local worker script.
- [ ] Device is `cuda` or `auto` for GPU validation.

## Diagnostics

- [ ] Diagnostics reports Python and default dependencies.
- [ ] Diagnostics reports torch/transformers as optional readiness checks.
- [ ] Diagnostics reports CUDA availability only if torch is installed.
- [ ] Diagnostics reports GPU name/VRAM when safely detectable.
- [ ] Diagnostics reports model path and worker Python readiness.
- [ ] Diagnostics reports `HF_HOME` and `HF_MODULES_CACHE` writability.
- [ ] Missing optional runtime pieces are warnings/info, not app failures.

## Tesseract Smoke

- [ ] Select a synthetic one-page image or PDF.
- [ ] Select TXT output.
- [ ] Select Markdown output.
- [ ] Run with Tesseract.
- [ ] Output TXT exists.
- [ ] Output Markdown exists.
- [ ] No crash.
- [ ] OCR text is written only to selected output files.

## Experimental Local Unlimited-OCR Smoke

- [ ] Launch with `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.
- [ ] Experimental Local Unlimited-OCR option is visible.
- [ ] UI copy says experimental, local-only, no upload, user-managed runtime,
      and not production-ready.
- [ ] Run worker_process OCR on a synthetic one-page image.
- [ ] TXT output exists.
- [ ] Markdown output exists.
- [ ] Run worker_process OCR on a synthetic two- or three-page PDF.
- [ ] TXT output exists.
- [ ] Markdown output exists.
- [ ] Page markers match the expected page count.
- [ ] No OCR full text, image bytes, model path, or document content appears in
      console/log output by default.
- [ ] Temporary worker directories are cleaned up.

## Failure Paths

- [ ] Missing consent shows a clear consent-required warning.
- [ ] Missing model path shows a clear configuration error.
- [ ] Invalid model path shows a clear not-found error.
- [ ] Missing worker Python shows a clear not-found error.
- [ ] Unsupported input type shows a clear unsupported-input error.
- [ ] Very short timeout shows a timeout error.
- [ ] Busy worker shows a retry-later message, if feasible to test.
- [ ] GPU/CUDA unavailable is covered by either manual environment testing or
      user-safe error mapping tests.

## Cancel And Timeout

- [ ] Cancel button becomes available during the run.
- [ ] Cancel reports `Document OCR cancelled.`
- [ ] Cancel resets progress and disables the Cancel button.
- [ ] Cancel terminates the worker process.
- [ ] Cancel writes no partial output for the cancelled file.
- [ ] Timeout terminates the worker process.
- [ ] Timeout writes no unexpected output.

## Privacy Review

- [ ] No external upload occurred.
- [ ] No hosted OCR service was contacted.
- [ ] No source file path was sent to a remote endpoint.
- [ ] No OCR text appears in diagnostics or workflow reports by default.
- [ ] No image bytes/base64 appears in logs or reports by default.
- [ ] Model/cache/runtime files remain outside the repository.
- [ ] Generated smoke outputs remain outside the repository or are deleted.

## Pass/Fail Decision

- Overall result: pass / fail
- Blocking issue:
- Follow-up issue:
- Notes:
