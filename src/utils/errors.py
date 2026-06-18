"""User-facing error formatting and recovery suggestions."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _contains(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def friendly_error_message(error: BaseException | str, context: str = "") -> str:
    """Return an actionable error message suitable for message boxes/reports."""
    if isinstance(error, BaseException):
        raw = str(error).strip() or error.__class__.__name__
    else:
        raw = str(error).strip()
    hint = error_hint(raw)
    prefix = f"{context}: " if context else ""
    if hint:
        return f"{prefix}{raw}\n\nSuggestion: {hint}"
    return f"{prefix}{raw}"


def error_hint(message: str) -> str:
    """Map common workflow failures to short recovery suggestions."""
    lowered = message.lower()
    if _contains(lowered, ("tesseract", "ocr text mode")):
        return (
            "Install Tesseract OCR, add it to PATH, and install the selected "
            "language data such as eng, chi_tra, or chi_sim."
        )
    if _contains(lowered, ("permission denied", "access is denied", "errno 13")):
        return "Choose a writable output folder, close locked files, or run from a user-owned directory."
    if _contains(lowered, ("encrypted", "password")):
        return "Open the PDF with its password first and save an unlocked copy before processing."
    if _contains(lowered, ("no such file", "file not found", "cannot find")):
        return "Confirm the source path still exists and re-add the file to the queue."
    if _contains(lowered, ("page range", "out of bounds", "range is empty")):
        return "Check the page range syntax, for example 1-3, 5, and keep it within the PDF page count."
    if _contains(lowered, ("invalid pdf", "cannot open broken document", "xref")):
        return "Try opening and re-saving the PDF in a reader, then process the repaired copy."
    if _contains(lowered, ("not enough memory", "memoryerror")):
        return "Process fewer files at once or lower OCR/PDF-to-image DPI."
    return ""


def describe_path(path: str) -> str:
    """Return a compact path state description for diagnostics."""
    if not path:
        return "not configured"
    target = Path(path)
    if target.exists():
        kind = "folder" if target.is_dir() else "file"
        return f"{kind}, exists"
    return "missing"
