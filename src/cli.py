"""Command-line and unattended batch entry point for Unified PDF Toolkit."""

from __future__ import annotations

import argparse
import json
import signal
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Sequence

from .core.batch import (
    COMPRESS,
    PDF_TO_IMAGES,
    PDF_TO_WORD_IMAGES,
    PDF_TO_WORD_OCR,
    PDF_TO_WORD_TEXT,
    BatchJob,
    HeadlessBatchRunner,
)
from .utils.workflow import CancellationToken


def _package_version() -> str:
    try:
        return version("pdf-toolkit")
    except PackageNotFoundError:
        return "development"


def _bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"value must be between {minimum} and {maximum}, got {number}"
            )
        return number

    return parse


def _add_execution_options(parser: argparse.ArgumentParser, *, output_required: bool) -> None:
    parser.add_argument(
        "-o",
        "--output-dir",
        required=output_required,
        help="Folder for generated files and workflow reports.",
    )
    parser.add_argument(
        "--conflict",
        choices=("rename", "overwrite", "skip"),
        default=None,
        help="Existing-output policy (default: rename, or the manifest value).",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop before the next job after the first failed job.",
    )
    parser.add_argument("--json", action="store_true", help="Write the final result as JSON.")
    parser.add_argument("--quiet", action="store_true", help="Hide progress messages.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-toolkit",
        description="Run Unified PDF Toolkit without opening the graphical interface.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_package_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("batch", help="Run jobs from a reusable JSON manifest.")
    manifest.add_argument("manifest", help="Path to a JSON manifest containing a jobs array.")
    _add_execution_options(manifest, output_required=False)

    compress = subparsers.add_parser("compress", help="Compress PDF, image, or text files.")
    compress.add_argument("sources", nargs="+", help="Input files.")
    compress.add_argument(
        "--level",
        choices=("Low", "Medium", "High"),
        default="Medium",
        help="Compression level (default: Medium).",
    )
    _add_execution_options(compress, output_required=True)

    images = subparsers.add_parser("pdf-to-images", help="Render PDF pages as image files.")
    images.add_argument("sources", nargs="+", help="Input PDF files.")
    images.add_argument("--dpi", type=_bounded_int(72, 600), default=150, metavar="72..600")
    images.add_argument("--format", choices=("png", "jpg", "jpeg"), default="png")
    images.add_argument("--pages", default="", help="Page range such as 1-3,5 (default: all).")
    _add_execution_options(images, output_required=True)

    word = subparsers.add_parser("pdf-to-word", help="Convert PDF files to DOCX.")
    word.add_argument("sources", nargs="+", help="Input PDF files.")
    word.add_argument(
        "--mode",
        choices=("text", "page-images", "ocr"),
        default="text",
        help="Conversion mode (default: text).",
    )
    word.add_argument("--pages", default="", help="Page range such as 1-3,5 (default: all).")
    word.add_argument("--ocr-lang", default="eng", help="Tesseract language expression.")
    word.add_argument(
        "--ocr-dpi",
        type=_bounded_int(100, 600),
        default=200,
        metavar="100..600",
    )
    word.add_argument(
        "--ocr-preprocess",
        choices=("None", "Grayscale", "Auto Contrast", "Threshold"),
        default="Grayscale",
    )
    _add_execution_options(word, output_required=True)
    return parser


def _manifest_jobs(path: Path) -> tuple[list[BatchJob], dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON manifest at line {exc.lineno}, column {exc.colno}.") from exc

    if isinstance(payload, list):
        raw_jobs = payload
        settings: dict[str, Any] = {}
    elif isinstance(payload, dict):
        raw_jobs = payload.get("jobs")
        settings = payload
    else:
        raise ValueError("Manifest must be a jobs array or an object containing a jobs array.")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise ValueError("Manifest must contain at least one job.")

    jobs = [BatchJob.from_mapping(value) for value in raw_jobs]
    base_dir = path.resolve().parent
    resolved = []
    for job in jobs:
        source = Path(job.source).expanduser()
        if not source.is_absolute():
            source = base_dir / source
        resolved.append(BatchJob(str(source.resolve()), job.operation, job.options))
    return resolved, settings


def _jobs_from_args(args: argparse.Namespace) -> tuple[list[BatchJob], str, str]:
    if args.command == "batch":
        manifest_path = Path(args.manifest).expanduser().resolve()
        jobs, settings = _manifest_jobs(manifest_path)
        configured_output = args.output_dir or settings.get("output_dir")
        if not isinstance(configured_output, str) or not configured_output.strip():
            raise ValueError("Provide --output-dir or a non-empty manifest 'output_dir'.")
        output_path = Path(configured_output).expanduser()
        if not output_path.is_absolute() and args.output_dir is None:
            output_path = manifest_path.parent / output_path
        manifest_policy = settings.get("conflict_policy", "rename")
        conflict_policy = args.conflict or manifest_policy
        if not isinstance(conflict_policy, str) or conflict_policy not in {
            "rename",
            "overwrite",
            "skip",
        }:
            raise ValueError("Manifest conflict_policy must be rename, overwrite, or skip.")
        return jobs, str(output_path.resolve()), conflict_policy

    sources = [str(Path(source).expanduser().resolve()) for source in args.sources]
    if args.command == "compress":
        jobs = [BatchJob(source, COMPRESS, {"compression_level": args.level}) for source in sources]
    elif args.command == "pdf-to-images":
        jobs = [
            BatchJob(
                source,
                PDF_TO_IMAGES,
                {"dpi": args.dpi, "format": args.format, "page_range": args.pages},
            )
            for source in sources
        ]
    else:
        operations = {
            "text": PDF_TO_WORD_TEXT,
            "page-images": PDF_TO_WORD_IMAGES,
            "ocr": PDF_TO_WORD_OCR,
        }
        jobs = [
            BatchJob(
                source,
                operations[args.mode],
                {
                    "page_range": args.pages,
                    "ocr_lang": args.ocr_lang,
                    "ocr_dpi": args.ocr_dpi,
                    "ocr_preprocess": args.ocr_preprocess,
                },
            )
            for source in sources
        ]
    return jobs, str(Path(args.output_dir).expanduser().resolve()), args.conflict or "rename"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        jobs, output_dir, conflict_policy = _jobs_from_args(args)
        token = CancellationToken()
        interrupt_count = 0

        def request_cancel(_signum: int, _frame: Any) -> None:
            nonlocal interrupt_count
            interrupt_count += 1
            if interrupt_count > 1:
                raise KeyboardInterrupt
            token.cancel()
            print("Cancellation requested; stopping before the next job.", file=sys.stderr)

        previous_sigint = None
        if hasattr(signal, "SIGINT"):
            previous_sigint = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, request_cancel)

        def progress(_index: int, _total: int, message: str) -> None:
            if not args.quiet:
                print(message, file=sys.stderr)

        try:
            result = HeadlessBatchRunner.run_jobs(
                jobs,
                output_dir,
                conflict_policy=conflict_policy,
                cancellation_check=token.is_cancelled,
                progress_callback=progress,
                stop_on_error=args.stop_on_error,
            )
        finally:
            if previous_sigint is not None:
                signal.signal(signal.SIGINT, previous_sigint)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(
                f"Complete: {result['success']} succeeded, {result['failed']} failed, "
                f"{result['skipped']} skipped."
            )
            print(f"Report: {result['report_path']}")
        if result["cancelled"]:
            return 130
        return 1 if result["failed"] else 0
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
