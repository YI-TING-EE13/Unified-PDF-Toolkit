import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image

from src.handlers.pdf import PDFCompressor
from src.tools.merger.tool import MergerTool
from src.tools.page_manager.tool import PageManagerTool
from src.tools.pdf2word.tool import PDFToWordTool
from src.tools.splitter.tool import SplitterTool


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

            PDFToWordTool.convert_pdf_to_docx(
                str(pdf_path), str(docx_path), mode="Page Images"
            )

            self.assertTrue(docx_path.exists())
            self.assertGreater(docx_path.stat().st_size, 0)

    def test_pdf_to_word_preflight_detects_text_pdf(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            pdf_path = Path(temp_dir) / "text.pdf"
            self._create_pdf(pdf_path, pages=2)

            report = PDFToWordTool.preflight_pdf(str(pdf_path), "1")

            self.assertEqual(report["page_count"], 2)
            self.assertEqual(report["selected_page_count"], 1)
            self.assertFalse(report["image_only"])

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
