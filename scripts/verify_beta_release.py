"""Verify controlled-beta source and built-artifact version alignment."""

from __future__ import annotations

import argparse
from importlib import metadata as importlib_metadata
from pathlib import Path
import re
import tarfile
import tomllib
from typing import Sequence
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "pdf-toolkit"


def source_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def installer_version(root: Path) -> str:
    text = (root / "installer" / "UnifiedPDFToolkit.iss").read_text(encoding="utf-8")
    match = re.search(r'^#define MyAppVersion "([^"]+)"$', text, re.MULTILINE)
    if not match:
        raise ValueError("Installer MyAppVersion was not found.")
    return match.group(1)


def expected_tag(version: str) -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)b(\d+)", version)
    if not match:
        raise ValueError(f"Unsupported controlled-beta package version: {version}")
    return f"v{match.group(1)}-beta.{match.group(2)}"


def _metadata_version(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="strict")
    match = re.search(r"^Version: (.+)$", text, re.MULTILINE)
    if not match:
        raise ValueError("Package metadata has no Version field.")
    return match.group(1).strip()


def _wheel_version(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"Wheel must contain one METADATA file: {path}")
        return _metadata_version(archive.read(metadata_names[0]))


def _sdist_version(path: Path) -> str:
    with tarfile.open(path, "r:gz") as archive:
        members = [item for item in archive.getmembers() if item.name.endswith("/PKG-INFO")]
        if len(members) != 1:
            raise ValueError(f"Source distribution must contain one PKG-INFO: {path}")
        extracted = archive.extractfile(members[0])
        if extracted is None:
            raise ValueError(f"Unable to read PKG-INFO: {path}")
        return _metadata_version(extracted.read())


def _bundle_version(bundle: Path) -> str:
    metadata_files = list(bundle.rglob("pdf_toolkit-*.dist-info/METADATA"))
    if len(metadata_files) != 1:
        raise ValueError("Packaged app must contain one pdf_toolkit dist-info METADATA file.")
    if (metadata_files[0].parent / "direct_url.json").exists():
        raise ValueError("Packaged app must not expose editable-install direct_url metadata.")
    return _metadata_version(metadata_files[0].read_bytes())


def _zip_bundle_version(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [
            name for name in archive.namelist()
            if re.search(r"pdf_toolkit-[^/]+\.dist-info/METADATA$", name)
        ]
        if len(metadata_names) != 1:
            raise ValueError("Windows ZIP must contain one pdf_toolkit METADATA file.")
        direct_url_names = [
            name for name in archive.namelist()
            if re.search(r"pdf_toolkit-[^/]+\.dist-info/direct_url\.json$", name)
        ]
        if direct_url_names:
            raise ValueError("Windows ZIP must not expose editable-install direct_url metadata.")
        return _metadata_version(archive.read(metadata_names[0]))


def verify(
    *,
    root: Path,
    tag: str | None = None,
    dist_dir: Path | None = None,
    bundle: Path | None = None,
    windows_zip: Path | None = None,
    check_installed: bool = True,
) -> list[str]:
    version = source_version(root)
    display_version = installer_version(root)
    intended_tag = expected_tag(version)
    expected_display = intended_tag.removeprefix("v")
    if display_version != expected_display:
        raise ValueError(
            f"Installer version {display_version} does not match package version {version}."
        )
    if tag is not None and tag != intended_tag:
        raise ValueError(f"Tag {tag} does not match expected tag {intended_tag}.")
    notes = root / "docs" / "releases" / f"{intended_tag}.md"
    if not notes.is_file():
        raise ValueError(f"Release notes are missing: {notes}")

    results = [
        f"source_version={version}",
        f"installer_version={display_version}",
        f"tag={intended_tag}",
        f"release_notes={notes.name}",
    ]
    if check_installed:
        installed = importlib_metadata.version(PROJECT_NAME)
        if installed != version:
            raise ValueError(f"Installed CLI metadata {installed} does not match {version}.")
        results.append(f"installed_version={installed}")

    if dist_dir is not None:
        wheel = dist_dir / f"pdf_toolkit-{version}-py3-none-any.whl"
        sdist = dist_dir / f"pdf_toolkit-{version}.tar.gz"
        installer = dist_dir / "installer" / f"Unified-PDF-Toolkit-Setup-{display_version}.exe"
        for path in (wheel, sdist, installer):
            if not path.is_file():
                raise ValueError(f"Expected release artifact is missing: {path}")
        if _wheel_version(wheel) != version:
            raise ValueError("Wheel metadata version does not match source.")
        if _sdist_version(sdist) != version:
            raise ValueError("Source distribution metadata version does not match source.")
        results.extend((f"wheel={wheel.name}", f"sdist={sdist.name}", f"installer={installer.name}"))

    if bundle is not None:
        if _bundle_version(bundle) != version:
            raise ValueError("Packaged app metadata version does not match source.")
        results.append(f"bundle_version={version}")
    if windows_zip is not None:
        if _zip_bundle_version(windows_zip) != version:
            raise ValueError("Windows ZIP metadata version does not match source.")
        results.append(f"windows_zip_version={version}")
    return results


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--dist-dir", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--windows-zip", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    for item in verify(
        root=ROOT,
        tag=args.tag,
        dist_dir=args.dist_dir,
        bundle=args.bundle,
        windows_zip=args.windows_zip,
    ):
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
