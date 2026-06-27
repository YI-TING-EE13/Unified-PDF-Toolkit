"""Experimental local Baidu Unlimited-OCR runner.

This module intentionally keeps torch/transformers imports inside the invoked
runtime path. It does not download models automatically and does not run at app
startup.
"""

from __future__ import annotations

import importlib
import importlib.util
import contextlib
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .exceptions import OcrBackendUnavailableError, OcrDependencyMissingError
from .models import OcrEngine, OcrPageResult, OcrRequest, OcrResult

DEFAULT_UNLIMITED_OCR_PROMPT = "<image>document parsing."
DEFAULT_UNLIMITED_OCR_MULTI_PROMPT = "<image>Multi page parsing."
DEFAULT_MAX_LENGTH = 32768
DEFAULT_SINGLE_IMAGE_SIZE = 640
DEFAULT_SINGLE_BASE_SIZE = 1024
DEFAULT_MULTI_IMAGE_SIZE = 1024
DEFAULT_NO_REPEAT_NGRAM_SIZE = 35
DEFAULT_SINGLE_NGRAM_WINDOW = 128
DEFAULT_MULTI_NGRAM_WINDOW = 1024


def run_unlimited_ocr_local(request_data: OcrRequest, *, config: Any) -> OcrResult:
    """Run experimental local Unlimited-OCR inference.

    The caller must validate consent first. This function validates local model
    configuration, lazily imports optional AI dependencies, writes only
    temporary page images, and returns sanitized OCR results.
    """

    model_path = _required_existing_model_path(getattr(config, "model_path", None))
    torch_module, transformers_module = _load_optional_runtime()
    device = _resolve_device(
        torch_module,
        getattr(config, "device_preference", "auto"),
    )

    image_paths: list[Path] = []
    page_numbers = list(request_data.page_numbers) or list(
        range(1, len(request_data.images) + 1)
    )
    if len(page_numbers) != len(request_data.images):
        raise OcrBackendUnavailableError(
            "Local Unlimited-OCR request has invalid page metadata."
        )

    with tempfile.TemporaryDirectory(prefix="pdf_toolkit_unlimited_ocr_") as tmpdir:
        temp_root = Path(tmpdir)
        image_dir = temp_root / "pages"
        output_dir = temp_root / "output"
        image_dir.mkdir()
        output_dir.mkdir()
        for index, image in enumerate(request_data.images, start=1):
            image_path = image_dir / f"page_{index:04d}.png"
            image.save(image_path, format="PNG")
            image_paths.append(image_path)

        try:
            with _suppress_model_console_output():
                tokenizer, model = _load_model(
                    transformers_module,
                    torch_module,
                    model_path,
                    local_files_only=_bool_option(
                        getattr(config, "options", None),
                        "local_files_only",
                        default=True,
                    ),
                )
                model = _move_model_to_device(model, device)
                returned = _run_model_inference(
                    model,
                    tokenizer,
                    image_paths=image_paths,
                    output_dir=output_dir,
                    options=getattr(config, "options", None),
                )
            texts = _collect_text_outputs(
                returned,
                output_dir=output_dir,
                expected_pages=len(image_paths),
            )
        except OcrDependencyMissingError:
            raise
        except OcrBackendUnavailableError:
            raise
        except Exception as exc:
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR inference failed. Check optional runtime, GPU, and model configuration."
            ) from exc

    pages = [
        OcrPageResult(
            page_number=int(page_number),
            text=text,
            confidence=None,
            warnings=[],
        )
        for page_number, text in zip(page_numbers, texts)
    ]
    warnings = []
    if device == "cpu":
        warnings.append("Local Unlimited-OCR ran on CPU; this may be very slow.")
    return OcrResult(
        engine=OcrEngine.LOCAL_MODEL,
        pages=pages,
        source_path=request_data.source_path,
        warnings=warnings,
        metadata={
            "provider": "baidu",
            "model_id": getattr(config, "model_id", "baidu/Unlimited-OCR"),
            "runtime": "local_unlimited_ocr",
            "backend": "transformers",
            "device": device,
            "real_inference": True,
        },
    )


class _NullTextSink:
    """Drop model console output so OCR text is not logged by default."""

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


def _suppress_model_console_output() -> contextlib.ExitStack:
    sink = _NullTextSink()
    stack = contextlib.ExitStack()
    stack.enter_context(contextlib.redirect_stdout(sink))
    stack.enter_context(contextlib.redirect_stderr(sink))
    return stack


def _required_existing_model_path(value: str | None) -> str:
    if not value:
        raise OcrBackendUnavailableError(
            "Local Unlimited-OCR model path is not configured."
        )
    path = Path(value)
    if not path.exists():
        raise OcrBackendUnavailableError(
            "Local Unlimited-OCR model path was not found."
        )
    return str(path)


def _load_optional_runtime() -> tuple[Any, Any]:
    if importlib.util.find_spec("torch") is None:
        raise OcrDependencyMissingError(
            "Optional dependency torch is required for local Unlimited-OCR."
        )
    if importlib.util.find_spec("transformers") is None:
        raise OcrDependencyMissingError(
            "Optional dependency transformers is required for local Unlimited-OCR."
        )
    try:
        torch_module = importlib.import_module("torch")
        transformers_module = importlib.import_module("transformers")
    except ImportError as exc:
        raise OcrDependencyMissingError(
            "Optional local Unlimited-OCR runtime dependencies could not be imported."
        ) from exc
    return torch_module, transformers_module


def _resolve_device(torch_module: Any, preference: str) -> str:
    value = (preference or "auto").lower()
    cuda_available = bool(torch_module.cuda.is_available())
    if value == "cuda":
        if not cuda_available:
            raise OcrBackendUnavailableError(
                "Local Unlimited-OCR CUDA device is not available."
            )
        return "cuda"
    if value == "cpu":
        return "cpu"
    return "cuda" if cuda_available else "cpu"


def _load_model(
    transformers_module: Any,
    torch_module: Any,
    model_path: str,
    *,
    local_files_only: bool,
) -> tuple[Any, Any]:
    tokenizer = transformers_module.AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        local_files_only=local_files_only,
    )
    model = transformers_module.AutoModel.from_pretrained(
        model_path,
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=getattr(torch_module, "bfloat16", None),
        local_files_only=local_files_only,
    )
    return tokenizer, model


def _move_model_to_device(model: Any, device: str) -> Any:
    if hasattr(model, "eval"):
        model = model.eval()
    if device == "cuda" and hasattr(model, "cuda"):
        return model.cuda()
    if hasattr(model, "to"):
        return model.to(device)
    return model


def _run_model_inference(
    model: Any,
    tokenizer: Any,
    *,
    image_paths: list[Path],
    output_dir: Path,
    options: Mapping[str, str] | None,
) -> Any:
    if len(image_paths) == 1 and hasattr(model, "infer"):
        return model.infer(
            tokenizer,
            prompt=str(_option(options, "prompt", DEFAULT_UNLIMITED_OCR_PROMPT)),
            image_file=str(image_paths[0]),
            output_path=str(output_dir),
            base_size=_int_option(options, "base_size", DEFAULT_SINGLE_BASE_SIZE),
            image_size=_int_option(options, "image_size", DEFAULT_SINGLE_IMAGE_SIZE),
            crop_mode=_bool_option(options, "crop_mode", default=True),
            max_length=_int_option(options, "max_length", DEFAULT_MAX_LENGTH),
            no_repeat_ngram_size=_int_option(
                options, "no_repeat_ngram_size", DEFAULT_NO_REPEAT_NGRAM_SIZE
            ),
            ngram_window=_int_option(
                options, "ngram_window", DEFAULT_SINGLE_NGRAM_WINDOW
            ),
            save_results=True,
        )
    if not hasattr(model, "infer_multi"):
        raise OcrBackendUnavailableError(
            "Local Unlimited-OCR model does not expose the expected inference API."
        )
    return model.infer_multi(
        tokenizer,
        prompt=str(_option(options, "multi_prompt", DEFAULT_UNLIMITED_OCR_MULTI_PROMPT)),
        image_files=[str(path) for path in image_paths],
        output_path=str(output_dir),
        image_size=_int_option(options, "multi_image_size", DEFAULT_MULTI_IMAGE_SIZE),
        max_length=_int_option(options, "max_length", DEFAULT_MAX_LENGTH),
        no_repeat_ngram_size=_int_option(
            options, "no_repeat_ngram_size", DEFAULT_NO_REPEAT_NGRAM_SIZE
        ),
        ngram_window=_int_option(options, "multi_ngram_window", DEFAULT_MULTI_NGRAM_WINDOW),
        save_results=True,
    )


def _collect_text_outputs(
    returned: Any,
    *,
    output_dir: Path,
    expected_pages: int,
) -> list[str]:
    texts = _texts_from_return_value(returned)
    if not texts:
        files = sorted(
            path
            for path in output_dir.rglob("*")
            if path.suffix.lower() in {".txt", ".md"}
        )
        texts = [path.read_text(encoding="utf-8") for path in files]
    if not texts:
        raise OcrBackendUnavailableError(
            "Local Unlimited-OCR did not produce readable OCR output."
        )
    if len(texts) == 1 and expected_pages > 1:
        return texts
    if len(texts) != expected_pages:
        raise OcrBackendUnavailableError(
            "Local Unlimited-OCR returned an unexpected number of page results."
        )
    return texts


def _texts_from_return_value(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        pages = value.get("pages")
        if isinstance(pages, list):
            return [
                page.get("text", "")
                for page in pages
                if isinstance(page, dict) and isinstance(page.get("text"), str)
            ]
        text = value.get("text")
        if isinstance(text, str):
            return [text]
    return []


def _option(options: Mapping[str, str] | None, key: str, default: Any) -> Any:
    return (options or {}).get(key, default)


def _int_option(options: Mapping[str, str] | None, key: str, default: int) -> int:
    try:
        return int(_option(options, key, default))
    except (TypeError, ValueError):
        return default


def _bool_option(
    options: Mapping[str, str] | None,
    key: str,
    *,
    default: bool,
) -> bool:
    value = _option(options, key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
