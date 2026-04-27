# Unified PDF Toolkit

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-PyMuPDF%20%7C%20Pillow%20%7C%20Tkinter-orange)](pyproject.toml)

A comprehensive, modular, and high-performance desktop application for manipulating PDF files. Built with Python and Tkinter, it leverages **PyMuPDF (fitz)** for robust backend processing, offering a modern graphical user interface for common PDF operations without external system dependencies like Poppler or Ghostscript.

> **Privacy-First**: All processing runs entirely on your local machine. No files are uploaded to any server — your data never leaves your computer.

---

## 🚀 Features

### 📉 Compress PDF/Image
*   **Intelligent Compression**: Utilizes sophisticated image resampling and garbage collection to reduce file size.
*   **Batch Processing**: Compress individual files or recursively scan entire directories.
*   **Mixed Mode**: Add multiple folders and files to a single compression queue.
*   **Multi-threaded**: Background processing prevents UI freezing during large batch operations.

### 📑 Merge PDFs
*   **Drag-and-Sort**: Intuitive UI to reorder files before merging.
*   **Recursive Loading**: One-click import of all PDFs within a folder structure.
*   **Smart Defaults**: If no output path is chosen, files are saved automatically to `~/Documents/PDFToolkit/Saved/Merged/`.

### ✂️ Split PDF
*   **Visual Preview**: Real-time thumbnail generation allows users to visually verify split points.
*   **Queue-Based Workflow**: Add multiple PDFs to a queue, click one to preview, and split only the currently loaded file.
*   **Smart Navigation**: Scroll, drag, or use sliders to navigate pages instantly.
*   **Flexible Syntax**: Supports complex range extraction (e.g., `1-3, 5, 8-10`).

### 🖼️ PDF to Image
*   **Batch Conversion**: Convert multiple PDFs to images in one operation.
*   **High Fidelity**: Export pages as PNG, JPG, or JPEG with customizable DPI (72–600).
*   **Throttled Rendering**: Optimized event loop ensures smooth UI updates even when processing hundreds of pages.

### 📷 Image to PDF
*   **One-Click Conversion**: Combine multiple images into a single PDF with configurable page order.
*   **Inline Compression**: Images are scaled and JPEG-optimized *during* PDF creation — no huge intermediate files.
*   **Adjustable Quality**: Choose from None, Low, Medium, or High compression presets.

### 📄 Page Manager
*   **Delete Pages**: Remove specific pages by range (e.g., `3, 5-7`).
*   **Rotate Pages**: Rotate pages by 90°, 180°, or 270° with visual preview.
*   **Non-Destructive**: All modifications are applied in-memory; save only when ready.

---

## 🛠️ Architecture

The application follows a **Modular Plugin Architecture**:

```
src/
├── app.py              # Main Application Shell (sidebar, navigation, frame caching)
├── base/
│   └── tool.py         # BaseTool ABC — all tools inherit from this
├── ui/
│   └── components.py   # Shared UI widgets (FileListWidget)
├── tools/              # Each tool is a self-contained package
│   ├── compressor/
│   ├── merger/
│   ├── splitter/
│   ├── converter/
│   ├── image2pdf/
│   └── page_manager/
├── core/               # Shared processors (BatchProcessor)
├── handlers/           # Format-specific compression logic (PDF, Image, Text)
└── utils/              # File operations, logging, default paths
```

### Key Design Patterns

*   **`FileListWidget`**: A reusable UI component shared across all tools, ensuring a consistent file selection experience (Add Files, Add Folder, Move Up/Down, Remove, Clear).
*   **Default Save Paths**: When no output path is specified, files are automatically saved to `~/Documents/PDFToolkit/Saved/{ToolName}/`. This avoids permission issues when the app is packaged as a standalone executable.
*   **Thread-Safe Queue**: All tools use a `queue.Queue` for communication between worker threads and the Tkinter main thread, ensuring responsive UI during heavy operations.

---

## 📦 Installation

This project uses `uv` for modern Python package management, but standard `pip` works as well.

### Prerequisites
*   Python 3.10 or higher

### Option A: Using `uv` (Recommended)
```bash
# 1. Clone the repository
git clone https://github.com/YI-TING-EE13/Unified-PDF-Toolkit.git
cd Unified-PDF-Toolkit

# 2. Sync dependencies
uv sync

# 3. Run the application
uv run python src/app.py
```

### Option B: Using standard `pip`
```bash
# 1. Create a virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dependencies
pip install pymupdf pillow

# 3. Run
python src/app.py
```

---

## 🖥️ Usage Guide

1.  **Launch the App**: Run `uv run python src/app.py`.
2.  **Select a Tool**: Use the dark sidebar to navigate between the 6 available tools.
3.  **Common Operations**:
    *   **Compress**: Add files/folders → select compression level → click "Start Compression".
    *   **Merge**: Add PDFs → use Move Up/Down to arrange order → click "Merge & Save As...".
    *   **Split**: Add PDFs to queue → click a file to preview → set page range → click "Split PDF".
    *   **PDF to Image**: Add PDFs → set DPI and format → click "Convert to Images".
    *   **Image to PDF**: Add images (order = page order) → select compression → click "Convert to PDF".
    *   **Page Manager**: Add a PDF → click to preview → delete or rotate pages → click "Save Modified PDF".

---

## 🤝 Contributing

Contributions are welcome! To add a new tool:

1.  Create a new directory in `src/tools/your_tool/`.
2.  Create `__init__.py` and `tool.py`.
3.  Inherit from `BaseTool` and implement `render()` and `execute()`.
4.  Use `FileListWidget` from `src/ui/components.py` for file selection.
5.  Register your tool in `src/app.py` → `_register_tools()`.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
