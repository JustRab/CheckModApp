# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for the portable CheckMod executable.

Goals, in order:

1. **One file.** The user copies ``CheckMod.exe`` anywhere and double-clicks
   it. No installer, no admin rights, nothing written outside the user's own
   profile (or the folder next to the exe in portable mode).
2. **Small.** Standard-library modules the app never touches are excluded,
   which takes the build from ~25 MB to roughly 12 MB.
3. **No console window.** ``console=False`` so no black terminal flashes
   behind the floating window.

Build with::

    pyinstaller packaging/CheckMod.spec --noconfirm --clean
"""

import os

# ``SPECPATH`` is injected by PyInstaller and points at this file's folder.
PROJECT_ROOT = os.path.dirname(os.path.abspath(SPECPATH))
ASSETS = os.path.join(PROJECT_ROOT, "assets")
ICON = os.path.join(ASSETS, "icon.ico")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "packaging", "launcher.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    # Bundled read-only resources; resolved at runtime via
    # checkmod.paths.resource_dir().
    datas=[
        (os.path.join(ASSETS, "icon.ico"), "assets"),
        (os.path.join(ASSETS, "icon.png"), "assets"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # CheckMod is offline by design and imports none of these. Excluding them
    # shrinks the binary and shrinks the attack surface a security reviewer
    # has to consider.
    excludes=[
        "asyncio", "email", "http", "urllib.request", "xml", "xmlrpc",
        "ssl", "socket", "ftplib", "smtplib", "telnetlib", "pydoc_data",
        "unittest", "doctest", "pdb", "distutils", "setuptools", "pip",
        "numpy", "pandas", "matplotlib", "PIL", "test", "lib2to3",
        "sqlite3", "multiprocessing", "concurrent",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CheckMod",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX-packed binaries trip corporate AV heuristics.
    runtime_tmpdir=None,
    console=False,           # No terminal window behind the floating UI.
    disable_windowed_traceback=False,
    icon=ICON if os.path.exists(ICON) else None,
    version=os.path.join(PROJECT_ROOT, "packaging", "version_info.txt")
    if os.path.exists(os.path.join(PROJECT_ROOT, "packaging", "version_info.txt"))
    else None,
)
