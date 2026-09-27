"""Load and validate compatibility metadata for optional OCR deployments."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlparse

from .versions import parse_numeric_version

TRUSTED_SOURCE_HOSTS = {
    "github.com",
    "huggingface.co",
    "pytorch.org",
    "download.pytorch.org",
    "docs.nvidia.com",
}


class CompatibilityMetadataError(ValueError):
    """Raised when compatibility metadata cannot be trusted."""


_COMPATIBILITY_SCHEMA_VERSION = "2.0"
_DRIVER_PLATFORMS = frozenset({"windows", "linux"})


def bundled_metadata_path() -> Path:
    return Path(
        resources.files("src.ocr.deployment.resources").joinpath(
            "unlimited_ocr_compatibility.json"
        )
    )


def load_compatibility_metadata(path: Path | None = None) -> dict[str, Any]:
    source = path or bundled_metadata_path()
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompatibilityMetadataError(f"Unable to load compatibility metadata: {exc}") from exc
    validate_compatibility_metadata(data)
    return data


def validate_compatibility_metadata(data: Mapping[str, Any]) -> None:
    required = (
        "schema_version",
        "model",
        "checked_at",
        "source_revision",
        "model_revision",
        "sources",
        "model_artifacts",
        "resource_estimates",
        "backends",
    )
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise CompatibilityMetadataError(
            f"Compatibility metadata is missing required fields: {', '.join(missing)}"
        )
    if data["schema_version"] != _COMPATIBILITY_SCHEMA_VERSION:
        raise CompatibilityMetadataError(
            f"Unsupported compatibility metadata schema version: {data['schema_version']}."
        )
    if "driver_families" in data:
        raise CompatibilityMetadataError(
            "Obsolete driver_families thresholds are ambiguous; use per-profile driver versions."
        )
    if data["model"] != "baidu/Unlimited-OCR":
        raise CompatibilityMetadataError("Unexpected model id in compatibility metadata.")
    for revision_key in ("source_revision", "model_revision"):
        value = str(data[revision_key])
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value.lower()):
            raise CompatibilityMetadataError(f"{revision_key} must be a full Git revision.")
    artifacts = data["model_artifacts"]
    if not isinstance(artifacts, Mapping) or int(artifacts.get("required_download_bytes", 0)) <= 0:
        raise CompatibilityMetadataError("Model artifact download size is invalid.")
    required_files = artifacts.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        raise CompatibilityMetadataError("Pinned model artifact inventory is required.")
    for name in required_files:
        _validate_relative_artifact_path(str(name), label="required model file")
    _validate_relative_artifact_path(
        str(artifacts.get("weight_file", "")), label="model weight file"
    )
    allow_patterns = artifacts.get("allow_patterns")
    if not isinstance(allow_patterns, list) or not allow_patterns:
        raise CompatibilityMetadataError("Pinned model allow-pattern inventory is required.")
    for pattern in allow_patterns:
        _validate_relative_artifact_path(str(pattern), label="model allow pattern")
    weight_sha256 = str(artifacts.get("weight_sha256", ""))
    if len(weight_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in weight_sha256.casefold()
    ):
        raise CompatibilityMetadataError("Pinned model weight SHA-256 is invalid.")
    backends = data["backends"]
    if not isinstance(backends, Mapping) or "transformers" not in backends:
        raise CompatibilityMetadataError("Transformers backend metadata is required.")
    for label, url in data["sources"].items():
        _validate_trusted_url(str(url), label=f"source {label}")
    transformer = backends["transformers"]
    packages = transformer.get("packages", {})
    if not isinstance(packages, Mapping) or not packages:
        raise CompatibilityMetadataError("Pinned Transformers packages are required.")
    for name, version in packages.items():
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(name)) or not re.fullmatch(
            r"[A-Za-z0-9_.+-]+", str(version)
        ):
            raise CompatibilityMetadataError("Unsafe package name or version in metadata.")
    profiles = transformer.get("pytorch_profiles", {})
    if not isinstance(profiles, Mapping) or not profiles:
        raise CompatibilityMetadataError("Official PyTorch wheel profiles are required.")
    for name, profile in profiles.items():
        if not re.fullmatch(r"cu\d+", str(name)) or not isinstance(profile, Mapping):
            raise CompatibilityMetadataError("Invalid PyTorch CUDA profile metadata.")
        if "minimum_driver_major" in profile:
            raise CompatibilityMetadataError(
                f"Profile {name} uses an ambiguous major-only NVIDIA Driver threshold."
            )
        minimums = profile.get("minimum_driver_versions")
        if not isinstance(minimums, Mapping) or set(minimums) != _DRIVER_PLATFORMS:
            raise CompatibilityMetadataError(
                f"Profile {name} must define Windows and Linux Driver minimums."
            )
        for platform_key, minimum in minimums.items():
            if not isinstance(minimum, str) or parse_numeric_version(minimum) is None:
                raise CompatibilityMetadataError(
                    f"Profile {name} has an invalid {platform_key} Driver minimum version."
                )
        _validate_trusted_url(str(profile.get("index_url", "")), label=f"profile {name}")
    uv_bootstrap = data.get("uv_bootstrap", {})
    if not isinstance(uv_bootstrap, Mapping) or not re.fullmatch(
        r"\d+\.\d+\.\d+", str(uv_bootstrap.get("version", ""))
    ):
        raise CompatibilityMetadataError("Pinned uv bootstrap metadata is required.")
    if not re.fullmatch(
        r"\d+\.\d+\.\d+", str(uv_bootstrap.get("minimum_compatible_version", ""))
    ):
        raise CompatibilityMetadataError("Minimum compatible uv version is required.")
    _validate_trusted_url(str(uv_bootstrap.get("source", "")), label="uv bootstrap source")
    assets = uv_bootstrap.get("assets", {})
    if not isinstance(assets, Mapping) or not assets:
        raise CompatibilityMetadataError("Pinned uv bootstrap assets are required.")
    for platform_key, asset in assets.items():
        if not re.fullmatch(r"(Windows|Linux|Darwin)-(x86_64|arm64)", str(platform_key)):
            raise CompatibilityMetadataError("Invalid uv bootstrap platform key.")
        if not isinstance(asset, Mapping):
            raise CompatibilityMetadataError("Invalid uv bootstrap asset metadata.")
        _validate_trusted_url(str(asset.get("url", "")), label=f"uv asset {platform_key}")
        digest = str(asset.get("sha256", ""))
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise CompatibilityMetadataError("Invalid uv bootstrap SHA-256.")
        if int(asset.get("size", 0)) <= 0:
            raise CompatibilityMetadataError("Invalid uv bootstrap asset size.")


def driver_platform_key(system: Any) -> str | None:
    """Normalize the OS names emitted by the environment inspector."""

    if not isinstance(system, str):
        return None
    platform_key = system.strip().casefold()
    return platform_key if platform_key in _DRIVER_PLATFORMS else None


def minimum_driver_versions_by_profile(
    data: Mapping[str, Any], system: Any
) -> dict[str, str]:
    """Return profile minimums for one supported OS from canonical metadata."""

    platform_key = driver_platform_key(system)
    if platform_key is None:
        return {}
    profiles = data["backends"]["transformers"]["pytorch_profiles"]
    profile_order = ("cu130", "cu128", "cu126")
    return {
        name: str(profiles[name]["minimum_driver_versions"][platform_key])
        for name in profile_order
        if name in profiles
    }


def _validate_trusted_url(value: str, *, label: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in TRUSTED_SOURCE_HOSTS:
        raise CompatibilityMetadataError(f"Untrusted HTTPS URL for {label}.")


def _validate_relative_artifact_path(value: str, *, label: str) -> None:
    """Reject absolute and parent-traversing repository artifact paths."""

    if not value or "\\" in value:
        raise CompatibilityMetadataError(f"Unsafe {label} path in compatibility metadata.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise CompatibilityMetadataError(f"Unsafe {label} path in compatibility metadata.")


def metadata_age_days(data: Mapping[str, Any], *, now: datetime | None = None) -> float:
    checked = str(data["checked_at"]).replace("Z", "+00:00")
    try:
        checked_at = datetime.fromisoformat(checked)
    except ValueError as exc:
        raise CompatibilityMetadataError("checked_at is not an ISO-8601 timestamp.") from exc
    current = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    return max(0.0, (current - checked_at).total_seconds() / 86400)
