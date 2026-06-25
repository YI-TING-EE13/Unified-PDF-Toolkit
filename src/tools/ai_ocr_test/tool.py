"""Developer-only fake AI OCR test workflow.

This tool intentionally uses only the fake Unlimited-OCR backend. It does not
download models, call local endpoint servers, import AI runtimes, or perform
real OCR inference.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import fitz
from PIL import Image

from ...base.tool import BaseTool
from ...ocr import OcrConsentRequiredError, OcrEngine, OcrRequest
from ...ocr.consent import load_advanced_ocr_consent, require_valid_consent
from ...ocr.unlimited_fake import (
    UNLIMITED_OCR_MODEL_ID,
    UNLIMITED_OCR_PROVIDER,
    FakeUnlimitedOcrBackend,
)
from ...ui.components import FileListWidget, OutputActions
from ...utils.file_ops import get_default_save_dir, resolve_output_path
from ...utils.settings import get_setting, set_setting
from ...utils.workflow import CancellationToken, get_conflict_policy, remember_inputs

SUPPORTED_INPUT_TYPES = [
    ("PDF and Images", "*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
    ("PDF", "*.pdf"),
    ("Images", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
]
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
SUPPORTED_OUTPUT_FORMATS = {"txt", "md"}
DEFAULT_PROMPT = "developer fake document parsing."


@dataclass(frozen=True)
class FakeAiOcrOutput:
    """One local output written by the fake OCR workflow."""

    source: str
    path: str
    format: str


@dataclass(frozen=True)
class FakeAiOcrWorkflowResult:
    """Summary returned by the fake OCR workflow without OCR text."""

    outputs: List[FakeAiOcrOutput] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def success_count(self) -> int:
        return len({output.source for output in self.outputs})


def _normalise_formats(formats: Iterable[str]) -> List[str]:
    selected = []
    for output_format in formats:
        value = output_format.lower().lstrip(".")
        if value not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output format: {output_format}")
        if value not in selected:
            selected.append(value)
    if not selected:
        raise ValueError("Select at least one output format.")
    return selected


def _render_pdf_pages(path: Path) -> tuple[List[Image.Image], List[int]]:
    images: List[Image.Image] = []
    page_numbers: List[int] = []
    with fitz.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            pixmap = page.get_pixmap(alpha=False)
            images.append(
                Image.frombytes(
                    "RGB", (pixmap.width, pixmap.height), pixmap.samples
                )
            )
            page_numbers.append(index)
    return images, page_numbers


def _load_input_images(path: Path) -> tuple[List[Image.Image], List[int]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _render_pdf_pages(path)
    if suffix in SUPPORTED_IMAGE_EXTENSIONS:
        with Image.open(path) as image:
            return [image.convert("RGB").copy()], [1]
    raise ValueError(f"Unsupported input type: {path.suffix or path.name}")


def _text_output(source_name: str, result) -> str:
    lines = [
        "Developer-only fake AI OCR output",
        "No real Unlimited-OCR inference was performed.",
        f"Source: {source_name}",
        "",
    ]
    for page in result.pages:
        lines.extend([f"Page {page.page_number}", page.text, ""])
    return "\n".join(lines).rstrip() + "\n"


def _markdown_output(source_name: str, result) -> str:
    lines = [
        "# Developer-only Fake AI OCR Output",
        "",
        "**No real Unlimited-OCR inference was performed.**",
        "",
        f"- Source: `{source_name}`",
        "- Backend: fake Unlimited-OCR test backend",
        "",
    ]
    for page in result.pages:
        lines.extend([f"## Page {page.page_number}", "", page.text, ""])
    return "\n".join(lines).rstrip() + "\n"


def _write_output(path: Path, output_format: str, source_name: str, result) -> str | None:
    requested = path / f"{source_name.rsplit('.', 1)[0]}_fake_ai_ocr.{output_format}"
    output_path = resolve_output_path(str(requested), get_conflict_policy())
    if output_path is None:
        return None

    content = (
        _markdown_output(source_name, result)
        if output_format == "md"
        else _text_output(source_name, result)
    )
    Path(output_path).write_text(content, encoding="utf-8")
    return output_path


def run_fake_ai_ocr_workflow(
    files: Sequence[str],
    output_dir: str,
    formats: Iterable[str],
    *,
    consent=None,
    cancellation_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> FakeAiOcrWorkflowResult:
    """Run deterministic fake OCR for selected files and write local outputs.

    The result intentionally omits OCR text. OCR-like text is written only to
    the requested local output files.
    """

    require_valid_consent(
        consent,
        provider=UNLIMITED_OCR_PROVIDER,
        model_id=UNLIMITED_OCR_MODEL_ID,
    )
    selected_formats = _normalise_formats(formats)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    backend = FakeUnlimitedOcrBackend(consent=consent)
    is_cancelled = cancellation_check or (lambda: False)
    outputs: List[FakeAiOcrOutput] = []
    failed: List[str] = []
    skipped: List[str] = []
    total = len(files)

    for index, file_path in enumerate(files, start=1):
        if is_cancelled():
            return FakeAiOcrWorkflowResult(
                outputs=outputs, failed=failed, skipped=skipped, cancelled=True
            )

        source = Path(file_path)
        source_name = source.name
        if progress_callback:
            progress_callback(index - 1, total, f"Preparing {source_name}")

        try:
            images, page_numbers = _load_input_images(source)
            request = OcrRequest(
                engine=OcrEngine.UNLIMITED_OCR_FAKE,
                images=images,
                source_path=str(source),
                page_numbers=page_numbers,
                prompt=DEFAULT_PROMPT,
            )
            result = backend.recognize(request)
            for output_format in selected_formats:
                output_path = _write_output(output_root, output_format, source_name, result)
                if output_path is None:
                    skipped.append(f"{source_name}.{output_format}")
                else:
                    outputs.append(
                        FakeAiOcrOutput(
                            source=source_name,
                            path=output_path,
                            format=output_format,
                        )
                    )
        except Exception as exc:
            failed.append(f"{source_name}: {exc}")

        if progress_callback:
            progress_callback(index, total, f"Processed {source_name}")

    return FakeAiOcrWorkflowResult(outputs=outputs, failed=failed, skipped=skipped)


class FakeAiOcrTestTool(BaseTool):
    """Hidden developer tool for testing future advanced OCR UI flows."""

    name: str = "[Dev] Fake AI OCR Test"
    icon: str = "[DEV]"

    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.cancel_token = CancellationToken()

    def render(self, parent: ttk.Frame) -> None:
        self.parent = parent

        notice = ttk.LabelFrame(parent, text="Developer/Test Only", padding=10)
        notice.pack(fill="x", pady=(0, 10))
        ttk.Label(
            notice,
            text=(
                "This workflow uses only the deterministic fake Unlimited-OCR "
                "backend. It performs no real AI OCR, model download, endpoint "
                "call, GPU runtime, network upload, screen OCR, or background OCR."
            ),
            wraplength=900,
        ).pack(anchor="w")

        self.file_list = FileListWidget(
            parent,
            label="PDF/Image Files",
            filetypes=SUPPORTED_INPUT_TYPES,
            show_ordering=True,
        )
        self.file_list.pack(fill="both", expand=True, pady=(0, 10))

        options = ttk.LabelFrame(parent, text="Fake Output Options", padding=10)
        options.pack(fill="x", pady=(0, 10))
        self.txt_var = tk.BooleanVar(value=True)
        self.md_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="TXT", variable=self.txt_var).pack(side="left")
        ttk.Checkbutton(options, text="Markdown", variable=self.md_var).pack(
            side="left", padx=(10, 0)
        )

        out_frame = ttk.Frame(parent)
        out_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(out_frame, text="Output Folder:").pack(side="left")
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(8, 5))
        self.output_entry.insert(
            0, get_setting("ai_ocr_test.output_dir", get_default_save_dir("FakeAIOCR"))
        )
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(side="left")

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(0, 8))
        self.start_btn = ttk.Button(
            actions, text="Run Fake AI OCR Test", command=self.execute
        )
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(
            actions, text="Cancel", command=self._cancel, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(parent, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 5))
        self.status_lbl = ttk.Label(parent, text="Ready")
        self.status_lbl.pack(anchor="w")
        self.output_actions = OutputActions(parent)
        self.output_actions.pack(anchor="w", pady=(8, 0))

    def execute(self, params: Optional[Dict] = None) -> None:
        files = self.file_list.get_files()
        if not files:
            messagebox.showwarning("Warning", "No files selected.")
            return
        output_dir = self.output_entry.get()
        if not output_dir:
            messagebox.showwarning("Warning", "Please choose an output folder.")
            return
        formats = self._selected_formats()
        if not formats:
            messagebox.showwarning("Warning", "Select TXT, Markdown, or both.")
            return

        consent = load_advanced_ocr_consent()
        if consent is None:
            messagebox.showwarning(
                "Consent Required",
                (
                    "Fake AI OCR test wiring uses the same consent gate as future "
                    "advanced OCR backends. Review and save consent in Settings / Recent first."
                ),
            )
            return

        set_setting("ai_ocr_test.output_dir", output_dir)
        remember_inputs(files)
        self.cancel_token.reset()
        self.progress["value"] = 0
        self.status_lbl.config(text="Starting fake AI OCR test...")
        self.output_actions.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        threading.Thread(
            target=self._run_workflow,
            args=(files, output_dir, formats, consent),
            daemon=True,
        ).start()
        self.parent.after(100, self._poll_queue)

    def _selected_formats(self) -> List[str]:
        selected = []
        if self.txt_var.get():
            selected.append("txt")
        if self.md_var.get():
            selected.append("md")
        return selected

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def _cancel(self) -> None:
        self.cancel_token.cancel()
        self.status_lbl.config(text="Cancelling...")

    def _progress(self, current: int, total: int, message: str) -> None:
        self.queue.put(("progress", (current, total, message)))

    def _run_workflow(self, files, output_dir, formats, consent) -> None:
        try:
            result = run_fake_ai_ocr_workflow(
                files,
                output_dir,
                formats,
                consent=consent,
                cancellation_check=self.cancel_token.is_cancelled,
                progress_callback=self._progress,
            )
            if result.cancelled:
                self.queue.put(("cancelled", result))
            elif result.failed:
                self.queue.put(("error", result))
            else:
                self.queue.put(("done", result))
        except OcrConsentRequiredError as exc:
            self.queue.put(("error_message", str(exc)))
        except Exception as exc:
            self.queue.put(("error_message", f"Fake AI OCR test failed: {exc}"))

    def _poll_queue(self) -> None:
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    current, total, message = data
                    pct = (current / total * 100) if total else 0
                    self.progress["value"] = pct
                    self.status_lbl.config(text=message)
                elif msg_type == "done":
                    self._finish()
                    first_output = data.outputs[0].path if data.outputs else ""
                    self.output_actions.set_path(first_output)
                    self.status_lbl.config(
                        text=f"Wrote {len(data.outputs)} fake output file(s)."
                    )
                    messagebox.showinfo(
                        "Done",
                        (
                            "Fake AI OCR test completed. No real Unlimited-OCR "
                            "inference was performed."
                        ),
                    )
                elif msg_type == "cancelled":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Fake AI OCR test cancelled.")
                    messagebox.showinfo("Cancelled", "Fake AI OCR test cancelled.")
                elif msg_type == "error":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Fake AI OCR test completed with errors.")
                    messagebox.showerror("Error", "\n".join(data.failed))
                elif msg_type == "error_message":
                    self._finish(reset_progress=True)
                    self.status_lbl.config(text="Fake AI OCR test failed.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass

        if self.cancel_btn["state"] == "normal":
            self.parent.after(100, self._poll_queue)

    def _finish(self, reset_progress: bool = False) -> None:
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.progress["value"] = 0 if reset_progress else 100
