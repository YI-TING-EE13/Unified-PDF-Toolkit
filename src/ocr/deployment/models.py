"""Typed records shared by the local OCR deployment framework."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class CompatibilityStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    SUPPORTED_WITH_CHANGES = "SUPPORTED_WITH_CHANGES"
    EXPERIMENTAL = "EXPERIMENTAL"
    CPU_ONLY_IF_AVAILABLE = "CPU_ONLY_IF_AVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class RuntimeBackend(str, Enum):
    TRANSFORMERS = "transformers"
    SGLANG = "sglang"
    VLLM_CONTAINER = "vllm_container"
    NONE = "none"


class InstallStage(str, Enum):
    PRECHECK = "PRECHECK"
    COMPATIBILITY_ANALYSIS = "COMPATIBILITY_ANALYSIS"
    USER_CONSENT = "USER_CONSENT"
    SNAPSHOT_CURRENT_STATE = "SNAPSHOT_CURRENT_STATE"
    UV_BOOTSTRAP = "UV_BOOTSTRAP"
    CREATE_ISOLATED_ENV = "CREATE_ISOLATED_ENV"
    INSTALL_DEPENDENCIES = "INSTALL_DEPENDENCIES"
    DOWNLOAD_MODEL = "DOWNLOAD_MODEL"
    VERIFY_CHECKSUM_OR_FILES = "VERIFY_CHECKSUM_OR_FILES"
    LOAD_MODEL = "LOAD_MODEL"
    RUN_SMOKE_TEST = "RUN_SMOKE_TEST"
    RUN_OCR_TEST = "RUN_OCR_TEST"
    BENCHMARK = "BENCHMARK"
    REGISTER_WITH_APP = "REGISTER_WITH_APP"
    COMPLETE = "COMPLETE"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class EnvironmentReport:
    schema_version: str
    generated_at: str
    os: Mapping[str, Any]
    cpu: Mapping[str, Any]
    memory: Mapping[str, Any]
    gpu: tuple[Mapping[str, Any], ...]
    nvidia_driver: Mapping[str, Any]
    cuda: Mapping[str, Any]
    python: Mapping[str, Any]
    pytorch: Mapping[str, Any]
    storage: Mapping[str, Any]
    runtime: Mapping[str, Any]
    containers: Mapping[str, Any]
    basic_ocr: Mapping[str, Any] = field(default_factory=dict)
    recommendation: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CompatibilityReport:
    status: CompatibilityStatus
    confidence: float
    reasons: tuple[str, ...]
    requirements_met: tuple[str, ...]
    requirements_missing: tuple[str, ...]
    required_changes: tuple[str, ...]
    estimated_download_size: int | None
    estimated_disk_usage: int | None
    estimated_vram_requirement: int | None
    recommended_backend: RuntimeBackend
    recommended_runtime: str | None
    risk_level: RiskLevel
    metadata_revision: str
    conflicts: tuple[str, ...] = ()
    app_compatibility: Mapping[str, Any] = field(default_factory=dict)
    basic_ocr: Mapping[str, Any] = field(default_factory=dict)
    recommended_provider: str = "tesseract"
    selected_gpu: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["recommended_backend"] = self.recommended_backend.value
        data["risk_level"] = self.risk_level.value
        return data


@dataclass(frozen=True)
class DeploymentError:
    error_code: str
    title: str
    user_message: str
    technical_details: str = ""
    detected_state: Mapping[str, Any] = field(default_factory=dict)
    expected_state: Mapping[str, Any] = field(default_factory=dict)
    automatic_fix_available: bool = False
    requires_admin: bool = False
    safe_to_retry: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimePlan:
    plan_id: str
    backend: RuntimeBackend
    runtime_root: str
    python_version: str
    environment_manager: str
    package_index_url: str | None
    packages: tuple[str, ...]
    model_id: str
    model_revision: str
    model_cache_dir: str
    commands: tuple[tuple[str, ...], ...]
    environment: Mapping[str, str]
    requires_admin: bool
    system_changes: tuple[str, ...]
    reversible_changes: tuple[str, ...]
    warnings: tuple[str, ...]
    blocked_reasons: tuple[str, ...] = ()
    bootstrap: Mapping[str, Any] = field(default_factory=dict)

    @property
    def executable(self) -> bool:
        return not self.blocked_reasons

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["backend"] = self.backend.value
        data["executable"] = self.executable
        data["plan_kind"] = "EXECUTABLE" if self.executable else "BLOCKED_INFORMATIONAL"
        data["commands_executable"] = self.executable
        return data


@dataclass
class InstallStepRecord:
    step_id: str
    stage: InstallStage
    status: StepStatus = StepStatus.PENDING
    progress: float = 0.0
    message: str = ""
    error_code: str | None = None
    attempts: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    retry_policy: dict[str, Any] = field(default_factory=dict)
    recovery_strategy: str = "Resume this stage without repeating completed stages."

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stage"] = self.stage.value
        data["status"] = self.status.value
        return data


@dataclass(frozen=True)
class BenchmarkResult:
    success: bool
    classification: str
    inference_seconds: float | None
    peak_ram_bytes: int | None
    peak_vram_bytes: int | None
    backend: str
    model_revision: str
    dependency_versions: Mapping[str, str]
    output_preview: str = ""
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderHealth:
    available: bool
    loaded: bool
    status: str
    details: Mapping[str, Any] = field(default_factory=dict)
    last_error: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
