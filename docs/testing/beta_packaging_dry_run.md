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

On the 2026-07-01 beta hardening pass:

- `git ls-files` static artifact search found no tracked optional runtime,
  model/cache, synthetic sample, torch, transformers, or CUDA package files.
- Default dependency files had no diff.
- No local artifact build was run in this pass because the goal was final beta
  release-candidate hardening without publishing or creating release artifacts.

## Remaining Packaging Work

- Run a real local artifact inspection on a clean build machine before any
  public beta announcement.
- Confirm release artifacts on GitHub Actions do not include optional OCR
  runtime folders or model caches.
- Keep beta notes explicit that optional OCR runtime setup is user-managed and
  separate from the default installer.
