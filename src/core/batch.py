"""Headless batch execution shared by the GUI and command-line interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

import fitz

from ..utils.errors import friendly_error_message
from ..utils.file_ops import resolve_output_path
from ..utils.workflow import WorkflowReport
from .processor import BatchProcessor


COMPRESS = "Compress PDF/Image"
PDF_TO_IMAGES = "PDF to Images"
PDF_TO_WORD_TEXT = "PDF to Word - Text Only"
PDF_TO_WORD_IMAGES = "PDF to Word - Page Images"
PDF_TO_WORD_OCR = "PDF to Word - OCR Text"

SUPPORTED_OPERATIONS = (
    COMPRESS,
    PDF_TO_IMAGES,
    PDF_TO_WORD_TEXT,
    PDF_TO_WORD_IMAGES,
    PDF_TO_WORD_OCR,
)

OPERATION_ALIASES = {
    "compress": COMPRESS,
    "compress-pdf-image": COMPRESS,
    "pdf-to-images": PDF_TO_IMAGES,
    "pdf-to-word-text": PDF_TO_WORD_TEXT,
    "pdf-to-word-images": PDF_TO_WORD_IMAGES,
    "pdf-to-word-ocr": PDF_TO_WORD_OCR,
}


def normalize_operation(value: str) -> str:
    """Return a stable display operation for a CLI alias or GUI operation name."""
    operation = str(value).strip()
    if operation in SUPPORTED_OPERATIONS:
        return operation
    normalized = OPERATION_ALIASES.get(operation.casefold())
    if normalized:
        return normalized
    choices = ", ".join(sorted(OPERATION_ALIASES))
    raise ValueError(f"Unsupported batch operation: {operation!r}. Use one of: {choices}.")


@dataclass(frozen=True)
class BatchJob:
    """One serializable headless batch operation."""

    source: str
    operation: str
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BatchJob":
        """Validate and construct a job loaded from a JSON manifest."""
        if not isinstance(value, Mapping):
            raise ValueError("Each manifest job must be a JSON object.")
        source = value.get("source")
        operation = value.get("operation")
        options = value.get("options", {})
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Each manifest job requires a non-empty string 'source'.")
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("Each manifest job requires a non-empty string 'operation'.")
        if not isinstance(options, dict):
            raise ValueError("Manifest job 'options' must be a JSON object.")
        return cls(source=source, operation=normalize_operation(operation), options=dict(options))


class HeadlessBatchRunner:
    """Run mixed PDF Toolkit jobs without creating a Tk window."""

    @classmethod
    def run_jobs(
        cls,
        jobs: Iterable[BatchJob],
        output_dir: str,
        *,
        conflict_policy: str = "rename",
        cancellation_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_on_error: bool = False,
    ) -> dict[str, Any]:
        job_list = list(jobs)
        if not isinstance(conflict_policy, str):
            raise ValueError("Conflict policy must be a string.")
        policy = conflict_policy.casefold()
        if policy not in {"rename", "overwrite", "skip"}:
            raise ValueError("Conflict policy must be one of: rename, overwrite, skip.")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        report = WorkflowReport(
            "Batch Queue",
            output_dir,
            options={"conflict_policy": policy, "jobs": len(job_list)},
        )
        result: dict[str, Any] = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "cancelled": False,
        }
        processor = BatchProcessor()

        for index, job in enumerate(job_list, start=1):
            if cancellation_check and cancellation_check():
                result["cancelled"] = True
                report.add(job.source, status="cancelled", message="Cancelled before job.")
                break
            failed_this_job = False
            try:
                operation = normalize_operation(job.operation)
                if progress_callback:
                    progress_callback(
                        index - 1,
                        len(job_list),
                        f"Running {index}/{len(job_list)}: {operation}",
                    )
                outputs = cls.run_single_job(job, output_dir, processor, policy)
                if not outputs:
                    result["skipped"] += 1
                    report.add(job.source, status="skipped", message="No output generated.")
                else:
                    result["success"] += 1
                    report.add(job.source, "; ".join(outputs), message=operation)
            except Exception as exc:
                failed_this_job = True
                result["failed"] += 1
                report.add(job.source, status="failed", message=friendly_error_message(exc))
            if progress_callback:
                progress_callback(index, len(job_list), f"Finished {index}/{len(job_list)}")
            if cancellation_check and cancellation_check():
                result["cancelled"] = True
                break
            if failed_this_job and stop_on_error:
                break

        result["report_path"] = report.write()
        return result

    @classmethod
    def run_single_job(
        cls,
        job: BatchJob,
        output_dir: str,
        processor: BatchProcessor,
        conflict_policy: str,
    ) -> list[str]:
        """Execute one validated job and return every generated output path."""
        source_path = Path(job.source)
        if not source_path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {job.source}")
        operation = normalize_operation(job.operation)
        if operation == COMPRESS:
            result = processor.process_files(
                [job.source],
                output_dir,
                str(job.options.get("compression_level", "Medium")),
                compression_options={
                    "optimize_images": True,
                    "lossless_only": False,
                    "max_image_dimension": None,
                    "jpeg_quality": None,
                },
                conflict_policy=conflict_policy,
            )
            outputs = [
                record.get("output", "")
                for record in result.get("records", [])
                if record.get("status") == "success" and record.get("output")
            ]
            if result.get("failed"):
                raise RuntimeError("; ".join(result.get("errors", [])) or "Compression failed.")
            return outputs

        if operation == PDF_TO_IMAGES:
            return cls.convert_pdf_to_images(
                job.source,
                output_dir,
                int(job.options.get("dpi", 150)),
                str(job.options.get("format", "png")),
                str(job.options.get("page_range", "")),
                conflict_policy,
            )

        if operation.startswith("PDF to Word"):
            # Imported lazily so compression-only headless runs do not load Tk modules.
            from ..tools.pdf2word.tool import PDFToWordTool

            if operation == PDF_TO_WORD_TEXT:
                mode = "Text Only"
            elif operation == PDF_TO_WORD_IMAGES:
                mode = "Page Images"
            else:
                mode = "OCR Text"
            ocr_dpi = int(job.options.get("ocr_dpi", 200))
            ocr_preprocess = str(job.options.get("ocr_preprocess", "Grayscale"))
            if operation == PDF_TO_WORD_OCR:
                if not 100 <= ocr_dpi <= 600:
                    raise ValueError("OCR DPI must be between 100 and 600.")
                if ocr_preprocess not in {
                    "None",
                    "Grayscale",
                    "Auto Contrast",
                    "Threshold",
                }:
                    raise ValueError(
                        "OCR preprocessing must be None, Grayscale, Auto Contrast, or Threshold."
                    )
            output_path = resolve_output_path(
                str(Path(output_dir) / f"{Path(job.source).stem}.docx"),
                conflict_policy,
            )
            if output_path is None:
                return []
            PDFToWordTool.convert_pdf_to_docx(
                job.source,
                output_path,
                range_text=str(job.options.get("page_range", "")),
                mode=mode,
                ocr_lang=str(job.options.get("ocr_lang", "eng")),
                ocr_dpi=ocr_dpi,
                ocr_preprocess=ocr_preprocess,
            )
            return [output_path]

        raise ValueError(f"Unsupported batch operation: {operation}")

    @staticmethod
    def convert_pdf_to_images(
        input_path: str,
        output_dir: str,
        dpi: int,
        fmt: str,
        range_text: str = "",
        conflict_policy: str = "rename",
    ) -> list[str]:
        """Render selected PDF pages while closing the source document deterministically."""
        from ..tools.pdf2word.tool import PDFToWordTool

        normalized_format = fmt.casefold()
        if normalized_format not in {"png", "jpg", "jpeg"}:
            raise ValueError("Image format must be one of: png, jpg, jpeg.")
        if not 72 <= dpi <= 600:
            raise ValueError("DPI must be between 72 and 600.")

        page_indices = PDFToWordTool.parse_page_range(range_text, input_path)
        outputs: list[str] = []
        with fitz.open(input_path) as document:
            selected = page_indices if page_indices is not None else list(range(document.page_count))
            for page_index in selected:
                pixmap = document[page_index].get_pixmap(dpi=dpi)
                requested = (
                    Path(output_dir)
                    / f"{Path(input_path).stem}_page_{page_index + 1}.{normalized_format}"
                )
                output_path = resolve_output_path(str(requested), conflict_policy)
                if output_path is None:
                    continue
                pixmap.save(output_path)
                outputs.append(output_path)
        return outputs
