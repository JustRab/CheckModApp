# -*- mode: python ; coding: utf-8 -*-
"""One-file build: a single portable CheckMod.exe.

The convenient layout - copy one file anywhere and double-click. It unpacks
itself into %TEMP% at launch, which is what makes the first start take a
second or two and what some antivirus heuristics dislike. For a locked-down
corporate machine, prefer CheckModFolder.spec.

Build with::

    pyinstaller packaging/CheckMod.spec --noconfirm --clean
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(SPECPATH)) + "/packaging")
import build_config as cfg  # noqa: E402

ROOT = cfg.project_root(SPECPATH)

a = Analysis(
    [cfg.entry_script(ROOT)],
    pathex=[ROOT],
    binaries=[],
    datas=cfg.bundled_data(ROOT),
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=cfg.EXCLUDES,
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
    upx=False,               # UPX packing is the top cause of AV false positives.
    runtime_tmpdir=None,
    console=False,           # No terminal window behind the floating UI.
    disable_windowed_traceback=False,
    icon=cfg.icon_path(ROOT),
    version=cfg.version_file(ROOT),
)
