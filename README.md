# Unified PDF Toolkit

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-PyMuPDF%20%7C%20Pillow%20%7C%20pdf2docx-orange)](pyproject.toml)

**Current version: 0.3.0**

Unified PDF Toolkit is a local-first desktop app for common PDF workflows. It is built with Python, Tkinter, PyMuPDF, Pillow, and pdf2docx. Files are processed on your machine; nothing is uploaded to an external service.

## Version 0.3.0 Highlights

*   **PDF to Word**: Added DOCX conversion with Preserve Layout, Text Only, and Page Images modes.
*   **PDF to Word preview and preflight**: Preview pages and detect encrypted, empty, or image-only PDFs before conversion.
*   **Merged PDF preview**: Merge mode now shows a larger live preview of the combined page order.
*   **Merge + Compress workflow**: Merge can automatically compress the final PDF with adjustable Low, Medium, or High settings.
*   **Larger workspace**: The app opens at a wider default size for preview-heavy workflows.
*   **Progress feedback**: Long-running tools show progress or busy indicators so users can tell work is still running.
*   **Saved roadmap**: PDF to Word implementation notes and references live in `docs/pdf_to_word_plan.md`.

## Features

### Compress PDF/Image

*   Compress PDF and image files in batches.
*   Add individual files or recursively scan folders.
*   Tune PDF image optimization, max image dimension, JPEG quality, or run lossless cleanup only.
*   Shows progress while files are processed.

### Merge PDFs

*   Add PDFs individually or from folders.
*   Reorder files with Move Up / Move Down before merging.
*   Show page counts directly in the merge list.
*   Preview the final merged page sequence before saving.
*   Optionally compress the merged PDF immediately after merge.
*   Shows merge progress by input file and a busy indicator during post-merge compression.

### Split PDF

*   Add PDFs to a queue and click one file to preview it.
*   Select page ranges with sliders or text syntax such as `1-3, 5, 8-10`.
*   Split only the currently previewed PDF.
*   Shows progress while output PDFs are created.

### PDF to Image

*   Convert PDF pages to PNG, JPG, or JPEG.
*   Customize DPI from 72 to 600.
*   Uses throttled UI updates for smoother large batch conversions.

### PDF to Word

*   Convert PDFs to `.docx` using `pdf2docx`.
*   Supports batch conversion.
*   Supports selected page ranges such as `1-3, 5`.
*   Modes:
    *   `Preserve Layout`: Best effort editable DOCX layout conversion.
    *   `Text Only`: Extracts editable text with simpler formatting.
    *   `Page Images`: Places each PDF page into DOCX as an image for visual fidelity.
*   Known limitation: editable conversion can garble complex math formulas, embedded fonts, or highly positioned layout. Use Page Images when visual fidelity matters more than editability.

### Image to PDF

*   Combine multiple images into one PDF.
*   Preserve image order as page order.
*   Apply inline compression during PDF creation.
*   Choose None, Low, Medium, or High compression presets.

### Page Manager

*   Delete pages by range.
*   Rotate pages by 90, 180, or 270 degrees.
*   Reorder pages, insert another PDF, or extract selected pages.
*   Applies edits in memory and saves only when ready.
*   Shows a busy indicator while writing the modified PDF.

## Architecture

The app uses a modular tool architecture:

```text
src/
  app.py              # Main Tkinter shell and navigation
  base/
    tool.py           # BaseTool interface
  ui/
    components.py     # Shared UI widgets
  tools/
    compressor/
    merger/
    splitter/
    converter/
    pdf2word/
    image2pdf/
    page_manager/
  handlers/           # Format-specific processing logic
  utils/              # File operations, settings, defaults
```

Key patterns:

*   **`FileListWidget`** provides consistent file selection, folder import, ordering, removal, and change callbacks.
*   **Visible output controls** show the output path or folder before work starts.
*   **Thread-safe queues** keep Tkinter responsive while worker threads process files.
*   **Output actions** let users open the output folder or copy the output path after completion.

## Installation

This project uses `uv` for dependency management, but standard `pip` also works.

### macOS double-click launcher

For friends or teammates who do not want to type commands in Terminal:

1.  Download or clone this project, then unzip it if needed.
2.  Open the project folder in Finder.
3.  Double-click `run-macos.command`.
4.  If macOS blocks the file the first time, right-click `run-macos.command`, choose **Open**, then confirm.
5.  If macOS says the file is not executable, open Terminal in this folder and run:

```bash
chmod +x run-macos.command
```

The launcher checks for `uv`, syncs the project dependencies, and starts the app with `uv run python src/app.py`. If `uv` is missing, it prints the install command and waits so the message stays visible.

### Windows double-click launcher

For friends or teammates on Windows:

1.  Download or clone this project, then unzip it if needed.
2.  Open the project folder in File Explorer.
3.  Double-click `run-windows.bat`.
4.  If Windows SmartScreen asks for confirmation, choose **More info** and then **Run anyway** only if you trust this project folder.

The launcher checks for `uv`, syncs the project dependencies, and starts the app with `uv run python src/app.py`. If `uv` is missing, it prints the Windows PowerShell install command and waits so the message stays visible.

### Option A: uv

```bash
git clone https://github.com/YI-TING-EE13/Unified-PDF-Toolkit.git
cd Unified-PDF-Toolkit
uv sync
uv run python src/app.py
```

### Option B: pip

```bash
python -m venv venv
venv\Scripts\activate
pip install pymupdf pillow pdf2docx
python src/app.py
```

## Usage

1.  Launch the app with `uv run python src/app.py`.
2.  Select a tool from the sidebar.
3.  Add source files or folders.
4.  Review preview, settings, and output path.
5.  Start the task and watch the progress/status area.

Common workflows:

*   **Compress**: Add files/folders -> select compression options -> click Start Compression.
*   **Merge**: Add PDFs -> arrange order -> review merged preview -> optionally enable compression -> click Merge PDFs.
*   **Split**: Add PDFs -> click one file to preview -> set page range -> click Split PDF.
*   **PDF to Image**: Add PDFs -> set DPI and format -> click Convert to Images.
*   **PDF to Word**: Add PDFs -> choose mode and optional page range -> click Convert to Word.
*   **Image to PDF**: Add images -> arrange order -> choose compression -> click Convert to PDF.
*   **Page Manager**: Add a PDF -> preview it -> edit pages -> click Save Modified PDF.

## Testing

```bash
uv run python -m unittest discover -s tests -v
uv run python verify_install.py
```

## Roadmap Notes

PDF to Word planning, implemented phases, references, and known conversion limits are documented in `docs/pdf_to_word_plan.md`.

## License

Distributed under the MIT License. See `LICENSE` for more information.
