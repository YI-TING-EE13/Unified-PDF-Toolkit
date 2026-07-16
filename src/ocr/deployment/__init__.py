"""Safe deployment framework for optional local AI OCR providers."""

from .environment import EnvironmentInspector, default_ocr_data_root
from .models import (
    CompatibilityReport,
    CompatibilityStatus,
    EnvironmentReport,
    RiskLevel,
)

__all__ = [
    "CompatibilityReport",
    "CompatibilityStatus",
    "EnvironmentInspector",
    "EnvironmentReport",
    "RiskLevel",
    "default_ocr_data_root",
]
