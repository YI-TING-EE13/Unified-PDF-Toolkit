"""Reusable advanced OCR workflow helpers for future UI wiring.

The future production advanced OCR direction is a user-owned local model
runtime. The endpoint path in this module remains mock-only by default and
requires an injected transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

import fitz
from PIL import Image

from .base import OcrBackend
from .consent import AdvancedOcrConsent, require_valid_consent
from .exceptions import (
    OcrBackendUnavailableError,
    OcrConsentRequiredError,
    OcrDependencyMissingError,
    OcrError,
)
from .local_endpoint import (
    EndpointTransport,
    LOCAL_ENDPOINT_MODEL_ID,
    LOCAL_ENDPOINT_PROVIDER,
    LocalEndpointOcrBackend,
)
from .local_model import (
    LOCAL_MODEL_MODEL_ID,
    LOCAL_MODEL_PROVIDER,
    LocalModelOcrBackend,
    LocalModelRuntimeConfig,
)
from .models import OcrEngine, OcrRequest, OcrResult
from .unlimited_fake import (
    UNLIMITED_OCR_MODEL_ID,
    UNLIMITED_OCR_PROVIDER,
    FakeUnlimitedOcrBackend,
)
from ..utils.file_ops import resolve_output_path
from ..utils.workflow import get_conflict_policy

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
SUPPORTED_OUTPUT_FORMATS = {"txt", "md"}
DEFAULT_ADVANCED_OCR_PROMPT = "developer fake document parsing."


class AdvancedOcrBackendChoice(str, Enum):
    """Safe backend choices for mock-only advanced OCR workflow wiring."""

    FAKE_UNLIMITED = "fake_unlimited"
    LOCAL_MODEL_FUTURE = "local_model_future"
    LOCAL_ENDPOINT_MOCK = "local_endpoint_mock"


@dataclass(frozen=True)
class AdvancedOcrBackendSelection:
    """Backend selection data for future advanced OCR UI flows."""

    choice: AdvancedOcrBackendChoice
    endpoint_url: str | None = None
    transport: EndpointTransport | None = None
    local_model_config: LocalModelRuntimeConfig | None = None


@dataclass(frozen=True)
class AdvancedOcrOutput:
    """One local output written by an advanced OCR workflow."""

    source: str
    path: str
    format: str


@dataclass(frozen=True)
class AdvancedOcrWorkflowResult:
    """Summary returned by workflow helpers without OCR text."""

    outputs: List[AdvancedOcrOutput] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def success_count(self) -> int:
        return len({output.source for output in self.outputs})


def fake_backend_selection() -> AdvancedOcrBackendSelection:
    """Return the developer/test fake backend selection."""

    return AdvancedOcrBackendSelection(AdvancedOcrBackendChoice.FAKE_UNLIMITED)


def local_model_future_selection(
    *,
    config: LocalModelRuntimeConfig | None = None,
) -> AdvancedOcrBackendSelection:
    """Return the future local model selection.

    This selection creates only the safe scaffold backend. It does not import AI
    runtimes, download models, or run real inference.
    """

    return AdvancedOcrBackendSelection(
        AdvancedOcrBackendChoice.LOCAL_MODEL_FUTURE,
        local_model_config=config,
    )


def local_endpoint_mock_selection(
    *,
    endpoint_url: str,
    transport: EndpointTransport,
) -> AdvancedOcrBackendSelection:
    """Return a mock-only local endpoint selection.

    A transport is required so tests can inject deterministic behavior without
    performing live network calls.
    """

    return AdvancedOcrBackendSelection(
        AdvancedOcrBackendChoice.LOCAL_ENDPOINT_MOCK,
        endpoint_url=endpoint_url,
        transport=transport,
    )


def provider_model_for_selection(
    selection: AdvancedOcrBackendSelection,
) -> tuple[str, str]:
    """Return provider/model identifiers required for consent validation."""

    if selection.choice == AdvancedOcrBackendChoice.FAKE_UNLIMITED:
        return UNLIMITED_OCR_PROVIDER, UNLIMITED_OCR_MODEL_ID
    if selection.choice == AdvancedOcrBackendChoice.LOCAL_MODEL_FUTURE:
        return LOCAL_MODEL_PROVIDER, LOCAL_MODEL_MODEL_ID
    if selection.choice == AdvancedOcrBackendChoice.LOCAL_ENDPOINT_MOCK:
        return LOCAL_ENDPOINT_PROVIDER, LOCAL_ENDPOINT_MODEL_ID
    raise OcrBackendUnavailableError("Unsupported advanced OCR backend selection.")


def require_consent_for_selection(
    consent: AdvancedOcrConsent | None,
    selection: AdvancedOcrBackendSelection,
) -> None:
    """Validate consent for the selected advanced OCR backend."""

    provider, model_id = provider_model_for_selection(selection)
    require_valid_consent(consent, provider=provider, model_id=model_id)


def create_backend_for_selection(
    selection: AdvancedOcrBackendSelection,
    *,
    consent: AdvancedOcrConsent | None,
) -> OcrBackend:
    """Create a backend for the selected mock-safe workflow path."""

    require_consent_for_selection(consent, selection)
    if selection.choice == AdvancedOcrBackendChoice.FAKE_UNLIMITED:
        return FakeUnlimitedOcrBackend(consent=consent)
    if selection.choice == AdvancedOcrBackendChoice.LOCAL_MODEL_FUTURE:
        return LocalModelOcrBackend(
            consent=consent,
            config=selection.local_model_config,
        )
    if selection.choice == AdvancedOcrBackendChoice.LOCAL_ENDPOINT_MOCK:
        if selection.transport is None:
            raise OcrBackendUnavailableError(
                "Local endpoint workflow requires a mocked transport in this milestone."
            )
        return LocalEndpointOcrBackend(
            endpoint_url=selection.endpoint_url or "",
            consent=consent,
            transport=selection.transport,
        )
    raise OcrBackendUnavailableError("Unsupported advanced OCR backend selection.")


def normalise_output_formats(formats: Iterable[str]) -> List[str]:
    """Validate and normalize requested local output formats."""

    selected: List[str] = []
    for output_format in formats:
        value = output_format.lower().lstrip(".")
        if value not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output format: {output_format}")
        if value not in selected:
            selected.append(value)
    if not selected:
        raise ValueError("Select at least one output format.")
    return selected


def render_pdf_pages(path: Path) -> tuple[List[Image.Image], List[int]]:
    """Render PDF pages to in-memory RGB images."""

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


def load_input_images(path: Path) -> tuple[List[Image.Image], List[int]]:
    """Load a PDF or image file as in-memory OCR page images."""

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return render_pdf_pages(path)
    if suffix in SUPPORTED_IMAGE_EXTENSIONS:
        with Image.open(path) as image:
            return [image.convert("RGB").copy()], [1]
    raise ValueError(f"Unsupported input type: {path.suffix or path.name}")


def text_output(source_name: str, result: OcrResult) -> str:
    """Build deterministic TXT output content."""

    lines = [
        "Developer-only fake AI OCR output",
        "No real Unlimited-OCR inference was performed.",
        f"Source: {source_name}",
        "",
    ]
    for page in result.pages:
        lines.extend([f"Page {page.page_number}", page.text, ""])
    return "\n".join(lines).rstrip() + "\n"


def markdown_output(source_name: str, result: OcrResult) -> str:
    """Build deterministic Markdown output content."""

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


def write_ocr_outputs(
    output_dir: Path,
    source_name: str,
    result: OcrResult,
    formats: Iterable[str],
    *,
    filename_suffix: str = "fake_ai_ocr",
) -> List[AdvancedOcrOutput]:
    """Write OCR text to user-selected local outputs only."""

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
            markdown_output(source_name, result)
            if output_format == "md"
            else text_output(source_name, result)
        )
        Path(output_path).write_text(content, encoding="utf-8")
        outputs.append(
            AdvancedOcrOutput(source=source_name, path=output_path, format=output_format)
        )
    return outputs


def user_safe_ocr_error_message(exc: Exception) -> str:
    """Map backend/workflow failures to user-safe messages."""

    if isinstance(exc, OcrConsentRequiredError):
        return "Advanced OCR consent is required before this backend can run."
    if isinstance(exc, OcrDependencyMissingError):
        return "The selected OCR backend is missing an optional dependency."
    if isinstance(exc, OcrBackendUnavailableError):
        detail = str(exc)
        if "cancelled" in detail.lower():
            return "The selected OCR backend was cancelled."
        if "worker is busy" in detail:
            return "The local OCR worker is busy. Wait for the current OCR job to finish and try again."
        if "Local Unlimited-OCR model path is not configured" in detail:
            return "The local Unlimited-OCR model path is not configured."
        if "Local Unlimited-OCR model path was not found" in detail:
            return "The configured local Unlimited-OCR model path was not found."
        if "Local Unlimited-OCR worker Python executable is not configured" in detail:
            return "The local Unlimited-OCR worker Python executable is not configured."
        if "Local Unlimited-OCR worker Python executable was not found" in detail:
            return "The configured local Unlimited-OCR worker Python executable was not found."
        if "CUDA" in detail or "GPU" in detail or "VRAM" in detail:
            return "The local AI OCR runtime could not use the requested GPU/CUDA device."
        if "Local AI OCR model" in detail:
            return "The local AI OCR model runtime is not installed or configured."
        if "timed out" in detail:
            return "The selected OCR backend timed out."
        if "connection failed" in detail or "request failed" in detail:
            return "The selected OCR backend is unavailable."
        if "response" in detail or "JSON" in detail or "page" in detail:
            return "The selected OCR backend returned an invalid response."
        return "The selected OCR backend is unavailable."
    if isinstance(exc, ValueError) and str(exc).startswith("Unsupported input type"):
        return str(exc)
    if isinstance(exc, OcrError):
        return "The selected OCR backend failed."
    return "Advanced OCR workflow failed."


def run_advanced_ocr_workflow(
    files: Sequence[str],
    output_dir: str,
    formats: Iterable[str],
    *,
    selection: AdvancedOcrBackendSelection,
    consent: AdvancedOcrConsent | None,
    cancellation_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> AdvancedOcrWorkflowResult:
    """Run a mock-safe advanced OCR workflow and write local output files."""

    selected_formats = normalise_output_formats(formats)
    backend = create_backend_for_selection(selection, consent=consent)
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
                source_path=str(source),
                page_numbers=page_numbers,
                prompt=DEFAULT_ADVANCED_OCR_PROMPT,
            )
            result = backend.recognize(request)
            written = write_ocr_outputs(output_root, source_name, result, selected_formats)
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
