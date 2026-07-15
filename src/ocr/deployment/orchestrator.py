"""Resumable, consent-gated staged installer for managed Unlimited-OCR."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import psutil

from .cache import ModelCacheManager
from .consent import DeploymentConsent
from .errors import DeploymentFailure, ErrorCode, classify_exception, make_error
from .metadata import load_compatibility_metadata
from .models import (
    CompatibilityReport,
    EnvironmentReport,
    InstallStage,
    InstallStepRecord,
    RuntimePlan,
    StepStatus,
)

_RESULT_PREFIX = "PDF_TOOLKIT_RESULT="
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


class CancellationToken:
    def __init__(self) -> None:
        self._cancel = threading.Event()
        self._pause = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def pause(self) -> None:
        self._pause.set()

    @property
    def cancellation_requested(self) -> bool:
        return self._cancel.is_set()

    @property
    def pause_requested(self) -> bool:
        return self._pause.is_set()


class _StopRequested(RuntimeError):
    def __init__(self, *, paused: bool) -> None:
        super().__init__("paused" if paused else "cancelled")
        self.paused = paused


ProgressCallback = Callable[[InstallStepRecord], None]
CommandRunner = Callable[[Sequence[str], Mapping[str, str], float, CancellationToken], dict[str, Any]]


class SetupOrchestrator:
    """Execute only a reviewed RuntimePlan that has matching explicit consent."""

    stages = tuple(InstallStage)

    def __init__(
        self,
        *,
        plan: RuntimePlan,
        compatibility: CompatibilityReport,
        environment: EnvironmentReport,
        consent: DeploymentConsent,
        metadata: Mapping[str, Any] | None = None,
        state_root: Path | None = None,
        cancellation: CancellationToken | None = None,
        progress_callback: ProgressCallback | None = None,
        command_runner: CommandRunner | None = None,
        validation_images: Sequence[Path] = (),
        validation_expectations: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self.plan = plan
        self.compatibility = compatibility
        self.environment = environment
        self.consent = consent
        self.metadata = dict(metadata or load_compatibility_metadata())
        self.runtime_root = Path(plan.runtime_root).resolve()
        self.state_root = (state_root or self.runtime_root / "state").resolve()
        self.cancellation = cancellation or CancellationToken()
        self.progress_callback = progress_callback
        self.command_runner = command_runner or self._run_command
        self.validation_images = tuple(Path(path).resolve() for path in validation_images)
        self.validation_expectations = {
            str(Path(path).resolve()): tuple(map(str, terms))
            for path, terms in (validation_expectations or {}).items()
        }
        self.journal_path = self.state_root / "installation.json"
        self.log_path = self.state_root / "installation.jsonl"
        self.lock_path = self.state_root / "installation.lock"
        self._journal: dict[str, Any] = {}
        self._active_record: InstallStepRecord | None = None

    def run(self, *, until: InstallStage | None = None) -> dict[str, Any]:
        self._validate_consent()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        try:
            self._journal = self._load_or_create_journal()
            for stage in self.stages:
                record = self._record(stage)
                if record.status == StepStatus.SUCCEEDED:
                    if self._completed_record_is_current(record):
                        if stage == until:
                            break
                        continue
                    record.status = StepStatus.PENDING
                    record.progress = 0.0
                    record.message = (
                        f"Refreshing legacy {stage.value} validation details."
                    )
                    self._save_record(record)
                while True:
                    try:
                        self._check_stop()
                        self._execute_stage(record)
                        break
                    except _StopRequested as exc:
                        record.status = StepStatus.PAUSED if exc.paused else StepStatus.CANCELLED
                        record.message = (
                            "Paused safely; rerun to resume this stage."
                            if exc.paused
                            else "Cancelled safely; rerun to resume this stage."
                        )
                        record.finished_at = _now()
                        self._save_record(record)
                        return self._journal
                    except DeploymentFailure as exc:
                        if self._schedule_retry(record, exc.error):
                            continue
                        record.status = StepStatus.FAILED
                        record.error_code = exc.error.error_code
                        record.message = exc.error.user_message
                        record.details["error"] = exc.error.to_dict()
                        record.finished_at = _now()
                        self._save_record(record)
                        raise
                    except Exception as exc:
                        error = classify_exception(exc)
                        if self._schedule_retry(record, error):
                            continue
                        record.status = StepStatus.FAILED
                        record.error_code = error.error_code
                        record.message = error.user_message
                        record.details["error"] = error.to_dict()
                        record.finished_at = _now()
                        self._save_record(record)
                        raise DeploymentFailure(error) from exc
                if stage == until:
                    break
            return self._journal
        finally:
            self._release_lock()

    @staticmethod
    def _completed_record_is_current(record: InstallStepRecord) -> bool:
        if record.stage != InstallStage.BENCHMARK:
            return True
        required = {
            "classification",
            "backend",
            "model_revision",
            "dependency_versions",
            "inference_seconds",
            "peak_ram_bytes",
            "peak_vram_bytes",
        }
        return required.issubset(record.details)

    def _execute_stage(self, record: InstallStepRecord) -> None:
        record.status = StepStatus.RUNNING
        record.progress = 0.0
        record.attempts += 1
        record.started_at = _now()
        record.finished_at = None
        record.error_code = None
        record.message = _stage_message(record.stage)
        self._save_record(record)
        handler = getattr(self, f"_stage_{record.stage.value.casefold()}")
        self._active_record = record
        try:
            details = handler() or {}
        finally:
            self._active_record = None
        self._check_stop()
        record.details.update(details)
        record.progress = 1.0
        record.status = StepStatus.SUCCEEDED
        record.finished_at = _now()
        record.message = f"{record.stage.value} completed."
        self._save_record(record)

    def _schedule_retry(self, record: InstallStepRecord, error: Any) -> bool:
        maximum = int(record.retry_policy.get("max_attempts", 1))
        if not error.safe_to_retry or record.attempts >= maximum:
            return False
        delay = min(
            float(record.retry_policy.get("initial_delay_seconds", 1.0))
            * (2 ** max(record.attempts - 1, 0)),
            float(record.retry_policy.get("maximum_delay_seconds", 5.0)),
        )
        record.status = StepStatus.PENDING
        record.error_code = error.error_code
        record.message = (
            f"Retrying {record.stage.value} after {error.error_code} "
            f"(attempt {record.attempts + 1}/{maximum})."
        )
        record.details.setdefault("retry_errors", []).append(error.to_dict())
        self._save_record(record)
        deadline = time.monotonic() + delay
        while time.monotonic() < deadline:
            if self.cancellation.pause_requested or self.cancellation.cancellation_requested:
                break
            time.sleep(min(0.1, max(deadline - time.monotonic(), 0.0)))
        return True

    def _stage_precheck(self) -> dict[str, Any]:
        storage = self.environment.storage
        required = int(self.metadata["resource_estimates"]["minimum_free_disk_bytes"])
        free = int(storage.get("free_bytes", 0))
        if free < required:
            raise DeploymentFailure(
                make_error(
                    ErrorCode.INSUFFICIENT_DISK,
                    detected_state={"free_bytes": free},
                    expected_state={"minimum_free_bytes": required},
                )
            )
        minimum_ram = int(self.metadata["resource_estimates"]["minimum_ram_bytes"])
        total_ram = int(self.environment.memory.get("total_bytes", 0))
        if total_ram < minimum_ram:
            raise DeploymentFailure(
                make_error(
                    ErrorCode.INSUFFICIENT_RAM,
                    detected_state={"total_bytes": total_ram},
                    expected_state={"minimum_bytes": minimum_ram},
                )
            )
        nvidia = [
            item
            for item in self.environment.gpu
            if str(item.get("vendor", "")).upper() == "NVIDIA"
        ]
        if not nvidia:
            raise DeploymentFailure(make_error(ErrorCode.NO_SUPPORTED_GPU))
        best_gpu = max(nvidia, key=lambda item: int(item.get("vram_total_bytes") or 0))
        minimum_vram = int(self.metadata["resource_estimates"]["minimum_vram_bytes"])
        detected_vram = int(best_gpu.get("vram_total_bytes") or 0)
        if detected_vram < minimum_vram:
            raise DeploymentFailure(
                make_error(
                    ErrorCode.INSUFFICIENT_VRAM,
                    detected_state={"vram_total_bytes": detected_vram},
                    expected_state={"minimum_bytes": minimum_vram},
                )
            )
        driver_version = self.environment.nvidia_driver.get("driver_version")
        if not driver_version:
            raise DeploymentFailure(make_error(ErrorCode.NVIDIA_DRIVER_MISSING))
        if not self.plan.package_index_url:
            raise DeploymentFailure(
                make_error(
                    ErrorCode.NVIDIA_DRIVER_TOO_OLD,
                    detected_state={"driver_version": driver_version},
                    expected_state={"supported_profiles": self.metadata["driver_families"]},
                )
            )
        if self.plan.environment_manager == "unresolved":
            raise DeploymentFailure(make_error(ErrorCode.PYTHON_VERSION_UNSUPPORTED))
        if not self.plan.executable:
            raise DeploymentFailure(
                make_error(
                    ErrorCode.DEPENDENCY_CONFLICT,
                    technical_details="; ".join(self.plan.blocked_reasons),
                )
            )
        return {"free_bytes": free, "required_free_bytes": required}

    def _stage_compatibility_analysis(self) -> dict[str, Any]:
        if self.compatibility.recommended_backend != self.plan.backend:
            raise DeploymentFailure(make_error(ErrorCode.PLAN_CHANGED))
        return self.compatibility.to_dict()

    def _stage_user_consent(self) -> dict[str, Any]:
        self._validate_consent()
        return {"consent_id": self.consent.consent_id, "created_at": self.consent.created_at}

    def _stage_snapshot_current_state(self) -> dict[str, Any]:
        snapshot_dir = self.state_root / "snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        _atomic_json(snapshot_dir / "environment.json", self.environment.to_dict())
        _atomic_json(snapshot_dir / "plan.json", self.plan.to_dict())
        _atomic_json(snapshot_dir / "consent.json", self.consent.to_dict())
        return {"snapshot_dir": str(snapshot_dir)}

    def _stage_create_isolated_env(self) -> dict[str, Any]:
        return self._execute_commands(self.plan.commands[:1], timeout=900)

    def _stage_install_dependencies(self) -> dict[str, Any]:
        return self._execute_commands(self.plan.commands[1:], timeout=3600)

    def _stage_download_model(self) -> dict[str, Any]:
        cache = ModelCacheManager(Path(self.plan.model_cache_dir))
        snapshot = cache.snapshot_path(self.plan.model_revision)
        artifacts = self.metadata["model_artifacts"]
        command = [
            str(
                _runtime_python(
                    Path(self.plan.runtime_root) / "environment",
                    self.plan.environment_manager,
                )
            ),
            str(Path(__file__).with_name("runtime_tasks.py")),
            "download",
            "--model-id",
            self.plan.model_id,
            "--revision",
            self.plan.model_revision,
            "--cache-dir",
            str(Path(self.plan.model_cache_dir) / "hub"),
            "--local-dir",
            str(snapshot),
        ]
        for pattern in artifacts.get("allow_patterns", []):
            command.extend(("--allow-pattern", str(pattern)))
        result = self._execute_commands(
            (tuple(command),),
            timeout=14400,
            failure_code=ErrorCode.MODEL_DOWNLOAD_FAILED,
        )
        cache.write_manifest(
            self.plan.model_revision,
            {
                "model_id": self.plan.model_id,
                "revision": self.plan.model_revision,
                "metadata_revision": self.compatibility.metadata_revision,
                "downloaded_at": _now(),
            },
        )
        result["snapshot_path"] = str(snapshot)
        return result

    def _stage_verify_checksum_or_files(self) -> dict[str, Any]:
        manager = ModelCacheManager(Path(self.plan.model_cache_dir))
        return manager.verify(self.plan.model_revision, self.metadata, full_hash=True).to_dict()

    def _stage_load_model(self) -> dict[str, Any]:
        return self._run_runtime_task("load", timeout=1800)

    def _stage_run_smoke_test(self) -> dict[str, Any]:
        return self._run_runtime_task("probe", timeout=120)

    def _stage_run_ocr_test(self) -> dict[str, Any]:
        if not self.validation_images:
            raise DeploymentFailure(
                make_error(
                    ErrorCode.INFERENCE_FAILED,
                    technical_details="No built-in OCR validation images were provided.",
                )
            )
        results = []
        for index, image in enumerate(self.validation_images):
            self._check_stop()
            results.append(
                self._run_runtime_task(
                    "ocr",
                    image=image,
                    output_dir=self.state_root / "ocr-results" / f"case-{index + 1}",
                    expected_terms=self.validation_expectations.get(str(image), ()),
                    timeout=3600,
                )
            )
        return {"cases": results, "success": all(item.get("success") for item in results)}

    def _stage_benchmark(self) -> dict[str, Any]:
        if not self.validation_images:
            raise DeploymentFailure(make_error(ErrorCode.INFERENCE_FAILED))
        return self._run_runtime_task(
            "benchmark",
            image=self.validation_images[0],
            output_dir=self.state_root / "benchmark",
            timeout=3600,
        )

    def _stage_register_with_app(self) -> dict[str, Any]:
        from ..consent import create_advanced_ocr_consent, save_advanced_ocr_consent
        from ..local_model import (
            LOCAL_MODEL_MODE_WORKER_PROCESS,
            LocalModelRuntimeConfig,
            save_local_model_runtime_config,
        )

        runtime_python = _runtime_python(
            Path(self.plan.runtime_root) / "environment", self.plan.environment_manager
        )
        snapshot = ModelCacheManager(Path(self.plan.model_cache_dir)).snapshot_path(
            self.plan.model_revision
        )
        config = LocalModelRuntimeConfig(
            enabled=True,
            mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
            model_id=self.plan.model_id,
            model_revision=self.plan.model_revision,
            model_path=str(snapshot),
            python_executable=str(runtime_python),
            device_preference="cuda",
            options={"managed_plan_id": self.plan.plan_id},
        )
        save_local_model_runtime_config(config)
        runtime_consent = create_advanced_ocr_consent(
            acknowledgements={
                "acknowledged_model_download_risk": True,
                "acknowledged_custom_code_risk": True,
                "acknowledged_gpu_vram_use": True,
                "acknowledged_temporary_page_images": True,
            }
        )
        if runtime_consent is None:
            raise DeploymentFailure(make_error(ErrorCode.CONSENT_REQUIRED))
        save_advanced_ocr_consent(runtime_consent)
        return {"registered": True, "runtime_config": config.to_dict()}

    @staticmethod
    def _stage_complete() -> dict[str, Any]:
        return {"complete": True}

    def _run_runtime_task(
        self,
        task: str,
        *,
        image: Path | None = None,
        output_dir: Path | None = None,
        expected_terms: Sequence[str] = (),
        timeout: float,
    ) -> dict[str, Any]:
        python = _runtime_python(
            Path(self.plan.runtime_root) / "environment", self.plan.environment_manager
        )
        command = [str(python), str(Path(__file__).with_name("runtime_tasks.py")), task]
        if task == "probe":
            command.append("--require-cuda")
        else:
            snapshot = ModelCacheManager(Path(self.plan.model_cache_dir)).snapshot_path(
                self.plan.model_revision
            )
            command.extend(
                (
                    "--model-path",
                    str(snapshot),
                    "--revision",
                    self.plan.model_revision,
                    "--device",
                    "cuda",
                )
            )
        if image is not None and output_dir is not None:
            command.extend(("--image", str(image), "--output-dir", str(output_dir)))
            for term in expected_terms:
                command.extend(("--expected-term", str(term)))
        result = self.command_runner(command, self._command_environment(), timeout, self.cancellation)
        self._check_stop()
        if int(result.get("returncode", 1)) != 0:
            code = _runtime_error_code(result)
            raise DeploymentFailure(
                make_error(code, technical_details=_technical_result(result))
            )
        parsed = _parse_runtime_result(str(result.get("stdout", "")))
        if not parsed.get("success"):
            raise DeploymentFailure(
                make_error(
                    _runtime_error_code(result, parsed),
                    technical_details=str(parsed.get("error", "runtime task failed")),
                )
            )
        return parsed

    def _execute_commands(
        self,
        commands: Sequence[Sequence[str]],
        *,
        timeout: float,
        failure_code: ErrorCode | None = None,
    ) -> dict[str, Any]:
        results = []
        for command in commands:
            self._check_stop()
            result = self.command_runner(command, self._command_environment(), timeout, self.cancellation)
            self._check_stop()
            results.append(
                {
                    "argv": list(command),
                    "returncode": result.get("returncode"),
                    "stdout_tail": str(result.get("stdout", ""))[-2000:],
                    "stderr_tail": str(result.get("stderr", ""))[-4000:],
                }
            )
            if int(result.get("returncode", 1)) != 0:
                selected_code = _setup_error_code(result)
                if failure_code is not None and selected_code in {
                    ErrorCode.NETWORK_ERROR,
                    ErrorCode.SUBPROCESS_CRASH,
                }:
                    selected_code = failure_code
                raise DeploymentFailure(
                    make_error(
                        selected_code,
                        technical_details=_technical_result(result),
                    )
                )
        return {"commands": results}

    def _command_environment(self) -> dict[str, str]:
        value = dict(os.environ)
        value.update({str(key): str(item) for key, item in self.plan.environment.items()})
        return value

    def _run_command(
        self,
        command: Sequence[str],
        environment: Mapping[str, str],
        timeout: float,
        cancellation: CancellationToken,
    ) -> dict[str, Any]:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            process = subprocess.Popen(
                list(map(str, command)),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                shell=False,
                env=dict(environment),
                creationflags=_CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP,
            )
            started = time.monotonic()
            last_progress_update = 0.0
            while process.poll() is None:
                if cancellation.cancellation_requested or cancellation.pause_requested:
                    _terminate_process_tree(process.pid)
                    raise _StopRequested(paused=cancellation.pause_requested)
                if time.monotonic() - started > timeout:
                    _terminate_process_tree(process.pid)
                    raise TimeoutError(f"Command exceeded {timeout:.0f} seconds.")
                if (
                    self._active_record is not None
                    and self._active_record.stage == InstallStage.DOWNLOAD_MODEL
                    and time.monotonic() - last_progress_update >= 1.0
                ):
                    expected = int(
                        self.metadata["model_artifacts"].get("required_download_bytes", 0)
                    )
                    snapshot = ModelCacheManager(
                        Path(self.plan.model_cache_dir)
                    ).snapshot_path(self.plan.model_revision)
                    downloaded = _directory_size(snapshot)
                    if expected > 0:
                        self._active_record.progress = min(downloaded / expected, 0.99)
                    self._active_record.message = (
                        "Downloading the pinned model snapshot: "
                        f"{_format_bytes(downloaded)} / {_format_bytes(expected)}."
                    )
                    self._save_record(self._active_record)
                    last_progress_update = time.monotonic()
                time.sleep(0.2)
            stdout_file.seek(0)
            stderr_file.seek(0)
            return {
                "returncode": process.returncode,
                "stdout": stdout_file.read().decode("utf-8", errors="replace"),
                "stderr": stderr_file.read().decode("utf-8", errors="replace"),
            }

    def _validate_consent(self) -> None:
        if not self.consent.is_valid_for(
            self.plan,
            metadata_revision=self.compatibility.metadata_revision,
        ):
            raise DeploymentFailure(make_error(ErrorCode.PLAN_CHANGED))

    def _check_stop(self) -> None:
        if self.cancellation.pause_requested:
            raise _StopRequested(paused=True)
        if self.cancellation.cancellation_requested:
            raise _StopRequested(paused=False)

    def _load_or_create_journal(self) -> dict[str, Any]:
        if self.journal_path.exists():
            value = json.loads(self.journal_path.read_text(encoding="utf-8"))
            if value.get("plan_id") != self.plan.plan_id:
                raise DeploymentFailure(make_error(ErrorCode.PLAN_CHANGED))
            return value
        value = {
            "schema_version": "1.0",
            "plan_id": self.plan.plan_id,
            "consent_id": self.consent.consent_id,
            "created_at": _now(),
            "updated_at": _now(),
            "steps": [
                InstallStepRecord(
                    step_id=f"{index + 1:02d}-{stage.value.casefold()}",
                    stage=stage,
                    retry_policy=_retry_policy(stage),
                    recovery_strategy=_recovery_strategy(stage),
                ).to_dict()
                for index, stage in enumerate(self.stages)
            ],
        }
        _atomic_json(self.journal_path, value)
        return value

    def _record(self, stage: InstallStage) -> InstallStepRecord:
        for value in self._journal["steps"]:
            if value["stage"] == stage.value:
                return InstallStepRecord(
                    step_id=value["step_id"],
                    stage=stage,
                    status=StepStatus(value["status"]),
                    progress=float(value.get("progress", 0.0)),
                    message=str(value.get("message", "")),
                    error_code=value.get("error_code"),
                    attempts=int(value.get("attempts", 0)),
                    started_at=value.get("started_at"),
                    finished_at=value.get("finished_at"),
                    details=dict(value.get("details", {})),
                    retry_policy=dict(value.get("retry_policy", _retry_policy(stage))),
                    recovery_strategy=str(
                        value.get("recovery_strategy", _recovery_strategy(stage))
                    ),
                )
        raise KeyError(stage.value)

    def _save_record(self, record: InstallStepRecord) -> None:
        for index, value in enumerate(self._journal["steps"]):
            if value["stage"] == record.stage.value:
                self._journal["steps"][index] = record.to_dict()
                break
        self._journal["updated_at"] = _now()
        _atomic_json(self.journal_path, self._journal)
        _append_jsonl(
            self.log_path,
            {
                "timestamp": _now(),
                "step_id": record.step_id,
                "stage": record.stage.value,
                "status": record.status.value,
                "progress": record.progress,
                "message": record.message,
                "error_code": record.error_code,
            },
        )
        if self.progress_callback:
            self.progress_callback(record)

    def _acquire_lock(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            try:
                lock = json.loads(self.lock_path.read_text(encoding="utf-8"))
                pid = int(lock["pid"])
                expected_created = float(lock["process_created_at"])
                process = psutil.Process(pid)
                active = abs(process.create_time() - expected_created) < 1.0
            except (
                OSError,
                TypeError,
                ValueError,
                KeyError,
                json.JSONDecodeError,
                psutil.Error,
            ):
                pid = -1
                active = False
            if active:
                raise DeploymentFailure(
                    make_error(
                        ErrorCode.SUBPROCESS_CRASH,
                        technical_details=f"Another setup process is active (PID {pid}).",
                    )
                )
            self.lock_path.unlink(missing_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": os.getpid(),
                    "process_created_at": psutil.Process().create_time(),
                    "plan_id": self.plan.plan_id,
                },
                handle,
            )

    def _release_lock(self) -> None:
        self.lock_path.unlink(missing_ok=True)


class DeploymentCleanup:
    """Explicit cleanup API; no path is removed without confirmation."""

    def __init__(self, plan: RuntimePlan) -> None:
        self.plan = plan

    def uninstall(
        self,
        *,
        confirmed: bool,
        remove_model: bool = False,
        clear_download_cache: bool = False,
    ) -> dict[str, bool]:
        if not confirmed:
            raise ValueError("Explicit uninstall confirmation is required.")
        runtime = Path(self.plan.runtime_root).resolve()
        data_root = runtime.parents[1]
        _assert_managed_child(runtime, data_root)
        removed_runtime = False
        if runtime.exists():
            shutil.rmtree(runtime, onerror=_clear_readonly_and_retry)
            removed_runtime = True
        cache = ModelCacheManager(Path(self.plan.model_cache_dir))
        removed_model = cache.uninstall_snapshot(self.plan.model_revision) if remove_model else False
        cleared_cache = cache.clear_download_cache() if clear_download_cache else False
        return {
            "runtime_removed": removed_runtime,
            "model_removed": removed_model,
            "download_cache_cleared": cleared_cache,
        }


def _runtime_python(environment_root: Path, manager: str = "uv") -> Path:
    if os.name == "nt":
        if manager == "conda":
            return environment_root / "python.exe"
        return environment_root / "Scripts" / "python.exe"
    return environment_root / "bin" / "python"


def _parse_runtime_result(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        if line.startswith(_RESULT_PREFIX):
            return json.loads(line[len(_RESULT_PREFIX) :])
    return {"success": False, "error": "Private runtime produced no structured result."}


def _runtime_error_code(result: Mapping[str, Any], parsed: Mapping[str, Any] | None = None) -> ErrorCode:
    text = f"{result.get('stderr', '')} {(parsed or {}).get('error', '')}".casefold()
    if "cuda out of memory" in text:
        return ErrorCode.CUDA_OOM
    if "cannot access cuda" in text or "cuda is required" in text:
        return ErrorCode.PYTORCH_CUDA_MISMATCH
    if "no space" in text:
        return ErrorCode.INSUFFICIENT_DISK
    if "permission" in text or "access is denied" in text:
        return ErrorCode.PERMISSION_DENIED
    if "download" in text or "connection" in text or "timed out" in text:
        return ErrorCode.MODEL_DOWNLOAD_FAILED
    return ErrorCode.MODEL_LOAD_FAILED


def _setup_error_code(result: Mapping[str, Any]) -> ErrorCode:
    text = f"{result.get('stdout', '')} {result.get('stderr', '')}".casefold()
    if "no space" in text:
        return ErrorCode.INSUFFICIENT_DISK
    if "permission" in text or "access is denied" in text:
        return ErrorCode.PERMISSION_DENIED
    if "resolution impossible" in text or "conflict" in text:
        return ErrorCode.DEPENDENCY_CONFLICT
    if "network" in text or "connection" in text or "timed out" in text:
        return ErrorCode.NETWORK_ERROR
    return ErrorCode.SUBPROCESS_CRASH


def _technical_result(result: Mapping[str, Any]) -> str:
    return (
        f"returncode={result.get('returncode')}\n"
        f"stdout={str(result.get('stdout', ''))[-2000:]}\n"
        f"stderr={str(result.get('stderr', ''))[-4000:]}"
    )


def _directory_size(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _format_bytes(value: int) -> str:
    amount = float(max(value, 0))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TiB"


def _terminate_process_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.Error:
        return
    processes = parent.children(recursive=True)
    processes.append(parent)
    for process in reversed(processes):
        try:
            process.terminate()
        except psutil.Error:
            continue
    _gone, alive = psutil.wait_procs(processes, timeout=5)
    for process in alive:
        try:
            process.kill()
        except psutil.Error:
            continue


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stage_message(stage: InstallStage) -> str:
    return {
        InstallStage.PRECHECK: "Checking disk, paths, and plan safety.",
        InstallStage.COMPATIBILITY_ANALYSIS: "Confirming the compatibility decision.",
        InstallStage.USER_CONSENT: "Validating plan-bound user consent.",
        InstallStage.SNAPSHOT_CURRENT_STATE: "Recording the reversible pre-install state.",
        InstallStage.CREATE_ISOLATED_ENV: "Creating the private Python environment.",
        InstallStage.INSTALL_DEPENDENCIES: "Installing pinned private dependencies.",
        InstallStage.DOWNLOAD_MODEL: "Downloading the pinned model snapshot.",
        InstallStage.VERIFY_CHECKSUM_OR_FILES: "Verifying required files and SHA-256.",
        InstallStage.LOAD_MODEL: "Loading the model in the private CUDA worker.",
        InstallStage.RUN_SMOKE_TEST: "Checking Python, PyTorch, CUDA, and GPU access.",
        InstallStage.RUN_OCR_TEST: "Running the built-in OCR functional suite.",
        InstallStage.BENCHMARK: "Measuring inference time and peak resource use.",
        InstallStage.REGISTER_WITH_APP: "Registering the verified provider with the APP.",
        InstallStage.COMPLETE: "Finalizing setup.",
    }[stage]


def _retry_policy(stage: InstallStage) -> dict[str, Any]:
    maximum = {
        InstallStage.CREATE_ISOLATED_ENV: 2,
        InstallStage.INSTALL_DEPENDENCIES: 2,
        InstallStage.DOWNLOAD_MODEL: 3,
    }.get(stage, 1)
    return {
        "max_attempts": maximum,
        "initial_delay_seconds": 1.0,
        "maximum_delay_seconds": 5.0,
    }


def _recovery_strategy(stage: InstallStage) -> str:
    if stage == InstallStage.DOWNLOAD_MODEL:
        return "Reuse the partial Hugging Face cache and resume the pinned revision."
    if stage in {InstallStage.CREATE_ISOLATED_ENV, InstallStage.INSTALL_DEPENDENCIES}:
        return "Retry inside the same private environment; never modify global packages."
    if stage == InstallStage.REGISTER_WITH_APP:
        return "Keep the existing OCR provider until registration succeeds."
    return "Rerun this stage while preserving every previously completed stage."


def _assert_managed_child(path: Path, root: Path) -> None:
    if path == root or root not in path.parents:
        raise ValueError("Cleanup target is outside the managed data root.")


def _clear_readonly_and_retry(function: Any, path: str, exc_info: Any) -> None:
    try:
        os.chmod(path, 0o700)
        function(path)
    except OSError:
        raise exc_info[1]
