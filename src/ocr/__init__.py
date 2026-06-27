"""OCR backend abstractions for local-first text extraction."""

from .exceptions import (
    OcrBackendUnavailableError,
    OcrConsentRequiredError,
    OcrDependencyMissingError,
    OcrError,
)
from .local_endpoint import LocalEndpointOcrBackend
from .local_model import (
    LOCAL_MODEL_DEVICE_AUTO,
    LOCAL_MODEL_DEVICE_CPU,
    LOCAL_MODEL_DEVICE_CUDA,
    LOCAL_MODEL_MODE_FAKE_WORKER,
    LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
    LocalModelOcrBackend,
    LocalModelRuntimeConfig,
    clear_local_model_runtime_config,
    load_local_model_runtime_config,
    save_local_model_runtime_config,
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
    "LocalEndpointOcrBackend",
    "LOCAL_MODEL_DEVICE_AUTO",
    "LOCAL_MODEL_DEVICE_CPU",
    "LOCAL_MODEL_DEVICE_CUDA",
    "LOCAL_MODEL_MODE_FAKE_WORKER",
    "LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR",
    "LocalModelOcrBackend",
    "LocalModelRuntimeConfig",
    "clear_local_model_runtime_config",
    "load_local_model_runtime_config",
    "save_local_model_runtime_config",
    "get_backend",
    "list_backends",
    "register_backend",
]
