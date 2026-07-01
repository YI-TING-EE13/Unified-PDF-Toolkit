# Local OCR Endpoint Contract

This document describes the intended high-level contract for the scaffolded
local OCR endpoint backend. It is not a production server specification, and the
project does not currently include, launch, or operate a real OCR server.

The primary future advanced OCR product direction is a local model runtime on
the user's own computer. This endpoint contract is retained only for
advanced/developer loopback integrations and user-managed local runtime
experiments.

## Status

- Client scaffold exists for future local endpoint integration.
- Endpoint mode is not the primary product direction.
- No production server is included.
- No real endpoint-backed Unlimited-OCR server is included or called by default.
- No endpoint is called by default.
- No server process is started or managed by the app.
- No hosted/shared OCR service is planned.

## Endpoint Locality

The endpoint must be local-first and loopback-only by default.

Allowed by policy:

- `http://127.0.0.1:<port>`
- `http://localhost:<port>` only when resolved to loopback addresses
- `http://[::1]:<port>` if IPv6 loopback is supported and reviewed

Rejected by policy:

- `https://...`
- `http://0.0.0.0:<port>`
- private LAN IPs
- public IPs
- domains
- missing ports
- credentials in URLs
- query strings or fragments
- unexpected paths
- malformed URLs
- file paths

No unsafe remote endpoint override is defined for the current scaffold.

## Request Expectations

Future endpoint requests must follow these rules:

- Require valid advanced OCR consent before sending any page payload.
- Send no source PDF/image file paths.
- Send no output folder paths.
- Send page images as in-memory bytes or base64 payloads, not file paths.
- Include only minimal OCR options needed for local processing.
- Use short timeouts.
- Stop sending further pages after cancellation.

A future JSON request may use this shape:

```json
{
  "engine": "local_endpoint",
  "language": "eng",
  "prompt": "document parsing.",
  "pages": [
    {
      "page_number": 1,
      "image_format": "png",
      "image_base64": "<in-memory page image payload>"
    }
  ]
}
```

This shape is a scaffolded expectation for tests and future review, not a
commitment that a compatible production server is bundled.

## Response Expectations

A future endpoint response should return page-level OCR results without requiring
the app to inspect server logs or external files.

Expected minimal response shape:

```json
{
  "pages": [
    {
      "page_number": 1,
      "text": "recognized text",
      "confidence": 0.92,
      "warnings": []
    }
  ],
  "warnings": [],
  "metadata": {
    "provider": "local_endpoint",
    "model_id": "local/Unlimited-OCR-compatible-endpoint"
  }
}
```

Rules:

- Page numbers should match the request when possible.
- The response page count must match the request page count.
- Every page result must include a positive integer `page_number` and string
  `text`.
- `confidence`, when present, must be numeric.
- Top-level and page-level `warnings`, when present, must be lists of strings.
- Text belongs only in user-selected output files, not logs or diagnostics.
- Missing confidence is allowed.
- Warnings must not include OCR text, image bytes, base64 payloads, or document
  content. The current scaffold validates warning shape but does not propagate
  endpoint warning text into result logs or reports by default.
- Malformed responses must produce clear user-facing errors.

## Timeout and Error Behavior

The client must handle:

- endpoint unavailable
- timeout
- invalid URL
- invalid JSON
- missing pages
- missing text fields
- mismatched page counts
- mismatched page numbers
- invalid confidence or warning fields
- server-side failure status
- cancellation before or during page processing

Errors must be clear and actionable. They must not include OCR text, rendered
image bytes, base64 payloads, source document content, or source file paths sent
to the backend.

## Logging Restrictions

Do not log by default:

- OCR text
- rendered page image bytes
- base64 image payloads
- document content
- source file paths sent to the endpoint
- full request or response payloads

Allowed high-level operational details:

- endpoint validation result
- backend name
- provider/model id
- page count
- timeout category
- elapsed time
- output path

## Consent and Diagnostics

- Endpoint execution must require valid advanced OCR consent.
- Diagnostics may report endpoint URL validity.
- Endpoint reachability checks must be safe, short-timeout, and must not send
  document content.
- Missing or unreachable endpoint is warning/info, not app startup failure.

## Future Server Notes

Any future server implementation must be reviewed separately. Placeholder
runtime commands, SGLang/Transformers launchers, and model download steps are
not normative in this repository until security review, GPU acceptance testing,
and release documentation are complete.
