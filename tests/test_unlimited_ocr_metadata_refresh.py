from __future__ import annotations

import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import refresh_unlimited_ocr_metadata as refresh
from scripts.refresh_unlimited_ocr_metadata import (
    build_candidate,
    detect_conflicts,
    fetch_bytes,
    metadata_content_changed,
    _profile_driver_minimum_versions,
    parse_nvidia_driver_minimums,
    parse_pytorch_profiles,
    parse_transformers_requirements,
)
from src.ocr.deployment.metadata import (
    bundled_metadata_path,
    load_compatibility_metadata,
)


class UnlimitedOcrMetadataRefreshTests(unittest.TestCase):
    @staticmethod
    def _source_patches(current):
        source_revision = current["source_revision"]
        model_revision = current["model_revision"]
        transformer = current["backends"]["transformers"]
        artifacts = current["model_artifacts"]

        readme = "\n".join(
            (
                f"Requirements tested on python {transformer['tested_python']} + "
                f"CUDA{transformer['tested_cuda']}:",
                "```",
                *(
                    f"{name}=={version}"
                    for name, version in transformer["packages"].items()
                ),
                "```",
                "kernels==0.9.0",
                "kernels==0.11.7",
            )
        )
        pytorch_page = "\n".join(
            f"torch=={transformer['packages']['torch']} torchvision=="
            f"{transformer['packages']['torchvision']} --index-url "
            f"https://download.pytorch.org/whl/{profile}"
            for profile in ("cu126", "cu128", "cu130")
        ) + '\n<h3 id="v-old">'

        weight_file = artifacts["weight_file"]
        other_required_files = [
            name for name in artifacts["required_files"] if name != weight_file
        ]
        other_required_bytes = (
            artifacts["required_download_bytes"] - artifacts["weight_bytes"]
        )
        sizes = {name: 1 for name in other_required_files}
        sizes[other_required_files[-1]] = (
            other_required_bytes - len(other_required_files) + 1
        )
        siblings = [
            {"rfilename": name, "size": artifacts["weight_bytes"]}
            if name == weight_file
            else {"rfilename": name, "size": sizes[name]}
            for name in artifacts["required_files"]
        ]
        siblings[artifacts["required_files"].index(weight_file)].update(
            {
                "blobId": artifacts["weight_blob_sha"],
                "lfs": {"sha256": artifacts["weight_sha256"]},
            }
        )
        siblings.append(
            {
                "rfilename": "unmatched-model-data.bin",
                "size": artifacts["reported_total_bytes"]
                - artifacts["required_download_bytes"],
            }
        )

        json_responses = {
            "https://api.github.com/repos/baidu/Unlimited-OCR": {
                "default_branch": "main"
            },
            "https://api.github.com/repos/baidu/Unlimited-OCR/branches/main": {
                "commit": {"sha": source_revision}
            },
            "https://huggingface.co/api/models/baidu/Unlimited-OCR?blobs=true": {
                "sha": model_revision,
                "siblings": siblings,
            },
        }
        text_responses = {
            f"https://raw.githubusercontent.com/baidu/Unlimited-OCR/"
            f"{source_revision}/README.md": readme,
            "https://pytorch.org/get-started/previous-versions/": pytorch_page,
            "https://docs.nvidia.com/deploy/cuda-compatibility/"
            "minor-version-compatibility.html": (
                "CUDA 13.x >= 580 N/A CUDA 12.x >= 525 < 580"
            ),
            current["sources"]["nvidia_cuda_12_release_notes"]: (
                "CUDA 12.x >=525.60.13 >=528.33"
            ),
        }

        def fetch_json(url):
            if url not in json_responses:
                raise AssertionError(f"Unexpected JSON source requested: {url}")
            return json_responses[url]

        def fetch_text(url):
            if url not in text_responses:
                raise AssertionError(f"Unexpected text source requested: {url}")
            return text_responses[url]

        return (
            patch.object(refresh, "fetch_json", side_effect=fetch_json),
            patch.object(refresh, "fetch_text", side_effect=fetch_text),
        )

    def _assert_candidate_contract(self, candidate, current):
        self.assertEqual(candidate["schema_version"], "2.0")
        profiles = candidate["backends"]["transformers"]["pytorch_profiles"]
        expected = {
            "cu126": {"windows": "528.33", "linux": "525.60.13"},
            "cu128": {"windows": "528.33", "linux": "525.60.13"},
            "cu130": {"windows": "580", "linux": "580"},
        }
        self.assertEqual(set(profiles), set(expected))
        for profile, minimums in expected.items():
            with self.subTest(profile=profile):
                self.assertEqual(
                    set(profiles[profile]["minimum_driver_versions"]),
                    {"windows", "linux"},
                )
                self.assertEqual(
                    profiles[profile]["minimum_driver_versions"], minimums
                )
                self.assertNotIn("minimum_driver_major", profiles[profile])
        self.assertNotIn("driver_families", candidate)

        def contains_key(value, expected_key):
            if isinstance(value, dict):
                return expected_key in value or any(
                    contains_key(child, expected_key) for child in value.values()
                )
            if isinstance(value, list):
                return any(contains_key(child, expected_key) for child in value)
            return False

        self.assertFalse(contains_key(candidate, "minimum_driver_major"))
        for required_key in (
            "model",
            "model_revision",
            "model_artifacts",
            "resource_estimates",
            "uv_bootstrap",
            "backends",
        ):
            self.assertIn(required_key, candidate)
        self.assertEqual(candidate["model"], current["model"])
        self.assertEqual(candidate["model_revision"], current["model_revision"])
        self.assertEqual(candidate["resource_estimates"], current["resource_estimates"])
        self.assertEqual(candidate["uv_bootstrap"], current["uv_bootstrap"])
        self.assertEqual(
            candidate["backends"]["transformers"]["packages"],
            current["backends"]["transformers"]["packages"],
        )

    def test_build_candidate_emits_complete_schema_2_driver_contract(self):
        current = load_compatibility_metadata()
        metadata_path = bundled_metadata_path()
        before = hashlib.sha256(metadata_path.read_bytes()).digest()
        fetch_json_patch, fetch_text_patch = self._source_patches(current)

        with fetch_json_patch, fetch_text_patch:
            candidate, _conflicts = build_candidate(current)

        self._assert_candidate_contract(candidate, current)
        self.assertEqual(hashlib.sha256(metadata_path.read_bytes()).digest(), before)

    def test_json_cli_emits_the_candidate_without_writing_reviewed_metadata(self):
        current = load_compatibility_metadata()
        metadata_path = bundled_metadata_path()
        before = hashlib.sha256(metadata_path.read_bytes()).digest()
        fetch_json_patch, fetch_text_patch = self._source_patches(current)
        stdout = io.StringIO()

        with fetch_json_patch, fetch_text_patch:
            expected_candidate, _conflicts = build_candidate(current)
            with redirect_stdout(stdout):
                exit_code = refresh.main(["--json"])

        self.assertEqual(exit_code, 0)
        output = json.loads(stdout.getvalue())
        candidate = output["candidate"]
        self._assert_candidate_contract(candidate, current)
        expected_candidate.pop("checked_at")
        candidate.pop("checked_at")
        self.assertEqual(candidate, expected_candidate)
        self.assertEqual(hashlib.sha256(metadata_path.read_bytes()).digest(), before)

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

    def test_driver_parser_reads_precise_platform_thresholds(self):
        compatibility_page = "CUDA 13.x &gt;= 580 N/A CUDA 12.x &gt;= 525 &lt; 580"
        release_notes = (
            "<tr><td>CUDA 12.x</td><td>&gt;=525.60.13</td>"
            "<td>&gt;=528.33</td></tr>"
        )
        self.assertEqual(
            parse_nvidia_driver_minimums(compatibility_page, release_notes),
            {
                "12": {"linux": "525.60.13", "windows": "528.33"},
                "13": {"linux": "580", "windows": "580"},
            },
        )

    def test_profile_threshold_builder_rejects_unreviewed_cuda_family(self):
        thresholds = {
            "12": {"linux": "525.60.13", "windows": "528.33"},
            "13": {"linux": "580", "windows": "580"},
        }
        self.assertEqual(
            _profile_driver_minimum_versions("cu128", thresholds),
            {"linux": "525.60.13", "windows": "528.33"},
        )
        with self.assertRaises(ValueError):
            _profile_driver_minimum_versions("cu110", thresholds)

    def test_driver_parser_fails_closed_when_exact_table_is_missing(self):
        with self.assertRaises(ValueError):
            parse_nvidia_driver_minimums(
                "CUDA 13.x >= 580 CUDA 12.x >= 525",
                "CUDA 12.x driver is at least 525",
            )

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
