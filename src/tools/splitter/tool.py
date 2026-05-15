"""
Splitter Tool - Splits PDF files by page range.

Features:
- Unified FileListWidget as a file queue (Option B).
- Click a file in the list to load its preview.
- Interactive PreviewPane (thumbnails of pages).
- Slider interaction to select start/end pages.
- Default save to ~/Documents/PDFToolkit/Saved/Split/.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import threading
import os
import queue
from PIL import Image, ImageTk
from typing import List, Tuple, Optional, Any, Dict

from ...base.tool import BaseTool
from ...ui.components import FileListWidget, OutputActions
from ...utils.file_ops import get_default_save_dir
from ...utils.settings import get_setting, set_setting


class SplitterTool(BaseTool):
    """
    GUI Tool for splitting PDF files.

    Uses Option B behavior: the file list is a queue, clicking a file
    loads it into the preview pane, and the Split button only processes
    the currently previewed file.
    """

    name: str = "Split PDF"
    icon: str = "[S]"

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.doc: Optional[fitz.Document] = None
        self.current_pdf_path: Optional[str] = None
        self.total_pages: int = 0
        self.preview_img: Optional[ImageTk.PhotoImage] = None  # Keep reference to prevent GC

    def render(self, parent: ttk.Frame) -> None:
        """
        Builds the UI with a PanedWindow (Split View).
        Left: Controls (File list, Range Sliders).
        Right: Preview (Image Canvas).
        """
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, pady=5)

        # --- Left Pane: Controls ---
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        # 1. File List (queue of PDFs)
        self.file_list = FileListWidget(
            left_frame,
            label="PDF Queue (click to preview)",
            filetypes=[("PDF Files", "*.pdf")],
            show_ordering=False,
        )
        self.file_list.pack(fill="both", expand=True, pady=5)

        # Bind selection event to load preview
        self.file_list.bind_select(self._on_file_select)

        # 2. Range Slider Area
        range_frame = ttk.LabelFrame(left_frame, text="Select Range", padding=10)
        range_frame.pack(fill="x", pady=5)

        # Sliders
        self.val_min_var = tk.IntVar(value=1)
        self.val_max_var = tk.IntVar(value=1)

        # Start Slider
        ttk.Label(range_frame, text="Start Page:").pack(anchor="w")
        self.scale_min = ttk.Scale(
            range_frame,
            from_=1,
            to=1,
            variable=self.val_min_var,
            command=lambda v: self._on_range_change("min"),
        )
        self.scale_min.pack(fill="x", pady=(0, 10))

        # End Slider
        ttk.Label(range_frame, text="End Page:").pack(anchor="w")
        self.scale_max = ttk.Scale(
            range_frame,
            from_=1,
            to=1,
            variable=self.val_max_var,
            command=lambda v: self._on_range_change("max"),
        )
        self.scale_max.pack(fill="x", pady=(0, 10))

        # Manual Text Entry
        ttk.Label(range_frame, text="Range Text (e.g., 1-5):").pack(anchor="w")
        self.range_entry = ttk.Entry(range_frame)
        self.range_entry.pack(fill="x")

        # 3. Output
        out_frame = ttk.LabelFrame(left_frame, text="Output", padding=10)
        out_frame.pack(fill="x", pady=5)
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True)
        self.output_entry.insert(
            0, get_setting("splitter.output_dir", get_default_save_dir("Split"))
        )
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(
            side="right"
        )

        # 4. Action
        self.btn = ttk.Button(
            left_frame, text="Split PDF", command=self.execute, state="disabled"
        )
        self.btn.pack(pady=20, fill="x")

        self.progress = ttk.Progressbar(left_frame, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 5))

        self.status_lbl = ttk.Label(left_frame, text="Add PDFs and click one to preview.")
        self.status_lbl.pack()

        self.output_actions = OutputActions(left_frame)
        self.output_actions.pack(anchor="w", pady=(8, 0))

        # --- Right Pane: Preview ---
        right_frame = ttk.LabelFrame(paned, text="Page Preview", padding=10)
        paned.add(right_frame, weight=3)  # Give more space to preview

        # Nav Controls (Above Image)
        nav_frame = ttk.Frame(right_frame)
        nav_frame.pack(fill="x", pady=(0, 5))

        self.page_lbl = ttk.Label(nav_frame, text="Page: -/-")
        self.page_lbl.pack(side="left")

        self.preview_var = tk.IntVar(value=1)
        self.preview_scale = ttk.Scale(
            nav_frame,
            from_=1,
            to=1,
            variable=self.preview_var,
            command=self._on_preview_change,
        )
        self.preview_scale.pack(side="right", fill="x", expand=True, padx=10)

        # Image Host
        self.preview_container = ttk.Frame(right_frame)
        self.preview_container.pack(fill="both", expand=True)

        self.preview_lbl = ttk.Label(
            self.preview_container, text="No PDF loaded", anchor="center"
        )
        self.preview_lbl.pack(fill="both", expand=True)

        # Bindings for Mouse Navigation
        self.preview_lbl.bind("<MouseWheel>", self._on_mouse_wheel)
        self.preview_lbl.bind("<Button-4>", self._on_mouse_wheel)  # Linux scroll up
        self.preview_lbl.bind("<Button-5>", self._on_mouse_wheel)  # Linux scroll down

        # Drag Logic State
        self.last_y = 0
        self.preview_lbl.bind("<Button-1>", self._on_drag_start)
        self.preview_lbl.bind("<B1-Motion>", self._on_drag_motion)

        self._process_queue()

    # File list selection

    def _on_file_select(self, event: Any) -> None:
        """
        Callback when a file in the list is clicked.
        Loads the selected PDF into the preview pane.
        """
        selected = self.file_list.get_selected_file()
        if selected and selected != self.current_pdf_path:
            self._load_pdf(selected)

    # Range and preview callbacks

    def _on_range_change(self, source: str) -> None:
        """
        Handles Start/End slider movements.
        Ensures Start <= End.
        Updates the text entry and preview.
        """
        start = self.val_min_var.get()
        end = self.val_max_var.get()
        if start > end:
            if source == "min":
                end = start  # Push end
            else:
                start = end  # Pull start
            self.val_min_var.set(start)
            self.val_max_var.set(end)

        self.range_entry.delete(0, tk.END)
        self.range_entry.insert(0, f"{start}-{end}")

        # Jump preview to the adjusted handle
        target_page = start if source == "min" else end
        self.preview_var.set(target_page)
        self._update_preview(target_page - 1)

    def _on_preview_change(self, event: Any) -> None:
        """Callback for the specific Preview-only slider."""
        pg = int(float(event))
        self._update_preview(pg - 1)

    def _on_mouse_wheel(self, event: Any) -> None:
        """Handles Mouse Wheel to scroll pages."""
        if self.total_pages == 0:
            return

        # Delta analysis
        delta = 0
        if event.num == 5 or event.delta < 0:
            delta = 1  # Next page
        elif event.num == 4 or event.delta > 0:
            delta = -1  # Prev page

        new_pg = self.preview_var.get() + delta
        new_pg = max(1, min(self.total_pages, new_pg))

        self.preview_var.set(new_pg)
        self._update_preview(new_pg - 1)

    def _on_drag_start(self, event: Any) -> None:
        """Capture Y position on click."""
        self.last_y = event.y

    def _on_drag_motion(self, event: Any) -> None:
        """Calculates vertical drag distance to emulate scrolling."""
        if self.total_pages == 0:
            return

        diff = event.y - self.last_y
        if abs(diff) > 20:  # Threshold for page flip
            delta = -1 if diff > 0 else 1  # Drag down -> Move up (Prev)

            new_pg = self.preview_var.get() + delta
            new_pg = max(1, min(self.total_pages, new_pg))

            if new_pg != self.preview_var.get():
                self.preview_var.set(new_pg)
                self._update_preview(new_pg - 1)
                self.last_y = event.y

    # Queue processing

    def _process_queue(self) -> None:
        """GUI Update Loop."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    self.status_lbl.config(text=data)
                elif msg_type == "progress":
                    pct, message = data
                    self.progress["value"] = pct
                    self.status_lbl.config(text=message)
                elif msg_type == "success":
                    message = data["message"] if isinstance(data, dict) else data
                    output_dir = data.get("output_dir", "") if isinstance(data, dict) else ""
                    self.progress["value"] = 100
                    self.status_lbl.config(text=message)
                    self.btn.config(state="normal")
                    self.output_actions.set_path(output_dir)
                    messagebox.showinfo("Success", message)
                elif msg_type == "error":
                    self.progress["value"] = 0
                    self.status_lbl.config(text="Error occurred.")
                    self.btn.config(state="normal")
                    messagebox.showerror("Error", data)
                elif msg_type == "preview":
                    # Update Image
                    img = data
                    self.preview_lbl.config(image=img, text="")
                    self.preview_img = img  # Keep ref
        except queue.Empty:
            pass

        if hasattr(self, "status_lbl") and self.status_lbl.winfo_exists():
            self.status_lbl.after(100, self._process_queue)

    # PDF loading and preview

    def _load_pdf(self, path: str) -> None:
        """
        Loads PDF metadata and renders the first page preview.
        """
        try:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(path)
            self.current_pdf_path = path
            self.total_pages = len(self.doc)

            # Configure Sliders
            self.scale_min.config(to=self.total_pages, value=1)
            self.scale_max.config(to=self.total_pages, value=self.total_pages)

            # Configure Preview Scale
            self.preview_scale.config(to=self.total_pages)
            self.preview_var.set(1)

            # Reset Range Text
            self.range_entry.delete(0, tk.END)
            self.range_entry.insert(0, f"1-{self.total_pages}")

            self.btn.config(state="normal")
            self.status_lbl.config(
                text=f"Loaded: {os.path.basename(path)} ({self.total_pages} pages)"
            )

            # Show Page 1
            self._update_preview(0)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load PDF: {e}")

    def _update_preview(self, page_num: int) -> None:
        """
        Generates a thumbnail for the specified page number.
        Uses Pillow to convert PyMuPDF Pixmap to Tkinter PhotoImage.
        """
        if not self.doc or page_num < 0 or page_num >= self.total_pages:
            return

        # Update text indicator
        self.page_lbl.config(text=f"Page: {page_num + 1}/{self.total_pages}")

        try:
            page = self.doc[page_num]
            # DPI 100 provides a good balance of speed vs quality for preview
            pix = page.get_pixmap(dpi=100)

            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            # Resize to fit within 500px high
            base_height = 500
            aspect = img.width / img.height
            new_w = int(base_height * aspect)

            img = img.resize((new_w, base_height), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)

            self.queue.put(("preview", tk_img))
        except Exception:
            pass

    def _browse_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    # Execution

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Validates inputs and starts splitting thread (Option B: current file only)."""
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            messagebox.showerror("Error", "No PDF is currently loaded for preview.")
            return

        ranges_str = self.range_entry.get()
        out_dir = self.output_entry.get()
        if not out_dir:
            messagebox.showwarning("Warning", "Please choose an output folder.")
            return
        set_setting("splitter.output_dir", out_dir)

        self.status_lbl.config(text="Splitting...")
        self.btn.config(state="disabled")
        self.progress["value"] = 0
        self.output_actions.clear()
        threading.Thread(
            target=self._run_split, args=(self.current_pdf_path, out_dir, ranges_str)
        ).start()

    def _parse_ranges(
        self, range_str: str, total_pages: int
    ) -> List[Tuple[int, int]]:
        """
        Parses range string (e.g., '1-3, 5') into list of tuples.
        Returns 0-indexed values.
        """
        if not range_str.strip():
            return [(i, i) for i in range(total_pages)]
        ranges = []
        parts = range_str.split(",")
        for p in parts:
            p = p.strip()
            if "-" in p:
                start, end = map(int, p.split("-"))
            else:
                start = end = int(p)
            if start < 1 or end < 1 or start > end or end > total_pages:
                raise ValueError(
                    f"Page range {p} is out of bounds. PDF has {total_pages} pages."
                )
            ranges.append((start - 1, end - 1))
        return ranges

    def _run_split(self, input_path: str, out_dir: str, ranges_str: str) -> None:
        """Worker thread logic for PDF splitting."""
        try:
            os.makedirs(out_dir, exist_ok=True)
            # Re-open doc in thread (PyMuPDF objects are not thread-safe across threads)
            doc = fitz.open(input_path)
            total = len(doc)

            try:
                page_ranges = self._parse_ranges(ranges_str, total)
            except ValueError as exc:
                self.queue.put(("error", str(exc)))
                doc.close()
                return

            base_name = os.path.splitext(os.path.basename(input_path))[0]
            count = 0
            total_ranges = len(page_ranges)
            for idx, (start, end) in enumerate(page_ranges, start=1):
                self.queue.put(
                    (
                        "progress",
                        (
                            ((idx - 1) / total_ranges) * 100,
                            f"Creating split {idx}/{total_ranges}: pages {start + 1}-{end + 1}",
                        ),
                    )
                )
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start, to_page=end)
                out_name = f"{base_name}_{start + 1}-{end + 1}.pdf"
                new_doc.save(os.path.join(out_dir, out_name))
                new_doc.close()
                count += 1
                self.queue.put(
                    (
                        "progress",
                        (
                            (idx / total_ranges) * 100,
                            f"Created split {idx}/{total_ranges}",
                        ),
                    )
                )

            doc.close()
            self.queue.put(
                (
                    "success",
                    {
                        "message": f"Created {count} files in {out_dir}",
                        "output_dir": out_dir,
                    },
                )
            )
        except Exception as e:
            self.queue.put(("error", str(e)))
