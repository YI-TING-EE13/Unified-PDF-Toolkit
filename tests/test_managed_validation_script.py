from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import validate_managed_unlimited_ocr as validation


class _FakeImage:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def convert(self, _mode):
        return self

    def copy(self):
        return self


class _FakeProvider:
    def __init__(self, root: Path) -> None:
        self.data_root = root
        self.plan = SimpleNamespace(environment={"CUDA_VISIBLE_DEVICES": "GPU-test"})
        self._worker = object()

    def is_available(self) -> bool:
        return True

    def check_compatibility(self):
        return SimpleNamespace(selected_gpu={"index": 1, "uuid": "GPU-test"})

    def load(self) -> None:
        self._worker = object()

    def unload(self, force: bool = False) -> None:
        self._worker = None

    def benchmark(self, _request):
        return SimpleNamespace(to_dict=lambda: {"success": True})


class ManagedValidationScriptTests(unittest.TestCase):
    def test_nearest_rank_percentile_and_resource_metrics(self):
        self.assertEqual(validation._nearest_rank_percentile([5, 1, 4, 2, 3], 0.95), 5)
        self.assertEqual(
            validation._resource_metrics(
                [{"rss_bytes": 10}, {"rss_bytes": 13}, {"rss_bytes": 12}],
                "rss_bytes",
                "rss_bytes",
            ),
            {
                "rss_bytes_first": 10,
                "rss_bytes_last": 12,
                "rss_bytes_growth": 2,
                "rss_bytes_peak": 13,
            },
        )

    def test_worker_sample_collects_cross_platform_process_metrics(self):
        provider = SimpleNamespace(
            health_check=lambda: SimpleNamespace(
                to_dict=lambda: {
                    "status": "HEALTHY",
                    "loaded": True,
                    "details": {"pid": 42, "allocated_vram_bytes": 99},
                }
            )
        )
        process = SimpleNamespace(
            memory_info=lambda: SimpleNamespace(rss=100),
            num_threads=lambda: 3,
            num_handles=lambda: 4,
            num_fds=lambda: 5,
            open_files=lambda: ["one", "two"],
            children=lambda recursive: [],
        )
        with (
            patch.object(validation.psutil, "pid_exists", return_value=True),
            patch.object(validation.psutil, "Process", return_value=process),
        ):
            sample = validation._worker_sample(provider)
        self.assertEqual(sample["rss_bytes"], 100)
        self.assertEqual(sample["thread_count"], 3)
        self.assertEqual(sample["handles"], 4)
        self.assertEqual(sample["file_descriptors"], 5)
        self.assertEqual(sample["open_files"], 2)

    def test_run_reports_distribution_consistency_and_resource_growth(self):
        with tempfile.TemporaryDirectory() as temporary:
            provider = _FakeProvider(Path(temporary))
            sample_number = 0

            def sample(_provider):
                nonlocal sample_number
                sample_number += 1
                return {
                    "health": "HEALTHY",
                    "loaded": True,
                    "pid": 7,
                    "rss_bytes": 100 + sample_number,
                    "allocated_vram_bytes": 200,
                    "file_descriptors": 5,
                    "thread_count": 2,
                    "open_files": 0,
                    "child_processes": 0,
                }

            case = SimpleNamespace(image_path=Path(temporary) / "case.png")
            result_number = 0

            def run_case(_provider, _case):
                nonlocal result_number
                result_number += 1
                return {
                    "success": True,
                    "elapsed_seconds": float(result_number),
                    "output_sha256": "same-output",
                }

            with (
                patch.object(validation, "UnlimitedOCRProvider", return_value=provider),
                patch.object(validation, "create_validation_suite", return_value=[case]),
                patch.object(validation, "_worker_sample", side_effect=sample),
                patch.object(validation, "_run_case", side_effect=run_case),
                patch.object(validation, "_wait_for_exit", return_value=True),
                patch.object(validation.Image, "open", return_value=_FakeImage()),
                patch.object(validation.psutil, "Process", return_value=SimpleNamespace(children=lambda recursive: [])),
            ):
                code, report = validation.run(
                    argparse.Namespace(stress_iterations=3, reload_cycles=0, output=None)
                )

        self.assertEqual(code, 0)
        self.assertTrue(report["success"])
        self.assertEqual(report["selected_gpu"]["uuid"], "GPU-test")
        self.assertEqual(report["cuda_visible_devices"], "GPU-test")
        self.assertEqual(report["stress"]["success_count"], 3)
        self.assertEqual(report["stress"]["latency_median_seconds"], 3.0)
        self.assertEqual(report["stress"]["latency_p95_seconds"], 4.0)
        self.assertTrue(report["stress"]["output_consistent"])
        self.assertEqual(report["stress"]["file_descriptors_growth"], 0)


if __name__ == "__main__":
    unittest.main()
