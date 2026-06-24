"""OCR backend abstractions for local-first text extraction."""

from .exceptions import (
    OcrBackendUnavailableError,
    OcrConsentRequiredError,
    OcrDependencyMissingError,
    OcrError,
)
from .models import OcrEngine, OcrPageResult, OcrRequest, OcrResult
from .registry import get_backend, list_backends, register_backend

__all__ = [
    "OcrBackendUnavailableError",
    "OcrConsentRequiredError",
    "OcrDependencyMissingError",
    "OcrEngine",
    "OcrError",
    "OcrPageResult",
    "OcrRequest",
    "OcrResult",
    "get_backend",
    "list_backends",
    "register_backend",
]
