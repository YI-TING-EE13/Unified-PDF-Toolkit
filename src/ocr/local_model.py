"""User-owned local AI OCR model backend scaffold.

This module intentionally does not import torch, transformers, SGLang, CUDA
helpers, or model code. It defines the future local model backend boundary and
allows explicit fake, direct local Unlimited-OCR, and worker-process runtime
paths only when configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from .consent import (
    ADVANCED_OCR_CONSENT_TEXT_VERSION,
    AdvancedOcrConsent,
    require_valid_consent,
)
from .exceptions import OcrBackendUnavailableError
from .local_worker import (
    default_fake_worker_script_path,
    default_unlimited_ocr_worker_script_path,
    run_local_model_worker_process,
    run_unlimited_ocr_worker_process,
)
from .model_policy import MODEL_REVISION_OPTION_KEY
from .unlimited_ocr_local import run_unlimited_ocr_local
from .models import OcrEngine, OcrRequest, OcrResult
from ..utils.settings import get_setting, load_settings, save_settings, set_setting

LOCAL_MODEL_PROVIDER = "baidu"
LOCAL_MODEL_MODEL_ID = "baidu/Unlimited-OCR"
LOCAL_MODEL_RUNTIME_SETTING_KEY = "advanced_ocr.local_model_runtime"
LOCAL_MODEL_MODE_DISABLED = "disabled"
LOCAL_MODEL_MODE_FAKE_WORKER = "fake_worker"
LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR = "local_unlimited_ocr"
LOCAL_MODEL_MODE_WORKER_PROCESS = "worker_process"
LOCAL_MODEL_MODE_IN_PROCESS_FUTURE = "in_process_future"
LOCAL_MODEL_DEVICE_AUTO = "auto"
LOCAL_MODEL_DEVICE_CUDA = "cuda"
LOCAL_MODEL_DEVICE_CPU = "cpu"
LOCAL_MODEL_RUNTIME_MODES = (
    LOCAL_MODEL_MODE_DISABLED,
    LOCAL_MODEL_MODE_FAKE_WORKER,
    LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LOCAL_MODEL_MODE_IN_PROCESS_FUTURE,
)
LOCAL_MODEL_DEVICE_PREFERENCES = (
    LOCAL_MODEL_DEVICE_AUTO,
    LOCAL_MODEL_DEVICE_CUDA,
    LOCAL_MODEL_DEVICE_CPU,
)
LOCAL_MODEL_CANCELLATION_CHECK_OPTION = "_cancellation_check"


@dataclass(frozen=True)
class LocalModelRuntimeConfig:
    """Future local model runtime configuration.

    The default is disabled. Paths are user-managed local runtime hints and
    must not trigger downloads.
    """

    enabled: bool = False
    mode: str = LOCAL_MODEL_MODE_DISABLED
    model_id: str = LOCAL_MODEL_MODEL_ID
    model_revision: str | None = None
    model_path: str | None = None
    python_executable: str | None = None
    worker_script_path: str | None = None
    device_preference: str = LOCAL_MODEL_DEVICE_AUTO
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
            model_revision=(
                _clean_optional_text(data.get("model_revision"))
                or _clean_optional_text((safe_options or {}).get(MODEL_REVISION_OPTION_KEY))
            ),
            model_path=_clean_optional_text(data.get("model_path")),
            python_executable=_clean_optional_text(data.get("python_executable")),
            worker_script_path=_clean_optional_text(data.get("worker_script_path")),
            device_preference=_clean_device_preference(data.get("device_preference")),
            options=safe_options,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return only settings-safe runtime configuration fields."""

        return {
            "enabled": bool(self.enabled),
            "mode": self.mode if self.mode in LOCAL_MODEL_RUNTIME_MODES else LOCAL_MODEL_MODE_DISABLED,
            "model_id": self.model_id or LOCAL_MODEL_MODEL_ID,
            "model_revision": self.model_revision or "",
            "model_path": self.model_path or "",
            "python_executable": self.python_executable or "",
            "worker_script_path": self.worker_script_path or "",
            "device_preference": (
                self.device_preference
                if self.device_preference in LOCAL_MODEL_DEVICE_PREFERENCES
                else LOCAL_MODEL_DEVICE_AUTO
            ),
            "options": dict(self.options or {}),
        }


def _clean_optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _clean_device_preference(value: Any) -> str:
    text = str(value).strip().lower() if value is not None else ""
    return text if text in LOCAL_MODEL_DEVICE_PREFERENCES else LOCAL_MODEL_DEVICE_AUTO


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
        """Validate consent, then run only explicitly configured local paths."""

        require_valid_consent(
            self.consent,
            provider=LOCAL_MODEL_PROVIDER,
            model_id=LOCAL_MODEL_MODEL_ID,
            consent_text_version=ADVANCED_OCR_CONSENT_TEXT_VERSION,
        )
        if self.config.mode == LOCAL_MODEL_MODE_FAKE_WORKER:
            self._validate_fake_worker_config()
            return run_local_model_worker_process(
                request_data,
                model_id=self.config.model_id or LOCAL_MODEL_MODEL_ID,
                runtime_mode=LOCAL_MODEL_MODE_FAKE_WORKER,
                python_executable=self.config.python_executable,
                worker_script_path=(
                    self.config.worker_script_path or default_fake_worker_script_path()
                ),
                timeout_seconds=_float_option(
                    self.config.options, "timeout_seconds", default=10.0
                ),
                options=self.config.options,
                cancellation_check=_request_cancellation_check(request_data),
            )
        if self.config.mode == LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR:
            self._validate_local_unlimited_ocr_config()
            return run_unlimited_ocr_local(request_data, config=self.config)
        if self.config.mode == LOCAL_MODEL_MODE_WORKER_PROCESS:
            self._validate_worker_process_config()
            return run_unlimited_ocr_worker_process(
                request_data,
                model_id=self.config.model_id or LOCAL_MODEL_MODEL_ID,
                model_path=self.config.model_path or "",
                runtime_mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
                device_preference=self.config.device_preference,
                python_executable=self.config.python_executable,
                worker_script_path=(
                    self.config.worker_script_path
                    or default_unlimited_ocr_worker_script_path()
                ),
                timeout_seconds=_float_option(
                    self.config.options, "timeout_seconds", default=120.0
                ),
                options=self.config.options,
                cancellation_check=_request_cancellation_check(request_data),
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
        if self.config.mode == LOCAL_MODEL_MODE_FAKE_WORKER:
            self._validate_fake_worker_config()
            return
        if self.config.mode == LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR:
            self._validate_local_unlimited_ocr_config()
            return
        if self.config.mode == LOCAL_MODEL_MODE_WORKER_PROCESS:
            self._validate_worker_process_config()
            return
        if not self.config.model_path:
            raise OcrBackendUnavailableError(
                "Local AI OCR model path is not configured."
            )
        if self.config.mode == LOCAL_MODEL_MODE_IN_PROCESS_FUTURE:
            raise OcrBackendUnavailableError(
                "Local AI OCR in-process runtime is not implemented."
            )
        if self.config.mode == LOCAL_MODEL_MODE_WORKER_PROCESS:
            self._validate_worker_process_config()
            return

    def _validate_local_unlimited_ocr_config(self) -> None:
        if not self.config.enabled:
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR runtime is disabled."
            )
        if not self.config.model_path:
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR model path is not configured."
            )

    def _validate_fake_worker_config(self) -> None:
        if not self.config.enabled:
            raise OcrBackendUnavailableError(
                "Local AI OCR fake worker runtime is disabled."
            )
        if not self.config.worker_script_path and not default_fake_worker_script_path():
            raise OcrBackendUnavailableError(
                "Local AI OCR fake worker script path is not configured."
            )

    def _validate_worker_process_config(self) -> None:
        if not self.config.enabled:
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR worker runtime is disabled."
            )
        if not self.config.model_path:
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR model path is not configured."
            )
        if not self.config.python_executable:
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR worker Python executable is not configured."
            )
        if not Path(self.config.model_path).exists():
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR model path was not found."
            )
        if not Path(self.config.python_executable).exists():
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR worker Python executable was not found."
            )


def _float_option(
    options: Mapping[str, str] | None,
    key: str,
    *,
    default: float,
) -> float:
    if not options or key not in options:
        return default
    try:
        return float(options[key])
    except (TypeError, ValueError):
        return default


def _request_cancellation_check(
    request_data: OcrRequest,
) -> Callable[[], bool] | None:
    callback = request_data.options.get(LOCAL_MODEL_CANCELLATION_CHECK_OPTION)
    return callback if callable(callback) else None
