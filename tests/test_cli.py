import contextlib
import io
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import fitz

from src.cli import _human_plan, main
from src.core.batch import BatchJob, HeadlessBatchRunner
from src.utils.diagnostics import _tesseract_language_check


def create_pdf(path: Path, pages: int = 1) -> None:
    document = fitz.open()
    try:
        for page_number in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"CLI page {page_number + 1}")
        document.save(path)
    finally:
        document.close()


class CommandLineTests(unittest.TestCase):
    def test_blocked_ocr_plan_is_actionable_and_does_not_offer_setup(self):
        payload = {
            "compatibility": {
                "status": "UNSUPPORTED",
                "confidence": 0.9,
                "risk_level": "BLOCKED",
                "recommended_backend": "none",
                "recommended_runtime": None,
                "estimated_download_size": 12 * 1024**3,
                "estimated_disk_usage": 20 * 1024**3,
                "estimated_vram_requirement": 12 * 1024**3,
                "reasons": ["Hardware requirements are not met."],
                "requirements_met": ["Linux is eligible."],
                "requirements_missing": ["VRAM is insufficient."],
                "required_changes": [],
            },
            "plan": {
                "plan_id": "blocked-plan",
                "runtime_root": "/tmp/private-runtime",
                "blocked_reasons": ["Compatibility status is UNSUPPORTED."],
            },
            "consent_summary": {"setup_allowed": False},
        }
        output = _human_plan(payload)
        self.assertIn("Can this device install Unlimited-OCR safely now? No", output)
        self.assertIn("Setup allowed: no", output)
        self.assertIn("VRAM is insufficient", output)
        self.assertIn("fallback architecture remains intact", output)

    def test_importing_cli_does_not_load_tkinter(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import src.cli; raise SystemExit('tkinter' in sys.modules)",
            ],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_managed_ocr_json_error_is_structured(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "ocr",
                    "setup",
                    "--plan-id",
                    "not-the-current-plan",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["error_code"], "INVALID_REQUEST")
        self.assertEqual(stderr.getvalue(), "")

    def test_manifest_resolves_relative_paths_and_generates_json_result(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "來源 file 😀.pdf"
            manifest = root / "jobs.json"
            create_pdf(source, pages=2)
            manifest.write_text(
                json.dumps(
                    {
                        "output_dir": "output",
                        "conflict_policy": "rename",
                        "jobs": [
                            {
                                "source": source.name,
                                "operation": "pdf-to-images",
                                "options": {"dpi": 72, "format": "png", "page_range": "1-2"},
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(["batch", str(manifest), "--json", "--quiet"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["success"], 1)
            self.assertEqual(payload["failed"], 0)
            self.assertTrue((root / "output" / "來源 file 😀_page_1.png").exists())
            self.assertTrue(Path(payload["report_path"]).exists())
            self.assertEqual(stderr.getvalue(), "")

    def test_invalid_manifest_returns_usage_error_without_traceback(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            manifest = Path(temp_dir) / "bad.json"
            manifest.write_text('{"jobs": [', encoding="utf-8")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                exit_code = main(["batch", str(manifest), "--output-dir", temp_dir])

            self.assertEqual(exit_code, 2)
            self.assertIn("Invalid JSON manifest", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_invalid_manifest_conflict_type_returns_usage_error(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.pdf"
            manifest = root / "bad-conflict.json"
            create_pdf(source)
            manifest.write_text(
                json.dumps(
                    {
                        "output_dir": "out",
                        "conflict_policy": ["rename"],
                        "jobs": [{"source": source.name, "operation": "pdf-to-images"}],
                    }
                ),
                encoding="utf-8",
            )
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                exit_code = main(["batch", str(manifest), "--quiet"])

            self.assertEqual(exit_code, 2)
            self.assertIn("conflict_policy", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_failed_input_returns_nonzero_and_writes_report(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            stdout = io.StringIO()
            stderr = io.StringIO()
            missing = Path(temp_dir) / "missing.pdf"

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(
                    [
                        "pdf-to-images",
                        str(missing),
                        "--output-dir",
                        str(Path(temp_dir) / "out"),
                        "--quiet",
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("1 failed", stdout.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_main_restores_sigint_handler(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            previous = signal.getsignal(signal.SIGINT)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                main(
                    [
                        "pdf-to-images",
                        str(Path(temp_dir) / "missing.pdf"),
                        "--output-dir",
                        str(Path(temp_dir) / "out"),
                        "--quiet",
                    ]
                )

            self.assertEqual(signal.getsignal(signal.SIGINT), previous)

    def test_dpi_help_is_bounded_and_does_not_expand_every_choice(self):
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "pdf-to-images", "--help"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("72..600", result.stdout)
        self.assertLess(len(result.stdout), 3000)

    def test_stop_on_error_does_not_start_later_jobs(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            valid = root / "valid.pdf"
            create_pdf(valid)
            result = HeadlessBatchRunner.run_jobs(
                [
                    BatchJob(str(root / "missing.pdf"), "pdf-to-images"),
                    BatchJob(str(valid), "pdf-to-images", {"dpi": 72}),
                ],
                str(root / "out"),
                stop_on_error=True,
            )

            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["success"], 0)
            self.assertFalse((root / "out" / "valid_page_1.png").exists())

    def test_invalid_programmatic_operation_is_recorded_in_report(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            source = Path(temp_dir) / "source.pdf"
            create_pdf(source)

            result = HeadlessBatchRunner.run_jobs(
                [BatchJob(str(source), "not-a-real-operation")],
                str(Path(temp_dir) / "out"),
            )

            self.assertEqual(result["failed"], 1)
            self.assertTrue(Path(result["report_path"]).exists())

    def test_manifest_ocr_rejects_extreme_dpi_before_rendering(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            source = Path(temp_dir) / "source.pdf"
            create_pdf(source)

            result = HeadlessBatchRunner.run_jobs(
                [
                    BatchJob(
                        str(source),
                        "pdf-to-word-ocr",
                        {"ocr_dpi": 100_000},
                    )
                ],
                str(Path(temp_dir) / "out"),
            )

            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["success"], 0)

    def test_cancellation_during_final_job_returns_cancelled(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            source = Path(temp_dir) / "source.pdf"
            create_pdf(source)
            cancelled = False

            def run_job(*_args):
                nonlocal cancelled
                cancelled = True
                return [str(Path(temp_dir) / "output.png")]

            with mock.patch(
                "src.core.batch.HeadlessBatchRunner.run_single_job",
                side_effect=run_job,
            ):
                result = HeadlessBatchRunner.run_jobs(
                    [BatchJob(str(source), "pdf-to-images")],
                    str(Path(temp_dir) / "out"),
                    cancellation_check=lambda: cancelled,
                )

            self.assertTrue(result["cancelled"])


class TesseractDiagnosticTests(unittest.TestCase):
    def test_missing_chinese_language_data_is_actionable(self):
        with mock.patch("pytesseract.get_languages", return_value=["eng", "osd"]):
            check = _tesseract_language_check("tesseract")

        self.assertEqual(check.status, "warning")
        self.assertIn("eng", check.detail)
        self.assertIn("chi_tra.traineddata", check.suggestion)

    def test_english_and_chinese_language_data_pass(self):
        with mock.patch("pytesseract.get_languages", return_value=["eng", "chi_tra"]):
            check = _tesseract_language_check("tesseract")

        self.assertEqual(check.status, "ok")


if __name__ == "__main__":
    unittest.main()
