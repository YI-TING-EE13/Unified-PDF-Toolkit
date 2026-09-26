import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fitz

from src.core.batch import BatchJob, HeadlessBatchRunner
from src.utils.file_ops import format_size


def _create_pdf(path: Path, pages: int) -> None:
    with fitz.open() as document:
        for page_number in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"Batch report page {page_number + 1}")
        document.save(path)


class BatchReportTests(unittest.TestCase):
    def test_single_and_multi_image_outputs_have_individual_report_sizes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            with mock.patch("src.utils.workflow.add_recent_path"):
                for pages in (2, 1):
                    with self.subTest(pages=pages):
                        source = root / f"source-{pages}.pdf"
                        output_dir = root / f"out-{pages}"
                        _create_pdf(source, pages=pages)
                        result = HeadlessBatchRunner.run_jobs(
                            [
                                BatchJob(
                                    str(source),
                                    "pdf-to-images",
                                    {"dpi": 72, "format": "png"},
                                )
                            ],
                            str(output_dir),
                        )

                        self.assertEqual(result["success"], 1)
                        report_txt = Path(result["report_path"])
                        report_csv = report_txt.with_suffix(".csv")
                        report_json = report_txt.with_suffix(".json")
                        expected_paths = [
                            output_dir / f"{source.stem}_page_{page}.png"
                            for page in range(1, pages + 1)
                        ]
                        payload = json.loads(report_json.read_text(encoding="utf-8"))
                        json_records = payload["records"]
                        with report_csv.open(newline="", encoding="utf-8") as file:
                            csv_records = list(csv.DictReader(file))
                        txt_content = report_txt.read_text(encoding="utf-8")

                        self.assertEqual(
                            [record["output"] for record in json_records],
                            [str(path) for path in expected_paths],
                        )
                        self.assertEqual(payload["summary"]["success"], 1)
                        self.assertEqual(payload["summary"]["failed"], 0)
                        self.assertEqual(payload["summary"]["skipped"], 0)
                        self.assertEqual(payload["summary"]["cancelled"], 0)
                        self.assertEqual(len(csv_records), pages)
                        self.assertEqual(len(json_records), pages)
                        self.assertIn(
                            "Summary: success=1, failed=0, skipped=0, cancelled=0",
                            txt_content,
                        )
                        for path, csv_record, json_record in zip(
                            expected_paths, csv_records, json_records
                        ):
                            actual_size = path.stat().st_size
                            self.assertEqual(json_record["output_size"], actual_size)
                            self.assertEqual(csv_record["output"], str(path))
                            self.assertEqual(csv_record["output_size"], str(actual_size))
                            self.assertIn(f"output: {path}", txt_content)
                            self.assertIn(
                                f"output_size: {format_size(actual_size)}", txt_content
                            )
                            self.assertNotIn("; ", json_record["output"])

    def test_summary_counts_jobs_when_jobs_produce_unequal_artifact_counts(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "out"
            sources = [root / "two-pages.pdf", root / "one-page.pdf"]
            _create_pdf(sources[0], pages=2)
            _create_pdf(sources[1], pages=1)
            jobs = [
                BatchJob(str(source), "pdf-to-images", {"dpi": 72, "format": "png"})
                for source in sources
            ]

            with mock.patch("src.utils.workflow.add_recent_path"):
                result = HeadlessBatchRunner.run_jobs(jobs, str(output_dir))

            self.assertEqual(result["success"], 2)
            report_txt = Path(result["report_path"])
            payload = json.loads(
                report_txt.with_suffix(".json").read_text(encoding="utf-8")
            )
            with report_txt.with_suffix(".csv").open(
                newline="", encoding="utf-8"
            ) as file:
                csv_records = list(csv.DictReader(file))

            self.assertEqual(payload["summary"]["success"], 2)
            self.assertEqual(len(payload["records"]), 3)
            self.assertEqual(len(csv_records), 3)
            self.assertIn(
                "Summary: success=2, failed=0, skipped=0, cancelled=0",
                report_txt.read_text(encoding="utf-8"),
            )

    def test_skipped_multi_output_job_counts_once(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.pdf"
            output_dir = root / "out"
            _create_pdf(source, pages=2)
            job = BatchJob(str(source), "pdf-to-images", {"dpi": 72, "format": "png"})

            with mock.patch("src.utils.workflow.add_recent_path"):
                created = HeadlessBatchRunner.run_jobs([job], str(output_dir))
                skipped = HeadlessBatchRunner.run_jobs(
                    [job], str(output_dir), conflict_policy="skip"
                )

            self.assertEqual(created["success"], 1)
            self.assertEqual(skipped["skipped"], 1)
            report_txt = Path(skipped["report_path"])
            payload = json.loads(
                report_txt.with_suffix(".json").read_text(encoding="utf-8")
            )
            with report_txt.with_suffix(".csv").open(
                newline="", encoding="utf-8"
            ) as file:
                csv_records = list(csv.DictReader(file))

            self.assertEqual(payload["summary"]["success"], 0)
            self.assertEqual(payload["summary"]["skipped"], 1)
            self.assertEqual(len(payload["records"]), 1)
            self.assertEqual(len(csv_records), 1)
            self.assertEqual(csv_records[0]["status"], "skipped")
            self.assertIn(
                "Summary: success=0, failed=0, skipped=1, cancelled=0",
                report_txt.read_text(encoding="utf-8"),
            )

    def test_failed_job_with_partial_output_counts_once(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.pdf"
            output_dir = root / "out"
            partial_output = output_dir / "partial.png"
            _create_pdf(source, pages=2)
            job = BatchJob(str(source), "pdf-to-images", {"dpi": 72, "format": "png"})

            def write_partial_then_fail(_job, _output_dir, _processor, _policy):
                output_dir.mkdir(parents=True, exist_ok=True)
                partial_output.write_bytes(b"partial artifact")
                raise RuntimeError("conversion failed after first artifact")

            with mock.patch("src.utils.workflow.add_recent_path"), mock.patch.object(
                HeadlessBatchRunner,
                "run_single_job",
                side_effect=write_partial_then_fail,
            ):
                result = HeadlessBatchRunner.run_jobs([job], str(output_dir))

            report_txt = Path(result["report_path"])
            payload = json.loads(
                report_txt.with_suffix(".json").read_text(encoding="utf-8")
            )
            with report_txt.with_suffix(".csv").open(
                newline="", encoding="utf-8"
            ) as file:
                csv_records = list(csv.DictReader(file))

            self.assertTrue(partial_output.is_file())
            self.assertEqual(result["failed"], 1)
            self.assertEqual(payload["summary"]["failed"], 1)
            self.assertEqual(len(payload["records"]), 1)
            self.assertEqual(len(csv_records), 1)
            self.assertEqual(csv_records[0]["status"], "failed")
            self.assertIn(
                "Summary: success=0, failed=1, skipped=0, cancelled=0",
                report_txt.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
