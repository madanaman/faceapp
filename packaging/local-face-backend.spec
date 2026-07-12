# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path.cwd()

datas = [
    (str(ROOT / "index.html"), "."),
    (str(ROOT / "app.js"), "."),
    (str(ROOT / "styles.css"), "."),
]
binaries = []
hiddenimports = [
    "cv2",
    "onnxruntime.capi.onnxruntime_pybind11_state",
    "PIL.Image",
    "PIL.ImageOps",
]

for package in ("insightface", "cv2", "PIL"):
    datas += collect_data_files(package)

for package in ("onnxruntime", "cv2"):
    binaries += collect_dynamic_libs(package)

a = Analysis(
    [str(ROOT / "packaging" / "backend_entry.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="local-face-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
