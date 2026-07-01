"""User-facing Document OCR tool.

The default path is Tesseract. Experimental local Unlimited-OCR is visible only
behind an explicit environment gate and must use the killable worker_process
runtime configured by the user.
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Iterable, List, Optional, Sequence

from ...base.tool import BaseTool
from ...ocr.consent import load_advanced_ocr_consent
from ...ocr.document_workflow import (
    DOCUMENT_OCR_BACKEND_TESSERACT,
    DocumentOcrBackendConfig,
    local_unlimited_worker_backend_config,
    run_document_ocr_workflow,
    tesseract_document_backend_config,
    user_safe_ocr_error_message,
)
from ...ocr.exceptions import OcrBackendUnavailableError, OcrConsentRequiredError
from ...ocr.local_model import (
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    load_local_model_runtime_config,
)
from ...ui.components import FileListWidget, OutputActions
from ...utils.file_ops import get_default_save_dir
from ...utils.settings import get_setting, set_setting
from ...utils.workflow import CancellationToken, remember_inputs

SUPPORTED_INPUT_TYPES = [
    ("PDF and Images", "*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
    ("PDF", "*.pdf"),
    ("Images", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
]

TESSERACT_BACKEND_LABEL = "Tesseract OCR (default)"
LOCAL_UNLIMITED_BACKEND_LABEL = (
    "Experimental Local Unlimited-OCR (worker process)"
)
EXPERIMENTAL_LOCAL_OCR_ENV = "PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR"


def experimental_local_ocr_enabled() -> bool:
    """Return true only when experimental local model OCR is explicitly enabled."""

    return os.environ.get(EXPERIMENTAL_LOCAL_OCR_ENV, "").lower() in {
        "1",
        "true",
        "yes",
    }


def available_document_ocr_backend_labels() -> List[str]:
    """Return UI backend labels, always keeping Tesseract first."""

    labels = [TESSERACT_BACKEND_LABEL]
    if experimental_local_ocr_enabled():
        labels.append(LOCAL_UNLIMITED_BACKEND_LABEL)
    return labels


def run_document_ocr_tool_workflow(
    files: Sequence[str],
    output_dir: str,
    formats: Iterable[str],
    *,
    backend_config: DocumentOcrBackendConfig,
    consent=None,
    cancellation_check=None,
    progress_callback=None,
):
    """Run the Document OCR workflow for tests and UI wiring."""

    return run_document_ocr_workflow(
        files,
        output_dir,
        formats,
        backend_config=backend_config,
        consent=consent,
        cancellation_check=cancellation_check,
        progress_callback=progress_callback,
    )


class DocumentOcrTool(BaseTool):
    """Document OCR UI with Tesseract default and gated experimental local model."""

    name: str = "Document OCR"
    icon: str = "[OCR]"

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.cancel_token = CancellationToken()

    def render(self, parent: ttk.Frame) -> None:
        self.parent = parent

        notice = ttk.LabelFrame(parent, text="Local Document OCR", padding=10)
        notice.pack(fill="x", pady=(0, 10))
        ttk.Label(
            notice,
            text=(
                "Default OCR uses Tesseract and runs locally. Experimental Local "
                "Unlimited-OCR, when explicitly enabled, also runs on this "
                "computer with no upload and requires a uv-managed optional "
                "runtime plus a local model folder configured by the user. "
                "It is not production-ready."
            ),
            wraplength=900,
        ).pack(anchor="w")

        self.file_list = FileListWidget(
            parent,
            label="PDF/Image Files",
            filetypes=SUPPORTED_INPUT_TYPES,
            show_ordering=True,
        )
        self.file_list.pack(fill="both", expand=True, pady=(0, 10))

        backend_frame = ttk.LabelFrame(parent, text="OCR Backend", padding=10)
        backend_frame.pack(fill="x", pady=(0, 10))
        self.backend_var = tk.StringVar(value=TESSERACT_BACKEND_LABEL)
        ttk.Label(backend_frame, text="Backend:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            backend_frame,
            textvariable=self.backend_var,
            values=available_document_ocr_backend_labels(),
            state="readonly",
            width=52,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 12))
        backend_frame.columnconfigure(1, weight=1)

        self.experimental_status_var = tk.StringVar()
        ttk.Label(
            backend_frame,
            textvariable=self.experimental_status_var,
            wraplength=850,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._refresh_experimental_status()

        options = ttk.LabelFrame(parent, text="Output Options", padding=10)
        options.pack(fill="x", pady=(0, 10))
        self.txt_var = tk.BooleanVar(value=True)
        self.md_var = tk.BooleanVar(value=False)
        self.language_var = tk.StringVar(
            value=get_setting("document_ocr.tesseract_language", "eng")
        )
        ttk.Checkbutton(options, text="TXT", variable=self.txt_var).pack(side="left")
        ttk.Checkbutton(options, text="Markdown", variable=self.md_var).pack(
            side="left", padx=(10, 0)
        )
        ttk.Label(options, text="Tesseract language:").pack(side="left", padx=(20, 4))
        ttk.Entry(options, textvariable=self.language_var, width=16).pack(side="left")

        out_frame = ttk.Frame(parent)
        out_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(out_frame, text="Output Folder:").pack(side="left")
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(8, 5))
        self.output_entry.insert(
            0,
            get_setting("document_ocr.output_dir", get_default_save_dir("DocumentOCR")),
        )
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(
            side="left"
        )

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(0, 8))
        self.start_btn = ttk.Button(actions, text="Run Document OCR", command=self.execute)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(
            actions, text="Cancel", command=self._cancel, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(parent, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 5))
        self.status_lbl = ttk.Label(parent, text="Ready")
        self.status_lbl.pack(anchor="w")
        self.output_actions = OutputActions(parent)
        self.output_actions.pack(anchor="w", pady=(8, 0))

    def execute(self, params: Optional[Dict] = None) -> None:
        files = self.file_list.get_files()
        if not files:
            messagebox.showwarning("Warning", "No files selected.")
            return
        output_dir = self.output_entry.get()
        if not output_dir:
            messagebox.showwarning("Warning", "Please choose an output folder.")
            return
        formats = self._selected_formats()
        if not formats:
            messagebox.showwarning("Warning", "Select TXT, Markdown, or both.")
            return
        try:
            backend_config = self._backend_config()
        except OcrBackendUnavailableError as exc:
            messagebox.showerror("Error", user_safe_ocr_error_message(exc))
            return

        consent = None
        if backend_config.backend != DOCUMENT_OCR_BACKEND_TESSERACT:
            consent = load_advanced_ocr_consent()
            if consent is None:
                messagebox.showwarning(
                    "Consent Required",
                    (
                        "Experimental Local Unlimited-OCR requires saved advanced "
                        "OCR consent in Settings / Recent before it can run. "
                        "Review the model download, custom-code, GPU/VRAM, and "
                        "temporary page-image acknowledgements first."
                    ),
                )
                return

        set_setting("document_ocr.output_dir", output_dir)
        set_setting("document_ocr.tesseract_language", self.language_var.get())
        remember_inputs(files)
        self.cancel_token.reset()
        self.progress["value"] = 0
        self.output_actions.clear()
        self.status_lbl.config(text="Starting Document OCR...")
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        threading.Thread(
            target=self._run_workflow,
            args=(files, output_dir, formats, backend_config, consent),
            daemon=True,
        ).start()
        self.parent.after(100, self._poll_queue)

    def _backend_config(self) -> DocumentOcrBackendConfig:
        label = self.backend_var.get()
        if label == TESSERACT_BACKEND_LABEL:
            return tesseract_document_backend_config(
                language=self.language_var.get() or "eng"
            )
        if label == LOCAL_UNLIMITED_BACKEND_LABEL:
            if not experimental_local_ocr_enabled():
                raise OcrBackendUnavailableError(
                    "Experimental Local Unlimited-OCR is not enabled."
                )
            config = load_local_model_runtime_config()
            if config.mode != LOCAL_MODEL_MODE_WORKER_PROCESS:
                raise OcrBackendUnavailableError(
                    "Experimental Local Unlimited-OCR requires worker_process runtime mode."
                )
            return local_unlimited_worker_backend_config(config)
        raise OcrBackendUnavailableError("Unsupported Document OCR backend selection.")

    def _selected_formats(self) -> List[str]:
        selected = []
        if self.txt_var.get():
            selected.append("txt")
        if self.md_var.get():
            selected.append("md")
        return selected

    def _refresh_experimental_status(self) -> None:
        if not experimental_local_ocr_enabled():
            self.experimental_status_var.set(
                "Experimental Local Unlimited-OCR is hidden. Set "
                f"{EXPERIMENTAL_LOCAL_OCR_ENV}=1 to show it for local-only testing."
            )
            return
        config = load_local_model_runtime_config()
        self.experimental_status_var.set(
            "Experimental Local Unlimited-OCR is visible. It runs on this computer, "
            "performs no upload, requires Settings / Recent consent plus a "
            f"worker_process local runtime, and is not production-ready. Current mode: "
            f"{config.mode}; device: {config.device_preference}."
        )

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def _cancel(self) -> None:
        self.cancel_token.cancel()
        self.status_lbl.config(text="Cancelling...")

    def _progress(self, current: int, total: int, message: str) -> None:
        self.queue.put(("progress", (current, total, message)))

    def _run_workflow(self, files, output_dir, formats, backend_config, consent) -> None:
        try:
            result = run_document_ocr_tool_workflow(
                files,
                output_dir,
                formats,
                backend_config=backend_config,
                consent=consent,
                cancellation_check=self.cancel_token.is_cancelled,
                progress_callback=self._progress,
            )
            if result.cancelled:
                self.queue.put(("cancelled", result))
            elif result.failed:
                self.queue.put(("error", result))
            else:
                self.queue.put(("done", result))
        except OcrConsentRequiredError as exc:
            self.queue.put(("error_message", user_safe_ocr_error_message(exc)))
        except Exception as exc:
            self.queue.put(("error_message", user_safe_ocr_error_message(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    current, total, message = data
                    pct = (current / total * 100) if total else 0
                    self.progress["value"] = pct
                    self.status_lbl.config(text=message)
                elif msg_type == "done":
                    self._finish()
                    first_output = data.outputs[0].path if data.outputs else ""
                    self.output_actions.set_path(first_output)
                    self.status_lbl.config(
                        text=f"Wrote {len(data.outputs)} OCR output file(s)."
                    )
                    messagebox.showinfo("Done", "Document OCR completed.")
                elif msg_type == "cancelled":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Document OCR cancelled.")
                    messagebox.showinfo("Cancelled", "Document OCR cancelled.")
                elif msg_type == "error":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Document OCR completed with errors.")
                    messagebox.showerror("Error", "\n".join(data.failed))
                elif msg_type == "error_message":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Document OCR failed.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        if self.cancel_btn["state"] == "normal":
            self.parent.after(100, self._poll_queue)

    def _finish(self, reset_progress: bool = False) -> None:
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.progress["value"] = 0 if reset_progress else 100
