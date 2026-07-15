"""Standalone tasks executed only inside the private Unlimited-OCR runtime."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Sequence

RESULT_PREFIX = "PDF_TOOLKIT_RESULT="


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Private Unlimited-OCR runtime tasks")
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser("download")
    download.add_argument("--model-id", required=True)
    download.add_argument("--revision", required=True)
    download.add_argument("--cache-dir", required=True)
    download.add_argument("--local-dir", required=True)
    download.add_argument("--allow-pattern", action="append", default=[])

    probe = sub.add_parser("probe")
    probe.add_argument("--require-cuda", action="store_true")

    for name in ("load", "ocr", "benchmark"):
        task = sub.add_parser(name)
        task.add_argument("--model-path", required=True)
        task.add_argument("--revision", required=True)
        task.add_argument("--device", choices=("cuda",), default="cuda")
        if name in {"ocr", "benchmark"}:
            task.add_argument("--image", required=True)
            task.add_argument("--output-dir", required=True)
            task.add_argument("--expected-term", action="append", default=[])
    return parser.parse_args(argv)


def _emit(value: dict[str, Any]) -> None:
    print(f"{RESULT_PREFIX}{json.dumps(value, ensure_ascii=True, sort_keys=True)}", flush=True)


def _download(args: argparse.Namespace) -> dict[str, Any]:
    from huggingface_hub import snapshot_download

    local_dir = Path(args.local_dir).resolve()
    local_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    path = snapshot_download(
        repo_id=args.model_id,
        revision=args.revision,
        cache_dir=str(Path(args.cache_dir).resolve()),
        local_dir=str(local_dir),
        allow_patterns=args.allow_pattern or None,
        etag_timeout=30,
        max_workers=4,
    )
    return {
        "task": "download",
        "success": True,
        "model_path": str(Path(path).resolve()),
        "revision": args.revision,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def _probe(args: argparse.Namespace) -> dict[str, Any]:
    import torch

    cuda_available = bool(torch.cuda.is_available())
    devices = []
    if cuda_available:
        for index in range(torch.cuda.device_count()):
            devices.append(
                {
                    "index": index,
                    "name": torch.cuda.get_device_name(index),
                    "compute_capability": ".".join(
                        map(str, torch.cuda.get_device_capability(index))
                    ),
                }
            )
    if args.require_cuda and not cuda_available:
        raise RuntimeError("Private PyTorch runtime cannot access CUDA.")
    packages = {}
    for name in (
        "torch",
        "torchvision",
        "transformers",
        "Pillow",
        "matplotlib",
        "einops",
        "addict",
        "easydict",
        "PyMuPDF",
        "psutil",
        "huggingface-hub",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "task": "probe",
        "success": True,
        "python": sys.version,
        "executable": sys.executable,
        "packages": packages,
        "torch_cuda_version": torch.version.cuda,
        "cuda_available": cuda_available,
        "cudnn_version": (
            torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None
        ),
        "devices": devices,
    }


def _validate_model_path(model_path: str, revision: str) -> Path:
    path = Path(model_path).resolve()
    required = ("config.json", "model-00001-of-000001.safetensors")
    missing = [name for name in required if not (path / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Pinned model snapshot is incomplete: {', '.join(missing)}")
    manifest = path / ".pdf-toolkit-manifest.json"
    if manifest.exists():
        value = json.loads(manifest.read_text(encoding="utf-8"))
        if value.get("revision") != revision:
            raise RuntimeError("Model manifest revision does not match the requested revision.")
    return path


def _load_model(model_path: Path, revision: str) -> tuple[Any, Any, Any, float]:
    import torch
    from transformers import AutoModel, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required by the managed Unlimited-OCR runtime.")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            revision=revision,
            trust_remote_code=True,
            local_files_only=True,
        )
        model = AutoModel.from_pretrained(
            str(model_path),
            revision=revision,
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=torch.bfloat16,
            local_files_only=True,
        )
        model = model.eval().cuda()
    return torch, tokenizer, model, time.perf_counter() - started


def _load(args: argparse.Namespace) -> dict[str, Any]:
    model_path = _validate_model_path(args.model_path, args.revision)
    torch, _tokenizer, model, elapsed = _load_model(model_path, args.revision)
    result = {
        "task": "load",
        "success": True,
        "revision": args.revision,
        "load_seconds": round(elapsed, 3),
        "peak_vram_bytes": int(torch.cuda.max_memory_allocated()),
        "gpu": torch.cuda.get_device_name(torch.cuda.current_device()),
    }
    del model
    torch.cuda.empty_cache()
    return result


def _recognize(args: argparse.Namespace, *, benchmark: bool) -> dict[str, Any]:
    model_path = _validate_model_path(args.model_path, args.revision)
    image = Path(args.image).resolve()
    if not image.is_file():
        raise FileNotFoundError("OCR test image was not found.")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    torch, tokenizer, model, load_seconds = _load_model(model_path, args.revision)
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
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            returned = model.infer(
                tokenizer,
                prompt="<image>document parsing.",
                image_file=str(image),
                output_path=str(output_dir),
                base_size=1024,
                image_size=640,
                crop_mode=True,
                max_length=32768,
                no_repeat_ngram_size=35,
                ngram_window=128,
                save_results=True,
            )
    finally:
        stop.set()
        sampler.join(timeout=1)
    inference_seconds = time.perf_counter() - started
    text = _find_output_text(returned, output_dir)
    normalized_text = _normalize_for_comparison(text)
    expected_terms = [str(term) for term in args.expected_term]
    matched_terms = [
        term for term in expected_terms if _normalize_for_comparison(term) in normalized_text
    ]
    match_ratio = len(matched_terms) / len(expected_terms) if expected_terms else None
    functional_success = bool(text.strip()) and (
        match_ratio is None or match_ratio >= 0.5
    )
    result = {
        "task": "benchmark" if benchmark else "ocr",
        "success": functional_success,
        "revision": args.revision,
        "load_seconds": round(load_seconds, 3),
        "inference_seconds": round(inference_seconds, 3),
        "peak_ram_bytes": int(peak_ram),
        "peak_vram_bytes": int(torch.cuda.max_memory_allocated()),
        "output_characters": len(text),
        "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "output_preview": text[:240] if os.environ.get("PDF_TOOLKIT_OCR_DEBUG_OUTPUT") == "1" else "",
        "expected_term_count": len(expected_terms),
        "matched_terms": matched_terms,
        "expected_term_match_ratio": (
            round(match_ratio, 4) if match_ratio is not None else None
        ),
    }
    if benchmark:
        total_vram = int(
            torch.cuda.get_device_properties(torch.cuda.current_device()).total_memory
        )
        result.update(
            {
                "classification": _benchmark_classification(
                    inference_seconds,
                    int(result["peak_vram_bytes"]),
                    total_vram,
                ),
                "backend": "transformers",
                "model_revision": args.revision,
                "dependency_versions": _dependency_versions(),
                "total_vram_bytes": total_vram,
            }
        )
    del model
    torch.cuda.empty_cache()
    return result


def _dependency_versions() -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for name in (
        "torch",
        "torchvision",
        "transformers",
        "Pillow",
        "PyMuPDF",
        "psutil",
    ):
        try:
            values[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            values[name] = None
    return values


def _benchmark_classification(
    seconds: float,
    peak_vram: int,
    total_vram: int,
) -> str:
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


def _find_output_text(returned: Any, output_dir: Path) -> str:
    if isinstance(returned, str):
        return returned
    if isinstance(returned, dict) and isinstance(returned.get("text"), str):
        return returned["text"]
    values = []
    for path in sorted(output_dir.rglob("*")):
        if (
            path.suffix.casefold() in {".txt", ".md"}
            and path.is_file()
            and not path.is_symlink()
        ):
            values.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(values)


def _normalize_for_comparison(value: str) -> str:
    return "".join(value.casefold().split())


def run(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "download":
            result = _download(args)
        elif args.command == "probe":
            result = _probe(args)
        elif args.command == "load":
            result = _load(args)
        elif args.command == "ocr":
            result = _recognize(args, benchmark=False)
        else:
            result = _recognize(args, benchmark=True)
    except Exception as exc:
        _emit(
            {
                "task": args.command,
                "success": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        return 1
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
