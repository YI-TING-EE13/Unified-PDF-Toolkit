"""Lightweight OCR backend registry."""

from __future__ import annotations

from typing import Dict

from .base import OcrBackend
from .exceptions import OcrBackendUnavailableError
from .models import OcrEngine

_BACKENDS: Dict[OcrEngine, OcrBackend] = {}


def register_backend(backend: OcrBackend) -> None:
    """Register or replace an OCR backend."""

    _BACKENDS[backend.engine] = backend


def get_backend(engine: OcrEngine | str) -> OcrBackend:
    """Return a registered backend by engine id."""

    try:
        engine_id = engine if isinstance(engine, OcrEngine) else OcrEngine(engine)
    except ValueError as exc:
        raise OcrBackendUnavailableError(f"Unknown OCR backend: {engine}") from exc

    try:
        return _BACKENDS[engine_id]
    except KeyError as exc:
        raise OcrBackendUnavailableError(f"OCR backend is not registered: {engine_id.value}") from exc


def list_backends() -> Dict[OcrEngine, OcrBackend]:
    """Return registered backends without importing optional runtimes."""

    return dict(_BACKENDS)


from .tesseract import TesseractBackend

register_backend(TesseractBackend())
