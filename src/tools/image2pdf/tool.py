"""
Image2PDF Tool — Converts multiple images into a single PDF with inline compression.

Features:
- Unified FileListWidget for image selection and ordering.
- Inline compression during PDF creation (adjust DPI/JPEG quality at write time).
- No intermediate large files — images are compressed before insertion.
- Default save to ~/Documents/PDFToolkit/Saved/Image2PDF/.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import threading
import io
import queue
import time
from datetime import datetime
from pathlib import Path
from PIL import Image
from typing import List, Optional, Dict, Any, Tuple

from ...base.tool import BaseTool
from ...ui.components import FileListWidget
from ...utils.file_ops import get_default_save_dir


class Image2PDFTool(BaseTool):
    """
    GUI Tool for converting images to PDF with inline compression.

    Compression is applied at image-insertion time (not as a post-process),
    avoiding huge intermediate files. The user can select a compression
    level that controls both DPI downscaling and JPEG quality.
    """

    name: str = "Image to PDF"
    icon: str = "📷"

    # Compression presets: (scale_factor, jpeg_quality)
    # Scale factor applied to original image dimensions before insertion.
    COMPRESSION_PRESETS: Dict[str, Tuple[float, int]] = {
        "None": (1.0, 95),     # Original resolution, near-lossless
        "Low": (0.9, 85),      # 90% scale, high quality
        "Medium": (0.75, 70),  # 75% scale, balanced
        "High": (0.5, 50),     # 50% scale, maximum compression
    }

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()

    def render(self, parent: ttk.Frame) -> None:
        """
        Renders the Image2PDF UI.

        Layout:
        1. FileListWidget for image selection (order = page order).
        2. Compression settings.
        3. Output file selection.
        4. Progress monitoring.
        """
        # 1. File List (image ordering = page order)
        self.file_list = FileListWidget(
            parent,
            label="Images (Top → Bottom = Page 1 → N)",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif")],
            show_ordering=True,
        )
        self.file_list.pack(fill="both", expand=True, pady=5)

        # 2. Compression Settings
        opts_frame = ttk.LabelFrame(parent, text="Compression Settings", padding=10)
        opts_frame.pack(fill="x", pady=5)

        ttk.Label(opts_frame, text="Compression Level:").pack(side="left")
        self.compression_var = tk.StringVar(value="Medium")
        ttk.Combobox(
            opts_frame,
            textvariable=self.compression_var,
            values=["None", "Low", "Medium", "High"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=10)

        ttk.Label(
            opts_frame,
            text="(Controls DPI scaling & JPEG quality at write time)",
            foreground="gray",
        ).pack(side="left", padx=10)

        # 3. Output
        out_frame = ttk.LabelFrame(parent, text="Output PDF", padding=10)
        out_frame.pack(fill="x", pady=5)

        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(out_frame, text="Save As...", command=self._browse_output).pack(
            side="right"
        )

        # 4. Action
        self.btn = ttk.Button(
            parent, text="Convert to PDF", command=self.execute
        )
        self.btn.pack(pady=15)

        # Progress
        self.progress = ttk.Progressbar(parent, mode="determinate")
        self.progress.pack(fill="x", padx=10)
        self.status_lbl = ttk.Label(parent, text="Ready.")
        self.status_lbl.pack()

        self._process_queue()

    def _process_queue(self) -> None:
        """Polls queue for progress updates."""
        BATCH_SIZE = 10
        processed = 0
        try:
            while processed < BATCH_SIZE:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    pct, msg = data
                    self.progress["value"] = pct
                    self.status_lbl.config(text=msg)
                elif msg_type == "success":
                    self.status_lbl.config(text=data)
                    self.btn.config(state="normal")
                    self.progress["value"] = 100
                    messagebox.showinfo("Success", "PDF Created!")
                elif msg_type == "error":
                    self.status_lbl.config(text="Error occurred.")
                    self.btn.config(state="normal")
                    messagebox.showerror("Error", data)
                processed += 1
        except queue.Empty:
            pass

        if hasattr(self, "status_lbl") and self.status_lbl.winfo_exists():
            self.status_lbl.after(50, self._process_queue)

    def _browse_output(self) -> None:
        """Opens file dialog for PDF output path selection."""
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")]
        )
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Validates input and starts conversion thread."""
        files = self.file_list.get_files()
        if not files:
            messagebox.showwarning("Warning", "No images selected!")
            return

        output_path = self.output_entry.get()
        if not output_path:
            default_dir = get_default_save_dir("Image2PDF")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path(default_dir) / f"Image2PDF_{timestamp}.pdf")

        level = self.compression_var.get()

        self.status_lbl.config(text="Converting...")
        self.btn.config(state="disabled")
        self.progress["value"] = 0
        threading.Thread(
            target=self._run_convert, args=(files, output_path, level)
        ).start()

    def _run_convert(
        self, files: List[str], output_path: str, level: str
    ) -> None:
        """
        Worker thread: converts images to PDF with inline compression.

        Strategy:
        - Open each image with PIL.
        - Apply scale factor and convert to RGB.
        - Encode as JPEG bytes at the configured quality.
        - Insert the compressed JPEG bytes directly into the PDF page.
        - Save with garbage collection and deflation.
        """
        try:
            scale, quality = self.COMPRESSION_PRESETS.get(level, (0.75, 70))
            doc = fitz.open()
            total = len(files)
            last_update = 0.0

            for i, img_path in enumerate(files):
                try:
                    with Image.open(img_path) as pil_img:
                        # Convert to RGB (required for JPEG)
                        if pil_img.mode != "RGB":
                            pil_img = pil_img.convert("RGB")

                        orig_w, orig_h = pil_img.size

                        # Apply scaling
                        if scale < 1.0:
                            new_w = int(orig_w * scale)
                            new_h = int(orig_h * scale)
                            pil_img = pil_img.resize(
                                (new_w, new_h), Image.Resampling.LANCZOS
                            )
                        else:
                            new_w, new_h = orig_w, orig_h

                        # Encode to JPEG bytes in memory
                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                        img_bytes = buf.getvalue()

                    # Create a PDF page matching the image dimensions (in points)
                    # 1 point = 1/72 inch; use 72 DPI mapping for page size
                    page_rect = fitz.Rect(0, 0, new_w * 72 / 96, new_h * 72 / 96)
                    page = doc.new_page(width=page_rect.width, height=page_rect.height)

                    # Insert the compressed image bytes directly
                    page.insert_image(page_rect, stream=img_bytes)

                except Exception as e:
                    self.queue.put(
                        ("error", f"Failed on image {Path(img_path).name}: {e}")
                    )
                    doc.close()
                    return

                # Rate-limited progress updates
                now = time.time()
                if now - last_update > 0.1 or i == total - 1:
                    pct = ((i + 1) / total) * 100
                    self.queue.put(
                        ("progress", (pct, f"Processed {i + 1}/{total} images"))
                    )
                    last_update = now

            # Save with cleanup
            doc.save(output_path, garbage=3, deflate=True)
            doc.close()

            self.queue.put(("success", f"Saved to {output_path}"))

        except Exception as e:
            self.queue.put(("error", str(e)))
