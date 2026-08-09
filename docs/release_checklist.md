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

Before creating a tag, run
[`docs/testing/windows_installer_lifecycle_acceptance.md`](testing/windows_installer_lifecycle_acceptance.md)
against the exact candidate installer and portable ZIP in a checkpoint-capable
Windows VM. Do not run install, upgrade, or uninstall acceptance on the primary
development host. Record the candidate commit and SHA-256 values before the
first scenario.

The release remains blocked when the VM is unavailable or when any fresh
install, beta.4-to-candidate upgrade, retained-data, uninstall, reinstall,
shortcut/registry, shutdown, or rollback scenario is incomplete. Static Inno
Setup review and a successful installer build do not replace this gate.

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
publishes the release artifacts and `SHA256SUMS.txt`. A tag must have a matching
`docs/releases/<tag>.md` release-note file. Confirm both the tag-triggered CI and
Release workflows are green, download every published asset into an isolated
directory, verify the checksum manifest and packaged startup/shutdown, and keep
alpha, beta, and release-candidate tags as GitHub prereleases.
