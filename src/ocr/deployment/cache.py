"""Pinned model snapshot inventory, integrity verification, and safe cleanup."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import DeploymentFailure, ErrorCode, make_error


@dataclass(frozen=True)
class ModelSnapshotStatus:
    revision: str
    path: str
    exists: bool
    complete: bool
    total_bytes: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "path": self.path,
            "exists": self.exists,
            "complete": self.complete,
            "total_bytes": self.total_bytes,
            "errors": self.errors,
        }


class ModelCacheManager:
    def __init__(self, cache_root: Path) -> None:
        declared = Path(os.path.abspath(str(cache_root.expanduser())))
        if _is_link_or_junction(declared):
            raise ValueError("Managed model cache root cannot be a symbolic link or junction.")
        self.cache_root = declared.resolve()
        self.snapshots_root = self.cache_root / "snapshots"

    def _assert_cache_root(self) -> None:
        if _is_link_or_junction(self.cache_root):
            raise ValueError("Managed model cache root cannot be a symbolic link or junction.")

    def snapshot_path(self, revision: str) -> Path:
        self._assert_cache_root()
        if not _is_revision(revision):
            raise ValueError("Model revision must be a full 40-character Git SHA.")
        _assert_child(self.snapshots_root, self.cache_root)
        path = self.snapshots_root / revision
        _assert_child(path, self.snapshots_root)
        return path

    def inspect(self, revision: str, metadata: Mapping[str, Any]) -> ModelSnapshotStatus:
        path = self.snapshot_path(revision)
        if not path.exists():
            return ModelSnapshotStatus(revision, str(path), False, False, 0, ("snapshot not found",))
        errors: list[str] = []
        artifacts = metadata["model_artifacts"]
        weight = path / str(artifacts["weight_file"])
        if not weight.is_file() or weight.is_symlink():
            errors.append("model weight file is missing")
        elif weight.stat().st_size != int(artifacts["weight_bytes"]):
            errors.append("model weight size does not match pinned metadata")
        for name in artifacts.get("required_files", []):
            required = path / str(name)
            if not required.is_file() or required.is_symlink():
                errors.append(f"required model file is missing: {name}")
        return ModelSnapshotStatus(
            revision=revision,
            path=str(path),
            exists=True,
            complete=not errors,
            total_bytes=_directory_size(path),
            errors=tuple(errors),
        )

    def verify(self, revision: str, metadata: Mapping[str, Any], *, full_hash: bool = True) -> ModelSnapshotStatus:
        status = self.inspect(revision, metadata)
        errors = list(status.errors)
        if status.exists and full_hash and not errors:
            artifacts = metadata["model_artifacts"]
            actual = _sha256(Path(status.path) / str(artifacts["weight_file"]))
            if actual.casefold() != str(artifacts["weight_sha256"]).casefold():
                errors.append("model weight SHA-256 does not match pinned metadata")
        verified = ModelSnapshotStatus(
            revision=status.revision,
            path=status.path,
            exists=status.exists,
            complete=status.exists and not errors,
            total_bytes=status.total_bytes,
            errors=tuple(errors),
        )
        if not verified.complete:
            raise DeploymentFailure(
                make_error(
                    ErrorCode.MODEL_INTEGRITY_FAILED,
                    technical_details="; ".join(verified.errors),
                    detected_state=verified.to_dict(),
                    expected_state={"revision": revision},
                )
            )
        return verified

    def write_manifest(self, revision: str, value: Mapping[str, Any]) -> Path:
        path = self.snapshot_path(revision) / ".pdf-toolkit-manifest.json"
        _atomic_json_write(path, dict(value))
        return path

    def uninstall_snapshot(self, revision: str) -> bool:
        path = self.snapshot_path(revision)
        _assert_child(path, self.snapshots_root)
        if not path.exists():
            return False
        if _is_link_or_junction(path):
            raise ValueError("Managed model snapshot was replaced by a link or junction.")
        shutil.rmtree(path, onerror=_clear_readonly_and_retry)
        return True

    def uninstall_all_snapshots(self) -> int:
        _assert_child(self.snapshots_root, self.cache_root)
        if not self.snapshots_root.exists():
            return 0
        if _is_link_or_junction(self.snapshots_root):
            raise ValueError("Managed snapshots root was replaced by a link or junction.")
        removed = 0
        for child in sorted(self.snapshots_root.iterdir()):
            if child.is_dir() and _is_revision(child.name):
                removed += int(self.uninstall_snapshot(child.name))
        return removed

    def clear_download_cache(self) -> bool:
        self._assert_cache_root()
        removed = False
        for name in ("hub", "hf-home", "modules", "transformers"):
            target = self.cache_root / name
            _assert_child(target, self.cache_root)
            if not target.exists():
                continue
            if _is_link_or_junction(target):
                raise ValueError(f"Managed {name} cache was replaced by a link or junction.")
            shutil.rmtree(target, onerror=_clear_readonly_and_retry)
            removed = True
        return removed


def _is_revision(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value.casefold())


def _is_link_or_junction(path: Path) -> bool:
    """Detect a link/reparse point on this path without rejecting aliased ancestors."""

    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except FileNotFoundError:
        return False


def _assert_child(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise ValueError("Cleanup target is outside the managed cache root.")


def _directory_size(path: Path) -> int:
    resolved_root = path.resolve()
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_symlink():
                continue
            resolved_item = item.resolve()
            if resolved_item != resolved_root and resolved_root not in resolved_item.parents:
                continue
            if resolved_item.is_file():
                total += resolved_item.stat().st_size
        except OSError:
            continue
    return total


def _sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(min(0.05 * (2**attempt), 0.5))


def _clear_readonly_and_retry(function: Any, path: str, exc_info: Any) -> None:
    try:
        os.chmod(path, 0o700)
        function(path)
    except OSError:
        raise exc_info[1]
