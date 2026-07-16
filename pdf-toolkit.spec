# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


block_cipher = None

tkinterdnd2_datas = collect_data_files("tkinterdnd2")
ocr_deployment_root = Path(SPECPATH) / "src" / "ocr" / "deployment"
ocr_deployment_datas = [
    (
        str(ocr_deployment_root / "resources" / "unlimited_ocr_compatibility.json"),
        "src/ocr/deployment/resources",
    ),
    (str(ocr_deployment_root / "runtime_tasks.py"), "src/ocr/deployment"),
    (str(ocr_deployment_root / "provider_worker.py"), "src/ocr/deployment"),
]

a = Analysis(
    ["src/app.py"],
    pathex=[],
    binaries=[],
    datas=tkinterdnd2_datas + ocr_deployment_datas,
    hiddenimports=[
        "tkinterdnd2",
        "pytesseract",
        "docx",
        "pdf2docx",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Unified PDF Toolkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Unified PDF Toolkit",
)
