# Beta Tag Readiness Review

This document records the current readiness review for a human-approved beta
tag. It does not create a tag, publish a GitHub Release, or approve production
Unlimited-OCR support.

## Current Repository State

- Review date: 2026-07-01.
- Branch reviewed: `main`.
- Latest reviewed remote commit before this readiness package:
  `2e2b9e9 Add beta packaging dry-run checks`.
- Existing stable release reference: `0.5.0`.
- Current beta work is in `Unreleased`.
- `README (1).md` is untracked and out of scope.

## Recommended Beta Tag

Recommended tag: `v0.6.0-beta.1`.

Reasoning:

- The beta adds a substantial experimental Document OCR path beyond the
  current `0.5.0` release surface.
- Tesseract remains the default production OCR backend.
- Unlimited-OCR remains gated, local-only, optional, and not production-ready.
- A new minor beta communicates that this is a larger feature preview while
  preserving the production boundary.

## Commits Included Since the Stable Baseline

The current beta scope includes the advanced OCR work recorded in
`CHANGELOG.md` under `Unreleased`, including:

- OCR backend abstraction and Tesseract wrapping.
- Advanced OCR consent settings and UI.
- Local endpoint and local model scaffolding.
- Experimental Local Unlimited-OCR backend with lazy optional imports.
- Killable `worker_process` runtime.
- Document OCR UI with Tesseract default and experimental backend gate.
- CUDA and GUI smoke validation reports.
- Runtime setup helper, beta setup docs, smoke checklists, security policy,
  packaging dry-run checks, and final beta tester checklist.

Before tagging, a maintainer should compare:

```powershell
git log --oneline v0.5.0..main
```

If no `v0.5.0` tag exists in the local checkout, compare against the release
commit used for the published `0.5.0` assets.

## Release Artifact Inspection Result

Static inspection for the readiness pass found:

- Release workflow: `.github/workflows/release.yml`.
- App bundle script: `scripts/run_pyinstaller.ps1`.
- Installer script: `scripts/build_installer.ps1`.
- Inno Setup definition: `installer/UnifiedPDFToolkit.iss`.
- The installer copies the PyInstaller app bundle only.
- Default dependency files remain the source of release packaging.
- The optional OCR runtime `.venv-ocr-runtime` is not part of the default
  dependency set.

Expected artifact exclusions:

- `.venv-ocr-runtime`;
- model folders;
- Hugging Face cache folders;
- generated OCR outputs;
- private validation inputs;
- `README (1).md`.

Expected repository/documentation inclusions:

- `scripts/setup_local_unlimited_ocr_runtime.py`;
- beta setup docs;
- runtime docs;
- smoke checklists;
- release notes draft;
- trust remote code / model revision policy docs.

Clean artifact inspection was then run in a detached worktree at:

```text
C:\tmp\pdf-toolkit-beta-artifact-inspection-20260701160913
```

Local build commands completed:

- `uv sync --dev`;
- `uv build`;
- `powershell -ExecutionPolicy Bypass -File .\scripts\run_pyinstaller.ps1`;
- `powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1`;
- `Compress-Archive -Path "dist\Unified PDF Toolkit" -DestinationPath "dist\Unified-PDF-Toolkit-Windows.zip" -Force`.

Artifacts produced locally for inspection:

| Artifact | Size |
| --- | ---: |
| `dist/pdf_toolkit-0.5.0-py3-none-any.whl` | 121,272 bytes |
| `dist/pdf_toolkit-0.5.0.tar.gz` | 230,001 bytes |
| `dist/Unified-PDF-Toolkit-Windows.zip` | 93,810,244 bytes |
| `dist/installer/Unified-PDF-Toolkit-Setup-0.5.0.exe` | 65,931,894 bytes |
| `dist/Unified PDF Toolkit/` app bundle | 228,083,251 bytes / 1,169 files |

Artifact inspection results:

- No forbidden path matches were found in the `dist/` filesystem, Windows ZIP,
  wheel, or source distribution for `.venv-ocr-runtime`, Hugging Face cache
  folders, validation sample names, `README (1).md`, model folders, torch,
  transformers, or CUDA package paths.
- The source distribution includes `README.md`, `CHANGELOG.md`, beta release
  docs, runtime docs, smoke checklists, and
  `scripts/setup_local_unlimited_ocr_runtime.py`.
- The Windows ZIP, installer, and wheel do not include beta docs or the setup
  helper. That is acceptable for the app bundle boundary, but beta release
  notes should link to repository docs or the source distribution.
- Packaged app launch smoke passed without the experimental flag and with the
  experimental flag. Both launches remained running after 8 seconds and closed
  through the main window.
- Clean-worktree GUI inspect confirmed `Tesseract OCR (default)` is the only
  backend without `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`; the
  Experimental Local Unlimited-OCR option appears only when the flag is set.

No GitHub Release, git tag, or published artifact was created by this review.

## Smoke Rerun Result

This readiness pass reran quick beta smoke checks using the existing
uv-managed optional OCR runtime and synthetic temp inputs:

- setup helper dry-run completed without installing packages or downloading
  models;
- optional runtime readiness detected Python 3.12.11, torch, transformers, and
  the configured local model path;
- worker-process CUDA OCR completed for a synthetic one-page image;
- worker-process CUDA OCR completed for a synthetic three-page PDF;
- GUI beta-check completed with Tesseract as the default backend and
  Experimental Local Unlimited-OCR visible only under the experimental gate;
- GUI beta-check wrote TXT and Markdown outputs for both Tesseract and the
  experimental worker path;
- smoke output printed page counts, output counts, byte sizes, and page-marker
  counts only, not full OCR text, image bytes, rendered page images, or private
  document content;
- worker temp directory count was `0` before and after the GUI beta-check.

## Remaining Release Blockers

Blockers before public production release:

- Broader Windows + NVIDIA GPU/runtime matrix validation.
- Clean release artifact build and inspection on a release machine.
- Enforced model revision allowlist/checksum strategy for wider distribution.
- Accessibility review of Document OCR and Settings text.
- More beta feedback on uv runtime setup and CUDA wheel selection.

Blockers before a controlled beta tag:

- Human maintainer review of this readiness package.
- Human decision on whether `v0.6.0-beta.1` is the intended beta version.
- Human decision on whether beta users should use repository/source-distribution
  docs or whether a separate docs ZIP should be attached manually.

## Go / No-Go Recommendation

Recommendation: **GO for a human-approved controlled beta tag**, not for a
public production release.

The controlled beta can proceed if the maintainer accepts:

- the experimental environment gate remains required;
- Tesseract remains default;
- optional OCR runtime and model files are user-managed;
- real Unlimited-OCR support is documented as experimental and local-only;
- Windows app/installer artifacts are allowed to omit beta docs/helper because
  release notes link to repository docs or source distribution content.

## Human Maintainer Commands If Approved

Do not run these commands as part of this review. They are for a future human
maintainer after approval.

```powershell
git status --short
git pull --ff-only origin main
git log --oneline -5
git tag --annotate v0.6.0-beta.1 -m "Experimental Local Unlimited-OCR beta 1"
git push origin v0.6.0-beta.1
```

If publishing a draft GitHub Release after the tag is approved:

```powershell
gh release create v0.6.0-beta.1 --draft --prerelease --title "Experimental Local Unlimited-OCR beta 1" --notes-file docs/releases/experimental_local_unlimited_ocr_beta_release_draft.md
```

The release workflow is tag-driven. Do not run these commands until the
maintainer explicitly approves creating the tag and release.
