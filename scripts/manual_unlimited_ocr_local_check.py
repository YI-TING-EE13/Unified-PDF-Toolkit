"""Manual local Unlimited-OCR readiness and smoke-check helper.

This script is opt-in and is not used by CI. It does not install dependencies,
download models, or run OCR unless --run and all required local paths/consent
acknowledgements are provided.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ocr.consent import AdvancedOcrConsent  # noqa: E402
from src.ocr.local_model import (  # noqa: E402
    LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
    LOCAL_MODEL_MODEL_ID,
    LOCAL_MODEL_PROVIDER,
    LocalModelOcrBackend,
    LocalModelRuntimeConfig,
)
from src.ocr.exceptions import OcrError  # noqa: E402
from src.ocr.models import OcrEngine, OcrRequest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual readiness check for experimental local Unlimited-OCR."
    )
    parser.add_argument("--model-path", default="", help="Existing local model directory.")
    parser.add_argument("--input", default="", help="Small local image or PDF to OCR.")
    parser.add_argument(
        "--device",
        default="auto",
        choices=("auto", "cuda", "cpu"),
        help="Device preference passed to the experimental backend.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Actually run OCR. Without this flag, only readiness is printed.",
    )
    parser.add_argument(
        "--acknowledge-experimental-consent",
        action="store_true",
        help="Required with --run to acknowledge local model/custom code/GPU risks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Experimental local Unlimited-OCR readiness")
    print(f"Python: {sys.version.split()[0]}")
    print(f"torch installed: {importlib.util.find_spec('torch') is not None}")
    print(f"transformers installed: {importlib.util.find_spec('transformers') is not None}")
    print(f"model path configured: {bool(args.model_path)}")
    if args.model_path:
        print(f"model path exists: {Path(args.model_path).exists()}")
    print(f"input configured: {bool(args.input)}")
    if args.input:
        print(f"input exists: {Path(args.input).exists()}")

    if not args.run:
        print("OCR not run. Pass --run with local paths and acknowledgement to execute.")
        return 0
    if not args.acknowledge_experimental_consent:
        print("--acknowledge-experimental-consent is required with --run.")
        return 2
    if not args.model_path or not Path(args.model_path).exists():
        print("A valid --model-path is required with --run.")
        return 2
    if not args.input or not Path(args.input).exists():
        print("A valid --input image/PDF is required with --run.")
        return 2

    images, page_numbers = load_input(Path(args.input))
    consent = AdvancedOcrConsent.create(
        provider=LOCAL_MODEL_PROVIDER,
        model_id=LOCAL_MODEL_MODEL_ID,
        acknowledged_model_download_risk=True,
        acknowledged_custom_code_risk=True,
        acknowledged_gpu_vram_use=True,
        acknowledged_temporary_page_images=True,
    )
    backend = LocalModelOcrBackend(
        consent=consent,
        config=LocalModelRuntimeConfig(
            enabled=True,
            mode=LOCAL_MODEL_MODE_LOCAL_UNLIMITED_OCR,
            model_path=args.model_path,
            device_preference=args.device,
        ),
    )
    try:
        result = backend.recognize(
            OcrRequest(
                engine=OcrEngine.LOCAL_MODEL,
                images=images,
                source_path=str(Path(args.input)),
                page_numbers=page_numbers,
            )
        )
    except OcrError as exc:
        print(f"OCR failed: {exc}")
        return 1
    except Exception:
        print("OCR failed unexpectedly. Check the optional runtime and model configuration.")
        return 1
    print(f"OCR pages: {len(result.pages)}")
    print(f"Runtime: {result.metadata.get('runtime')}")
    print(f"Device: {result.metadata.get('device')}")
    print("OCR completed. Text is not printed by this readiness helper.")
    return 0


def load_input(path: Path) -> tuple[list[Image.Image], list[int]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import fitz

        images: list[Image.Image] = []
        page_numbers: list[int] = []
        with tempfile.TemporaryDirectory(prefix="pdf_toolkit_manual_ocr_"):
            with fitz.open(path) as doc:
                for index, page in enumerate(doc, start=1):
                    pixmap = page.get_pixmap(alpha=False)
                    images.append(
                        Image.frombytes(
                            "RGB",
                            (pixmap.width, pixmap.height),
                            pixmap.samples,
                        )
                    )
                    page_numbers.append(index)
        return images, page_numbers
    with Image.open(path) as image:
        return [image.convert("RGB").copy()], [1]


if __name__ == "__main__":
    raise SystemExit(main())
