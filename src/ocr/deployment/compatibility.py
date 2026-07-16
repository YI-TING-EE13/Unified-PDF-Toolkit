"""Metadata-driven compatibility evaluation for Unlimited-OCR."""

from __future__ import annotations

from typing import Any, Mapping

from .metadata import load_compatibility_metadata, metadata_age_days
from .models import (
    CompatibilityReport,
    CompatibilityStatus,
    EnvironmentReport,
    RiskLevel,
    RuntimeBackend,
)


class CompatibilityEngine:
    """Evaluate support conservatively; unknown evidence never becomes supported."""

    def __init__(self, metadata: Mapping[str, Any] | None = None) -> None:
        self.metadata = dict(metadata or load_compatibility_metadata())

    def evaluate(self, report: EnvironmentReport | Mapping[str, Any]) -> CompatibilityReport:
        env = report.to_dict() if isinstance(report, EnvironmentReport) else dict(report)
        met: list[str] = []
        missing: list[str] = []
        changes: list[str] = []
        reasons: list[str] = []
        conflicts = list(self.metadata.get("known_conflicts", []))
        status = CompatibilityStatus.SUPPORTED
        confidence = 0.96

        os_name = str(env.get("os", {}).get("system", ""))
        architecture = str(env.get("os", {}).get("machine", ""))
        is_wsl = bool(env.get("os", {}).get("is_wsl"))
        if os_name not in {"Windows", "Linux"}:
            missing.append(f"Unlimited-OCR has no verified NVIDIA Transformers path for {os_name or 'this OS'}.")
            status = CompatibilityStatus.UNSUPPORTED
        elif architecture.casefold() not in {"amd64", "x86_64"}:
            missing.append(f"Architecture {architecture or 'unknown'} is not verified by this integration.")
            status = CompatibilityStatus.UNKNOWN
            confidence = min(confidence, 0.45)
        else:
            met.append(f"64-bit {os_name} runtime is eligible for an isolated Python environment.")
            if is_wsl:
                status = _degrade(status, CompatibilityStatus.EXPERIMENTAL)
                reasons.append("WSL2 GPU pass-through must be validated inside the selected distribution.")

        gpu = _best_nvidia_gpu(env.get("gpu", []))
        estimates = self.metadata["resource_estimates"]
        minimum_vram = int(estimates["minimum_vram_bytes"])
        recommended_vram = int(estimates["recommended_vram_bytes"])
        if gpu is None:
            vendors = sorted({str(item.get("vendor", "Unknown")) for item in env.get("gpu", [])})
            missing.append(
                "A CUDA-capable NVIDIA GPU is required by the upstream Transformers recipe; "
                f"detected vendors: {', '.join(vendors) or 'none'}."
            )
            status = CompatibilityStatus.UNSUPPORTED
        else:
            vram = _as_int(gpu.get("vram_total_bytes"))
            if vram is None:
                missing.append("NVIDIA GPU VRAM could not be measured reliably.")
                status = _degrade(status, CompatibilityStatus.UNKNOWN)
                confidence = min(confidence, 0.55)
            elif vram < minimum_vram:
                missing.append(
                    f"GPU VRAM is {_gib(vram)} GiB; conservative minimum is {_gib(minimum_vram)} GiB."
                )
                status = CompatibilityStatus.UNSUPPORTED
            elif vram < recommended_vram:
                met.append(f"NVIDIA GPU detected with {_gib(vram)} GiB VRAM.")
                reasons.append("VRAM is between the conservative minimum and recommended amount.")
                status = _degrade(status, CompatibilityStatus.EXPERIMENTAL)
                confidence = min(confidence, 0.7)
            else:
                met.append(
                    f"{gpu.get('name', 'NVIDIA GPU')} has {_gib(vram)} GiB VRAM, meeting the conservative recommendation."
                )
            capability = _version_tuple(gpu.get("compute_capability"))
            minimum_capability = _version_tuple(estimates["minimum_compute_capability"])
            if capability is None:
                missing.append("GPU compute capability could not be determined.")
                status = _degrade(status, CompatibilityStatus.UNKNOWN)
                confidence = min(confidence, 0.6)
            elif capability < minimum_capability:
                missing.append(
                    "The official BF16 inference path requires an Ampere-class or newer GPU in this integration."
                )
                status = CompatibilityStatus.UNSUPPORTED
            else:
                met.append(f"GPU compute capability {gpu.get('compute_capability')} supports the BF16 plan.")

        memory = _as_int(env.get("memory", {}).get("total_bytes")) or 0
        if memory < int(estimates["minimum_ram_bytes"]):
            missing.append(f"System RAM is {_gib(memory)} GiB; at least {_gib(estimates['minimum_ram_bytes'])} GiB is required.")
            status = CompatibilityStatus.UNSUPPORTED
        elif memory < int(estimates["recommended_ram_bytes"]):
            met.append(f"System RAM is {_gib(memory)} GiB.")
            reasons.append("RAM meets minimum but not the conservative recommendation.")
            status = _degrade(status, CompatibilityStatus.EXPERIMENTAL)
        else:
            met.append(f"System RAM is {_gib(memory)} GiB, meeting the conservative recommendation.")

        disk_free = _as_int(env.get("storage", {}).get("free_bytes")) or 0
        if disk_free < int(estimates["minimum_free_disk_bytes"]):
            missing.append(
                f"Free disk is {_gib(disk_free)} GiB; setup requires at least {_gib(estimates['minimum_free_disk_bytes'])} GiB."
            )
            status = CompatibilityStatus.UNSUPPORTED
        else:
            met.append(f"Free disk space is {_gib(disk_free)} GiB.")
        if not bool(env.get("storage", {}).get("writable_parent")):
            missing.append("The private OCR data-root parent is not writable.")
            status = CompatibilityStatus.UNSUPPORTED

        driver = env.get("nvidia_driver", {})
        driver_major = _driver_major(driver.get("driver_version"))
        profile, index_url = self._select_pytorch_profile(driver_major)
        if gpu is not None and profile is None:
            missing.append("NVIDIA Driver is missing, unknown, or too old for an official PyTorch 2.10 CUDA wheel.")
            status = CompatibilityStatus.UNSUPPORTED if driver_major is not None else CompatibilityStatus.UNKNOWN
        elif profile:
            met.append(f"NVIDIA Driver {driver.get('driver_version')} supports the PyTorch {profile} wheel family.")
            changes.append(
                f"Install torch 2.10.0 and torchvision 0.25.0 from {index_url} inside the private OCR runtime."
            )

        python = env.get("python", {})
        tools = python.get("tools", {})
        uv_details = tools.get("uv", {})
        uv_detected = bool(uv_details.get("available"))
        minimum_uv = _version_tuple(
            self.metadata.get("uv_bootstrap", {}).get("minimum_compatible_version")
        )
        detected_uv = _tool_version_tuple(uv_details.get("version_output"))
        uv_available = bool(
            uv_detected
            and detected_uv
            and minimum_uv
            and detected_uv >= minimum_uv
        )
        uv_bootstrap_available = bool(tools.get("uv", {}).get("bootstrap_available")) and bool(
            _uv_bootstrap_asset(self.metadata, env)
        )
        conda_available = bool(tools.get("conda", {}).get("available"))
        current_python = str(python.get("version", ""))
        if current_python.startswith("3.12."):
            met.append(f"Current Python {current_python} matches the upstream 3.12 major/minor.")
        elif uv_available:
            changes.append("Use uv to provision a private CPython 3.12 runtime without replacing system Python.")
        elif conda_available:
            changes.append(
                "Use Conda to provision a private CPython 3.12 prefix without replacing system Python."
            )
        elif uv_bootstrap_available:
            changes.append(
                "Use the verified APP-managed uv bootstrap to provision private CPython 3.12."
            )
        else:
            missing.append(
                "Python 3.12 is not active and neither uv nor Conda can provision it safely."
            )
            status = _degrade(status, CompatibilityStatus.UNKNOWN)
        if uv_available:
            suffix = (
                f" at {uv_details.get('path')} (outside PATH; the absolute executable will be used)"
                if uv_details.get("state") == "DETECTED_OUTSIDE_PATH"
                else ""
            )
            met.append(f"uv is available{suffix} for isolated, reproducible environment creation.")
            environment_manager = "uv"
        elif conda_available:
            if uv_detected:
                changes.append(
                    f"Detected uv is older than the supported minimum {self.metadata['uv_bootstrap']['minimum_compatible_version']}; use Conda instead."
                )
            met.append("Conda is available for isolated prefix creation.")
            environment_manager = "conda"
        elif uv_bootstrap_available:
            bootstrap = self.metadata["uv_bootstrap"]
            changes.append(
                f"After consent, download and SHA-256 verify uv {bootstrap['version']} "
                "inside the APP-managed OCR runtime without editing PATH or shell profiles."
            )
            environment_manager = "managed_uv"
        else:
            environment_manager = None
            if current_python.startswith("3.12."):
                missing.append(
                    "A supported environment manager is required so setup never modifies the APP runtime."
                )
                status = _degrade(status, CompatibilityStatus.UNKNOWN)

        pytorch = env.get("pytorch", {})
        if not pytorch.get("installed"):
            changes.append("Install PyTorch only inside the private OCR runtime; the APP runtime remains unchanged.")
        elif not pytorch.get("cuda_available"):
            changes.append("Do not reuse the current CPU-only PyTorch; install a compatible private CUDA build.")
        else:
            met.append("The currently inspected runtime can access CUDA, but it will not be modified or reused automatically.")

        changes.extend(
            [
                "Download the pinned Unlimited-OCR model revision after explicit consent.",
                "Execute pinned Hugging Face custom model code only inside the private worker process.",
            ]
        )
        if status == CompatibilityStatus.SUPPORTED:
            status = CompatibilityStatus.SUPPORTED_WITH_CHANGES
        reasons.insert(
            0,
            "Upstream documents NVIDIA Transformers inference, but installation and a real benchmark are still required.",
        )
        age = metadata_age_days(self.metadata)
        if age > 30:
            reasons.append(f"Bundled compatibility metadata is {age:.0f} days old and should be refreshed.")
            status = _degrade(status, CompatibilityStatus.UNKNOWN)
            confidence = min(confidence, 0.55)
        if conflicts:
            reasons.append("Known upstream metadata conflicts are recorded; incompatible backends remain blocked.")
            confidence = min(confidence, 0.9)

        artifacts = self.metadata["model_artifacts"]
        download = int(artifacts["required_download_bytes"]) + int(
            estimates["estimated_runtime_download_bytes"]
        )
        risk = RiskLevel.MEDIUM
        if status in {CompatibilityStatus.UNSUPPORTED, CompatibilityStatus.UNKNOWN}:
            risk = RiskLevel.BLOCKED
        elif status == CompatibilityStatus.EXPERIMENTAL:
            risk = RiskLevel.HIGH
        return CompatibilityReport(
            status=status,
            confidence=round(max(0.0, min(confidence, 1.0)), 2),
            reasons=tuple(_dedupe(reasons)),
            requirements_met=tuple(_dedupe(met)),
            requirements_missing=tuple(_dedupe(missing)),
            required_changes=tuple(_dedupe(changes)),
            estimated_download_size=download,
            estimated_disk_usage=int(estimates["estimated_installed_bytes"]),
            estimated_vram_requirement=int(estimates["recommended_vram_bytes"]),
            recommended_backend=(
                RuntimeBackend.TRANSFORMERS
                if status not in {CompatibilityStatus.UNSUPPORTED, CompatibilityStatus.UNKNOWN}
                else RuntimeBackend.NONE
            ),
            recommended_runtime=(
                f"private {environment_manager} CPython 3.12 / torch 2.10.0 {profile or 'unresolved'} worker"
                if profile and environment_manager
                else None
            ),
            risk_level=risk,
            metadata_revision=str(self.metadata["source_revision"]),
            conflicts=tuple(conflicts),
            app_compatibility=_app_compatibility(env),
            basic_ocr=_basic_ocr_compatibility(env),
            recommended_provider=(
                "unlimited_ocr_after_setup"
                if status
                not in {CompatibilityStatus.UNSUPPORTED, CompatibilityStatus.UNKNOWN}
                else "tesseract"
                if bool(env.get("basic_ocr", {}).get("executable_available"))
                else "tesseract_after_install"
            ),
            selected_gpu=_selected_gpu_summary(gpu),
        )

    def _select_pytorch_profile(self, driver_major: int | None) -> tuple[str | None, str | None]:
        if driver_major is None:
            return None, None
        profiles = self.metadata["backends"]["transformers"]["pytorch_profiles"]
        for name in ("cu130", "cu128", "cu126"):
            profile = profiles[name]
            if driver_major >= int(profile["minimum_driver_major"]):
                return name, str(profile["index_url"])
        return None, None


def _best_nvidia_gpu(items: Any) -> Mapping[str, Any] | None:
    candidates = [item for item in items or [] if str(item.get("vendor", "")).upper() == "NVIDIA"]
    if not candidates:
        return None
    return max(
        enumerate(candidates),
        key=lambda pair: (
            _as_int(pair[1].get("vram_total_bytes")) or 0,
            -(
                _as_int(pair[1].get("index"))
                if _as_int(pair[1].get("index")) is not None
                else pair[0]
            ),
        ),
    )[1]


def _selected_gpu_summary(gpu: Mapping[str, Any] | None) -> dict[str, Any]:
    if gpu is None:
        return {}
    return {
        "index": gpu.get("index"),
        "uuid": gpu.get("uuid"),
        "name": gpu.get("name"),
        "vram_total_bytes": _as_int(gpu.get("vram_total_bytes")),
        "compute_capability": gpu.get("compute_capability"),
        "selection_policy": "highest_vram_then_lowest_index",
    }


def _uv_bootstrap_asset(
    metadata: Mapping[str, Any], env: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    os_info = env.get("os", {})
    system = str(os_info.get("system", ""))
    machine = str(os_info.get("machine", "")).casefold()
    normalized = (
        "x86_64"
        if machine in {"amd64", "x86_64"}
        else "arm64"
        if machine in {"arm64", "aarch64"}
        else ""
    )
    if not normalized or (
        system == "Linux" and "musl" in str(os_info.get("platform", "")).casefold()
    ):
        return None
    asset = metadata.get("uv_bootstrap", {}).get("assets", {}).get(
        f"{system}-{normalized}"
    )
    return asset if isinstance(asset, Mapping) else None


def _app_compatibility(env: Mapping[str, Any]) -> dict[str, Any]:
    version = str(env.get("python", {}).get("version", ""))
    parts = _version_tuple(version)
    supported = bool(parts and parts >= (3, 10))
    gui = dict(env.get("runtime", {}).get("gui", {}))
    return {
        "status": "SUPPORTED" if supported else "UNSUPPORTED_SOURCE_RUNTIME",
        "cli_status": "AVAILABLE" if supported else "PYTHON_TOO_OLD",
        "gui_status": gui.get("status", "UNKNOWN"),
        "tkinter_importable": gui.get("tkinter_importable"),
        "display_available": gui.get("display_available"),
        "python_version": version,
        "requires_python": ">=3.10",
        "reason": (
            "The active APP runtime satisfies the project Python requirement."
            if supported
            else "The active source runtime is older than the project Python requirement."
        ),
    }


def _basic_ocr_compatibility(env: Mapping[str, Any]) -> dict[str, Any]:
    detected = dict(env.get("basic_ocr", {}))
    available = bool(detected.get("executable_available"))
    return {
        **detected,
        "status": "AVAILABLE" if available else "OPTIONAL_DEPENDENCY_MISSING",
        "app_usable_without_it": True,
    }


def _driver_major(value: Any) -> int | None:
    try:
        return int(str(value).split(".", 1)[0])
    except (TypeError, ValueError):
        return None


def _version_tuple(value: Any) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in str(value).split("."))
    except (TypeError, ValueError):
        return None


def _tool_version_tuple(value: Any) -> tuple[int, ...] | None:
    text = str(value)
    for token in text.split():
        parsed = _version_tuple(token)
        if parsed:
            return parsed
    return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _gib(value: Any) -> float:
    return round(int(value) / (1024**3), 1)


def _degrade(current: CompatibilityStatus, candidate: CompatibilityStatus) -> CompatibilityStatus:
    order = {
        CompatibilityStatus.SUPPORTED: 0,
        CompatibilityStatus.SUPPORTED_WITH_CHANGES: 1,
        CompatibilityStatus.CPU_ONLY_IF_AVAILABLE: 2,
        CompatibilityStatus.EXPERIMENTAL: 3,
        CompatibilityStatus.UNKNOWN: 4,
        CompatibilityStatus.UNSUPPORTED: 5,
    }
    return candidate if order[candidate] > order[current] else current


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
