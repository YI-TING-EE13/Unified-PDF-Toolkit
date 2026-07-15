"""Audit official sources and optionally refresh reviewed compatibility metadata."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ocr.deployment.metadata import (  # noqa: E402
    bundled_metadata_path,
    load_compatibility_metadata,
    validate_compatibility_metadata,
)

ALLOWED_HOSTS = {
    "api.github.com",
    "raw.githubusercontent.com",
    "huggingface.co",
    "pytorch.org",
    "docs.nvidia.com",
}
MAX_METADATA_BYTES = 12 * 1024 * 1024
USER_AGENT = "Unified-PDF-Toolkit-metadata-audit/1.0"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare bundled Unlimited-OCR compatibility metadata with official sources."
    )
    parser.add_argument("--json", action="store_true", help="Print candidate metadata as JSON.")
    parser.add_argument(
        "--write-reviewed",
        action="store_true",
        help="Write the candidate after maintainer review.",
    )
    parser.add_argument(
        "--acknowledge-conflicts",
        action="store_true",
        help="Required with --write-reviewed while official sources still conflict.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=bundled_metadata_path(),
        help="Reviewed metadata output path.",
    )
    return parser.parse_args(argv)


def fetch_bytes(url: str, *, timeout: float = 30.0) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"Metadata source is not allowlisted: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > MAX_METADATA_BYTES:
            raise ValueError(f"Metadata response is too large: {url}")
        value = response.read(MAX_METADATA_BYTES + 1)
    if len(value) > MAX_METADATA_BYTES:
        raise ValueError(f"Metadata response exceeded the safety limit: {url}")
    return value


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


def build_candidate(current: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    candidate = copy.deepcopy(dict(current))
    repository = fetch_json("https://api.github.com/repos/baidu/Unlimited-OCR")
    branch = str(repository["default_branch"])
    branch_data = fetch_json(
        f"https://api.github.com/repos/baidu/Unlimited-OCR/branches/{branch}"
    )
    source_revision = str(branch_data["commit"]["sha"])
    readme = fetch_text(
        f"https://raw.githubusercontent.com/baidu/Unlimited-OCR/{source_revision}/README.md"
    )
    model = fetch_json("https://huggingface.co/api/models/baidu/Unlimited-OCR?blobs=true")
    model_revision = str(model["sha"])
    requirement = parse_transformers_requirements(readme)
    pytorch_page = fetch_text("https://pytorch.org/get-started/previous-versions/")
    profiles = parse_pytorch_profiles(pytorch_page, requirement["packages"]["torch"])
    nvidia_page = fetch_text(
        "https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html"
    )
    driver_minimums = parse_nvidia_driver_minimums(nvidia_page)
    siblings = {str(item["rfilename"]): item for item in model.get("siblings", [])}
    weight_name = "model-00001-of-000001.safetensors"
    weight = siblings[weight_name]
    required_patterns = candidate["model_artifacts"]["allow_patterns"]
    required_files = sorted(
        name for name in siblings if _matches_any(name, required_patterns)
    )
    required_bytes = sum(
        int(item.get("size") or 0)
        for name, item in siblings.items()
        if _matches_any(name, required_patterns)
    )

    candidate.update(
        {
            "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_revision": source_revision,
            "model_revision": model_revision,
        }
    )
    candidate["sources"]["repository_readme"] = (
        f"https://github.com/baidu/Unlimited-OCR/blob/{source_revision}/README.md"
    )
    candidate["sources"]["model"] = (
        f"https://huggingface.co/baidu/Unlimited-OCR/tree/{model_revision}"
    )
    candidate["model_artifacts"].update(
        {
            "reported_total_bytes": sum(
                int(item.get("size") or 0) for item in siblings.values()
            ),
            "required_download_bytes": required_bytes,
            "required_files": required_files,
            "weight_bytes": int(weight["size"]),
            "weight_blob_sha": str(weight["blobId"]),
            "weight_sha256": str(weight["lfs"]["sha256"]),
        }
    )
    transformer = candidate["backends"]["transformers"]
    transformer.update(
        {
            "tested_python": requirement["python"],
            "python_major_minor": ".".join(requirement["python"].split(".")[:2]),
            "tested_cuda": requirement["cuda"],
            "packages": requirement["packages"],
            "pytorch_profiles": {
                profile: {
                    "minimum_driver_major": (
                        driver_minimums[13] if profile.startswith("cu13") else driver_minimums[12]
                    ),
                    "index_url": f"https://download.pytorch.org/whl/{profile}",
                }
                for profile in profiles
            },
        }
    )
    conflicts = detect_conflicts(readme, requirement["cuda"], profiles)
    candidate["known_conflicts"] = list(conflicts)
    validate_compatibility_metadata(candidate)
    return candidate, conflicts


def parse_transformers_requirements(readme: str) -> dict[str, Any]:
    match = re.search(
        r"Requirements tested on python\s+([\d.]+)\s*\+\s*CUDA\s*([\d.]+).*?```\s*\n(.*?)```",
        readme,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Unable to locate the official Transformers requirement block.")
    packages = {}
    for line in match.group(3).splitlines():
        if "==" not in line:
            continue
        name, version = line.strip().split("==", 1)
        packages[name] = version
    for required in ("torch", "torchvision", "transformers", "Pillow", "pymupdf"):
        if required not in packages:
            raise ValueError(f"Official requirement block is missing {required}.")
    return {"python": match.group(1), "cuda": match.group(2), "packages": packages}


def parse_pytorch_profiles(page: str, torch_version: str) -> tuple[str, ...]:
    section = re.search(
        rf"torch=={re.escape(torch_version)}.*?(?=<h3 id=\"v|\Z)",
        page,
        re.DOTALL,
    )
    if not section:
        raise ValueError(f"PyTorch official page has no section for torch {torch_version}.")
    profiles = sorted(set(re.findall(r"/whl/(cu\d+)", section.group(0))))
    if not profiles:
        raise ValueError(f"No CUDA wheel profiles found for torch {torch_version}.")
    return tuple(profiles)


def parse_nvidia_driver_minimums(page: str) -> dict[int, int]:
    text = re.sub(r"<[^>]+>", " ", page)
    values = {}
    for family in (12, 13):
        match = re.search(rf"CUDA\s+{family}\.x\s*&gt;=\s*(\d+)", text)
        if not match:
            match = re.search(rf"CUDA\s+{family}\.x\s*>=\s*(\d+)", text)
        if not match:
            raise ValueError(f"Unable to locate NVIDIA CUDA {family}.x minimum Driver.")
        values[family] = int(match.group(1))
    return values


def detect_conflicts(
    readme: str,
    tested_cuda: str,
    pytorch_profiles: Sequence[str],
) -> tuple[str, ...]:
    conflicts = []
    expected_profile = "cu" + tested_cuda.replace(".", "")
    if expected_profile not in pytorch_profiles:
        conflicts.append(
            f"Unlimited-OCR reports testing with CUDA {tested_cuda}, but official PyTorch "
            f"wheels are {', '.join(pytorch_profiles)}; no {expected_profile} wheel is published."
        )
    kernel_versions = sorted(set(re.findall(r"kernels==([\d.]+)", readme)))
    if len(kernel_versions) > 1:
        conflicts.append(
            "Unlimited-OCR SGLang instructions contain conflicting kernels pins: "
            + ", ".join(kernel_versions)
            + "."
        )
    return tuple(conflicts)


def _matches_any(name: str, patterns: Sequence[str]) -> bool:
    from fnmatch import fnmatch

    return any(fnmatch(name, pattern) for pattern in patterns)


def metadata_content_changed(
    current: Mapping[str, Any], candidate: Mapping[str, Any]
) -> bool:
    """Return whether source-derived metadata changed, ignoring audit time alone."""

    current_copy = copy.deepcopy(dict(current))
    candidate_copy = copy.deepcopy(dict(candidate))
    current_copy.pop("checked_at", None)
    candidate_copy.pop("checked_at", None)
    return current_copy != candidate_copy


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    current = load_compatibility_metadata()
    try:
        candidate, conflicts = build_candidate(current)
    except Exception as exc:
        print(f"metadata audit failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    changed = metadata_content_changed(current, candidate)
    summary = {
        "changed": changed,
        "source_revision": candidate["source_revision"],
        "model_revision": candidate["model_revision"],
        "checked_at": candidate["checked_at"],
        "conflicts": conflicts,
    }
    if args.json:
        print(json.dumps({"summary": summary, "candidate": candidate}, indent=2))
    else:
        print(json.dumps(summary, indent=2))
    if args.write_reviewed:
        if conflicts and not args.acknowledge_conflicts:
            print(
                "Refusing to write while official sources conflict. Review and pass "
                "--acknowledge-conflicts if the safe backend policy is intentional.",
                file=sys.stderr,
            )
            return 3
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
        print(f"Reviewed metadata written: {output}")
    return 1 if changed and not args.write_reviewed else 0


if __name__ == "__main__":
    raise SystemExit(main())
