"""Settings and recent activity view."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional

from ...base.tool import BaseTool
from ...ocr.consent import (
    DEFAULT_ADVANCED_OCR_MODEL_ID,
    DEFAULT_ADVANCED_OCR_PROVIDER,
    clear_advanced_ocr_consent,
    get_saved_advanced_ocr_consent,
    load_advanced_ocr_consent,
    save_advanced_ocr_consent,
)
from ...ocr.local_model import (
    LOCAL_MODEL_DEVICE_AUTO,
    LOCAL_MODEL_DEVICE_CPU,
    LOCAL_MODEL_DEVICE_CUDA,
    LOCAL_MODEL_MODE_DISABLED,
    LOCAL_MODEL_MODE_FAKE_WORKER,
    LOCAL_MODEL_MODE_IN_PROCESS_FUTURE,
    LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LocalModelRuntimeConfig,
    clear_local_model_runtime_config,
    load_local_model_runtime_config,
    save_local_model_runtime_config,
)
from ...ui.advanced_ocr_consent import request_advanced_ocr_consent
from ...ui.components import responsive_wraplength
from ...utils.settings import (
    clear_recent_paths,
    get_recent_paths,
    get_setting,
    set_setting,
)


class SettingsTool(BaseTool):
    """GUI tool for global preferences and recent activity."""

    name: str = "Settings / Recent"
    icon: str = "[SET]"

    RECENT_KEYS = (
        ("recent.inputs", "Recent Inputs"),
        ("recent.outputs", "Recent Outputs"),
        ("recent.reports", "Recent Reports"),
    )

    def render(self, parent: ttk.Frame) -> None:
        self.parent = parent
        prefs = ttk.LabelFrame(parent, text="Global Output Preferences", padding=10)
        prefs.pack(fill="x", pady=(0, 10))

        ttk.Label(prefs, text="When an output file already exists:").pack(side="left")
        self.conflict_var = tk.StringVar(
            value=get_setting("output.conflict_policy", "rename")
        )
        ttk.Combobox(
            prefs,
            textvariable=self.conflict_var,
            values=["rename", "overwrite", "skip"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=10)
        ttk.Button(
            prefs,
            text="Save",
            command=self._save_preferences,
            style="Accent.TButton",
        ).pack(side="left")

        consent_frame = ttk.LabelFrame(
            parent, text="Experimental Advanced Local AI OCR Consent", padding=10
        )
        consent_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            consent_frame,
            text=(
                "Experimental local Unlimited-OCR is optional, disabled by "
                "default, and runs only on this computer with user-managed "
                "runtime/model files. Consent records acknowledgement for "
                "local model download/cache, custom model code / "
                "trust_remote_code, GPU/VRAM, temporary page images, and the "
                "no-upload boundary."
            ),
            wraplength=responsive_wraplength(parent),
        ).pack(anchor="w", pady=(0, 6))
        self.advanced_ocr_status_var = tk.StringVar()
        ttk.Label(
            consent_frame,
            textvariable=self.advanced_ocr_status_var,
            wraplength=responsive_wraplength(parent),
        ).pack(anchor="w", pady=(0, 8))
        consent_actions = ttk.Frame(consent_frame)
        consent_actions.pack(fill="x")
        ttk.Button(
            consent_actions,
            text="Review / Save Consent",
            command=self._review_advanced_ocr_consent,
        ).pack(side="left")
        ttk.Button(
            consent_actions,
            text="Reset Consent",
            command=self._reset_advanced_ocr_consent,
        ).pack(side="left", padx=(8, 0))

        managed_frame = ttk.LabelFrame(
            parent, text="Managed Unlimited-OCR Setup", padding=10
        )
        managed_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            managed_frame,
            text=(
                "Analyze this computer, review model and hardware costs, then optionally create "
                "an isolated runtime, download a pinned model, validate it, benchmark it, and "
                "register it with the APP. Analysis alone never downloads or modifies the system."
            ),
            wraplength=responsive_wraplength(parent),
        ).pack(anchor="w", pady=(0, 8))
        ttk.Button(
            managed_frame,
            text="Analyze / Install / Manage Unlimited-OCR",
            command=self._open_managed_unlimited_ocr_setup,
        ).pack(anchor="w")

        runtime_frame = ttk.LabelFrame(
            parent, text="Experimental Local Model OCR Runtime", padding=10
        )
        runtime_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            runtime_frame,
            text=(
                "Experimental Local Unlimited-OCR is beta local AI OCR. It "
                "runs on this computer only when explicitly enabled, keeps "
                "Tesseract as the default OCR backend, and requires a local "
                "model folder plus a uv-managed OCR runtime such as "
                ".venv-ocr-runtime. There is no model download, cloud upload, "
                "or server start action here."
            ),
            wraplength=responsive_wraplength(parent),
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        self.local_model_status_var = tk.StringVar()
        ttk.Label(
            runtime_frame,
            textvariable=self.local_model_status_var,
            wraplength=responsive_wraplength(parent),
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.local_model_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            runtime_frame,
            text="Enable experimental local model runtime configuration",
            variable=self.local_model_enabled_var,
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(0, 6))
        self.local_model_mode_var = tk.StringVar(value=LOCAL_MODEL_MODE_DISABLED)
        self.local_model_id_var = tk.StringVar(value=DEFAULT_ADVANCED_OCR_MODEL_ID)
        self.local_model_revision_var = tk.StringVar()
        self.local_model_path_var = tk.StringVar()
        self.local_model_python_var = tk.StringVar()
        self.local_model_worker_var = tk.StringVar()
        ttk.Label(runtime_frame, text="Runtime mode:").grid(row=3, column=0, sticky="w")
        ttk.Combobox(
            runtime_frame,
            textvariable=self.local_model_mode_var,
            values=[
                LOCAL_MODEL_MODE_DISABLED,
                LOCAL_MODEL_MODE_FAKE_WORKER,
                LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
                LOCAL_MODEL_MODE_WORKER_PROCESS,
                LOCAL_MODEL_MODE_IN_PROCESS_FUTURE,
            ],
            state="readonly",
            width=20,
        ).grid(row=3, column=1, sticky="ew", padx=(8, 12), pady=2)
        ttk.Label(runtime_frame, text="Model id:").grid(row=3, column=2, sticky="w")
        ttk.Entry(runtime_frame, textvariable=self.local_model_id_var).grid(
            row=3, column=3, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Label(runtime_frame, text="Model revision pin (optional):").grid(row=4, column=0, sticky="w")
        ttk.Entry(runtime_frame, textvariable=self.local_model_revision_var).grid(
            row=4, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=2
        )
        self.local_model_device_var = tk.StringVar(value=LOCAL_MODEL_DEVICE_AUTO)
        ttk.Label(runtime_frame, text="Device:").grid(row=5, column=0, sticky="w")
        ttk.Combobox(
            runtime_frame,
            textvariable=self.local_model_device_var,
            values=[
                LOCAL_MODEL_DEVICE_AUTO,
                LOCAL_MODEL_DEVICE_CUDA,
                LOCAL_MODEL_DEVICE_CPU,
            ],
            state="readonly",
            width=20,
        ).grid(row=5, column=1, sticky="ew", padx=(8, 12), pady=2)
        ttk.Label(runtime_frame, text="Local Unlimited-OCR model folder:").grid(row=6, column=0, sticky="w")
        ttk.Entry(runtime_frame, textvariable=self.local_model_path_var).grid(
            row=6, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Label(runtime_frame, text="Worker Python path (uv OCR runtime):").grid(row=7, column=0, sticky="w")
        ttk.Entry(runtime_frame, textvariable=self.local_model_python_var).grid(
            row=7, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Label(runtime_frame, text="Worker script path:").grid(row=8, column=0, sticky="w")
        ttk.Entry(runtime_frame, textvariable=self.local_model_worker_var).grid(
            row=8, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=2
        )
        runtime_frame.columnconfigure(1, weight=1)
        runtime_frame.columnconfigure(3, weight=1)
        runtime_actions = ttk.Frame(runtime_frame)
        runtime_actions.grid(row=9, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(
            runtime_actions,
            text="Save Runtime Settings",
            command=self._save_local_model_runtime_settings,
        ).pack(side="left")
        ttk.Button(
            runtime_actions,
            text="Reset Runtime Settings",
            command=self._reset_local_model_runtime_settings,
        ).pack(side="left", padx=(8, 0))

        self.lists: Dict[str, tk.Listbox] = {}
        recent_frame = ttk.Frame(parent)
        recent_frame.pack(fill="both", expand=True)
        recent_frame.columnconfigure((0, 1, 2), weight=1)
        recent_frame.rowconfigure(0, weight=1)

        for column, (key, label) in enumerate(self.RECENT_KEYS):
            frame = ttk.LabelFrame(recent_frame, text=label, padding=10)
            frame.grid(row=0, column=column, sticky="nsew", padx=5)
            listbox = tk.Listbox(frame, height=14)
            listbox.pack(fill="both", expand=True)
            self.lists[key] = listbox
            ttk.Button(
                frame,
                text="Copy Selected",
                command=lambda k=key: self._copy_selected(k),
            ).pack(fill="x", pady=(8, 4))
            ttk.Button(
                frame,
                text="Clear",
                command=lambda k=key: self._clear_recent(k),
            ).pack(fill="x")

        ttk.Button(parent, text="Refresh", command=self._refresh).pack(anchor="e")
        self._refresh()

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        self._save_preferences()

    def _open_managed_unlimited_ocr_setup(self) -> None:
        from ...ui.unlimited_ocr_setup import open_unlimited_ocr_setup

        open_unlimited_ocr_setup(self.parent.winfo_toplevel())

    def _save_preferences(self) -> None:
        set_setting("output.conflict_policy", self.conflict_var.get())
        messagebox.showinfo("Saved", "Output preference saved.")

    def _refresh(self) -> None:
        self._refresh_advanced_ocr_status()
        self._refresh_local_model_runtime_status()
        for key, listbox in self.lists.items():
            listbox.delete(0, tk.END)
            for path in get_recent_paths(key):
                listbox.insert(tk.END, path)

    def _refresh_advanced_ocr_status(self) -> None:
        valid = load_advanced_ocr_consent()
        saved = get_saved_advanced_ocr_consent()
        if valid:
            self.advanced_ocr_status_var.set(
                f"Valid consent saved for {valid.provider}/{valid.model_id} at {valid.timestamp_utc}."
            )
        elif saved:
            self.advanced_ocr_status_var.set(
                "Saved consent exists but is no longer valid for the current provider/model/version."
            )
        else:
            self.advanced_ocr_status_var.set(
                f"No valid consent saved for {DEFAULT_ADVANCED_OCR_PROVIDER}/{DEFAULT_ADVANCED_OCR_MODEL_ID}."
            )

    def _review_advanced_ocr_consent(self) -> None:
        consent = request_advanced_ocr_consent(self.parent.winfo_toplevel())
        if consent is None:
            messagebox.showinfo("Consent Not Saved", "Advanced OCR consent was not saved.")
        else:
            save_advanced_ocr_consent(consent)
            messagebox.showinfo("Saved", "Advanced OCR consent saved.")
        self._refresh_advanced_ocr_status()

    def _reset_advanced_ocr_consent(self) -> None:
        clear_advanced_ocr_consent()
        self._refresh_advanced_ocr_status()
        messagebox.showinfo("Reset", "Advanced OCR consent cleared.")

    def _load_local_model_runtime_config_from_vars(self) -> LocalModelRuntimeConfig:
        mode = self.local_model_mode_var.get()
        enabled = bool(self.local_model_enabled_var.get()) and mode != LOCAL_MODEL_MODE_DISABLED
        return LocalModelRuntimeConfig(
            enabled=enabled,
            mode=mode,
            model_id=self.local_model_id_var.get(),
            model_revision=self.local_model_revision_var.get(),
            model_path=self.local_model_path_var.get(),
            python_executable=self.local_model_python_var.get(),
            worker_script_path=self.local_model_worker_var.get(),
            device_preference=self.local_model_device_var.get(),
        )

    def _apply_local_model_runtime_config(self, config: LocalModelRuntimeConfig) -> None:
        self.local_model_enabled_var.set(config.enabled)
        self.local_model_mode_var.set(config.mode)
        self.local_model_id_var.set(config.model_id)
        self.local_model_revision_var.set(config.model_revision or "")
        self.local_model_path_var.set(config.model_path or "")
        self.local_model_python_var.set(config.python_executable or "")
        self.local_model_worker_var.set(config.worker_script_path or "")
        self.local_model_device_var.set(config.device_preference)

    def _refresh_local_model_runtime_status(self) -> None:
        config = load_local_model_runtime_config()
        self._apply_local_model_runtime_config(config)
        if not config.enabled or config.mode == LOCAL_MODEL_MODE_DISABLED:
            self.local_model_status_var.set("Local model OCR runtime is disabled.")
        else:
            self.local_model_status_var.set(
                "Experimental local model runtime configured as "
                f"{config.mode}; execution remains opt-in, local-only, and "
                "requires the experimental gate plus saved consent."
            )

    def _save_local_model_runtime_settings(self) -> None:
        config = self._load_local_model_runtime_config_from_vars()
        save_local_model_runtime_config(config)
        self._refresh_local_model_runtime_status()
        messagebox.showinfo(
            "Saved",
            "Local model OCR runtime settings saved. Tesseract remains the default; Experimental Local Unlimited-OCR remains opt-in and gated.",
        )

    def _reset_local_model_runtime_settings(self) -> None:
        clear_local_model_runtime_config()
        self._refresh_local_model_runtime_status()
        messagebox.showinfo("Reset", "Local model OCR runtime settings cleared.")

    def _copy_selected(self, key: str) -> None:
        listbox = self.lists[key]
        selection = listbox.curselection()
        if not selection:
            return
        value = listbox.get(selection[0])
        listbox.clipboard_clear()
        listbox.clipboard_append(value)
        messagebox.showinfo("Copied", "Path copied to clipboard.")

    def _clear_recent(self, key: str) -> None:
        clear_recent_paths(key)
        self._refresh()
