"""Document OCR workflow helpers for production and experimental UI paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

from .base import OcrBackend
from .consent import AdvancedOcrConsent
from .exceptions import OcrBackendUnavailableError
from .local_model import (
    LOCAL_MODEL_MODE_WORKER_PROCESS,
    LocalModelOcrBackend,
    LocalModelRuntimeConfig,
)
from .models import OcrEngine, OcrRequest, OcrResult
from .registry import get_backend
from .workflow import (
    AdvancedOcrOutput,
    AdvancedOcrWorkflowResult,
    load_input_images,
    normalise_output_formats,
    user_safe_ocr_error_message,
)
from ..utils.file_ops import resolve_output_path
from ..utils.workflow import get_conflict_policy

DOCUMENT_OCR_BACKEND_TESSERACT = "tesseract"
DOCUMENT_OCR_BACKEND_LOCAL_UNLIMITED_WORKER = "local_unlimited_worker"


@dataclass(frozen=True)
class DocumentOcrBackendConfig:
    """Backend config for the user-facing Document OCR workflow."""

    backend: str = DOCUMENT_OCR_BACKEND_TESSERACT
    display_name: str = "Tesseract OCR"
    tesseract_language: str = "eng"
    local_model_config: LocalModelRuntimeConfig | None = None


@dataclass(frozen=True)
class DocumentOcrRunSummary:
    """Small, text-free summary useful for status displays and tests."""

    page_count: int = 0
    backend: str = DOCUMENT_OCR_BACKEND_TESSERACT
    warnings: List[str] = field(default_factory=list)


def tesseract_document_backend_config(
    *,
    language: str = "eng",
) -> DocumentOcrBackendConfig:
    """Return the default production Document OCR backend config."""

    return DocumentOcrBackendConfig(
        backend=DOCUMENT_OCR_BACKEND_TESSERACT,
        display_name="Tesseract OCR",
        tesseract_language=language or "eng",
    )


def local_unlimited_worker_backend_config(
    config: LocalModelRuntimeConfig,
) -> DocumentOcrBackendConfig:
    """Return the experimental local Unlimited-OCR worker backend config."""

    if config.mode != LOCAL_MODEL_MODE_WORKER_PROCESS:
        raise OcrBackendUnavailableError(
            "Experimental Local Unlimited-OCR requires worker_process runtime mode."
        )
    return DocumentOcrBackendConfig(
        backend=DOCUMENT_OCR_BACKEND_LOCAL_UNLIMITED_WORKER,
        display_name="Experimental Local Unlimited-OCR (worker process)",
        local_model_config=config,
    )


def create_document_ocr_backend(
    config: DocumentOcrBackendConfig,
    *,
    consent: AdvancedOcrConsent | None = None,
) -> OcrBackend:
    """Create the selected OCR backend without importing heavy AI runtimes."""

    if config.backend == DOCUMENT_OCR_BACKEND_TESSERACT:
        return get_backend(OcrEngine.TESSERACT)
    if config.backend == DOCUMENT_OCR_BACKEND_LOCAL_UNLIMITED_WORKER:
        if config.local_model_config is None:
            raise OcrBackendUnavailableError(
                "Experimental Local Unlimited-OCR runtime is not configured."
            )
        if config.local_model_config.mode != LOCAL_MODEL_MODE_WORKER_PROCESS:
            raise OcrBackendUnavailableError(
                "Experimental Local Unlimited-OCR requires worker_process runtime mode."
            )
        return LocalModelOcrBackend(
            consent=consent,
            config=config.local_model_config,
        )
    raise OcrBackendUnavailableError("Unsupported Document OCR backend selection.")


def document_text_output(
    source_name: str,
    result: OcrResult,
    *,
    backend_label: str,
) -> str:
    """Build deterministic TXT output content without source paths."""

    lines = [
        "Document OCR output",
        f"Backend: {backend_label}",
        f"Source: {source_name}",
        "",
    ]
    for page in result.pages:
        lines.extend([f"Page {page.page_number}", page.text, ""])
    return "\n".join(lines).rstrip() + "\n"


def document_markdown_output(
    source_name: str,
    result: OcrResult,
    *,
    backend_label: str,
) -> str:
    """Build deterministic Markdown output content without source paths."""

    lines = [
        "# Document OCR Output",
        "",
        f"- Backend: {backend_label}",
        f"- Source: `{source_name}`",
        "",
    ]
    for page in result.pages:
        lines.extend([f"## Page {page.page_number}", "", page.text, ""])
    return "\n".join(lines).rstrip() + "\n"


def write_document_ocr_outputs(
    output_dir: Path,
    source_name: str,
    result: OcrResult,
    formats: Iterable[str],
    *,
    backend_label: str,
    filename_suffix: str = "document_ocr",
) -> List[AdvancedOcrOutput]:
    """Write OCR text only to user-selected local output files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[AdvancedOcrOutput] = []
    for output_format in normalise_output_formats(formats):
        requested = output_dir / (
            f"{source_name.rsplit('.', 1)[0]}_{filename_suffix}.{output_format}"
        )
        output_path = resolve_output_path(str(requested), get_conflict_policy())
        if output_path is None:
            continue
        content = (
            document_markdown_output(source_name, result, backend_label=backend_label)
            if output_format == "md"
            else document_text_output(source_name, result, backend_label=backend_label)
        )
        Path(output_path).write_text(content, encoding="utf-8")
        outputs.append(
            AdvancedOcrOutput(source=source_name, path=output_path, format=output_format)
        )
    return outputs


def run_document_ocr_workflow(
    files: Sequence[str],
    output_dir: str,
    formats: Iterable[str],
    *,
    backend_config: DocumentOcrBackendConfig,
    consent: AdvancedOcrConsent | None = None,
    cancellation_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> AdvancedOcrWorkflowResult:
    """Run Document OCR and write local TXT/Markdown outputs."""

    selected_formats = normalise_output_formats(formats)
    backend = create_document_ocr_backend(backend_config, consent=consent)
    is_cancelled = cancellation_check or (lambda: False)
    output_root = Path(output_dir)
    outputs: List[AdvancedOcrOutput] = []
    failed: List[str] = []
    skipped: List[str] = []
    total = len(files)

    for index, file_path in enumerate(files, start=1):
        if is_cancelled():
            return AdvancedOcrWorkflowResult(
                outputs=outputs, failed=failed, skipped=skipped, cancelled=True
            )

        source = Path(file_path)
        source_name = source.name
        if progress_callback:
            progress_callback(index - 1, total, f"Preparing {source_name}")

        try:
            images, page_numbers = load_input_images(source)
            request = OcrRequest(
                engine=backend.engine,
                images=images,
                source_path=(
                    str(source)
                    if backend_config.backend == DOCUMENT_OCR_BACKEND_TESSERACT
                    else None
                ),
                page_numbers=page_numbers,
                language=backend_config.tesseract_language,
            )
            result = backend.recognize(request)
            written = write_document_ocr_outputs(
                output_root,
                source_name,
                result,
                selected_formats,
                backend_label=backend_config.display_name,
            )
            outputs.extend(written)
            written_formats = {output.format for output in written}
            skipped.extend(
                f"{source_name}.{output_format}"
                for output_format in selected_formats
                if output_format not in written_formats
            )
        except Exception as exc:
            failed.append(f"{source_name}: {user_safe_ocr_error_message(exc)}")

        if progress_callback:
            progress_callback(index, total, f"Processed {source_name}")

    return AdvancedOcrWorkflowResult(outputs=outputs, failed=failed, skipped=skipped)
