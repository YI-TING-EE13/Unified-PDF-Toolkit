"""Developer-only fake AI OCR test workflow.

This tool intentionally uses only the fake Unlimited-OCR backend. It does not
download models, call local endpoint servers, import AI runtimes, or perform
real OCR inference.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from ...base.tool import BaseTool
from ...ocr import OcrConsentRequiredError
from ...ocr.consent import load_advanced_ocr_consent
from ...ocr.workflow import (
    AdvancedOcrOutput as FakeAiOcrOutput,
    AdvancedOcrWorkflowResult as FakeAiOcrWorkflowResult,
    fake_backend_selection,
    run_advanced_ocr_workflow,
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


class FakeAiOcrTestTool(BaseTool):
    """Hidden developer tool for testing future advanced OCR UI flows."""

    name: str = "[Dev] Fake AI OCR Test"
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
                "This workflow uses only the deterministic fake Unlimited-OCR "
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

        options = ttk.LabelFrame(parent, text="Fake Output Options", padding=10)
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
            0, get_setting("ai_ocr_test.output_dir", get_default_save_dir("FakeAIOCR"))
        )
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(side="left")

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(0, 8))
        self.start_btn = ttk.Button(
            actions, text="Run Fake AI OCR Test", command=self.execute
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

        consent = load_advanced_ocr_consent()
        if consent is None:
            messagebox.showwarning(
                "Consent Required",
                (
                    "Fake AI OCR test wiring uses the same consent gate as future "
                    "advanced OCR backends. Review and save consent in Settings / Recent first."
                ),
            )
            return

        set_setting("ai_ocr_test.output_dir", output_dir)
        remember_inputs(files)
        self.cancel_token.reset()
        self.progress["value"] = 0
        self.status_lbl.config(text="Starting fake AI OCR test...")
        self.output_actions.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        threading.Thread(
            target=self._run_workflow,
            args=(files, output_dir, formats, consent),
            daemon=True,
        ).start()
        self.parent.after(100, self._poll_queue)

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

    def _run_workflow(self, files, output_dir, formats, consent) -> None:
        try:
            result = run_fake_ai_ocr_workflow(
                files,
                output_dir,
                formats,
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
            self.queue.put(("error_message", str(exc)))
        except Exception as exc:
            self.queue.put(("error_message", f"Fake AI OCR test failed: {exc}"))

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
                        text=f"Wrote {len(data.outputs)} fake output file(s)."
                    )
                    messagebox.showinfo(
                        "Done",
                        (
                            "Fake AI OCR test completed. No real Unlimited-OCR "
                            "inference was performed."
                        ),
                    )
                elif msg_type == "cancelled":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Fake AI OCR test cancelled.")
                    messagebox.showinfo("Cancelled", "Fake AI OCR test cancelled.")
                elif msg_type == "error":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Fake AI OCR test completed with errors.")
                    messagebox.showerror("Error", "\n".join(data.failed))
                elif msg_type == "error_message":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Fake AI OCR test failed.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        if self.cancel_btn["state"] == "normal":
            self.parent.after(100, self._poll_queue)

    def _finish(self, reset_progress: bool = False) -> None:
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.progress["value"] = 0 if reset_progress else 100
