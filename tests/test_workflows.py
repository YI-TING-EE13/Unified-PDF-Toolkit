import tempfile
import unittest
from pathlib import Path

import fitz

from src.handlers.pdf import PDFCompressor
from src.tools.merger.tool import MergerTool
from src.tools.page_manager.tool import PageManagerTool
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


if __name__ == "__main__":
    unittest.main()
