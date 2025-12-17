# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Timer Tool

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect sv_ttk theme files
sv_ttk_datas = collect_data_files('sv_ttk')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=sv_ttk_datas,
    hiddenimports=[
        'pystray._win32',
        'PIL._tkinter_finder',
        'babel.numbers',
        'tkcalendar',
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'pynput.mouse',
        'pynput.mouse._win32',
        'pynput._util',
        'pynput._util.win32',
        'sv_ttk',
        'pywinstyles',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TimerTool',
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
    icon=None,  # Add icon path here if you have one: icon='timer.ico'
)
