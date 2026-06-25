"""Developer-only Document OCR shell for mock-safe advanced OCR wiring.

This tool intentionally exposes only the fake Unlimited-OCR backend. It does
not download models, call local endpoint servers, import AI runtimes, or
perform real OCR inference.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from ...base.tool import BaseTool
from ...ocr import OcrBackendUnavailableError, OcrConsentRequiredError
from ...ocr.consent import load_advanced_ocr_consent
from ...ocr.workflow import (
    AdvancedOcrBackendSelection,
    AdvancedOcrOutput as FakeAiOcrOutput,
    AdvancedOcrWorkflowResult as FakeAiOcrWorkflowResult,
    fake_backend_selection,
    run_advanced_ocr_workflow,
    user_safe_ocr_error_message,
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

FAKE_BACKEND_LABEL = "Fake Unlimited-OCR backend (dev/test only)"


def run_fake_ai_ocr_workflow(
    files: Sequence[str],
    output_dir: str,
    formats: Iterable[str],
    *,
    consent=None,
    cancellation_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> FakeAiOcrWorkflowResult:
    """Run deterministic fake OCR for selected files and write local outputs."""

    return run_advanced_ocr_workflow(
        files,
        output_dir,
        formats,
        selection=fake_backend_selection(),
        consent=consent,
        cancellation_check=cancellation_check,
        progress_callback=progress_callback,
    )


class DevDocumentOcrTool(BaseTool):
    """Hidden developer tool for testing future advanced OCR UI flows."""

    name: str = "[Dev] Document OCR Shell"
    icon: str = "[DEV]"

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.cancel_token = CancellationToken()

    def render(self, parent: ttk.Frame) -> None:
        self.parent = parent

        notice = ttk.LabelFrame(parent, text="Developer/Test Only", padding=10)
        notice.pack(fill="x", pady=(0, 10))
        ttk.Label(
            notice,
            text=(
                "This developer-only shell validates future Document OCR UI "
                "plumbing using only the deterministic fake Unlimited-OCR "
                "backend. It performs no real AI OCR, model download, endpoint "
                "call, GPU runtime, network upload, screen OCR, or background OCR."
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

        backend_frame = ttk.LabelFrame(parent, text="Backend Selection", padding=10)
        backend_frame.pack(fill="x", pady=(0, 10))
        self.backend_var = tk.StringVar(value=FAKE_BACKEND_LABEL)
        ttk.Label(backend_frame, text="Backend:").pack(side="left")
        ttk.Combobox(
            backend_frame,
            textvariable=self.backend_var,
            values=[FAKE_BACKEND_LABEL],
            state="readonly",
            width=42,
        ).pack(side="left", padx=(8, 12))
        ttk.Label(
            backend_frame,
            text=(
                "Local endpoint mode is test/mock-only in this milestone and is "
                "not exposed from this UI."
            ),
            wraplength=520,
        ).pack(side="left", fill="x", expand=True)

        options = ttk.LabelFrame(parent, text="Output Options", padding=10)
        options.pack(fill="x", pady=(0, 10))
        self.txt_var = tk.BooleanVar(value=True)
        self.md_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="TXT", variable=self.txt_var).pack(side="left")
        ttk.Checkbutton(options, text="Markdown", variable=self.md_var).pack(
            side="left", padx=(10, 0)
        )

        out_frame = ttk.Frame(parent)
        out_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(out_frame, text="Output Folder:").pack(side="left")
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(8, 5))
        self.output_entry.insert(
            0,
            get_setting(
                "dev_document_ocr.output_dir", get_default_save_dir("DocumentOCRDev")
            ),
        )
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(side="left")

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(0, 8))
        self.start_btn = ttk.Button(
            actions, text="Run Dev Document OCR", command=self.execute
        )
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
            selection = self._backend_selection()
        except OcrBackendUnavailableError as exc:
            messagebox.showerror("Error", user_safe_ocr_error_message(exc))
            return

        consent = load_advanced_ocr_consent()
        if consent is None:
            messagebox.showwarning(
                "Consent Required",
                (
                    "The dev Document OCR shell uses the same consent gate as "
                    "future advanced OCR backends. Review and save consent in "
                    "Settings / Recent first."
                ),
            )
            return

        set_setting("dev_document_ocr.output_dir", output_dir)
        remember_inputs(files)
        self.cancel_token.reset()
        self.progress["value"] = 0
        self.status_lbl.config(text="Starting dev Document OCR shell...")
        self.output_actions.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        threading.Thread(
            target=self._run_workflow,
            args=(files, output_dir, formats, selection, consent),
            daemon=True,
        ).start()
        self.parent.after(100, self._poll_queue)

    def _backend_selection(self) -> AdvancedOcrBackendSelection:
        """Return the selected mock-safe backend.

        The UI exposes only the fake backend. Local endpoint workflow coverage
        remains unit-test/mock-only until a later reviewed milestone.
        """

        if self.backend_var.get() == FAKE_BACKEND_LABEL:
            return fake_backend_selection()
        raise OcrBackendUnavailableError(
            "Unsupported advanced OCR backend selection."
        )

    def _selected_formats(self) -> List[str]:
        selected = []
        if self.txt_var.get():
            selected.append("txt")
        if self.md_var.get():
            selected.append("md")
        return selected

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

    def _run_workflow(self, files, output_dir, formats, selection, consent) -> None:
        try:
            result = run_advanced_ocr_workflow(
                files,
                output_dir,
                formats,
                selection=selection,
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
            self.queue.put(
                (
                    "error_message",
                    f"Dev Document OCR shell failed: {user_safe_ocr_error_message(exc)}",
                )
            )

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
                        text=f"Wrote {len(data.outputs)} dev OCR output file(s)."
                    )
                    messagebox.showinfo(
                        "Done",
                        (
                            "Dev Document OCR shell completed with the fake backend. "
                            "No real Unlimited-OCR inference was performed."
                        ),
                    )
                elif msg_type == "cancelled":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Dev Document OCR shell cancelled.")
                    messagebox.showinfo("Cancelled", "Dev Document OCR shell cancelled.")
                elif msg_type == "error":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(
                        text="Dev Document OCR shell completed with errors."
                    )
                    messagebox.showerror("Error", "\n".join(data.failed))
                elif msg_type == "error_message":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Dev Document OCR shell failed.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        if self.cancel_btn["state"] == "normal":
            self.parent.after(100, self._poll_queue)

    def _finish(self, reset_progress: bool = False) -> None:
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.progress["value"] = 0 if reset_progress else 100


FakeAiOcrTestTool = DevDocumentOcrTool
