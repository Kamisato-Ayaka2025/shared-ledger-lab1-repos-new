# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['tongzhang.api', 'tongzhang.desktop', 'e2e_driver', 'tray_driver']
hiddenimports += collect_submodules('uvicorn')


a = Analysis(
    ['scripts/launch.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/tongzhang/assets/tongzhang.ico', 'tongzhang/assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt uses Windows ICU exports without version suffixes. Do not bundle a PATH ICU.
a.binaries = [item for item in a.binaries if item[0].lower() != "icuuc.dll"]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Tongzhang',
    icon='src/tongzhang/assets/tongzhang.ico',
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
    name='Tongzhang',
)
