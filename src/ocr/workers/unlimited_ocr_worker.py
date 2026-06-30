"""One-shot experimental local Unlimited-OCR worker process.

The worker reads a sanitized JSON request from stdin and writes a JSON response
to stdout. It imports optional AI runtime dependencies only after it starts, and
it does not log OCR text, image bytes, source document paths, or local model
paths by default.
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from src.ocr.local_model import (  # noqa: E402
    LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
    LOCAL_MODEL_MODEL_ID,
    LocalModelRuntimeConfig,
)
from src.ocr.models import OcrEngine, OcrRequest  # noqa: E402
from src.ocr.unlimited_ocr_local import run_unlimited_ocr_local  # noqa: E402


class _NullTextSink:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


def main() -> int:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError:
        return _write_error("invalid_request", "Worker received invalid JSON.", 2)

    try:
        response = _handle_request(request)
    except WorkerInputError as exc:
        return _write_error("invalid_request", str(exc), 2)
    except Exception:
        return _write_error(
            "worker_failed",
            "Local Unlimited-OCR worker failed. Check optional runtime, GPU, and model configuration.",
            1,
        )

    print(json.dumps(response, ensure_ascii=True))
    return 0


def _handle_request(request: Mapping[str, Any]) -> dict[str, Any]:
    model_path = _required_text(request, "model_path", "Model path is not configured.")
    pages = request.get("pages")
    if not isinstance(pages, list) or not pages:
        raise WorkerInputError("Worker request has invalid pages.")

    images: list[Image.Image] = []
    page_numbers: list[int] = []
    for page in pages:
        if not isinstance(page, dict):
            raise WorkerInputError("Worker request has invalid pages.")
        page_number = page.get("page_number")
        image_path = page.get("image_path")
        if not isinstance(page_number, int) or not isinstance(image_path, str):
            raise WorkerInputError("Worker request has invalid pages.")
        path = Path(image_path)
        if not path.exists():
            raise WorkerInputError("Worker request page image was not found.")
        with Image.open(path) as image:
            images.append(image.convert("RGB").copy())
        page_numbers.append(page_number)

    config = LocalModelRuntimeConfig(
        enabled=True,
        mode=LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
        model_id=str(request.get("model_id") or LOCAL_MODEL_MODEL_ID),
        model_path=model_path,
        device_preference=str(request.get("device_preference") or "auto"),
        options=_safe_options(request.get("options")),
    )
    ocr_request = OcrRequest(
        engine=OcrEngine.LOCAL_MODEL,
        images=images,
        source_path=None,
        page_numbers=page_numbers,
        prompt=request.get("prompt") if isinstance(request.get("prompt"), str) else None,
    )
    sink = _NullTextSink()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        result = run_unlimited_ocr_local(ocr_request, config=config)

    return {
        "request_id": request.get("request_id"),
        "pages": [
            {
                "page_number": page.page_number,
                "text": page.text,
                "confidence": page.confidence,
                "warnings": page.warnings,
            }
            for page in result.pages
        ],
        "warnings": result.warnings,
        "metadata": {
            "provider": result.metadata.get("provider", "baidu"),
            "model_id": result.metadata.get("model_id", LOCAL_MODEL_MODEL_ID),
            "runtime": "worker_process",
            "backend": "transformers_worker",
            "device": result.metadata.get("device"),
            "real_inference": True,
        },
    }


def _required_text(request: Mapping[str, Any], key: str, message: str) -> str:
    value = request.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkerInputError(message)
    if key == "model_path" and not Path(value).exists():
        raise WorkerInputError("Model path was not found.")
    return value


def _safe_options(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    return {str(key): str(item) for key, item in value.items()}


def _write_error(code: str, message: str, exit_code: int) -> int:
    print(
        json.dumps(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "retryable": False,
                }
            },
            ensure_ascii=True,
        )
    )
    return exit_code


class WorkerInputError(Exception):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
