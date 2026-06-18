"""Environment diagnostics for support and release smoke checks."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from .file_ops import get_default_save_dir
from .settings import get_settings_path


@dataclass
class DiagnosticCheck:
    name: str
    status: str
    detail: str
    suggestion: str = ""


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def collect_diagnostics() -> List[DiagnosticCheck]:
    """Collect dependency, runtime, OCR, and write-permission checks."""
    checks: List[DiagnosticCheck] = []
    checks.append(
        DiagnosticCheck(
            "Python",
            "ok" if sys.version_info >= (3, 10) else "error",
            platform.python_version(),
            "Install Python 3.10 or newer." if sys.version_info < (3, 10) else "",
        )
    )
    checks.append(DiagnosticCheck("Platform", "info", platform.platform()))

    try:
        root = tk.Tk()
        try:
            root.withdraw()
            tk_version = root.tk.call("info", "patchlevel")
        finally:
            root.destroy()
        checks.append(DiagnosticCheck("Tkinter", "ok", f"Tk {tk_version}"))
    except tk.TclError as exc:
        checks.append(
            DiagnosticCheck(
                "Tkinter",
                "warning",
                str(exc),
                "Run the GUI from a desktop session with an available display.",
            )
        )

    for module_name in (
        "fitz",
        "PIL",
        "pdf2docx",
        "docx",
        "tkinterdnd2",
        "pytesseract",
    ):
        available = _module_available(module_name)
        checks.append(
            DiagnosticCheck(
                module_name,
                "ok" if available else "error",
                "available" if available else "missing",
                "Run uv sync to install project dependencies."
                if not available
                else "",
            )
        )

    tesseract_path = shutil.which("tesseract")
    checks.append(
        DiagnosticCheck(
            "Tesseract executable",
            "ok" if tesseract_path else "warning",
            tesseract_path or "not found on PATH",
            "Install Tesseract OCR and add it to PATH before using OCR Text mode."
            if not tesseract_path
            else "",
        )
    )

    checks.append(_write_check("Default save folder", Path(get_default_save_dir("Diagnostics"))))
    checks.append(_write_check("Settings file folder", get_settings_path().parent))
    return checks


def _write_check(name: str, folder: Path) -> DiagnosticCheck:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".pdf_toolkit_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return DiagnosticCheck(name, "ok", str(folder))
    except OSError as exc:
        return DiagnosticCheck(
            name,
            "error",
            f"{folder}: {exc}",
            "Choose an output folder under your user profile or fix folder permissions.",
        )


def diagnostics_to_text(checks: Iterable[DiagnosticCheck]) -> str:
    lines = ["Unified PDF Toolkit Diagnostics", ""]
    for check in checks:
        lines.append(f"[{check.status.upper()}] {check.name}: {check.detail}")
        if check.suggestion:
            lines.append(f"  Suggestion: {check.suggestion}")
    return "\n".join(lines) + "\n"
