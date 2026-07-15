# Unified PDF Toolkit

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/YI-TING-EE13/Unified-PDF-Toolkit?include_prereleases&label=release)](https://github.com/YI-TING-EE13/Unified-PDF-Toolkit/releases)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Unified PDF Toolkit is a local-first desktop and command-line application for
everyday PDF work: compressing, merging, splitting, converting, page editing,
OCR-assisted text extraction, and repeatable batch jobs.

The app runs on your machine. Source files are not uploaded to any external
service.

## Highlights

- **All-in-one PDF workspace**: compress PDFs and images, merge files, split
  selected ranges, convert PDF pages to images, convert images to PDF, and edit
  page order or rotation.
- **PDF to Word workflows**: export to DOCX using layout preservation, text-only
  extraction, page images, or OCR text mode.
- **Document OCR outputs**: extract OCR text from PDF/image files to local TXT
  or Markdown files, using Tesseract by default.
- **GUI and headless Batch Queue**: run repeatable mixed jobs from the desktop
  app or a JSON manifest and generate TXT, CSV, and JSON reports.
- **Diagnostics**: check Python, Tkinter, key dependencies, Tesseract executable
  and language data, and writable output folders from inside the app.
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
- Run the same supported operations without a GUI through the `pdf-toolkit`
  command and reusable JSON manifests.

### Document OCR

- Select PDF or image files and write local TXT or Markdown OCR outputs.
- Uses Tesseract OCR by default.
- Settings / Recent includes a read-only device analyzer and consent-gated
  managed setup for the optional Unlimited-OCR advanced local provider.
- A successful managed install registers its isolated worker automatically;
  developers can still expose a manually configured controlled-beta runtime
  with `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.
- Unlimited-OCR is local-only, optional, disabled until setup succeeds, and
  automatically falls back to Tesseract when unavailable.
- Beginner walkthrough:
  [docs/tutorials/getting_started_document_ocr.md](docs/tutorials/getting_started_document_ocr.md).

### Diagnostics and Settings

- Check runtime dependencies and writable folders.
- Copy diagnostic results for troubleshooting.
- Review recent inputs, outputs, and reports.
- Configure output conflict behavior.

### Advanced Local Unlimited-OCR

The APP now includes a managed, metadata-driven deployment framework for
[Baidu Unlimited-OCR](https://github.com/baidu/Unlimited-OCR). It inspects the
device, reports a conservative compatibility status, shows exact download,
disk, VRAM, custom-code, privacy, and system-change boundaries, and requires six
explicit acknowledgements before setup can begin. It does not treat every
NVIDIA GPU as supported.

Approved setup creates an APP-private uv environment or private Conda prefix,
installs a compatible official PyTorch CUDA wheel, downloads a pinned model
revision with resumable cache, verifies the complete selected file inventory
and model SHA-256, then runs import, CUDA, model-load, five-case OCR, and resource
benchmark gates. The staged journal supports retry, pause, cancellation, resume,
diagnostics, uninstall, and cache cleanup.

The default APP still does not bundle torch, Transformers, CUDA runtimes, or the
model, and does not import the AI runtime at startup. The managed plan never
updates NVIDIA Driver, replaces system CUDA, edits PATH, or changes global
Python. Pages and OCR output remain local; full OCR text is excluded from normal
setup logs. Tesseract remains the default and fallback provider.

Device analysis reports APP/CLI readiness, current GUI/display readiness,
Tesseract availability, and Unlimited-OCR compatibility separately. An
unsupported advanced provider does not make the normal PDF/CLI tools
unsupported. If neither a compatible uv nor Conda installation is available,
an otherwise eligible advanced-OCR plan can disclose a consent-gated,
SHA-256-verified APP-managed uv prerequisite; it never edits PATH or shell
profiles.

See the [managed setup and security guide](docs/runtime/managed_unlimited_ocr.md),
[current validation record](docs/testing/managed_unlimited_ocr_validation.md),
and [custom model-code policy](docs/security/unlimited_ocr_trust_remote_code_policy.md).
The older manual controlled-beta guide remains available for developer-managed
runtimes.

For development and UI-flow testing only, setting
`PDF_TOOLKIT_ENABLE_DEV_TOOLS=1` exposes the hidden `[Dev] Document OCR Shell`.
It uses deterministic placeholder output from the fake backend, requires the
same advanced OCR consent record, and still performs no real Unlimited-OCR
inference, model download, endpoint call, GPU execution, or network upload.

## Requirements

- Python 3.10 or newer for source runs.
- `uv` is recommended for dependency management.
- Tesseract OCR is optional, but required for OCR Text mode and default
  Document OCR.
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
uv run --no-sync python src/app.py
```

If `uv` is not on `PATH`, first check the normal user locations
`~/.local/bin/uv` and `~/.cargo/bin/uv`. Install it from the
[official uv instructions](https://docs.astral.sh/uv/getting-started/installation/)
only when it is genuinely absent. To keep shell profiles unchanged on Linux or
macOS, use the official installer with `UV_NO_MODIFY_PATH=1`, then invoke the
result by absolute path. If the system Python is older than this project's
`>=3.10` requirement, select a compatible existing interpreter explicitly:

```bash
~/.local/bin/uv sync --python /path/to/python3.12
~/.local/bin/uv run --no-sync python src/app.py
```

The source-checkout bootstrap is separate from optional Unlimited-OCR setup.
Normal APP dependencies never include torch, Transformers, or a model.

On macOS, prefer a Tk-enabled Python runtime:

```bash
uv sync --python /opt/homebrew/bin/python3.12
uv run --no-sync --python /opt/homebrew/bin/python3.12 python src/app.py
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

- `run-windows.bat` checks for `uv`, repairs incomplete project package metadata,
  syncs dependencies with an uv-managed Python 3.12 runtime, and starts the app
  without a redundant second dependency sync.
- `run-macos.command` checks for `uv`, prefers a Tk-enabled Python 3.12 runtime,
  performs the same metadata repair, syncs dependencies, and starts the app.

The metadata repair removes only this project's incomplete `pdf_toolkit-*.dist-info`
folders when their required `RECORD` file is missing. If repair reports that a
folder is still in use, close running Python or PDF Toolkit processes and start
the launcher again.

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

## Command-Line and Headless Batch

Installing the project creates a `pdf-toolkit` console command. It does not open
Tkinter and is suitable for scripts, scheduled tasks, CI, and servers without a
display. Direct commands support compression, PDF-to-image, and PDF-to-Word
jobs—the same operation set as Batch Queue.

```powershell
uv run --no-sync pdf-toolkit compress "input.pdf" -o "output" --level Medium
uv run --no-sync pdf-toolkit pdf-to-images "input.pdf" -o "output" --dpi 150 --pages "1-3,5"
uv run --no-sync pdf-toolkit pdf-to-word "input.pdf" -o "output" --mode text
uv run --no-sync pdf-toolkit batch "docs/examples/batch-manifest.json" --json
```

Every command accepts `--conflict rename|overwrite|skip`; `rename` is the
default. Batch source paths and an unqualified manifest `output_dir` are resolved
relative to the manifest file. Pressing Ctrl+C stops before the next job and
returns exit code 130. See [docs/cli.md](docs/cli.md) for the manifest schema,
exit codes, and automation examples.

## Project Structure

```text
src/
  app.py              # Tkinter shell and navigation
  cli.py              # Headless CLI and manifest entry point
  core/
    batch.py          # GUI-independent batch execution
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
  ocr/               # OCR backend contracts and optional-backend scaffolding
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
uv run --no-sync ruff check .
uv run --no-sync bandit -q -r src scripts -x tests -ll
uv run --no-sync pip-audit --skip-editable
uv run --no-sync coverage run -m unittest discover -s tests -v
uv run --no-sync coverage report
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python verify_install.py
uv run --no-sync python scripts/gui_smoke.py
uv run --no-sync python -m compileall -q src tests verify_install.py scripts
uv build
```

Release-specific checks are documented in
[docs/release_checklist.md](docs/release_checklist.md). Manual GUI checks are
documented in [docs/gui_smoke_checklist.md](docs/gui_smoke_checklist.md). The
P0-P2 adversarial and resource gates are mapped in
[docs/testing/stability_matrix.md](docs/testing/stability_matrix.md).

## Packaging

Build a Windows app bundle with the repository wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_pyinstaller.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_packaged_app.ps1
```

Build a Windows installer when Inno Setup 6 is installed:

```powershell
.\scripts\build_installer.ps1
```

Tagged releases are handled by `.github/workflows/release.yml`.

## Roadmap

The canonical [Advanced OCR Roadmap](docs/roadmap/advanced_ocr_next_goals.md)
tracks the verified hardware matrix, next validation priorities, known limits,
research directions, and evidence required before expanding support claims.

Broader product ideas include searchable PDF OCR output, watermark/page number
tools, metadata privacy cleanup, and direct CLI coverage for merge, split,
image-to-PDF, and page-editing workflows.

PDF to Word planning notes and known conversion limits are documented in
[docs/pdf_to_word_plan.md](docs/pdf_to_word_plan.md).

## Versioning Policy

README should describe the current project, current stable release, installation
paths, and major capabilities. Detailed historical release notes belong in
[CHANGELOG.md](CHANGELOG.md). This keeps the project homepage readable while
preserving a full version history for users who need it.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
