# Manual Document OCR Smoke Test Template

Use this template for future Document OCR fake-backend UI smoke runs. Do not
use it to record OCR text, image bytes, base64 payloads, source file paths, or
document content.

## Run Metadata

- Date:
- Tester:
- App version or commit:
- Platform:
- Python/runtime:
- Display mode: desktop / headless / other
- Dev flag state:
  - `PDF_TOOLKIT_ENABLE_DEV_TOOLS=1`: yes / no
  - Production Document OCR feature switch: enabled / disabled / not present

## Backend and Consent

- Backend mode:
  - fake Unlimited-OCR backend
  - mocked local endpoint transport
  - other:
- Real model used: no
- Live endpoint called: no
- Consent state:
  - valid
  - missing
  - declined
  - stale provider/model
  - stale consent text version
- Expected consent behavior:
- Observed consent behavior:

## Input Selection

- Input file type:
  - PDF
  - PNG
  - JPEG
  - TIFF
  - BMP
  - unsupported type
- Page count:
- File count:
- Source path recorded in logs/reports: no / yes
- Notes without document content:

## Output Selection

- Output folder:
  - temporary test folder
  - user-selected local folder
  - other:
- Selected output format:
  - TXT
  - Markdown
  - TXT + Markdown
  - none
- Expected output files:
- Actual output files:
- Output conflict policy observed:
- OCR text appeared outside selected outputs: no / yes

## Readiness and Diagnostics

- torch installed: yes / no / not checked
- transformers installed: yes / no / not checked
- CUDA/GPU available: yes / no / not checked
- Model cache present: yes / no / not checked
- Endpoint URL validation result, if applicable:
- Endpoint reachability check sent document content: no / yes / not checked
- Diagnostics caused app failure: no / yes
- Warnings observed:

## Progress and Cancellation

- Progress visible before start: yes / no
- Progress updates during run: yes / no
- Cancel tested: yes / no
- Cancel timing:
  - before first file
  - during file/page processing
  - during output writing
- Expected cancellation behavior:
- Observed cancellation behavior:
- Temporary files cleaned up: yes / no / not applicable

## Error Handling

- Scenario tested:
  - missing consent
  - unsupported input
  - missing output folder
  - no output format
  - backend unavailable
  - mocked timeout
  - mocked connection failure
  - mocked malformed response
  - unexpected failure
- Expected user-safe message:
- Observed message:
- Message included OCR text: no / yes
- Message included image bytes/base64: no / yes
- Message included document content: no / yes

## Privacy Checklist

- Files uploaded externally: no / yes
- OCR text uploaded externally: no / yes
- Source file paths sent to backend: no / yes / not applicable
- OCR text logged by default: no / yes
- Image bytes/base64 logged by default: no / yes
- Document content in diagnostics/reports: no / yes
- Temporary rendered page images cleaned up: yes / no / not applicable
- Screen OCR or background OCR used: no / yes

## Result

- Pass/fail decision:
- Blocking issues:
- Non-blocking issues:
- Follow-up required:
- Rollback/hide-feature behavior verified: yes / no / not applicable
