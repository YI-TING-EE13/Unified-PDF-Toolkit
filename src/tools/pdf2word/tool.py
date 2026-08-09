"""
PDF to Word Tool - Converts PDFs to DOCX using pdf2docx Layout Mode.

This tool follows the same visual pattern as preview-oriented PDF tools:
left-side controls and right-side page preview. Conversion runs in a
background thread and preserves the shared output actions.
"""

import os
import queue
import contextlib
import logging
import tempfile
import threading
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz
import tkinter as tk
from docx import Document
from docx.shared import Inches
from pdf2docx import Converter
from PIL import Image, ImageOps, ImageTk
from tkinter import filedialog, messagebox, ttk

from ...base.tool import BaseTool
from ...ocr import OcrDependencyMissingError, OcrEngine, OcrRequest, get_backend
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


class PDFToWordTool(BaseTool):
    """GUI tool for converting PDF files to Word DOCX files."""

    name: str = "PDF to Word"
    icon: str = "[W]"
    MODES = ("Preserve Layout", "Text Only", "Page Images", "OCR Text")
    OCR_PREPROCESS_OPTIONS = ("None", "Grayscale", "Auto Contrast", "Threshold")

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.doc: Optional[fitz.Document] = None
        self.current_pdf_path: Optional[str] = None
        self.total_pages = 0
        self.preview_img: Optional[ImageTk.PhotoImage] = None
        self.cancel_token = CancellationToken()

    def render(self, parent: ttk.Frame) -> None:
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, pady=5)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        self.file_list = FileListWidget(
            left_frame,
            label="Source PDFs (click to preview)",
            filetypes=[("PDF Files", "*.pdf")],
            show_ordering=False,
            display_formatter=lambda path: os.path.basename(path),
        )
        self.file_list.pack(fill="both", expand=True, pady=5)
        self.file_list.bind_select(self._on_file_select)

        settings_frame = ttk.LabelFrame(left_frame, text="Conversion Settings", padding=10)
        settings_frame.pack(fill="x", pady=5)

        ttk.Label(settings_frame, text="Mode:").grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        self.mode_var = tk.StringVar(
            value=get_setting("pdf2word.mode", "Preserve Layout")
        )
        ttk.Combobox(
            settings_frame,
            textvariable=self.mode_var,
            values=self.MODES,
            state="readonly",
            width=18,
        ).grid(
            row=0, column=1, sticky="w", padx=(0, 25)
        )

        ttk.Label(settings_frame, text="Page Range:").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(8, 0)
        )
        self.range_entry = ttk.Entry(settings_frame)
        self.range_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        settings_frame.columnconfigure(2, weight=1)

        ttk.Label(settings_frame, text="OCR Language:").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=(8, 0)
        )
        self.ocr_lang_var = tk.StringVar(
            value=get_setting("pdf2word.ocr_lang", "eng")
        )
        ttk.Combobox(
            settings_frame,
            textvariable=self.ocr_lang_var,
            values=["eng", "chi_tra", "chi_sim", "eng+chi_tra", "eng+chi_sim"],
            width=18,
        ).grid(row=2, column=1, sticky="w", pady=(8, 0))

        ttk.Label(settings_frame, text="OCR DPI:").grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=(8, 0)
        )
        self.ocr_dpi_var = tk.IntVar(value=int(get_setting("pdf2word.ocr_dpi", 200)))
        ttk.Spinbox(
            settings_frame,
            from_=100,
            to=600,
            increment=50,
            textvariable=self.ocr_dpi_var,
            width=10,
        ).grid(row=3, column=1, sticky="w", pady=(8, 0))

        ttk.Label(settings_frame, text="OCR Cleanup:").grid(
            row=4, column=0, sticky="w", padx=(0, 10), pady=(8, 0)
        )
        self.ocr_preprocess_var = tk.StringVar(
            value=get_setting("pdf2word.ocr_preprocess", "Grayscale")
        )
        ttk.Combobox(
            settings_frame,
            textvariable=self.ocr_preprocess_var,
            values=self.OCR_PREPROCESS_OPTIONS,
            state="readonly",
            width=18,
        ).grid(row=4, column=1, sticky="w", pady=(8, 0))

        ttk.Label(
            settings_frame,
            text="Blank page range = all pages. OCR requires Tesseract and installed language data.",
            foreground="gray",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.preflight_lbl = ttk.Label(
            settings_frame, text="Select a PDF to preview and preflight.", foreground="gray"
        )
        self.preflight_lbl.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))

        out_frame = ttk.LabelFrame(left_frame, text="Output Folder", padding=10)
        out_frame.pack(fill="x", pady=5)
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.output_entry.insert(
            0, get_setting("pdf2word.output_dir", get_default_save_dir("Word"))
        )
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(
            side="right"
        )

        self.btn = ttk.Button(left_frame, text="Convert to Word", command=self.execute)
        self.btn.pack(pady=(15, 5), fill="x")
        self.cancel_btn = ttk.Button(
            left_frame, text="Cancel", command=self._cancel, state="disabled"
        )
        self.cancel_btn.pack(pady=(0, 10), fill="x")

        self.progress = ttk.Progressbar(left_frame, mode="determinate")
        self.progress.pack(fill="x")
        self.status_lbl = ttk.Label(left_frame, text="Ready.")
        self.status_lbl.pack(anchor="w")

        self.output_actions = OutputActions(left_frame)
        self.output_actions.pack(anchor="w", pady=(8, 0))

        right_frame = ttk.LabelFrame(paned, text="PDF Preview", padding=10)
        paned.add(right_frame, weight=3)

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

        self.preview_lbl = ttk.Label(right_frame, text="No PDF loaded", anchor="center")
        self.preview_lbl.pack(fill="both", expand=True)
        self.preview_lbl.bind("<MouseWheel>", self._on_mouse_wheel)
        self.preview_lbl.bind("<Button-4>", self._on_mouse_wheel)
        self.preview_lbl.bind("<Button-5>", self._on_mouse_wheel)

        self._process_queue()

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def _on_file_select(self, event: Any) -> None:
        selected = self.file_list.get_selected_file()
        if selected and selected != self.current_pdf_path:
            self._load_pdf(selected)

    def _load_pdf(self, path: str) -> None:
        try:
            if self.doc:
                self.doc.close()
            doc = fitz.open(path)
            if doc.needs_pass:
                doc.close()
                raise ValueError("This PDF is encrypted and cannot be previewed.")
            if doc.page_count == 0:
                doc.close()
                raise ValueError("This PDF has no pages.")

            self.doc = doc
            self.current_pdf_path = path
            self.total_pages = doc.page_count
            self.preview_scale.config(to=max(1, self.total_pages))
            self.preview_var.set(1)
            self._update_preview(0)
            self._update_preflight_label(path)
        except Exception as exc:
            self.doc = None
            self.current_pdf_path = None
            self.total_pages = 0
            self.page_lbl.config(text="Page: -/-")
            self.preview_lbl.config(image="", text="No PDF loaded")
            self.preflight_lbl.config(text=f"Preview unavailable: {exc}")
            messagebox.showerror("Error", f"Failed to load PDF preview: {exc}")

    def _update_preflight_label(self, path: str) -> None:
        try:
            report = self.preflight_pdf(path, self.range_entry.get().strip())
            message = (
                f"{report['page_count']} pages, "
                f"{report['selected_page_count']} selected. "
            )
            if report["image_only"]:
                message += "Looks image-only/scanned; OCR Text or Page Images may help."
            else:
                message += "Text detected."
            self.preflight_lbl.config(text=message)
        except Exception as exc:
            self.preflight_lbl.config(text=f"Preflight warning: {exc}")

    def _on_preview_change(self, value: Any) -> None:
        page_num = int(float(value)) - 1
        self._update_preview(page_num)

    def _on_mouse_wheel(self, event: Any) -> None:
        if self.total_pages == 0:
            return
        delta = 1 if (getattr(event, "num", None) == 5 or event.delta < 0) else -1
        new_page = max(1, min(self.total_pages, self.preview_var.get() + delta))
        self.preview_var.set(new_page)
        self._update_preview(new_page - 1)

    def _update_preview(self, page_num: int) -> None:
        if not self.doc or page_num < 0 or page_num >= self.total_pages:
            return
        self.page_lbl.config(text=f"Page: {page_num + 1}/{self.total_pages}")
        try:
            page = self.doc[page_num]
            pix = page.get_pixmap(dpi=100)
            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            max_height = 560
            if img.height > max_height:
                ratio = max_height / img.height
                img = img.resize(
                    (int(img.width * ratio), max_height), Image.Resampling.LANCZOS
                )

            tk_img = ImageTk.PhotoImage(img)
            self.preview_lbl.config(image=tk_img, text="")
            self.preview_img = tk_img
        except Exception as exc:
            self.preview_lbl.config(image="", text=f"Preview failed: {exc}")

    def _process_queue(self) -> None:
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    pct, message = data
                    self.progress["value"] = pct
                    self.status_lbl.config(text=message)
                elif msg_type == "success":
                    self.btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.progress["value"] = 100
                    output_dir = data["output_dir"]
                    report_path = data.get("report_path", "")
                    self.output_actions.set_path(output_dir)
                    self.status_lbl.config(text=data["message"])
                    message = data["message"]
                    if report_path:
                        message += f"\nReport: {report_path}"
                    messagebox.showinfo("Success", message)
                elif msg_type == "cancelled":
                    self.btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.progress["value"] = 0
                    self.status_lbl.config(text=data["message"])
                    messagebox.showinfo("Cancelled", data["message"])
                elif msg_type == "error":
                    self.btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.progress["value"] = 0
                    self.status_lbl.config(text="Error occurred.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        if hasattr(self, "status_lbl") and self.status_lbl.winfo_exists():
            self.status_lbl.after(100, self._process_queue)

    def _cancel(self) -> None:
        self.cancel_token.cancel()
        self.status_lbl.config(text="Cancelling after current file...")

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        files = self.file_list.get_files()
        if not files:
            messagebox.showwarning("Warning", "No files selected!")
            return

        output_dir = self.output_entry.get()
        if not output_dir:
            messagebox.showwarning("Warning", "Please choose an output folder.")
            return

        range_text = self.range_entry.get().strip()
        mode = self.mode_var.get()
        ocr_lang = self.ocr_lang_var.get().strip() or "eng"
        ocr_dpi = max(100, min(600, int(self.ocr_dpi_var.get())))
        ocr_preprocess = self.ocr_preprocess_var.get()
        preflight = self.preflight_files(files, range_text, mode)
        if preflight["fatal_errors"]:
            messagebox.showerror(
                "Preflight Failed",
                "\n".join(friendly_error_message(item) for item in preflight["fatal_errors"][:8]),
            )
            return
        if preflight["warnings"]:
            messagebox.showwarning(
                "Preflight Warnings",
                "\n".join(preflight["warnings"][:8]),
            )

        set_setting("pdf2word.output_dir", output_dir)
        set_setting("pdf2word.mode", mode)
        set_setting("pdf2word.ocr_lang", ocr_lang)
        set_setting("pdf2word.ocr_dpi", ocr_dpi)
        set_setting("pdf2word.ocr_preprocess", ocr_preprocess)
        remember_inputs(files)

        self.btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.cancel_token.reset()
        self.progress["value"] = 0
        self.output_actions.clear()
        self.status_lbl.config(text="Converting PDFs to Word...")

        threading.Thread(
            target=self._run_conversion,
            args=(files, output_dir, range_text, mode, ocr_lang, ocr_dpi, ocr_preprocess),
            daemon=True,
        ).start()

    def _run_conversion(
        self,
        files: List[str],
        output_dir: str,
        range_text: str,
        mode: str,
        ocr_lang: str = "eng",
        ocr_dpi: int = 200,
        ocr_preprocess: str = "Grayscale",
    ) -> None:
        results = {"success": 0, "failed": 0, "skipped": 0, "errors": []}
        total = len(files)
        report = WorkflowReport(
            "PDF to Word",
            output_dir,
            options={
                "mode": mode,
                "page_range": range_text or "all",
                "ocr_lang": ocr_lang,
                "ocr_dpi": ocr_dpi,
                "ocr_preprocess": ocr_preprocess,
                "conflict_policy": get_conflict_policy(),
            },
        )

        try:
            os.makedirs(output_dir, exist_ok=True)

            for idx, input_path in enumerate(files, start=1):
                if self.cancel_token.is_cancelled():
                    report.add(input_path, status="cancelled")
                    report_path = report.write()
                    self.queue.put(
                        (
                            "cancelled",
                            {
                                "message": (
                                    f"Cancelled. Success: {results['success']}, "
                                    f"failed: {results['failed']}, skipped: {results['skipped']}.\n"
                                    f"Report: {report_path}"
                                ),
                                "report_path": report_path,
                            },
                        )
                    )
                    return
                pct = ((idx - 1) / total) * 100
                self.queue.put(
                    (
                        "progress",
                        (pct, f"Converting {idx}/{total}: {os.path.basename(input_path)}"),
                    )
                )

                try:
                    if not os.path.exists(input_path):
                        results["skipped"] += 1
                        results["errors"].append(f"File not found: {input_path}")
                        report.add(input_path, status="skipped", message="File not found.")
                        continue

                    output_path = self._output_path(input_path, output_dir)
                    resolved_output_path = resolve_output_path(
                        output_path, get_conflict_policy()
                    )
                    if resolved_output_path is None:
                        results["skipped"] += 1
                        report.add(
                            input_path,
                            output_path,
                            status="skipped",
                            message="Output exists and conflict policy is skip.",
                        )
                        continue
                    self.convert_pdf_to_docx(
                        input_path,
                        resolved_output_path,
                        range_text,
                        mode,
                        ocr_lang=ocr_lang,
                        ocr_dpi=ocr_dpi,
                        ocr_preprocess=ocr_preprocess,
                    )
                    results["success"] += 1
                    report.add(input_path, resolved_output_path)
                except Exception as exc:
                    friendly = friendly_error_message(exc)
                    results["failed"] += 1
                    results["errors"].append(
                        f"{os.path.basename(input_path)}: {friendly}"
                    )
                    report.add(input_path, status="failed", message=friendly)

            self.queue.put(("progress", (100, "Conversion complete.")))
            report_path = report.write()
            summary = (
                f"Word conversion complete ({mode}). Success: {results['success']}, "
                f"failed: {results['failed']}, skipped: {results['skipped']}."
            )
            if results["errors"]:
                summary += "\n" + "\n".join(results["errors"][:5])
            self.queue.put(
                (
                    "success",
                    {
                        "message": summary,
                        "output_dir": output_dir,
                        "report_path": report_path,
                    },
                )
            )
        except Exception as exc:
            report.add("", status="failed", message=str(exc))
            report.write()
            self.queue.put(("error", friendly_error_message(exc, "PDF to Word failed")))

    @classmethod
    def convert_pdf_to_docx(
        cls,
        input_path: str,
        output_path: str,
        range_text: str = "",
        mode: str = "Preserve Layout",
        ocr_lang: str = "eng",
        ocr_dpi: int = 200,
        ocr_preprocess: str = "Grayscale",
    ) -> None:
        """
        Converts a PDF to DOCX using the selected quality mode.

        Preserve Layout produces the most editable layout, while Page Images is
        the visual-fidelity fallback for formulas, scanned pages, and complex
        PDFs that do not convert cleanly into editable Word content.
        """
        _, page_indices = cls._inspect_pdf(input_path, range_text)

        if mode == "Text Only":
            cls._convert_text_only(input_path, output_path, page_indices)
            return
        if mode == "Page Images":
            cls._convert_page_images(input_path, output_path, page_indices)
            return
        if mode == "OCR Text":
            cls._convert_ocr_text(
                input_path,
                output_path,
                page_indices,
                ocr_lang=ocr_lang,
                ocr_dpi=ocr_dpi,
                ocr_preprocess=ocr_preprocess,
            )
            return

        temp_path = ""
        source_path = input_path

        try:
            if page_indices is not None:
                temp_path = cls._create_selected_pages_pdf(input_path, page_indices)
                source_path = temp_path

            with cls._suppress_upstream_console_output():
                converter = Converter(source_path)
                try:
                    converter.convert(output_path)
                finally:
                    converter.close()
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    @classmethod
    def preflight_files(
        cls, files: List[str], range_text: str, mode: str = "Preserve Layout"
    ) -> Dict[str, List[str]]:
        warnings: List[str] = []
        fatal_errors: List[str] = []

        for input_path in files:
            try:
                report = cls.preflight_pdf(input_path, range_text)
                if report["image_only"] and mode != "Page Images":
                    warnings.append(
                        f"{os.path.basename(input_path)} looks image-only/scanned. "
                        "Use OCR Text for editable extracted text or Page Images for visual fidelity."
                    )
            except Exception as exc:
                fatal_errors.append(f"{os.path.basename(input_path)}: {exc}")

        return {"warnings": warnings, "fatal_errors": fatal_errors}

    @staticmethod
    def _selected_pages(doc: fitz.Document, page_indices: Optional[List[int]]) -> List[int]:
        return page_indices if page_indices is not None else list(range(doc.page_count))

    @classmethod
    def _convert_text_only(
        cls, input_path: str, output_path: str, page_indices: Optional[List[int]]
    ) -> None:
        document = Document()
        document.add_heading(Path(input_path).stem, level=1)

        with fitz.open(input_path) as doc:
            selected = cls._selected_pages(doc, page_indices)
            for count, page_index in enumerate(selected):
                if count:
                    document.add_page_break()
                document.add_heading(f"Page {page_index + 1}", level=2)
                text = doc[page_index].get_text("text").strip()
                if text:
                    for block in text.split("\n\n"):
                        clean = " ".join(line.strip() for line in block.splitlines() if line.strip())
                        if clean:
                            document.add_paragraph(clean)
                else:
                    document.add_paragraph("[No extractable text on this page.]")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        document.save(output_path)

    @classmethod
    def _convert_page_images(
        cls, input_path: str, output_path: str, page_indices: Optional[List[int]]
    ) -> None:
        document = Document()
        section = document.sections[0]
        usable_width = section.page_width - section.left_margin - section.right_margin
        image_width = Inches(usable_width / 914400)

        with fitz.open(input_path) as doc:
            selected = cls._selected_pages(doc, page_indices)
            for count, page_index in enumerate(selected):
                if count:
                    document.add_page_break()
                pix = doc[page_index].get_pixmap(dpi=150, alpha=False)
                # PyMuPDF already owns the rendered pixmap. Encoding it directly
                # avoids a full-frame copy into Pillow and its PNG encoder path.
                buffer = BytesIO(pix.tobytes("png"))
                document.add_picture(buffer, width=image_width)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        document.save(output_path)

    @classmethod
    def _convert_ocr_text(
        cls,
        input_path: str,
        output_path: str,
        page_indices: Optional[List[int]],
        ocr_lang: str = "eng",
        ocr_dpi: int = 200,
        ocr_preprocess: str = "Grayscale",
    ) -> None:
        document = Document()
        document.add_heading(Path(input_path).stem, level=1)
        backend = get_backend(OcrEngine.TESSERACT)

        with fitz.open(input_path) as doc:
            selected = cls._selected_pages(doc, page_indices)
            for count, page_index in enumerate(selected):
                if count:
                    document.add_page_break()
                document.add_heading(f"Page {page_index + 1}", level=2)
                pix = doc[page_index].get_pixmap(dpi=ocr_dpi, alpha=False)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                image = cls.prepare_ocr_image(image, ocr_preprocess)
                try:
                    result = backend.recognize(
                        OcrRequest(
                            engine=OcrEngine.TESSERACT,
                            images=[image],
                            source_path=input_path,
                            page_numbers=[page_index + 1],
                            language=ocr_lang,
                        )
                    )
                except OcrDependencyMissingError as exc:
                    raise RuntimeError(str(exc)) from exc
                text = result.pages[0].text.strip() if result.pages else ""
                document.add_paragraph(text or "[No OCR text detected on this page.]")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        document.save(output_path)

    @classmethod
    def prepare_ocr_image(cls, image: Image.Image, preprocess: str = "Grayscale") -> Image.Image:
        mode = preprocess if preprocess in cls.OCR_PREPROCESS_OPTIONS else "Grayscale"
        if mode == "None":
            return image
        gray = ImageOps.grayscale(image)
        if mode == "Grayscale":
            return gray
        if mode == "Auto Contrast":
            return ImageOps.autocontrast(gray)
        if mode == "Threshold":
            contrasted = ImageOps.autocontrast(gray)
            return contrasted.point(lambda px: 255 if px > 180 else 0, mode="1")
        return gray

    @classmethod
    def preflight_pdf(cls, input_path: str, range_text: str = "") -> Dict[str, Any]:
        report, _ = cls._inspect_pdf(input_path, range_text)
        return report

    @classmethod
    def _inspect_pdf(
        cls, input_path: str, range_text: str = ""
    ) -> tuple[Dict[str, Any], Optional[List[int]]]:
        if not os.path.exists(input_path):
            raise FileNotFoundError(input_path)

        with fitz.open(input_path) as doc:
            if doc.needs_pass:
                raise ValueError("PDF is encrypted and cannot be converted.")
            if doc.page_count == 0:
                raise ValueError("PDF has no pages.")
            page_indices = cls._parse_page_range_text(range_text, doc.page_count)
            selected = page_indices if page_indices is not None else list(range(doc.page_count))
            text_pages = 0
            for page_index in selected[:10]:
                if doc[page_index].get_text("text").strip():
                    text_pages += 1

            report = {
                "page_count": doc.page_count,
                "selected_page_count": len(selected),
                "text_pages_sampled": text_pages,
                "image_only": text_pages == 0,
            }
        return report, page_indices

    @staticmethod
    def parse_page_range(range_text: str, input_path: str) -> Optional[List[int]]:
        if not range_text.strip():
            return None

        with fitz.open(input_path) as doc:
            total_pages = doc.page_count
            if doc.needs_pass:
                raise ValueError("PDF is encrypted and cannot be read.")

        return PDFToWordTool._parse_page_range_text(range_text, total_pages)

    @staticmethod
    def _parse_page_range_text(range_text: str, total_pages: int) -> Optional[List[int]]:
        if not range_text.strip():
            return None

        page_indices: List[int] = []
        for raw_part in range_text.split(","):
            part = raw_part.strip()
            if not part:
                continue
            if "-" in part:
                start, end = map(int, part.split("-", 1))
            else:
                start = end = int(part)

            if start < 1 or end < 1 or start > end or end > total_pages:
                raise ValueError(
                    f"Page range {part} is out of bounds. PDF has {total_pages} pages."
                )
            page_indices.extend(range(start - 1, end))

        if not page_indices:
            raise ValueError("Page range is empty.")
        return page_indices

    @staticmethod
    def _create_selected_pages_pdf(input_path: str, page_indices: List[int]) -> str:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", prefix="pdf_to_word_", delete=False
        ) as temp_file:
            temp_path = temp_file.name

        with fitz.open(input_path) as source_doc:
            selected_doc = fitz.open()
            try:
                for page_index in page_indices:
                    selected_doc.insert_pdf(
                        source_doc, from_page=page_index, to_page=page_index
                    )
                selected_doc.save(temp_path)
            finally:
                selected_doc.close()

        return temp_path

    @staticmethod
    def _suppress_upstream_console_output() -> contextlib.ExitStack:
        sink = _NullTextSink()
        stack = contextlib.ExitStack()
        stack.enter_context(contextlib.redirect_stdout(sink))
        stack.enter_context(contextlib.redirect_stderr(sink))
        stack.enter_context(_temporarily_disabled_logging())
        return stack

    @staticmethod
    def _output_path(input_path: str, output_dir: str) -> str:
        return str(Path(output_dir) / f"{Path(input_path).stem}.docx")


class _NullTextSink:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


@contextlib.contextmanager
def _temporarily_disabled_logging():
    previous_disable_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous_disable_level)
