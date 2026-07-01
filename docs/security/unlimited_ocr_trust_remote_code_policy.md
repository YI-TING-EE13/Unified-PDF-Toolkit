# Unlimited-OCR `trust_remote_code` and Model Revision Policy

This policy applies to Experimental Local Unlimited-OCR and any future
Unlimited-OCR-compatible local model backend. It is a beta safety boundary, not
a production support statement.

## Why `trust_remote_code=True` Is Risky

Some Hugging Face models, including Unlimited-OCR-style model examples, require
custom repository code to define loading and inference behavior. Enabling
`trust_remote_code=True` lets that model-provided Python code execute inside the
selected runtime environment.

Risks include:

- arbitrary local code execution inside the optional OCR runtime;
- dependency behavior that differs by model revision;
- unexpected filesystem, GPU, or network behavior from model code;
- compatibility changes when an unpinned model repository updates;
- difficulty auditing the exact code path after a beta run.

Because of this, the app must never execute custom model code at startup, must
not download or run model code silently, and must keep the backend disabled
unless the user explicitly opts in.

## Consent Requirement

Real local Unlimited-OCR execution requires valid Advanced Local AI OCR consent.
The consent must cover:

- potential model download size and cache usage;
- custom model code / `trust_remote_code` execution;
- GPU and VRAM use;
- temporary local rendered page images;
- local-only processing and no upload by this feature.

Changing provider, model id, or consent text version invalidates existing
consent. Declining consent must leave the backend blocked.

## Local-Only Execution Boundary

The supported beta boundary is local user-owned execution:

- The model runtime runs on the user's computer.
- The project does not provide hosted OCR or a project-operated OCR server.
- User files, rendered pages, OCR text, image bytes, model paths, and document
  content must not be uploaded or printed in logs/reports by default.
- The experimental backend remains hidden unless
  `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1` is set.
- Tesseract remains the default OCR backend.

The optional runtime may read local model files and temporary page images only
for the selected OCR request. Generated outputs are local files selected by the
user.

## Recommended Model Revision Pinning

Controlled beta runs should record:

- model id, for example `baidu/Unlimited-OCR`;
- local model directory path type, without publishing private absolute paths;
- source revision or commit hash when known;
- optional runtime package versions;
- GPU and driver/CUDA context.

Future public beta or production builds should prefer explicit model revision
pinning instead of floating branch names. A pinned revision makes it possible to
audit model code, reproduce failures, and write support guidance for a specific
runtime combination.

## Future Allowlist and Checksum Direction

Before broader release, maintainers should consider:

- allowlisting reviewed provider/model/revision combinations;
- documenting expected file hashes or signed release artifacts when practical;
- warning when a configured local model directory cannot be tied to a reviewed
  revision;
- storing only safe metadata, never OCR text, document content, image bytes, or
  source file paths;
- keeping allowlist checks advisory during early beta if local model layouts are
  still changing.

Checksums and allowlists must not trigger automatic downloads. Any model update
remains explicit and user-managed.

## Maintainer Review Before Public Release

Before claiming public beta or production support, maintainers must confirm:

- default dependencies still exclude torch, transformers, CUDA, SGLang/vLLM,
  model files, and model caches;
- heavy AI libraries are not imported at app startup;
- the GUI exposes only the reviewed worker-process path, not direct in-process
  model execution;
- missing consent, model path, worker Python, CUDA, and runtime dependencies
  produce user-safe errors;
- worker timeout and cancellation terminate the worker process;
- smoke tools and diagnostics do not print OCR text, image bytes, rendered page
  images, model paths, or document content;
- beta release notes and setup docs explain `trust_remote_code` and revision
  risk clearly;
- at least one additional Windows + NVIDIA runtime matrix run has been
  recorded after the RTX 3060 validation.

## Beta User Responsibilities

Beta users must understand that:

- Experimental Local Unlimited-OCR is not production-ready.
- The model and runtime are user-managed local components.
- `trust_remote_code=True` means model-provided Python code can execute locally.
- Model files and caches may be large and should stay outside the repository.
- Private documents should not be used for setup validation.
- Disabling the environment gate or clearing runtime settings returns the app
  to Tesseract-only Document OCR behavior.
