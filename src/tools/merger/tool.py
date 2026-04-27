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
from datetime import datetime
from typing import List, Optional, Any, Dict

from ...base.tool import BaseTool
from ...ui.components import FileListWidget
from ...utils.file_ops import get_default_save_dir


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
        )
        self.file_list.pack(fill="both", expand=True, pady=5)

        # 2. Output & Execute
        action_frame = ttk.LabelFrame(parent, text="Output", padding=10)
        action_frame.pack(fill="x", pady=10)

        self.merge_btn = ttk.Button(
            action_frame, text="Merge & Save As...", command=self.execute
        )
        self.merge_btn.pack(fill="x", padx=20)

        self.status_lbl = ttk.Label(parent, text="Ready to merge.")
        self.status_lbl.pack(anchor="w")

        # Start Polling
        self._process_queue()

    def _process_queue(self) -> None:
        """Polls the queue for updates."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    self.status_lbl.config(text=data)
                elif msg_type == "success":
                    self.merge_btn.config(state="normal")
                    self.status_lbl.config(text=f"Saved to {data}")
                    messagebox.showinfo("Success", "Merge Complete!")
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

        # Ask user for save location
        output_path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")]
        )

        # If user cancels, auto-save to default directory
        if not output_path:
            default_dir = get_default_save_dir("Merged")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(default_dir, f"Merged_{timestamp}.pdf")

        self.status_lbl.config(text="Merging...")
        self.merge_btn.config(state="disabled")

        # Run in thread
        threading.Thread(
            target=self._run_merge, args=(files, output_path)
        ).start()

    def _run_merge(self, files: List[str], output_path: str) -> None:
        """Worker thread for merging."""
        try:
            doc = fitz.open()
            for pdf_path in files:
                with fitz.open(pdf_path) as src:
                    doc.insert_pdf(src)
            doc.save(output_path)
            doc.close()

            # Safe Update
            self.queue.put(("success", output_path))
        except Exception as e:
            self.queue.put(("error", str(e)))
