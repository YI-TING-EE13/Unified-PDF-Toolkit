"""User-facing hardware analysis, informed consent, setup, and cleanup UI."""

from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from ..ocr.consent import clear_advanced_ocr_consent
from ..ocr.deployment.consent import (
    REQUIRED_INSTALL_ACKNOWLEDGEMENTS,
    DeploymentConsent,
    build_consent_summary,
)
from ..ocr.deployment.errors import DeploymentFailure
from ..ocr.deployment.models import CompatibilityStatus, InstallStepRecord
from ..ocr.deployment.orchestrator import CancellationToken, DeploymentCleanup
from ..ocr.deployment.providers import (
    UnlimitedOCRProvider,
    shutdown_managed_unlimited_ocr_provider,
)
from ..ocr.deployment.validation_assets import create_validation_suite
from ..ocr.local_model import clear_local_model_runtime_config

_ACTIVE_LOCK = threading.Lock()
_ACTIVE_SETUPS: list[tuple[CancellationToken, threading.Event]] = []

ACK_LABELS = {
    "large_download": "I understand that setup downloads about the amount shown above.",
    "private_environment": "I allow the APP to create a private Python environment and model cache.",
    "custom_code": "I understand that pinned Hugging Face custom model code will run locally.",
    "resource_usage": "I understand the model can use substantial RAM, VRAM, disk, and processing time.",
    "local_processing_and_temporary_files": "I understand PDF pages are rendered to temporary local images and are not uploaded.",
    "no_performance_guarantee": "I understand OCR accuracy, speed, and OOM-free operation are not guaranteed.",
}


def cancel_active_setups(*, wait_seconds: float = 6.0) -> None:
    """Cancel active installer subprocesses before the main APP exits."""

    with _ACTIVE_LOCK:
        active = list(_ACTIVE_SETUPS)
    for token, _done in active:
        token.cancel()
    deadline = time.monotonic() + max(0.0, wait_seconds)
    for _token, done in active:
        done.wait(max(0.0, deadline - time.monotonic()))


class UnlimitedOcrSetupDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("Managed Local Unlimited-OCR Setup")
        self.geometry("920x760")
        self.minsize(780, 620)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.provider = UnlimitedOCRProvider()
        self.environment = None
        self.compatibility = None
        self.plan = None
        self.consent_summary: dict[str, Any] | None = None
        self.last_journal: dict[str, Any] | None = None
        self.last_error: dict[str, Any] | None = None
        self.cancellation: CancellationToken | None = None
        self.done_event: threading.Event | None = None
        self.running = False
        self.cleanup_running = False
        self.close_after_stop = False
        self.ack_vars = {
            key: tk.BooleanVar(value=False) for key in REQUIRED_INSTALL_ACKNOWLEDGEMENTS
        }
        self._build_ui()
        self.after(50, self._analyze)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        ttk.Label(
            outer,
            text="Advanced Local OCR - Device Analysis and Setup",
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=(
                "Analysis is read-only. No model, AI runtime, Driver, CUDA Toolkit, PATH, "
                "or system Python change occurs until you explicitly choose Install and Enable."
            ),
            wraplength=860,
        ).grid(row=1, column=0, sticky="ew", pady=(6, 12))

        body = ttk.Frame(outer)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        self.status_var = tk.StringVar(value="Analyzing this computer...")
        ttk.Label(body, textvariable=self.status_var, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        notebook = ttk.Notebook(body)
        notebook.grid(row=1, column=0, sticky="nsew")
        summary_tab = ttk.Frame(notebook, padding=10)
        consent_tab = ttk.Frame(notebook, padding=10)
        progress_tab = ttk.Frame(notebook, padding=10)
        notebook.add(summary_tab, text="Summary")
        notebook.add(consent_tab, text="Consent")
        notebook.add(progress_tab, text="Progress")

        self.summary_text = tk.Text(summary_tab, wrap="word", height=18, state="disabled")
        summary_scroll = ttk.Scrollbar(summary_tab, command=self.summary_text.yview)
        self.summary_text.configure(yscrollcommand=summary_scroll.set)
        self.summary_text.pack(side="left", fill="both", expand=True)
        summary_scroll.pack(side="right", fill="y")

        ttk.Label(
            consent_tab,
            text=(
                "Review every item. These boxes are never preselected. Consent applies only "
                "to the exact plan and model revision shown on the Summary tab."
            ),
            wraplength=820,
        ).pack(anchor="w", pady=(0, 8))
        for key in REQUIRED_INSTALL_ACKNOWLEDGEMENTS:
            ttk.Checkbutton(
                consent_tab,
                text=ACK_LABELS[key],
                variable=self.ack_vars[key],
                command=self._update_install_state,
            ).pack(anchor="w", fill="x", pady=4)

        self.progress_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(progress_tab, variable=self.progress_var, maximum=100).pack(
            fill="x", pady=(0, 10)
        )
        self.progress_text = tk.Text(progress_tab, wrap="word", height=17, state="disabled")
        self.progress_text.pack(fill="both", expand=True)
        progress_actions = ttk.Frame(progress_tab)
        progress_actions.pack(fill="x", pady=(10, 0))
        self.pause_button = ttk.Button(
            progress_actions, text="Pause", command=self._pause, state="disabled"
        )
        self.pause_button.pack(side="left")
        self.cancel_button = ttk.Button(
            progress_actions, text="Cancel Setup", command=self._cancel, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=(8, 0))

        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.install_button = ttk.Button(
            actions,
            text="Install and Enable",
            command=self._begin_install,
            state="disabled",
        )
        self.install_button.pack(side="right")
        ttk.Button(actions, text="Not Now", command=self._close).pack(side="right", padx=(0, 8))
        self.details_button = ttk.Button(
            actions,
            text="View Technical Details",
            command=self._show_technical_details,
            state="disabled",
        )
        self.details_button.pack(side="left")
        self.uninstall_button = ttk.Button(
            actions,
            text="Uninstall Managed Runtime",
            command=self._uninstall_runtime,
            state="disabled",
        )
        self.uninstall_button.pack(side="left", padx=(8, 0))
        self.remove_all_button = ttk.Button(
            actions,
            text="Remove Runtime, Model and Cache",
            command=self._remove_all,
            state="disabled",
        )
        self.remove_all_button.pack(side="left", padx=(8, 0))

    def _analyze(self) -> None:
        if self.running:
            return
        self.status_var.set("Analyzing this computer...")
        threading.Thread(target=self._analyze_worker, daemon=True).start()

    def _analyze_worker(self) -> None:
        try:
            environment, compatibility, plan = self.provider.analyze()
            summary = build_consent_summary(compatibility, plan)
            available = self.provider.is_available()
            managed_data_exists = (
                Path(plan.runtime_root).exists()
                or Path(plan.model_cache_dir).exists()
            )
        except Exception as exc:
            self.after(0, lambda error=exc: self._analysis_failed(error))
            return
        self.after(
            0,
            lambda: self._analysis_complete(
                environment,
                compatibility,
                plan,
                summary,
                available,
                managed_data_exists,
            ),
        )

    def _analysis_complete(
        self,
        environment: Any,
        compatibility: Any,
        plan: Any,
        summary: dict[str, Any],
        available: bool,
        managed_data_exists: bool,
    ) -> None:
        self.environment = environment
        self.compatibility = compatibility
        self.plan = plan
        self.consent_summary = summary
        self.details_button.configure(state="normal")
        self.status_var.set(
            f"Compatibility: {compatibility.status.value} "
            f"(confidence {compatibility.confidence:.0%}, risk {compatibility.risk_level.value})"
        )
        self._set_text(self.summary_text, _format_summary(environment, compatibility, plan, summary))
        self.uninstall_button.configure(
            state="normal" if Path(plan.runtime_root).exists() else "disabled"
        )
        self.remove_all_button.configure(
            state="normal" if managed_data_exists else "disabled"
        )
        self._update_install_state()

    def _analysis_failed(self, exc: Exception) -> None:
        self.last_error = {"type": type(exc).__name__, "message": str(exc)}
        self.status_var.set("Environment analysis failed safely. No changes were made.")
        self.details_button.configure(state="normal")

    def _update_install_state(self) -> None:
        allowed = (
            not self.running
            and self.plan is not None
            and self.plan.executable
            and self.compatibility.status
            not in {CompatibilityStatus.UNSUPPORTED, CompatibilityStatus.UNKNOWN}
            and all(var.get() for var in self.ack_vars.values())
        )
        self.install_button.configure(state="normal" if allowed else "disabled")

    def _begin_install(self) -> None:
        if self.running or self.plan is None or self.compatibility is None:
            return
        try:
            consent = DeploymentConsent.create(
                plan=self.plan,
                metadata_revision=self.compatibility.metadata_revision,
                acknowledgements={key: var.get() for key, var in self.ack_vars.items()},
            )
        except ValueError as exc:
            messagebox.showerror("Consent Required", str(exc), parent=self)
            return
        self.running = True
        self.close_after_stop = False
        self.cancellation = CancellationToken()
        self.done_event = threading.Event()
        with _ACTIVE_LOCK:
            _ACTIVE_SETUPS.append((self.cancellation, self.done_event))
        self.install_button.configure(state="disabled")
        self.pause_button.configure(state="normal")
        self.cancel_button.configure(state="normal")
        self.status_var.set("Setup started. You can pause or cancel safely.")
        self._append_progress("Setup started with explicit plan-bound consent.\n")
        threading.Thread(
            target=self._install_worker,
            args=(consent, self.cancellation, self.done_event),
            daemon=True,
        ).start()

    def _install_worker(
        self,
        consent: DeploymentConsent,
        cancellation: CancellationToken,
        done_event: threading.Event,
    ) -> None:
        try:
            validation_root = Path(self.plan.runtime_root) / "state" / "validation-assets"
            cases = create_validation_suite(validation_root)
            journal = self.provider.setup(
                consent=consent,
                cancellation=cancellation,
                progress_callback=lambda record: self.after(
                    0, lambda item=record: self._progress_update(item)
                ),
                validation_images=[case.image_path for case in cases],
                validation_expectations={
                    str(case.image_path): case.expected_terms for case in cases
                },
            )
        except DeploymentFailure as exc:
            error = exc.error.to_dict()
            self.after(0, lambda value=error: self._install_failed(value))
        except Exception as exc:
            error = {
                "error_code": "UNKNOWN_ERROR",
                "title": "Unexpected setup error",
                "user_message": "Setup stopped safely. No system-wide runtime was modified.",
                "technical_details": f"{type(exc).__name__}: {exc}",
            }
            self.after(
                0,
                lambda value=error: self._install_failed(value),
            )
        else:
            self.after(0, lambda: self._install_finished(journal))
        finally:
            done_event.set()
            with _ACTIVE_LOCK:
                try:
                    _ACTIVE_SETUPS.remove((cancellation, done_event))
                except ValueError:
                    pass

    def _progress_update(self, record: InstallStepRecord) -> None:
        stage_count = 14
        try:
            index = list(record.stage.__class__).index(record.stage)
        except ValueError:
            index = 0
        self.progress_var.set(((index + record.progress) / stage_count) * 100)
        self.status_var.set(record.message)
        self._append_progress(
            f"[{record.stage.value}] {record.status.value}: {record.message}\n"
        )

    def _install_finished(self, journal: dict[str, Any]) -> None:
        self.running = False
        self.last_journal = journal
        self.pause_button.configure(state="disabled")
        self.cancel_button.configure(state="disabled")
        statuses = [step.get("status") for step in journal.get("steps", [])]
        if statuses and statuses[-1] == "SUCCEEDED":
            self.progress_var.set(100)
            self.status_var.set("Unlimited-OCR setup and validation completed.")
            messagebox.showinfo(
                "Setup Complete",
                "The managed provider passed setup stages and is registered with the APP.",
                parent=self,
            )
        elif "PAUSED" in statuses:
            self.status_var.set("Setup paused safely. Review the same plan and choose Resume.")
            self.install_button.configure(text="Resume Installation")
        elif "CANCELLED" in statuses:
            self.status_var.set("Setup cancelled safely. Verified cache data is retained for resume.")
            self.install_button.configure(text="Resume Installation")
        self._update_install_state()
        if self.close_after_stop:
            self.destroy()

    def _install_failed(self, error: dict[str, Any]) -> None:
        self.running = False
        self.last_error = error
        self.pause_button.configure(state="disabled")
        self.cancel_button.configure(state="disabled")
        self.status_var.set(str(error.get("user_message", "Setup failed safely.")))
        self._append_progress(
            f"ERROR {error.get('error_code', 'UNKNOWN_ERROR')}: "
            f"{error.get('user_message', '')}\n"
        )
        self.details_button.configure(state="normal")
        self._update_install_state()
        if not self.close_after_stop:
            messagebox.showerror(
                str(error.get("title", "Setup Error")),
                str(error.get("user_message", "Setup failed safely.")),
                parent=self,
            )
        else:
            self.destroy()

    def _pause(self) -> None:
        if self.cancellation:
            self.cancellation.pause()
            self.status_var.set("Pausing safely after the current process is stopped...")
            self.pause_button.configure(state="disabled")

    def _cancel(self) -> None:
        if self.cancellation:
            self.cancellation.cancel()
            self.status_var.set("Cancelling and cleaning up active subprocesses...")
            self.pause_button.configure(state="disabled")
            self.cancel_button.configure(state="disabled")

    def _close(self) -> None:
        if self.cleanup_running:
            self.close_after_stop = True
            self.status_var.set("Waiting for safe cleanup to finish before closing...")
            return
        if self.running and self.cancellation:
            self.close_after_stop = True
            self.cancellation.cancel()
            self.status_var.set("Stopping setup safely before closing...")
            return
        self.destroy()

    def _show_technical_details(self) -> None:
        details = {
            "environment": self.environment.to_dict() if self.environment else None,
            "compatibility": self.compatibility.to_dict() if self.compatibility else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "consent_summary": self.consent_summary,
            "journal": self.last_journal,
            "last_error": self.last_error,
        }
        window = tk.Toplevel(self)
        window.title("Unlimited-OCR Technical Details")
        window.geometry("900x680")
        text = tk.Text(window, wrap="none")
        y_scroll = ttk.Scrollbar(window, command=text.yview)
        x_scroll = ttk.Scrollbar(window, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        text.insert("1.0", json.dumps(details, ensure_ascii=False, indent=2))
        text.configure(state="disabled")

    def _uninstall_runtime(self) -> None:
        if not self.plan or not messagebox.askyesno(
            "Uninstall Managed Runtime",
            "Remove the private Python runtime? The model cache will be kept for reuse.",
            parent=self,
        ):
            return
        self._start_cleanup(
            remove_model=False,
            clear_download_cache=False,
            success_message="Managed runtime removed. Model cache was kept.",
        )

    def _remove_all(self) -> None:
        if not self.plan or not messagebox.askyesno(
            "Remove Runtime, Model and Cache",
            "Permanently remove the private runtime, all managed model snapshots, and managed caches?",
            parent=self,
        ):
            return
        self._start_cleanup(
            remove_model=True,
            clear_download_cache=True,
            success_message=(
                "Managed runtime, model snapshots, and caches removed."
            ),
        )

    def _start_cleanup(
        self,
        *,
        remove_model: bool,
        clear_download_cache: bool,
        success_message: str,
    ) -> None:
        if self.running or self.plan is None:
            return
        self.running = True
        self.cleanup_running = True
        self.install_button.configure(state="disabled")
        self.uninstall_button.configure(state="disabled")
        self.remove_all_button.configure(state="disabled")
        self.status_var.set("Removing only APP-managed Unlimited-OCR data...")
        plan = self.plan

        def worker() -> None:
            try:
                self.provider.unload(force=True)
                shutdown_managed_unlimited_ocr_provider()
                DeploymentCleanup(plan).uninstall(
                    confirmed=True,
                    remove_model=remove_model,
                    clear_download_cache=clear_download_cache,
                )
                clear_local_model_runtime_config()
                clear_advanced_ocr_consent()
            except Exception as exc:
                self.after(0, lambda error=exc: self._cleanup_failed(error))
            else:
                self.after(0, lambda: self._cleanup_finished(success_message))

        threading.Thread(target=worker, daemon=True).start()

    def _cleanup_finished(self, message: str) -> None:
        self.running = False
        self.cleanup_running = False
        self.status_var.set(message)
        if self.close_after_stop:
            self.destroy()
            return
        self._analyze()

    def _cleanup_failed(self, exc: Exception) -> None:
        self.running = False
        self.cleanup_running = False
        self.last_error = {"type": type(exc).__name__, "message": str(exc)}
        self.status_var.set("Cleanup could not finish; no unmanaged path was removed.")
        messagebox.showerror(
            "Cleanup Error",
            "Some APP-managed data could not be removed. Close processes using those files and retry.",
            parent=self,
        )
        if self.close_after_stop:
            self.destroy()
            return
        self._analyze()

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _append_progress(self, value: str) -> None:
        self.progress_text.configure(state="normal")
        self.progress_text.insert("end", value)
        self.progress_text.see("end")
        self.progress_text.configure(state="disabled")


def open_unlimited_ocr_setup(parent: tk.Misc) -> UnlimitedOcrSetupDialog:
    return UnlimitedOcrSetupDialog(parent)


def _format_summary(environment: Any, compatibility: Any, plan: Any, summary: dict[str, Any]) -> str:
    gpu = _best_nvidia_gpu_for_display(environment.gpu)
    setup_allowed = bool(summary.get("setup_allowed"))
    lines = [
        f"Decision: {compatibility.status.value}",
        f"Confidence: {compatibility.confidence:.0%}",
        f"Risk: {compatibility.risk_level.value}",
        f"APP compatibility: {compatibility.app_compatibility.get('status', 'unknown')}",
        f"Basic OCR: {compatibility.basic_ocr.get('status', 'unknown')}",
        f"Recommended provider: {compatibility.recommended_provider}",
        f"Setup allowed: {'Yes' if setup_allowed else 'No'}",
        (
            "Recommendation for this device: Installation may proceed after explicit consent."
            if setup_allowed
            else (
                "Recommendation for this device: Do not install Unlimited-OCR; use the Tesseract fallback."
                if compatibility.basic_ocr.get("status") == "AVAILABLE"
                else "Recommendation for this device: Do not install Unlimited-OCR; install Tesseract to enable basic OCR."
            )
        ),
        "",
        "Detected device",
        f"- OS: {environment.os.get('platform')}",
        f"- CPU: {environment.cpu.get('model')}",
        f"- RAM: {_format_bytes(environment.memory.get('total_bytes'))}",
        f"- GPU: {gpu.get('name', 'No supported NVIDIA GPU')}",
        f"- VRAM: {_format_bytes(gpu.get('vram_total_bytes'))}",
        f"- NVIDIA Driver: {environment.nvidia_driver.get('driver_version')}",
        f"- CUDA Driver API: {environment.cuda.get('driver_api_version')}",
        f"- Installed CUDA Toolkit: {environment.cuda.get('toolkit_version') or 'not found'} (not modified)",
        f"- Free disk: {_format_bytes(environment.storage.get('free_bytes'))}",
        "",
        "Installation facts",
        f"- Fully local processing: {'Yes' if summary['local_only'] else 'No'}",
        f"- Documents leave this device: {'Yes' if summary['data_leaves_device'] else 'No'}",
        f"- Estimated download: {_format_bytes(summary['estimated_download_bytes'])}",
        f"- Optional uv prerequisite download: {_format_bytes(summary['prerequisite_download_bytes'])}",
        f"- Estimated installed disk use: {_format_bytes(summary['estimated_disk_usage_bytes'])}",
        f"- Minimum / recommended RAM: {_format_bytes(summary['minimum_ram_bytes'])} / "
        f"{_format_bytes(summary['recommended_ram_bytes'])}",
        f"- Estimated VRAM target: {_format_bytes(summary['estimated_vram_bytes'])}",
        f"- Administrator rights: {'Required' if summary['requires_admin'] else 'Not required'}",
        "- NVIDIA Driver update: Not included",
        "- System CUDA modification: Not included",
        "- PATH/global Python modification: Not included",
        f"- Candidate backend: {summary['backend']}",
        f"- Recommended backend: {summary['recommended_backend']}",
        f"- Recommended runtime: {summary['recommended_runtime'] or 'none'}",
        f"- Private runtime: {summary['runtime_root']}",
        f"- Private model cache: {summary['model_cache_dir']}",
        f"- Model revision: {summary['model_revision']}",
        f"- Plan type: {'Executable' if plan.executable else 'Blocked informational only'}",
        "",
        "Why Unlimited-OCR may help on supported devices",
        summary["why_recommended"],
        summary["comparison_to_basic_ocr"],
        "",
        "Requirements met",
        *[f"- {item}" for item in compatibility.requirements_met],
        "",
        "Required changes",
        *[f"- {item}" for item in compatibility.required_changes],
        "",
        "Known conflicts and limitations",
        *[f"- {item}" for item in compatibility.conflicts],
        f"- {summary['cannot_guarantee']}",
        "",
        "Reversible changes",
        *[f"- {item}" for item in plan.reversible_changes],
    ]
    if compatibility.requirements_missing:
        lines.extend(
            ["", "Missing requirements", *[f"- {item}" for item in compatibility.requirements_missing]]
        )
    if plan.blocked_reasons:
        lines.extend(["", "Setup blockers", *[f"- {item}" for item in plan.blocked_reasons]])
    return "\n".join(lines)


def _best_nvidia_gpu_for_display(items: Any) -> dict[str, Any]:
    candidates = [item for item in items if str(item.get("vendor", "")).upper() == "NVIDIA"]
    if not candidates:
        return {}

    def vram(item: dict[str, Any]) -> int:
        try:
            return int(item.get("vram_total_bytes") or 0)
        except (TypeError, ValueError):
            return 0

    return max(candidates, key=vram)


def _format_bytes(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if number < 1024 or unit == "TiB":
            return f"{number:.1f} {unit}"
        number /= 1024
    return "unknown"
