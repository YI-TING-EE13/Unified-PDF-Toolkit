"""
Merger Tool - Combines multiple PDF files into a single document.

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
from typing import List, Optional, Any, Dict, Tuple

from PIL import Image, ImageTk

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
    icon: str = "[M]"

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.preview_pages: List[Tuple[str, int, int]] = []
        self.preview_img: Optional[ImageTk.PhotoImage] = None
        self.preview_resize_after: Optional[str] = None

    def render(self, parent: ttk.Frame) -> None:
        """
        Renders the Merger UI with ordering controls and merged-output preview.
        """
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, pady=5)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        self.file_list = FileListWidget(
            left_frame,
            label="Files to Merge (Ordered)",
            filetypes=[("PDF Files", "*.pdf")],
            show_ordering=True,
            display_formatter=self._format_pdf_list_item,
            on_change=self._on_files_changed,
        )
        self.file_list.pack(fill="both", expand=True, pady=5)

        compression_frame = ttk.LabelFrame(
            left_frame, text="Post-Merge Compression", padding=10
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

        action_frame = ttk.LabelFrame(left_frame, text="Output", padding=10)
        action_frame.pack(fill="x", pady=10)

        self.output_entry = ttk.Entry(action_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.output_entry.insert(0, self._default_output_path())
        ttk.Button(action_frame, text="Save As...", command=self._browse_output).pack(
            side="right"
        )

        self.merge_btn = ttk.Button(left_frame, text="Merge PDFs", command=self.execute)
        self.merge_btn.pack(fill="x", padx=20, pady=(0, 8))

        self.progress = ttk.Progressbar(left_frame, mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(0, 5))

        self.status_lbl = ttk.Label(left_frame, text="Ready to merge.")
        self.status_lbl.pack(anchor="w")

        self.output_actions = OutputActions(left_frame)
        self.output_actions.pack(anchor="w", pady=(8, 0))

        right_frame = ttk.LabelFrame(paned, text="Merged Preview", padding=10)
        paned.add(right_frame, weight=5)

        nav_frame = ttk.Frame(right_frame)
        nav_frame.pack(fill="x", pady=(0, 5))

        self.preview_page_lbl = ttk.Label(nav_frame, text="Page: -/-")
        self.preview_page_lbl.pack(side="left")

        self.preview_var = tk.IntVar(value=1)
        self.preview_scale = ttk.Scale(
            nav_frame,
            from_=1,
            to=1,
            variable=self.preview_var,
            command=self._on_preview_change,
            state="disabled",
        )
        self.preview_scale.pack(side="right", fill="x", expand=True, padx=10)

        self.preview_container = ttk.Frame(right_frame)
        self.preview_container.pack(fill="both", expand=True)
        self.preview_container.bind("<Configure>", self._on_preview_resize)

        self.preview_lbl = ttk.Label(
            self.preview_container,
            text="Add PDFs to preview merged output",
            anchor="center",
        )
        self.preview_lbl.pack(fill="both", expand=True)
        self.preview_lbl.bind("<MouseWheel>", self._on_mouse_wheel)
        self.preview_lbl.bind("<Button-4>", self._on_mouse_wheel)
        self.preview_lbl.bind("<Button-5>", self._on_mouse_wheel)

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

    @staticmethod
    def _short_file_name(file_path: str, max_length: int = 34) -> str:
        file_name = os.path.basename(file_path)
        if len(file_name) <= max_length:
            return file_name
        return f"{file_name[:15]}...{file_name[-16:]}"

    @staticmethod
    def build_preview_index(files: List[str]) -> List[Tuple[str, int, int]]:
        """
        Maps merged page order to source PDF path, page index, and source size.

        The preview renders directly from source PDFs instead of creating a
        temporary merged file every time the user reorders the list.
        """
        preview_pages: List[Tuple[str, int, int]] = []
        for file_path in files:
            with fitz.open(file_path) as doc:
                if doc.needs_pass:
                    raise ValueError(f"{os.path.basename(file_path)} is encrypted.")
                for page_idx in range(doc.page_count):
                    preview_pages.append((file_path, page_idx, doc.page_count))
        return preview_pages

    def _on_files_changed(self, files: List[str]) -> None:
        if hasattr(self, "preview_lbl") and self.preview_lbl.winfo_exists():
            self._rebuild_preview_index(files)

    def _on_preview_resize(self, event: Any) -> None:
        if not self.preview_pages:
            return
        if self.preview_resize_after:
            self.preview_container.after_cancel(self.preview_resize_after)
        self.preview_resize_after = self.preview_container.after(
            120, self._render_preview_after_resize
        )

    def _render_preview_after_resize(self) -> None:
        self.preview_resize_after = None
        self._update_preview(self.preview_var.get() - 1)

    def _rebuild_preview_index(self, files: List[str]) -> None:
        try:
            self.preview_pages = self.build_preview_index(files)
        except Exception as exc:
            self.preview_pages = []
            self.preview_img = None
            self.preview_scale.config(to=1, state="disabled")
            self.preview_var.set(1)
            self.preview_page_lbl.config(text="Page: -/-")
            self.preview_lbl.config(image="", text=f"Preview unavailable: {exc}")
            return

        total_pages = len(self.preview_pages)
        if total_pages == 0:
            self.preview_img = None
            self.preview_scale.config(to=1, state="disabled")
            self.preview_var.set(1)
            self.preview_page_lbl.config(text="Page: -/-")
            self.preview_lbl.config(image="", text="Add PDFs to preview merged output")
            return

        current_page = max(1, min(total_pages, self.preview_var.get()))
        self.preview_scale.config(to=max(1, total_pages), state="normal")
        self.preview_var.set(current_page)
        self._update_preview(current_page - 1)

    def _on_preview_change(self, value: Any) -> None:
        if not self.preview_pages:
            return
        page_num = int(float(value)) - 1
        self._update_preview(page_num)

    def _on_mouse_wheel(self, event: Any) -> None:
        if not self.preview_pages:
            return
        event_delta = getattr(event, "delta", 0)
        delta = 1 if (getattr(event, "num", None) == 5 or event_delta < 0) else -1
        new_page = max(1, min(len(self.preview_pages), self.preview_var.get() + delta))
        self.preview_var.set(new_page)
        self._update_preview(new_page - 1)

    def _update_preview(self, page_num: int) -> None:
        total_pages = len(self.preview_pages)
        if page_num < 0 or page_num >= total_pages:
            return

        pdf_path, source_page_idx, source_page_count = self.preview_pages[page_num]
        source_name = self._short_file_name(pdf_path)
        self.preview_page_lbl.config(
            text=(
                f"Page: {page_num + 1}/{total_pages} "
                f"({source_name} {source_page_idx + 1}/{source_page_count})"
            )
        )

        try:
            with fitz.open(pdf_path) as doc:
                page = doc.load_page(source_page_idx)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            container_width = self.preview_container.winfo_width()
            container_height = self.preview_container.winfo_height()
            max_width = container_width - 20 if container_width > 80 else 900
            max_height = container_height - 20 if container_height > 80 else 720
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            tk_img = ImageTk.PhotoImage(img)
            self.preview_lbl.config(image=tk_img, text="")
            self.preview_img = tk_img
        except Exception as exc:
            self.preview_img = None
            self.preview_lbl.config(image="", text=f"Preview failed: {exc}")

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
                elif msg_type == "progress":
                    pct, message = data
                    self.progress.stop()
                    self.progress.config(mode="determinate")
                    self.progress["value"] = pct
                    self.status_lbl.config(text=message)
                elif msg_type == "busy":
                    active, message = data
                    if active:
                        self.progress.config(mode="indeterminate")
                        self.progress.start(12)
                    else:
                        self.progress.stop()
                        self.progress.config(mode="determinate")
                    self.status_lbl.config(text=message)
                elif msg_type == "success":
                    output_path = data["output_path"] if isinstance(data, dict) else data
                    detail = data.get("detail", "") if isinstance(data, dict) else ""
                    self.merge_btn.config(state="normal")
                    self.progress.stop()
                    self.progress.config(mode="determinate")
                    self.progress["value"] = 100
                    self.output_actions.set_path(output_path)
                    self.status_lbl.config(text=f"Saved to {output_path}")
                    message = "Merge Complete!"
                    if detail:
                        message += f"\n{detail}"
                    messagebox.showinfo("Success", message)
                elif msg_type == "error":
                    self.merge_btn.config(state="normal")
                    self.progress.stop()
                    self.progress.config(mode="determinate")
                    self.progress["value"] = 0
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
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress["value"] = 0
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
            output_dir = os.path.dirname(output_path) or os.getcwd()
            os.makedirs(output_dir, exist_ok=True)
            if auto_compress:
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf",
                    prefix="pdf_toolkit_merge_",
                    dir=output_dir,
                    delete=False,
                ) as temp_file:
                    temp_path = temp_file.name
                merge_output_path = temp_path

            self.queue.put(("progress", (0, "Merging PDFs...")))
            doc = fitz.open()
            total_files = len(files)
            for idx, pdf_path in enumerate(files, start=1):
                progress_start = ((idx - 1) / total_files) * 85
                self.queue.put(
                    (
                        "progress",
                        (
                            progress_start,
                            f"Merging {idx}/{total_files}: {os.path.basename(pdf_path)}",
                        ),
                    )
                )
                with fitz.open(pdf_path) as src:
                    doc.insert_pdf(src)
                progress_done = (idx / total_files) * 85
                self.queue.put(
                    (
                        "progress",
                        (
                            progress_done,
                            f"Merged {idx}/{total_files}: {os.path.basename(pdf_path)}",
                        ),
                    )
                )
            doc.save(merge_output_path)
            doc.close()

            detail = ""
            if auto_compress:
                self.queue.put(("busy", (True, "Compressing merged PDF...")))
                original_size = get_file_size(temp_path)
                compressor = PDFCompressor(compression_level)
                if not compressor.compress(temp_path, output_path):
                    raise RuntimeError("Merge completed, but post-merge compression failed.")
                self.queue.put(("busy", (False, "Compression complete.")))

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

            self.queue.put(("progress", (100, "Merge complete.")))
            self.queue.put(("success", {"output_path": output_path, "detail": detail}))
        except Exception as e:
            self.queue.put(("error", str(e)))
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
