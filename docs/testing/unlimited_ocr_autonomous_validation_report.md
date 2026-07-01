# Unlimited-OCR Autonomous Validation Report

Date: 2026-06-30

## Scope

This report records the autonomous validation and hardening pass for the
experimental local Baidu Unlimited-OCR path.

The work keeps Unified PDF Toolkit local-first:

- Tesseract remains the default production OCR engine.
- Unlimited-OCR remains optional, experimental, local-only, and disabled by
  default.
- The project does not provide a hosted OCR service.
- No document upload, screen OCR, background OCR, model download, or default AI
  OCR behavior was added.
- Default project dependencies were not changed.

## Pushed Commits

The following green commits were pushed to `origin/main` during this run:

- `f7908d7 Add killable Unlimited-OCR worker runtime`
- `454b371 Harden Unlimited-OCR worker runtime safety`
- `846389f Expose experimental local Unlimited-OCR in Document OCR UI`
- `e0a1589 Harden experimental local OCR failure handling`

Final local `HEAD`: `e0a15894f2dbf25ea8db53d873bc5d4110e0db71`

Final local tracking `origin/main`: `e0a15894f2dbf25ea8db53d873bc5d4110e0db71`

## What Works Now

- `worker_process` runs local Unlimited-OCR in a one-shot subprocess instead of
  the app process.
- Timeout/cancellation can terminate the worker process.
- Only one experimental Unlimited-OCR worker is allowed by default to avoid
  accidental concurrent GPU jobs.
- Worker stderr is discarded and structured worker errors are parsed only when
  safe.
- Temporary controller-owned page images are cleaned up after success/failure.
- A user-facing `Document OCR` tool exists.
- `Document OCR` uses Tesseract by default.
- Experimental Local Unlimited-OCR is visible only when
  `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` is set.
- Experimental Local Unlimited-OCR requires saved advanced OCR consent and
  `worker_process` runtime settings.
- TXT and Markdown outputs are written only to a selected local folder.

## Still Experimental

- Local Unlimited-OCR is not production-ready.
- It requires user-managed `.venv-ocr-runtime` packages and local model files.
- It uses model custom code through the optional runtime path.
- Hardware behavior can vary by GPU, CUDA, drivers, and model revision.
- The UI path is gated and not the default.
- Batch Queue AI OCR, screen OCR, hosted OCR, model download controls, and
  production endpoint OCR are not supported.

## Runtime Used

- Optional runtime: `.venv-ocr-runtime`, managed by `uv`.
- Python: `3.12.11`.
- torch: `2.11.0+cu128`.
- transformers: `4.57.1`.
- CUDA available: `True`.
- GPU: `NVIDIA GeForce RTX 3060`.
- Model source: local directory under
  `%TEMP%\pdf_toolkit_ocr_validation\Unlimited-OCR`.
- Hugging Face cache/module paths used for validation:
  `%TEMP%\pdf_toolkit_ocr_validation\hf_home` and
  `%TEMP%\pdf_toolkit_ocr_validation\hf_modules`.

No model, cache, private input, or generated OCR output files were committed.

## Real OCR Validation

Synthetic non-sensitive inputs were created under
`%TEMP%\pdf_toolkit_phase3_workflow_validation`:

- `phase3_image.png`: one image page.
- `phase3_3page.pdf`: three synthetic PDF pages.

Readiness command:

```powershell
uv run --no-cache --python .\.venv-ocr-runtime\Scripts\python.exe --no-project python scripts\manual_unlimited_ocr_local_check.py --model-path "%TEMP%\pdf_toolkit_ocr_validation\Unlimited-OCR"
```

Result:

- Python `3.12.11`.
- torch installed: `True`.
- transformers installed: `True`.
- model path configured: `True`.
- model path exists: `True`.
- readiness completed without running OCR.

Workflow-level real OCR commands used a temporary runner plus:

```powershell
uv run --no-cache --python .\.venv-ocr-runtime\Scripts\python.exe --no-project python "%TEMP%\pdf_toolkit_phase3_workflow_validation\run_document_ocr_workflow.py" "%TEMP%\pdf_toolkit_phase3_workflow_validation\phase3_image.png" "%TEMP%\pdf_toolkit_phase3_workflow_validation\out_image"
```

Result:

- cancelled: `False`
- failed count: `0`
- output count: `2`
- success count: `1`
- TXT page markers: `1`
- Markdown page markers: `1`

```powershell
uv run --no-cache --python .\.venv-ocr-runtime\Scripts\python.exe --no-project python "%TEMP%\pdf_toolkit_phase3_workflow_validation\run_document_ocr_workflow.py" "%TEMP%\pdf_toolkit_phase3_workflow_validation\phase3_3page.pdf" "%TEMP%\pdf_toolkit_phase3_workflow_validation\out_pdf"
```

Result:

- cancelled: `False`
- failed count: `0`
- output count: `2`
- success count: `1`
- TXT page markers: `3`
- Markdown page markers: `3`

OCR text was not printed to the console. Only counts and file sizes were
reported.

## GUI Smoke Status

Update on 2026-07-01: the real Windows Tkinter GUI was launched successfully in
this desktop session.

Manual launch commands:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

```powershell
$env:PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR='1'; .\.venv\Scripts\python.exe src\app.py
```

Both launch attempts entered the GUI main loop without traceback. The windows
were later closed by terminating the smoke-launched `src\app.py` processes.

A repo-local manual smoke runner was added for repeatable Tkinter validation:

```powershell
.\.venv\Scripts\python.exe scripts\manual_document_ocr_gui_smoke.py --mode inspect
```

Without the experimental flag:

- `Document OCR` loaded.
- Default backend was `Tesseract OCR (default)`.
- Experimental Local Unlimited-OCR was hidden.
- Tesseract OCR on a synthetic one-page image wrote local TXT and Markdown
  outputs.

With `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`:

- Experimental Local Unlimited-OCR appeared as a gated worker-process option.
- The status text clearly stated local-only, no upload, consent/runtime
  requirements, and non-production status.
- Real worker-process OCR on a synthetic one-page image wrote TXT and Markdown
  outputs.
- Real worker-process OCR on a synthetic three-page PDF wrote TXT and Markdown
  outputs.
- The smoke output printed only status, message summaries, output counts, file
  sizes, and page-marker counts. It did not print OCR text, image bytes, model
  cache paths, or document content.

GUI cancel/timeout UX was validated after hardening:

- Cancel now propagates from the Document OCR GUI through the workflow into the
  `worker_process` controller.
- The worker process is terminated on cancel.
- The GUI returns to `Document OCR cancelled.`, resets progress to `0`, disables
  the Cancel button, and writes no output files for the cancelled run.
- Very short timeout reports `The selected OCR backend timed out.`

Update on 2026-07-01 beta-readiness pass:

- A controlled beta setup guide was added at
  `docs/runtime/local_unlimited_ocr_beta_setup.md`.
- A beta smoke checklist was added at
  `docs/testing/document_ocr_beta_smoke_checklist.md`.
- A release-gate audit was added at
  `docs/testing/local_unlimited_ocr_beta_release_gate_audit.md`.
- The manual GUI smoke runner gained `--mode beta-check`, which summarizes
  Tesseract default behavior, experimental gate state, worker-process output
  creation, and worker temp cleanup without printing OCR text.
- Diagnostics now report optional torch/transformers versions when detectable,
  `HF_HOME` and `HF_MODULES_CACHE` writability, configured worker Python
  readiness, and whether the worker Python resembles the uv-managed optional OCR
  runtime.
- Settings and Document OCR copy were tightened to emphasize experimental
  status, no upload, user-owned local runtime/model files, uv-managed worker
  Python, and Tesseract remaining the default.

## Failure Path Results

Failure scenarios were run through a temporary local runner with the uv-managed
OCR runtime. No OCR text, image bytes, model paths, or document content were
printed.

Results:

- Missing model path: `The local Unlimited-OCR model path is not configured.`
- Invalid model path: `The configured local Unlimited-OCR model path was not found.`
- Missing worker Python: `The configured local Unlimited-OCR worker Python executable was not found.`
- Missing consent: `Advanced OCR consent is required before this backend can run.`
- Busy worker: `The local OCR worker is busy. Wait for the current OCR job to finish and try again.`
- Unsupported input: `Unsupported input type: .txt`
- Very short timeout: `The selected OCR backend timed out.`
- CUDA/GPU unavailable behavior is covered by user-safe error mapping tests.
  Real CUDA-unavailable execution was not run because this machine has an
  available RTX 3060 CUDA runtime and masking the GPU in the real worker would
  not be a representative hardware failure.

## Automated Validation

The required default validation commands were run with the repo-local
`.\.venv\Scripts\python.exe` because `..\.venv\Scripts\python.exe` is not
available in this checkout.

Latest full validation results:

- `git diff --check`: exit `0` with CRLF warnings only.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`: exit `0`,
  `Ran 98 tests`, `OK`.
- `.\.venv\Scripts\python.exe verify_install.py`: exit `0`; all tools loaded,
  including `Document OCR`; Tkinter `init.tcl` warning only.
- `.\.venv\Scripts\python.exe -m compileall -q src tests verify_install.py scripts`:
  exit `0`.

Additional targeted checks:

- `tests.test_ocr_backends.LocalModelBackendTests`: exit `0`, 18 tests.
- `tests.test_document_ocr_tool`: exit `0`, 7 tests.
- `tests.test_advanced_ocr_workflow_helpers tests.test_document_ocr_tool tests.test_fake_ai_ocr_workflow`:
  exit `0`, 24 tests.

## Files Changed In This Run

Code and tests:

- `src/ocr/local_worker.py`
- `src/ocr/document_workflow.py`
- `src/ocr/workflow.py`
- `src/tools/document_ocr/__init__.py`
- `src/tools/document_ocr/tool.py`
- `src/tools/settings/tool.py`
- `src/app.py`
- `tests/test_advanced_ocr_workflow_helpers.py`
- `tests/test_document_ocr_tool.py`
- `tests/test_ocr_backends.py`
- `verify_install.py`

Documentation:

- `README.md`
- `CHANGELOG.md`
- `docs/advanced_ocr_maintainer_guide.md`
- `docs/roadmap/advanced_ocr_next_goals.md`
- `docs/runtime/local_model_ocr_runtime.md`
- `docs/runtime/local_model_worker_contract.md`
- `docs/runtime/local_unlimited_ocr_beta_setup.md`
- `docs/testing/document_ocr_beta_smoke_checklist.md`
- `docs/testing/local_unlimited_ocr_beta_release_gate_audit.md`
- `docs/testing/unlimited_ocr_autonomous_validation_report.md`

## Exclusions Confirmed

- `README (1).md` remained untracked and was not modified, staged, committed,
  or pushed.
- `.venv-ocr-runtime` was not committed.
- Model/cache directories were not committed.
- Synthetic inputs and generated OCR outputs remained under `%TEMP%`.
- Default dependency files were not changed.

## Remaining Production Blockers

- Need broader GPU/runtime matrix validation beyond RTX 3060.
- Need broader accessibility review for the new Document OCR UI.
- Need beta feedback on setup clarity, CUDA wheel selection, model revision
  behavior, and support expectations.
- Need packaging documentation for optional OCR runtime path in installer
  release notes.
- Need final release-gate review before removing the experimental env gate.

## Update: Final Beta Hardening Pass

Date: 2026-07-01

Additional beta release-candidate hardening added:

- Warning-only model revision safety checks in `src/ocr/model_policy.py`.
- Local model runtime settings now include an optional model revision pin.
- Diagnostics now report model id allowlist status, revision pin status, local
  model metadata presence, and valid `trust_remote_code` consent for the
  configured model id.
- Document OCR and Settings / Recent copy were tightened to say Tesseract is the
  default, Experimental Local Unlimited-OCR is beta local AI OCR, it runs on
  this computer with no upload, and it requires a uv-managed runtime, local
  model folder, consent, and may use GPU/VRAM plus custom model code.
- `docs/testing/beta_packaging_dry_run.md` records a release artifact dry-run
  checklist without creating a GitHub Release or tag.
- `docs/testing/final_beta_tester_checklist.md` records the final controlled
  beta tester flow, success criteria, failure cases, cleanup, and reporting
  expectations.

Validation notes for this pass:

- Direct optional runtime readiness passed with `.venv-ocr-runtime` Python,
  torch installed, transformers installed, and local model path detected.
- Real worker-process OCR smoke was rerun on the existing local synthetic
  one-page image and three-page PDF. Both completed with `Runtime:
  worker_process` and `Device: cuda`; the helper did not print OCR text.
- GUI beta-check was attempted but could not be rerun in this automation pass
  because the required escalated Windows desktop GUI execution was rejected by
  the local execution environment usage limit. The blocker is environmental,
  not a code assertion.
- Static packaging audit confirmed no tracked `.venv-ocr-runtime`, model/cache
  folders, synthetic samples, torch, transformers, or CUDA package files.

The beta remains controlled and not production-ready. Do not remove
`PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`, do not make Unlimited-OCR the
default backend, and do not publish a release until the remaining blockers are
closed.

## Recommended Next Milestone

Run controlled beta validation on at least one additional Windows + NVIDIA GPU
configuration using `docs/testing/document_ocr_beta_smoke_checklist.md`, then
record any CUDA wheel, model revision, setup, or UI accessibility issues before
considering a public beta announcement.
