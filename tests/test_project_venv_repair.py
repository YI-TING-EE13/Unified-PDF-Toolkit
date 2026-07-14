import contextlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts" / "repair_project_venv.py"


def load_helper_module():
    spec = importlib.util.spec_from_file_location(
        "repair_project_venv",
        HELPER_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ProjectVenvRepairTests(unittest.TestCase):
    def setUp(self):
        self.helper = load_helper_module()

    def test_removes_only_incomplete_project_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            venv = Path(temp_dir) / ".venv"
            site_packages = venv / "Lib" / "site-packages"
            incomplete = site_packages / "pdf_toolkit-0.5.0.dist-info"
            valid = site_packages / "pdf_toolkit-0.6.0b3.dist-info"
            unrelated = site_packages / "another_package-1.0.dist-info"
            (incomplete / "licenses").mkdir(parents=True)
            valid.mkdir(parents=True)
            unrelated.mkdir(parents=True)
            (valid / "RECORD").write_text("valid", encoding="utf-8")

            # The original launcher failure involved Windows read-only
            # attributes. On POSIX, S_IREAD also removes directory search
            # permission, preventing the helper from inspecting RECORD.
            if os.name == "nt":
                os.chmod(incomplete / "licenses", stat.S_IREAD)
                os.chmod(incomplete, stat.S_IREAD)
            removed = self.helper.repair_incomplete_metadata(venv)

            self.assertEqual(removed, [incomplete])
            self.assertFalse(incomplete.exists())
            self.assertTrue(valid.exists())
            self.assertTrue(unrelated.exists())

    def test_supports_posix_versioned_site_packages_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            venv = Path(temp_dir) / ".venv"
            incomplete = (
                venv
                / "lib"
                / "python3.12"
                / "site-packages"
                / "pdf_toolkit-0.3.0.dist-info"
            )
            incomplete.mkdir(parents=True)

            removed = self.helper.repair_incomplete_metadata(venv)

            self.assertEqual(removed, [incomplete])
            self.assertFalse(incomplete.exists())

    def test_deduplicates_case_insensitive_site_packages_aliases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            venv = Path(temp_dir) / ".venv"
            upper = venv / "Lib" / "site-packages"
            lower = venv / "lib" / "site-packages"
            upper.mkdir(parents=True)
            lower.mkdir(parents=True, exist_ok=True)

            def case_insensitive_samefile(current, other):
                return str(current).casefold() == str(other).casefold()

            with mock.patch.object(
                Path,
                "samefile",
                autospec=True,
                side_effect=case_insensitive_samefile,
            ):
                site_packages = list(self.helper.iter_site_packages(venv))

            self.assertEqual(site_packages, [upper])

    def test_missing_environment_is_a_successful_noop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = self.helper.run(
                    ["--venv", str(Path(temp_dir) / "missing-venv")]
                )

            self.assertEqual(code, 0)
            self.assertIn("metadata check passed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
