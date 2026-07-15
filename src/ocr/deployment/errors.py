"""Structured, user-safe deployment errors and classification."""

from __future__ import annotations

import errno
from enum import Enum
from typing import Any, Mapping

from .models import DeploymentError


class ErrorCode(str, Enum):
    NO_SUPPORTED_GPU = "NO_SUPPORTED_GPU"
    INSUFFICIENT_VRAM = "INSUFFICIENT_VRAM"
    INSUFFICIENT_RAM = "INSUFFICIENT_RAM"
    INSUFFICIENT_DISK = "INSUFFICIENT_DISK"
    NVIDIA_DRIVER_MISSING = "NVIDIA_DRIVER_MISSING"
    NVIDIA_DRIVER_TOO_OLD = "NVIDIA_DRIVER_TOO_OLD"
    CUDA_RUNTIME_MISMATCH = "CUDA_RUNTIME_MISMATCH"
    PYTORCH_CUDA_MISMATCH = "PYTORCH_CUDA_MISMATCH"
    PYTHON_VERSION_UNSUPPORTED = "PYTHON_VERSION_UNSUPPORTED"
    UV_BOOTSTRAP_FAILED = "UV_BOOTSTRAP_FAILED"
    DEPENDENCY_CONFLICT = "DEPENDENCY_CONFLICT"
    MODEL_DOWNLOAD_FAILED = "MODEL_DOWNLOAD_FAILED"
    MODEL_INTEGRITY_FAILED = "MODEL_INTEGRITY_FAILED"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    CUDA_OOM = "CUDA_OOM"
    RAM_OOM = "RAM_OOM"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NETWORK_ERROR = "NETWORK_ERROR"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    PLAN_CHANGED = "PLAN_CHANGED"
    SETUP_ALREADY_RUNNING = "SETUP_ALREADY_RUNNING"
    SUBPROCESS_CRASH = "SUBPROCESS_CRASH"
    CANCELLED = "CANCELLED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


_MESSAGES: dict[ErrorCode, tuple[str, str, bool, bool, bool]] = {
    ErrorCode.NO_SUPPORTED_GPU: ("No supported GPU", "A supported NVIDIA GPU was not found.", False, False, False),
    ErrorCode.INSUFFICIENT_VRAM: ("Insufficient GPU memory", "The selected GPU does not have enough VRAM for the safe setup profile.", False, False, False),
    ErrorCode.INSUFFICIENT_RAM: ("Insufficient system memory", "The computer does not have enough RAM for the safe setup profile.", False, False, False),
    ErrorCode.INSUFFICIENT_DISK: ("Insufficient disk space", "Free space is below the amount reserved for the runtime and model.", True, False, True),
    ErrorCode.NVIDIA_DRIVER_MISSING: ("NVIDIA Driver not found", "Install an NVIDIA Driver before using this provider.", False, True, False),
    ErrorCode.NVIDIA_DRIVER_TOO_OLD: ("NVIDIA Driver is too old", "A newer Driver is required for the selected PyTorch CUDA runtime.", False, True, False),
    ErrorCode.CUDA_RUNTIME_MISMATCH: ("CUDA runtime mismatch", "The private runtime and Driver could not initialize a compatible CUDA path.", True, False, True),
    ErrorCode.PYTORCH_CUDA_MISMATCH: ("PyTorch CUDA mismatch", "PyTorch was installed but cannot use the detected GPU.", True, False, True),
    ErrorCode.PYTHON_VERSION_UNSUPPORTED: ("Unsupported Python", "A private supported Python version could not be created.", True, False, True),
    ErrorCode.UV_BOOTSTRAP_FAILED: ("uv bootstrap failed", "The verified private uv prerequisite could not be installed.", True, False, True),
    ErrorCode.DEPENDENCY_CONFLICT: ("Dependency conflict", "The pinned private runtime dependencies could not be resolved together.", True, False, True),
    ErrorCode.MODEL_DOWNLOAD_FAILED: ("Model download failed", "The model download did not complete. Partial verified cache data is kept for resume.", True, False, True),
    ErrorCode.MODEL_INTEGRITY_FAILED: ("Model verification failed", "Downloaded model files do not match the pinned metadata.", True, False, True),
    ErrorCode.MODEL_LOAD_FAILED: ("Model load failed", "The pinned model could not be loaded in the private worker.", True, False, True),
    ErrorCode.CUDA_OOM: ("GPU memory exhausted", "The model or input exceeded available GPU memory.", True, False, True),
    ErrorCode.RAM_OOM: ("System memory exhausted", "The model or input exceeded available system memory.", True, False, True),
    ErrorCode.INFERENCE_FAILED: ("OCR inference failed", "The model loaded, but OCR could not finish for the test input.", True, False, True),
    ErrorCode.PERMISSION_DENIED: ("Permission denied", "The APP cannot write to its private OCR data folder.", True, False, True),
    ErrorCode.NETWORK_ERROR: ("Network error", "The trusted model or package source could not be reached.", True, False, True),
    ErrorCode.CONSENT_REQUIRED: ("Consent required", "Installation cannot start until all required facts are acknowledged.", False, False, True),
    ErrorCode.PLAN_CHANGED: ("Installation plan changed", "Hardware, metadata, or commands changed after consent. Review the new plan.", False, False, True),
    ErrorCode.SETUP_ALREADY_RUNNING: ("Setup already running", "Another managed Unlimited-OCR setup is already active.", False, False, True),
    ErrorCode.SUBPROCESS_CRASH: ("Setup process stopped", "A private setup or worker process exited unexpectedly.", True, False, True),
    ErrorCode.CANCELLED: ("Setup cancelled", "Setup stopped safely. Completed cache data is retained for resume.", True, False, True),
    ErrorCode.UNKNOWN_ERROR: ("Unexpected setup error", "Setup stopped without modifying system-wide Python, CUDA, or PATH.", False, False, True),
}


class DeploymentFailure(RuntimeError):
    def __init__(self, error: DeploymentError) -> None:
        super().__init__(error.user_message)
        self.error = error


def make_error(
    code: ErrorCode,
    *,
    technical_details: str = "",
    detected_state: Mapping[str, Any] | None = None,
    expected_state: Mapping[str, Any] | None = None,
) -> DeploymentError:
    title, message, automatic, admin, retry = _MESSAGES[code]
    return DeploymentError(
        error_code=code.value,
        title=title,
        user_message=message,
        technical_details=technical_details,
        detected_state=dict(detected_state or {}),
        expected_state=dict(expected_state or {}),
        automatic_fix_available=automatic,
        requires_admin=admin,
        safe_to_retry=retry,
    )


def classify_exception(exc: BaseException, *, default: ErrorCode = ErrorCode.UNKNOWN_ERROR) -> DeploymentError:
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.casefold()
    if isinstance(exc, PermissionError) or (
        isinstance(exc, OSError) and exc.errno in {errno.EACCES, errno.EPERM}
    ):
        code = ErrorCode.PERMISSION_DENIED
    elif isinstance(exc, OSError) and exc.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)}:
        code = ErrorCode.INSUFFICIENT_DISK
    elif "cuda out of memory" in lowered or "cuda oom" in lowered:
        code = ErrorCode.CUDA_OOM
    elif "out of memory" in lowered or "memoryerror" in lowered:
        code = ErrorCode.RAM_OOM
    elif any(token in lowered for token in ("connection", "timed out", "dns", "network")):
        code = ErrorCode.NETWORK_ERROR
    else:
        code = default
    return make_error(code, technical_details=text)
