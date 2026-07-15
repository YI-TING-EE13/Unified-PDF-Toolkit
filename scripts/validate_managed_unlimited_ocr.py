"""Opt-in real validation for an already-installed managed Unlimited-OCR runtime.

This script never installs dependencies or downloads/removes a model. OCR text is
hashed and measured, not printed or persisted in the validation report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

import psutil
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ocr.deployment.providers import UnlimitedOCRProvider  # noqa: E402
from src.ocr.deployment.validation_assets import (  # noqa: E402
    ValidationCase,
    create_validation_suite,
)
from src.ocr.models import OcrEngine, OcrRequest  # noqa: E402


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an existing managed Unlimited-OCR install without downloading."
    )
    parser.add_argument("--stress-iterations", type=int, default=0, metavar="0..100")
    parser.add_argument("--reload-cycles", type=int, default=1, metavar="0..5")
    parser.add_argument("--output", type=Path, help="Optional UTF-8 JSON report path.")
    args = parser.parse_args(argv)
    if not 0 <= args.stress_iterations <= 100:
        parser.error("--stress-iterations must be between 0 and 100")
    if not 0 <= args.reload_cycles <= 5:
        parser.error("--reload-cycles must be between 0 and 5")
    return args


def _normalize(value: str) -> str:
    return "".join(value.casefold().split())


def _run_case(provider: UnlimitedOCRProvider, case: ValidationCase) -> dict[str, Any]:
    with Image.open(case.image_path) as source:
        image = source.convert("RGB").copy()
    started = time.perf_counter()
    result = provider.recognize(
        OcrRequest(
            engine=OcrEngine.LOCAL_MODEL,
            images=[image],
            page_numbers=[1],
            options={"timeout_seconds": 1800},
        )
    )
    text = result.text
    normalized = _normalize(text)
    matched = [term for term in case.expected_terms if _normalize(term) in normalized]
    ratio = len(matched) / len(case.expected_terms) if case.expected_terms else 1.0
    return {
        "category": case.category,
        "success": bool(text.strip()) and ratio >= 0.5,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "expected_term_count": len(case.expected_terms),
        "matched_term_count": len(matched),
        "match_ratio": round(ratio, 4),
        "output_characters": len(text),
        "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "inference_seconds": result.metadata.get("inference_seconds"),
        "peak_vram_bytes": result.metadata.get("peak_vram_bytes"),
    }


def _worker_sample(provider: UnlimitedOCRProvider) -> dict[str, Any]:
    health = provider.health_check().to_dict()
    pid = health.get("details", {}).get("pid")
    sample: dict[str, Any] = {
        "health": health.get("status"),
        "loaded": health.get("loaded"),
        "pid": pid,
        "allocated_vram_bytes": health.get("details", {}).get("allocated_vram_bytes"),
    }
    if isinstance(pid, int) and psutil.pid_exists(pid):
        process = psutil.Process(pid)
        sample["rss_bytes"] = process.memory_info().rss
        if hasattr(process, "num_handles"):
            sample["handles"] = process.num_handles()
        sample["child_processes"] = len(process.children(recursive=True))
    return sample


def _wait_for_exit(pid: Any, timeout: float = 10.0) -> bool:
    if not isinstance(pid, int):
        return True
    deadline = time.monotonic() + timeout
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not psutil.pid_exists(pid)


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    provider = UnlimitedOCRProvider()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "stress_iterations": args.stress_iterations,
        "reload_cycles": args.reload_cycles,
        "functional_cases": [],
        "reload_results": [],
        "stress": {},
    }
    if not provider.is_available():
        report.update({"success": False, "error": "Managed provider is not installed."})
        return 2, report

    session_root = provider.data_root / "sessions"
    before_children = {child.pid for child in psutil.Process().children(recursive=True)}
    started = time.perf_counter()
    worker_pid: int | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="managed-ocr-validation-") as temporary:
            cases = create_validation_suite(Path(temporary))
            provider.load()
            initial = _worker_sample(provider)
            worker_pid = initial.get("pid")
            report["initial_health"] = initial
            report["functional_cases"] = [_run_case(provider, case) for case in cases]

            for cycle in range(args.reload_cycles):
                previous_pid = _worker_sample(provider).get("pid")
                provider.unload()
                exited = _wait_for_exit(previous_pid)
                provider.load()
                sample = _worker_sample(provider)
                check = _run_case(provider, cases[0])
                report["reload_results"].append(
                    {
                        "cycle": cycle + 1,
                        "previous_pid": previous_pid,
                        "previous_worker_exited": exited,
                        "new_pid": sample.get("pid"),
                        "ocr_success": check["success"],
                        "elapsed_seconds": check["elapsed_seconds"],
                    }
                )

            stress_samples = []
            stress_latencies = []
            for index in range(args.stress_iterations):
                item = _run_case(provider, cases[0])
                stress_latencies.append(item["elapsed_seconds"])
                sample = _worker_sample(provider)
                sample["iteration"] = index + 1
                stress_samples.append(sample)
            if stress_samples:
                rss = [int(item.get("rss_bytes", 0)) for item in stress_samples]
                handles = [int(item.get("handles", 0)) for item in stress_samples]
                report["stress"] = {
                    "completed": len(stress_samples),
                    "all_healthy": all(item.get("health") == "HEALTHY" for item in stress_samples),
                    "worker_pid_count": len({item.get("pid") for item in stress_samples}),
                    "rss_first_bytes": rss[0],
                    "rss_last_bytes": rss[-1],
                    "rss_growth_bytes": rss[-1] - rss[0],
                    "rss_peak_bytes": max(rss),
                    "handles_first": handles[0],
                    "handles_last": handles[-1],
                    "handles_growth": handles[-1] - handles[0],
                    "handles_peak": max(handles),
                    "latency_average_seconds": round(
                        sum(stress_latencies) / len(stress_latencies), 3
                    ),
                    "latency_max_seconds": max(stress_latencies),
                }

            with Image.open(cases[0].image_path) as source:
                benchmark_request = OcrRequest(
                    engine=OcrEngine.LOCAL_MODEL,
                    images=[source.convert("RGB").copy()],
                )
            report["benchmark"] = provider.benchmark(benchmark_request).to_dict()
    except KeyboardInterrupt:
        report.update({"success": False, "cancelled": True})
        return 130, report
    except Exception as exc:
        report.update(
            {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return 1, report
    finally:
        current_pid = _worker_sample(provider).get("pid") if provider._worker else worker_pid
        provider.unload(force=True)
        report["worker_exited_after_unload"] = _wait_for_exit(current_pid)
        after_children = {child.pid for child in psutil.Process().children(recursive=True)}
        report["new_child_processes_after_unload"] = sorted(after_children - before_children)
        report["session_temp_leftovers"] = (
            len(list(session_root.glob("request-*"))) if session_root.exists() else 0
        )
        report["total_elapsed_seconds"] = round(time.perf_counter() - started, 3)

    functional_ok = all(item.get("success") for item in report["functional_cases"])
    reload_ok = all(
        item.get("previous_worker_exited") and item.get("ocr_success")
        for item in report["reload_results"]
    )
    stress_ok = not args.stress_iterations or (
        report["stress"].get("completed") == args.stress_iterations
        and report["stress"].get("all_healthy")
        and report["stress"].get("worker_pid_count") == 1
    )
    report["success"] = bool(
        functional_ok
        and reload_ok
        and stress_ok
        and report.get("worker_exited_after_unload")
        and not report.get("new_child_processes_after_unload")
        and report.get("session_temp_leftovers") == 0
    )
    return (0 if report["success"] else 1), report


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    code, report = run(args)
    output = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output:
        path = args.output.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
