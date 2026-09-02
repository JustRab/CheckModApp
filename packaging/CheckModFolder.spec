# -*- mode: python ; coding: utf-8 -*-
"""One-folder build: dist/CheckMod/ containing CheckMod.exe and its libraries.

The layout to hand to a corporate machine. Compared with the one-file build:

* nothing is extracted to %TEMP% at launch - the single behaviour most likely
  to trip heuristic antivirus rules;
* start-up is immediate rather than a second or two;
* the contents are plainly visible to anyone reviewing what was installed.

It is still portable and still needs no administrator rights: copy the whole
folder anywhere and run the exe inside it.

Build with::

    pyinstaller packaging/CheckModFolder.spec --noconfirm --clean
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
    [],
    exclude_binaries=True,   # binaries live beside the exe, not inside it
    name="CheckMod",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=cfg.icon_path(ROOT),
    version=cfg.version_file(ROOT),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CheckMod",
)
