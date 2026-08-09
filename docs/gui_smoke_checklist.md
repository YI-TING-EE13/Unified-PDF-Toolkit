# GUI Smoke Checklist

Run this checklist before publishing a desktop build.

## Setup

- Start from a clean checkout.
- Run `uv sync --dev`.
- Run `uv run --no-sync python scripts/gui_smoke.py`.
- Run `uv run --no-sync python src/app.py`.
- Prepare one small text PDF, one image-only PDF, and two PNG/JPG images.

## Core UI

- Confirm every sidebar tool opens without errors.
- Confirm the sidebar groups Organize, Convert & Extract, and Workspace are
  visible and the active indicator settles on the selected tool.
- Switch rapidly across all tools and confirm only the final selected view
  remains visible.
- Resize the app below 1040 pixels. Confirm preview-heavy workflows expose
  `Controls` and `Preview` tabs instead of clipped side-by-side panes.
- Confirm every visible vertical scrollbar reaches the bottom content and can
  return to the top.
- Run `uv run --no-sync python scripts/gui_smoke.py --reduce-motion` and confirm
  all tools, responsive tabs, scrolling, and the consent dialog still work.
- Open and close the Advanced Local AI OCR consent dialog; confirm the modal
  enters and exits without leaving the main window blocked.
- Drag a PDF onto a PDF file list.
- Drag an image onto the Image to PDF file list.
- Drag a folder onto a file list and confirm supported files are added.
- Confirm unsupported dragged files are ignored.

## Output Behavior

- Open Settings / Recent.
- Set conflict behavior to `rename` and run a workflow twice.
- Set conflict behavior to `skip` and confirm existing outputs are skipped.
- Set conflict behavior back to `rename` after testing.
- Confirm recent inputs, outputs, and reports are listed.
- Confirm Copy Selected works for each recent list.

## Workflows

- Compress one small PDF and confirm an output report is written.
- Merge two PDFs and confirm preview page order and output report.
- Split one PDF and confirm selected range output.
- Convert one PDF to PNG images.
- Convert two images to a PDF.
- Use Page Manager to rotate one page, save, and reopen the output.
- Convert a text PDF to Word using Text Only.
- Convert an image-only PDF to Word using Page Images.
- Add PDF to Image and PDF to Word jobs to Batch Queue, run the queue, and confirm a report is written.
- Open Diagnostics, run checks, and copy the results.

## Adversarial and Recovery Inputs

- Try an encrypted PDF, damaged PDF, blank PDF, and zero-page PDF; confirm the
  workflow rejects or describes each input without a traceback.
- Try a high-page-count PDF with a small selected range before testing a full
  conversion.
- Use paths containing Chinese characters, spaces, Emoji, and a long filename.
- Test an unwritable output folder, a nearly full test volume, and an output file
  held open by another program; confirm the recovery suggestion is specific.
- Run the same workflow repeatedly and verify `rename`, `overwrite`, and `skip`
  all behave as selected.
- Process 50-100 small documents and confirm memory, open file handles, and child
  process counts return near baseline after completion.

## OCR

- If Tesseract is not installed, run OCR Text and confirm the error message explains the missing executable.
- If Tesseract is installed, run OCR Text with `eng`.
- If Traditional Chinese language data is installed, run OCR Text with `eng+chi_tra`.
- In Diagnostics, confirm installed Tesseract language codes are listed and a
  missing `chi_tra`/`chi_sim` pack produces an actionable warning.
- Confirm OCR DPI changes are accepted and persisted.
- Confirm OCR cleanup options are selectable and persisted.
- Open Settings / Recent and start the managed Unlimited-OCR analyzer. Confirm
  inspection does not create the runtime/model data root and all consent boxes
  start unchecked.
- Confirm compatibility, confidence, risk, download/disk/VRAM estimates,
  private paths, backend, Driver/CUDA boundaries, custom-code risk, and the
  `Install and Enable`, technical details, and `Not Now` choices are visible.
- Without accepting every acknowledgement, confirm installation remains
  disabled and no model/runtime download starts.
- On an approved GPU test device, validate pause, cancel, close-window resume,
  checksum, five synthetic OCR cases, benchmark, registration, worker unload,
  Tesseract fallback, runtime-only uninstall, and full model/cache cleanup.

## Cancellation

- Start a multi-file PDF to Image conversion and press Cancel.
- Confirm processing stops after the current page or file.
- Confirm the cancellation report is written.
- Start a long-running workflow, close the app, and confirm no Python or PDF
  Toolkit process remains running in the background.

## CLI and Packaged Build

- Run one direct `pdf-toolkit` command and one JSON manifest from a folder with
  spaces; confirm JSON output and the process exit code.
- Run `powershell -ExecutionPolicy Bypass -File .\scripts\run_pyinstaller.ps1`.
- Run `powershell -ExecutionPolicy Bypass -File .\scripts\smoke_packaged_app.ps1`.
- Repeat both commands without deleting `dist` manually.
- Launch `dist/Unified PDF Toolkit/Unified PDF Toolkit.exe`.
- Confirm the app window opens and all sidebar tools render.
- If Inno Setup 6 is installed, build `installer/UnifiedPDFToolkit.iss` and launch the setup executable.
