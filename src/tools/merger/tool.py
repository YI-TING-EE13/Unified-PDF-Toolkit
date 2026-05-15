"""
Merger Tool — Combines multiple PDF files into a single document.

Features:
- Unified FileListWidget for file selection and ordering.
- Recursive folder import.
- Default save to ~/Documents/PDFToolkit/Saved/Merged/ when no path is chosen.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import threading
import os
import queue
import tempfile
from datetime import datetime
from typing import List, Optional, Any, Dict

from ...base.tool import BaseTool
from ...handlers.pdf import PDFCompressor
from ...ui.components import FileListWidget, OutputActions
from ...utils.file_ops import get_default_save_dir, get_file_size, format_size
from ...utils.settings import get_setting, set_setting


class MergerTool(BaseTool):
    """
    GUI Tool for merging multiple PDF files.

    Features:
    - List-based file ordering via shared FileListWidget.
    - Drag-and-remove functionality.
    - Recursive folder adding.
    """

    name: str = "Merge PDFs"
    icon: str = "📑"

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()

    def render(self, parent: ttk.Frame) -> None:
        """
        Renders the Merger UI: A robust file list with ordering controls.
        """
        # 1. File List Area (using shared widget)
        self.file_list = FileListWidget(
            parent,
            label="Files to Merge (Ordered)",
            filetypes=[("PDF Files", "*.pdf")],
            show_ordering=True,
            display_formatter=self._format_pdf_list_item,
        )
        self.file_list.pack(fill="both", expand=True, pady=5)

        # 2. Optional post-merge compression
        compression_frame = ttk.LabelFrame(
            parent, text="Post-Merge Compression", padding=10
        )
        compression_frame.pack(fill="x", pady=5)

        self.auto_compress_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            compression_frame,
            text="Compress merged PDF automatically",
            variable=self.auto_compress_var,
            command=self._sync_compression_state,
        ).grid(row=0, column=0, sticky="w", padx=(0, 20))

        ttk.Label(compression_frame, text="Compression Level:").grid(
            row=0, column=1, sticky="w", padx=(0, 10)
        )
        self.compression_level_var = tk.StringVar(value="Medium")
        self.compression_level_combo = ttk.Combobox(
            compression_frame,
            textvariable=self.compression_level_var,
            values=["Low", "Medium", "High"],
            state="disabled",
            width=10,
        )
        self.compression_level_combo.grid(row=0, column=2, sticky="w")
        compression_frame.columnconfigure(3, weight=1)

        # 3. Output & Execute
        action_frame = ttk.LabelFrame(parent, text="Output", padding=10)
        action_frame.pack(fill="x", pady=10)

        self.output_entry = ttk.Entry(action_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.output_entry.insert(0, self._default_output_path())
        ttk.Button(action_frame, text="Save As...", command=self._browse_output).pack(
            side="right"
        )

        self.merge_btn = ttk.Button(parent, text="Merge PDFs", command=self.execute)
        self.merge_btn.pack(fill="x", padx=20, pady=(0, 8))

        self.status_lbl = ttk.Label(parent, text="Ready to merge.")
        self.status_lbl.pack(anchor="w")

        self.output_actions = OutputActions(parent)
        self.output_actions.pack(anchor="w", pady=(8, 0))

        # Start Polling
        self._process_queue()

    def _sync_compression_state(self) -> None:
        """Enables compression parameters only when post-merge compression is on."""
        state = "readonly" if self.auto_compress_var.get() else "disabled"
        self.compression_level_combo.config(state=state)

    def _format_pdf_list_item(self, file_path: str) -> str:
        """Shows file name and page count while preserving full paths internally."""
        try:
            with fitz.open(file_path) as doc:
                return f"{os.path.basename(file_path)} - {doc.page_count} pages"
        except Exception:
            return os.path.basename(file_path)

    def _default_output_path(self) -> str:
        default_dir = get_setting("merger.output_dir", get_default_save_dir("Merged"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(default_dir, f"Merged_{timestamp}.pdf")

    def _browse_output(self) -> None:
        current_path = self.output_entry.get()
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=os.path.basename(current_path or "Merged.pdf"),
            initialdir=os.path.dirname(current_path or get_default_save_dir("Merged")),
        )
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def _process_queue(self) -> None:
        """Polls the queue for updates."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    self.status_lbl.config(text=data)
                elif msg_type == "success":
                    output_path = data["output_path"] if isinstance(data, dict) else data
                    detail = data.get("detail", "") if isinstance(data, dict) else ""
                    self.merge_btn.config(state="normal")
                    self.output_actions.set_path(output_path)
                    self.status_lbl.config(text=f"Saved to {output_path}")
                    message = "Merge Complete!"
                    if detail:
                        message += f"\n{detail}"
                    messagebox.showinfo("Success", message)
                elif msg_type == "error":
                    self.merge_btn.config(state="normal")
                    self.status_lbl.config(text="Error occurred.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        if hasattr(self, "status_lbl") and self.status_lbl.winfo_exists():
            self.status_lbl.after(100, self._process_queue)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Starts the merge operation."""
        files = self.file_list.get_files()
        if not files:
            messagebox.showwarning("Warning", "No files selected!")
            return

        output_path = self.output_entry.get()
        if not output_path:
            messagebox.showwarning("Warning", "Please choose an output PDF path.")
            return

        auto_compress = self.auto_compress_var.get()
        compression_level = self.compression_level_var.get()
        set_setting("merger.output_dir", os.path.dirname(output_path) or os.getcwd())

        self.status_lbl.config(text="Merging...")
        self.merge_btn.config(state="disabled")
        self.output_actions.clear()

        # Run in thread
        threading.Thread(
            target=self._run_merge,
            args=(files, output_path, auto_compress, compression_level),
        ).start()

    def _run_merge(
        self,
        files: List[str],
        output_path: str,
        auto_compress: bool,
        compression_level: str,
    ) -> None:
        """Worker thread for merging."""
        temp_path = ""
        try:
            merge_output_path = output_path
            if auto_compress:
                output_dir = os.path.dirname(output_path) or os.getcwd()
                os.makedirs(output_dir, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf",
                    prefix="pdf_toolkit_merge_",
                    dir=output_dir,
                    delete=False,
                ) as temp_file:
                    temp_path = temp_file.name
                merge_output_path = temp_path

            self.queue.put(("status", "Merging PDFs..."))
            doc = fitz.open()
            for pdf_path in files:
                with fitz.open(pdf_path) as src:
                    doc.insert_pdf(src)
            doc.save(merge_output_path)
            doc.close()

            detail = ""
            if auto_compress:
                self.queue.put(("status", "Compressing merged PDF..."))
                original_size = get_file_size(temp_path)
                compressor = PDFCompressor(compression_level)
                if not compressor.compress(temp_path, output_path):
                    raise RuntimeError("Merge completed, but post-merge compression failed.")

                compressed_size = get_file_size(output_path)
                saved_bytes = original_size - compressed_size
                size_detail = (
                    f"Saved {format_size(saved_bytes)}"
                    if saved_bytes >= 0
                    else f"Size increased by {format_size(abs(saved_bytes))}"
                )
                detail = (
                    f"Compressed with {compression_level} level. "
                    f"{size_detail}."
                )

            self.queue.put(("success", {"output_path": output_path, "detail": detail}))
        except Exception as e:
            self.queue.put(("error", str(e)))
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
