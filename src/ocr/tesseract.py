"""Tesseract OCR backend wrapper."""

from __future__ import annotations

from .exceptions import OcrDependencyMissingError
from .models import OcrEngine, OcrPageResult, OcrRequest, OcrResult


class TesseractBackend:
    """OCR backend using pytesseract and the external Tesseract executable."""

    engine = OcrEngine.TESSERACT
    display_name = "Tesseract OCR"

    def recognize(self, request: OcrRequest) -> OcrResult:
        try:
            import pytesseract
        except ImportError as exc:
            raise OcrDependencyMissingError(
                "OCR Text mode requires pytesseract. Run uv sync and install Tesseract OCR."
            ) from exc

        pages = []
        page_numbers = list(request.page_numbers)
        for index, image in enumerate(request.images):
            page_number = page_numbers[index] if index < len(page_numbers) else index + 1
            try:
                text = pytesseract.image_to_string(image, lang=request.language).strip()
            except pytesseract.pytesseract.TesseractNotFoundError as exc:
                raise OcrDependencyMissingError(
                    "OCR Text mode requires the Tesseract executable. "
                    "Install Tesseract OCR and make sure it is on PATH."
                ) from exc
            pages.append(OcrPageResult(page_number=page_number, text=text))

        return OcrResult(
            engine=self.engine,
            pages=pages,
            source_path=request.source_path,
        )
