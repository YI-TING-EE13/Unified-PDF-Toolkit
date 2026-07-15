"""Pinned model snapshot inventory, integrity verification, and safe cleanup."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
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
        self.cache_root = cache_root.expanduser().resolve()
        self.snapshots_root = self.cache_root / "snapshots"

    def snapshot_path(self, revision: str) -> Path:
        if not _is_revision(revision):
            raise ValueError("Model revision must be a full 40-character Git SHA.")
        return self.snapshots_root / revision

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
        shutil.rmtree(path, onerror=_clear_readonly_and_retry)
        return True

    def clear_download_cache(self) -> bool:
        hub = self.cache_root / "hub"
        _assert_child(hub, self.cache_root)
        if not hub.exists():
            return False
        shutil.rmtree(hub, onerror=_clear_readonly_and_retry)
        return True


def _is_revision(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value.casefold())


def _assert_child(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise ValueError("Cleanup target is outside the managed cache root.")


def _directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
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
    os.replace(temporary, path)


def _clear_readonly_and_retry(function: Any, path: str, exc_info: Any) -> None:
    try:
        os.chmod(path, 0o700)
        function(path)
    except OSError:
        raise exc_info[1]
