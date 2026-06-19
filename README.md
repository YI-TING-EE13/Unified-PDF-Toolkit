# Unified PDF Toolkit

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/YI-TING-EE13/Unified-PDF-Toolkit?include_prereleases&label=release)](https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/releases)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Unified PDF Toolkit is a local-first desktop application for everyday PDF work:
compressing, merging, splitting, converting, page editing, OCR-assisted text
extraction, and repeatable batch jobs.

The app runs on your machine. Source files are not uploaded to any external
service.

## Highlights

- **All-in-one PDF workspace**: compress PDFs and images, merge files, split
  selected ranges, convert PDF pages to images, convert images to PDF, and edit
  page order or rotation.
- **PDF to Word workflows**: export to DOCX using layout preservation, text-only
  extraction, page images, or OCR text mode.
- **Batch Queue**: run repeatable mixed jobs and generate TXT, CSV, and JSON
  reports.
- **Diagnostics**: check Python, Tkinter, key dependencies, Tesseract OCR, and
  writable output folders from inside the app.
- **Local release packaging**: CI builds Python packages, a Windows app bundle,
  and a Windows installer for tagged releases.

Current stable release: **0.5.0**. See [CHANGELOG.md](CHANGELOG.md) for the
full release history.

## Download

Windows users can download the latest release from:

<https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/releases>

Available release assets usually include:

- `Unified-PDF-Toolkit-Setup-<version>.exe`: Windows installer.
- `Unified-PDF-Toolkit-Windows.zip`: portable Windows app bundle.
- `pdf_toolkit-<version>-py3-none-any.whl` and `.tar.gz`: Python package
  artifacts.

If Windows SmartScreen warns about the installer, only continue if you trust the
repository and release source. The project currently does not ship with a paid
code-signing certificate.

## Features

### Compress PDF/Image

- Compress PDF and image files in batches.
- Add files directly or scan folders recursively.
- Tune PDF image optimization, max image dimension, JPEG quality, or run
  lossless cleanup.
- Choose output conflict handling: rename, overwrite, or skip.

### Merge PDFs

- Add PDFs individually or from folders.
- Reorder inputs before merging.
- Preview the combined page order.
- Optionally compress the merged output.

### Split PDF

- Preview a selected PDF before splitting.
- Select pages with sliders or range syntax such as `1-3, 5, 8-10`.
- Save only the selected ranges.

### PDF to Image

- Convert PDF pages to PNG, JPG, or JPEG.
- Select render DPI from 72 to 600.
- Uses throttled UI updates for large files.

### PDF to Word

- Convert PDFs to `.docx` with multiple modes:
  - `Preserve Layout`: best-effort editable DOCX conversion.
  - `Text Only`: simpler editable text extraction.
  - `Page Images`: each PDF page is placed into DOCX as an image.
  - `OCR Text`: scanned pages are rendered and sent through Tesseract OCR.
- Supports selected page ranges.
- Detects common preflight issues such as encrypted, empty, or image-only PDFs.
- Supports OCR cleanup modes: None, Grayscale, Auto Contrast, and Threshold.

Editable PDF-to-DOCX conversion is best effort. Complex math, embedded fonts, or
heavily positioned layouts may not convert cleanly. Use Page Images when visual
fidelity matters more than editability.

### Image to PDF

- Combine images into one PDF.
- Preserve image order as page order.
- Apply optional compression during PDF creation.

### Page Manager

- Delete, rotate, reorder, insert, or extract pages.
- Apply edits in memory and save when ready.
- Preview the current page while editing.

### Batch Queue

- Queue mixed jobs across compression, PDF to image, and PDF to Word modes.
- Reuse page range, OCR language, DPI, and OCR cleanup settings.
- Run jobs sequentially with a structured completion report.

### Diagnostics and Settings

- Check runtime dependencies and writable folders.
- Copy diagnostic results for troubleshooting.
- Review recent inputs, outputs, and reports.
- Configure output conflict behavior.

## Requirements

- Python 3.10 or newer for source runs.
- `uv` is recommended for dependency management.
- Tesseract OCR is optional, but required for OCR Text mode.
- macOS users should use a Python build with modern Tkinter support. The system
  `/usr/bin/python3` can use an older Tcl/Tk runtime on recent macOS versions.

## Installation

### Option 1: Windows Installer

1. Download `Unified-PDF-Toolkit-Setup-<version>.exe` from the latest release.
2. Run the installer.
3. Start Unified PDF Toolkit from the Start Menu or desktop shortcut.

The installer uses a per-user install location and does not require
administrator privileges.

### Option 2: Portable Windows Bundle

1. Download `Unified-PDF-Toolkit-Windows.zip` from the latest release.
2. Extract the archive.
3. Run `Unified PDF Toolkit.exe`.

### Option 3: Source Checkout with uv

```bash
git clone https://github.com/YI-TING-EE13/Unified-PDF-Toolkit.git
cd Unified-PDF-Toolkit
uv sync
uv run python src/app.py
```

On macOS, prefer a Tk-enabled Python runtime:

```bash
uv sync --python /opt/homebrew/bin/python3.12
uv run --python /opt/homebrew/bin/python3.12 python src/app.py
```

### Option 4: Source Checkout with pip

```bash
python -m venv venv
venv\Scripts\activate
pip install pymupdf pillow pdf2docx python-docx tkinterdnd2 pytesseract
python src/app.py
```

OCR Text mode also requires the Tesseract executable and the relevant language
data files. Use language codes such as `eng`, `chi_tra`, `chi_sim`,
`eng+chi_tra`, or `eng+chi_sim` only when the matching Tesseract data is
installed.

## Double-Click Launchers

The repository includes convenience launchers for source checkouts:

- `run-windows.bat` checks for `uv`, syncs dependencies with Python 3.12, and
  starts the app.
- `run-macos.command` checks for `uv`, prefers a Tk-enabled Python 3.12 runtime,
  syncs dependencies, and starts the app.

If macOS reports that `run-macos.command` is not executable:

```bash
chmod +x run-macos.command
```

## Basic Usage

1. Launch the app.
2. Select a tool from the sidebar.
3. Add source files or folders.
4. Review previews, settings, and output paths.
5. Start the task and monitor the progress area.
6. Open the output folder or copy the output path when the task completes.

## Project Structure

```text
src/
  app.py              # Tkinter shell and navigation
  base/
    tool.py           # BaseTool interface
  ui/
    components.py     # Shared widgets and output actions
  tools/
    compressor/
    merger/
    splitter/
    converter/
    pdf2word/
    image2pdf/
    page_manager/
    batch_queue/
    diagnostics/
  handlers/           # Format-specific processing logic
  utils/              # File operations, settings, diagnostics, reports
```

Design patterns used throughout the app:

- Shared file-list and output-action widgets for consistent workflows.
- Worker threads and queues to keep Tkinter responsive.
- Visible output paths before execution.
- Structured reports for long-running or batch workflows.
- Friendly error messages with recovery suggestions.

## Development

Install development dependencies:

```bash
uv sync --dev
```

Run the validation suite:

```bash
uv run python -m unittest discover -s tests -v
uv run python verify_install.py
uv run python scripts/gui_smoke.py
uv run python -m compileall -q src tests verify_install.py scripts
uv build
```

Release-specific checks are documented in
[docs/release_checklist.md](docs/release_checklist.md). Manual GUI checks are
documented in [docs/gui_smoke_checklist.md](docs/gui_smoke_checklist.md).

## Packaging

Build a Windows app bundle with the repository wrapper:

```powershell
.\scripts\run_pyinstaller.ps1
```

Build a Windows installer when Inno Setup 6 is installed:

```powershell
.\scripts\build_installer.ps1
```

Tagged releases are handled by `.github/workflows/release.yml`.

## Roadmap

Useful next improvements include searchable PDF OCR output, watermark/page
number tools, metadata privacy cleanup, broader Batch Queue coverage, and a CLI
for automation.

PDF to Word planning notes and known conversion limits are documented in
[docs/pdf_to_word_plan.md](docs/pdf_to_word_plan.md).

## Versioning Policy

README should describe the current project, current stable release, installation
paths, and major capabilities. Detailed historical release notes belong in
[CHANGELOG.md](CHANGELOG.md). This keeps the project homepage readable while
preserving a full version history for users who need it.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
