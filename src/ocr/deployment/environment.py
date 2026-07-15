"""Cross-platform, read-only environment inspection for local AI OCR."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import psutil

from .models import EnvironmentReport

_MIB = 1024 * 1024
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def default_ocr_data_root() -> Path:
    """Return the user-private root for optional OCR runtimes and models."""

    override = os.environ.get("PDF_TOOLKIT_OCR_DATA_ROOT")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "UnifiedPDFToolkit" / "ocr"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "UnifiedPDFToolkit" / "ocr"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "unified-pdf-toolkit" / "ocr"


class EnvironmentInspector:
    """Collect a structured report without modifying the inspected machine."""

    schema_version = "1.0"

    def __init__(self, *, data_root: Path | None = None, command_timeout: float = 8.0) -> None:
        self.data_root = (data_root or default_ocr_data_root()).expanduser()
        self.command_timeout = max(1.0, float(command_timeout))
        self._warnings: list[str] = []

    def inspect(self) -> EnvironmentReport:
        self._warnings = []
        gpu, nvidia = self._gpu_info()
        report = EnvironmentReport(
            schema_version=self.schema_version,
            generated_at=datetime.now(timezone.utc).isoformat(),
            os=self._os_info(),
            cpu=self._cpu_info(),
            memory=self._memory_info(),
            gpu=tuple(gpu),
            nvidia_driver=nvidia,
            cuda=self._cuda_info(nvidia),
            python=self._python_info(),
            pytorch=self._pytorch_info(),
            storage=self._storage_info(),
            runtime=self._runtime_info(),
            containers=self._container_info(),
            recommendation={"status": "NOT_EVALUATED"},
            warnings=tuple(self._warnings),
        )
        return report

    def _os_info(self) -> dict[str, Any]:
        uname = platform.uname()
        is_wsl = bool(os.environ.get("WSL_DISTRO_NAME")) or "microsoft" in uname.release.lower()
        return {
            "system": uname.system,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
            "architecture": platform.architecture()[0],
            "platform": platform.platform(),
            "is_wsl": is_wsl,
            "wsl_distribution": os.environ.get("WSL_DISTRO_NAME"),
        }

    def _cpu_info(self) -> dict[str, Any]:
        physical = psutil.cpu_count(logical=False)
        logical = psutil.cpu_count(logical=True) or os.cpu_count()
        name = self._cpu_model()
        return {
            "model": name or "unknown",
            "architecture": platform.machine(),
            "physical_cores": physical,
            "logical_cores": logical,
            "frequency_mhz": self._cpu_frequency(),
        }

    def _cpu_model(self) -> str:
        if sys.platform == "win32":
            result = self._run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name",
                ]
            )
            if result["returncode"] == 0 and result["stdout"].strip():
                return result["stdout"].strip()
        elif sys.platform.startswith("linux"):
            try:
                cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
            except OSError:
                cpuinfo = ""
            for key in ("model name", "hardware", "processor"):
                match = re.search(
                    rf"^{re.escape(key)}\s*:\s*(.+)$",
                    cpuinfo,
                    re.MULTILINE | re.IGNORECASE,
                )
                if match and match.group(1).strip():
                    return match.group(1).strip()
        elif sys.platform == "darwin":
            result = self._run(["sysctl", "-n", "machdep.cpu.brand_string"])
            if result["returncode"] == 0 and result["stdout"].strip():
                return result["stdout"].strip()
        return (
            platform.processor().strip()
            or os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
            or "unknown"
        )

    @staticmethod
    def _cpu_frequency() -> float | None:
        try:
            value = psutil.cpu_freq()
        except (AttributeError, OSError):
            return None
        return round(float(value.current), 2) if value else None

    @staticmethod
    def _memory_info() -> dict[str, Any]:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total_bytes": int(memory.total),
            "available_bytes": int(memory.available),
            "used_percent": float(memory.percent),
            "swap_total_bytes": int(swap.total),
            "swap_free_bytes": int(swap.free),
        }

    def _gpu_info(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        try:
            return self._gpu_info_nvml()
        except Exception as exc:  # NVML has platform-specific exception classes
            self._warnings.append(f"NVML unavailable: {type(exc).__name__}: {exc}")
        gpu, nvidia = self._gpu_info_nvidia_smi()
        if sys.platform == "win32":
            gpu = self._merge_gpu_lists(gpu, self._windows_video_controllers())
        elif sys.platform == "darwin":
            gpu = self._merge_gpu_lists(gpu, self._mac_video_controllers())
        elif not gpu:
            gpu = self._linux_video_controllers()
        return gpu, nvidia

    def _gpu_info_nvml(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        import pynvml

        pynvml.nvmlInit()
        try:
            driver = _decode(pynvml.nvmlSystemGetDriverVersion())
            cuda_driver = None
            get_cuda = getattr(pynvml, "nvmlSystemGetCudaDriverVersion_v2", None)
            if get_cuda is None:
                get_cuda = getattr(pynvml, "nvmlSystemGetCudaDriverVersion", None)
            if get_cuda:
                raw = int(get_cuda())
                cuda_driver = _format_cuda_driver_version(raw)
            devices: list[dict[str, Any]] = []
            for index in range(int(pynvml.nvmlDeviceGetCount())):
                handle = pynvml.nvmlDeviceGetHandleByIndex(index)
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                capability = None
                get_capability = getattr(pynvml, "nvmlDeviceGetCudaComputeCapability", None)
                if get_capability:
                    try:
                        major, minor = get_capability(handle)
                        capability = f"{major}.{minor}"
                    except Exception:
                        capability = None
                pci = pynvml.nvmlDeviceGetPciInfo(handle)
                devices.append(
                    {
                        "index": index,
                        "vendor": "NVIDIA",
                        "name": _decode(pynvml.nvmlDeviceGetName(handle)),
                        "uuid": _decode(pynvml.nvmlDeviceGetUUID(handle)),
                        "vram_total_bytes": int(memory.total),
                        "vram_free_bytes": int(memory.free),
                        "driver_version": driver,
                        "compute_capability": capability,
                        "pci_bus_id": _decode(getattr(pci, "busId", "")),
                        "source": "nvml",
                    }
                )
            return devices, {
                "available": True,
                "driver_version": driver,
                "cuda_driver_api_version": cuda_driver,
                "nvidia_smi_available": shutil.which("nvidia-smi") is not None,
                "source": "nvml",
            }
        finally:
            pynvml.nvmlShutdown()

    def _gpu_info_nvidia_smi(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        fields = (
            "index,name,uuid,memory.total,memory.free,driver_version,pci.bus_id,compute_cap"
        )
        result = self._run(["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"])
        if not result["available"] or result["returncode"] != 0:
            return [], {
                "available": False,
                "driver_version": None,
                "cuda_driver_api_version": None,
                "nvidia_smi_available": bool(result["available"]),
                "error": result.get("error") or result.get("stderr"),
                "source": "nvidia-smi",
            }
        rows = list(csv.reader(io.StringIO(result["stdout"])))
        devices: list[dict[str, Any]] = []
        for row in rows:
            if len(row) < 8:
                continue
            devices.append(
                {
                    "index": _safe_int(row[0]),
                    "vendor": "NVIDIA",
                    "name": row[1].strip(),
                    "uuid": row[2].strip(),
                    "vram_total_bytes": (_safe_int(row[3]) or 0) * _MIB,
                    "vram_free_bytes": (_safe_int(row[4]) or 0) * _MIB,
                    "driver_version": row[5].strip(),
                    "pci_bus_id": row[6].strip(),
                    "compute_capability": row[7].strip() or None,
                    "source": "nvidia-smi",
                }
            )
        header = self._run(["nvidia-smi"])
        cuda_version = _regex_group(
            header.get("stdout", ""),
            r"CUDA(?:\s+UMD)?\s+Version:\s*([\d.]+)",
        )
        driver = devices[0]["driver_version"] if devices else None
        return devices, {
            "available": bool(devices),
            "driver_version": driver,
            "cuda_driver_api_version": cuda_version,
            "nvidia_smi_available": True,
            "source": "nvidia-smi",
        }

    def _windows_video_controllers(self) -> list[dict[str, Any]]:
        script = (
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,AdapterRAM,PNPDeviceID,DriverVersion | ConvertTo-Json -Compress"
        )
        result = self._run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
        if result["returncode"] != 0 or not result["stdout"].strip():
            return []
        try:
            parsed = json.loads(result["stdout"])
        except json.JSONDecodeError:
            return []
        rows = parsed if isinstance(parsed, list) else [parsed]
        return [
            {
                "index": index,
                "vendor": _gpu_vendor(str(item.get("Name", ""))),
                "name": str(item.get("Name", "unknown")),
                "uuid": None,
                "vram_total_bytes": _safe_int(item.get("AdapterRAM")),
                "vram_free_bytes": None,
                "driver_version": item.get("DriverVersion"),
                "compute_capability": None,
                "pci_bus_id": item.get("PNPDeviceID"),
                "source": "windows-cim",
            }
            for index, item in enumerate(rows)
            if isinstance(item, Mapping)
        ]

    def _mac_video_controllers(self) -> list[dict[str, Any]]:
        result = self._run(["system_profiler", "SPDisplaysDataType", "-json"])
        if result["returncode"] != 0:
            return []
        try:
            rows = json.loads(result["stdout"]).get("SPDisplaysDataType", [])
        except (json.JSONDecodeError, AttributeError):
            return []
        devices = []
        for index, item in enumerate(rows):
            name = str(item.get("sppci_model", item.get("_name", "unknown")))
            devices.append(
                {
                    "index": index,
                    "vendor": _gpu_vendor(name),
                    "name": name,
                    "uuid": None,
                    "vram_total_bytes": None,
                    "vram_free_bytes": None,
                    "driver_version": None,
                    "compute_capability": None,
                    "pci_bus_id": item.get("spdisplays_device-id"),
                    "source": "system_profiler",
                }
            )
        return devices

    def _linux_video_controllers(self) -> list[dict[str, Any]]:
        result = self._run(["lspci", "-nn"])
        if result["returncode"] != 0:
            return []
        devices = []
        for line in result["stdout"].splitlines():
            if not re.search(r"VGA compatible controller|3D controller|Display controller", line, re.I):
                continue
            devices.append(
                {
                    "index": len(devices),
                    "vendor": _gpu_vendor(line),
                    "name": line.split(":", 2)[-1].strip(),
                    "uuid": None,
                    "vram_total_bytes": None,
                    "vram_free_bytes": None,
                    "driver_version": None,
                    "compute_capability": None,
                    "pci_bus_id": line.split()[0],
                    "source": "lspci",
                }
            )
        return devices

    @staticmethod
    def _merge_gpu_lists(primary: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
        names = {str(item.get("name", "")).casefold() for item in primary}
        merged = list(primary)
        for item in extra:
            name = str(item.get("name", "")).casefold()
            if name and not any(name in existing or existing in name for existing in names if existing):
                item = dict(item)
                item["index"] = len(merged)
                merged.append(item)
                names.add(name)
        return merged

    def _cuda_info(self, nvidia: Mapping[str, Any]) -> dict[str, Any]:
        result = self._run(["nvcc", "--version"])
        output = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
        toolkit = _regex_group(output, r"release\s+([\d.]+)")
        return {
            "driver_api_version": nvidia.get("cuda_driver_api_version"),
            "toolkit_installed": bool(result["available"] and result["returncode"] == 0),
            "toolkit_version": toolkit,
            "nvcc_path": result.get("path"),
            "cuda_path": os.environ.get("CUDA_PATH"),
            "note": "A PyTorch bundled CUDA runtime normally does not require a system CUDA Toolkit.",
        }

    def _python_info(self) -> dict[str, Any]:
        tools = {name: self._tool_version(name) for name in ("uv", "conda", "pip")}
        return {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
            "is_virtual_environment": sys.prefix != sys.base_prefix,
            "architecture": platform.architecture()[0],
            "tools": tools,
        }

    def _tool_version(self, name: str) -> dict[str, Any]:
        if name == "pip":
            result = self._run([sys.executable, "-m", "pip", "--version"])
        else:
            executable = self._find_tool(name)
            result = (
                self._run([str(executable), "--version"])
                if executable is not None
                else {
                    "available": False,
                    "returncode": None,
                    "stdout": "",
                    "stderr": "",
                    "path": None,
                }
            )
        return {
            "available": bool(result["available"] and result["returncode"] == 0),
            "path": result.get("path"),
            "version_output": (result.get("stdout") or result.get("stderr") or "").strip(),
        }

    @staticmethod
    def _find_tool(name: str) -> Path | None:
        """Find supported user-level environment managers without modifying PATH."""

        discovered = shutil.which(name)
        if discovered:
            return Path(discovered)

        home = Path.home()
        candidates: list[Path] = []
        if name == "conda":
            if sys.platform == "win32":
                candidates.extend(
                    Path(root) / "Scripts" / "conda.exe"
                    for root in (
                        sys.base_prefix,
                        home / "miniforge3",
                        home / "Miniforge3",
                        home / "miniconda3",
                        home / "Miniconda3",
                        home / "anaconda3",
                        home / "Anaconda3",
                    )
                )
            else:
                candidates.extend(
                    Path(root) / "bin" / "conda"
                    for root in (
                        sys.base_prefix,
                        home / "miniforge3",
                        home / "miniconda3",
                        home / "anaconda3",
                    )
                )
        elif name == "uv":
            executable = "uv.exe" if sys.platform == "win32" else "uv"
            candidates.extend(
                (
                    home / ".local" / "bin" / executable,
                    home / ".cargo" / "bin" / executable,
                )
            )

        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate.resolve()
        return None

    def _pytorch_info(self) -> dict[str, Any]:
        if importlib.util.find_spec("torch") is None:
            return {"installed": False, "version": None, "cuda_available": False, "devices": []}
        probe = (
            "import json,torch; d={'installed':True,'version':torch.__version__,"
            "'torch_cuda_version':torch.version.cuda,'cuda_available':torch.cuda.is_available(),"
            "'cudnn_version':torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,"
            "'devices':[]}; "
            "d['devices']=[{'index':i,'name':torch.cuda.get_device_name(i),"
            "'compute_capability':'.'.join(map(str,torch.cuda.get_device_capability(i)))} "
            "for i in range(torch.cuda.device_count())] if d['cuda_available'] else []; print(json.dumps(d))"
        )
        result = self._run([sys.executable, "-c", probe], timeout=20.0)
        if result["returncode"] != 0:
            return {
                "installed": True,
                "probe_failed": True,
                "cuda_available": False,
                "devices": [],
                "error": (result.get("stderr") or result.get("error") or "unknown error").strip(),
            }
        try:
            return json.loads(result["stdout"])
        except json.JSONDecodeError:
            return {
                "installed": True,
                "probe_failed": True,
                "cuda_available": False,
                "devices": [],
                "error": "PyTorch probe returned invalid JSON.",
            }

    def _storage_info(self) -> dict[str, Any]:
        probe = self.data_root
        while not probe.exists() and probe.parent != probe:
            probe = probe.parent
        usage = shutil.disk_usage(probe)
        return {
            "data_root": str(self.data_root),
            "probe_path": str(probe),
            "total_bytes": int(usage.total),
            "used_bytes": int(usage.used),
            "free_bytes": int(usage.free),
            "writable_parent": os.access(probe, os.W_OK),
        }

    def _runtime_info(self) -> dict[str, Any]:
        return {
            "app_executable": sys.executable,
            "frozen": bool(getattr(sys, "frozen", False)),
            "working_directory": str(Path.cwd()),
            "project_root": str(Path(__file__).resolve().parents[3]),
            "virtual_environment": (
                os.environ.get("VIRTUAL_ENV")
                or (sys.prefix if sys.prefix != sys.base_prefix else None)
            ),
            "ocr_data_root": str(self.data_root),
            "process_id": os.getpid(),
        }

    def _container_info(self) -> dict[str, Any]:
        docker = self._run(["docker", "--version"])
        wsl = {"available": False, "status": None}
        if sys.platform == "win32":
            wsl_result = self._run(["wsl.exe", "--status"])
            wsl = {
                "available": bool(wsl_result["available"] and wsl_result["returncode"] == 0),
                "status": (wsl_result.get("stdout") or wsl_result.get("stderr") or "").strip(),
            }
        return {
            "docker": {
                "available": bool(docker["available"] and docker["returncode"] == 0),
                "path": docker.get("path"),
                "version_output": (docker.get("stdout") or docker.get("stderr") or "").strip(),
            },
            "wsl2": wsl,
        }

    def _run(self, argv: Sequence[str], *, timeout: float | None = None) -> dict[str, Any]:
        executable = shutil.which(argv[0]) if not Path(argv[0]).is_absolute() else argv[0]
        if not executable:
            return {"available": False, "returncode": None, "stdout": "", "stderr": "", "path": None}
        command = [str(executable), *map(str, argv[1:])]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                timeout=timeout or self.command_timeout,
                shell=False,
                creationflags=_CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "available": True,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "path": str(executable),
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "available": True,
            "returncode": completed.returncode,
            "stdout": _decode_command_output(completed.stdout),
            "stderr": _decode_command_output(completed.stderr),
            "path": str(executable),
        }


def _decode(value: Any) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)


def _decode_command_output(value: bytes | str | None) -> str:
    if value is None or isinstance(value, str):
        return value or ""
    if value.startswith((b"\xff\xfe", b"\xfe\xff")) or (
        value and value.count(b"\x00") / len(value) > 0.15
    ):
        try:
            return value.decode("utf-16")
        except UnicodeDecodeError:
            return value.decode("utf-16-le", errors="replace")
    for encoding in ("utf-8", locale.getpreferredencoding(False)):
        try:
            return value.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return value.decode("utf-8", errors="replace")


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _regex_group(value: str, pattern: str) -> str | None:
    match = re.search(pattern, value, re.IGNORECASE)
    return match.group(1) if match else None


def _format_cuda_driver_version(raw: int) -> str | None:
    if raw <= 0:
        return None
    major = raw // 1000
    minor = (raw % 1000) // 10
    return f"{major}.{minor}"


def _gpu_vendor(name: str) -> str:
    lowered = name.casefold()
    if "nvidia" in lowered:
        return "NVIDIA"
    if "amd" in lowered or "radeon" in lowered or "advanced micro devices" in lowered:
        return "AMD"
    if "intel" in lowered:
        return "Intel"
    if "apple" in lowered:
        return "Apple"
    return "Unknown"
