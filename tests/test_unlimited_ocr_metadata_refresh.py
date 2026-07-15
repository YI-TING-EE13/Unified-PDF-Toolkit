from __future__ import annotations

import unittest

from scripts.refresh_unlimited_ocr_metadata import (
    detect_conflicts,
    fetch_bytes,
    metadata_content_changed,
    parse_nvidia_driver_minimums,
    parse_pytorch_profiles,
    parse_transformers_requirements,
)


class UnlimitedOcrMetadataRefreshTests(unittest.TestCase):
    def test_requirement_parser_reads_official_style_block(self):
        readme = """
        Requirements tested on python 3.12.3 + CUDA12.9:
        ```
        torch==2.10.0
        torchvision==0.25.0
        transformers==4.57.1
        Pillow==12.1.1
        pymupdf==1.27.2.2
        ```
        """
        value = parse_transformers_requirements(readme)
        self.assertEqual(value["python"], "3.12.3")
        self.assertEqual(value["cuda"], "12.9")
        self.assertEqual(value["packages"]["torch"], "2.10.0")

    def test_pytorch_profile_parser_is_scoped_to_requested_version(self):
        page = """
        torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu126
        torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu130
        <h3 id="v-old">old</h3>
        torch==1.0 --index-url https://download.pytorch.org/whl/cu999
        """
        self.assertEqual(parse_pytorch_profiles(page, "2.10.0"), ("cu126", "cu130"))

    def test_driver_parser_reads_cuda_major_families(self):
        page = "CUDA 13.x &gt;= 580 N/A CUDA 12.x &gt;= 525 &lt; 580"
        self.assertEqual(parse_nvidia_driver_minimums(page), {12: 525, 13: 580})

    def test_conflicts_detect_missing_wheel_and_kernel_pin_disagreement(self):
        conflicts = detect_conflicts(
            "Use kernels==0.9.0 then uv pip install kernels==0.11.7",
            "12.9",
            ("cu126", "cu128", "cu130"),
        )
        self.assertEqual(len(conflicts), 2)
        self.assertIn("no cu129 wheel", conflicts[0])
        self.assertIn("0.9.0", conflicts[1])

    def test_fetch_rejects_non_allowlisted_or_non_https_sources(self):
        with self.assertRaises(ValueError):
            fetch_bytes("http://api.github.com/repos/baidu/Unlimited-OCR")
        with self.assertRaises(ValueError):
            fetch_bytes("https://example.com/metadata.json")

    def test_metadata_drift_ignores_audit_timestamp_only(self):
        current = {"checked_at": "2026-01-01T00:00:00Z", "source_revision": "abc"}
        refreshed = {"checked_at": "2026-07-14T00:00:00Z", "source_revision": "abc"}
        self.assertFalse(metadata_content_changed(current, refreshed))
        refreshed["source_revision"] = "def"
        self.assertTrue(metadata_content_changed(current, refreshed))


if __name__ == "__main__":
    unittest.main()
