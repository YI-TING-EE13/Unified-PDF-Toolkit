"""Warning-only model revision policy checks for experimental local OCR.

This module performs local metadata inspection only. It does not import AI
runtimes, access the network, download models, or block local model paths by
default.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


RECOMMENDED_UNLIMITED_OCR_MODEL_ID = "baidu/Unlimited-OCR"
DEFAULT_ALLOWED_UNLIMITED_OCR_MODEL_IDS = (RECOMMENDED_UNLIMITED_OCR_MODEL_ID,)
MODEL_REVISION_OPTION_KEY = "model_revision"
MODEL_ALLOWED_IDS_OPTION_KEY = "allowed_model_ids"

_HF_SNAPSHOT_REVISION_RE = re.compile(r"^[0-9a-f]{8,64}$", re.IGNORECASE)
_METADATA_FILES = (
    "config.json",
    "tokenizer_config.json",
    "preprocessor_config.json",
    "generation_config.json",
)
_METADATA_GLOBS = (
    "modeling_*.py",
    "configuration_*.py",
)


@dataclass(frozen=True)
class ModelRevisionPolicyStatus:
    model_id: str
    model_id_allowed: bool
    allowed_model_ids: tuple[str, ...]
    revision: str | None
    revision_pinned: bool
    revision_source: str | None
    metadata_present: bool | None
    metadata_detail: str
    metadata_model_hint: str | None
    warnings: tuple[str, ...]


def allowed_model_ids_from_options(
    options: Mapping[str, str] | None,
) -> tuple[str, ...]:
    """Return optional comma-separated allowed model ids from safe config options."""

    if not options:
        return DEFAULT_ALLOWED_UNLIMITED_OCR_MODEL_IDS
    value = options.get(MODEL_ALLOWED_IDS_OPTION_KEY)
    if not value:
        return DEFAULT_ALLOWED_UNLIMITED_OCR_MODEL_IDS
    parsed = tuple(
        item.strip()
        for item in str(value).replace("\n", ",").split(",")
        if item.strip()
    )
    return parsed or DEFAULT_ALLOWED_UNLIMITED_OCR_MODEL_IDS


def evaluate_unlimited_ocr_model_policy(
    *,
    model_id: str | None,
    model_path: str | None = None,
    model_revision: str | None = None,
    allowed_model_ids: Sequence[str] | None = None,
) -> ModelRevisionPolicyStatus:
    """Evaluate local beta policy status without failing unknown local paths."""

    cleaned_model_id = (model_id or "").strip() or RECOMMENDED_UNLIMITED_OCR_MODEL_ID
    allowed = tuple(allowed_model_ids or DEFAULT_ALLOWED_UNLIMITED_OCR_MODEL_IDS)
    model_id_allowed = cleaned_model_id in allowed
    warnings: list[str] = []
    if not model_id_allowed:
        warnings.append(
            "Configured model id is not in the beta allowed model id list."
        )

    revision, revision_source = _resolve_revision_hint(
        model_path=model_path,
        model_revision=model_revision,
    )
    revision_pinned = bool(revision)
    if not revision_pinned:
        warnings.append(
            "Model revision is not pinned. Record an explicit revision before broader beta use."
        )

    metadata_present, metadata_detail, metadata_model_hint = _inspect_model_metadata(
        model_path
    )
    if metadata_present is False:
        warnings.append(
            "Local model folder has no recognizable Hugging Face metadata files."
        )

    return ModelRevisionPolicyStatus(
        model_id=cleaned_model_id,
        model_id_allowed=model_id_allowed,
        allowed_model_ids=allowed,
        revision=revision,
        revision_pinned=revision_pinned,
        revision_source=revision_source,
        metadata_present=metadata_present,
        metadata_detail=metadata_detail,
        metadata_model_hint=metadata_model_hint,
        warnings=tuple(warnings),
    )


def _resolve_revision_hint(
    *,
    model_path: str | None,
    model_revision: str | None,
) -> tuple[str | None, str | None]:
    explicit = (model_revision or "").strip()
    if explicit:
        return explicit, "settings"
    path = Path(model_path) if model_path else None
    if path is None:
        return None, None
    detected = _detect_huggingface_snapshot_revision(path)
    if detected:
        return detected, "huggingface snapshot path"
    return None, None


def _detect_huggingface_snapshot_revision(path: Path) -> str | None:
    parts = path.parts
    for index, part in enumerate(parts[:-1]):
        if part == "snapshots":
            candidate = parts[index + 1]
            if _HF_SNAPSHOT_REVISION_RE.match(candidate):
                return candidate
    if path.parent.name == "snapshots" and _HF_SNAPSHOT_REVISION_RE.match(path.name):
        return path.name
    return None


def _inspect_model_metadata(
    model_path: str | None,
) -> tuple[bool | None, str, str | None]:
    if not model_path:
        return None, "model path not configured", None
    path = Path(model_path)
    if not path.exists():
        return None, "model path not found", None
    if not path.is_dir():
        return False, "model path is not a folder", None

    found = [name for name in _METADATA_FILES if (path / name).exists()]
    for pattern in _METADATA_GLOBS:
        if any(path.glob(pattern)):
            found.append(pattern)
    if not found:
        return False, "no recognizable metadata files found", None
    return True, f"found {', '.join(sorted(set(found)))}", _read_model_hint(path)


def _read_model_hint(path: Path) -> str | None:
    config_path = path / "config.json"
    if not config_path.exists():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for key in ("_name_or_path", "model_type"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    architectures = data.get("architectures")
    if isinstance(architectures, list):
        for item in architectures:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None
