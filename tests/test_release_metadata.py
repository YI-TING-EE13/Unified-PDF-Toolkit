import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts" / "verify_beta_release.py"


def load_helper_module():
    spec = importlib.util.spec_from_file_location("verify_beta_release", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReleaseMetadataTests(unittest.TestCase):
    def setUp(self):
        self.helper = load_helper_module()

    def _source_tree(self, root: Path, *, version: str = "0.6.0b4") -> None:
        (root / "installer").mkdir(parents=True)
        (root / "docs" / "releases").mkdir(parents=True)
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "pdf-toolkit"\nversion = "{version}"\n',
            encoding="utf-8",
        )
        (root / "installer" / "UnifiedPDFToolkit.iss").write_text(
            '#define MyAppVersion "0.6.0-beta.4"\n', encoding="utf-8"
        )
        (root / "docs" / "releases" / "v0.6.0-beta.4.md").write_text(
            "# Release notes\n", encoding="utf-8"
        )

    def test_source_alignment_accepts_matching_beta_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._source_tree(root)
            with mock.patch.object(
                self.helper.importlib_metadata, "version", return_value="0.6.0b4"
            ):
                result = self.helper.verify(root=root, tag="v0.6.0-beta.4")
            self.assertIn("installed_version=0.6.0b4", result)

    def test_source_alignment_rejects_tag_or_installer_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._source_tree(root)
            with self.assertRaises(ValueError):
                self.helper.verify(
                    root=root,
                    tag="v0.6.0-beta.5",
                    check_installed=False,
                )
            (root / "installer" / "UnifiedPDFToolkit.iss").write_text(
                '#define MyAppVersion "0.6.0-beta.3"\n', encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                self.helper.verify(root=root, check_installed=False)

    def test_built_artifact_metadata_must_match_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._source_tree(root)
            dist = root / "dist"
            bundle = root / "bundle"
            metadata = b"Metadata-Version: 2.4\nVersion: 0.6.0b4\n"
            (dist / "installer").mkdir(parents=True)
            (bundle / "_internal" / "pdf_toolkit-0.6.0b4.dist-info").mkdir(parents=True)
            (bundle / "_internal" / "pdf_toolkit-0.6.0b4.dist-info" / "METADATA").write_bytes(metadata)
            wheel = dist / "pdf_toolkit-0.6.0b4-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("pdf_toolkit-0.6.0b4.dist-info/METADATA", metadata)
            sdist = dist / "pdf_toolkit-0.6.0b4.tar.gz"
            pkg_info = root / "PKG-INFO"
            pkg_info.write_bytes(metadata)
            with tarfile.open(sdist, "w:gz") as archive:
                archive.add(pkg_info, arcname="pdf_toolkit-0.6.0b4/PKG-INFO")
            installer = dist / "installer" / "Unified-PDF-Toolkit-Setup-0.6.0-beta.4.exe"
            installer.write_bytes(b"test")
            windows_zip = dist / "Unified-PDF-Toolkit-Windows.zip"
            with zipfile.ZipFile(windows_zip, "w") as archive:
                archive.writestr(
                    "Unified PDF Toolkit/_internal/pdf_toolkit-0.6.0b4.dist-info/METADATA",
                    metadata,
                )

            result = self.helper.verify(
                root=root,
                tag="v0.6.0-beta.4",
                dist_dir=dist,
                bundle=bundle,
                windows_zip=windows_zip,
                check_installed=False,
            )
            self.assertIn("bundle_version=0.6.0b4", result)
            self.assertIn("windows_zip_version=0.6.0b4", result)

    def test_packaged_artifacts_reject_editable_install_direct_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_metadata = (
                root / "bundle" / "_internal" / "pdf_toolkit-0.6.0b4.dist-info"
            )
            bundle_metadata.mkdir(parents=True)
            (bundle_metadata / "METADATA").write_text(
                "Metadata-Version: 2.4\nVersion: 0.6.0b4\n", encoding="utf-8"
            )
            (bundle_metadata / "direct_url.json").write_text(
                '{"url":"file:///C:/private/repository"}', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "direct_url"):
                self.helper._bundle_version(root / "bundle")

            windows_zip = root / "windows.zip"
            with zipfile.ZipFile(windows_zip, "w") as archive:
                prefix = "Unified PDF Toolkit/_internal/pdf_toolkit-0.6.0b4.dist-info"
                archive.writestr(
                    f"{prefix}/METADATA",
                    "Metadata-Version: 2.4\nVersion: 0.6.0b4\n",
                )
                archive.writestr(
                    f"{prefix}/direct_url.json",
                    '{"url":"file:///C:/private/repository"}',
                )
            with self.assertRaisesRegex(ValueError, "direct_url"):
                self.helper._zip_bundle_version(windows_zip)
