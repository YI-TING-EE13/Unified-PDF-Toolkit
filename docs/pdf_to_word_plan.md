# PDF to Word Feature Plan

## References

- pdf2docx documentation: https://pdf2docx.readthedocs.io/
- pdf2docx PyPI package: https://pypi.org/project/pdf2docx/
- PyMuPDF text extraction documentation: https://pymupdf.readthedocs.io/en/latest/recipes-text.html
- python-docx quickstart: https://python-docx.readthedocs.io/en/stable/user/quickstart.html

## Product Goal

Add a `PDF to Word` tool that matches the existing PDF Toolkit interaction style:

- Uses `FileListWidget` for file selection.
- Uses visible output folder/path controls before processing starts.
- Runs conversion work in a background thread.
- Reports progress through the Tkinter queue pattern.
- Uses `OutputActions` for Open Output Folder / Copy Path.
- Persists common settings locally through `src/utils/settings.py`.

## Phase 1: Layout Mode MVP

Scope:

- Add a new `PDF to Word` sidebar tool.
- Use `pdf2docx` Layout Mode via `Converter`.
- Support batch conversion from PDF files to `.docx`.
- Use default output folder `~/Documents/PDFToolkit/Saved/Word/`.
- Add a read-only Mode field set to `Preserve Layout`.
- Add optional page range input:
  - Empty means all pages.
  - Supports a single page (`5`), continuous range (`1-3`), or comma-separated ranges (`1-3, 5`).
  - For non-contiguous ranges, create a temporary PDF with selected pages before passing it to `pdf2docx`.
- Continue processing remaining files if one file fails.
- Report success / failed / skipped counts.
- Add tests that create a simple PDF, convert it to `.docx`, and verify output exists and is non-empty.

Known limits:

- PDF is not a Word source format, so complex layouts may not round-trip perfectly.
- Scanned/image-only PDFs need OCR, which is outside Phase 1.
- Some fonts, tables, columns, and vector graphics may need later quality improvements.

## Phase 2: Reliability and User Control

Implemented additions:

- Preflight detection for encrypted PDFs, empty PDFs, and image-only PDFs.
- More detailed per-file error report.
- Better page-range validation feedback before starting conversion.
- PDF page preview in the `PDF to Word` tool, matching the Split/Page Manager preview pattern.
- More unit tests around bad page ranges and image-only PDFs.

Deferred:

- Optional "open output on completion" preference.

## Later Phases

Potential additions:

- OCR Mode for scanned PDFs.
- Conversion report with page count, elapsed time, output size, and failure list.

## Phase 3: Quality Modes

Implemented additions:

- Enlarged the application window to make preview-heavy workflows easier to use.
- Added conversion mode selection:
  - `Preserve Layout`: existing `pdf2docx` layout-preserving conversion.
  - `Text Only`: extracts editable text with PyMuPDF and writes DOCX with python-docx.
  - `Page Images`: renders each selected PDF page into the Word document as an image.
- `Page Images` is intended as a practical fallback when Preserve Layout creates blank pages or mishandles complex image-heavy pages.
- Math formulas may become garbled in editable modes because PDF formulas are often stored as positioned glyphs or embedded fonts rather than semantic equations. Use `Page Images` when visual fidelity is more important than editability.

## Phase 4: Workflow Controls and OCR

Implemented additions:

- Drag-and-drop support for file lists when native Tk drag-and-drop support is available.
- Completion reports for long-running workflows.
- Shared output conflict policy: rename, overwrite, or skip.
- Cancel buttons for long-running/background workflows.
- Settings / Recent view for conflict policy and recent paths.
- `OCR Text` mode for scanned PDFs through `pytesseract`.
- Configurable OCR language codes such as `eng`, `chi_tra`, `chi_sim`, and combined language packs.
- Configurable OCR render DPI for quality/performance tradeoffs.
- TXT, CSV, and JSON completion reports for workflow review and automation.

External requirement:

- OCR Text requires the Tesseract executable to be installed separately and available on PATH.

## Phase 5: OCR Cleanup and Batch Integration

Implemented in 0.5.0:

- OCR cleanup options for None, Grayscale, Auto Contrast, and Threshold preprocessing.
- Batch Queue integration for PDF to Word Text Only, Page Images, and OCR Text jobs.
- User-facing recovery suggestions for OCR, page-range, encrypted-PDF, missing-file, permission, and damaged-PDF failures.
- Diagnostics view for validating Tesseract and dependency availability before OCR workflows.

Remaining later work:

- Optional formula-aware conversion/OCR investigation for users who need editable equations.
- Conversion report with page count, elapsed time, output size, and failure list.
