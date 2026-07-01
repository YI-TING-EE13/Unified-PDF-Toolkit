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

Static inspection for this readiness pass found:

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
- Optional clean-machine artifact build inspection if the beta will ship
  downloadable assets.

## Go / No-Go Recommendation

Recommendation: **GO for a human-approved controlled beta tag**, not for a
public production release.

The controlled beta can proceed if the maintainer accepts:

- the experimental environment gate remains required;
- Tesseract remains default;
- optional OCR runtime and model files are user-managed;
- real Unlimited-OCR support is documented as experimental and local-only;
- release artifacts are inspected before sharing.

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
