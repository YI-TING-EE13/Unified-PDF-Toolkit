"""User-owned local AI OCR model backend scaffold.

This module intentionally does not import torch, transformers, SGLang, CUDA
helpers, or model code. It defines the future local model backend boundary and
fails with clear runtime/model-not-configured errors until a reviewed runtime is
implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .consent import (
    ADVANCED_OCR_CONSENT_TEXT_VERSION,
    AdvancedOcrConsent,
    require_valid_consent,
)
from .exceptions import OcrBackendUnavailableError
from .models import OcrEngine, OcrRequest, OcrResult

LOCAL_MODEL_PROVIDER = "baidu"
LOCAL_MODEL_MODEL_ID = "baidu/Unlimited-OCR"


@dataclass(frozen=True)
class LocalModelRuntimeConfig:
    """Future local model runtime configuration.

    `mode` is intentionally descriptive only for this scaffold. Supported
    future values are expected to be `worker_process` or `in_process` after a
    security review. `runtime_path` and `model_path` are user-managed local
    paths and must not trigger downloads.
    """

    mode: str = "worker_process"
    runtime_path: str | None = None
    model_path: str | None = None
    options: Mapping[str, str] | None = None


class LocalModelOcrBackend:
    """Scaffold for future user-owned local Unlimited-OCR-compatible runtime."""

    engine = OcrEngine.LOCAL_MODEL
    display_name = "Local AI OCR Model"

    def __init__(
        self,
        *,
        consent: AdvancedOcrConsent | None = None,
        config: LocalModelRuntimeConfig | None = None,
    ) -> None:
        self.consent = consent
        self.config = config or LocalModelRuntimeConfig()

    def recognize(self, request_data: OcrRequest) -> OcrResult:
        """Validate consent, then report that runtime integration is pending."""

        require_valid_consent(
            self.consent,
            provider=LOCAL_MODEL_PROVIDER,
            model_id=LOCAL_MODEL_MODEL_ID,
            consent_text_version=ADVANCED_OCR_CONSENT_TEXT_VERSION,
        )
        self._validate_runtime_config()
        raise OcrBackendUnavailableError(
            "Local AI OCR model runtime is not installed or configured."
        )

    def _validate_runtime_config(self) -> None:
        if self.config.mode not in {"worker_process", "in_process"}:
            raise OcrBackendUnavailableError(
                "Local AI OCR model runtime mode is unsupported."
            )
        if not self.config.runtime_path:
            raise OcrBackendUnavailableError(
                "Local AI OCR model runtime is not installed or configured."
            )
        if not self.config.model_path:
            raise OcrBackendUnavailableError(
                "Local AI OCR model path is not configured."
            )
