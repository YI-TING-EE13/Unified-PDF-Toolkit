# Unified PDF Toolkit

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-PyMuPDF%20%7C%20Pillow%20%7C%20Tkinter-orange)](pyproject.toml)

A comprehensive, modular, and high-performance desktop application for manipulating PDF files. Built with Python and Tkinter, it leverages **PyMuPDF (fitz)** for robust backend processing, offering a modern graphical user interface for common PDF operations without external system dependencies like Poppler or Ghostscript.

---

## 🚀 Features

### 📉 PDF Compressor
*   **Intelligent Compression**: utilizes sophisticated image resampling and garbage collection to reduce file size.
*   **Batch Processing**: Support for compressing individual files or recursively scanning entire directories.
*   **Mixed Mode**: Add multiple folders and files to a single compression queue.
*   **Performance**: Multi-threaded processing prevents UI freezing during large batch operations.

### 📑 PDF Merger
*   **Drag-and-Sort**: Intuitive UI to reorder files before merging.
*   **Recursive Loading**: One-click import of all PDFs within a folder structure.
*   **Safe Merge**: Validates file integrity before attempting to combine documents.

### ✂️ PDF Splitter
*   **Visual Preview**: Real-time thumbnail generation allows users to visually verify split points.
*   **Smart Navigation**: Scroll, drag, or use sliders to navigate pages instantly.
*   **Flexible Syntax**: Supports complex range extraction (e.g., `1-3, 5, 8-10`).

### 🖼️ PDF to Image Converter
*   **High Fidelity**: Convert PDF pages to JPG or PNG with customizable DPI.
*   **Throttled Rendering**: Optimized event loop ensures smooth UI updates even when processing hundreds of pages per second.

---

## 🛠️ Architecture

The application follows a **Modular Plugin Architecture**:

*   **`src/app.py`**: The main Application Shell. It handles the lifecycle, navigation sidebar, and frame persistence (caching UIs so state is not lost when switching tabs).
*   **`src/base/tool.py`**: Defines the `BaseTool` abstract interface. New tools can be added by simply inheriting from this class and implementing the `render` and `execute` methods.
*   **`src/tools/`**: Each functionality (Compressor, Merger, etc.) is a self-contained package.
*   **`src/core/`**: Shared resources and processor logic (e.g., `BatchProcessor`).

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
uv run src/app.py
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

## 🖥️ Usage Guide

1.  **Launch the App**: Run `src/app.py`.
2.  **Select a Tool**: Use the dark sidebar to navigate between tools.
3.  **Operation**:
    *   **Compress**: Click "Add Folder", select your source, choose "Medium" level, and click Start.
    *   **Split**: Open a PDF. Use the top slider to drag through pages. Set "Start" and "End" sliders to mark your clip. Click "Split PDF".
    *   **Merge**: Add multiple files. Use "Move Up/Down" to arrange order. Click "Merge".

## 🤝 Contributing

Contributions are welcome! Please follow the existing modular structure:
1.  Create a new directory in `src/tools/`.
2.  Inherit from `BaseTool`.
3.  Register your tool in `src/app.py`.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
