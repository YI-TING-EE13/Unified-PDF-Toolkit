"""Deterministic fake local model OCR worker.

This script is a subprocess target for developer/tests only. It uses only the
Python standard library and does not import AI runtimes, download models, read
source documents, or run real OCR.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "invalid_request",
                        "message": "Fake local OCR worker received invalid JSON.",
                        "retryable": False,
                    }
                }
            )
        )
        return 2

    pages = request.get("pages", [])
    if not isinstance(pages, list):
        print(
            json.dumps(
                {
                    "error": {
                        "code": "invalid_request",
                        "message": "Fake local OCR worker received invalid pages.",
                        "retryable": False,
                    }
                }
            )
        )
        return 2

    response_pages = []
    for page in pages:
        if not isinstance(page, dict):
            return 2
        page_number = int(page.get("page_number", len(response_pages) + 1))
        response_pages.append(
            {
                "page_number": page_number,
                "text": f"Fake local model OCR text for page {page_number}.",
                "confidence": 1.0,
                "warnings": ["fake local model worker; no real inference"],
            }
        )

    print(
        json.dumps(
            {
                "request_id": request.get("request_id"),
                "pages": response_pages,
                "metadata": {
                    "provider": request.get("provider", "baidu"),
                    "model_id": request.get("model_id", "baidu/Unlimited-OCR"),
                    "runtime": "fake_worker",
                    "real_inference": False,
                },
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
