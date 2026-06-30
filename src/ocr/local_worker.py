"""Local model worker-process controller for OCR runtime tests.

This module uses only the Python standard library. It does not import AI
runtimes, download models, or run real OCR in the app process. The fake worker
path is deterministic test scaffolding. The Unlimited-OCR worker path is an
explicit subprocess boundary for experimental local inference.
"""

from __future__ import annotations

import json
import os
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


def default_unlimited_ocr_worker_script_path() -> str:
    """Return the repo-local experimental Unlimited-OCR worker script path."""

    return str(Path(__file__).with_name("workers") / "unlimited_ocr_worker.py")


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


def build_unlimited_ocr_worker_payload(
    request_data: OcrRequest,
    *,
    model_id: str,
    model_path: str,
    runtime_mode: str,
    device_preference: str,
    page_image_paths: list[Path],
    options: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build an explicit real-worker payload with temporary page image paths only."""

    page_numbers = list(request_data.page_numbers) or list(
        range(1, len(request_data.images) + 1)
    )
    return {
        "request_id": "local-unlimited-ocr-worker",
        "provider": "baidu",
        "model_id": model_id,
        "model_path": model_path,
        "runtime": runtime_mode,
        "device_preference": device_preference,
        "prompt": request_data.prompt,
        "pages": [
            {
                "page_number": int(page_number),
                "image_index": index,
                "image_path": str(page_image_paths[index]),
            }
            for index, page_number in enumerate(page_numbers)
        ],
        "options": _safe_worker_options(options),
    }


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

    response = _run_json_worker_process(
        executable=executable,
        script_path=script_path,
        payload=payload,
        timeout_seconds=timeout_seconds,
        cancellation_check=cancellation_check,
    )
    return _parse_worker_response(
        response,
        request_data=request_data,
        expected_page_numbers=[page["page_number"] for page in payload["pages"]],
    )


def run_unlimited_ocr_worker_process(
    request_data: OcrRequest,
    *,
    model_id: str,
    model_path: str,
    runtime_mode: str,
    device_preference: str,
    python_executable: str | None = None,
    worker_script_path: str | None = None,
    timeout_seconds: float = DEFAULT_WORKER_TIMEOUT_SECONDS,
    options: Mapping[str, str] | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> OcrResult:
    """Run experimental local Unlimited-OCR in a killable one-shot worker."""

    executable = python_executable or sys.executable
    script_path = worker_script_path or default_unlimited_ocr_worker_script_path()
    page_numbers = list(request_data.page_numbers) or list(
        range(1, len(request_data.images) + 1)
    )
    if len(page_numbers) != len(request_data.images):
        raise OcrBackendUnavailableError(
            "Local AI OCR worker request has invalid page metadata."
        )
    if cancellation_check and cancellation_check():
        raise OcrBackendUnavailableError("Local AI OCR worker process was cancelled.")

    import tempfile

    with tempfile.TemporaryDirectory(prefix="pdf_toolkit_unlimited_worker_") as tmpdir:
        temp_root = Path(tmpdir)
        page_dir = temp_root / "pages"
        child_temp_root = temp_root / "worker_tmp"
        page_dir.mkdir()
        child_temp_root.mkdir()
        page_image_paths: list[Path] = []
        for index, image in enumerate(request_data.images, start=1):
            image_path = page_dir / f"page_{index:04d}.png"
            image.save(image_path, format="PNG")
            page_image_paths.append(image_path)
        payload = build_unlimited_ocr_worker_payload(
            request_data,
            model_id=model_id,
            model_path=model_path,
            runtime_mode=runtime_mode,
            device_preference=device_preference,
            page_image_paths=page_image_paths,
            options=options,
        )
        response = _run_json_worker_process(
            executable=executable,
            script_path=script_path,
            payload=payload,
            timeout_seconds=timeout_seconds,
            cancellation_check=cancellation_check,
            env_updates={
                "PDF_TOOLKIT_UNLIMITED_OCR_TMP_ROOT": str(child_temp_root),
            },
        )
        return _parse_worker_response(
            response,
            request_data=request_data,
            expected_page_numbers=[
                page["page_number"] for page in payload["pages"]
            ],
        )


def _run_json_worker_process(
    *,
    executable: str,
    script_path: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
    cancellation_check: Callable[[], bool] | None = None,
    env_updates: Mapping[str, str] | None = None,
) -> Any:
    env = None
    if env_updates:
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in env_updates.items()})
    try:
        process = subprocess.Popen(
            [executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
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
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise OcrBackendUnavailableError(
            "Local AI OCR worker process returned invalid JSON."
        ) from exc


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
