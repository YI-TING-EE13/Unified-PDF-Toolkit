"""User-owned local AI OCR model backend scaffold.

This module intentionally does not import torch, transformers, SGLang, CUDA
helpers, or model code. It defines the future local model backend boundary and
fails with clear runtime/model-not-configured errors until a reviewed runtime is
implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from .consent import (
    ADVANCED_OCR_CONSENT_TEXT_VERSION,
    AdvancedOcrConsent,
    require_valid_consent,
)
from .exceptions import OcrBackendUnavailableError
from .models import OcrEngine, OcrRequest, OcrResult
from ..utils.settings import get_setting, load_settings, save_settings, set_setting

LOCAL_MODEL_PROVIDER = "baidu"
LOCAL_MODEL_MODEL_ID = "baidu/Unlimited-OCR"
LOCAL_MODEL_RUNTIME_SETTING_KEY = "advanced_ocr.local_model_runtime"
LOCAL_MODEL_MODE_DISABLED = "disabled"
LOCAL_MODEL_MODE_WORKER_PROCESS = "worker_process"
LOCAL_MODEL_MODE_IN_PROCESS_FUTURE = "in_process_future"
LOCAL_MODEL_RUNTIME_MODES = (
    LOCAL_MODEL_MODE_DISABLED,
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LOCAL_MODEL_MODE_IN_PROCESS_FUTURE,
)


@dataclass(frozen=True)
class LocalModelRuntimeConfig:
    """Future local model runtime configuration.

    The default is disabled. Paths are user-managed local runtime hints and
    must not trigger downloads or worker execution in this scaffold.
    """

    enabled: bool = False
    mode: str = LOCAL_MODEL_MODE_DISABLED
    model_id: str = LOCAL_MODEL_MODEL_ID
    model_path: str | None = None
    python_executable: str | None = None
    worker_script_path: str | None = None
    options: Mapping[str, str] | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LocalModelRuntimeConfig":
        """Load a settings-safe config record."""

        mode = str(data.get("mode", LOCAL_MODEL_MODE_DISABLED)).strip()
        if mode not in LOCAL_MODEL_RUNTIME_MODES:
            mode = LOCAL_MODEL_MODE_DISABLED
        enabled = bool(data.get("enabled")) and mode != LOCAL_MODEL_MODE_DISABLED
        options = data.get("options")
        safe_options = (
            {str(key): str(value) for key, value in options.items()}
            if isinstance(options, Mapping)
            else None
        )
        return cls(
            enabled=enabled,
            mode=mode,
            model_id=_clean_optional_text(data.get("model_id")) or LOCAL_MODEL_MODEL_ID,
            model_path=_clean_optional_text(data.get("model_path")),
            python_executable=_clean_optional_text(data.get("python_executable")),
            worker_script_path=_clean_optional_text(data.get("worker_script_path")),
            options=safe_options,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return only settings-safe runtime configuration fields."""

        return {
            "enabled": bool(self.enabled),
            "mode": self.mode if self.mode in LOCAL_MODEL_RUNTIME_MODES else LOCAL_MODEL_MODE_DISABLED,
            "model_id": self.model_id or LOCAL_MODEL_MODEL_ID,
            "model_path": self.model_path or "",
            "python_executable": self.python_executable or "",
            "worker_script_path": self.worker_script_path or "",
            "options": dict(self.options or {}),
        }


def _clean_optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def load_local_model_runtime_config() -> LocalModelRuntimeConfig:
    """Load future local model runtime settings, defaulting to disabled."""

    value = get_setting(LOCAL_MODEL_RUNTIME_SETTING_KEY, {})
    if not isinstance(value, Mapping):
        return LocalModelRuntimeConfig()
    return LocalModelRuntimeConfig.from_dict(value)


def save_local_model_runtime_config(config: LocalModelRuntimeConfig) -> None:
    """Persist only safe local model runtime configuration fields."""

    set_setting(LOCAL_MODEL_RUNTIME_SETTING_KEY, config.to_dict())


def clear_local_model_runtime_config() -> None:
    """Remove local model runtime settings."""

    settings = load_settings()
    settings.pop(LOCAL_MODEL_RUNTIME_SETTING_KEY, None)
    save_settings(settings)


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
        self.config = config or load_local_model_runtime_config()

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
        if not self.config.enabled or self.config.mode == LOCAL_MODEL_MODE_DISABLED:
            raise OcrBackendUnavailableError(
                "Local AI OCR model runtime is disabled."
            )
        if self.config.mode not in LOCAL_MODEL_RUNTIME_MODES:
            raise OcrBackendUnavailableError(
                "Local AI OCR model runtime mode is unsupported."
            )
        if not self.config.model_path:
            raise OcrBackendUnavailableError(
                "Local AI OCR model path is not configured."
            )
        if self.config.mode == LOCAL_MODEL_MODE_IN_PROCESS_FUTURE:
            raise OcrBackendUnavailableError(
                "Local AI OCR in-process runtime is not implemented."
            )
        if self.config.mode == LOCAL_MODEL_MODE_WORKER_PROCESS:
            if not self.config.python_executable:
                raise OcrBackendUnavailableError(
                    "Local AI OCR worker Python executable is not configured."
                )
            if not self.config.worker_script_path:
                raise OcrBackendUnavailableError(
                    "Local AI OCR worker script path is not configured."
                )
            raise OcrBackendUnavailableError(
                "Local AI OCR worker process execution is not implemented."
            )
