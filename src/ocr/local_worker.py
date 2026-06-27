"""Local model worker-process controller for fake/dev OCR runtime tests.

This module uses only the Python standard library. It does not import AI
runtimes, download models, or run real OCR. The current worker path is intended
only for deterministic fake worker subprocess tests.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from .exceptions import OcrBackendUnavailableError
from .models import OcrEngine, OcrPageResult, OcrRequest, OcrResult

DEFAULT_WORKER_TIMEOUT_SECONDS = 10.0
FORBIDDEN_OPTION_TOKENS = (
    "source",
    "path",
    "ocr_text",
    "image",
    "base64",
    "document",
    "content",
)


def default_fake_worker_script_path() -> str:
    """Return the repo-local fake worker script path."""

    return str(Path(__file__).with_name("workers") / "fake_local_model_worker.py")


def build_local_model_worker_payload(
    request_data: OcrRequest,
    *,
    model_id: str,
    runtime_mode: str,
    options: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build a sanitized worker payload.

    The payload intentionally excludes source paths, OCR text, image bytes,
    base64 payloads, and document content. It contains only page metadata and
    backend/runtime hints needed by the fake worker contract.
    """

    page_numbers = list(request_data.page_numbers) or list(
        range(1, len(request_data.images) + 1)
    )
    return {
        "request_id": "local-model-fake-worker",
        "provider": "baidu",
        "model_id": model_id,
        "runtime": runtime_mode,
        "prompt": request_data.prompt,
        "pages": [
            {"page_number": int(page_number), "image_index": index}
            for index, page_number in enumerate(page_numbers)
        ],
        "options": _safe_worker_options(options),
    }


def _safe_worker_options(options: Mapping[str, str] | None) -> Dict[str, str]:
    safe: Dict[str, str] = {}
    for key, value in (options or {}).items():
        key_text = str(key)
        normalized = key_text.lower()
        if any(token in normalized for token in FORBIDDEN_OPTION_TOKENS):
            continue
        safe[key_text] = str(value)
    return safe


def run_local_model_worker_process(
    request_data: OcrRequest,
    *,
    model_id: str,
    runtime_mode: str,
    python_executable: str | None = None,
    worker_script_path: str | None = None,
    timeout_seconds: float = DEFAULT_WORKER_TIMEOUT_SECONDS,
    options: Mapping[str, str] | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> OcrResult:
    """Run the configured fake local model worker once and parse the response."""

    executable = python_executable or sys.executable
    script_path = worker_script_path or default_fake_worker_script_path()
    payload = build_local_model_worker_payload(
        request_data,
        model_id=model_id,
        runtime_mode=runtime_mode,
        options=options,
    )
    if cancellation_check and cancellation_check():
        raise OcrBackendUnavailableError("Local AI OCR worker process was cancelled.")

    try:
        process = subprocess.Popen(
            [executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        raise OcrBackendUnavailableError(
            "Local AI OCR worker process could not be started."
        ) from exc

    try:
        assert process.stdin is not None
        process.stdin.write(json.dumps(payload))
        process.stdin.close()
        process.stdin = None
    except OSError as exc:
        _terminate_worker(process)
        _close_worker_pipes(process)
        raise OcrBackendUnavailableError(
            "Local AI OCR worker process could not receive the request."
        ) from exc

    deadline = time.monotonic() + max(timeout_seconds, 0.01)
    cancelled = cancellation_check or (lambda: False)
    while process.poll() is None:
        if cancelled():
            _terminate_worker(process)
            _close_worker_pipes(process)
            raise OcrBackendUnavailableError(
                "Local AI OCR worker process was cancelled."
            )
        if time.monotonic() >= deadline:
            _terminate_worker(process)
            _close_worker_pipes(process)
            raise OcrBackendUnavailableError(
                "Local AI OCR worker process timed out."
            )
        time.sleep(0.01)

    stdout = process.stdout.read() if process.stdout is not None else ""
    _ = process.stderr.read() if process.stderr is not None else ""
    _close_worker_pipes(process)
    if process.returncode != 0:
        raise OcrBackendUnavailableError("Local AI OCR worker process failed.")
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise OcrBackendUnavailableError(
            "Local AI OCR worker process returned invalid JSON."
        ) from exc
    return _parse_worker_response(
        response,
        request_data=request_data,
        expected_page_numbers=[page["page_number"] for page in payload["pages"]],
    )


def _terminate_worker(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)


def _close_worker_pipes(process: subprocess.Popen[str]) -> None:
    for pipe_name in ("stdin", "stdout", "stderr"):
        pipe = getattr(process, pipe_name)
        if pipe is not None and not pipe.closed:
            pipe.close()


def _parse_worker_response(
    response: Any,
    *,
    request_data: OcrRequest,
    expected_page_numbers: list[int],
) -> OcrResult:
    if not isinstance(response, dict):
        raise OcrBackendUnavailableError(
            "Local AI OCR worker process returned an invalid response."
        )
    pages = response.get("pages")
    if not isinstance(pages, list) or len(pages) != len(expected_page_numbers):
        raise OcrBackendUnavailableError(
            "Local AI OCR worker process returned an invalid page response."
        )

    parsed_pages: list[OcrPageResult] = []
    for expected_page, page in zip(expected_page_numbers, pages):
        if not isinstance(page, dict):
            raise OcrBackendUnavailableError(
                "Local AI OCR worker process returned an invalid page response."
            )
        page_number = page.get("page_number")
        text = page.get("text")
        confidence = page.get("confidence")
        warnings = page.get("warnings", [])
        if page_number != expected_page or not isinstance(text, str):
            raise OcrBackendUnavailableError(
                "Local AI OCR worker process returned an invalid page response."
            )
        if confidence is not None and not isinstance(confidence, (int, float)):
            raise OcrBackendUnavailableError(
                "Local AI OCR worker process returned an invalid page response."
            )
        if not isinstance(warnings, list) or not all(
            isinstance(item, str) for item in warnings
        ):
            raise OcrBackendUnavailableError(
                "Local AI OCR worker process returned an invalid page response."
            )
        parsed_pages.append(
            OcrPageResult(
                page_number=int(page_number),
                text=text,
                confidence=float(confidence) if confidence is not None else None,
                warnings=list(warnings),
            )
        )

    metadata = response.get("metadata", {})
    if not isinstance(metadata, dict):
        raise OcrBackendUnavailableError(
            "Local AI OCR worker process returned an invalid response."
        )
    return OcrResult(
        engine=OcrEngine.LOCAL_MODEL,
        pages=parsed_pages,
        source_path=request_data.source_path,
        warnings=[],
        metadata=dict(metadata),
    )
