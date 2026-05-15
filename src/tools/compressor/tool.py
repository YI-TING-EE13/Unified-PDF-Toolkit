"""
Compressor Tool — Batch-compresses PDF and Image files.

Features:
- Unified FileListWidget for file selection.
- Asynchronous processing via background thread.
- Live progress updates using a thread-safe Queue.
- Default save to ~/Documents/PDFToolkit/Saved/Compressed/.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
from pathlib import Path
from typing import List, Optional, Any, Dict

from ...base.tool import BaseTool
from ...core.processor import BatchProcessor
from ...ui.components import FileListWidget, OutputActions
from ...utils.file_ops import get_default_save_dir, format_size
from ...utils.settings import get_setting, set_setting


class CompressorTool(BaseTool):
    """
    GUI Tool for compressing PDF and Image files.

    Features:
    - Multi-file and Folder selection via shared FileListWidget.
    - Asynchronous processing via background thread.
    - Live progress updates using a thread-safe Queue.
    """

    name: str = "Compress PDF/Image"
    icon: str = "📉"

    def __init__(self) -> None:
        """Initialize the Compressor tool state."""
        self.processor = BatchProcessor()
        self.queue: queue.Queue = queue.Queue()

    def render(self, parent: ttk.Frame) -> None:
        """
        Builds the UI Layout.

        Layout sections:
        1. Input Selection (FileListWidget).
        2. Settings (Compression Level).
        3. Output Configuration.
        4. Progress Monitoring.

        Args:
            parent (ttk.Frame): The parent container.
        """
        # --- 1. Input Selection Area (using shared widget) ---
        self.file_list = FileListWidget(
            parent,
            label="Input Selection",
            filetypes=[("All Supported", "*.pdf *.jpg *.jpeg *.png *.txt")],
            show_ordering=False,
        )
        self.file_list.pack(fill="both", expand=True, pady=5)

        # --- 2. Settings & Output ---
        opts_frame = ttk.LabelFrame(parent, text="Settings & Output", padding=10)
        opts_frame.pack(fill="x", pady=5)

        # Compression Level
        ttk.Label(opts_frame, text="Compression Level:").grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        self.level_var = tk.StringVar(value="Medium")
        ttk.Combobox(
            opts_frame,
            textvariable=self.level_var,
            values=["Low", "Medium", "High"],
            state="readonly",
            width=10,
        ).grid(row=0, column=1, sticky="w")

        # Output Directory
        ttk.Label(opts_frame, text="Output Folder:").grid(
            row=0, column=2, sticky="w", padx=(20, 10)
        )
        self.output_entry = ttk.Entry(opts_frame, width=40)
        self.output_entry.grid(row=0, column=3, sticky="ew")
        ttk.Button(opts_frame, text="Browse", command=self._browse_output).grid(
            row=0, column=4, padx=5
        )

        opts_frame.columnconfigure(3, weight=1)
        self.output_entry.insert(
            0, get_setting("compressor.output_dir", get_default_save_dir("Compressed"))
        )

        # Advanced PDF-only options. A value of 0 keeps the preset default.
        advanced_frame = ttk.LabelFrame(parent, text="Advanced PDF Options", padding=10)
        advanced_frame.pack(fill="x", pady=5)

        self.lossless_only_var = tk.BooleanVar(
            value=bool(get_setting("compressor.lossless_only", False))
        )
        ttk.Checkbutton(
            advanced_frame,
            text="Lossless cleanup only",
            variable=self.lossless_only_var,
        ).grid(row=0, column=0, sticky="w", padx=(0, 20))

        self.optimize_images_var = tk.BooleanVar(
            value=bool(get_setting("compressor.optimize_images", True))
        )
        ttk.Checkbutton(
            advanced_frame,
            text="Optimize PDF images",
            variable=self.optimize_images_var,
        ).grid(row=0, column=1, sticky="w", padx=(0, 20))

        ttk.Label(advanced_frame, text="Max image dimension:").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        self.max_dim_var = tk.IntVar(
            value=int(get_setting("compressor.max_image_dimension", 0) or 0)
        )
        ttk.Spinbox(
            advanced_frame,
            from_=0,
            to=8000,
            increment=100,
            textvariable=self.max_dim_var,
            width=10,
        ).grid(row=1, column=1, sticky="w", pady=(8, 0))

        ttk.Label(advanced_frame, text="JPEG quality:").grid(
            row=1, column=2, sticky="w", padx=(20, 10), pady=(8, 0)
        )
        self.jpeg_quality_var = tk.IntVar(
            value=int(get_setting("compressor.jpeg_quality", 0) or 0)
        )
        ttk.Spinbox(
            advanced_frame,
            from_=0,
            to=100,
            increment=5,
            textvariable=self.jpeg_quality_var,
            width=10,
        ).grid(row=1, column=3, sticky="w", pady=(8, 0))

        ttk.Label(
            advanced_frame,
            text="Use 0 to keep the selected preset default.",
            foreground="gray",
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        # --- 3. Action Buttons ---
        self.start_btn = ttk.Button(
            parent, text="Start Compression", command=self.execute
        )
        self.start_btn.pack(pady=10)

        # --- 4. Progress Log ---
        log_frame = ttk.LabelFrame(parent, text="Progress Log", padding=10)
        log_frame.pack(fill="x", expand=False)

        self.progress = ttk.Progressbar(log_frame, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 5))

        self.status_lbl = ttk.Label(log_frame, text="Ready.")
        self.status_lbl.pack(anchor="w")

        self.output_actions = OutputActions(log_frame)
        self.output_actions.pack(anchor="w", pady=(8, 0))

        # Start background polling for queue messages
        self._process_queue()

    def _browse_output(self) -> None:
        """Opens directory dialog for output path."""
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def update_progress(self, current: int, total: int, msg: str) -> None:
        """
        Callback bound to BatchProcessor to receive updates from the worker thread.

        Args:
            current (int): Current items processed.
            total (int): Total items.
            msg (str): Status message.
        """
        self.queue.put(("progress", (current, total, msg)))

    def _process_queue(self) -> None:
        """
        Polls the thread-safe queue for messages and updates the GUI.
        Run periodically via `after()`.
        """
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    curr, total, status = data
                    if total > 0:
                        pct = (curr / total) * 100
                        self.progress["value"] = pct
                    self.status_lbl.config(text=f"[{curr}/{total}] {status}")
                elif msg_type == "done":
                    output_dir, result = data
                    self.start_btn.config(state="normal")
                    self.progress["value"] = 100
                    self.output_actions.set_path(output_dir)
                    summary = (
                        f"Processing complete. Success: {result['success']}, "
                        f"failed: {result['failed']}, skipped: {result['skipped']}, "
                        f"saved: {format_size(result['total_saved_bytes'])}."
                    )
                    self.status_lbl.config(text=summary)
                    messagebox.showinfo("Done", summary)
                elif msg_type == "error":
                    self.start_btn.config(state="normal")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        # Re-schedule poller if the view is still active
        if hasattr(self, "start_btn") and self.start_btn.winfo_exists():
            self.start_btn.after(100, self._process_queue)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Starts the compression process in a background thread.
        """
        input_items = self.file_list.get_files()
        if not input_items:
            messagebox.showwarning("Warning", "No files selected!")
            return

        output_dir = self.output_entry.get()
        if not output_dir:
            output_dir = get_default_save_dir("Compressed")

        level = self.level_var.get()
        compression_options = self._get_compression_options()
        self._save_current_settings(output_dir, compression_options)

        # Lock UI
        self.start_btn.config(state="disabled")
        self.status_lbl.config(text="Scanning files...")
        self.progress["value"] = 0
        self.output_actions.clear()

        # Start Thread
        thread = threading.Thread(
            target=self._run_compression,
            args=(list(input_items), output_dir, level, compression_options),
        )
        thread.start()

    def _get_compression_options(self) -> Dict[str, Any]:
        max_dim = self.max_dim_var.get()
        jpeg_quality = self.jpeg_quality_var.get()
        return {
            "optimize_images": self.optimize_images_var.get(),
            "lossless_only": self.lossless_only_var.get(),
            "max_image_dimension": max_dim if max_dim > 0 else None,
            "jpeg_quality": jpeg_quality if jpeg_quality > 0 else None,
        }

    def _save_current_settings(
        self, output_dir: str, compression_options: Dict[str, Any]
    ) -> None:
        set_setting("compressor.output_dir", output_dir)
        set_setting("compressor.optimize_images", compression_options["optimize_images"])
        set_setting("compressor.lossless_only", compression_options["lossless_only"])
        set_setting(
            "compressor.max_image_dimension",
            compression_options["max_image_dimension"] or 0,
        )
        set_setting("compressor.jpeg_quality", compression_options["jpeg_quality"] or 0)

    def _run_compression(
        self,
        input_paths: List[str],
        output_dir: str,
        level: str,
        compression_options: Dict[str, Any],
    ) -> None:
        """
        Worker thread logic. Expands folders and invokes BatchProcessor.
        """
        try:
            # 1. Expand Folders using glob
            all_files = []
            for path_str in input_paths:
                p = Path(path_str)
                if p.is_dir():
                    # Recursive scan for all files in folder
                    all_files.extend([str(x) for x in p.rglob("*") if x.is_file()])
                else:
                    all_files.append(str(p))

            if not all_files:
                self.queue.put(("error", "No files found in selection."))
                return

            # 2. Process
            result = self.processor.process_files(
                all_files,
                output_dir if output_dir else None,
                level,
                progress_callback=self.update_progress,
                compression_options=compression_options,
            )

            self.queue.put(("done", (output_dir, result)))
        except Exception as e:
            self.queue.put(("error", str(e)))
