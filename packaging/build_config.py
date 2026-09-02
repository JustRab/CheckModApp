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
files means the exclude list (which is a privacy guarantee, not just a size
optimisation) can never drift between the two builds.
"""

from __future__ import annotations

import os

#: Standard-library packages CheckMod never imports.
#:
#: Excluding them halves the binary, but the networking entries matter for a
#: different reason: they make "this application cannot reach the network" a
#: structural property of the artifact rather than a claim in a README. A
#: reviewer can confirm it by inspecting the bundle.
EXCLUDES = [
    # Networking - deliberately absent. See docs/PRIVACY.md.
    "asyncio", "email", "http", "urllib.request", "ssl", "socket",
    "ftplib", "smtplib", "telnetlib", "xml", "xmlrpc",
    # Development and packaging tooling.
    "pydoc_data", "unittest", "doctest", "pdb", "distutils", "setuptools",
    "pip", "test", "lib2to3",
    # Heavy third-party libraries that are not dependencies.
    "numpy", "pandas", "matplotlib", "PIL",
    # Unused standard-library subsystems.
    "sqlite3", "multiprocessing", "concurrent",
]


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
