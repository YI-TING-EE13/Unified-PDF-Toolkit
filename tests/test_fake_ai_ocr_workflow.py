import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src.ocr import OcrConsentRequiredError
from src.ocr.consent import AdvancedOcrConsent
from src.ocr.unlimited_fake import UNLIMITED_OCR_MODEL_ID, UNLIMITED_OCR_PROVIDER
from src.tools.ai_ocr_test.tool import run_fake_ai_ocr_workflow


def _valid_fake_consent() -> AdvancedOcrConsent:
    return AdvancedOcrConsent.create(
        provider=UNLIMITED_OCR_PROVIDER,
        model_id=UNLIMITED_OCR_MODEL_ID,
        acknowledged_model_download_risk=True,
        acknowledged_custom_code_risk=True,
        acknowledged_gpu_vram_use=True,
        acknowledged_temporary_page_images=True,
    )


class FakeAiOcrWorkflowTests(unittest.TestCase):
    def test_fake_ai_ocr_workflow_writes_deterministic_txt_and_markdown(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            output_dir = root / "out"
            Image.new("RGB", (18, 12), "white").save(image_path)

            result = run_fake_ai_ocr_workflow(
                [str(image_path)],
                str(output_dir),
                ["txt", "md"],
                consent=_valid_fake_consent(),
            )

            self.assertFalse(result.failed)
            self.assertFalse(result.cancelled)
            self.assertEqual(len(result.outputs), 2)
            output_paths = {Path(output.path).suffix: Path(output.path) for output in result.outputs}
            self.assertIn(".txt", output_paths)
            self.assertIn(".md", output_paths)

            txt = output_paths[".txt"].read_text(encoding="utf-8")
            md = output_paths[".md"].read_text(encoding="utf-8")
            self.assertIn("[fake Unlimited-OCR] page=1 size=18x12", txt)
            self.assertIn("No real Unlimited-OCR inference was performed.", txt)
            self.assertIn("# Developer-only Fake AI OCR Output", md)
            self.assertNotIn(str(image_path), txt)
            self.assertNotIn(str(image_path), md)

    def test_fake_ai_ocr_workflow_requires_consent(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            output_dir = root / "out"
            Image.new("RGB", (10, 10), "white").save(image_path)

            with self.assertRaises(OcrConsentRequiredError):
                run_fake_ai_ocr_workflow(
                    [str(image_path)],
                    str(output_dir),
                    ["txt"],
                    consent=None,
                )

            self.assertFalse(output_dir.exists())

    def test_fake_ai_ocr_workflow_can_cancel_before_processing(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            output_dir = root / "out"
            Image.new("RGB", (10, 10), "white").save(image_path)

            result = run_fake_ai_ocr_workflow(
                [str(image_path)],
                str(output_dir),
                ["txt"],
                consent=_valid_fake_consent(),
                cancellation_check=lambda: True,
            )

            self.assertTrue(result.cancelled)
            self.assertFalse(result.outputs)
            self.assertFalse(list(output_dir.glob("*")))

    def test_fake_ai_ocr_tool_imports_no_heavy_ai_runtime(self):
        for module_name in ("torch", "transformers", "sglang"):
            self.assertNotIn(module_name, sys.modules)

    def test_developer_tool_registration_flag_is_explicit(self):
        from src import app

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(app.developer_tools_enabled())
        with mock.patch.dict(os.environ, {"PDF_TOOLKIT_ENABLE_DEV_TOOLS": "1"}):
            self.assertTrue(app.developer_tools_enabled())


if __name__ == "__main__":
    unittest.main()
