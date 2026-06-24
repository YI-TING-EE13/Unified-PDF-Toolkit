"""Shared OCR backend contract."""

from __future__ import annotations

from typing import Protocol

from .models import OcrEngine, OcrRequest, OcrResult


class OcrBackend(Protocol):
    """Protocol implemented by OCR engines."""

    engine: OcrEngine
    display_name: str

    def recognize(self, request: OcrRequest) -> OcrResult:
        """Recognize text from the prepared OCR request."""
