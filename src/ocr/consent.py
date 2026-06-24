"""Consent model for optional advanced local AI OCR."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from .exceptions import OcrConsentRequiredError

ADVANCED_OCR_CONSENT_TEXT_VERSION = "2026-06-24"


@dataclass(frozen=True)
class AdvancedOcrConsent:
    """User acknowledgements required before future real AI OCR use."""

    provider: str
    model_id: str
    consent_text_version: str
    acknowledged_model_download_risk: bool
    acknowledged_custom_code_risk: bool
    acknowledged_gpu_vram_use: bool
    acknowledged_temporary_page_images: bool
    timestamp_utc: str

    @classmethod
    def create(
        cls,
        *,
        provider: str,
        model_id: str,
        consent_text_version: str = ADVANCED_OCR_CONSENT_TEXT_VERSION,
        acknowledged_model_download_risk: bool,
        acknowledged_custom_code_risk: bool,
        acknowledged_gpu_vram_use: bool,
        acknowledged_temporary_page_images: bool,
    ) -> "AdvancedOcrConsent":
        return cls(
            provider=provider,
            model_id=model_id,
            consent_text_version=consent_text_version,
            acknowledged_model_download_risk=acknowledged_model_download_risk,
            acknowledged_custom_code_risk=acknowledged_custom_code_risk,
            acknowledged_gpu_vram_use=acknowledged_gpu_vram_use,
            acknowledged_temporary_page_images=acknowledged_temporary_page_images,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
        )

    def is_valid_for(
        self,
        *,
        provider: str,
        model_id: str,
        consent_text_version: str = ADVANCED_OCR_CONSENT_TEXT_VERSION,
    ) -> bool:
        return (
            self.provider == provider
            and self.model_id == model_id
            and self.consent_text_version == consent_text_version
            and self.acknowledged_model_download_risk
            and self.acknowledged_custom_code_risk
            and self.acknowledged_gpu_vram_use
            and self.acknowledged_temporary_page_images
            and bool(self.timestamp_utc)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON/settings-compatible representation."""

        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "consent_text_version": self.consent_text_version,
            "acknowledged_model_download_risk": self.acknowledged_model_download_risk,
            "acknowledged_custom_code_risk": self.acknowledged_custom_code_risk,
            "acknowledged_gpu_vram_use": self.acknowledged_gpu_vram_use,
            "acknowledged_temporary_page_images": self.acknowledged_temporary_page_images,
            "timestamp_utc": self.timestamp_utc,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdvancedOcrConsent":
        """Load a consent record from settings-style JSON data."""

        return cls(
            provider=str(data.get("provider", "")),
            model_id=str(data.get("model_id", "")),
            consent_text_version=str(data.get("consent_text_version", "")),
            acknowledged_model_download_risk=bool(data.get("acknowledged_model_download_risk")),
            acknowledged_custom_code_risk=bool(data.get("acknowledged_custom_code_risk")),
            acknowledged_gpu_vram_use=bool(data.get("acknowledged_gpu_vram_use")),
            acknowledged_temporary_page_images=bool(data.get("acknowledged_temporary_page_images")),
            timestamp_utc=str(data.get("timestamp_utc", "")),
        )


def require_valid_consent(
    consent: AdvancedOcrConsent | None,
    *,
    provider: str,
    model_id: str,
    consent_text_version: str = ADVANCED_OCR_CONSENT_TEXT_VERSION,
) -> None:
    """Raise if consent is missing or no longer matches the active backend."""

    if consent is None or not consent.is_valid_for(
        provider=provider,
        model_id=model_id,
        consent_text_version=consent_text_version,
    ):
        raise OcrConsentRequiredError(
            "Advanced local AI OCR requires explicit consent for this provider, "
            "model, and consent text version."
        )
