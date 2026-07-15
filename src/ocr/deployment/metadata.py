"""Load and validate compatibility metadata for optional OCR deployments."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlparse

TRUSTED_SOURCE_HOSTS = {
    "github.com",
    "huggingface.co",
    "pytorch.org",
    "download.pytorch.org",
    "docs.nvidia.com",
}


class CompatibilityMetadataError(ValueError):
    """Raised when compatibility metadata cannot be trusted."""


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
        _validate_trusted_url(str(profile.get("index_url", "")), label=f"profile {name}")
    uv_bootstrap = data.get("uv_bootstrap", {})
    if not isinstance(uv_bootstrap, Mapping) or not re.fullmatch(
        r"\d+\.\d+\.\d+", str(uv_bootstrap.get("version", ""))
    ):
        raise CompatibilityMetadataError("Pinned uv bootstrap metadata is required.")
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
