"""Environment diagnostics for support and release smoke checks."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from .file_ops import get_default_save_dir
from .settings import get_settings_path
from ..ocr.local_endpoint import get_local_endpoint_url, validate_local_endpoint_url
from ..ocr.local_model import (
    LOCAL_MODEL_MODE_DISABLED,
    LOCAL_MODEL_MODE_IN_PROCESS_FUTURE,
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LocalModelRuntimeConfig,
    load_local_model_runtime_config,
)


@dataclass
class DiagnosticCheck:
    name: str
    status: str
    detail: str
    suggestion: str = ""


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _optional_ai_ocr_checks() -> List[DiagnosticCheck]:
    checks: List[DiagnosticCheck] = [
        DiagnosticCheck(
            "Advanced OCR architecture",
            "info",
            "experimental optional backend wiring only; real Unlimited-OCR inference is not enabled",
        )
    ]

    torch_available = _module_available("torch")
    checks.append(
        DiagnosticCheck(
            "Advanced OCR torch",
            "info" if torch_available else "warning",
            "available" if torch_available else "not installed",
            "Optional only. Do not install torch unless you are testing a future local AI OCR runtime."
            if not torch_available
            else "",
        )
    )

    transformers_available = _module_available("transformers")
    checks.append(
        DiagnosticCheck(
            "Advanced OCR transformers",
            "info" if transformers_available else "warning",
            "available" if transformers_available else "not installed",
            "Optional only. Real Unlimited-OCR inference is not part of the default install."
            if not transformers_available
            else "",
        )
    )

    if torch_available:
        checks.extend(_torch_readiness_checks())
    else:
        checks.append(DiagnosticCheck("Advanced OCR CUDA", "info", "not checked because torch is not installed"))

    checks.extend(_local_model_runtime_checks(load_local_model_runtime_config()))

    cache_path = _unlimited_ocr_cache_path()
    checks.append(
        DiagnosticCheck(
            "Advanced OCR model cache",
            "info",
            f"found at {cache_path}" if cache_path.exists() else "baidu/Unlimited-OCR cache not detected",
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
                "Enable only after installing a reviewed local model runtime. Real inference is not implemented yet.",
            )
        ]

    checks.append(
        DiagnosticCheck(
            "Advanced OCR local model runtime",
            "warning",
            f"{config.mode} configured; real inference is not implemented yet",
            "This configuration is for future local runtime readiness only.",
        )
    )
    checks.append(
        _path_readiness_check(
            "Advanced OCR local model path",
            config.model_path,
            expect_file=False,
        )
    )
    if config.mode == LOCAL_MODEL_MODE_WORKER_PROCESS:
        checks.append(
            _path_readiness_check(
                "Advanced OCR worker Python",
                config.python_executable,
                expect_file=True,
            )
        )
        checks.append(
            _path_readiness_check(
                "Advanced OCR worker script",
                config.worker_script_path,
                expect_file=True,
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
        f"{path} exists" if exists else f"{path} not found",
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
            "Future real AI OCR may need an NVIDIA GPU with enough VRAM."
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
    except tk.TclError as exc:
        checks.append(
            DiagnosticCheck(
                "Tkinter",
                "warning",
                str(exc),
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
            tesseract_path or "not found on PATH",
            "Install Tesseract OCR and add it to PATH before using OCR Text mode."
            if not tesseract_path
            else "",
        )
    )

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
        return DiagnosticCheck(name, "ok", str(folder))
    except OSError as exc:
        return DiagnosticCheck(
            name,
            "error",
            f"{folder}: {exc}",
            "Choose an output folder under your user profile or fix folder permissions.",
        )


def diagnostics_to_text(checks: Iterable[DiagnosticCheck]) -> str:
    lines = ["Unified PDF Toolkit Diagnostics", ""]
    for check in checks:
        lines.append(f"[{check.status.upper()}] {check.name}: {check.detail}")
        if check.suggestion:
            lines.append(f"  Suggestion: {check.suggestion}")
    return "\n".join(lines) + "\n"
