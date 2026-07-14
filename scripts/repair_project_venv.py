"""Repair incomplete project-package metadata in a uv virtual environment.

An interrupted editable-package uninstall can leave a ``*.dist-info`` folder
without its ``RECORD`` file. Package managers cannot uninstall that metadata
cleanly on the next sync, so remove only those incomplete project-owned
folders before asking uv to synchronize the environment again.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Iterable, Sequence


DEFAULT_VENV = Path(".venv")
PROJECT_METADATA_GLOB = "pdf_toolkit-*.dist-info"


def _same_directory(left: Path, right: Path) -> bool:
    """Return whether two existing paths identify the same directory."""

    try:
        return left.samefile(right)
    except OSError:
        return left == right


def iter_site_packages(venv_path: Path) -> Iterable[Path]:
    """Yield existing site-packages folders for Windows and POSIX venvs."""

    candidates = [
        venv_path / "Lib" / "site-packages",
        venv_path / "lib" / "site-packages",
        *sorted((venv_path / "lib").glob("python*/site-packages")),
    ]
    seen: list[Path] = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if any(_same_directory(candidate, existing) for existing in seen):
            continue
        seen.append(candidate)
        yield candidate


def _remove_readonly(func, path: str, _exc_info) -> None:
    """Make a path writable and retry a failed shutil.rmtree operation."""

    os.chmod(path, stat.S_IRWXU)
    func(path)


def find_incomplete_metadata(venv_path: Path) -> list[Path]:
    """Return project dist-info folders that do not contain RECORD."""

    incomplete: list[Path] = []
    for site_packages in iter_site_packages(venv_path):
        for metadata_dir in sorted(site_packages.glob(PROJECT_METADATA_GLOB)):
            if metadata_dir.is_dir() and not (metadata_dir / "RECORD").is_file():
                incomplete.append(metadata_dir)
    return incomplete


def repair_incomplete_metadata(venv_path: Path) -> list[Path]:
    """Remove incomplete project metadata and return the removed folders."""

    removed: list[Path] = []
    for metadata_dir in find_incomplete_metadata(venv_path):
        shutil.rmtree(metadata_dir, onerror=_remove_readonly)
        removed.append(metadata_dir)
    return removed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair incomplete PDF Toolkit metadata before uv sync."
    )
    parser.add_argument(
        "--venv",
        type=Path,
        default=DEFAULT_VENV,
        help="Virtual environment folder. Default: .venv",
    )
    return parser.parse_args(argv)


def run(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        removed = repair_incomplete_metadata(args.venv)
    except OSError as exc:
        print(
            "Error: Could not repair incomplete PDF Toolkit package metadata: "
            f"{exc}",
            file=sys.stderr,
        )
        print(
            "Close any Python or PDF Toolkit processes using .venv, then run "
            "the launcher again.",
            file=sys.stderr,
        )
        return 1

    if removed:
        print(f"Repaired {len(removed)} incomplete package metadata folder(s).")
    else:
        print("Environment metadata check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
