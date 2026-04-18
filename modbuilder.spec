# modbuilder.spec
# -*- mode: python ; coding: utf-8 -*-

import os

REPO_ROOT = os.path.abspath(os.getcwd())
SCRIPT_PATH = os.path.join(REPO_ROOT, "modbuilder.py")

datas = [
    # "/org" folder is an externally-provided asset bundle. Required for packaged releases.
    (os.path.join(REPO_ROOT, "modbuilder/org"), "org"),
    (os.path.join(REPO_ROOT, "modbuilder/plugins/*.py"), "plugins"),
    (os.path.join(REPO_ROOT, "modbuilder/saves"), "saves"),
    (os.path.join(REPO_ROOT, "modbuilder/name_map.yaml"), "."),
    (os.path.join(REPO_ROOT, "deca/*.py"), "deca"),
]

a = Analysis(
    [SCRIPT_PATH],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='modbuilder',
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='modbuilder',
)
