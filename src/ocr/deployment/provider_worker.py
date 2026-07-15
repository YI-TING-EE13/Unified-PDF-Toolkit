"""Persistent JSON-lines worker for the private Unlimited-OCR runtime."""

from __future__ import annotations

import contextlib
import importlib.metadata
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

try:
    from .runtime_tasks import _load_model, _validate_model_path
except ImportError:  # Executed as a standalone file by the private Python runtime.
    from runtime_tasks import _load_model, _validate_model_path

_MAX_OUTPUT_CHARACTERS = 16 * 1024 * 1024
_MAX_PROMPT_CHARACTERS = 4096


class Worker:
    def __init__(self) -> None:
        self.torch: Any = None
        self.tokenizer: Any = None
        self.model: Any = None
        self.model_path: Path | None = None
        self.revision: str | None = None
        self.model_root = Path(os.environ["PDF_TOOLKIT_OCR_MODEL_ROOT"]).resolve()
        self.session_root = Path(os.environ["PDF_TOOLKIT_OCR_SESSION_ROOT"]).resolve()

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        command = request.get("command")
        if command == "health":
            return self.health()
        if command == "load":
            return self.load(str(request.get("model_path", "")), str(request.get("revision", "")))
        if command == "recognize":
            return self.recognize(request)
        if command == "benchmark":
            return self.benchmark(request)
        if command == "unload":
            self.unload()
            return {"success": True, "loaded": False}
        if command == "shutdown":
            self.unload()
            return {"success": True, "shutdown": True}
        raise ValueError(f"Unknown worker command: {command}")

    def health(self) -> dict[str, Any]:
        import torch

        return {
            "success": True,
            "pid": os.getpid(),
            "loaded": self.model is not None,
            "revision": self.revision,
            "cuda_available": bool(torch.cuda.is_available()),
            "torch_version": torch.__version__,
            "torch_cuda_version": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "allocated_vram_bytes": (
                int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0
            ),
        }

    def load(self, model_path: str, revision: str) -> dict[str, Any]:
        path = _validate_model_path(str(self._allowed_model_path(model_path)), revision)
        if self.model is not None and path == self.model_path and revision == self.revision:
            return {"success": True, "loaded": True, "reused": True, "revision": revision}
        self.unload()
        self.torch, self.tokenizer, self.model, elapsed = _load_model(path, revision)
        self.model_path = path
        self.revision = revision
        return {
            "success": True,
            "loaded": True,
            "reused": False,
            "revision": revision,
            "load_seconds": round(elapsed, 3),
            "peak_vram_bytes": int(self.torch.cuda.max_memory_allocated()),
        }

    def recognize(self, request: dict[str, Any]) -> dict[str, Any]:
        self._require_loaded()
        image_paths = [self._allowed_session_file(str(value)) for value in request.get("images", [])]
        if not image_paths:
            raise ValueError("At least one managed session image is required.")
        output_dir = self._allowed_session_path(str(request.get("output_dir", "")))
        output_dir.mkdir(parents=True, exist_ok=True)
        options = request.get("options") if isinstance(request.get("options"), dict) else {}
        started = time.perf_counter()
        self.torch.cuda.reset_peak_memory_stats()
        with contextlib.redirect_stdout(sys.stderr):
            returned = self._infer(image_paths, output_dir, options)
        texts = _collect_outputs(returned, output_dir)
        return {
            "success": bool(texts),
            "texts": texts,
            "combined_multi_page": len(image_paths) > 1 and len(texts) == 1,
            "inference_seconds": round(time.perf_counter() - started, 3),
            "peak_vram_bytes": int(self.torch.cuda.max_memory_allocated()),
        }

    def benchmark(self, request: dict[str, Any]) -> dict[str, Any]:
        import psutil

        process = psutil.Process()
        peak_ram = process.memory_info().rss
        stop = threading.Event()

        def sample_memory() -> None:
            nonlocal peak_ram
            while not stop.wait(0.05):
                try:
                    peak_ram = max(peak_ram, process.memory_info().rss)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return

        sampler = threading.Thread(target=sample_memory, daemon=True)
        sampler.start()
        try:
            result = self.recognize(request)
        finally:
            stop.set()
            sampler.join(timeout=1)
        result.update(
            {
                "peak_ram_bytes": peak_ram,
                "classification": _benchmark_classification(
                    float(result.get("inference_seconds", 9999)),
                    int(result.get("peak_vram_bytes", 0)),
                    int(self.torch.cuda.get_device_properties(0).total_memory),
                ),
                "backend": "transformers",
                "model_revision": self.revision,
                "dependency_versions": _dependency_versions(),
            }
        )
        result.pop("texts", None)
        return result

    def _infer(self, image_paths: list[Path], output_dir: Path, options: dict[str, Any]) -> Any:
        max_length = _bounded_int(options.get("max_length"), 32768, 1024, 32768)
        prompt = str(options.get("prompt", "<image>document parsing."))
        if len(prompt) > _MAX_PROMPT_CHARACTERS:
            raise ValueError("OCR prompt exceeds the managed worker safety limit.")
        if len(image_paths) == 1:
            return self.model.infer(
                self.tokenizer,
                prompt=prompt,
                image_file=str(image_paths[0]),
                output_path=str(output_dir),
                base_size=1024,
                image_size=640,
                crop_mode=True,
                max_length=max_length,
                no_repeat_ngram_size=35,
                ngram_window=128,
                save_results=True,
            )
        if not hasattr(self.model, "infer_multi"):
            raise RuntimeError("Pinned model does not expose infer_multi.")
        return self.model.infer_multi(
            self.tokenizer,
            prompt=(
                prompt
                if "prompt" in options
                else "<image>Multi page parsing."
            ),
            image_files=[str(path) for path in image_paths],
            output_path=str(output_dir),
            image_size=1024,
            max_length=max_length,
            no_repeat_ngram_size=35,
            ngram_window=1024,
            save_results=True,
        )

    def unload(self) -> None:
        self.model = None
        self.tokenizer = None
        if self.torch is not None and self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()
        self.torch = None
        self.model_path = None
        self.revision = None

    def _require_loaded(self) -> None:
        if self.model is None:
            raise RuntimeError("Model is not loaded.")

    def _allowed_model_path(self, value: str) -> Path:
        return _require_child(Path(value).resolve(), self.model_root, require_file=False)

    def _allowed_session_path(self, value: str) -> Path:
        return _require_child(Path(value).resolve(), self.session_root, require_file=False)

    def _allowed_session_file(self, value: str) -> Path:
        return _require_child(Path(value).resolve(), self.session_root, require_file=True)


def _require_child(path: Path, root: Path, *, require_file: bool) -> Path:
    if path == root or root not in path.parents:
        raise PermissionError("Worker path is outside the managed root.")
    if require_file and (not path.is_file() or path.is_symlink()):
        raise FileNotFoundError("Managed worker input is not a regular file.")
    return path


def _collect_outputs(returned: Any, output_dir: Path) -> list[str]:
    if isinstance(returned, str):
        return _bounded_output_texts([returned])
    if isinstance(returned, (list, tuple)):
        return _bounded_output_texts(
            [item for item in returned if isinstance(item, str) and item]
        )
    if isinstance(returned, dict):
        pages = returned.get("pages")
        if isinstance(pages, list):
            return _bounded_output_texts(
                [
                    str(page.get("text", ""))
                    for page in pages
                    if isinstance(page, dict) and page.get("text")
                ]
            )
        if isinstance(returned.get("text"), str):
            return _bounded_output_texts([returned["text"]])
    resolved_root = output_dir.resolve()
    values = []
    for path in sorted(output_dir.rglob("*")):
        try:
            if path.is_symlink() or path.suffix.casefold() not in {".txt", ".md"}:
                continue
            resolved = path.resolve()
            if resolved == resolved_root or resolved_root not in resolved.parents:
                continue
            if not resolved.is_file():
                continue
            remaining = _MAX_OUTPUT_CHARACTERS - sum(len(value) for value in values)
            if remaining <= 0:
                raise ValueError("OCR output exceeds the managed worker safety limit.")
            with resolved.open("r", encoding="utf-8", errors="replace") as handle:
                value = handle.read(remaining + 1)
            if len(value) > remaining:
                raise ValueError("OCR output exceeds the managed worker safety limit.")
            if value:
                values.append(value)
        except OSError:
            continue
    return values


def _bounded_output_texts(values: list[str]) -> list[str]:
    total = sum(len(value) for value in values)
    if total > _MAX_OUTPUT_CHARACTERS:
        raise ValueError("OCR output exceeds the managed worker safety limit.")
    return values


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(max(int(value), minimum), maximum)
    except (TypeError, ValueError):
        return default


def _dependency_versions() -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for name in ("torch", "torchvision", "transformers", "Pillow", "PyMuPDF", "psutil"):
        try:
            values[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            values[name] = None
    return values


def _benchmark_classification(seconds: float, peak_vram: int, total_vram: int) -> str:
    ratio = peak_vram / total_vram if total_vram else 1.0
    if ratio >= 0.95:
        return "EASILY_OOM"
    if seconds <= 5 and ratio < 0.85:
        return "REAL_TIME_SUITABLE"
    if seconds <= 20 and ratio < 0.9:
        return "GENERAL_OCR_SUITABLE"
    if seconds <= 90:
        return "USABLE_BUT_SLOW"
    return "LOCAL_USE_NOT_RECOMMENDED"


def main() -> int:
    try:
        worker = Worker()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "id": None,
                    "error": {
                        "type": type(exc).__name__,
                        "message": "Managed worker environment is incomplete.",
                    },
                },
                ensure_ascii=True,
            ),
            flush=True,
        )
        return 2
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            result = worker.dispatch(request)
            response = {"id": request_id, "result": result}
        except Exception as exc:
            response = {
                "id": request_id,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        print(json.dumps(response, ensure_ascii=True), flush=True)
        if response.get("result", {}).get("shutdown"):
            return 0
    worker.unload()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
