# GUI Smoke Checklist

Run this checklist before publishing a desktop build.

## Setup

- Start from a clean checkout.
- Run `uv sync --dev`.
- Run `uv run python scripts/gui_smoke.py`.
- Run `uv run python src/app.py`.
- Prepare one small text PDF, one image-only PDF, and two PNG/JPG images.

## Core UI

- Confirm every sidebar tool opens without errors.
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

## OCR

- If Tesseract is not installed, run OCR Text and confirm the error message explains the missing executable.
- If Tesseract is installed, run OCR Text with `eng`.
- If Traditional Chinese language data is installed, run OCR Text with `eng+chi_tra`.
- Confirm OCR DPI changes are accepted and persisted.
- Confirm OCR cleanup options are selectable and persisted.

## Cancellation

- Start a multi-file PDF to Image conversion and press Cancel.
- Confirm processing stops after the current page or file.
- Confirm the cancellation report is written.

## Packaged Build

- Run `uv run pyinstaller pdf-toolkit.spec --noconfirm`.
- Launch `dist/Unified PDF Toolkit/Unified PDF Toolkit.exe`.
- Confirm the app window opens and all sidebar tools render.
- If Inno Setup 6 is installed, build `installer/UnifiedPDFToolkit.iss` and launch the setup executable.
