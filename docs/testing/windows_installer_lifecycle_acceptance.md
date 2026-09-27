# Windows Installer Lifecycle Acceptance

This runbook verifies the Windows installer and portable ZIP without risking a
developer workstation or user data. Run it only against an exact release
candidate in a checkpoint-capable disposable Windows VM.

Current status for `v0.6.0-beta.5`: **DEFERRED — no recoverable Windows VM is
available on the development host.** The commands below are maintained but were
not executed during beta.5 candidate preparation.

## Acceptance boundary

### Target

- Windows 10 or Windows 11 x64 VM.
- Standard non-administrator test account.
- Candidate installer, portable ZIP, wheel, source distribution, and
  `SHA256SUMS.txt` built from one verified commit.
- Published immutable beta.4 installer and ZIP for the upgrade baseline.

### Protected systems and data

- Do not install, upgrade, or uninstall on the primary development host.
- Do not attach the developer's Documents, `%LOCALAPPDATA%`, OCR model cache,
  SSH directory, browser profile, or private documents to the VM.
- Use only synthetic PDFs and images with no personal information.
- Keep VM checkpoints separate from release artifacts and evidence exports.
- Do not disable TLS, SmartScreen, signature checks, SSH host-key checks, or
  antivirus controls to make a scenario pass.

### Minimum VM

- 4 virtual CPUs.
- 8 GiB RAM minimum; 16 GiB preferred.
- 80 GiB dynamic disk minimum; 120 GiB preferred.
- NAT networking.
- Checkpoint/snapshot support with enough free host storage for every named
  checkpoint below.
- No preinstalled Python, uv, Tesseract, PDF Toolkit, or source checkout at the
  clean checkpoint.

GPU passthrough is not required for default installer lifecycle acceptance.
Actual managed Unlimited-OCR installation and reuse require a separately
approved compatible GPU VM or physical disposable test machine.

## Candidate identity

Before starting a VM, record the candidate outside the VM:

```powershell
git status --short --branch
git rev-parse HEAD
Get-FileHash -Algorithm SHA256 -LiteralPath .\dist\installer\Unified-PDF-Toolkit-Setup-0.6.0-beta.5.exe
Get-FileHash -Algorithm SHA256 -LiteralPath .\dist\Unified-PDF-Toolkit-Windows.zip
Get-FileHash -Algorithm SHA256 -LiteralPath .\dist\pdf_toolkit-0.6.0b5-py3-none-any.whl
Get-FileHash -Algorithm SHA256 -LiteralPath .\dist\pdf_toolkit-0.6.0b5.tar.gz
```

Copy artifacts into an isolated VM staging folder such as
`C:\Acceptance\Artifacts`. Verify every hash again inside the VM. A hash
mismatch is a stop condition.

Create an evidence directory inside the VM:

```powershell
$EvidenceRoot = 'C:\Acceptance\Evidence\beta5'
New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
```

Export the evidence directory after each scenario. Do not depend on a later VM
checkpoint to preserve the only copy of evidence.

## Checkpoint topology

Create and verify these checkpoints in the hypervisor:

```text
clean-windows
├── beta5-fresh-installed
├── beta5-portable-checked
└── beta4-installed
    ├── beta5-upgraded
    ├── beta5-uninstalled-retained
    └── beta5-reinstalled
```

Restore `clean-windows` before the fresh installer and portable ZIP scenarios.
Restore `beta4-installed` before each upgrade, retention, failure, or rollback
scenario. Do not continue from a contaminated failed state.

## Evidence inventory

Capture the following before and after each scenario:

```powershell
$AppRoot = Join-Path $env:LOCALAPPDATA 'Programs\Unified PDF Toolkit'
$OcrRoot = Join-Path $env:LOCALAPPDATA 'UnifiedPDFToolkit\ocr'
$SettingsRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'PDFToolkit\Saved\Settings'
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'

Get-Date -Format o
Get-ComputerInfo | Select-Object WindowsProductName,WindowsVersion,OsBuildNumber,OsArchitecture
Get-Process | Where-Object { $_.ProcessName -match 'PDF|python|tesseract' } |
    Select-Object ProcessName,Id,Path
Get-ItemProperty $UninstallKey -ErrorAction SilentlyContinue |
    Where-Object DisplayName -EQ 'Unified PDF Toolkit' |
    Select-Object DisplayName,DisplayVersion,InstallLocation,UninstallString
Get-ChildItem -LiteralPath $AppRoot -Recurse -Force -ErrorAction SilentlyContinue |
    Select-Object FullName,Length,LastWriteTime
Get-ChildItem -LiteralPath $SettingsRoot -Recurse -Force -ErrorAction SilentlyContinue |
    Select-Object FullName,Length,LastWriteTime
Get-ChildItem -LiteralPath $OcrRoot -Recurse -Force -ErrorAction SilentlyContinue |
    Select-Object FullName,Length,LastWriteTime
```

Redirect each command to a timestamped UTF-8 evidence file. Sanitize local user
names before sharing evidence publicly; do not collect OCR text or private
document content.

## Scenario A — Fresh beta.5 installer

1. Restore `clean-windows`.
2. Verify candidate hashes.
3. Run the installer as the standard test user and select the desktop shortcut.
4. Confirm one per-user uninstall entry, Start Menu shortcut, desktop shortcut,
   and installation under `%LOCALAPPDATA%\Programs\Unified PDF Toolkit`.
5. Launch every tool, run the repository GUI checklist with synthetic inputs,
   and close the app through the main window.
6. Confirm no PDF Toolkit, Python, OCR worker, or child process remains.
7. Restart Windows, launch the app again, and repeat normal shutdown.
8. Create checkpoint `beta5-fresh-installed`.

Pass criteria: the installer requires no administrator elevation, the app starts
and closes cleanly before and after restart, version `0.6.0-beta.5` is visible
in the uninstall entry, and no unexpected system-wide Python/CUDA/PATH change
appears.

## Scenario B — Portable ZIP

1. Restore `clean-windows`.
2. Extract `Unified-PDF-Toolkit-Windows.zip` into a new user-writable folder.
3. Launch `Unified PDF Toolkit.exe`, exercise the GUI checklist with synthetic
   inputs, and close normally.
4. Confirm the portable run creates no uninstall entry or Start Menu shortcut.
5. Delete the extracted folder after confirming no process holds a file handle.
6. Create checkpoint `beta5-portable-checked` only if evidence retention needs
   a local checkpoint.

Pass criteria: the portable app starts and closes without an installer, leaves
no registration/shortcut state, and the extracted folder remains deletable.

## Scenario C — beta.4 to beta.5 upgrade

1. Restore `clean-windows` and install the immutable published beta.4 asset.
2. Launch beta.4, change one output preference, process one synthetic PDF, and
   create non-sensitive sentinel files under the settings and managed OCR data
   roots.
3. Record beta.4 registry, shortcut, file, settings, and OCR-root inventories.
4. Create checkpoint `beta4-installed`.
5. Verify beta.5 hashes and run the beta.5 installer without uninstalling
   beta.4 first.
6. Confirm one uninstall entry remains, its version is beta.5, and the existing
   install directory was reused.
7. Launch beta.5 and confirm the preference, recent path/report state, and both
   sentinel files remain.
8. Exercise a normal PDF workflow and close the app.
9. Confirm no process remains and create checkpoint `beta5-upgraded`.

Pass criteria: the shared AppId performs an in-place upgrade, user state is
retained, app files are updated to beta.5, and no duplicate uninstall entries
or shortcuts appear.

## Scenario D — Uninstall, retained data, and reinstall

1. Restore `beta5-upgraded`.
2. Uninstall Unified PDF Toolkit from Windows Settings or the registered
   uninstall command.
3. Confirm application files and application shortcuts are removed.
4. Confirm settings and managed OCR roots remain unchanged, including the
   synthetic sentinels.
5. Confirm the uninstall entry is removed and no app/worker process remains.
6. Create checkpoint `beta5-uninstalled-retained`.
7. Reinstall the exact beta.5 candidate.
8. Confirm retained preferences/sentinels are still present and the application
   can complete a synthetic workflow.
9. Create checkpoint `beta5-reinstalled`.

Pass criteria: uninstall removes application-owned installed files and
registration but does not silently delete user settings or potentially large
managed OCR data; reinstall restores the app without corrupting retained data.

## Scenario E — Active app and rollback behavior

1. Restore `beta4-installed`.
2. Start beta.4 and leave its main window open. Start a synthetic multi-file job
   only when it can be cancelled without losing user data.
3. Run the beta.5 installer and record whether Windows Restart Manager requests
   closure, closes the app, requires a restart, or blocks the upgrade.
4. If the installer reports failure or cancellation, restore
   `beta4-installed`; do not retry repeatedly in the same state.
5. Verify beta.4 still starts and completes a synthetic workflow after restore.

Pass criteria: installer behavior is understandable, no silent data loss occurs,
and restoring the checkpoint returns the exact beta.4 baseline.

## Stop conditions

Stop the run and restore the scenario checkpoint when:

- any artifact hash differs;
- the VM cannot create or restore checkpoints;
- an installer targets a path outside the expected per-user app root;
- the test unexpectedly requests administrator privileges or system-wide
  Python/CUDA/PATH changes;
- user settings or managed OCR data are deleted without an explicit reviewed
  cleanup action;
- an app, Python, OCR worker, or child process remains after the bounded close
  timeout;
- registry, shortcuts, or file inventory cannot be captured;
- the scenario would require disabling a security control or using private
  documents.

Do not reinterpret a stopped or incomplete scenario as a pass.

## Acceptance record

Record each scenario with:

| Field | Required evidence |
| --- | --- |
| Candidate | Commit, version, filenames, SHA-256 values |
| VM | Windows edition/build, CPU/RAM/disk, hypervisor |
| Checkpoint | Restored starting checkpoint and created ending checkpoint |
| Procedure | Exact installer/ZIP commands and user choices |
| Result | PASS, FAIL, or DEFERRED |
| Inventory | Registry, shortcuts, app files, settings, OCR root, processes |
| Recovery | Restore result and elapsed recovery time |
| Artifacts | Sanitized log/screenshot/inventory paths |
| Gap | Anything not tested or requiring separate GPU/device acceptance |

The beta.5 tag gate passes only when every release-blocking scenario is `PASS`,
all evidence belongs to the exact candidate commit/artifact hashes, and a
maintainer reviews the record. A build-only or static-review result remains
`DEFERRED`.
