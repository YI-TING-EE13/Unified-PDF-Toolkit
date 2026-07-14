"""Localhost-only OCR endpoint backend scaffold."""

from __future__ import annotations

import base64
import json
import socket
from io import BytesIO
from typing import Any, Callable, Dict, List
from urllib import error, request
from urllib.parse import urlparse

from .consent import (
    ADVANCED_OCR_CONSENT_TEXT_VERSION,
    AdvancedOcrConsent,
    require_valid_consent,
)
from .exceptions import OcrBackendUnavailableError
from .models import OcrEngine, OcrPageResult, OcrRequest, OcrResult
from ..utils.settings import get_setting, set_setting

LOCAL_ENDPOINT_PROVIDER = "local_endpoint"
LOCAL_ENDPOINT_MODEL_ID = "local/Unlimited-OCR-compatible-endpoint"
LOCAL_ENDPOINT_SETTING_KEY = "advanced_ocr.local_endpoint_url"
DEFAULT_LOCAL_ENDPOINT_URL = "http://127.0.0.1:8765"
DEFAULT_LOCAL_ENDPOINT_TIMEOUT_SECONDS = 10.0

EndpointTransport = Callable[[str, Dict[str, Any], float], Dict[str, Any]]


def get_local_endpoint_url() -> str:
    """Load the configured local endpoint URL."""

    return str(get_setting(LOCAL_ENDPOINT_SETTING_KEY, DEFAULT_LOCAL_ENDPOINT_URL))


def set_local_endpoint_url(url: str) -> None:
    """Persist a validated localhost-only endpoint URL."""

    validate_local_endpoint_url(url)
    set_setting(LOCAL_ENDPOINT_SETTING_KEY, url)


def validate_local_endpoint_url(url: str) -> str:
    """Validate and normalize a localhost-only HTTP endpoint URL."""

    if not isinstance(url, str) or not url.strip():
        raise ValueError("Local OCR endpoint must be a non-empty URL.")
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise ValueError("Local OCR endpoint must use http.")
    if not parsed.hostname:
        raise ValueError("Local OCR endpoint must include a host.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Local OCR endpoint must include a valid port.") from exc
    if port is None:
        raise ValueError("Local OCR endpoint must include an explicit port.")
    if port <= 0:
        raise ValueError("Local OCR endpoint port must be greater than zero.")
    if parsed.username or parsed.password:
        raise ValueError("Local OCR endpoint must not include credentials.")
    if parsed.path not in {"", "/"}:
        raise ValueError("Local OCR endpoint must not include a path.")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Local OCR endpoint must not include params, query, or fragment.")

    hostname = parsed.hostname.lower()
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Local OCR endpoint must target localhost only.")
    if hostname == "localhost":
        try:
            resolved = {info[4][0] for info in socket.getaddrinfo(hostname, port)}
        except socket.gaierror as exc:
            raise ValueError("Local OCR endpoint localhost name could not be resolved.") from exc
        if not resolved or any(address not in {"127.0.0.1", "::1"} for address in resolved):
            raise ValueError("Local OCR endpoint localhost must resolve only to loopback addresses.")

    return url


def post_json(url: str, payload: Dict[str, Any], timeout_seconds: float) -> Dict[str, Any]:
    """POST JSON using the standard library.

    The payload is expected to contain in-memory page image data only. Source
    file paths are never added by this backend.
    """

    validate_local_endpoint_url(url)
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        # URL validation above restricts this transport to explicit loopback HTTP.
        with request.urlopen(req, timeout=timeout_seconds) as response:  # nosec B310
            body = response.read()
    except TimeoutError as exc:
        raise OcrBackendUnavailableError("Local OCR endpoint request timed out.") from exc
    except error.URLError as exc:
        raise OcrBackendUnavailableError("Local OCR endpoint request failed.") from exc
    except OSError as exc:
        raise OcrBackendUnavailableError("Local OCR endpoint connection failed.") from exc
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OcrBackendUnavailableError("Local OCR endpoint returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise OcrBackendUnavailableError("Local OCR endpoint returned a non-object JSON response.")
    return parsed


class LocalEndpointOcrBackend:
    """OCR backend scaffold for a user-managed localhost OCR server."""

    engine = OcrEngine.LOCAL_ENDPOINT
    display_name = "Local OCR Endpoint"

    def __init__(
        self,
        *,
        endpoint_url: str = DEFAULT_LOCAL_ENDPOINT_URL,
        consent: AdvancedOcrConsent | None = None,
        timeout_seconds: float = DEFAULT_LOCAL_ENDPOINT_TIMEOUT_SECONDS,
        transport: EndpointTransport = post_json,
    ) -> None:
        self.endpoint_url = validate_local_endpoint_url(endpoint_url)
        self.consent = consent
        if timeout_seconds <= 0:
            raise ValueError("Local OCR endpoint timeout must be greater than zero.")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def recognize(self, request_data: OcrRequest) -> OcrResult:
        require_valid_consent(
            self.consent,
            provider=LOCAL_ENDPOINT_PROVIDER,
            model_id=LOCAL_ENDPOINT_MODEL_ID,
            consent_text_version=ADVANCED_OCR_CONSENT_TEXT_VERSION,
        )
        payload = self._build_payload(request_data)
        try:
            response = self.transport(self.endpoint_url, payload, self.timeout_seconds)
        except OcrBackendUnavailableError:
            raise
        except TimeoutError as exc:
            raise OcrBackendUnavailableError("Local OCR endpoint request timed out.") from exc
        except (ConnectionError, OSError) as exc:
            raise OcrBackendUnavailableError("Local OCR endpoint connection failed.") from exc
        except Exception as exc:
            raise OcrBackendUnavailableError("Local OCR endpoint request failed.") from exc
        if not isinstance(response, dict):
            raise OcrBackendUnavailableError("Local OCR endpoint returned a non-object response.")
        return self._parse_response(response, request_data)

    def _build_payload(self, request_data: OcrRequest) -> Dict[str, Any]:
        if not request_data.images:
            raise OcrBackendUnavailableError("Local OCR endpoint request must include at least one page image.")
        page_numbers = list(request_data.page_numbers)
        pages = []
        for index, image in enumerate(request_data.images):
            page_number = page_numbers[index] if index < len(page_numbers) else index + 1
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            pages.append(
                {
                    "page_number": page_number,
                    "image_format": "png",
                    "image_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
                }
            )
        return {
            "engine": self.engine.value,
            "language": request_data.language,
            "prompt": request_data.prompt,
            "pages": pages,
        }

    def _parse_response(self, response: Dict[str, Any], request_data: OcrRequest) -> OcrResult:
        warnings = response.get("warnings", [])
        if warnings is not None and (
            not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings)
        ):
            raise OcrBackendUnavailableError("Local OCR endpoint warnings must be a list of strings.")
        metadata = response.get("metadata", {})
        if metadata is not None and not isinstance(metadata, dict):
            raise OcrBackendUnavailableError("Local OCR endpoint metadata must be an object.")

        raw_pages = response.get("pages")
        if not isinstance(raw_pages, list):
            raise OcrBackendUnavailableError("Local OCR endpoint response must include a pages list.")
        expected_count = len(request_data.images)
        if len(raw_pages) != expected_count:
            raise OcrBackendUnavailableError(
                "Local OCR endpoint response page count must match the request page count."
            )

        pages: List[OcrPageResult] = []
        expected_page_numbers = list(request_data.page_numbers)
        for index, raw_page in enumerate(raw_pages):
            if not isinstance(raw_page, dict):
                raise OcrBackendUnavailableError("Local OCR endpoint page result must be an object.")
            if "text" not in raw_page:
                raise OcrBackendUnavailableError("Local OCR endpoint page result must include text.")
            text = raw_page.get("text")
            if not isinstance(text, str):
                raise OcrBackendUnavailableError("Local OCR endpoint page text must be a string.")
            if "page_number" not in raw_page:
                raise OcrBackendUnavailableError("Local OCR endpoint page result must include page_number.")
            page_number_value = raw_page.get("page_number")
            if isinstance(page_number_value, bool):
                raise OcrBackendUnavailableError("Local OCR endpoint page_number must be an integer.")
            try:
                page_number = int(page_number_value)
            except (TypeError, ValueError) as exc:
                raise OcrBackendUnavailableError("Local OCR endpoint page_number must be an integer.") from exc
            if page_number <= 0:
                raise OcrBackendUnavailableError("Local OCR endpoint page_number must be positive.")
            expected_page_number = (
                expected_page_numbers[index] if index < len(expected_page_numbers) else index + 1
            )
            if page_number != expected_page_number:
                raise OcrBackendUnavailableError(
                    "Local OCR endpoint page_number must match the request page order."
                )
            confidence_value = raw_page.get("confidence")
            if isinstance(confidence_value, bool):
                raise OcrBackendUnavailableError("Local OCR endpoint confidence must be numeric.")
            try:
                confidence = float(confidence_value) if confidence_value is not None else None
            except (TypeError, ValueError) as exc:
                raise OcrBackendUnavailableError("Local OCR endpoint confidence must be numeric.") from exc
            page_warnings = raw_page.get("warnings", [])
            if page_warnings is not None and (
                not isinstance(page_warnings, list)
                or not all(isinstance(item, str) for item in page_warnings)
            ):
                raise OcrBackendUnavailableError(
                    "Local OCR endpoint page warnings must be a list of strings."
                )
            pages.append(
                OcrPageResult(
                    page_number=page_number,
                    text=text,
                    confidence=confidence,
                )
            )

        return OcrResult(
            engine=self.engine,
            pages=pages,
            source_path=request_data.source_path,
            warnings=["Local endpoint backend scaffold; no server is started by this app."],
            metadata={
                "provider": LOCAL_ENDPOINT_PROVIDER,
                "model_id": LOCAL_ENDPOINT_MODEL_ID,
                "endpoint_url": self.endpoint_url,
                "omitted_endpoint_warning_count": len(warnings or []),
            },
        )
