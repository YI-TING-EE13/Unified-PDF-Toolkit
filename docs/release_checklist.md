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
uv run --no-sync python -m compileall -q src tests verify_install.py scripts
uv build
powershell -ExecutionPolicy Bypass -File .\scripts\run_pyinstaller.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_packaged_app.ps1
uv tool run --from .\dist\pdf_toolkit-<version>-py3-none-any.whl pdf-toolkit --version
```

Run the PyInstaller wrapper and packaged smoke a second time on the same output
path. This checks stale read-only build cleanup and confirms no app process or
file handle remains after shutdown.

If Inno Setup 6 is installed:

```powershell
.\scripts\build_installer.ps1
```

## Publish

1. Update `CHANGELOG.md`, `README.md`, `pyproject.toml`, and
   `installer/UnifiedPDFToolkit.iss`.
2. Commit all release changes.
3. Create and push a version tag:

```powershell
git tag v<version>
git push origin v<version>
```

The `Release` workflow builds package artifacts, a Windows ZIP bundle, installs
Inno Setup on the Windows runner, builds a current-user Windows installer, and
publishes the installer artifact. Confirm the CI and Release workflows are green
before marking a release as latest. Alpha, beta, and release-candidate tags must
remain GitHub prereleases.
