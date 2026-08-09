import contextlib
import io
import json
import queue
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

import fitz
from PIL import Image

from src.handlers.pdf import PDFCompressor
from src.tools.batch_queue.tool import BatchJob, BatchQueueTool
from src.tools.converter.tool import ConverterTool
from src.tools.image2pdf.tool import Image2PDFTool
from src.tools.merger.tool import MergerTool
from src.tools.page_manager.tool import PageManagerTool
from src.tools.pdf2word.tool import PDFToWordTool
from src.tools.splitter.tool import SplitterTool
from src.utils.diagnostics import DiagnosticCheck, diagnostics_to_text
from src.utils.errors import error_hint, friendly_error_message
from src.utils.workflow import WorkflowReport


class FakeWidget:
    def config(self, **kwargs):
        self.kwargs = kwargs


class FakeEntry:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def delete(self, start, end=None) -> None:
        self.value = ""


class FakeVar:
    def __init__(self, value) -> None:
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


class FakeOutputActions:
    def set_path(self, path: str) -> None:
        self.path = path


class RangeParsingTests(unittest.TestCase):
    def test_splitter_rejects_out_of_bounds_ranges(self):
        splitter = SplitterTool()

        with self.assertRaises(ValueError):
            splitter._parse_ranges("1-3, 9", total_pages=5)

    def test_splitter_parses_ranges(self):
        splitter = SplitterTool()

        self.assertEqual(splitter._parse_ranges("1-2, 4", total_pages=5), [(0, 1), (3, 3)])

    def test_page_manager_preserves_sequence_order(self):
        manager = PageManagerTool()

        self.assertEqual(manager._parse_page_sequence("3,1-2"), [2, 0, 1])
        self.assertEqual(manager._parse_page_sequence("3-1"), [2, 1, 0])


class CompressionWorkflowTests(unittest.TestCase):
    def test_pdf_compressor_accepts_advanced_options(self):
        compressor = PDFCompressor(
            "Medium",
            optimize_images=True,
            max_image_dimension=1200,
            jpeg_quality=65,
        )

        self.assertEqual(compressor.max_image_dimension, 1200)
        self.assertEqual(compressor.jpeg_quality, 65)

    def test_pdf_compressor_resizes_flate_image_without_png_round_trip(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_path = root / "source.png"
            input_path = root / "source.pdf"
            output_path = root / "compressed.pdf"
            Image.effect_noise((600, 400), 80).convert("RGB").save(image_path)

            with fitz.open() as document:
                page = document.new_page(width=600, height=400)
                page.insert_image(page.rect, filename=str(image_path))
                document.save(input_path)

            compressor = PDFCompressor(
                "Medium", max_image_dimension=200, jpeg_quality=65
            )
            self.assertTrue(compressor.compress(str(input_path), str(output_path)))

            with fitz.open(output_path) as document:
                image_info = document[0].get_images(full=True)[0]
                self.assertEqual(image_info[2:4], (200, 133))
                self.assertEqual(image_info[8], "DCTDecode")

    def test_pdf_compressor_skips_decisively_larger_jpeg_candidate(self):
        image = Image.linear_gradient("L").resize((1600, 2200)).convert("RGB")
        source_size = len(zlib.compress(image.tobytes()))

        self.assertFalse(
            PDFCompressor._jpeg_candidate_may_shrink(
                image,
                (1454, 2000),
                quality=70,
                source_size=source_size,
            )
        )

    def test_merge_with_auto_compression_creates_final_pdf(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            inputs = []
            for idx in range(2):
                path = root / f"input_{idx}.pdf"
                doc = fitz.open()
                page = doc.new_page()
                page.insert_text((72, 72), f"Test page {idx + 1}")
                doc.save(path)
                doc.close()
                inputs.append(str(path))

            output_path = root / "merged.pdf"
            tool = MergerTool()
            tool._run_merge(inputs, str(output_path), True, "Medium")

            self.assertTrue(output_path.exists())
            with fitz.open(output_path) as merged:
                self.assertEqual(merged.page_count, 2)
            self.assertFalse(list(root.glob("pdf_toolkit_merge_*.pdf")))

    def test_merge_preview_index_tracks_ordered_pages(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            first_path = root / "first.pdf"
            second_path = root / "second.pdf"

            for path, pages in ((first_path, 2), (second_path, 1)):
                doc = fitz.open()
                for idx in range(pages):
                    page = doc.new_page()
                    page.insert_text((72, 72), f"{path.stem} page {idx + 1}")
                doc.save(path)
                doc.close()

            preview_index = MergerTool.build_preview_index(
                [str(second_path), str(first_path)]
            )

            self.assertEqual(
                preview_index,
                [
                    (str(second_path), 0, 1),
                    (str(first_path), 0, 2),
                    (str(first_path), 1, 2),
                ],
            )


class ResourceLifecycleTests(unittest.TestCase):
    def test_converter_closes_input_document_when_rendering_fails(self):
        count_doc = mock.MagicMock()
        count_doc.__enter__.return_value = count_doc
        count_doc.__len__.return_value = 1
        processing_doc = mock.MagicMock()
        page = mock.Mock()
        page.get_pixmap.side_effect = RuntimeError("render failed")
        processing_doc.__iter__.return_value = iter([page])

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir, mock.patch(
            "src.tools.converter.tool.fitz.open",
            side_effect=[count_doc, processing_doc],
        ):
            ConverterTool()._run_convert(
                [str(Path(temp_dir) / "input.pdf")],
                temp_dir,
                150,
                "png",
            )

        processing_doc.close.assert_called_once_with()

    def test_image_to_pdf_closes_document_when_output_is_skipped(self):
        document = mock.Mock()

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir, mock.patch(
            "src.tools.image2pdf.tool.fitz.open",
            return_value=document,
        ), mock.patch(
            "src.tools.image2pdf.tool.resolve_output_path",
            return_value=None,
        ):
            Image2PDFTool()._run_convert(
                [str(Path(temp_dir) / "input.png")],
                str(Path(temp_dir) / "output.pdf"),
                "Medium",
            )

        document.close.assert_called_once_with()

    def test_merger_closes_output_document_when_an_input_fails(self):
        output_document = mock.Mock()

        def open_document(path=None):
            if path is None:
                return output_document
            raise RuntimeError("invalid input")

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir, mock.patch(
            "src.tools.merger.tool.fitz.open",
            side_effect=open_document,
        ):
            MergerTool()._run_merge(
                [str(Path(temp_dir) / "invalid.pdf")],
                str(Path(temp_dir) / "merged.pdf"),
                False,
                "Medium",
            )

        output_document.close.assert_called_once_with()

    def test_splitter_closes_input_document_after_invalid_range(self):
        input_document = mock.MagicMock()
        input_document.__len__.return_value = 1

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir, mock.patch(
            "src.tools.splitter.tool.fitz.open",
            return_value=input_document,
        ):
            SplitterTool()._run_split(
                str(Path(temp_dir) / "input.pdf"),
                temp_dir,
                "2",
            )

        input_document.close.assert_called_once_with()


class ImageAndPageWorkflowTests(unittest.TestCase):
    def _create_pdf(self, path: Path, pages: int = 2) -> None:
        doc = fitz.open()
        for idx in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"Workflow test page {idx + 1}")
        doc.save(path)
        doc.close()

    def _queue_messages(self, tool_queue: queue.Queue):
        messages = []
        while True:
            try:
                messages.append(tool_queue.get_nowait())
            except queue.Empty:
                return messages

    def test_pdf_to_image_creates_one_image_per_page(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "source.pdf"
            output_dir = root / "images"
            self._create_pdf(pdf_path, pages=2)

            tool = ConverterTool()
            tool._run_convert([str(pdf_path)], str(output_dir), 72, "png")

            output_files = sorted(output_dir.glob("source_page_*.png"))
            self.assertEqual(len(output_files), 2)
            for output_file in output_files:
                with Image.open(output_file) as image:
                    self.assertGreater(image.width, 0)
                    self.assertGreater(image.height, 0)

            messages = self._queue_messages(tool.queue)
            self.assertFalse([data for msg_type, data in messages if msg_type == "error"])

    def test_image_to_pdf_creates_page_per_image(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            image_paths = []
            for idx, color in enumerate(("white", "lightblue"), start=1):
                image_path = root / f"image_{idx}.png"
                Image.new("RGB", (120, 80), color).save(image_path)
                image_paths.append(str(image_path))

            output_path = root / "combined.pdf"
            tool = Image2PDFTool()
            tool._run_convert(image_paths, str(output_path), "Medium")

            self.assertTrue(output_path.exists())
            with fitz.open(output_path) as doc:
                self.assertEqual(doc.page_count, 2)

            messages = self._queue_messages(tool.queue)
            self.assertFalse([data for msg_type, data in messages if msg_type == "error"])

    def test_page_manager_save_writes_modified_pdf(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.pdf"
            output_path = root / "managed.pdf"
            self._create_pdf(source_path, pages=2)

            tool = PageManagerTool()
            tool.doc = fitz.open(source_path)
            try:
                tool.doc[0].set_rotation(90)
                tool._run_save(str(output_path))
            finally:
                tool.doc.close()

            self.assertTrue(output_path.exists())
            with fitz.open(output_path) as doc:
                self.assertEqual(doc.page_count, 2)
                self.assertEqual(doc[0].rotation, 90)

            messages = self._queue_messages(tool.queue)
            self.assertFalse([data for msg_type, data in messages if msg_type == "error"])

    def test_page_manager_delete_rotate_reorder_insert_extract(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.pdf"
            insert_path = root / "insert.pdf"
            extract_path = root / "extract.pdf"
            self._create_pdf(source_path, pages=3)
            self._create_pdf(insert_path, pages=1)

            tool = PageManagerTool()
            tool.doc = fitz.open(source_path)
            tool.current_pdf_path = str(source_path)
            tool.total_pages = 3
            tool.preview_scale = FakeWidget()
            tool.preview_var = FakeVar(1)
            tool.status_lbl = FakeWidget()
            tool._update_preview = lambda page_num: None

            tool.delete_entry = FakeEntry("2")
            tool._delete_pages()
            self.assertEqual(tool.total_pages, 2)

            tool.rotate_entry = FakeEntry("1")
            tool.angle_var = FakeVar("90")
            tool._rotate_pages()
            self.assertEqual(tool.doc[0].rotation, 90)

            tool.reorder_entry = FakeEntry("2,1")
            tool._reorder_pages()
            self.assertEqual(tool.total_pages, 2)

            tool.insert_after_var = FakeVar(1)
            with mock.patch(
                "src.tools.page_manager.tool.filedialog.askopenfilename",
                return_value=str(insert_path),
            ):
                tool._insert_pdf()
            self.assertEqual(tool.total_pages, 3)

            tool.extract_entry = FakeEntry("1,3")
            tool.output_actions = FakeOutputActions()
            with mock.patch(
                "src.tools.page_manager.tool.filedialog.asksaveasfilename",
                return_value=str(extract_path),
            ):
                with mock.patch("src.tools.page_manager.tool.messagebox.showinfo"):
                    tool._extract_pages()

            with fitz.open(extract_path) as extracted:
                self.assertEqual(extracted.page_count, 2)
            tool.doc.close()


class ReportWorkflowTests(unittest.TestCase):
    def test_workflow_report_writes_txt_csv_and_json(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.txt"
            output_path = root / "output.txt"
            source_path.write_text("input", encoding="utf-8")
            output_path.write_text("output", encoding="utf-8")

            report = WorkflowReport("Test Tool", str(root), options={"mode": "test"})
            report.add(str(source_path), str(output_path))
            txt_path = Path(report.write())
            csv_path = txt_path.with_suffix(".csv")
            json_path = txt_path.with_suffix(".json")

            self.assertTrue(txt_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["tool"], "Test Tool")
            self.assertEqual(payload["summary"]["success"], 1)
            self.assertEqual(payload["records"][0]["source"], str(source_path))


class ErrorAndDiagnosticsTests(unittest.TestCase):
    def test_error_hints_cover_common_recovery_paths(self):
        self.assertIn("Tesseract OCR", error_hint("Tesseract is not installed"))
        self.assertIn("page range", error_hint("Page range 9 is out of bounds"))
        self.assertIn("Suggestion:", friendly_error_message("Permission denied"))

    def test_gui_startup_error_message_is_user_safe(self):
        from src.app import gui_startup_error_message

        message = gui_startup_error_message()

        self.assertIn("Tk/Tcl", message)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("init.tcl", message)
        self.assertNotIn("C:/", message)
        self.assertNotIn("\\", message)

    def test_manual_smoke_sanitizers_redact_local_paths(self):
        from scripts.manual_document_ocr_gui_smoke import sanitize_message as gui_sanitize
        from scripts.manual_unlimited_ocr_local_check import sanitize_message as ocr_sanitize

        message = f"Failed at {Path.home()} with C:/other/path/source.pdf"

        for sanitize in (gui_sanitize, ocr_sanitize):
            sanitized = sanitize(message)
            self.assertNotIn(str(Path.home()), sanitized)
            self.assertNotIn("C:/other/path/source.pdf", sanitized)
            self.assertIn("<path>", sanitized)

    def test_diagnostics_text_includes_suggestions(self):
        text = diagnostics_to_text(
            [
                DiagnosticCheck(
                    "Tesseract executable",
                    "warning",
                    "not found on PATH",
                    "Install Tesseract OCR.",
                )
            ]
        )

        self.assertIn("[WARNING] Tesseract executable", text)
        self.assertIn("Suggestion: Install Tesseract OCR.", text)


class BatchQueueWorkflowTests(unittest.TestCase):
    def _create_pdf(self, path: Path, pages: int = 2) -> None:
        doc = fitz.open()
        for idx in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"Batch queue page {idx + 1}")
        doc.save(path)
        doc.close()

    def test_batch_queue_converts_pdf_to_images(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "source.pdf"
            output_dir = root / "out"
            self._create_pdf(pdf_path, pages=2)

            result = BatchQueueTool.run_jobs(
                [
                    BatchJob(
                        str(pdf_path),
                        "PDF to Images",
                        {"dpi": 72, "format": "png", "page_range": "1-2"},
                    )
                ],
                str(output_dir),
            )

            self.assertEqual(result["success"], 1)
            self.assertTrue((output_dir / "source_page_1.png").exists())
            self.assertTrue((output_dir / "source_page_2.png").exists())
            self.assertTrue(Path(result["report_path"]).exists())

    def test_batch_queue_converts_pdf_to_word_text_only(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "source.pdf"
            output_dir = root / "out"
            self._create_pdf(pdf_path, pages=1)

            result = BatchQueueTool.run_jobs(
                [BatchJob(str(pdf_path), "PDF to Word - Text Only", {"page_range": "1"})],
                str(output_dir),
            )

            self.assertEqual(result["success"], 1)
            self.assertTrue((output_dir / "source.docx").exists())


class PDFToWordWorkflowTests(unittest.TestCase):
    def _create_pdf(self, path: Path, pages: int = 2) -> None:
        doc = fitz.open()
        for idx in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"Word conversion test page {idx + 1}")
        doc.save(path)
        doc.close()

    def test_pdf_to_word_page_range_parser(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            pdf_path = Path(temp_dir) / "range.pdf"
            self._create_pdf(pdf_path, pages=5)

            self.assertEqual(
                PDFToWordTool.parse_page_range("1-2, 4", str(pdf_path)),
                [0, 1, 3],
            )

            with self.assertRaises(ValueError):
                PDFToWordTool.parse_page_range("6", str(pdf_path))

    def test_pdf_to_word_creates_docx(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "source.pdf"
            docx_path = root / "source.docx"
            self._create_pdf(pdf_path, pages=1)

            PDFToWordTool.convert_pdf_to_docx(str(pdf_path), str(docx_path))

            self.assertTrue(docx_path.exists())
            self.assertGreater(docx_path.stat().st_size, 0)

    def test_pdf_to_word_preserve_layout_suppresses_source_path_console_logs(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "source.pdf"
            docx_path = root / "source.docx"
            self._create_pdf(pdf_path, pages=1)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                PDFToWordTool.convert_pdf_to_docx(str(pdf_path), str(docx_path))

            captured = stdout.getvalue() + stderr.getvalue()
            self.assertTrue(docx_path.exists())
            self.assertNotIn(str(pdf_path), captured)
            self.assertNotIn("Start to convert", captured)

    def test_pdf_to_word_text_only_creates_docx(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "source.pdf"
            docx_path = root / "text_only.docx"
            self._create_pdf(pdf_path, pages=1)

            PDFToWordTool.convert_pdf_to_docx(
                str(pdf_path), str(docx_path), mode="Text Only"
            )

            self.assertTrue(docx_path.exists())
            self.assertGreater(docx_path.stat().st_size, 0)

    def test_pdf_to_word_page_images_creates_docx(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "source.pdf"
            docx_path = root / "page_images.docx"
            self._create_pdf(pdf_path, pages=1)

            with fitz.open(pdf_path) as source:
                expected = source[0].get_pixmap(dpi=150, alpha=False)

            with mock.patch(
                "src.tools.pdf2word.tool.Image.frombytes",
                side_effect=AssertionError("Page Images should use the pixmap PNG encoder."),
            ):
                PDFToWordTool.convert_pdf_to_docx(
                    str(pdf_path), str(docx_path), mode="Page Images"
                )

            self.assertTrue(docx_path.exists())
            self.assertGreater(docx_path.stat().st_size, 0)
            with zipfile.ZipFile(docx_path) as archive:
                media_names = [name for name in archive.namelist() if name.startswith("word/media/")]
                self.assertEqual(len(media_names), 1)
                with Image.open(io.BytesIO(archive.read(media_names[0]))) as embedded:
                    self.assertEqual(embedded.size, (expected.width, expected.height))
                    self.assertEqual(embedded.convert("RGB").tobytes(), expected.samples)

    def test_pdf_to_word_ocr_text_creates_docx_with_mocked_tesseract(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "source.pdf"
            docx_path = root / "ocr_text.docx"
            self._create_pdf(pdf_path, pages=1)

            with mock.patch("pytesseract.image_to_string", return_value="OCR text") as ocr_mock:
                PDFToWordTool.convert_pdf_to_docx(
                    str(pdf_path),
                    str(docx_path),
                    mode="OCR Text",
                    ocr_lang="eng+chi_tra",
                    ocr_dpi=150,
                    ocr_preprocess="Threshold",
                )

            self.assertTrue(docx_path.exists())
            self.assertGreater(docx_path.stat().st_size, 0)
            self.assertEqual(ocr_mock.call_args.kwargs["lang"], "eng+chi_tra")
            self.assertEqual(ocr_mock.call_args.args[0].mode, "1")

    def test_pdf_to_word_ocr_preprocess_options(self):
        image = Image.new("RGB", (20, 20), "gray")

        self.assertEqual(PDFToWordTool.prepare_ocr_image(image, "None").mode, "RGB")
        self.assertEqual(PDFToWordTool.prepare_ocr_image(image, "Grayscale").mode, "L")
        self.assertEqual(PDFToWordTool.prepare_ocr_image(image, "Threshold").mode, "1")

    def test_pdf_to_word_preflight_detects_text_pdf(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            pdf_path = Path(temp_dir) / "text.pdf"
            self._create_pdf(pdf_path, pages=2)

            with mock.patch("src.tools.pdf2word.tool.fitz.open", wraps=fitz.open) as open_mock:
                report = PDFToWordTool.preflight_pdf(str(pdf_path), "1")

            self.assertEqual(report["page_count"], 2)
            self.assertEqual(report["selected_page_count"], 1)
            self.assertFalse(report["image_only"])
            open_mock.assert_called_once_with(str(pdf_path))

    def test_pdf_to_word_preflight_warns_image_only_pdf(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            img_path = root / "image.png"
            pdf_path = root / "image_only.pdf"

            Image.new("RGB", (120, 80), "white").save(img_path)
            doc = fitz.open()
            page = doc.new_page(width=120, height=80)
            page.insert_image(fitz.Rect(0, 0, 120, 80), filename=str(img_path))
            doc.save(pdf_path)
            doc.close()

            report = PDFToWordTool.preflight_pdf(str(pdf_path))

            self.assertTrue(report["image_only"])

    def test_pdf_to_word_preflight_files_reports_bad_range(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            pdf_path = Path(temp_dir) / "range.pdf"
            self._create_pdf(pdf_path, pages=2)

            report = PDFToWordTool.preflight_files([str(pdf_path)], "9")

            self.assertTrue(report["fatal_errors"])


if __name__ == "__main__":
    unittest.main()
