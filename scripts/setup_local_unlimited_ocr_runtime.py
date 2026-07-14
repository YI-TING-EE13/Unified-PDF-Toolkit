"""Opt-in setup helper for the experimental local Unlimited-OCR runtime.

This helper manages only the optional OCR runtime environment. It does not
modify project dependencies, download model files, or run OCR.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence


DEFAULT_RUNTIME_PATH = ".venv-ocr-runtime"
DEFAULT_PYTHON = "3.12"
DEFAULT_RUNTIME_PACKAGES = ("transformers", "accelerate", "pillow", "pymupdf")

TORCH_INDEX_URLS = {
    "cpu": "https://download.pytorch.org/whl/cpu",
    "cu121": "https://download.pytorch.org/whl/cu121",
    "cu124": "https://download.pytorch.org/whl/cu124",
    "cu126": "https://download.pytorch.org/whl/cu126",
    "cu128": "https://download.pytorch.org/whl/cu128",
}


@dataclass(frozen=True)
class SetupPlan:
    runtime_path: Path
    worker_python: Path
    torch_profile: str
    commands: list[list[str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create or update the optional uv-managed runtime for the "
            "experimental local Unlimited-OCR backend."
        )
    )
    parser.add_argument(
        "--runtime-path",
        default=DEFAULT_RUNTIME_PATH,
        help=f"Optional OCR runtime folder. Default: {DEFAULT_RUNTIME_PATH}",
    )
    parser.add_argument(
        "--python",
        default=DEFAULT_PYTHON,
        help=f"Python version or executable for uv venv. Default: {DEFAULT_PYTHON}",
    )
    parser.add_argument(
        "--torch-profile",
        default="none",
        choices=("none", *TORCH_INDEX_URLS.keys()),
        help=(
            "Optional PyTorch wheel profile. Use none to create the runtime "
            "without torch, or choose cpu/cu121/cu124/cu126/cu128 explicitly."
        ),
    )
    parser.add_argument(
        "--extra-package",
        action="append",
        default=[],
        help="Extra optional package to install with uv into the OCR runtime.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the exact uv commands without executing them.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Run without interactive confirmation.",
    )
    return parser.parse_args(argv)


def runtime_python_path(runtime_path: Path) -> Path:
    if os.name == "nt":
        return runtime_path / "Scripts" / "python.exe"
    return runtime_path / "bin" / "python"


def build_setup_plan(args: argparse.Namespace) -> SetupPlan:
    runtime_path = Path(args.runtime_path)
    worker_python = runtime_python_path(runtime_path)
    packages = [*DEFAULT_RUNTIME_PACKAGES, *args.extra_package]
    commands: list[list[str]] = [
        ["uv", "venv", str(runtime_path), "--python", str(args.python)]
    ]
    warnings: list[str] = []

    if args.torch_profile == "none":
        warnings.append(
            "No torch profile selected. The runtime can be created, but real "
            "Unlimited-OCR CUDA/CPU inference still requires an explicitly "
            "installed torch wheel that matches the machine."
        )
    else:
        commands.append(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(worker_python),
                "--index-url",
                TORCH_INDEX_URLS[args.torch_profile],
                "torch",
                "torchvision",
                "torchaudio",
            ]
        )

    commands.append(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(worker_python),
            *packages,
        ]
    )
    return SetupPlan(
        runtime_path=runtime_path,
        worker_python=worker_python,
        torch_profile=args.torch_profile,
        commands=commands,
        warnings=warnings,
    )


def format_command(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    try:
        import shlex

        return shlex.join(command)
    except AttributeError:
        return " ".join(command)


def print_plan(plan: SetupPlan, *, dry_run: bool) -> None:
    print("Experimental Local Unlimited-OCR optional runtime setup")
    print(f"Runtime folder: {plan.runtime_path}")
    print(f"Worker Python: {plan.worker_python}")
    print(f"Torch profile: {plan.torch_profile}")
    print("Model download: not performed by this helper.")
    print("Default project dependencies: not modified.")
    if dry_run:
        print("Mode: dry-run; no commands will be executed.")
    for warning in plan.warnings:
        print(f"Warning: {warning}")
    print("")
    print("Commands:")
    for command in plan.commands:
        print(f"  {format_command(command)}")


def print_next_steps(plan: SetupPlan) -> None:
    print("")
    print("Next steps:")
    print("1. Set writable local Hugging Face cache folders, for example:")
    print(
        '   $env:HF_HOME="$env:TEMP\\pdf_toolkit_ocr_validation\\hf_home"'
    )
    print(
        '   $env:HF_MODULES_CACHE="$env:TEMP\\pdf_toolkit_ocr_validation\\hf_modules"'
    )
    print("2. Configure the existing local model folder in Settings / Recent.")
    print("3. Set PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1 before launching the GUI.")
    print("4. Set worker Python to:")
    print(f"   {plan.worker_python}")
    print("5. Run the beta-check smoke command from docs/runtime/local_unlimited_ocr_beta_setup.md.")


def user_confirm(input_func: Callable[[str], str]) -> bool:
    answer = input_func(
        "Create/update the optional OCR runtime and install packages with uv? [y/N] "
    )
    return answer.strip().lower() in {"y", "yes"}


def execute_commands(
    commands: Iterable[Sequence[str]],
    run_func: Callable[..., subprocess.CompletedProcess],
) -> int:
    for command in commands:
        print(f"Running: {format_command(command)}")
        completed = run_func(list(command), check=False)
        if completed.returncode != 0:
            print("Command failed. Fix the runtime setup issue and rerun this helper.")
            return completed.returncode
    return 0


def run(
    argv: Sequence[str] | None = None,
    *,
    input_func: Callable[[str], str] = input,
    run_func: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> int:
    args = parse_args(argv)
    plan = build_setup_plan(args)
    print_plan(plan, dry_run=args.dry_run)
    print_next_steps(plan)
    if args.dry_run:
        return 0
    if not args.yes and not user_confirm(input_func):
        print("Cancelled. No runtime changes were made by this helper.")
        return 1
    return execute_commands(plan.commands, run_func)


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
