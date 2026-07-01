# Experimental Local Unlimited-OCR Beta Packaging Dry Run

This checklist verifies packaging boundaries before any controlled beta build.
It does not create a GitHub Release or git tag.

## Scope

The release workflow remains tag-triggered and uses:

- `.github/workflows/release.yml`
- `scripts/run_pyinstaller.ps1`
- `scripts/build_installer.ps1`
- `installer/UnifiedPDFToolkit.iss`

The beta packaging check is intentionally a dry run / static audit unless a
maintainer explicitly chooses to build local artifacts. Experimental Local
Unlimited-OCR must remain gated, optional, and excluded from default dependency
and installer/runtime bundling decisions.

## Static Checks Run

Run from the repository root:

```powershell
git ls-files | rg "\.venv-ocr-runtime|Unlimited-OCR|hf_home|hf_modules|pdf_toolkit_ocr_validation|sample\.png|multi_page_sample|torch|transformers|CUDA|cuda"
git diff -- pyproject.toml uv.lock requirements.txt
rg -n "PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR|Experimental Local Unlimited-OCR|Tesseract OCR \(default\)" src\tools\document_ocr src\app.py README.md
```

Expected result:

- The first command exits with no matches.
- Default dependency files have no diff.
- Document OCR keeps Tesseract as the first/default backend.
- Experimental Local Unlimited-OCR remains behind
  `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.

## Optional Artifact Inspection

If a maintainer intentionally builds local artifacts without publishing:

```powershell
.\scripts\run_pyinstaller.ps1
.\scripts\build_installer.ps1
```

Inspect the resulting `dist/` output before sharing:

```powershell
Get-ChildItem -Recurse dist | Select-String -Pattern "\.venv-ocr-runtime|Unlimited-OCR|hf_home|hf_modules|torch|transformers|CUDA|cuda"
```

This optional inspection should confirm:

- `.venv-ocr-runtime` is not bundled.
- Local model folders and Hugging Face caches are not bundled.
- Generated OCR outputs and private inputs are not bundled.
- Setup helper/docs are included only as repository/documentation artifacts,
  not as default-installed AI runtime packages.

## Packaging Boundary

The Windows installer copies the PyInstaller app bundle:

```text
Source: "{#AppBundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
```

Therefore the app bundle must be built from the default project environment,
not from `.venv-ocr-runtime`, and maintainers must inspect the bundle if they
manually build it on a machine that also has optional OCR runtime files.

## Pass Criteria

- Default dependencies still exclude torch, transformers, SGLang/vLLM, CUDA,
  model files, and model caches.
- `.venv-ocr-runtime` is untracked and excluded.
- Model/cache/private input/generated OCR output files are untracked and
  excluded.
- Experimental Local Unlimited-OCR remains hidden without
  `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.
- No GitHub Release or tag is created by this dry run.

## Current Result

On the 2026-07-01 beta hardening, tag-readiness, and clean artifact
inspection passes:

- `git ls-files` static artifact search found no tracked optional runtime,
  model/cache, synthetic sample, torch, transformers, or CUDA package files.
- Default dependency files had no diff.
- Release workflow, PyInstaller wrapper, Inno Setup wrapper, and installer
  definition were inspected.
- A clean detached worktree was created under `C:\tmp` for artifact inspection.
- `uv sync --dev`, `uv build`, PyInstaller bundle build, Windows ZIP creation,
  and Inno Setup installer build completed locally in the clean worktree.
- No GitHub Release or git tag was created.

Artifacts produced locally for inspection:

| Artifact | Size |
| --- | ---: |
| `dist/pdf_toolkit-0.5.0-py3-none-any.whl` | 121,272 bytes |
| `dist/pdf_toolkit-0.5.0.tar.gz` | 230,001 bytes |
| `dist/Unified-PDF-Toolkit-Windows.zip` | 93,810,244 bytes |
| `dist/installer/Unified-PDF-Toolkit-Setup-0.5.0.exe` | 65,931,894 bytes |
| `dist/Unified PDF Toolkit/` app bundle | 228,083,251 bytes / 1,169 files |

Inspection results:

- No forbidden path matches were found in the `dist/` filesystem, Windows ZIP,
  wheel, or source distribution for `.venv-ocr-runtime`, Hugging Face cache
  folders, validation sample names, `README (1).md`, model folders, torch,
  transformers, or CUDA package paths.
- The source distribution includes `README.md`, `CHANGELOG.md`, beta release
  docs, runtime docs, smoke checklists, and
  `scripts/setup_local_unlimited_ocr_runtime.py`.
- The Windows ZIP, installer, and wheel do not include beta docs or the setup
  helper. For controlled beta users, release notes must link to repository
  docs or the source distribution if they need the helper script.
- Packaged app launch smoke passed without the experimental flag and with the
  experimental flag. Both launches stayed running after 8 seconds and closed
  through the main window.
- Clean-worktree GUI inspect confirmed `Tesseract OCR (default)` is the only
  backend without `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`; the
  Experimental Local Unlimited-OCR option appears only when the flag is set.

Version consistency follow-up:

- These 0.5.0 artifact names were correct for the metadata at the time of the
  first inspection, but inconsistent with the recommended `v0.6.0-beta.1` tag.
- Package metadata is expected to use PEP 440 version `0.6.0b1`.
- Installer metadata is expected to use display/output version
  `0.6.0-beta.1`.
- A follow-up clean rebuild must confirm the renamed Python and installer
  artifacts before the beta tag is created.
- In this Codex run, that rebuild was attempted but blocked by local uv cache
  permission errors after escalation was unavailable. The expected rerun
  commands are still the same clean build commands below.

## Missing Build Steps Before Sharing Assets

There is no no-op release artifact dry-run target. The clean local build above
is the current inspection baseline. Before a human maintainer shares future
beta artifacts, repeat an intentional clean build and inspect the outputs:

```powershell
uv sync --dev
uv run python -m unittest discover -s tests -v
uv run python verify_install.py
.\scripts\run_pyinstaller.ps1
.\scripts\build_installer.ps1
```

Then inspect `dist/` for accidental optional runtime, model, cache, private
input, and generated OCR output files before uploading or attaching anything to
a release.

## Remaining Packaging Work

- Confirm release artifacts on GitHub Actions do not include optional OCR
  runtime folders or model caches.
- Keep beta notes explicit that optional OCR runtime setup is user-managed and
  separate from the default installer.
- Decide whether beta users should use repository/source-distribution docs or
  whether a separate docs ZIP should be attached manually. Do not add docs or
  optional OCR runtime packages to the default app bundle without review.
