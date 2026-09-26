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
                        self.assertEqual(len(csv_records), pages)
                        self.assertEqual(len(json_records), pages)
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


if __name__ == "__main__":
    unittest.main()
