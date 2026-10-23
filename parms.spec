# -*- mode: python ; coding: utf-8 -*-
import os

# site-packages 路径：优先环境变量 SITE_PACKAGES，
# 否则默认当前用户 home 下的 CEDA 虚拟环境（相对用户名，可移植）
_site_packages = os.environ.get(
    'SITE_PACKAGES',
    os.path.join(os.path.expanduser('~'), '.virtualenvs', 'CEDA', 'lib', 'python3.10', 'site-packages'))

a = Analysis(
    ['main_ui.py'],
    pathex=[],
    binaries=[(_site_packages, 'site-packages')],
    datas=[('device_generation', 'device_generation'), ('analog_placement', 'analog_placement'), ('ota_case1', 'ota_case1'), ('rsmt_router', 'rsmt_router'), ('assets', 'assets')],
    hiddenimports=['PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.sip'],
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
    name='parms',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
