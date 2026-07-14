# Release Checklist

Use this checklist before publishing a tagged release.

## Local verification

```powershell
uv sync --dev
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python verify_install.py
uv run --no-sync python scripts/gui_smoke.py
uv run --no-sync python -m compileall -q src tests verify_install.py scripts
uv build
uv run --no-sync pyinstaller pdf-toolkit.spec --noconfirm
```

If Inno Setup 6 is installed:

```powershell
.\scripts\build_installer.ps1
```

## Publish

1. Update `CHANGELOG.md`, `README.md`, and `installer/UnifiedPDFToolkit.iss`.
2. Commit all release changes.
3. Create and push a version tag:

```powershell
git tag v0.5.0
git push origin v0.5.0
```

The `Release` workflow builds package artifacts, a Windows ZIP bundle, installs
Inno Setup on the Windows runner, builds a current-user Windows installer, and
publishes the installer artifact.
