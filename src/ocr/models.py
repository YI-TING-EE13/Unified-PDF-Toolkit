"""Typed OCR request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image


class OcrEngine(str, Enum):
    """Known OCR backend identifiers."""

    TESSERACT = "tesseract"
    UNLIMITED_OCR_FAKE = "unlimited_ocr_fake"
    LOCAL_ENDPOINT = "local_endpoint"


@dataclass(frozen=True)
class OcrRequest:
    """Prepared image-based OCR request.

    Images are provided by the caller so backends do not need to know how the
    PDF was rendered. Callers are responsible for not logging image contents.
    """

    engine: OcrEngine
    images: Sequence[Image.Image]
    source_path: Optional[str] = None
    page_numbers: Sequence[int] = field(default_factory=list)
    language: str = "eng"
    prompt: str = "document parsing."
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OcrPageResult:
    """OCR output for one rendered page or image."""

    page_number: int
    text: str
    confidence: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class OcrResult:
    """OCR output for a request."""

    engine: OcrEngine
    pages: List[OcrPageResult]
    source_path: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Combined text in page order."""

        return "\n\n".join(page.text for page in self.pages)

    @property
    def source_name(self) -> str:
        """Source filename without exposing file contents."""

        return Path(self.source_path).name if self.source_path else ""
