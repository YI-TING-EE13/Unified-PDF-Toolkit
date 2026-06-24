"""Consent model for optional advanced local AI OCR."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from .exceptions import OcrConsentRequiredError
from ..utils.settings import get_setting, load_settings, save_settings, set_setting

ADVANCED_OCR_CONSENT_TEXT_VERSION = "2026-06-24"
ADVANCED_OCR_CONSENT_SETTING_KEY = "advanced_ocr.consent"
DEFAULT_ADVANCED_OCR_PROVIDER = "baidu"
DEFAULT_ADVANCED_OCR_MODEL_ID = "baidu/Unlimited-OCR"

REQUIRED_ACKNOWLEDGEMENT_KEYS = (
    "acknowledged_model_download_risk",
    "acknowledged_custom_code_risk",
    "acknowledged_gpu_vram_use",
    "acknowledged_temporary_page_images",
)


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


def create_advanced_ocr_consent(
    *,
    provider: str = DEFAULT_ADVANCED_OCR_PROVIDER,
    model_id: str = DEFAULT_ADVANCED_OCR_MODEL_ID,
    consent_text_version: str = ADVANCED_OCR_CONSENT_TEXT_VERSION,
    acknowledgements: Dict[str, bool],
) -> AdvancedOcrConsent | None:
    """Create consent only when every required acknowledgement is true."""

    if not all(bool(acknowledgements.get(key)) for key in REQUIRED_ACKNOWLEDGEMENT_KEYS):
        return None
    return AdvancedOcrConsent.create(
        provider=provider,
        model_id=model_id,
        consent_text_version=consent_text_version,
        acknowledged_model_download_risk=True,
        acknowledged_custom_code_risk=True,
        acknowledged_gpu_vram_use=True,
        acknowledged_temporary_page_images=True,
    )


def get_saved_advanced_ocr_consent() -> AdvancedOcrConsent | None:
    """Load the stored consent record without treating invalid records as valid."""

    value = get_setting(ADVANCED_OCR_CONSENT_SETTING_KEY)
    if not isinstance(value, dict):
        return None
    return AdvancedOcrConsent.from_dict(value)


def load_advanced_ocr_consent(
    *,
    provider: str = DEFAULT_ADVANCED_OCR_PROVIDER,
    model_id: str = DEFAULT_ADVANCED_OCR_MODEL_ID,
    consent_text_version: str = ADVANCED_OCR_CONSENT_TEXT_VERSION,
) -> AdvancedOcrConsent | None:
    """Load stored consent only when it matches the active provider/model/version."""

    consent = get_saved_advanced_ocr_consent()
    if consent and consent.is_valid_for(
        provider=provider,
        model_id=model_id,
        consent_text_version=consent_text_version,
    ):
        return consent
    return None


def save_advanced_ocr_consent(consent: AdvancedOcrConsent) -> None:
    """Persist consent using the repository's JSON settings file."""

    set_setting(ADVANCED_OCR_CONSENT_SETTING_KEY, consent.to_dict())


def clear_advanced_ocr_consent() -> None:
    """Remove advanced OCR consent from settings."""

    settings = load_settings()
    settings.pop(ADVANCED_OCR_CONSENT_SETTING_KEY, None)
    save_settings(settings)
