from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import psutil

from src.ocr.consent import create_advanced_ocr_consent
from src.ocr.deployment.cache import ModelCacheManager
from src.ocr.deployment.compatibility import CompatibilityEngine
from src.ocr.deployment.consent import (
    REQUIRED_INSTALL_ACKNOWLEDGEMENTS,
    DeploymentConsent,
    build_consent_summary,
)
from src.ocr.deployment.environment import (
    EnvironmentInspector,
    _decode_command_output,
)
from src.ocr.deployment.errors import (
    DeploymentFailure,
    ErrorCode,
    classify_exception,
)
from src.ocr.deployment.metadata import (
    CompatibilityMetadataError,
    load_compatibility_metadata,
    metadata_age_days,
    validate_compatibility_metadata,
)
from src.ocr.deployment.models import (
    CompatibilityStatus,
    EnvironmentReport,
    InstallStepRecord,
    InstallStage,
    RuntimeBackend,
)
from src.ocr.deployment.orchestrator import (
    CancellationToken,
    DeploymentCleanup,
    SetupOrchestrator,
)
from src.ocr.deployment.provider_worker import (
    _benchmark_classification,
    _bounded_int,
    _require_child,
)
from src.ocr.deployment.providers import (
    BasicOCRProvider,
    OCRProviderRouter,
    PersistentRuntimeWorker,
    _worker_error_code,
)
from src.ocr.deployment.resolver import EnvironmentResolver
from src.ocr.deployment.runtime_tasks import (
    _benchmark_classification as _setup_benchmark_classification,
    _normalize_for_comparison,
)
from src.ocr.deployment.validation_assets import create_validation_suite
from src.ocr.models import OcrEngine, OcrPageResult, OcrRequest, OcrResult


def _environment(**overrides):
    values = {
        "schema_version": "1.0",
        "generated_at": "2026-07-14T00:00:00+00:00",
        "os": {
            "system": "Windows",
            "release": "11",
            "version": "test",
            "machine": "AMD64",
            "architecture": "64bit",
            "platform": "Windows-test",
            "is_wsl": False,
            "wsl_distribution": None,
        },
        "cpu": {"model": "test", "architecture": "AMD64", "physical_cores": 8, "logical_cores": 16},
        "memory": {"total_bytes": 64 * 1024**3, "available_bytes": 48 * 1024**3},
        "gpu": (
            {
                "index": 0,
                "vendor": "NVIDIA",
                "name": "RTX test",
                "vram_total_bytes": 12 * 1024**3,
                "vram_free_bytes": 11 * 1024**3,
                "driver_version": "610.47",
                "compute_capability": "8.6",
            },
        ),
        "nvidia_driver": {
            "available": True,
            "driver_version": "610.47",
            "cuda_driver_api_version": "13.3",
        },
        "cuda": {"driver_api_version": "13.3", "toolkit_installed": True, "toolkit_version": "12.2"},
        "python": {
            "version": "3.12.12",
            "tools": {"uv": {"available": True}, "pip": {"available": True}, "conda": {"available": False}},
        },
        "pytorch": {"installed": False, "cuda_available": False, "devices": []},
        "storage": {"free_bytes": 128 * 1024**3, "writable_parent": True, "data_root": "test"},
        "runtime": {"frozen": False},
        "containers": {"docker": {"available": False}, "wsl2": {"available": True}},
        "recommendation": {},
        "warnings": (),
    }
    values.update(overrides)
    return EnvironmentReport(**values)


def _acknowledgements():
    return {key: True for key in REQUIRED_INSTALL_ACKNOWLEDGEMENTS}


class MetadataTests(unittest.TestCase):
    def test_pyinstaller_bundles_private_runtime_entrypoint_scripts(self):
        spec = (Path(__file__).parents[1] / "pdf-toolkit.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn('ocr_deployment_root / "runtime_tasks.py"', spec)
        self.assertIn('ocr_deployment_root / "provider_worker.py"', spec)
        self.assertIn('"src/ocr/deployment"', spec)

    def test_bundled_metadata_is_complete_and_pinned(self):
        metadata = load_compatibility_metadata()
        self.assertEqual(metadata["model"], "baidu/Unlimited-OCR")
        self.assertEqual(len(metadata["source_revision"]), 40)
        self.assertEqual(len(metadata["model_revision"]), 40)
        self.assertEqual(len(metadata["model_artifacts"]["weight_sha256"]), 64)
        self.assertGreater(metadata["model_artifacts"]["required_download_bytes"], 6_000_000_000)

    def test_metadata_rejects_missing_or_unpinned_values(self):
        metadata = load_compatibility_metadata()
        broken = copy.deepcopy(metadata)
        broken["model_revision"] = "main"
        with self.assertRaises(CompatibilityMetadataError):
            validate_compatibility_metadata(broken)
        del broken["model_revision"]
        with self.assertRaises(CompatibilityMetadataError):
            validate_compatibility_metadata(broken)

    def test_metadata_rejects_untrusted_package_index(self):
        metadata = load_compatibility_metadata()
        metadata["backends"]["transformers"]["pytorch_profiles"]["cu130"][
            "index_url"
        ] = "https://example.com/fake-wheels"
        with self.assertRaises(CompatibilityMetadataError):
            validate_compatibility_metadata(metadata)

    def test_metadata_age_is_non_negative(self):
        self.assertGreaterEqual(metadata_age_days(load_compatibility_metadata()), 0)


class EnvironmentInspectorTests(unittest.TestCase):
    def test_missing_command_is_reported_without_exception(self):
        inspector = EnvironmentInspector(command_timeout=1)
        result = inspector._run(["pdf-toolkit-command-that-does-not-exist"])
        self.assertFalse(result["available"])
        self.assertIsNone(result["returncode"])

    def test_utf16_command_output_is_decoded(self):
        value = "預設版本: 2".encode("utf-16")
        self.assertEqual(_decode_command_output(value), "預設版本: 2")

    def test_inspector_shape_with_stubbed_collectors(self):
        inspector = EnvironmentInspector(data_root=Path(tempfile.gettempdir()) / "ocr-inspector-test")
        with (
            patch.object(inspector, "_gpu_info", return_value=([], {"available": False})),
            patch.object(inspector, "_os_info", return_value={"system": "TestOS"}),
            patch.object(inspector, "_cpu_info", return_value={"model": "CPU"}),
            patch.object(inspector, "_memory_info", return_value={"total_bytes": 1}),
            patch.object(inspector, "_cuda_info", return_value={"toolkit_installed": False}),
            patch.object(inspector, "_python_info", return_value={"version": "3.12"}),
            patch.object(inspector, "_pytorch_info", return_value={"installed": False}),
            patch.object(inspector, "_storage_info", return_value={"free_bytes": 1}),
            patch.object(inspector, "_runtime_info", return_value={"frozen": False}),
            patch.object(inspector, "_container_info", return_value={"docker": {"available": False}}),
        ):
            report = inspector.inspect().to_dict()
        self.assertEqual(report["os"]["system"], "TestOS")
        self.assertEqual(report["gpu"], ())
        self.assertEqual(report["recommendation"]["status"], "NOT_EVALUATED")


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.metadata = load_compatibility_metadata()

    def evaluate(self, environment=None, metadata=None):
        return CompatibilityEngine(metadata or self.metadata).evaluate(environment or _environment())

    def test_supported_windows_nvidia_requires_private_changes(self):
        result = self.evaluate()
        self.assertEqual(result.status, CompatibilityStatus.SUPPORTED_WITH_CHANGES)
        self.assertEqual(result.recommended_backend, RuntimeBackend.TRANSFORMERS)
        self.assertIn("cu130", result.recommended_runtime)
        self.assertEqual(result.risk_level.value, "MEDIUM")

    def test_linux_driver_uses_cu128_when_cuda13_driver_is_unavailable(self):
        env = _environment(
            os={**_environment().os, "system": "Linux", "platform": "Linux-test"},
            nvidia_driver={"available": True, "driver_version": "550.90"},
        )
        result = self.evaluate(env)
        self.assertEqual(result.status, CompatibilityStatus.SUPPORTED_WITH_CHANGES)
        self.assertIn("cu128", result.recommended_runtime)

    def test_conda_is_safe_fallback_when_uv_is_unavailable(self):
        env = _environment(
            python={
                "version": "3.11.9",
                "tools": {
                    "uv": {"available": False},
                    "pip": {"available": True},
                    "conda": {"available": True},
                },
            }
        )
        result = self.evaluate(env)
        self.assertEqual(result.status, CompatibilityStatus.SUPPORTED_WITH_CHANGES)
        self.assertIn("private conda", result.recommended_runtime)
        with tempfile.TemporaryDirectory() as temporary:
            plan = EnvironmentResolver(self.metadata).resolve(
                result, data_root=Path(temporary)
            )
        self.assertEqual(plan.environment_manager, "conda")
        self.assertEqual(plan.commands[0][0:2], ("conda", "create"))

    def test_missing_environment_manager_is_not_auto_supported(self):
        env = _environment(
            python={
                "version": "3.12.12",
                "tools": {
                    "uv": {"available": False},
                    "pip": {"available": True},
                    "conda": {"available": False},
                },
            }
        )
        result = self.evaluate(env)
        self.assertEqual(result.status, CompatibilityStatus.UNKNOWN)
        self.assertIsNone(result.recommended_runtime)

    def test_no_nvidia_gpu_is_unsupported(self):
        env = _environment(
            gpu=({"vendor": "AMD", "name": "Radeon", "vram_total_bytes": 24 * 1024**3},),
            nvidia_driver={"available": False, "driver_version": None},
        )
        result = self.evaluate(env)
        self.assertEqual(result.status, CompatibilityStatus.UNSUPPORTED)
        self.assertEqual(result.recommended_backend, RuntimeBackend.NONE)

    def test_apple_silicon_is_not_claimed_as_supported(self):
        env = _environment(
            os={**_environment().os, "system": "Darwin", "machine": "arm64", "platform": "macOS"},
            gpu=({"vendor": "Apple", "name": "Apple M4", "vram_total_bytes": None},),
            nvidia_driver={"available": False, "driver_version": None},
        )
        self.assertEqual(self.evaluate(env).status, CompatibilityStatus.UNSUPPORTED)

    def test_wsl2_is_experimental_even_with_good_gpu(self):
        env = _environment(os={**_environment().os, "system": "Linux", "is_wsl": True})
        self.assertEqual(self.evaluate(env).status, CompatibilityStatus.EXPERIMENTAL)

    def test_largest_nvidia_gpu_is_selected(self):
        small = dict(_environment().gpu[0], name="small", vram_total_bytes=8 * 1024**3)
        large = dict(_environment().gpu[0], name="large", vram_total_bytes=24 * 1024**3)
        result = self.evaluate(_environment(gpu=(small, large)))
        self.assertTrue(any("large" in item for item in result.requirements_met))

    def test_insufficient_vram_is_unsupported(self):
        gpu = dict(_environment().gpu[0], vram_total_bytes=8 * 1024**3)
        self.assertEqual(self.evaluate(_environment(gpu=(gpu,))).status, CompatibilityStatus.UNSUPPORTED)

    def test_unknown_vram_never_becomes_supported(self):
        gpu = dict(_environment().gpu[0], vram_total_bytes=None)
        self.assertEqual(self.evaluate(_environment(gpu=(gpu,))).status, CompatibilityStatus.UNKNOWN)

    def test_old_compute_capability_is_unsupported(self):
        gpu = dict(_environment().gpu[0], compute_capability="7.5")
        self.assertEqual(self.evaluate(_environment(gpu=(gpu,))).status, CompatibilityStatus.UNSUPPORTED)

    def test_insufficient_ram_or_disk_is_unsupported(self):
        self.assertEqual(
            self.evaluate(_environment(memory={"total_bytes": 8 * 1024**3})).status,
            CompatibilityStatus.UNSUPPORTED,
        )
        self.assertEqual(
            self.evaluate(
                _environment(storage={"free_bytes": 10 * 1024**3, "writable_parent": True})
            ).status,
            CompatibilityStatus.UNSUPPORTED,
        )

    def test_readonly_data_root_is_unsupported(self):
        result = self.evaluate(
            _environment(storage={"free_bytes": 100 * 1024**3, "writable_parent": False})
        )
        self.assertEqual(result.status, CompatibilityStatus.UNSUPPORTED)

    def test_old_driver_is_unsupported(self):
        result = self.evaluate(
            _environment(nvidia_driver={"available": True, "driver_version": "510.0"})
        )
        self.assertEqual(result.status, CompatibilityStatus.UNSUPPORTED)

    def test_missing_driver_version_remains_unknown(self):
        result = self.evaluate(
            _environment(nvidia_driver={"available": True, "driver_version": None})
        )
        self.assertEqual(result.status, CompatibilityStatus.UNKNOWN)

    def test_stale_metadata_blocks_automatic_support(self):
        metadata = copy.deepcopy(self.metadata)
        metadata["checked_at"] = "2020-01-01T00:00:00Z"
        result = self.evaluate(metadata=metadata)
        self.assertEqual(result.status, CompatibilityStatus.UNKNOWN)
        self.assertEqual(result.risk_level.value, "BLOCKED")

    def test_upstream_conflict_is_exposed(self):
        result = self.evaluate()
        self.assertTrue(result.conflicts)
        self.assertIn("no cu129 wheel", result.conflicts[0])


class ResolverAndConsentTests(unittest.TestCase):
    def setUp(self):
        self.metadata = load_compatibility_metadata()
        self.compatibility = CompatibilityEngine(self.metadata).evaluate(_environment())

    def test_resolver_has_no_system_changes_or_shell_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = EnvironmentResolver(self.metadata).resolve(
                self.compatibility, data_root=Path(temporary)
            )
        self.assertTrue(plan.executable)
        self.assertFalse(plan.requires_admin)
        self.assertEqual(plan.system_changes, ())
        self.assertTrue(all(command[0] == "uv" for command in plan.commands))
        self.assertNotIn("CUDA_PATH", plan.environment)

    def test_consent_requires_every_explicit_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = EnvironmentResolver(self.metadata).resolve(
                self.compatibility, data_root=Path(temporary)
            )
        acknowledgements = _acknowledgements()
        acknowledgements["custom_code"] = False
        with self.assertRaises(ValueError):
            DeploymentConsent.create(
                plan=plan,
                metadata_revision=self.compatibility.metadata_revision,
                acknowledgements=acknowledgements,
            )

    def test_consent_invalidates_when_plan_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = EnvironmentResolver(self.metadata).resolve(
                self.compatibility, data_root=Path(temporary)
            )
        consent = DeploymentConsent.create(
            plan=plan,
            metadata_revision=self.compatibility.metadata_revision,
            acknowledgements=_acknowledgements(),
        )
        self.assertTrue(
            consent.is_valid_for(plan, metadata_revision=self.compatibility.metadata_revision)
        )
        self.assertFalse(
            consent.is_valid_for(
                replace(plan, plan_id="different"),
                metadata_revision=self.compatibility.metadata_revision,
            )
        )

    def test_consent_summary_discloses_local_and_system_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = EnvironmentResolver(self.metadata).resolve(
                self.compatibility, data_root=Path(temporary)
            )
        summary = build_consent_summary(self.compatibility, plan)
        self.assertTrue(summary["local_only"])
        self.assertFalse(summary["data_leaves_device"])
        self.assertFalse(summary["driver_update_included"])
        self.assertFalse(summary["system_cuda_change_included"])
        self.assertGreater(summary["estimated_download_bytes"], 10 * 1024**3)
        self.assertEqual(summary["recommended_ram_bytes"], 32 * 1024**3)


class CacheTests(unittest.TestCase):
    def _small_metadata(self, content: bytes):
        metadata = copy.deepcopy(load_compatibility_metadata())
        metadata["model_artifacts"].update(
            {
                "weight_file": "weight.bin",
                "weight_bytes": len(content),
                "weight_sha256": hashlib.sha256(content).hexdigest(),
                "allow_patterns": ["*.json"],
                "required_files": ["weight.bin", "config.json"],
            }
        )
        return metadata

    def test_cache_verifies_size_and_sha256(self):
        content = b"safe-model"
        revision = "a" * 40
        with tempfile.TemporaryDirectory() as temporary:
            manager = ModelCacheManager(Path(temporary))
            snapshot = manager.snapshot_path(revision)
            snapshot.mkdir(parents=True)
            (snapshot / "weight.bin").write_bytes(content)
            (snapshot / "config.json").write_text("{}", encoding="utf-8")
            status = manager.verify(revision, self._small_metadata(content))
        self.assertTrue(status.complete)

    def test_cache_rejects_corruption(self):
        content = b"safe-model"
        revision = "b" * 40
        with tempfile.TemporaryDirectory() as temporary:
            manager = ModelCacheManager(Path(temporary))
            snapshot = manager.snapshot_path(revision)
            snapshot.mkdir(parents=True)
            (snapshot / "weight.bin").write_bytes(b"corrupt!!!")
            (snapshot / "config.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(DeploymentFailure) as caught:
                manager.verify(revision, self._small_metadata(content))
        self.assertEqual(caught.exception.error.error_code, "MODEL_INTEGRITY_FAILED")

    def test_cache_cleanup_is_revision_bound(self):
        revision = "c" * 40
        with tempfile.TemporaryDirectory() as temporary:
            manager = ModelCacheManager(Path(temporary))
            snapshot = manager.snapshot_path(revision)
            snapshot.mkdir(parents=True)
            (snapshot / "file").write_text("x", encoding="utf-8")
            self.assertTrue(manager.uninstall_snapshot(revision))
            self.assertFalse(snapshot.exists())
            with self.assertRaises(ValueError):
                manager.snapshot_path("../outside")


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.metadata = load_compatibility_metadata()
        self.environment = _environment()
        self.compatibility = CompatibilityEngine(self.metadata).evaluate(self.environment)

    @staticmethod
    def _success_runner(command, environment, timeout, cancellation):
        return {"returncode": 0, "stdout": "", "stderr": ""}

    def _build(self, root: Path, **kwargs):
        plan = EnvironmentResolver(self.metadata).resolve(self.compatibility, data_root=root)
        consent = DeploymentConsent.create(
            plan=plan,
            metadata_revision=self.compatibility.metadata_revision,
            acknowledgements=_acknowledgements(),
        )
        return plan, consent, SetupOrchestrator(
            plan=plan,
            compatibility=self.compatibility,
            environment=self.environment,
            consent=consent,
            metadata=self.metadata,
            state_root=root / "state",
            command_runner=kwargs.pop("command_runner", self._success_runner),
            **kwargs,
        )

    def test_missing_or_changed_consent_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, consent, _orchestrator = self._build(root)
            invalid = replace(consent, plan_id="different")
            orchestrator = SetupOrchestrator(
                plan=plan,
                compatibility=self.compatibility,
                environment=self.environment,
                consent=invalid,
                metadata=self.metadata,
                state_root=root / "state-invalid",
                command_runner=self._success_runner,
            )
            with self.assertRaises(DeploymentFailure):
                orchestrator.run(until=InstallStage.PRECHECK)
            self.assertFalse((root / "state-invalid").exists())

    def test_precheck_uses_specific_unsupported_gpu_error(self):
        environment = _environment(
            gpu=({"vendor": "AMD", "name": "Radeon", "vram_total_bytes": 24 * 1024**3},),
            nvidia_driver={"available": False, "driver_version": None},
        )
        compatibility = CompatibilityEngine(self.metadata).evaluate(environment)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = EnvironmentResolver(self.metadata).resolve(
                compatibility, data_root=root
            )
            consent = DeploymentConsent.create(
                plan=plan,
                metadata_revision=compatibility.metadata_revision,
                acknowledgements=_acknowledgements(),
            )
            orchestrator = SetupOrchestrator(
                plan=plan,
                compatibility=compatibility,
                environment=environment,
                consent=consent,
                metadata=self.metadata,
                state_root=root / "state",
                command_runner=self._success_runner,
            )
            with self.assertRaises(DeploymentFailure) as caught:
                orchestrator.run(until=InstallStage.PRECHECK)
        self.assertEqual(caught.exception.error.error_code, "NO_SUPPORTED_GPU")

    def test_journal_resumes_completed_stages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _plan, _consent, first = self._build(root)
            journal = first.run(until=InstallStage.CREATE_ISOLATED_ENV)
            create_step = next(
                step for step in journal["steps"] if step["stage"] == "CREATE_ISOLATED_ENV"
            )
            self.assertEqual(create_step["status"], "SUCCEEDED")
            _plan, _consent, second = self._build(root)
            journal = second.run(until=InstallStage.INSTALL_DEPENDENCIES)
            create_step = next(
                step for step in journal["steps"] if step["stage"] == "CREATE_ISOLATED_ENV"
            )
            install_step = next(
                step for step in journal["steps"] if step["stage"] == "INSTALL_DEPENDENCIES"
            )
            self.assertEqual(create_step["attempts"], 1)
            self.assertEqual(install_step["status"], "SUCCEEDED")

    def test_cancelled_command_marks_step_and_keeps_resume_state(self):
        token = CancellationToken()

        def cancel_runner(command, environment, timeout, cancellation):
            token.cancel()
            return {"returncode": 0, "stdout": "", "stderr": ""}

        with tempfile.TemporaryDirectory() as temporary:
            _plan, _consent, orchestrator = self._build(
                Path(temporary), command_runner=cancel_runner, cancellation=token
            )
            journal = orchestrator.run(until=InstallStage.CREATE_ISOLATED_ENV)
        step = next(
            item for item in journal["steps"] if item["stage"] == "CREATE_ISOLATED_ENV"
        )
        self.assertEqual(step["status"], "CANCELLED")

    def test_pre_requested_pause_is_recorded_without_running_commands(self):
        token = CancellationToken()
        token.pause()
        with tempfile.TemporaryDirectory() as temporary:
            _plan, _consent, orchestrator = self._build(Path(temporary), cancellation=token)
            journal = orchestrator.run(until=InstallStage.PRECHECK)
        self.assertEqual(journal["steps"][0]["status"], "PAUSED")

    def test_active_install_lock_blocks_duplicate_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _plan, _consent, orchestrator = self._build(root)
            orchestrator.state_root.mkdir(parents=True)
            orchestrator.lock_path.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "process_created_at": psutil.Process().create_time(),
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(DeploymentFailure) as caught:
                orchestrator.run(until=InstallStage.PRECHECK)
        self.assertEqual(caught.exception.error.error_code, "SUBPROCESS_CRASH")

    def test_stale_reboot_lock_is_removed_instead_of_blocking_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _plan, _consent, orchestrator = self._build(root)
            orchestrator.state_root.mkdir(parents=True)
            orchestrator.lock_path.write_text(
                json.dumps({"pid": os.getpid(), "process_created_at": 0}),
                encoding="utf-8",
            )
            journal = orchestrator.run(until=InstallStage.PRECHECK)
        self.assertEqual(journal["steps"][0]["status"], "SUCCEEDED")

    def test_transient_private_environment_failure_retries_by_policy(self):
        calls = 0

        def transient_runner(command, environment, timeout, cancellation):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"returncode": 1, "stdout": "", "stderr": "process crashed"}
            return {"returncode": 0, "stdout": "", "stderr": ""}

        policy = {
            "max_attempts": 2,
            "initial_delay_seconds": 0.0,
            "maximum_delay_seconds": 0.0,
        }
        with tempfile.TemporaryDirectory() as temporary, patch(
            "src.ocr.deployment.orchestrator._retry_policy", return_value=policy
        ):
            _plan, _consent, orchestrator = self._build(
                Path(temporary), command_runner=transient_runner
            )
            journal = orchestrator.run(until=InstallStage.CREATE_ISOLATED_ENV)
        step = next(
            item for item in journal["steps"] if item["stage"] == "CREATE_ISOLATED_ENV"
        )
        self.assertEqual(calls, 2)
        self.assertEqual(step["attempts"], 2)
        self.assertEqual(step["status"], "SUCCEEDED")
        self.assertEqual(len(step["details"]["retry_errors"]), 1)

    def test_runtime_task_receives_expected_terms_without_raw_output_logging(self):
        received = []

        def runner(command, environment, timeout, cancellation):
            received.append(list(command))
            return {
                "returncode": 0,
                "stdout": 'PDF_TOOLKIT_RESULT={"success": true, "output_sha256": "abc"}\n',
                "stderr": "",
            }

        with tempfile.TemporaryDirectory() as temporary:
            _plan, _consent, orchestrator = self._build(
                Path(temporary), command_runner=runner
            )
            result = orchestrator._run_runtime_task(
                "ocr",
                image=Path(temporary) / "sample.png",
                output_dir=Path(temporary) / "output",
                expected_terms=("中英文", "Document ID"),
                timeout=1,
            )
        self.assertTrue(result["success"])
        self.assertEqual(received[0].count("--expected-term"), 2)
        self.assertNotIn("中英文", result)

    def test_cleanup_requires_confirmation_and_stays_inside_data_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = EnvironmentResolver(self.metadata).resolve(self.compatibility, data_root=root)
            runtime = Path(plan.runtime_root)
            runtime.mkdir(parents=True)
            (runtime / "marker").write_text("managed", encoding="utf-8")
            cleanup = DeploymentCleanup(plan)
            with self.assertRaises(ValueError):
                cleanup.uninstall(confirmed=False)
            result = cleanup.uninstall(confirmed=True)
            self.assertTrue(result["runtime_removed"])
            self.assertTrue(root.exists())


class ProviderAndAssetTests(unittest.TestCase):
    def test_persistent_worker_discards_stale_responses_and_closes_handles(self):
        import io
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worker = PersistentRuntimeWorker(
                python_executable=Path(os.sys.executable),
                model_root=root / "models",
                session_root=root / "sessions",
                environment={},
                log_path=root / "worker.log",
            )
            worker._responses.put(RuntimeError("stale worker failure"))
            worker._discard_stale_responses()
            self.assertTrue(worker._responses.empty())

            process = Mock()
            process.poll.return_value = 0
            process.stdin = io.StringIO()
            process.stdout = io.StringIO()
            reader = Mock()
            log_handle = io.StringIO()
            worker.process = process
            worker._reader_thread = reader
            worker._log_handle = log_handle

            worker._finalize_stopped_process()

            reader.join.assert_called_once_with(timeout=2)
            self.assertTrue(process.stdin.closed)
            self.assertTrue(process.stdout.closed)
            self.assertTrue(log_handle.closed)
            self.assertIsNone(worker.process)

    def test_basic_provider_benchmark_reads_typed_result_metadata(self):
        class Backend:
            def recognize(self, request):
                return OcrResult(
                    engine=OcrEngine.TESSERACT,
                    pages=[OcrPageResult(1, "recognized")],
                    metadata={"dependency_versions": {"tesseract": "5.5.0"}},
                )

        result = BasicOCRProvider(backend=Backend()).benchmark(
            OcrRequest(engine=OcrEngine.TESSERACT, images=[])
        )
        self.assertTrue(result.success)
        self.assertEqual(result.dependency_versions, {"tesseract": "5.5.0"})

    def test_provider_router_falls_back_when_advanced_is_unavailable(self):
        class Basic:
            def recognize(self, request):
                return OcrResult(
                    engine=OcrEngine.TESSERACT,
                    pages=[OcrPageResult(page_number=1, text="basic")],
                )

        class Advanced:
            @staticmethod
            def is_available():
                return False

        result = OCRProviderRouter(basic=Basic(), advanced=Advanced()).recognize(
            OcrRequest(engine=OcrEngine.LOCAL_MODEL, images=[]),
            prefer_advanced=True,
        )
        self.assertEqual(result.text, "basic")
        self.assertTrue(any("fallback" in warning for warning in result.warnings))

    def test_provider_router_falls_back_after_advanced_failure(self):
        class Basic:
            def recognize(self, request):
                return OcrResult(
                    engine=OcrEngine.TESSERACT,
                    pages=[OcrPageResult(page_number=1, text="basic")],
                )

        class Advanced:
            @staticmethod
            def is_available():
                return True

            @staticmethod
            def recognize(request):
                raise RuntimeError("worker crash")

        result = OCRProviderRouter(basic=Basic(), advanced=Advanced()).recognize(
            OcrRequest(engine=OcrEngine.LOCAL_MODEL, images=[]),
            prefer_advanced=True,
        )
        self.assertEqual(result.text, "basic")
        self.assertTrue(any("RuntimeError" in warning for warning in result.warnings))

    def test_worker_path_guard_rejects_escape_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            child = root / "child.txt"
            child.write_text("safe", encoding="utf-8")
            self.assertEqual(_require_child(child, root, require_file=True), child)
            with self.assertRaises(PermissionError):
                _require_child(root.parent / "outside.txt", root, require_file=False)

    def test_bounded_options_and_benchmark_classification(self):
        self.assertEqual(_bounded_int("999999", 10, 1, 100), 100)
        self.assertEqual(_bounded_int("bad", 10, 1, 100), 10)
        self.assertEqual(_benchmark_classification(4, 8, 12), "REAL_TIME_SUITABLE")
        self.assertEqual(_benchmark_classification(200, 8, 12), "LOCAL_USE_NOT_RECOMMENDED")
        self.assertEqual(
            _setup_benchmark_classification(7.8, 7_564_874_752, 12_884_901_888),
            "GENERAL_OCR_SUITABLE",
        )
        self.assertEqual(_normalize_for_comparison(" Docu ment\nID "), "documentid")

    def test_legacy_benchmark_record_requires_targeted_refresh(self):
        record = InstallStepRecord("12-benchmark", InstallStage.BENCHMARK)
        record.details = {
            "inference_seconds": 7.8,
            "peak_ram_bytes": 1,
            "peak_vram_bytes": 2,
        }
        self.assertFalse(SetupOrchestrator._completed_record_is_current(record))
        record.details.update(
            {
                "classification": "GENERAL_OCR_SUITABLE",
                "backend": "transformers",
                "model_revision": "revision",
                "dependency_versions": {"torch": "2.10.0+cu130"},
            }
        )
        self.assertTrue(SetupOrchestrator._completed_record_is_current(record))

    def test_validation_suite_contains_required_categories_and_readable_pdfs(self):
        import fitz

        with tempfile.TemporaryDirectory() as temporary:
            cases = create_validation_suite(Path(temporary))
            categories = {case.category for case in cases}
            self.assertEqual(
                categories,
                {"pure_text", "table", "mixed_language", "complex_layout", "rotation"},
            )
            for case in cases:
                with fitz.open(case.pdf_path) as document:
                    self.assertEqual(document.page_count, 1)
                self.assertGreater(case.image_path.stat().st_size, 1000)

    def test_error_classifier_maps_permission_and_disk(self):
        self.assertEqual(
            classify_exception(PermissionError("denied")).error_code,
            ErrorCode.PERMISSION_DENIED.value,
        )
        error = OSError(28, "No space left on device")
        self.assertEqual(
            classify_exception(error).error_code,
            ErrorCode.INSUFFICIENT_DISK.value,
        )
        self.assertEqual(
            _worker_error_code("recognize", "CUDA out of memory"),
            ErrorCode.CUDA_OOM,
        )
        self.assertEqual(
            _worker_error_code("recognize", "host out of memory"),
            ErrorCode.RAM_OOM,
        )
        self.assertEqual(
            _worker_error_code("load", "invalid model config"),
            ErrorCode.MODEL_LOAD_FAILED,
        )

    def test_existing_runtime_consent_can_still_be_created(self):
        consent = create_advanced_ocr_consent(
            acknowledgements={
                "acknowledged_model_download_risk": True,
                "acknowledged_custom_code_risk": True,
                "acknowledged_gpu_vram_use": True,
                "acknowledged_temporary_page_images": True,
            }
        )
        self.assertIsNotNone(consent)


if __name__ == "__main__":
    unittest.main()
