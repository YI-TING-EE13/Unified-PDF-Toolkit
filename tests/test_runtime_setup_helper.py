import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts" / "setup_local_unlimited_ocr_runtime.py"


def load_helper_module():
    spec = importlib.util.spec_from_file_location(
        "setup_local_unlimited_ocr_runtime",
        HELPER_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LocalUnlimitedOcrRuntimeSetupHelperTests(unittest.TestCase):
    def setUp(self):
        self.helper = load_helper_module()

    def test_default_plan_uses_uv_and_skips_torch_until_explicit_profile(self):
        args = self.helper.parse_args(["--runtime-path", ".venv-ocr-runtime"])

        plan = self.helper.build_setup_plan(args)

        self.assertEqual(plan.torch_profile, "none")
        self.assertTrue(plan.warnings)
        for command in plan.commands:
            self.assertEqual(command[0], "uv")
            self.assertNotEqual(command[0], "pip")
            self.assertNotEqual(command[:3], ["python", "-m", "pip"])
        joined = "\n".join(" ".join(command) for command in plan.commands)
        self.assertNotIn("pyproject.toml", joined)
        self.assertNotIn("requirements.txt", joined)
        self.assertNotIn("torchvision", joined)

    def test_cuda_profile_adds_explicit_pytorch_index(self):
        args = self.helper.parse_args(["--torch-profile", "cu128"])

        plan = self.helper.build_setup_plan(args)

        joined = "\n".join(" ".join(command) for command in plan.commands)
        self.assertIn("https://download.pytorch.org/whl/cu128", joined)
        self.assertIn("torch", joined)
        self.assertIn("transformers", joined)

    def test_dry_run_prints_commands_and_does_not_execute(self):
        fake_run = mock.Mock()
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = self.helper.run(
                ["--dry-run", "--torch-profile", "cu128"],
                run_func=fake_run,
            )

        text = output.getvalue()
        self.assertEqual(code, 0)
        self.assertFalse(fake_run.called)
        self.assertIn("Mode: dry-run", text)
        self.assertIn("uv venv", text)
        self.assertIn("PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1", text)
        self.assertIn("Model download: not performed", text)

    def test_confirmation_decline_makes_no_runtime_changes(self):
        fake_run = mock.Mock()
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = self.helper.run(
                ["--torch-profile", "cpu"],
                input_func=lambda _prompt: "n",
                run_func=fake_run,
            )

        self.assertEqual(code, 1)
        self.assertFalse(fake_run.called)
        self.assertIn("Cancelled", output.getvalue())


if __name__ == "__main__":
    unittest.main()
