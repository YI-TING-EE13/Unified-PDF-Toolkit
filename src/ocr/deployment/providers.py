"""OCR provider abstraction with managed Unlimited-OCR and safe fallback."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from .cache import ModelCacheManager
from .compatibility import CompatibilityEngine
from .environment import EnvironmentInspector, default_ocr_data_root
from .errors import DeploymentFailure, ErrorCode, make_error
from .models import (
    BenchmarkResult,
    CompatibilityReport,
    ProviderHealth,
    RuntimePlan,
)
from .orchestrator import _terminate_process_tree
from .resolver import EnvironmentResolver
from ..base import OcrBackend
from ..models import OcrEngine, OcrPageResult, OcrRequest, OcrResult
from ..registry import get_backend

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


class OCRProvider(ABC):
    provider_id: str
    display_name: str

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def check_compatibility(self) -> CompatibilityReport | None: ...

    @abstractmethod
    def setup(self, **kwargs: Any) -> Any: ...

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def recognize(self, input_data: OcrRequest) -> OcrResult: ...

    @abstractmethod
    def benchmark(self, input_data: OcrRequest) -> BenchmarkResult: ...

    @abstractmethod
    def health_check(self) -> ProviderHealth: ...

    @abstractmethod
    def unload(self) -> None: ...


class BasicOCRProvider(OCRProvider):
    provider_id = "basic_tesseract"
    display_name = "Basic OCR (Tesseract)"

    def __init__(self, backend: OcrBackend | None = None) -> None:
        self.backend = backend or get_backend(OcrEngine.TESSERACT)

    def is_available(self) -> bool:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def check_compatibility(self) -> None:
        return None

    def setup(self, **kwargs: Any) -> None:
        return None

    def load(self) -> None:
        return None

    def recognize(self, input_data: OcrRequest) -> OcrResult:
        return self.backend.recognize(replace(input_data, engine=OcrEngine.TESSERACT))

    def benchmark(self, input_data: OcrRequest) -> BenchmarkResult:
        import time

        started = time.perf_counter()
        result = self.recognize(input_data)
        return BenchmarkResult(
            success=bool(result.text.strip()),
            classification="GENERAL_OCR_SUITABLE",
            inference_seconds=time.perf_counter() - started,
            peak_ram_bytes=None,
            peak_vram_bytes=0,
            backend=self.provider_id,
            model_revision="system-tesseract",
            dependency_versions=dict(result.metadata.get("dependency_versions", {})),
        )

    def health_check(self) -> ProviderHealth:
        available = self.is_available()
        return ProviderHealth(available, available, "READY" if available else "UNAVAILABLE")

    def unload(self) -> None:
        return None


class PersistentRuntimeWorker:
    def __init__(
        self,
        *,
        python_executable: Path,
        model_root: Path,
        session_root: Path,
        environment: Mapping[str, str],
        log_path: Path,
    ) -> None:
        self.python_executable = python_executable
        self.model_root = model_root.resolve()
        self.session_root = session_root.resolve()
        self.environment = dict(environment)
        self.log_path = log_path
        self.process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._request_lock = threading.Lock()
        self._log_handle: Any = None
        self._reader_thread: threading.Thread | None = None

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return
        self._finalize_stopped_process()
        self._discard_stale_responses()
        self.session_root.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.update(self.environment)
        env["PDF_TOOLKIT_OCR_MODEL_ROOT"] = str(self.model_root)
        env["PDF_TOOLKIT_OCR_SESSION_ROOT"] = str(self.session_root)
        env["PYTHONIOENCODING"] = "utf-8"
        self._log_handle = self.log_path.open("a", encoding="utf-8")
        self.process = subprocess.Popen(
            [str(self.python_executable), str(Path(__file__).with_name("provider_worker.py"))],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log_handle,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=False,
            env=env,
            creationflags=_CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP,
        )
        self._reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self._reader_thread.start()

    def request(self, command: str, *, timeout: float = 1800, **payload: Any) -> dict[str, Any]:
        self.start()
        assert self.process is not None
        request_id = uuid.uuid4().hex
        message = {"id": request_id, "command": command, **payload}
        with self._request_lock:
            if self.process.poll() is not None or self.process.stdin is None:
                raise DeploymentFailure(make_error(ErrorCode.SUBPROCESS_CRASH))
            try:
                self.process.stdin.write(json.dumps(message, ensure_ascii=True) + "\n")
                self.process.stdin.flush()
            except (OSError, ValueError) as exc:
                self.stop(force=True)
                raise DeploymentFailure(
                    make_error(ErrorCode.SUBPROCESS_CRASH, technical_details=str(exc))
                ) from exc
            try:
                response = self._responses.get(timeout=timeout)
            except queue.Empty as exc:
                self.stop(force=True)
                raise DeploymentFailure(
                    make_error(
                        ErrorCode.SUBPROCESS_CRASH,
                        technical_details=f"Worker request timed out after {timeout:.0f}s.",
                    )
                ) from exc
            if isinstance(response, BaseException):
                raise DeploymentFailure(
                    make_error(ErrorCode.SUBPROCESS_CRASH, technical_details=str(response))
                )
            if response.get("id") != request_id:
                raise DeploymentFailure(
                    make_error(ErrorCode.SUBPROCESS_CRASH, technical_details="Worker response id mismatch.")
                )
            if "error" in response:
                error = response["error"]
                code = _worker_error_code(command, error)
                raise DeploymentFailure(make_error(code, technical_details=json.dumps(error)))
            return dict(response.get("result", {}))

    def stop(self, *, force: bool = False) -> None:
        process = self.process
        if process is None:
            return
        if not force and process.poll() is None:
            try:
                self.request("shutdown", timeout=15)
            except Exception:
                force = True
        if force and process.poll() is None:
            _terminate_process_tree(process.pid)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process.pid)
            process.wait(timeout=5)
        self._finalize_stopped_process()
        self._discard_stale_responses()

    def _finalize_stopped_process(self) -> None:
        process = self.process
        if process is not None and process.poll() is None:
            return
        reader = self._reader_thread
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=2)
        if process is not None:
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
        if self._log_handle:
            self._log_handle.close()
        self.process = None
        self._reader_thread = None
        self._log_handle = None

    def _discard_stale_responses(self) -> None:
        while True:
            try:
                self._responses.get_nowait()
            except queue.Empty:
                return

    def _read_responses(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                try:
                    self._responses.put(json.loads(line))
                except json.JSONDecodeError as exc:
                    self._responses.put(exc)
        finally:
            if process.poll() not in {None, 0}:
                self._responses.put(RuntimeError(f"Worker exited with code {process.returncode}."))


class UnlimitedOCRProvider(OCRProvider):
    provider_id = "unlimited_ocr_local"
    display_name = "Unlimited-OCR (Managed Local)"

    def __init__(
        self,
        *,
        environment_inspector: EnvironmentInspector | None = None,
        compatibility_engine: CompatibilityEngine | None = None,
        resolver: EnvironmentResolver | None = None,
        data_root: Path | None = None,
    ) -> None:
        self.data_root = (data_root or default_ocr_data_root()).expanduser().resolve()
        self.inspector = environment_inspector or EnvironmentInspector(data_root=self.data_root)
        self.engine = compatibility_engine or CompatibilityEngine()
        self.resolver = resolver or EnvironmentResolver()
        self._environment = None
        self._compatibility = None
        self._plan: RuntimePlan | None = None
        self._worker: PersistentRuntimeWorker | None = None
        self._last_error: dict[str, Any] | None = None

    def _refresh_plan(self) -> RuntimePlan:
        inspected = self.inspector.inspect()
        self._compatibility = self.engine.evaluate(inspected)
        self._environment = replace(
            inspected, recommendation=self._compatibility.to_dict()
        )
        self._plan = self.resolver.resolve(self._compatibility, data_root=self.data_root)
        return self._plan

    @property
    def plan(self) -> RuntimePlan:
        return self._plan or self._refresh_plan()

    def analyze(self) -> tuple[Any, CompatibilityReport, RuntimePlan]:
        plan = self._refresh_plan()
        assert self._environment is not None
        assert self._compatibility is not None
        return self._environment, self._compatibility, plan

    def is_available(self) -> bool:
        plan = self.plan
        python = _runtime_python(
            Path(plan.runtime_root) / "environment", plan.environment_manager
        )
        status = ModelCacheManager(Path(plan.model_cache_dir)).inspect(
            plan.model_revision,
            self.engine.metadata,
        )
        return plan.executable and python.is_file() and status.complete

    def check_compatibility(self) -> CompatibilityReport:
        self._refresh_plan()
        assert self._compatibility is not None
        return self._compatibility

    def setup(self, **kwargs: Any) -> Any:
        from .orchestrator import SetupOrchestrator

        plan = self.plan
        if self._environment is None or self._compatibility is None:
            self._refresh_plan()
        return SetupOrchestrator(
            plan=plan,
            compatibility=self._compatibility,
            environment=self._environment,
            metadata=self.engine.metadata,
            **kwargs,
        ).run()

    def load(self) -> None:
        if not self.is_available():
            raise DeploymentFailure(make_error(ErrorCode.MODEL_LOAD_FAILED))
        plan = self.plan
        session_root = self.data_root / "sessions"
        self._worker = self._worker or PersistentRuntimeWorker(
            python_executable=_runtime_python(
                Path(plan.runtime_root) / "environment", plan.environment_manager
            ),
            model_root=Path(plan.model_cache_dir) / "snapshots",
            session_root=session_root,
            environment=plan.environment,
            log_path=self.data_root / "logs" / "provider-worker.log",
        )
        snapshot = ModelCacheManager(Path(plan.model_cache_dir)).snapshot_path(plan.model_revision)
        self._worker.request(
            "load",
            model_path=str(snapshot),
            revision=plan.model_revision,
            timeout=1800,
        )

    def recognize(self, input_data: OcrRequest) -> OcrResult:
        if self._worker is None:
            self.load()
        assert self._worker is not None
        session_root = self.data_root / "sessions"
        session_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="request-", dir=session_root) as temporary:
            root = Path(temporary)
            image_paths = []
            for index, image in enumerate(input_data.images):
                path = root / f"page-{index + 1:04d}.png"
                image.save(path, format="PNG")
                image_paths.append(str(path))
            result = self._worker.request(
                "recognize",
                images=image_paths,
                output_dir=str(root / "output"),
                options=_safe_worker_options(input_data.options),
                timeout=float(input_data.options.get("timeout_seconds", 1800)),
            )
        texts = list(result.get("texts", []))
        warnings = []
        if result.get("combined_multi_page"):
            warnings.append("Unlimited-OCR returned one combined multi-page result.")
        if len(texts) == 1 and len(input_data.images) > 1:
            texts.extend("" for _ in range(len(input_data.images) - 1))
        pages = [
            OcrPageResult(
                page_number=(
                    input_data.page_numbers[index]
                    if index < len(input_data.page_numbers)
                    else index + 1
                ),
                text=texts[index] if index < len(texts) else "",
                warnings=list(warnings if index == 0 else []),
            )
            for index in range(len(input_data.images))
        ]
        return OcrResult(
            engine=OcrEngine.LOCAL_MODEL,
            pages=pages,
            source_path=input_data.source_path,
            warnings=warnings,
            metadata={
                "provider": self.provider_id,
                "model_revision": self.plan.model_revision,
                "inference_seconds": result.get("inference_seconds"),
                "peak_vram_bytes": result.get("peak_vram_bytes"),
            },
        )

    def benchmark(self, input_data: OcrRequest) -> BenchmarkResult:
        if not input_data.images:
            raise ValueError("Benchmark requires one image.")
        if self._worker is None:
            self.load()
        assert self._worker is not None
        session_root = self.data_root / "sessions"
        session_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="benchmark-", dir=session_root) as temporary:
            root = Path(temporary)
            image = root / "benchmark.png"
            input_data.images[0].save(image, format="PNG")
            result = self._worker.request(
                "benchmark",
                images=[str(image)],
                output_dir=str(root / "output"),
                options=_safe_worker_options(input_data.options),
                timeout=float(input_data.options.get("timeout_seconds", 1800)),
            )
        return BenchmarkResult(
            success=bool(result.get("success")),
            classification=str(result.get("classification", "UNKNOWN")),
            inference_seconds=_optional_float(result.get("inference_seconds")),
            peak_ram_bytes=_optional_int(result.get("peak_ram_bytes")),
            peak_vram_bytes=_optional_int(result.get("peak_vram_bytes")),
            backend=self.provider_id,
            model_revision=self.plan.model_revision,
            dependency_versions={},
        )

    def health_check(self) -> ProviderHealth:
        if not self.is_available():
            return ProviderHealth(False, False, "NOT_INSTALLED", last_error=self._last_error)
        if self._worker is None:
            return ProviderHealth(True, False, "READY", last_error=self._last_error)
        try:
            details = self._worker.request("health", timeout=15)
            return ProviderHealth(True, bool(details.get("loaded")), "HEALTHY", details)
        except DeploymentFailure as exc:
            self._last_error = exc.error.to_dict()
            return ProviderHealth(True, False, "UNHEALTHY", last_error=self._last_error)

    def unload(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker = None


class OCRProviderRouter:
    def __init__(
        self,
        basic: BasicOCRProvider | None = None,
        advanced: UnlimitedOCRProvider | None = None,
    ) -> None:
        self.basic = basic or BasicOCRProvider()
        self.advanced = advanced or UnlimitedOCRProvider()

    def recognize(
        self,
        request: OcrRequest,
        *,
        prefer_advanced: bool,
        allow_fallback: bool = True,
    ) -> OcrResult:
        if prefer_advanced and self.advanced.is_available():
            try:
                return self.advanced.recognize(request)
            except Exception as exc:
                if not allow_fallback:
                    raise
                fallback = self.basic.recognize(request)
                return replace(
                    fallback,
                    warnings=[
                        *fallback.warnings,
                        f"Unlimited-OCR failed; Basic OCR fallback was used ({type(exc).__name__}).",
                    ],
                )
        fallback = self.basic.recognize(request)
        if prefer_advanced:
            return replace(
                fallback,
                warnings=[
                    *fallback.warnings,
                    "Unlimited-OCR is not ready; Basic OCR fallback was used.",
                ],
            )
        return fallback


_MANAGED_PROVIDER: UnlimitedOCRProvider | None = None


def get_managed_unlimited_ocr_provider() -> UnlimitedOCRProvider:
    global _MANAGED_PROVIDER
    if _MANAGED_PROVIDER is None:
        _MANAGED_PROVIDER = UnlimitedOCRProvider()
    return _MANAGED_PROVIDER


def shutdown_managed_unlimited_ocr_provider() -> None:
    global _MANAGED_PROVIDER
    if _MANAGED_PROVIDER is not None:
        _MANAGED_PROVIDER.unload()
        _MANAGED_PROVIDER = None


def _runtime_python(environment_root: Path, manager: str = "uv") -> Path:
    if os.name == "nt" and manager == "conda":
        return environment_root / "python.exe"
    return (
        environment_root / "Scripts" / "python.exe"
        if os.name == "nt"
        else environment_root / "bin" / "python"
    )


def _safe_worker_options(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {"prompt", "max_length"}
    return {key: item for key, item in value.items() if key in allowed and isinstance(item, (str, int))}


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _worker_error_code(command: str, error: Any) -> ErrorCode:
    text = str(error).casefold()
    if "out of memory" in text or "oom" in text:
        return ErrorCode.CUDA_OOM if "cuda" in text else ErrorCode.RAM_OOM
    if command == "load":
        return ErrorCode.MODEL_LOAD_FAILED
    if "cuda" in text:
        return ErrorCode.PYTORCH_CUDA_MISMATCH
    return ErrorCode.INFERENCE_FAILED


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
