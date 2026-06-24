"""Fake Unlimited-OCR backend for tests and UI/dev wiring only."""

from __future__ import annotations

from .consent import AdvancedOcrConsent, require_valid_consent
from .models import OcrEngine, OcrPageResult, OcrRequest, OcrResult

UNLIMITED_OCR_PROVIDER = "baidu"
UNLIMITED_OCR_MODEL_ID = "baidu/Unlimited-OCR"


class FakeUnlimitedOcrBackend:
    """Deterministic placeholder backend.

    This backend intentionally performs no model loading, inference, network
    access, torch import, transformers import, or file upload.
    """

    engine = OcrEngine.UNLIMITED_OCR_FAKE
    display_name = "Unlimited-OCR Fake Backend"

    def __init__(self, consent: AdvancedOcrConsent | None = None) -> None:
        self.consent = consent

    def recognize(self, request: OcrRequest) -> OcrResult:
        require_valid_consent(
            self.consent,
            provider=UNLIMITED_OCR_PROVIDER,
            model_id=UNLIMITED_OCR_MODEL_ID,
        )
        page_numbers = list(request.page_numbers)
        pages = []
        for index, image in enumerate(request.images):
            page_number = page_numbers[index] if index < len(page_numbers) else index + 1
            pages.append(
                OcrPageResult(
                    page_number=page_number,
                    text=(
                        f"[fake Unlimited-OCR] page={page_number} "
                        f"size={image.width}x{image.height} prompt={request.prompt}"
                    ),
                    warnings=["Fake backend only; no real model inference was performed."],
                )
            )
        return OcrResult(
            engine=self.engine,
            pages=pages,
            source_path=request.source_path,
            warnings=["Fake backend only; no real model inference was performed."],
            metadata={"provider": UNLIMITED_OCR_PROVIDER, "model_id": UNLIMITED_OCR_MODEL_ID},
        )
