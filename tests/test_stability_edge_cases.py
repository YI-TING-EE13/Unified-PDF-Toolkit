import errno
import gc
from pathlib import Path
import queue
import tempfile
import unittest
from unittest import mock

import fitz
import psutil
from docx import Document

from src.tools.batch_queue.tool import BatchJob, BatchQueueTool
from src.tools.merger.tool import MergerTool
from src.tools.pdf2word.tool import PDFToWordTool
from src.utils.errors import friendly_error_message
from src.utils.file_ops import resolve_output_path


STRESS_FILE_COUNT = 60
LARGE_PDF_PAGE_COUNT = 1000


def create_pdf(path: Path, *, pages: int = 1, text: str = "PDF Toolkit test") -> None:
    document = fitz.open()
    try:
        for index in range(pages):
            page = document.new_page(width=144, height=144)
            if text:
                page.insert_text((12, 24), f"{text} {index + 1}", fontsize=8)
        document.save(path)
    finally:
        document.close()


def create_zero_page_pdf(path: Path) -> None:
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [] /Count 0 >>",
    )
    content = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{object_number} 0 obj\n".encode("ascii"))
        content.extend(body)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(content)


def drain_messages(tool_queue: queue.Queue) -> list[tuple[str, object]]:
    messages = []
    while True:
        try:
            messages.append(tool_queue.get_nowait())
        except queue.Empty:
            return messages


class AdversarialPdfTests(unittest.TestCase):
    def test_encrypted_pdf_is_rejected_before_conversion(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "encrypted.pdf"
            document = fitz.open()
            document.new_page()
            document.save(
                path,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw="owner-secret",
                user_pw="user-secret",
            )
            document.close()

            with self.assertRaisesRegex(ValueError, "encrypted"):
                PDFToWordTool.preflight_pdf(str(path))

    def test_corrupted_pdf_is_reported_without_crashing_batch_preflight(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "damaged.pdf"
            path.write_bytes(b"%PDF-1.7\nthis is not a valid PDF")

            result = PDFToWordTool.preflight_files([str(path)], "")

            self.assertEqual(result["warnings"], [])
            self.assertEqual(len(result["fatal_errors"]), 1)
            self.assertIn("damaged.pdf", result["fatal_errors"][0])

    def test_zero_page_pdf_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "zero-pages.pdf"
            create_zero_page_pdf(path)

            with self.assertRaisesRegex(ValueError, "no pages"):
                PDFToWordTool.preflight_pdf(str(path))

    def test_blank_page_pdf_is_detected_as_image_only(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "blank.pdf"
            create_pdf(path, text="")

            result = PDFToWordTool.preflight_pdf(str(path))

            self.assertEqual(result["page_count"], 1)
            self.assertTrue(result["image_only"])

    def test_high_page_count_pdf_preflight_and_range_selection(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "large-page-count.pdf"
            create_pdf(path, pages=LARGE_PDF_PAGE_COUNT, text="")

            result = PDFToWordTool.preflight_pdf(str(path), "1,500,1000")

            self.assertEqual(result["page_count"], LARGE_PDF_PAGE_COUNT)
            self.assertEqual(result["selected_page_count"], 3)
            self.assertEqual(
                PDFToWordTool.parse_page_range("1,500,1000", str(path)),
                [0, 499, 999],
            )


class PathAndConflictTests(unittest.TestCase):
    def test_unicode_spaces_emoji_and_long_filename_round_trip(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir) / "中文 space 🚀"
            root.mkdir()
            stem = "報告 with spaces 🚀 " + ("長" * 60)
            source = root / f"{stem}.pdf"
            output = root / f"{stem}.docx"
            create_pdf(source, text="Unicode path content")

            PDFToWordTool.convert_pdf_to_docx(
                str(source),
                str(output),
                mode="Text Only",
            )

            self.assertTrue(output.exists())
            document = Document(output)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            self.assertIn("Unicode path content", text)

    def test_rename_overwrite_and_skip_conflict_policies(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            requested = Path(temp_dir) / "output.pdf"
            requested.write_bytes(b"existing")

            renamed = resolve_output_path(str(requested), "rename")

            self.assertEqual(renamed, str(requested.with_name("output_2.pdf")))
            self.assertEqual(resolve_output_path(str(requested), "overwrite"), str(requested))
            self.assertIsNone(resolve_output_path(str(requested), "skip"))


class IoFailureTests(unittest.TestCase):
    def test_permission_denied_output_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            tool = MergerTool()
            output = Path(temp_dir) / "blocked" / "merged.pdf"
            error = PermissionError(errno.EACCES, "Permission denied", str(output))

            with mock.patch("src.tools.merger.tool.os.makedirs", side_effect=error):
                tool._run_merge(["input.pdf"], str(output), False, "Medium")

            errors = [data for kind, data in drain_messages(tool.queue) if kind == "error"]
            self.assertEqual(len(errors), 1)
            self.assertIn("Permission denied", str(errors[0]))
            self.assertIn("writable output folder", friendly_error_message(error))

    def test_disk_full_and_locked_output_are_reported_and_closed(self):
        failures = (
            OSError(errno.ENOSPC, "No space left on device"),
            PermissionError(
                errno.EACCES,
                "The output file is being used by another process",
            ),
        )
        for failure in failures:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(
                dir=Path.cwd()
            ) as temp_dir:
                output_document = mock.Mock()
                output_document.save.side_effect = failure
                source_document = mock.MagicMock()
                source_document.__enter__.return_value = source_document

                def open_document(path=None):
                    return output_document if path is None else source_document

                tool = MergerTool()
                output = Path(temp_dir) / "merged.pdf"
                with mock.patch(
                    "src.tools.merger.tool.fitz.open",
                    side_effect=open_document,
                ):
                    tool._run_merge(["input.pdf"], str(output), False, "Medium")

                errors = [data for kind, data in drain_messages(tool.queue) if kind == "error"]
                self.assertEqual(len(errors), 1)
                self.assertIn(str(failure), str(errors[0]))
                output_document.close.assert_called_once_with()
                self.assertIn("Suggestion:", friendly_error_message(failure))


class CancellationAndRepeatTests(unittest.TestCase):
    def test_batch_cancellation_stops_before_remaining_jobs(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            jobs = [BatchJob(f"input-{index}.pdf", "PDF to Images") for index in range(10)]
            completed = 0

            def run_single_job(*_args):
                nonlocal completed
                completed += 1
                return [str(Path(temp_dir) / f"output-{completed}.png")]

            with mock.patch(
                "src.core.batch.HeadlessBatchRunner.run_single_job",
                side_effect=run_single_job,
            ):
                result = BatchQueueTool.run_jobs(
                    jobs,
                    temp_dir,
                    cancellation_check=lambda: completed >= 3,
                )

            self.assertTrue(result["cancelled"])
            self.assertEqual(result["success"], 3)
            self.assertEqual(completed, 3)

    def test_repeated_merge_uses_deterministic_renamed_outputs(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.pdf"
            requested = root / "merged.pdf"
            create_pdf(source)

            with mock.patch(
                "src.tools.merger.tool.get_conflict_policy",
                return_value="rename",
            ):
                for _ in range(3):
                    MergerTool()._run_merge(
                        [str(source)],
                        str(requested),
                        False,
                        "Medium",
                    )

            outputs = [requested, root / "merged_2.pdf", root / "merged_3.pdf"]
            self.assertTrue(all(path.exists() for path in outputs))
            for output in outputs:
                with fitz.open(output) as document:
                    self.assertEqual(document.page_count, 1)


class ResourceStressTests(unittest.TestCase):
    def test_sixty_input_merge_releases_files_memory_and_child_processes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir).resolve()
            inputs = []
            for index in range(STRESS_FILE_COUNT):
                path = root / f"stress-{index:03d}.pdf"
                create_pdf(path, text=f"Stress {index}")
                inputs.append(path)

            process = psutil.Process()
            children_before = {child.pid for child in process.children(recursive=True)}
            rss_before = process.memory_info().rss
            if hasattr(process, "num_handles"):
                resource_count_before = process.num_handles()
            else:
                resource_count_before = process.num_fds()

            output = root / "stress-merged.pdf"
            MergerTool()._run_merge(
                [str(path) for path in inputs],
                str(output),
                False,
                "Medium",
            )
            with fitz.open(output) as document:
                self.assertEqual(document.page_count, STRESS_FILE_COUNT)

            gc.collect()
            open_under_test_root = [
                entry.path
                for entry in process.open_files()
                if Path(entry.path).resolve().is_relative_to(root)
            ]
            children_after = {child.pid for child in process.children(recursive=True)}
            rss_after = process.memory_info().rss
            if hasattr(process, "num_handles"):
                resource_count_after = process.num_handles()
            else:
                resource_count_after = process.num_fds()

            self.assertEqual(open_under_test_root, [])
            self.assertEqual(children_after, children_before)
            self.assertLessEqual(resource_count_after, resource_count_before + 12)
            self.assertLess(rss_after - rss_before, 96 * 1024 * 1024)

            for path in inputs:
                path.unlink()
            output.unlink()


if __name__ == "__main__":
    unittest.main()
