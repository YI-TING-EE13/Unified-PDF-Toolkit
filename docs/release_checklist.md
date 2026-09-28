# Release Checklist

Use this checklist before publishing a tagged release.

## Local verification

```powershell
uv sync --dev
uv run --no-sync ruff check .
uv run --no-sync bandit -q -r src scripts -x tests -ll
uv run --no-sync pip-audit --skip-editable
uv run --no-sync coverage run -m unittest discover -s tests -v
uv run --no-sync coverage report
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python verify_install.py
uv run --no-sync python scripts/gui_smoke.py
uv run --no-sync python scripts/gui_smoke.py --reduce-motion
uv run --no-sync python -m compileall -q src tests verify_install.py scripts
uv run --no-sync python scripts/verify_beta_release.py --tag v<version>
uv build
powershell -ExecutionPolicy Bypass -File .\scripts\run_pyinstaller.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_packaged_app.ps1
Compress-Archive -Path "dist\Unified PDF Toolkit" -DestinationPath "dist\Unified-PDF-Toolkit-Windows.zip" -Force
uv tool run --from .\dist\pdf_toolkit-<version>-py3-none-any.whl pdf-toolkit --version
```

Run the PyInstaller wrapper and packaged smoke a second time on the same output
path. This checks stale read-only build cleanup and confirms no app process or
file handle remains after shutdown.

If Inno Setup 6 is installed:

```powershell
.\scripts\build_installer.ps1
```

After the installer is built, verify the complete candidate artifact set:

```powershell
uv run --no-sync python scripts/verify_beta_release.py --tag v<version> --dist-dir dist --bundle "dist\Unified PDF Toolkit" --windows-zip "dist\Unified-PDF-Toolkit-Windows.zip"
```

## Windows installer lifecycle acceptance

Before creating a tag, the normal gate is to run
[`docs/testing/windows_installer_lifecycle_acceptance.md`](testing/windows_installer_lifecycle_acceptance.md)
against the exact candidate installer and portable ZIP in a checkpoint-capable
Windows VM. Do not run install, upgrade, or uninstall acceptance on the primary
development host. Record the candidate commit and SHA-256 values before the
first scenario.

The lifecycle gate is normally required before tagging. Static Inno Setup
review, a successful installer build, and packaged-app smoke do not replace
actual lifecycle acceptance.

### Controlled prerelease waiver

A maintainer may waive this gate only for a controlled alpha, beta, or release
candidate, and only when all of the following are true:

1. The release is an alpha, beta, or release candidate, not a stable production
   release.
2. The maintainer explicitly approves and records the waiver.
3. Release notes disclose every untested scenario and the accepted risk.
4. No lifecycle scenario has actually failed. Unrun scenarios remain
   unverified and must never be reported as passing.
5. Exact-main CI and the applicable packaging smoke are green.
6. The release remains marked as a prerelease.
7. The waiver documentation is committed before the tag is created.

For `v0.6.0-beta.5`, the specific waiver is recorded in
[`docs/releases/beta_tag_readiness_review.md`](releases/beta_tag_readiness_review.md)
and [`docs/releases/v0.6.0-beta.5.md`](releases/v0.6.0-beta.5.md). It accepts
the missing VM evidence for this controlled beta only; it does not change the
lifecycle result from `DEFERRED_NO_VM` or imply production readiness. The
release was subsequently published and verified on 2026-09-28; that successful
release evidence does not retroactively convert the waived lifecycle matrix to
`PASS`.

Stable/public production releases still require actual lifecycle acceptance
unless release policy is separately changed and approved.

## Publish

1. Update `CHANGELOG.md`, `pyproject.toml`,
   `installer/UnifiedPDFToolkit.iss`, and the versioned release notes. Update
   `README.md` only when current usage, download, or support information
   changes; keep detailed release history in `CHANGELOG.md`.
2. Commit all release changes.
3. Create an annotated version tag, verify its peeled target, and push only
   that tag:

```powershell
git tag -a v<version> <verified-main-sha> -m "<release summary>"
git rev-parse v<version>^{}
git push origin v<version>
```

The `Release` workflow builds package artifacts, a Windows ZIP bundle, installs
Inno Setup on the Windows runner, builds a current-user Windows installer, and
publishes the release artifacts and `SHA256SUMS.txt` for tag-triggered runs.
A manual `workflow_dispatch` run is an authoritative pre-tag dry run: it
executes the same build/verification path and uploads the workflow artifact, but
the publication step remains skipped because no tag ref is present. A tag must have a matching
`docs/releases/<tag>.md` release-note file. Confirm both the tag-triggered CI and
Release workflows are green, download every published asset into an isolated
directory, verify the checksum manifest and packaged startup/shutdown, and keep
alpha, beta, and release-candidate tags as GitHub prereleases.

## Post-release evidence closure

After a release is published, record the immutable tag target, tag-triggered
workflow run, final asset hashes, and any required normal-desktop qualification
in the versioned release notes/readiness record on `main`. Do not move the tag
or replace published assets merely to add post-release documentation. Historical
pre-tag evidence should remain labeled as historical instead of being rewritten
as if it occurred at publication time.
