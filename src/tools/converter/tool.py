"""
Converter Tool - Batch-converts PDF pages to images (PNG/JPG/JPEG).

Features:
- Unified FileListWidget for multi-PDF batch conversion.
- Customizable DPI (Resolution).
- Throttled UI updates for performance.
- Default save to ~/Documents/PDFToolkit/Saved/Images/.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import threading
import os
import queue
import time
from typing import List, Optional, Dict, Any

from ...base.tool import BaseTool
from ...ui.components import FileListWidget, OutputActions
from ...utils.file_ops import get_default_save_dir
from ...utils.settings import get_setting, set_setting


class ConverterTool(BaseTool):
    """
    GUI Tool for converting PDF pages to Images (PNG/JPG/JPEG).

    Features:
    - Batch conversion of multiple PDFs.
    - Customizable DPI (Resolution).
    - Throttled UI updates for performance.
    """

    name: str = "PDF to Image"
    icon: str = "[IMG]"

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()

    def render(self, parent: ttk.Frame) -> None:
        """
        Renders the Converter UI.

        Layout:
        1. FileListWidget for multi-PDF selection.
        2. Image Settings (DPI, Format).
        3. Output Folder selection.
        4. Progress Monitoring.
        """
        # 1. File List (batch support)
        self.file_list = FileListWidget(
            parent,
            label="Source PDFs",
            filetypes=[("PDF Files", "*.pdf")],
            show_ordering=False,
        )
        self.file_list.pack(fill="both", expand=True, pady=5)

        # 2. Settings (DPI, Format)
        opts_frame = ttk.LabelFrame(parent, text="Image Settings", padding=10)
        opts_frame.pack(fill="x", pady=5)

        ttk.Label(opts_frame, text="DPI (Resolution):").pack(side="left")
        self.dpi_var = tk.IntVar(value=int(get_setting("converter.dpi", 150)))
        ttk.Spinbox(
            opts_frame, from_=72, to=600, textvariable=self.dpi_var, width=10
        ).pack(side="left", padx=10)

        ttk.Label(opts_frame, text="Format:").pack(side="left", padx=(20, 0))
        self.fmt_var = tk.StringVar(value=get_setting("converter.format", "png"))
        ttk.Combobox(
            opts_frame,
            textvariable=self.fmt_var,
            values=["png", "jpg", "jpeg"],
            state="readonly",
            width=10,
        ).pack(side="left", padx=10)

        # 3. Output
        out_frame = ttk.LabelFrame(parent, text="Output Folder", padding=10)
        out_frame.pack(fill="x", pady=5)
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.output_entry.insert(
            0, get_setting("converter.output_dir", get_default_save_dir("Images"))
        )

        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(
            side="right"
        )

        # 4. Action
        self.btn = ttk.Button(
            parent, text="Convert to Images", command=self.execute
        )
        self.btn.pack(pady=20)

        self.status = ttk.Progressbar(parent, mode="determinate")
        self.status.pack(fill="x", padx=10)
        self.status_lbl = ttk.Label(parent, text="Ready.")
        self.status_lbl.pack()

        self.output_actions = OutputActions(parent)
        self.output_actions.pack(anchor="w", pady=(8, 0))

        self._process_queue()

    def _process_queue(self) -> None:
        """
        Polls queue for progress updates.
        Throttle: Only processes small batch at a time to prevent blocking main thread.
        """
        BATCH_SIZE = 10
        processed = 0
        try:
            while processed < BATCH_SIZE:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    pct, msg = data
                    self.status["value"] = pct
                    self.status_lbl.config(text=msg)
                elif msg_type == "success":
                    message = data["message"] if isinstance(data, dict) else data
                    output_dir = data.get("output_dir", "") if isinstance(data, dict) else ""
                    self.status_lbl.config(text=message)
                    self.btn.config(state="normal")
                    self.output_actions.set_path(output_dir)
                    self.status["value"] = 100
                    messagebox.showinfo("Success", message)
                elif msg_type == "error":
                    self.status_lbl.config(text="Error occurred.")
                    self.btn.config(state="normal")
                    self.status["value"] = 0
                    messagebox.showerror("Error", data)
                processed += 1
        except queue.Empty:
            pass

        if hasattr(self, "status_lbl") and self.status_lbl.winfo_exists():
            self.status_lbl.after(50, self._process_queue)

    def _browse_output(self) -> None:
        """Opens directory dialog for output path selection."""
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Validates input and starts conversion thread."""
        files = self.file_list.get_files()
        if not files:
            messagebox.showwarning("Warning", "No files selected!")
            return

        out_dir = self.output_entry.get()
        if not out_dir:
            messagebox.showwarning("Warning", "Please choose an output folder.")
            return

        dpi = self.dpi_var.get()
        fmt = self.fmt_var.get()
        set_setting("converter.output_dir", out_dir)
        set_setting("converter.dpi", dpi)
        set_setting("converter.format", fmt)

        self.status_lbl.config(text="Converting...")
        self.btn.config(state="disabled")
        self.status["value"] = 0
        self.output_actions.clear()
        threading.Thread(
            target=self._run_convert, args=(files, out_dir, dpi, fmt)
        ).start()

    def _run_convert(
        self, files: List[str], out_dir: str, dpi: int, fmt: str
    ) -> None:
        """
        Worker thread for batch conversion.
        Includes simple throttling logic to avoid flooding the GUI queue.
        """
        try:
            os.makedirs(out_dir, exist_ok=True)

            # Count total pages across all files for accurate progress
            total_pages = 0
            for f in files:
                try:
                    doc = fitz.open(f)
                    total_pages += len(doc)
                    doc.close()
                except Exception:
                    pass

            if total_pages == 0:
                self.queue.put(("error", "No valid PDF pages found."))
                return

            current_page = 0
            last_update = 0.0

            for pdf_path in files:
                try:
                    doc = fitz.open(pdf_path)
                    base_name = os.path.splitext(os.path.basename(pdf_path))[0]

                    for i, page in enumerate(doc):
                        pix = page.get_pixmap(dpi=dpi)
                        out_name = f"{base_name}_page_{i + 1}.{fmt}"
                        out_path = os.path.join(out_dir, out_name)
                        pix.save(out_path)

                        current_page += 1

                        # Rate Limiting: Only update GUI every 0.1s or on last page
                        now = time.time()
                        if now - last_update > 0.1 or current_page == total_pages:
                            pct = (current_page / total_pages) * 100
                            self.queue.put(
                                (
                                    "progress",
                                    (pct, f"Saved page {current_page}/{total_pages}"),
                                )
                            )
                            last_update = now

                    doc.close()
                except Exception as e:
                    self.queue.put(
                        (
                            "error",
                            f"Error processing {os.path.basename(pdf_path)}: {e}",
                        )
                    )
                    return

            self.queue.put(
                (
                    "success",
                    {
                        "message": f"Converted {total_pages} pages to {out_dir}.",
                        "output_dir": out_dir,
                    },
                )
            )

        except Exception as e:
            self.queue.put(("error", str(e)))
