"""Resolve a compatibility result into a reviewable, isolated runtime plan."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Mapping

from .environment import default_ocr_data_root
from .metadata import load_compatibility_metadata
from .models import CompatibilityReport, CompatibilityStatus, RuntimeBackend, RuntimePlan


class EnvironmentResolver:
    """Create argv-only plans. It never executes commands or modifies the system."""

    def __init__(self, metadata: Mapping[str, Any] | None = None) -> None:
        self.metadata = dict(metadata or load_compatibility_metadata())

    def resolve(
        self,
        compatibility: CompatibilityReport,
        *,
        data_root: Path | None = None,
    ) -> RuntimePlan:
        root = (data_root or default_ocr_data_root()).expanduser().resolve()
        runtime_root = root / "runtimes" / "unlimited-ocr-transformers"
        environment_root = runtime_root / "environment"
        python = _runtime_python(environment_root)
        model_cache = root / "models"
        model_revision = str(self.metadata["model_revision"])
        model_id = str(self.metadata["model"])
        backend = self.metadata["backends"]["transformers"]
        profile_name = _profile_from_runtime(compatibility.recommended_runtime)
        environment_manager = _manager_from_runtime(compatibility.recommended_runtime)
        profile = backend["pytorch_profiles"].get(profile_name or "")
        blocked: list[str] = []
        if compatibility.status in {
            CompatibilityStatus.UNSUPPORTED,
            CompatibilityStatus.UNKNOWN,
        }:
            blocked.append(f"Compatibility status is {compatibility.status.value}.")
        if compatibility.recommended_backend != RuntimeBackend.TRANSFORMERS:
            blocked.append("No safe Transformers backend was selected.")
        if not profile:
            driver_is_incompatible = any(
                "NVIDIA Driver is missing, unknown, or too old" in reason
                for reason in compatibility.requirements_missing
            )
            blocked.append(
                "No official PyTorch CUDA wheel profile matches the detected Driver."
                if driver_is_incompatible
                else "The PyTorch CUDA wheel profile could not be resolved from the compatibility result."
            )
        if environment_manager not in {"uv", "conda"}:
            blocked.append("No supported private environment manager was selected.")

        packages = backend["packages"]
        torch_packages = (
            f"torch=={packages['torch']}",
            f"torchvision=={packages['torchvision']}",
        )
        runtime_packages = tuple(
            f"{name}=={version}"
            for name, version in packages.items()
            if name not in {"torch", "torchvision"}
        )
        commands: list[tuple[str, ...]] = []
        if environment_manager == "conda":
            python = _runtime_python(environment_root, environment_manager)
            commands.append(
                ("conda", "create", "--yes", "--prefix", str(environment_root), "python=3.12", "pip")
            )
            if profile:
                commands.append(
                    (
                        str(python),
                        "-m",
                        "pip",
                        "install",
                        "--index-url",
                        str(profile["index_url"]),
                        *torch_packages,
                    )
                )
            commands.append((str(python), "-m", "pip", "install", *runtime_packages))
        elif environment_manager == "uv":
            commands.append(("uv", "venv", str(environment_root), "--python", "3.12"))
            if profile:
                commands.append(
                    (
                        "uv",
                        "pip",
                        "install",
                        "--python",
                        str(python),
                        "--index-url",
                        str(profile["index_url"]),
                        *torch_packages,
                    )
                )
            commands.append(
                (
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    *runtime_packages,
                )
            )
        environment = {
            "HF_HOME": str(model_cache / "hf-home"),
            "HF_HUB_CACHE": str(model_cache / "hub"),
            "HF_MODULES_CACHE": str(model_cache / "modules"),
            "TRANSFORMERS_CACHE": str(model_cache / "transformers"),
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
            "PYTHONNOUSERSITE": "1",
        }
        plan_material = "\n".join(
            [model_revision, str(runtime_root), *(" ".join(command) for command in commands)]
        )
        plan_id = hashlib.sha256(plan_material.encode("utf-8")).hexdigest()[:16]
        warnings = [
            "The model repository contains custom Python code and will run only in the private worker environment.",
            "The existing system CUDA Toolkit is not removed, upgraded, or added to PATH.",
            "Driver changes are never part of this plan and require separate explicit user action.",
        ]
        warnings.extend(compatibility.conflicts)
        return RuntimePlan(
            plan_id=plan_id,
            backend=RuntimeBackend.TRANSFORMERS,
            runtime_root=str(runtime_root),
            python_version="3.12",
            environment_manager=environment_manager or "unresolved",
            package_index_url=str(profile["index_url"]) if profile else None,
            packages=(*torch_packages, *runtime_packages),
            model_id=model_id,
            model_revision=model_revision,
            model_cache_dir=str(model_cache),
            commands=tuple(commands),
            environment=environment,
            requires_admin=False,
            system_changes=(),
            reversible_changes=(
                f"Create private runtime under {runtime_root}",
                f"Create private model cache under {model_cache}",
                "Register provider settings in the APP user configuration",
            ),
            warnings=tuple(warnings),
            blocked_reasons=tuple(blocked),
        )


def _runtime_python(environment_root: Path, manager: str = "uv") -> Path:
    if os.name == "nt":
        if manager == "conda":
            return environment_root / "python.exe"
        return environment_root / "Scripts" / "python.exe"
    return environment_root / "bin" / "python"


def _profile_from_runtime(value: str | None) -> str | None:
    if not value:
        return None
    for profile in ("cu130", "cu128", "cu126"):
        if profile in value:
            return profile
    return None


def _manager_from_runtime(value: str | None) -> str | None:
    if not value:
        return None
    for manager in ("uv", "conda"):
        if f"private {manager} " in value.casefold():
            return manager
    return None
