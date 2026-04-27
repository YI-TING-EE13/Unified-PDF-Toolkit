"""
Page Manager Tool — Delete and rotate pages within a PDF.

Features:
- Unified FileListWidget as a file queue.
- Click a file in the list to load its preview (same pattern as Splitter).
- Delete pages by range (e.g., '3, 5-7').
- Rotate pages by range with selectable angle (90°, 180°, 270°).
- Default save to ~/Documents/PDFToolkit/Saved/Managed/.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import threading
import os
import queue
from datetime import datetime
from PIL import Image, ImageTk
from typing import List, Optional, Any, Dict

from ...base.tool import BaseTool
from ...ui.components import FileListWidget
from ...utils.file_ops import get_default_save_dir


class PageManagerTool(BaseTool):
    """
    GUI Tool for managing PDF pages (delete / rotate).

    Shares the same preview-pane pattern as the Splitter tool.
    Operations only affect the currently loaded/previewed PDF.
    """

    name: str = "Page Manager"
    icon: str = "📄"

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.doc: Optional[fitz.Document] = None
        self.current_pdf_path: Optional[str] = None
        self.total_pages: int = 0
        self.preview_img: Optional[ImageTk.PhotoImage] = None

    def render(self, parent: ttk.Frame) -> None:
        """
        Builds the UI with a PanedWindow (Split View).
        Left: Controls (File list, Actions).
        Right: Preview.
        """
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, pady=5)

        # --- Left Pane: Controls ---
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        # 1. File List
        self.file_list = FileListWidget(
            left_frame,
            label="PDF Queue (click to preview)",
            filetypes=[("PDF Files", "*.pdf")],
            show_ordering=False,
        )
        self.file_list.pack(fill="x", pady=5)
        self.file_list.bind_select(self._on_file_select)

        # 2. Delete Pages
        del_frame = ttk.LabelFrame(left_frame, text="Delete Pages", padding=10)
        del_frame.pack(fill="x", pady=5)

        ttk.Label(del_frame, text="Pages to delete (e.g., 3, 5-7):").pack(anchor="w")
        self.delete_entry = ttk.Entry(del_frame)
        self.delete_entry.pack(fill="x", pady=(0, 5))
        self.delete_btn = ttk.Button(
            del_frame, text="🗑️ Delete Pages", command=self._delete_pages, state="disabled"
        )
        self.delete_btn.pack(fill="x")

        # 3. Rotate Pages
        rot_frame = ttk.LabelFrame(left_frame, text="Rotate Pages", padding=10)
        rot_frame.pack(fill="x", pady=5)

        row1 = ttk.Frame(rot_frame)
        row1.pack(fill="x", pady=(0, 5))
        ttk.Label(row1, text="Pages (e.g., 1-3):").pack(side="left")
        self.rotate_entry = ttk.Entry(row1, width=15)
        self.rotate_entry.pack(side="left", padx=5)

        ttk.Label(row1, text="Angle:").pack(side="left", padx=(10, 0))
        self.angle_var = tk.StringVar(value="90")
        ttk.Combobox(
            row1,
            textvariable=self.angle_var,
            values=["90", "180", "270"],
            state="readonly",
            width=6,
        ).pack(side="left", padx=5)

        self.rotate_btn = ttk.Button(
            rot_frame, text="🔄 Rotate Pages", command=self._rotate_pages, state="disabled"
        )
        self.rotate_btn.pack(fill="x")

        # 4. Output & Save
        out_frame = ttk.LabelFrame(left_frame, text="Output", padding=10)
        out_frame.pack(fill="x", pady=5)
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(
            side="right"
        )

        self.save_btn = ttk.Button(
            left_frame, text="💾 Save Modified PDF", command=self.execute, state="disabled"
        )
        self.save_btn.pack(pady=10, fill="x")

        self.status_lbl = ttk.Label(left_frame, text="Add PDFs and click one to preview.")
        self.status_lbl.pack()

        # --- Right Pane: Preview ---
        right_frame = ttk.LabelFrame(paned, text="Page Preview", padding=10)
        paned.add(right_frame, weight=3)

        # Nav Controls
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

        # Mouse wheel navigation
        self.preview_lbl.bind("<MouseWheel>", self._on_mouse_wheel)

        self._process_queue()

    # ── File List Selection ─────────────────────────────────────────

    def _on_file_select(self, event: Any) -> None:
        """Loads the clicked file into the preview."""
        selected = self.file_list.get_selected_file()
        if selected and selected != self.current_pdf_path:
            self._load_pdf(selected)

    # ── PDF Loading ─────────────────────────────────────────────────

    def _load_pdf(self, path: str) -> None:
        """Loads a PDF and configures the UI for it."""
        try:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(path)
            self.current_pdf_path = path
            self.total_pages = len(self.doc)

            self.preview_scale.config(to=max(1, self.total_pages))
            self.preview_var.set(1)

            self._enable_buttons()
            self.status_lbl.config(
                text=f"Loaded: {os.path.basename(path)} ({self.total_pages} pages)"
            )
            self._update_preview(0)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load PDF: {e}")

    def _enable_buttons(self) -> None:
        """Enables action buttons after a PDF is loaded."""
        self.delete_btn.config(state="normal")
        self.rotate_btn.config(state="normal")
        self.save_btn.config(state="normal")

    # ── Preview ─────────────────────────────────────────────────────

    def _on_preview_change(self, event: Any) -> None:
        pg = int(float(event))
        self._update_preview(pg - 1)

    def _on_mouse_wheel(self, event: Any) -> None:
        if self.total_pages == 0:
            return
        delta = 1 if (event.num == 5 or event.delta < 0) else -1
        new_pg = max(1, min(self.total_pages, self.preview_var.get() + delta))
        self.preview_var.set(new_pg)
        self._update_preview(new_pg - 1)

    def _update_preview(self, page_num: int) -> None:
        """Generates a thumbnail for the specified page."""
        if not self.doc or page_num < 0 or page_num >= self.total_pages:
            return

        self.page_lbl.config(text=f"Page: {page_num + 1}/{self.total_pages}")

        try:
            page = self.doc[page_num]
            pix = page.get_pixmap(dpi=100)

            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            base_height = 500
            aspect = img.width / img.height
            new_w = int(base_height * aspect)
            img = img.resize((new_w, base_height), Image.Resampling.LANCZOS)

            tk_img = ImageTk.PhotoImage(img)
            self.queue.put(("preview", tk_img))
        except Exception:
            pass

    # ── Queue ───────────────────────────────────────────────────────

    def _process_queue(self) -> None:
        """Polls the thread-safe queue for messages and updates the GUI."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "preview":
                    self.preview_lbl.config(image=data, text="")
                    self.preview_img = data
                elif msg_type == "status":
                    self.status_lbl.config(text=data)
                elif msg_type == "success":
                    self.save_btn.config(state="normal")
                    self.status_lbl.config(text=data)
                    messagebox.showinfo("Success", data)
                elif msg_type == "error":
                    self.save_btn.config(state="normal")
                    self.status_lbl.config(text="Error.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        if hasattr(self, "status_lbl") and self.status_lbl.winfo_exists():
            self.status_lbl.after(100, self._process_queue)

    # ── Parse Range ─────────────────────────────────────────────────

    def _parse_page_list(self, range_str: str) -> List[int]:
        """
        Parses a page range string into a sorted list of 0-indexed page numbers.
        Example: '3, 5-7' -> [2, 4, 5, 6]
        """
        pages = set()
        if not range_str.strip():
            return []
        for part in range_str.split(","):
            part = part.strip()
            if "-" in part:
                start, end = map(int, part.split("-"))
                for p in range(start, end + 1):
                    pages.add(p - 1)  # 0-indexed
            else:
                pages.add(int(part) - 1)
        return sorted(pages)

    # ── Actions ─────────────────────────────────────────────────────

    def _delete_pages(self) -> None:
        """Deletes the specified pages from the in-memory document."""
        if not self.doc:
            return

        range_str = self.delete_entry.get()
        try:
            pages = self._parse_page_list(range_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid page range format.")
            return

        if not pages:
            messagebox.showwarning("Warning", "No pages specified.")
            return

        # Validate page numbers
        invalid = [p for p in pages if p < 0 or p >= self.total_pages]
        if invalid:
            messagebox.showerror(
                "Error",
                f"Page numbers out of range: {[p + 1 for p in invalid]}. "
                f"PDF has {self.total_pages} pages.",
            )
            return

        try:
            # delete_pages expects 0-indexed list
            self.doc.delete_pages(pages)
            self.total_pages = len(self.doc)

            # Refresh UI
            self.preview_scale.config(to=max(1, self.total_pages))
            self.preview_var.set(1)
            self._update_preview(0)

            self.status_lbl.config(
                text=f"Deleted {len(pages)} page(s). Now {self.total_pages} pages. (Unsaved)"
            )
            self.delete_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete pages: {e}")

    def _rotate_pages(self) -> None:
        """Rotates the specified pages by the selected angle."""
        if not self.doc:
            return

        range_str = self.rotate_entry.get()
        try:
            pages = self._parse_page_list(range_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid page range format.")
            return

        if not pages:
            # If no range specified, rotate current preview page
            pages = [self.preview_var.get() - 1]

        angle = int(self.angle_var.get())

        invalid = [p for p in pages if p < 0 or p >= self.total_pages]
        if invalid:
            messagebox.showerror(
                "Error",
                f"Page numbers out of range: {[p + 1 for p in invalid]}.",
            )
            return

        try:
            for p in pages:
                page = self.doc[p]
                page.set_rotation((page.rotation + angle) % 360)

            # Refresh preview
            current = self.preview_var.get() - 1
            self._update_preview(current)

            self.status_lbl.config(
                text=f"Rotated {len(pages)} page(s) by {angle}°. (Unsaved)"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rotate pages: {e}")

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")]
        )
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    # ── Execute (Save) ──────────────────────────────────────────────

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Saves the modified PDF to the specified output path."""
        if not self.doc:
            messagebox.showerror("Error", "No PDF is loaded.")
            return

        output_path = self.output_entry.get()
        if not output_path:
            default_dir = get_default_save_dir("Managed")
            base_name = os.path.splitext(os.path.basename(self.current_pdf_path or "output"))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(default_dir, f"{base_name}_managed_{timestamp}.pdf")

        self.save_btn.config(state="disabled")
        self.status_lbl.config(text="Saving...")

        threading.Thread(target=self._run_save, args=(output_path,)).start()

    def _run_save(self, output_path: str) -> None:
        """Worker thread for saving the modified PDF."""
        try:
            self.doc.save(output_path, garbage=3, deflate=True)
            self.queue.put(("success", f"Saved to {output_path}"))
        except Exception as e:
            self.queue.put(("error", str(e)))
