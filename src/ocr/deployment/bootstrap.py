"""Verified APP-managed prerequisite bootstrap helpers."""

from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

_TRUSTED_DOWNLOAD_HOSTS = {"github.com", "release-assets.githubusercontent.com"}


class UvBootstrapper:
    """Download one pinned uv archive and install only its executables."""

    def __init__(self, bootstrap: Mapping[str, Any], *, runtime_root: Path) -> None:
        self.bootstrap = dict(bootstrap)
        self.runtime_root = runtime_root.resolve()
        self.install_dir = Path(str(self.bootstrap["install_dir"])).resolve()
        self.executable = Path(str(self.bootstrap["executable"])).resolve()
        if not self.install_dir.is_relative_to(self.runtime_root):
            raise ValueError("uv bootstrap destination is outside the managed runtime.")

    def install(self, *, check_cancel: Callable[[], None]) -> dict[str, Any]:
        if self.executable.is_file():
            return {
                "reused_existing": True,
                "executable": str(self.executable),
                "version": str(self.bootstrap["version"]),
            }

        url = str(self.bootstrap["url"])
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "github.com":
            raise ValueError("uv bootstrap URL is not an allowlisted GitHub HTTPS asset.")

        prerequisites = self.install_dir.parent
        prerequisites.mkdir(parents=True, exist_ok=True)
        archive = prerequisites / (str(self.bootstrap["filename"]) + ".part")
        staging = Path(tempfile.mkdtemp(prefix="uv-bootstrap-", dir=prerequisites))
        try:
            digest, total = self._download(url, archive, check_cancel=check_cancel)
            expected = str(self.bootstrap["sha256"])
            if digest != expected:
                raise ValueError(
                    f"uv bootstrap SHA-256 mismatch: expected {expected}, detected {digest}."
                )
            self._extract_executables(archive, staging)
            check_cancel()
            self.install_dir.mkdir(parents=True, exist_ok=True)
            installed: list[str] = []
            for name in ("uv", "uvx", "uv.exe", "uvx.exe"):
                source = staging / name
                if not source.is_file():
                    continue
                destination = self.install_dir / name
                os.replace(source, destination)
                if os.name != "nt":
                    destination.chmod(0o755)
                installed.append(str(destination))
            if not self.executable.is_file():
                raise ValueError("Verified uv archive did not contain the expected executable.")
            return {
                "reused_existing": False,
                "executable": str(self.executable),
                "version": str(self.bootstrap["version"]),
                "downloaded_bytes": total,
                "sha256": digest,
                "installed_files": installed,
                "path_modified": False,
                "shell_profile_modified": False,
            }
        finally:
            archive.unlink(missing_ok=True)
            shutil.rmtree(staging, ignore_errors=True)

    def _download(
        self,
        url: str,
        destination: Path,
        *,
        check_cancel: Callable[[], None],
    ) -> tuple[str, int]:
        request = urllib.request.Request(url, headers={"User-Agent": "Unified-PDF-Toolkit"})
        expected_size = int(self.bootstrap["size"])
        maximum_size = expected_size + 1024 * 1024
        digest = hashlib.sha256()
        total = 0
        with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as out:
            final_host = urlparse(response.geturl()).hostname
            if final_host not in _TRUSTED_DOWNLOAD_HOSTS:
                raise ValueError("uv bootstrap redirect left the trusted GitHub release hosts.")
            while True:
                check_cancel()
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum_size:
                    raise ValueError("uv bootstrap archive exceeded the pinned size limit.")
                digest.update(chunk)
                out.write(chunk)
        if total != expected_size:
            raise ValueError(
                f"uv bootstrap size mismatch: expected {expected_size}, detected {total}."
            )
        return digest.hexdigest(), total

    @staticmethod
    def _extract_executables(archive: Path, destination: Path) -> None:
        names = {"uv", "uvx", "uv.exe", "uvx.exe"}
        if str(archive).removesuffix(".part").endswith(".zip"):
            with zipfile.ZipFile(archive) as source:
                for item in source.infolist():
                    basename = Path(item.filename).name
                    if basename not in names or item.is_dir():
                        continue
                    with source.open(item) as value, (destination / basename).open("wb") as out:
                        shutil.copyfileobj(value, out)
            return
        with tarfile.open(archive, mode="r:gz") as source:
            for item in source.getmembers():
                basename = Path(item.name).name
                if basename not in names or not item.isfile():
                    continue
                value = source.extractfile(item)
                if value is None:
                    continue
                with value, (destination / basename).open("wb") as out:
                    shutil.copyfileobj(value, out)
