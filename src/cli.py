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

    ocr = subparsers.add_parser(
        "ocr",
        help="Inspect, plan, install, validate, or remove managed Unlimited-OCR.",
    )
    ocr_subparsers = ocr.add_subparsers(dest="ocr_command", required=True)
    for name, help_text in (
        ("inspect", "Collect a read-only hardware and software environment report."),
        ("plan", "Evaluate compatibility and print the exact consent-bound setup plan."),
        ("status", "Show managed runtime, model cache, journal, and provider health status."),
    ):
        command = ocr_subparsers.add_parser(name, help=help_text)
        command.add_argument("--output", help="Optional UTF-8 JSON output file.")
        command.add_argument("--json", action="store_true", help="Print structured JSON.")

    setup = ocr_subparsers.add_parser(
        "setup",
        help="Execute a previously reviewed plan after explicit acknowledgements.",
    )
    setup.add_argument("--plan-id", required=True, help="Exact plan_id printed by 'ocr plan'.")
    for key in (
        "large-download",
        "private-environment",
        "custom-code",
        "resource-usage",
        "local-processing-and-temporary-files",
        "no-performance-guarantee",
    ):
        setup.add_argument(f"--ack-{key}", action="store_true", help=argparse.SUPPRESS)
    setup.add_argument("--json", action="store_true", help="Print the final journal as JSON.")
    setup.add_argument("--quiet", action="store_true", help="Hide stage progress messages.")

    uninstall = ocr_subparsers.add_parser(
        "uninstall",
        help="Remove only managed paths after exact plan confirmation.",
    )
    uninstall.add_argument(
        "--confirm-plan-id",
        required=True,
        help="Exact current plan_id; prevents stale or accidental cleanup.",
    )
    uninstall.add_argument("--remove-model", action="store_true")
    uninstall.add_argument("--clear-download-cache", action="store_true")
    uninstall.add_argument("--json", action="store_true")
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
    _configure_console_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ocr":
        return _run_managed_ocr_command(args)
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
            print(json.dumps(result, ensure_ascii=True, indent=2))
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


def _configure_console_streams() -> None:
    """Prevent legacy Windows console encodings from turning success into an error."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(errors="backslashreplace")
            except (OSError, ValueError):
                continue


def _run_managed_ocr_command(args: argparse.Namespace) -> int:
    from .ocr.consent import clear_advanced_ocr_consent
    from .ocr.deployment.cache import ModelCacheManager
    from .ocr.deployment.consent import DeploymentConsent, build_consent_summary
    from .ocr.deployment.errors import DeploymentFailure
    from .ocr.deployment.models import CompatibilityStatus
    from .ocr.deployment.orchestrator import CancellationToken as SetupCancellationToken
    from .ocr.deployment.orchestrator import DeploymentCleanup
    from .ocr.deployment.providers import UnlimitedOCRProvider
    from .ocr.deployment.validation_assets import create_validation_suite
    from .ocr.local_model import clear_local_model_runtime_config

    provider = UnlimitedOCRProvider()
    try:
        environment, compatibility, plan = provider.analyze()
        if environment is None or compatibility is None:
            raise RuntimeError("Managed OCR analysis returned no result.")
        summary = build_consent_summary(compatibility, plan)

        if args.ocr_command == "inspect":
            payload = environment.to_dict()
            payload["recommendation"] = compatibility.to_dict()
            _write_or_print_ocr_payload(payload, args, human=_human_environment(payload))
            return 0

        if args.ocr_command == "plan":
            payload = {
                "environment": environment.to_dict(),
                "compatibility": compatibility.to_dict(),
                "plan": plan.to_dict(),
                "consent_summary": summary,
            }
            _write_or_print_ocr_payload(payload, args, human=_human_plan(payload))
            return (
                3
                if compatibility.status
                in {CompatibilityStatus.UNSUPPORTED, CompatibilityStatus.UNKNOWN}
                else 0
            )

        cache = ModelCacheManager(Path(plan.model_cache_dir))
        if args.ocr_command == "status":
            journal_path = Path(plan.runtime_root) / "state" / "installation.json"
            journal = None
            if journal_path.is_file():
                try:
                    journal = json.loads(journal_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    journal = {"error": f"Unable to read journal: {exc}"}
            payload = {
                "plan_id": plan.plan_id,
                "compatibility": compatibility.to_dict(),
                "model": cache.inspect(plan.model_revision, provider.engine.metadata).to_dict(),
                "provider": provider.health_check().to_dict(),
                "journal": journal,
            }
            _write_or_print_ocr_payload(payload, args, human=_human_status(payload))
            return 0

        if args.ocr_command == "uninstall":
            if args.confirm_plan_id != plan.plan_id:
                raise ValueError("confirm-plan-id does not match the current reviewed plan.")
            provider.unload()
            result = DeploymentCleanup(plan).uninstall(
                confirmed=True,
                remove_model=args.remove_model,
                clear_download_cache=args.clear_download_cache,
            )
            clear_local_model_runtime_config()
            clear_advanced_ocr_consent()
            if args.json:
                print(json.dumps(result, ensure_ascii=True, indent=2))
            else:
                print("Managed Unlimited-OCR cleanup completed.")
                for key, value in result.items():
                    print(f"- {key}: {value}")
            return 0

        if args.plan_id != plan.plan_id:
            raise ValueError(
                "plan-id does not match the current hardware/metadata plan. Run 'ocr plan' again."
            )
        acknowledgements = {
            "large_download": args.ack_large_download,
            "private_environment": args.ack_private_environment,
            "custom_code": args.ack_custom_code,
            "resource_usage": args.ack_resource_usage,
            "local_processing_and_temporary_files": (
                args.ack_local_processing_and_temporary_files
            ),
            "no_performance_guarantee": args.ack_no_performance_guarantee,
        }
        consent = DeploymentConsent.create(
            plan=plan,
            metadata_revision=compatibility.metadata_revision,
            acknowledgements=acknowledgements,
        )
        token = SetupCancellationToken()
        previous_sigint = signal.getsignal(signal.SIGINT)

        def request_cancel(_signum: int, _frame: Any) -> None:
            token.cancel()
            print("Cancellation requested; stopping the active private process.", file=sys.stderr)

        signal.signal(signal.SIGINT, request_cancel)
        cases = create_validation_suite(Path(plan.runtime_root) / "state" / "validation-assets")

        def progress(record: Any) -> None:
            if not args.quiet:
                print(
                    f"[{record.stage.value}] {record.status.value}: {record.message}",
                    file=sys.stderr,
                )

        try:
            journal = provider.setup(
                consent=consent,
                cancellation=token,
                progress_callback=progress,
                validation_images=[case.image_path for case in cases],
                validation_expectations={
                    str(case.image_path): case.expected_terms for case in cases
                },
            )
        finally:
            signal.signal(signal.SIGINT, previous_sigint)
        if args.json:
            print(json.dumps(journal, ensure_ascii=True, indent=2))
        else:
            final = journal.get("steps", [])[-1] if journal.get("steps") else {}
            print(f"Managed Unlimited-OCR setup status: {final.get('status', 'UNKNOWN')}")
            print(f"Journal: {Path(plan.runtime_root) / 'state' / 'installation.json'}")
        statuses = [step.get("status") for step in journal.get("steps", [])]
        return 130 if any(value in {"CANCELLED", "PAUSED"} for value in statuses) else 0
    except DeploymentFailure as exc:
        error = exc.error.to_dict()
        if getattr(args, "json", False):
            print(json.dumps({"success": False, "error": error}, ensure_ascii=True, indent=2))
        else:
            print(f"error [{error['error_code']}]: {error['user_message']}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "success": False,
                        "error": {
                            "error_code": "INVALID_REQUEST",
                            "title": "Managed OCR command could not run",
                            "user_message": str(exc),
                            "technical_details": f"{type(exc).__name__}: {exc}",
                            "safe_to_retry": True,
                        },
                    },
                    ensure_ascii=True,
                    indent=2,
                )
            )
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2


def _write_or_print_ocr_payload(
    payload: dict[str, Any],
    args: argparse.Namespace,
    *,
    human: str,
) -> None:
    output = getattr(args, "output", None)
    if output:
        path = Path(output).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.json:
            print(f"Report written: {path}")
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    elif not output:
        print(human)


def _human_environment(payload: dict[str, Any]) -> str:
    gpu = payload.get("gpu", [])
    gpu_lines = [
        f"- {item.get('name', 'unknown')} ({_human_bytes(item.get('vram_total_bytes'))} VRAM, "
        f"compute capability {item.get('compute_capability') or 'unknown'})"
        for item in gpu
    ]
    recommendation = payload.get("recommendation", {})
    lines = [
        f"OS: {payload.get('os', {}).get('platform')}",
        f"CPU: {payload.get('cpu', {}).get('model')}",
        f"RAM: {_human_bytes(payload.get('memory', {}).get('total_bytes'))} "
        f"({_human_bytes(payload.get('memory', {}).get('available_bytes'))} available)",
        "GPU(s):",
        *(gpu_lines or ["- none"]),
        f"NVIDIA Driver: {payload.get('nvidia_driver', {}).get('driver_version')}",
        f"CUDA Driver API: {payload.get('cuda', {}).get('driver_api_version')}",
        f"Installed CUDA Toolkit: {payload.get('cuda', {}).get('toolkit_version') or 'not found'}",
        _human_selected_gpu(recommendation),
        f"Free disk: {_human_bytes(payload.get('storage', {}).get('free_bytes'))}",
        f"Compatibility: {recommendation.get('status')}",
        f"Risk: {recommendation.get('risk_level')}",
        f"APP compatibility: {recommendation.get('app_compatibility', {}).get('status')}",
        f"Basic OCR: {recommendation.get('basic_ocr', {}).get('status')}",
        f"Recommended provider: {recommendation.get('recommended_provider')}",
    ]
    missing = recommendation.get("requirements_missing", [])
    if missing:
        lines.extend(["Missing requirements:", *[f"- {item}" for item in missing]])
    return "\n".join(lines)


def _human_plan(payload: dict[str, Any]) -> str:
    plan = payload["plan"]
    compatibility = payload["compatibility"]
    summary = payload["consent_summary"]
    setup_allowed = bool(summary.get("setup_allowed"))
    lines = [
        f"Can this device install Unlimited-OCR safely now? {'Yes' if setup_allowed else 'No'}",
        f"Decision: {compatibility['status']} (confidence {compatibility['confidence']:.0%})",
        f"Risk: {compatibility['risk_level']}",
        f"Setup allowed: {'yes' if setup_allowed else 'no'}",
        f"Plan kind: {plan.get('plan_kind', 'unknown')}",
        f"Recommended backend: {compatibility['recommended_backend']}",
        f"Recommended runtime: {compatibility['recommended_runtime'] or 'none'}",
        f"Recommended provider: {compatibility.get('recommended_provider', 'tesseract')}",
        _human_selected_gpu(compatibility),
        f"APP compatibility: {compatibility.get('app_compatibility', {}).get('status', 'unknown')}",
        f"Basic OCR: {compatibility.get('basic_ocr', {}).get('status', 'unknown')}",
        f"Plan ID: {plan['plan_id']}",
        f"Estimated download: {_human_bytes(compatibility['estimated_download_size'])}",
        f"Estimated disk use: {_human_bytes(compatibility['estimated_disk_usage'])}",
        f"Estimated VRAM target: {_human_bytes(compatibility['estimated_vram_requirement'])}",
        f"Private runtime: {plan['runtime_root']}",
        "No Driver, system CUDA, PATH, or global Python change is included.",
        _tesseract_fallback_message(compatibility),
    ]
    for heading, key in (
        ("Why", "reasons"),
        ("Requirements met", "requirements_met"),
        ("Missing requirements", "requirements_missing"),
        ("Changes required after consent", "required_changes"),
        ("Setup blockers", "blocked_reasons"),
    ):
        values = plan.get(key, []) if key == "blocked_reasons" else compatibility.get(key, [])
        if values:
            lines.extend([heading + ":", *[f"- {item}" for item in values]])
    lines.append("Run with --json or --output for complete technical and consent details.")
    return "\n".join(lines)


def _human_status(payload: dict[str, Any]) -> str:
    model = payload["model"]
    provider = payload["provider"]
    compatibility = payload["compatibility"]
    return "\n".join(
        [
            f"Plan ID: {payload['plan_id']}",
            f"Compatibility: {compatibility['status']} (risk={compatibility['risk_level']})",
            f"APP compatibility: {compatibility.get('app_compatibility', {}).get('status', 'unknown')}",
            f"Basic OCR: {compatibility.get('basic_ocr', {}).get('status', 'unknown')}",
            f"Recommended provider: {compatibility.get('recommended_provider', 'tesseract')}",
            _human_selected_gpu(compatibility),
            f"Provider: {provider['status']} (available={provider['available']}, loaded={provider['loaded']})",
            f"Model snapshot: exists={model['exists']}, complete={model['complete']}",
            f"Journal present: {payload['journal'] is not None}",
            _tesseract_fallback_message(compatibility),
        ]
    )


def _human_bytes(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if number < 1024 or unit == "TiB":
            return f"{number:.1f} {unit}"
        number /= 1024
    return "unknown"


def _human_selected_gpu(compatibility: dict[str, Any]) -> str:
    selected = compatibility.get("selected_gpu") or {}
    if not selected:
        return "Selected GPU: none"
    index = selected.get("index")
    index_text = f"index {index}" if index is not None else "index unknown"
    return (
        f"Selected GPU: {selected.get('name') or 'NVIDIA GPU'} "
        f"({index_text}, {_human_bytes(selected.get('vram_total_bytes'))} VRAM)"
    )


def _tesseract_fallback_message(compatibility: dict[str, Any]) -> str:
    if compatibility.get("basic_ocr", {}).get("status") == "AVAILABLE":
        return "Tesseract is available as the basic OCR fallback."
    return (
        "The Tesseract fallback architecture remains intact, but the Tesseract executable "
        "must be installed separately on this device."
    )


if __name__ == "__main__":
    raise SystemExit(main())
