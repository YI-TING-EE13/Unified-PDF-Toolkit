"""Manual Tkinter smoke runner for the Document OCR GUI.

This helper is opt-in and not used by CI. It creates the real Tk app/widgets,
drives the Document OCR tool through its UI object model, and prints only
high-level status. It does not print OCR text or commit generated outputs.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app import PDFToolkitApp  # noqa: E402
from src.ocr.consent import AdvancedOcrConsent  # noqa: E402
from src.ocr.local_model import (  # noqa: E402
    LOCAL_MODEL_DEVICE_CUDA,
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LOCAL_MODEL_MODEL_ID,
    LOCAL_MODEL_PROVIDER,
    LocalModelRuntimeConfig,
)
from src.tools.document_ocr import tool as document_ocr_tool  # noqa: E402
from src.tools.document_ocr.tool import (  # noqa: E402
    LOCAL_UNLIMITED_BACKEND_LABEL,
    TESSERACT_BACKEND_LABEL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual GUI smoke test for Document OCR."
    )
    parser.add_argument(
        "--mode",
        choices=(
            "inspect",
            "tesseract",
            "experimental",
            "failure",
            "cancel",
        ),
        required=True,
    )
    parser.add_argument("--input", default="", help="Optional image/PDF input path.")
    parser.add_argument("--output-dir", default="", help="Optional output folder.")
    parser.add_argument("--model-path", default="", help="Local Unlimited-OCR model dir.")
    parser.add_argument("--worker-python", default=sys.executable)
    parser.add_argument("--timeout-seconds", default="180")
    parser.add_argument(
        "--failure-scenario",
        default="missing_consent",
        choices=(
            "missing_consent",
            "missing_model_path",
            "invalid_model_path",
            "missing_worker_python",
            "unsupported_input",
            "very_short_timeout",
        ),
    )
    parser.add_argument("--cancel-after-seconds", type=float, default=0.2)
    parser.add_argument("--wait-seconds", type=float, default=300.0)
    return parser.parse_args()


class MessageRecorder:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def info(self, title: str, message: str, *args: Any, **kwargs: Any) -> None:
        self.messages.append(("info", title, message))

    def warning(self, title: str, message: str, *args: Any, **kwargs: Any) -> None:
        self.messages.append(("warning", title, message))

    def error(self, title: str, message: str, *args: Any, **kwargs: Any) -> None:
        self.messages.append(("error", title, message))


def main() -> int:
    args = parse_args()
    app = PDFToolkitApp()
    recorder = MessageRecorder()
    document_ocr_tool.messagebox.showinfo = recorder.info
    document_ocr_tool.messagebox.showwarning = recorder.warning
    document_ocr_tool.messagebox.showerror = recorder.error

    try:
        app.update()
        app.switch_view("Document OCR")
        app.update()
        tool = app.tools["Document OCR"]
        if args.mode == "inspect":
            return inspect_tool(tool, recorder)

        input_path = Path(args.input) if args.input else create_sample_image()
        if args.mode == "failure" and args.failure_scenario == "unsupported_input":
            input_path = create_unsupported_input()
        output_dir = Path(args.output_dir) if args.output_dir else create_output_dir(args.mode)
        output_dir.mkdir(parents=True, exist_ok=True)

        configure_common_fields(tool, input_path, output_dir)
        if args.mode == "tesseract":
            tool.backend_var.set(TESSERACT_BACKEND_LABEL)
        else:
            tool.backend_var.set(LOCAL_UNLIMITED_BACKEND_LABEL)
            install_experimental_config(args, input_path)

        tool.execute()
        if recorder.messages and not is_running(tool):
            print_summary(tool, recorder, output_dir)
            return 0

        wait_for_completion(
            app,
            tool,
            recorder,
            output_dir,
            timeout_seconds=args.wait_seconds,
            cancel_after_seconds=(
                args.cancel_after_seconds if args.mode == "cancel" else None
            ),
        )
        print_summary(tool, recorder, output_dir)
        return 0
    finally:
        app.destroy()


def inspect_tool(tool: Any, recorder: MessageRecorder) -> int:
    labels = document_ocr_tool.available_document_ocr_backend_labels()
    print(f"tool_name={tool.name}")
    print(f"default_backend={tool.backend_var.get()}")
    print(f"backend_labels={'|'.join(labels)}")
    print(f"experimental_status={tool.experimental_status_var.get()}")
    print(f"message_count={len(recorder.messages)}")
    return 0


def configure_common_fields(tool: Any, input_path: Path, output_dir: Path) -> None:
    tool.file_list.set_files([str(input_path)])
    tool.output_entry.delete(0, "end")
    tool.output_entry.insert(0, str(output_dir))
    tool.txt_var.set(True)
    tool.md_var.set(True)
    tool.language_var.set("eng")


def install_experimental_config(args: argparse.Namespace, input_path: Path) -> None:
    consent = AdvancedOcrConsent.create(
        provider=LOCAL_MODEL_PROVIDER,
        model_id=LOCAL_MODEL_MODEL_ID,
        acknowledged_model_download_risk=True,
        acknowledged_custom_code_risk=True,
        acknowledged_gpu_vram_use=True,
        acknowledged_temporary_page_images=True,
    )
    model_path = args.model_path
    worker_python = args.worker_python
    timeout = args.timeout_seconds

    if args.mode == "failure":
        if args.failure_scenario == "missing_consent":
            consent = None
        elif args.failure_scenario == "missing_model_path":
            model_path = ""
        elif args.failure_scenario == "invalid_model_path":
            model_path = str(input_path.parent / "missing-model-dir")
        elif args.failure_scenario == "missing_worker_python":
            worker_python = str(input_path.parent / "missing-python.exe")
        elif args.failure_scenario == "very_short_timeout":
            timeout = "0.01"

    config = LocalModelRuntimeConfig(
        enabled=True,
        mode=LOCAL_MODEL_MODE_WORKER_PROCESS,
        model_path=model_path,
        python_executable=worker_python,
        device_preference=LOCAL_MODEL_DEVICE_CUDA,
        options={"timeout_seconds": timeout, "local_files_only": "true"},
    )
    document_ocr_tool.load_advanced_ocr_consent = lambda: consent
    document_ocr_tool.load_local_model_runtime_config = lambda: config


def wait_for_completion(
    app: PDFToolkitApp,
    tool: Any,
    recorder: MessageRecorder,
    output_dir: Path,
    *,
    timeout_seconds: float,
    cancel_after_seconds: float | None = None,
) -> None:
    started = time.monotonic()
    saw_running = False
    cancelled = False
    while time.monotonic() - started < timeout_seconds:
        app.update()
        tool._poll_queue()
        if str(tool.cancel_btn["state"]) == "normal":
            saw_running = True
        if (
            cancel_after_seconds is not None
            and not cancelled
            and time.monotonic() - started >= cancel_after_seconds
        ):
            tool._cancel()
            cancelled = True
        if saw_running and not is_running(tool):
            return
        if recorder.messages and not is_running(tool):
            return
        if (
            str(tool.start_btn["state"]) == "normal"
            and not is_running(tool)
            and has_output_files(output_dir)
        ):
            return
        time.sleep(0.05)
    raise TimeoutError("Document OCR GUI smoke runner timed out.")


def is_running(tool: Any) -> bool:
    return str(tool.cancel_btn["state"]) == "normal"


def has_output_files(output_dir: Path) -> bool:
    return any(
        path.suffix.lower() in {".txt", ".md"}
        for path in output_dir.glob("*")
    )


def print_summary(tool: Any, recorder: MessageRecorder, output_dir: Path) -> None:
    outputs = sorted(
        path
        for path in output_dir.glob("*")
        if path.suffix.lower() in {".txt", ".md"}
    )
    print(f"status={tool.status_lbl.cget('text')}")
    print(f"progress={tool.progress['value']}")
    print(f"start_state={tool.start_btn['state']}")
    print(f"cancel_state={tool.cancel_btn['state']}")
    print(f"message_count={len(recorder.messages)}")
    for level, title, message in recorder.messages:
        print(f"message={level}:{title}:{sanitize_message(message)}")
    print(f"output_count={len(outputs)}")
    for output in outputs:
        text = output.read_text(encoding="utf-8")
        print(
            f"output={output.suffix.lstrip('.')};bytes={output.stat().st_size};"
            f"page_markers={text.count('Page ')}"
        )


def sanitize_message(message: str) -> str:
    return " ".join(str(message).split())


def create_output_dir(mode: str) -> Path:
    root = Path(tempfile.gettempdir()) / "pdf_toolkit_gui_smoke"
    return root / f"out_{mode}_{int(time.time())}"


def create_sample_image() -> Path:
    root = Path(tempfile.gettempdir()) / "pdf_toolkit_gui_smoke"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "sample_image.png"
    image = Image.new("RGB", (640, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 90), "Unified PDF Toolkit GUI OCR smoke", fill="black")
    image.save(path)
    return path


def create_unsupported_input() -> Path:
    root = Path(tempfile.gettempdir()) / "pdf_toolkit_gui_smoke"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "unsupported_input.txt"
    path.write_text("not a supported OCR input", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
