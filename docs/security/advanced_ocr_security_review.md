# Advanced OCR Privacy and Security Review

This review defines the security, privacy, and release requirements for any
future real advanced local AI OCR or Unlimited-OCR-compatible backend. The app
now includes an experimental local Unlimited-OCR backend path, but the default
app does not download models, start OCR servers, call a real OCR endpoint, add
GPU/runtime dependencies, or expose production-ready Unlimited-OCR support.

## Scope

This review applies to current gated experimental work and future work that
processes user-selected PDF or image files through an optional advanced OCR
backend. Covered backend types include:

- A user-managed local OCR endpoint.
- An in-process local model runtime.
- The gated experimental local Unlimited-OCR worker runtime.

This review does not approve production-ready AI OCR. Any expansion beyond the
current gated experimental worker path must satisfy the release gates below
before it can be enabled for broader use.

## Assets to Protect

- Source PDF and image files.
- Rendered page images and temporary files.
- OCR text and structured OCR output.
- Source file paths and output folder paths.
- User consent records and settings.
- Local model cache paths and runtime configuration.
- Diagnostics and workflow reports.
- The default lightweight app installation.
- The user's GPU/VRAM and system stability.

## Trust Boundaries

- User-selected files enter the app through explicit file selection or existing
  file-list controls.
- PDF pages may be rendered into in-memory images or temporary local images.
- Optional OCR backends must run locally and must be consent-gated.
- A local endpoint backend must remain on loopback only by default.
- Optional model/runtime packages are outside the default dependency boundary.
- Diagnostics may inspect dependency availability and settings, but must not
  inspect or transmit document content.
- Logs and workflow reports are outside the OCR data boundary and must not
  receive OCR text or rendered page images by default.

## Threat Model

Potential threats:

- Accidental upload of documents, rendered images, OCR text, or source paths.
- Unsafe endpoint configuration that sends data to LAN, public IPs, domains, or
  non-HTTP schemes.
- Model supply-chain compromise through unreviewed model files, package
  dependencies, or custom model code.
- Arbitrary code execution through `trust_remote_code` or equivalent custom
  model hooks.
- Sensitive data leakage through logs, diagnostics, crash reports, workflow
  reports, or UI status messages.
- Temporary file persistence after success, failure, or cancellation.
- Background processing without a visible user action.
- GPU/VRAM exhaustion causing app instability or system impact.
- Default-install bloat or accidental startup-time imports of heavy runtimes.
- Confusing UI that implies production-ready Unlimited-OCR support before it is
  reviewed and released.

Out of scope for this stage:

- Guaranteeing model accuracy.
- Defending against malicious files beyond the protections already expected of
  PDF/image parsing libraries.
- Running untrusted remote OCR services.

## Privacy Risks and Requirements

- No external upload is allowed by default.
- No source file path may be sent to OCR backends or endpoints.
- OCR text, rendered images, base64 image payloads, and document content must not
  appear in logs, diagnostics, reports, or exception messages by default.
- Output files must be written only to the user-selected local output folder.
- Any partial output after cancellation must be clearly marked or avoided.
- Sample files used in manual validation must be local and non-sensitive.
- Future documentation must describe exactly what data is processed locally.

## Supply-Chain Risks

Future real backend work must document and review:

- Optional runtime packages and exact versions.
- Model provider, model id, and expected cache location.
- Package and model license compatibility.
- Dependency provenance and installation instructions.
- Whether model files are downloaded manually or by a reviewed installer step.
- How a reviewer can reproduce the runtime environment.

Default dependencies must not include torch, transformers, SGLang, CUDA, model
files, or server runtimes unless a later release decision explicitly changes
this policy.

## Custom Code and `trust_remote_code` Risks

Any backend requiring `trust_remote_code=True` or equivalent custom model code
must be treated as executing third-party code locally.

Requirements before enabling such a backend:

- Explicit user consent that names the custom-code risk.
- Documentation explaining why custom code is required.
- Security review of the model repository and pinned revision.
- Lazy import and lazy execution only after consent and backend selection.
- No execution at app startup.
- Clear rollback instructions to disable the backend and remove optional runtime
  packages.

## Local Endpoint Risks

Endpoint mode must stay local-first:

- Default endpoint must be loopback only.
- Allowed by default: `http://127.0.0.1:<port>`.
- Allowed only after validation: `http://localhost:<port>` if it resolves to
  loopback addresses, and `http://[::1]:<port>` if IPv6 loopback is supported.
- Rejected by default: `0.0.0.0`, private LAN IPs, public IPs, domains,
  credentials, query strings, unexpected paths, missing ports, malformed URLs,
  file paths, and non-HTTP schemes.
- No source file paths may be included in payloads.
- Page images, if sent, must be in-memory bytes or base64 payloads only.
- Timeout must be short and user-facing.
- Reachability checks must be opt-in or safe, must use short timeouts, and must
  not send document content.

## Temporary File and Image Risks

Future real backend work must define:

- Whether rendered pages stay in memory or are written to local temp files.
- The temp directory policy.
- Cleanup behavior after success, failure, cancellation, and app shutdown.
- Protections against leaving sensitive images in predictable locations.
- Tests or manual checks proving cleanup works.

## Logging and Reporting Risks

Logs, diagnostics, workflow reports, and error messages must not contain:

- OCR text.
- Rendered page image bytes.
- Base64 image payloads.
- Document content.
- Source PDF/image paths sent to backends.
- Model-generated structured content.

Allowed by default:

- Backend name.
- Provider/model id.
- Page counts.
- Timing summaries.
- Output file paths.
- High-level error categories.

## Consent Requirements

Before any real advanced OCR execution:

- Consent must be required.
- Consent must match provider, model id, and consent text version.
- Changing provider, model id, or consent text version must invalidate prior
  consent.
- Consent must acknowledge model download risk, custom-code risk, GPU/VRAM use,
  and temporary rendered page images.
- Cancelled or declined consent must leave the backend unavailable.
- Consent records must not store OCR text, rendered page images, source file
  paths, output contents, or document content.

## Diagnostics Requirements

Diagnostics must remain safe when optional dependencies are absent:

- Use optional detection for torch, transformers, SGLang, CUDA, and model cache.
- Do not import heavy runtimes at app startup.
- Import torch only inside guarded diagnostics helpers when installed.
- Missing runtime, missing GPU, missing model, and unreachable endpoint must be
  warning/info states, not app startup failures.
- Diagnostics must not download models, call real OCR endpoints with document
  content, or require internet access.

## Packaging and Runtime Risks

- Default installs must remain lightweight.
- Windows installer and portable bundle must not include AI runtimes, model
  files, CUDA, SGLang, vLLM, torch, or transformers by default.
- Optional runtime installation must be documented separately.
- Optional runtime failures must not break Tesseract OCR or non-OCR PDF tools.
- Heavy imports must occur only after explicit backend selection and consent.

## Release Gates Before Real Model Integration

Real advanced OCR integration cannot ship until all gates pass:

- Security/privacy checklist passes.
- GPU acceptance plan has been executed on approved local samples.
- Consent flow is reviewed against the actual provider/model/version.
- Endpoint policy rejects non-loopback targets by default.
- No source file paths are sent to OCR backends.
- Logs, diagnostics, and reports are verified not to contain OCR text or image
  payloads.
- Temporary image cleanup is verified for success, failure, and cancellation.
- Missing GPU/model/runtime/server paths produce clear user-facing errors.
- Tesseract remains the default PDF to Word OCR Text engine.
- Default dependencies remain free of heavy AI runtime packages.
- README and release notes accurately state what is and is not supported.
- Rollback plan is documented and tested.

## Rollback Requirements

Future real backend work must provide a rollback path:

- Disable the experimental backend without affecting Tesseract OCR.
- Clear advanced OCR consent if the provider/model/version changes or is
  withdrawn.
- Remove optional runtime setup instructions from release docs if the backend is
  pulled.
- Preserve existing PDF tools and PDF to Word OCR Text behavior.
- Avoid leaving model downloads, temp images, or server processes managed by the
  app.
