"""OCR-specific exceptions."""


class OcrError(RuntimeError):
    """Base class for OCR backend failures."""


class OcrDependencyMissingError(OcrError):
    """Raised when an OCR backend dependency is unavailable."""


class OcrConsentRequiredError(OcrError):
    """Raised when an optional AI OCR backend lacks required consent."""


class OcrBackendUnavailableError(OcrError):
    """Raised when a requested OCR backend is unavailable or unregistered."""
