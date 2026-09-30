"""Shared PyInstaller configuration for both build layouts.

Two distributions are produced from one recipe:

``CheckMod.exe`` (one file)
    The convenient one. Unpacks itself into ``%TEMP%`` at launch and runs from
    there. Self-extraction is the behaviour heuristic antivirus engines most
    often flag, so this is the layout most likely to need an exception.

``CheckMod/`` (one folder)
    The corporate-friendly one. A plain folder holding ``CheckMod.exe`` beside
    its libraries. Nothing is written to ``%TEMP%``, nothing is extracted at
    runtime, and the executable starts instantly. Still portable - copy the
    folder anywhere and run the exe inside it.

Keeping the analysis settings here rather than duplicating them in two spec
files means the exclude list (which bounds what the artifact can do, not just
its size) can never drift between the two builds.
"""

from __future__ import annotations

import os

#: Standard-library packages CheckMod never imports.
#:
#: Excluding them halves the binary, and the omissions also bound what the
#: artifact is *able* to do - a reviewer can confirm each one by inspecting
#: the bundle rather than taking a README's word for it.
#:
#: Until 1.4.0 that included every networking module. The optional AHT sheet
#: sync (``checkmod/sheets.py``) needs an HTTPS ``GET``, so ``urllib.request``
#: and its dependencies now ship. What remains excluded is still meaningful:
#: no mail, no FTP, no XML-RPC, no async server machinery - the one thing the
#: binary can do on a network is fetch a URL, which is the whole of that
#: feature. See docs/PRIVACY.md for the rest of the guarantee.
EXCLUDES = [
    # HTTPS GET is supported (the opt-in AHT sheet sync) and nothing else:
    # every other protocol stays out of the bundle.
    "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "nntplib",
    "xmlrpc", "socketserver", "http.server", "wsgiref", "asyncio",
    "xml",
    # Development and packaging tooling.
    "pydoc_data", "unittest", "doctest", "pdb", "distutils", "setuptools",
    "pip", "test", "lib2to3",
    # Heavy third-party libraries that are not dependencies.
    "numpy", "pandas", "matplotlib", "PIL",
    # Unused standard-library subsystems.
    "sqlite3", "multiprocessing", "concurrent",
]


#: Modules PyInstaller must bundle even though nothing imports them at module
#: scope. ``checkmod.sheets`` imports ``urllib.request`` inside its fetch
#: function - deliberately, so an install that was never pointed at a sheet
#: never loads networking code - and a lazy import is easy for a future
#: PyInstaller to miss. Naming them here makes the sync work in the frozen
#: build regardless.
HIDDEN_IMPORTS = ["urllib.request", "urllib.error", "http.client", "ssl"]


def project_root(spec_path: str) -> str:
    """Repository root, given the folder containing the running spec file."""
    return os.path.dirname(os.path.abspath(spec_path))


def bundled_data(root: str):
    """Read-only resources to ship, resolved at runtime by ``paths.resource_dir``."""
    assets = os.path.join(root, "assets")
    return [
        (os.path.join(assets, "icon.ico"), "assets"),
        (os.path.join(assets, "icon.png"), "assets"),
    ]


def entry_script(root: str) -> str:
    """The frozen entry point."""
    return os.path.join(root, "packaging", "launcher.py")


def icon_path(root: str):
    """Path to the .ico, or ``None`` when it has not been generated yet."""
    path = os.path.join(root, "assets", "icon.ico")
    return path if os.path.exists(path) else None


def version_file(root: str):
    """Path to the Windows version resource, or ``None`` if absent."""
    path = os.path.join(root, "packaging", "version_info.txt")
    return path if os.path.exists(path) else None
