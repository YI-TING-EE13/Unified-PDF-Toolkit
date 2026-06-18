"""Cross-tool batch queue for repeatable multi-step processing."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import fitz
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...base.tool import BaseTool
from ...core.processor import BatchProcessor
from ...ui.components import FileListWidget, OutputActions
from ...utils.errors import friendly_error_message
from ...utils.file_ops import get_default_save_dir, resolve_output_path
from ...utils.settings import get_setting, set_setting
from ...utils.workflow import (
    CancellationToken,
    WorkflowReport,
    get_conflict_policy,
    remember_inputs,
)
from ..pdf2word.tool import PDFToWordTool


@dataclass
class BatchJob:
    source: str
    operation: str
    options: Dict[str, Any] = field(default_factory=dict)


class BatchQueueTool(BaseTool):
    """GUI tool for queuing mixed operations and running them sequentially."""

    name: str = "Batch Queue"
    icon: str = "[Q]"

    OPERATIONS = (
        "Compress PDF/Image",
        "PDF to Images",
        "PDF to Word - Text Only",
        "PDF to Word - Page Images",
        "PDF to Word - OCR Text",
    )

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.cancel_token = CancellationToken()
        self.jobs: List[BatchJob] = []

    def render(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="both", expand=True)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=2)
        top.rowconfigure(0, weight=1)

        left = ttk.Frame(top)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.file_list = FileListWidget(
            left,
            label="Files to add",
            filetypes=[("Supported files", "*.pdf *.jpg *.jpeg *.png *.txt")],
            show_ordering=False,
        )
        self.file_list.pack(fill="both", expand=True)

        options = ttk.LabelFrame(left, text="Queue Options", padding=10)
        options.pack(fill="x", pady=(8, 0))

        ttk.Label(options, text="Operation:").grid(row=0, column=0, sticky="w")
        self.operation_var = tk.StringVar(value=get_setting("batch.operation", self.OPERATIONS[0]))
        ttk.Combobox(
            options,
            textvariable=self.operation_var,
            values=self.OPERATIONS,
            state="readonly",
            width=24,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(options, text="Page range:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.range_var = tk.StringVar(value=get_setting("batch.page_range", ""))
        ttk.Entry(options, textvariable=self.range_var).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0)
        )

        ttk.Label(options, text="OCR language:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.ocr_lang_var = tk.StringVar(value=get_setting("batch.ocr_lang", "eng"))
        ttk.Combobox(
            options,
            textvariable=self.ocr_lang_var,
            values=["eng", "chi_tra", "chi_sim", "eng+chi_tra", "eng+chi_sim"],
            width=14,
        ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        ttk.Label(options, text="DPI:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.dpi_var = tk.IntVar(value=int(get_setting("batch.dpi", 150)))
        ttk.Spinbox(options, from_=72, to=600, textvariable=self.dpi_var, width=8).grid(
            row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        ttk.Label(options, text="OCR cleanup:").grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.ocr_preprocess_var = tk.StringVar(value=get_setting("batch.ocr_preprocess", "Grayscale"))
        ttk.Combobox(
            options,
            textvariable=self.ocr_preprocess_var,
            values=PDFToWordTool.OCR_PREPROCESS_OPTIONS,
            state="readonly",
            width=14,
        ).grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        options.columnconfigure(1, weight=1)

        ttk.Button(options, text="Add Files to Queue", command=self._add_jobs).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        right = ttk.Frame(top)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            right, columns=("operation", "source", "status"), show="headings", height=12
        )
        self.tree.heading("operation", text="Operation")
        self.tree.heading("source", text="Source")
        self.tree.heading("status", text="Status")
        self.tree.column("operation", width=190, stretch=False)
        self.tree.column("source", width=520)
        self.tree.column("status", width=100, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")

        queue_buttons = ttk.Frame(right)
        queue_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(queue_buttons, text="Remove Selected", command=self._remove_selected).pack(side="left")
        ttk.Button(queue_buttons, text="Clear Queue", command=self._clear_jobs).pack(side="left", padx=8)

        out_frame = ttk.LabelFrame(parent, text="Output Folder", padding=10)
        out_frame.pack(fill="x", pady=(8, 0))
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.output_entry.insert(0, get_setting("batch.output_dir", get_default_save_dir("Batch")))
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(side="right")

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(10, 0))
        self.start_btn = ttk.Button(actions, text="Run Queue", command=self.execute)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(actions, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(actions, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)
        self.status_lbl = ttk.Label(parent, text="Ready.")
        self.status_lbl.pack(anchor="w", pady=(6, 0))
        self.output_actions = OutputActions(parent)
        self.output_actions.pack(anchor="w", pady=(8, 0))
        self._process_queue()

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def _add_jobs(self) -> None:
        files = self.file_list.get_files()
        if not files:
            messagebox.showwarning("Warning", "No files selected!")
            return
        operation = self.operation_var.get()
        options = self._current_options()
        for source in files:
            job = BatchJob(source=source, operation=operation, options=dict(options))
            self.jobs.append(job)
            self.tree.insert("", tk.END, values=(job.operation, job.source, "Queued"))
        self.status_lbl.config(text=f"Queued {len(self.jobs)} jobs.")

    def _current_options(self) -> Dict[str, Any]:
        return {
            "page_range": self.range_var.get().strip(),
            "ocr_lang": self.ocr_lang_var.get().strip() or "eng",
            "dpi": max(72, min(600, int(self.dpi_var.get()))),
            "ocr_dpi": max(100, min(600, int(self.dpi_var.get()))),
            "format": "png",
            "ocr_preprocess": self.ocr_preprocess_var.get(),
            "compression_level": "Medium",
        }

    def _remove_selected(self) -> None:
        selected = list(self.tree.selection())
        if not selected:
            return
        indexes = sorted((self.tree.index(item) for item in selected), reverse=True)
        for index in indexes:
            del self.jobs[index]
        for item in selected:
            self.tree.delete(item)

    def _clear_jobs(self) -> None:
        self.jobs.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.status_lbl.config(text="Queue cleared.")

    def _cancel(self) -> None:
        self.cancel_token.cancel()
        self.status_lbl.config(text="Cancelling after current job...")

    def _process_queue(self) -> None:
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    index, total, message = data
                    self.progress["value"] = (index / total) * 100 if total else 0
                    self.status_lbl.config(text=message)
                    children = self.tree.get_children()
                    if 0 < index <= len(children):
                        values = list(self.tree.item(children[index - 1], "values"))
                        values[2] = "Done"
                        self.tree.item(children[index - 1], values=values)
                elif msg_type == "done":
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.progress["value"] = 100
                    self.output_actions.set_path(data["output_dir"])
                    message = data["message"]
                    if data.get("report_path"):
                        message += f"\nReport: {data['report_path']}"
                    self.status_lbl.config(text=data["message"])
                    messagebox.showinfo("Done", message)
                elif msg_type == "cancelled":
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.status_lbl.config(text=data["message"])
                    messagebox.showinfo("Cancelled", data["message"])
                elif msg_type == "error":
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.status_lbl.config(text="Error occurred.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        if hasattr(self, "start_btn") and self.start_btn.winfo_exists():
            self.start_btn.after(100, self._process_queue)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        if not self.jobs:
            messagebox.showwarning("Warning", "Queue is empty.")
            return
        output_dir = self.output_entry.get() or get_default_save_dir("Batch")
        set_setting("batch.output_dir", output_dir)
        set_setting("batch.operation", self.operation_var.get())
        set_setting("batch.page_range", self.range_var.get().strip())
        set_setting("batch.ocr_lang", self.ocr_lang_var.get().strip() or "eng")
        set_setting("batch.dpi", int(self.dpi_var.get()))
        set_setting("batch.ocr_preprocess", self.ocr_preprocess_var.get())
        remember_inputs([job.source for job in self.jobs])
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0
        self.output_actions.clear()
        self.cancel_token.reset()
        threading.Thread(
            target=self._run_jobs_thread,
            args=(list(self.jobs), output_dir),
        ).start()

    def _run_jobs_thread(self, jobs: List[BatchJob], output_dir: str) -> None:
        try:
            result = self.run_jobs(
                jobs,
                output_dir,
                cancellation_check=self.cancel_token.is_cancelled,
                progress_callback=lambda index, total, message: self.queue.put(
                    ("progress", (index, total, message))
                ),
            )
            msg_type = "cancelled" if result["cancelled"] else "done"
            self.queue.put(
                (
                    msg_type,
                    {
                        "message": (
                            f"Queue complete. Success: {result['success']}, "
                            f"failed: {result['failed']}, skipped: {result['skipped']}."
                        ),
                        "output_dir": output_dir,
                        "report_path": result["report_path"],
                    },
                )
            )
        except Exception as exc:
            self.queue.put(("error", friendly_error_message(exc, "Batch queue failed")))

    @classmethod
    def run_jobs(
        cls,
        jobs: List[BatchJob],
        output_dir: str,
        cancellation_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        report = WorkflowReport(
            "Batch Queue",
            output_dir,
            options={"conflict_policy": get_conflict_policy(), "jobs": len(jobs)},
        )
        result = {"success": 0, "failed": 0, "skipped": 0, "cancelled": False}
        processor = BatchProcessor()

        for index, job in enumerate(jobs, start=1):
            if cancellation_check and cancellation_check():
                result["cancelled"] = True
                report.add(job.source, status="cancelled", message="Cancelled before job.")
                break
            if progress_callback:
                progress_callback(index - 1, len(jobs), f"Running {index}/{len(jobs)}: {job.operation}")
            try:
                outputs = cls._run_single_job(job, output_dir, processor)
                if not outputs:
                    result["skipped"] += 1
                    report.add(job.source, status="skipped", message="No output generated.")
                else:
                    result["success"] += 1
                    report.add(job.source, "; ".join(outputs), message=job.operation)
            except Exception as exc:
                result["failed"] += 1
                report.add(job.source, status="failed", message=friendly_error_message(exc))
            if progress_callback:
                progress_callback(index, len(jobs), f"Finished {index}/{len(jobs)}")

        result["report_path"] = report.write()
        return result

    @classmethod
    def _run_single_job(
        cls, job: BatchJob, output_dir: str, processor: BatchProcessor
    ) -> List[str]:
        operation = job.operation
        if operation == "Compress PDF/Image":
            result = processor.process_files(
                [job.source],
                output_dir,
                job.options.get("compression_level", "Medium"),
                compression_options={
                    "optimize_images": True,
                    "lossless_only": False,
                    "max_image_dimension": None,
                    "jpeg_quality": None,
                },
                conflict_policy=get_conflict_policy(),
            )
            outputs = [
                record.get("output", "")
                for record in result.get("records", [])
                if record.get("status") == "success" and record.get("output")
            ]
            if result.get("failed"):
                raise RuntimeError("; ".join(result.get("errors", [])) or "Compression failed.")
            return outputs

        if operation == "PDF to Images":
            return cls._convert_pdf_to_images(
                job.source,
                output_dir,
                int(job.options.get("dpi", 150)),
                str(job.options.get("format", "png")),
                str(job.options.get("page_range", "")),
            )

        if operation.startswith("PDF to Word"):
            if operation.endswith("Text Only"):
                mode = "Text Only"
            elif operation.endswith("Page Images"):
                mode = "Page Images"
            else:
                mode = "OCR Text"
            output_path = resolve_output_path(
                str(Path(output_dir) / f"{Path(job.source).stem}.docx"),
                get_conflict_policy(),
            )
            if output_path is None:
                return []
            PDFToWordTool.convert_pdf_to_docx(
                job.source,
                output_path,
                range_text=str(job.options.get("page_range", "")),
                mode=mode,
                ocr_lang=str(job.options.get("ocr_lang", "eng")),
                ocr_dpi=int(job.options.get("ocr_dpi", 200)),
                ocr_preprocess=str(job.options.get("ocr_preprocess", "Grayscale")),
            )
            return [output_path]

        raise ValueError(f"Unsupported batch operation: {operation}")

    @staticmethod
    def _convert_pdf_to_images(
        input_path: str, output_dir: str, dpi: int, fmt: str, range_text: str = ""
    ) -> List[str]:
        page_indices = PDFToWordTool.parse_page_range(range_text, input_path)
        outputs: List[str] = []
        with fitz.open(input_path) as doc:
            selected = page_indices if page_indices is not None else list(range(doc.page_count))
            for page_index in selected:
                pix = doc[page_index].get_pixmap(dpi=dpi)
                requested = Path(output_dir) / f"{Path(input_path).stem}_page_{page_index + 1}.{fmt}"
                output_path = resolve_output_path(str(requested), get_conflict_policy())
                if output_path is None:
                    continue
                pix.save(output_path)
                outputs.append(output_path)
        return outputs
