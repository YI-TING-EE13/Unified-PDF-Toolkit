"""Environment diagnostics for support and release smoke checks."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
import tkinter as tk
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Iterable, List

from .file_ops import get_default_save_dir
from .settings import get_settings_path
from ..ocr.consent import load_advanced_ocr_consent
from ..ocr.local_endpoint import get_local_endpoint_url, validate_local_endpoint_url
from ..ocr.local_model import (
    LOCAL_MODEL_MODE_DISABLED,
    LOCAL_MODEL_MODE_FAKE_WORKER,
    LOCAL_MODEL_MODE_IN_PROCESS_FUTURE,
    LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LOCAL_MODEL_PROVIDER,
    LocalModelRuntimeConfig,
    load_local_model_runtime_config,
)
from ..ocr.model_policy import (
    allowed_model_ids_from_options,
    evaluate_unlimited_ocr_model_policy,
)


@dataclass
class DiagnosticCheck:
    name: str
    status: str
    detail: str
    suggestion: str = ""


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _module_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "unknown version"


def _optional_ai_ocr_checks() -> List[DiagnosticCheck]:
    checks: List[DiagnosticCheck] = [
        DiagnosticCheck(
            "Advanced OCR architecture",
            "info",
            "experimental local-only backend support; disabled by default and never used by Tesseract OCR",
        )
    ]

    torch_available = _module_available("torch")
    checks.append(
        DiagnosticCheck(
            "Advanced OCR torch",
            "info" if torch_available else "warning",
            f"available ({_module_version('torch')})" if torch_available else "not installed",
            "Optional only. Install torch only in a uv-managed OCR runtime for experimental local model testing."
            if not torch_available
            else "",
        )
    )

    transformers_available = _module_available("transformers")
    checks.append(
        DiagnosticCheck(
            "Advanced OCR transformers",
            "info" if transformers_available else "warning",
            f"available ({_module_version('transformers')})" if transformers_available else "not installed",
            "Optional only. Install transformers only in a uv-managed OCR runtime for experimental local model testing."
            if not transformers_available
            else "",
        )
    )

    if torch_available:
        checks.extend(_torch_readiness_checks())
    else:
        checks.append(DiagnosticCheck("Advanced OCR CUDA", "info", "not checked because torch is not installed"))

    checks.extend(_local_model_runtime_checks(load_local_model_runtime_config()))
    checks.extend(_huggingface_cache_checks())

    cache_path = _unlimited_ocr_cache_path()
    checks.append(
        DiagnosticCheck(
            "Advanced OCR model cache",
            "info",
            (
                "baidu/Unlimited-OCR local cache detected"
                if cache_path.exists()
                else "baidu/Unlimited-OCR cache not detected"
            ),
            "This check is local-only and does not download models.",
        )
    )
    endpoint_url = get_local_endpoint_url()
    try:
        validate_local_endpoint_url(endpoint_url)
        checks.append(
            DiagnosticCheck(
                "Advanced OCR local endpoint URL",
                "info",
                f"{endpoint_url} is localhost-only; reachability not checked automatically",
            )
        )
    except ValueError as exc:
        checks.append(
            DiagnosticCheck(
                "Advanced OCR local endpoint URL",
                "warning",
                f"{endpoint_url}: {exc}",
                "Use an http://127.0.0.1:<port>, http://localhost:<port>, or http://[::1]:<port> endpoint.",
            )
        )
    return checks


def _local_model_runtime_checks(config: LocalModelRuntimeConfig) -> List[DiagnosticCheck]:
    checks: List[DiagnosticCheck] = []
    if not config.enabled or config.mode == LOCAL_MODEL_MODE_DISABLED:
        return [
            DiagnosticCheck(
                "Advanced OCR local model runtime",
                "info",
                "disabled",
                "Enable only for experimental local Unlimited-OCR beta testing with a uv-managed runtime.",
            )
        ]

    checks.append(
        DiagnosticCheck(
            "Advanced OCR local model runtime",
            "warning",
            f"{config.mode} configured"
            if config.mode == LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR
            else f"{config.mode} configured",
            "Experimental local Unlimited-OCR requires optional runtime dependencies."
            if config.mode in (LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR, LOCAL_MODEL_MODE_WORKER_PROCESS)
            else "This configuration is for local runtime readiness only.",
        )
    )
    if config.mode != LOCAL_MODEL_MODE_FAKE_WORKER:
        checks.append(
            _path_readiness_check(
                "Advanced OCR local model path",
                config.model_path,
                expect_file=False,
            )
        )
        checks.extend(_local_model_policy_checks(config))
    if config.mode == LOCAL_MODEL_MODE_WORKER_PROCESS:
        checks.append(
            _path_readiness_check(
                "Advanced OCR worker Python",
                config.python_executable,
                expect_file=True,
            )
        )
        checks.append(_worker_python_runtime_hint(config.python_executable))
        checks.append(
            _path_readiness_check(
                "Advanced OCR worker script",
                config.worker_script_path,
                expect_file=True,
            )
        )
    elif config.mode == LOCAL_MODEL_MODE_FAKE_WORKER:
        checks.append(
            DiagnosticCheck(
                "Advanced OCR fake worker",
                "warning",
                "developer/test-only fake worker mode selected",
                "This mode returns deterministic fake OCR and does not run real inference.",
            )
        )
        if config.worker_script_path:
            checks.append(
                _path_readiness_check(
                    "Advanced OCR fake worker script",
                    config.worker_script_path,
                    expect_file=True,
                )
            )
    elif config.mode == LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR:
        checks.append(
            DiagnosticCheck(
                "Advanced OCR local Unlimited-OCR",
                "warning",
                f"experimental Transformers runtime selected; device={config.device_preference}",
                "Requires user-installed torch/transformers and a local model path.",
            )
        )
    elif config.mode == LOCAL_MODEL_MODE_IN_PROCESS_FUTURE:
        checks.append(
            DiagnosticCheck(
                "Advanced OCR in-process runtime",
                "warning",
                "selected for future review only; not implemented",
                "Use only after security and dependency review.",
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                "Advanced OCR local model mode",
                "warning",
                f"unsupported mode: {config.mode}",
            )
        )
    return checks


def _local_model_policy_checks(config: LocalModelRuntimeConfig) -> List[DiagnosticCheck]:
    status = evaluate_unlimited_ocr_model_policy(
        model_id=config.model_id,
        model_path=config.model_path,
        model_revision=config.model_revision,
        allowed_model_ids=allowed_model_ids_from_options(config.options),
    )
    checks = [
        DiagnosticCheck(
            "Advanced OCR model id policy",
            "info" if status.model_id_allowed else "warning",
            (
                f"{status.model_id} is allowed for controlled beta"
                if status.model_id_allowed
                else f"{status.model_id} is not in the beta allowed model id list"
            ),
            "Use baidu/Unlimited-OCR unless a maintainer has reviewed another local model id."
            if not status.model_id_allowed
            else "",
        ),
        DiagnosticCheck(
            "Advanced OCR model revision",
            "info" if status.revision_pinned else "warning",
            (
                f"{status.revision} ({status.revision_source})"
                if status.revision_pinned
                else "not pinned"
            ),
            "Record a model revision pin before broader beta use."
            if not status.revision_pinned
            else "",
        ),
        DiagnosticCheck(
            "Advanced OCR model metadata",
            "info" if status.metadata_present else "warning",
            _metadata_detail_for_diagnostics(status.metadata_detail, status.metadata_model_hint),
            "Choose a local Hugging Face model folder with config/tokenizer metadata."
            if status.metadata_present is False
            else "",
        ),
    ]
    consent = load_advanced_ocr_consent(
        provider=LOCAL_MODEL_PROVIDER,
        model_id=config.model_id,
    )
    checks.append(
        DiagnosticCheck(
            "Advanced OCR trust_remote_code consent",
            "info" if consent else "warning",
            "valid consent saved" if consent else "no valid consent saved for this model id",
            "Review and save Advanced Local AI OCR consent before running Experimental Local Unlimited-OCR."
            if not consent
            else "",
        )
    )
    return checks


def _metadata_detail_for_diagnostics(detail: str, hint: str | None) -> str:
    if not hint:
        return detail
    if ":" in hint or "/" in hint or "\\" in hint:
        return f"{detail}; metadata hint present"
    return f"{detail}; metadata hint: {hint}"


def _worker_python_runtime_hint(value: str | None) -> DiagnosticCheck:
    if not value:
        return DiagnosticCheck(
            "Advanced OCR worker runtime",
            "warning",
            "not configured",
            "Use a uv-managed optional OCR runtime such as .venv-ocr-runtime.",
        )
    normalized_parts = {part.lower() for part in Path(value).parts}
    looks_like_uv_runtime = ".venv-ocr-runtime" in normalized_parts
    return DiagnosticCheck(
        "Advanced OCR worker runtime",
        "info",
        "looks like .venv-ocr-runtime" if looks_like_uv_runtime else "custom worker Python configured",
        ""
        if looks_like_uv_runtime
        else "For beta validation, confirm this Python belongs to a uv-managed optional OCR runtime.",
    )


def _path_readiness_check(
    name: str,
    value: str | None,
    *,
    expect_file: bool,
) -> DiagnosticCheck:
    if not value:
        return DiagnosticCheck(name, "warning", "not configured")
    path = Path(value)
    exists = path.is_file() if expect_file else path.exists()
    return DiagnosticCheck(
        name,
        "info" if exists else "warning",
        "configured path exists" if exists else "configured path not found",
    )


def _torch_readiness_checks() -> List[DiagnosticCheck]:
    try:
        import torch
    except Exception as exc:
        return [
            DiagnosticCheck(
                "Advanced OCR torch import",
                "warning",
                f"torch installed but import failed: {exc}",
            )
        ]

    try:
        cuda_available = bool(torch.cuda.is_available())
    except Exception as exc:
        return [
            DiagnosticCheck(
                "Advanced OCR CUDA",
                "warning",
                f"CUDA readiness check failed: {exc}",
            )
        ]

    checks = [
        DiagnosticCheck(
            "Advanced OCR CUDA",
            "info" if cuda_available else "warning",
            "available" if cuda_available else "not available",
            "Experimental local Unlimited-OCR may need an NVIDIA CUDA wheel matching the driver plus enough VRAM."
            if not cuda_available
            else "",
        )
    ]
    if not cuda_available:
        return checks

    try:
        index = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(index)
        total_gb = props.total_memory / (1024**3)
        checks.append(
            DiagnosticCheck(
                "Advanced OCR GPU",
                "info",
                f"{props.name}, {total_gb:.1f} GB VRAM",
            )
        )
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                "Advanced OCR GPU",
                "warning",
                f"GPU details unavailable: {exc}",
            )
        )
    return checks


def _unlimited_ocr_cache_path() -> Path:
    base = os.environ.get("HF_HOME")
    if base:
        return Path(base) / "hub" / "models--baidu--Unlimited-OCR"
    return Path.home() / ".cache" / "huggingface" / "hub" / "models--baidu--Unlimited-OCR"


def _huggingface_cache_checks() -> List[DiagnosticCheck]:
    return [
        _env_directory_writable_check(
            "HF_HOME",
            "Hugging Face home/cache",
            "Set HF_HOME to a writable local folder before manual model cache/download work.",
        ),
        _env_directory_writable_check(
            "HF_MODULES_CACHE",
            "Hugging Face custom-code module cache",
            "Set HF_MODULES_CACHE to a writable local folder before running trust_remote_code models.",
        ),
    ]


def _tesseract_language_check(tesseract_path: str | None) -> DiagnosticCheck:
    if not tesseract_path:
        return DiagnosticCheck(
            "Tesseract languages",
            "info",
            "not checked because the executable was not found",
        )
    try:
        import pytesseract

        languages = sorted(set(pytesseract.get_languages(config="")))
    except Exception as exc:
        return DiagnosticCheck(
            "Tesseract languages",
            "warning",
            f"could not query installed language data ({exc.__class__.__name__})",
            "Check TESSDATA_PREFIX and the Tesseract installation, then run Diagnostics again.",
        )

    detail = ", ".join(languages) if languages else "none detected"
    if "eng" not in languages:
        return DiagnosticCheck(
            "Tesseract languages",
            "error",
            detail,
            "Install eng.traineddata because English is the default OCR language.",
        )
    if not {"chi_tra", "chi_sim"}.intersection(languages):
        return DiagnosticCheck(
            "Tesseract languages",
            "warning",
            detail,
            (
                "Chinese OCR is unavailable. Install chi_tra.traineddata and/or "
                "chi_sim.traineddata in Tesseract's tessdata folder."
            ),
        )
    return DiagnosticCheck("Tesseract languages", "ok", detail)


def _env_directory_writable_check(
    env_name: str,
    label: str,
    unset_suggestion: str,
) -> DiagnosticCheck:
    value = os.environ.get(env_name)
    if not value:
        return DiagnosticCheck(
            f"Advanced OCR {env_name}",
            "info",
            "not set",
            unset_suggestion,
        )
    path = Path(value)
    if not path.exists():
        return DiagnosticCheck(
            f"Advanced OCR {env_name}",
            "warning",
            f"{label} path is configured but not found",
            "Create the folder or choose an existing writable local folder.",
        )
    if not path.is_dir():
        return DiagnosticCheck(
            f"Advanced OCR {env_name}",
            "warning",
            f"{label} path is not a folder",
            "Choose a writable local folder.",
        )
    try:
        probe = path / ".pdf_toolkit_advanced_ocr_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError:
        return DiagnosticCheck(
            f"Advanced OCR {env_name}",
            "warning",
            f"{label} path is not writable",
            "Choose a writable local folder under your user profile or temp directory.",
        )
    return DiagnosticCheck(
        f"Advanced OCR {env_name}",
        "info",
        f"{label} path is writable",
    )


def collect_diagnostics() -> List[DiagnosticCheck]:
    """Collect dependency, runtime, OCR, and write-permission checks."""
    checks: List[DiagnosticCheck] = []
    checks.append(
        DiagnosticCheck(
            "Python",
            "ok" if sys.version_info >= (3, 10) else "error",
            platform.python_version(),
            "Install Python 3.10 or newer." if sys.version_info < (3, 10) else "",
        )
    )
    checks.append(DiagnosticCheck("Platform", "info", platform.platform()))

    try:
        root = tk.Tk()
        try:
            root.withdraw()
            tk_version = root.tk.call("info", "patchlevel")
        finally:
            root.destroy()
        checks.append(DiagnosticCheck("Tkinter", "ok", f"Tk {tk_version}"))
    except tk.TclError:
        checks.append(
            DiagnosticCheck(
                "Tkinter",
                "warning",
                "desktop Tk/Tcl runtime unavailable or misconfigured",
                "Run the GUI from a desktop session with an available display.",
            )
        )

    for module_name in (
        "fitz",
        "PIL",
        "pdf2docx",
        "docx",
        "tkinterdnd2",
        "pytesseract",
    ):
        available = _module_available(module_name)
        checks.append(
            DiagnosticCheck(
                module_name,
                "ok" if available else "error",
                "available" if available else "missing",
                "Run uv sync to install project dependencies."
                if not available
                else "",
            )
        )

    tesseract_path = shutil.which("tesseract")
    checks.append(
        DiagnosticCheck(
            "Tesseract executable",
            "ok" if tesseract_path else "warning",
            "found on PATH" if tesseract_path else "not found on PATH",
            "Install Tesseract OCR and add it to PATH before using OCR Text mode."
            if not tesseract_path
            else "",
        )
    )
    checks.append(_tesseract_language_check(tesseract_path))

    checks.extend(_optional_ai_ocr_checks())
    checks.append(_write_check("Default save folder", Path(get_default_save_dir("Diagnostics"))))
    checks.append(_write_check("Settings file folder", get_settings_path().parent))
    return checks


def _write_check(name: str, folder: Path) -> DiagnosticCheck:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".pdf_toolkit_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return DiagnosticCheck(name, "ok", "writable")
    except OSError:
        return DiagnosticCheck(
            name,
            "error",
            "not writable",
            "Choose an output folder under your user profile or fix folder permissions.",
        )


def diagnostics_to_text(checks: Iterable[DiagnosticCheck]) -> str:
    lines = ["Unified PDF Toolkit Diagnostics", ""]
    for check in checks:
        lines.append(f"[{check.status.upper()}] {check.name}: {check.detail}")
        if check.suggestion:
            lines.append(f"  Suggestion: {check.suggestion}")
    return "\n".join(lines) + "\n"
