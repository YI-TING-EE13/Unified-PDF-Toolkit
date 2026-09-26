import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fitz

from src.core.batch import BatchJob, HeadlessBatchRunner
from src.utils import file_ops
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

    def test_late_skip_collision_on_later_image_preserves_foreign_output(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.pdf"
            output_dir = root / "out"
            _create_pdf(source, pages=2)
            page_two = output_dir / "source_page_2.png"
            original_publish = file_ops._publish_without_replacing

            def inject_page_two_collision(staged_path, destination):
                destination = Path(destination)
                if destination == page_two and not page_two.exists():
                    page_two.parent.mkdir(parents=True, exist_ok=True)
                    page_two.write_bytes(b"foreign page two")
                return original_publish(staged_path, destination)

            with (
                mock.patch("src.utils.workflow.add_recent_path"),
                mock.patch(
                    "src.utils.file_ops._publish_without_replacing",
                    side_effect=inject_page_two_collision,
                ),
            ):
                result = HeadlessBatchRunner.run_jobs(
                    [BatchJob(str(source), "pdf-to-images", {"dpi": 72, "format": "png"})],
                    str(output_dir),
                    conflict_policy="skip",
                )

            report_txt = Path(result["report_path"])
            payload = json.loads(report_txt.with_suffix(".json").read_text(encoding="utf-8"))
            artifacts = [record for record in payload["records"] if record["output"]]

            self.assertEqual(result["success"], 1)
            self.assertEqual(result["failed"], 0)
            self.assertEqual(result["skipped"], 0)
            self.assertEqual([record["output"] for record in artifacts], [str(output_dir / "source_page_1.png")])
            self.assertTrue((output_dir / "source_page_1.png").is_file())
            self.assertEqual(page_two.read_bytes(), b"foreign page two")
            self.assertEqual(list(output_dir.glob(".pdf-toolkit-stage-*")), [])

    def test_failed_job_reports_every_partial_artifact_without_multiplying_failure(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            cases = ((2, 2, 1), (3, 3, 2), (2, 1, 0))

            class FakePixmap:
                def __init__(self, page_number, calls, fail_on_call):
                    self.page_number = page_number
                    self.calls = calls
                    self.fail_on_call = fail_on_call

                def save(self, output_path):
                    self.calls[0] += 1
                    if self.calls[0] == self.fail_on_call:
                        Path(output_path).write_bytes(
                            f"partial-failed-{self.page_number}".encode()
                        )
                        raise RuntimeError("page write failed")
                    Path(output_path).write_bytes(f"partial-{self.page_number}".encode())

            class FakePage:
                def __init__(self, page_number, calls, fail_on_call):
                    self.page_number = page_number
                    self.calls = calls
                    self.fail_on_call = fail_on_call

                def get_pixmap(self, dpi):
                    return FakePixmap(self.page_number, self.calls, self.fail_on_call)

            class FakeDocument:
                def __init__(self, pages, calls, fail_on_call):
                    self.page_count = pages
                    self.calls = calls
                    self.fail_on_call = fail_on_call

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def __getitem__(self, index):
                    return FakePage(index + 1, self.calls, self.fail_on_call)

            for pages, fail_on_call, expected_partial_count in cases:
                with self.subTest(
                    pages=pages,
                    fail_on_call=fail_on_call,
                    expected_partial_count=expected_partial_count,
                ):
                    source = root / f"source-{pages}-{fail_on_call}.pdf"
                    output_dir = root / f"out-{pages}-{fail_on_call}"
                    source.write_bytes(b"fixture")
                    calls = [0]
                    document = FakeDocument(pages, calls, fail_on_call)
                    job = BatchJob(
                        str(source), "pdf-to-images", {"dpi": 72, "format": "png"}
                    )

                    with (
                        mock.patch("src.utils.workflow.add_recent_path"),
                        mock.patch(
                            "src.tools.pdf2word.tool.PDFToWordTool.parse_page_range",
                            return_value=None,
                        ),
                        mock.patch("src.core.batch.fitz.open", return_value=document),
                    ):
                        result = HeadlessBatchRunner.run_jobs([job], str(output_dir))

                    report_txt = Path(result["report_path"])
                    payload = json.loads(
                        report_txt.with_suffix(".json").read_text(encoding="utf-8")
                    )
                    records = payload["records"]
                    artifacts = [record for record in records if record["output"]]
                    failed_rows = [record for record in records if record["status"] == "failed"]

                    self.assertEqual(result["failed"], 1)
                    self.assertEqual(payload["summary"]["failed"], 1)
                    self.assertEqual(payload["summary"]["success"], 0)
                    self.assertEqual(len(artifacts), expected_partial_count)
                    self.assertEqual(len(failed_rows), 1)
                    self.assertEqual(
                        len(list(output_dir.glob("*.png"))), expected_partial_count
                    )
                    self.assertFalse(
                        (output_dir / f"{source.stem}_page_{fail_on_call}.png").exists()
                    )
                    self.assertEqual(list(output_dir.glob(".pdf-toolkit-stage-*")), [])
                    for record in artifacts:
                        output = Path(record["output"])
                        self.assertTrue(output.is_file())
                        self.assertGreater(output.stat().st_size, 0)
                        self.assertEqual(record["output_size"], output.stat().st_size)
                    self.assertIn(
                        "Summary: success=0, failed=1, skipped=0, cancelled=0",
                        report_txt.read_text(encoding="utf-8"),
                    )


if __name__ == "__main__":
    unittest.main()
