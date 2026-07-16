# Beta Tag Readiness Review

This document records the current readiness review for a human-approved beta
tag. It does not create a tag, publish a GitHub Release, or approve production
Unlimited-OCR support.

## Current Beta 4 Readiness (2026-07-16)

Release candidate metadata:

- Python package version: `0.6.0b4`.
- User-facing and installer version: `0.6.0-beta.4`.
- Intended annotated tag: `v0.6.0-beta.4`.
- Starting `main` commit: `e208bdf3008952488330fd3cc3f9f5d787e273c9`.
- Canonical release notes: `docs/releases/v0.6.0-beta.4.md`.

The candidate packages the already-merged managed Unlimited-OCR deployment.
It does not add an OCR feature or broaden platform support. Release-only
hardening adds deterministic version checks for source metadata, installed
metadata, wheel, source distribution, PyInstaller bundle, Windows ZIP, and
installer; embeds package metadata in the PyInstaller bundle; publishes a
SHA-256 manifest; and supplies non-empty GitHub release notes.

Pre-tag local gates completed for this candidate:

- `254` tests and `40` subtests passed.
- Branch coverage was `53%`, above the `45%` CI gate.
- Ruff, Bandit medium/high, pip-audit, compileall, installation verification,
  import checks, CLI help, and CLI version checks passed.
- Wheel and source-distribution clean-environment installation smokes passed.
- PyInstaller build and packaged GUI startup/shutdown passed.
- Release metadata aligned at every locally built artifact boundary.
- Artifact inspection found no managed AI runtime, model weights, Hugging Face
  cache, validation results, private paths, SSH material, or CUDA/PyTorch
  package trees in the default release artifacts.
- The first metadata-enabled bundle exposed the editable checkout path through
  `direct_url.json`. That candidate was rejected, packaging was narrowed to the
  required `METADATA` file, and regression checks now reject this file in both
  the bundle and ZIP. A new serialized rebuild and 1,409-file scan passed.

The local serialized build gate is complete. The final tag remains conditional
on `main` CI, Windows and AI1 real-device health/OCR gates, the Acer
unsupported-device gate, and successful tag-triggered CI and Release workflows.
Exact published hashes belong in the generated `SHA256SUMS.txt`, avoiding
circular documentation changes after the candidate artifacts are built.

## Historical Beta 2 Repository State

- Review date: 2026-07-01.
- Branch reviewed: `main`.
- Latest reviewed remote commit before this readiness package:
  `2e2b9e9 Add beta packaging dry-run checks`.
- Existing stable release reference: `0.5.0`.
- Current beta work is in `Unreleased`.
- `README (1).md` is untracked and out of scope.

## Historical Recommended Beta Tag (2026-07-01)

Recommended tag: `v0.6.0-beta.2`.

Version metadata:

- Python package version: `0.6.0b2` (PEP 440 compliant).
- User-facing release name: `0.6.0-beta.2`.
- Windows installer display/output version: `0.6.0-beta.2`.

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

Version consistency update:

- The 0.5.0 artifact names above exposed a beta tag/version mismatch.
- Package metadata was aligned to `0.6.0b1`.
- Installer metadata was aligned to `0.6.0-beta.1`.
- A version-aligned rebuild was rerun from a clean `git archive` source tree at
  `C:\tmp\pdf-toolkit-beta-rebuild-20260701195336`.
- `UV_CACHE_DIR` was set to
  `%TEMP%\pdf_toolkit_uv_cache_beta_build`, avoiding the prior global uv cache
  permission blocker.
- `uv sync --dev`, `uv build`, PyInstaller, Inno Setup, and Windows ZIP
  creation completed.
- The rebuild produced `pdf_toolkit-0.6.0b1-*` Python artifacts and
  `Unified-PDF-Toolkit-Setup-0.6.0-beta.1.exe`.

Version-aligned artifacts produced:

| Artifact | Size |
| --- | ---: |
| `dist/pdf_toolkit-0.6.0b1-py3-none-any.whl` | 121,297 bytes |
| `dist/pdf_toolkit-0.6.0b1.tar.gz` | 232,140 bytes |
| `dist/Unified-PDF-Toolkit-Windows.zip` | 93,810,084 bytes |
| `dist/installer/Unified-PDF-Toolkit-Setup-0.6.0-beta.1.exe` | 65,942,238 bytes |
| `dist/Unified PDF Toolkit/` app bundle | 228,083,251 bytes / 1,169 files |

Artifact exclusion inspection found no forbidden path matches in the `dist/`
filesystem, Windows ZIP, wheel, or source distribution for `.venv-ocr-runtime`,
the isolated uv cache folder, Hugging Face cache folders, validation sample
names, `README (1).md`, model folders, torch, transformers, nvidia, or CUDA
package paths.

## Tag and Release Triage

`v0.6.0-beta.1` was created and published after the version-aligned artifact
inspection:

- Tag target commit:
  `3be6ba933c767fdbb731f3e146de4ba31536be5b`.
- GitHub Release was created by the tag-driven release workflow.
- Release assets were produced:
  `pdf_toolkit-0.6.0b1-py3-none-any.whl`,
  `pdf_toolkit-0.6.0b1.tar.gz`,
  `Unified-PDF-Toolkit-Windows.zip`, and
  `Unified-PDF-Toolkit-Setup-0.6.0-beta.1.exe`.
- Release workflow completed successfully.
- The separate tag-triggered CI workflow passed on Windows but failed on
  Ubuntu and macOS because one unit test asserted a Windows-only
  `C:\...` path string for a payload generated from `Path("C:/...")`.
- This was a cross-platform test assertion bug, not an OCR runtime, packaging,
  Tesseract, dependency, or product behavior regression.
- The generated `v0.6.0-beta.1` GitHub Release was not marked as a prerelease
  by the original release workflow.

Recommendation after triage: hold broad distribution of `v0.6.0-beta.1`.
`v0.6.0-beta.2` is the clean controlled beta target after the CI test fix and
prerelease workflow metadata fix landed on `main`. Keep `v0.6.0-beta.1`
unchanged for traceability; do not move or recreate the tag.

## Beta 2 Metadata Update

`main` now targets the follow-up controlled beta:

- Git tag target: `v0.6.0-beta.2`.
- Python package version: `0.6.0b2`.
- User-facing release name: `0.6.0-beta.2`.
- Windows installer display/output version: `0.6.0-beta.2`.
- `v0.6.0-beta.1` remains untouched and held.
- The release workflow now marks future `alpha`, `beta`, and `rc` tags as
  prereleases.

## Beta 2 Artifact Rebuild Result

A clean artifact rebuild for `v0.6.0-beta.2` was run from a `git archive`
source tree at:

```text
C:\tmp\pdf-toolkit-beta2-rebuild-20260701205002
```

Build isolation:

- `README (1).md` was not present in the clean source tree.
- `UV_CACHE_DIR` was set to
  `C:\tmp\pdf-toolkit-uv-cache-beta2-20260701205002`.
- `uv sync --dev` installed `pdf-toolkit==0.6.0b2`.
- `uv build`, PyInstaller, Inno Setup, and Windows ZIP creation completed.

Version-aligned artifacts produced:

| Artifact | Size |
| --- | ---: |
| `dist/pdf_toolkit-0.6.0b2-py3-none-any.whl` | 121,296 bytes |
| `dist/pdf_toolkit-0.6.0b2.tar.gz` | 233,796 bytes |
| `dist/Unified-PDF-Toolkit-Windows.zip` | 93,810,790 bytes |
| `dist/installer/Unified-PDF-Toolkit-Setup-0.6.0-beta.2.exe` | 65,952,323 bytes |
| `dist/Unified PDF Toolkit/` app bundle | 228,083,251 bytes / 1,169 files |

Artifact exclusion inspection found no forbidden path matches in the `dist/`
filesystem, Windows ZIP, wheel, or source distribution for `.venv-ocr-runtime`,
the isolated uv cache folder, Hugging Face cache folders, validation sample
names, `README (1).md`, model folders, torch, transformers, nvidia, or CUDA
package paths.

Packaged app launch smoke passed without the experimental flag and with
`PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`. Both launches remained running
after 8 seconds and closed through the main window.

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
- Human decision on whether `v0.6.0-beta.2` is the intended clean beta version.
- Human decision on whether beta users should use repository/source-distribution
  docs or whether a separate docs ZIP should be attached manually.

## Go / No-Go Recommendation

Recommendation: **GO for a human-approved `v0.6.0-beta.2` controlled beta tag**,
not for a public production release.

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
git tag --annotate v0.6.0-beta.2 -m "Experimental Local Unlimited-OCR controlled beta 2"
git push origin v0.6.0-beta.2
```

If publishing a draft GitHub Release after the tag is approved:

```powershell
gh release create v0.6.0-beta.2 --draft --prerelease --title "Experimental Local Unlimited-OCR beta 2" --notes-file docs/releases/experimental_local_unlimited_ocr_beta_release_draft.md
```

The release workflow is tag-driven. Do not run these commands until the
maintainer explicitly approves creating the tag and release.

## Beta 3 Follow-Up: Logging and Onboarding Hardening

After `v0.6.0-beta.2`, `main` added user-safe beta logging/error handling and
beginner onboarding docs. `v0.6.0-beta.1` and `v0.6.0-beta.2` must remain
unchanged.

Recommended next controlled beta target:

- Git tag target: `v0.6.0-beta.3`.
- Python package version: `0.6.0b3`.
- User-facing release name: `0.6.0-beta.3`.
- Windows installer display/output version: `0.6.0-beta.3`.
- `v0.6.0-beta.3` replaces `v0.6.0-beta.2` for controlled beta distribution
  because it includes beta logging/error hardening and beginner tutorials.

Before creating the tag, repeat the clean artifact rebuild and exclusion
inspection, then push only the annotated beta 3 tag. Do not manually edit the
existing beta 1 or beta 2 GitHub Releases.

### Beta 3 Clean Artifact Rebuild

A clean artifact rebuild for `v0.6.0-beta.3` was run from a fresh local clone of
`main` at `10afbaad9bf9a0d7c80ec18d412656264322743e`. `UV_CACHE_DIR` was set to
an isolated folder under `%TEMP%`.

Build results:

- `uv sync --dev` installed `pdf-toolkit==0.6.0b3`.
- `uv build` produced the expected `0.6.0b3` wheel and source distribution.
- PyInstaller completed after explicitly pointing `TCL_LIBRARY` and
  `TK_LIBRARY` at the local Tk runtime so `_tkinter`, `_tcl_data`, and
  `_tk_data` were included.
- Inno Setup built `Unified-PDF-Toolkit-Setup-0.6.0-beta.3.exe`.
- Windows ZIP creation completed from the PyInstaller bundle.
- Artifact exclusion inspection found no forbidden optional runtime/cache/model,
  private input, generated OCR output, or raw-log path matches in the app
  bundle, Windows ZIP, wheel, or source distribution.
- Packaged app launch smoke passed without the experimental flag and with
  `PDF_TOOLKIT_ENABLE_EXPERIMENTAL_LOCAL_OCR=1`.

Version-aligned beta 3 artifacts:

| Artifact | Size |
| --- | ---: |
| `dist/pdf_toolkit-0.6.0b3-py3-none-any.whl` | 121,959 bytes |
| `dist/pdf_toolkit-0.6.0b3.tar.gz` | 240,096 bytes |
| `dist-beta3/Unified-PDF-Toolkit-Windows.zip` | 93,813,218 bytes |
| `dist-beta3/installer/Unified-PDF-Toolkit-Setup-0.6.0-beta.3.exe` | 65,941,656 bytes |
| `dist-beta3/Unified PDF Toolkit/` app bundle | 228,089,226 bytes / 1,169 files |
