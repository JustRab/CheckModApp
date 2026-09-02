"""Filesystem locations used by CheckMod.

CheckMod supports two storage layouts:

``portable``
    Everything lives in a ``CheckModData`` folder created next to the
    executable (or next to the repository root when running from source).
    This is the layout used when the app runs from a USB stick or a personal
    folder, and it is what makes "copy the .exe, double click, done" work.

``roaming``
    The classic per-user application-data folder
    (``%APPDATA%\\CheckMod`` on Windows, ``~/.config/CheckMod`` elsewhere).
    Used when the executable sits in a read-only location.

Portable mode is enabled by dropping an empty marker file named
``checkmod.portable`` next to the executable; Dev Mode can create or remove
that marker for you. Either way **no data ever leaves the machine** and no
registry keys or system directories are touched, so the app never needs
administrator rights.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Name of the marker file that switches the app into portable mode.
PORTABLE_MARKER = "checkmod.portable"

#: Folder created next to the executable when portable mode is active.
PORTABLE_DIR_NAME = "CheckModData"

#: Environment variable that overrides every other storage rule. Handy for
#: testing, and for team leads who want the data on a specific drive.
ENV_OVERRIDE = "CHECKMOD_DATA_DIR"


def is_frozen() -> bool:
    """Return ``True`` when running from a PyInstaller-built executable."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Directory that holds the executable (frozen) or the project root."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Directory that holds bundled read-only resources (icons, docs).

    PyInstaller unpacks one-file builds into a temporary folder exposed as
    ``sys._MEIPASS``; everywhere else the project root is used.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def portable_marker_path() -> Path:
    """Full path of the portable-mode marker file."""
    return app_dir() / PORTABLE_MARKER


def is_portable() -> bool:
    """Return ``True`` when the portable marker exists next to the app."""
    try:
        return portable_marker_path().exists()
    except OSError:  # pragma: no cover - exotic filesystem errors
        return False


def _roaming_dir() -> Path:
    """Per-user configuration directory for the current platform."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base) / "CheckMod"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "CheckMod"
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "CheckMod"


def data_dir() -> Path:
    """Resolve (and create) the directory holding settings and history.

    Resolution order: ``$CHECKMOD_DATA_DIR`` -> portable folder -> roaming
    folder. If the preferred location cannot be created (for example the app
    was copied into a read-only share) the roaming folder is used as a
    fallback so the app never fails to start.
    """
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return _ensure(Path(override).expanduser())

    if is_portable():
        candidate = app_dir() / PORTABLE_DIR_NAME
        try:
            return _ensure(candidate)
        except OSError:
            pass  # Read-only location: silently fall back to roaming.

    return _ensure(_roaming_dir())


def _ensure(path: Path) -> Path:
    """Create ``path`` (including parents) and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    """Path of the human-readable JSON settings file."""
    return data_dir() / "settings.json"


def history_file() -> Path:
    """Path of the append-only JSON Lines history log."""
    return data_dir() / "history.jsonl"


def backup_file() -> Path:
    """Path of the previous settings revision, kept for one-click rollback."""
    return data_dir() / "settings.backup.json"


def enable_portable(enabled: bool) -> bool:
    """Create or remove the portable marker.

    Returns ``True`` when the requested state was achieved. Failure is not an
    error the user needs to act on - it simply means the folder is read-only.
    """
    marker = portable_marker_path()
    try:
        if enabled:
            marker.write_text(
                "CheckMod portable mode.\n"
                "While this file exists, settings and history are stored in "
                f"./{PORTABLE_DIR_NAME}/ next to the executable.\n"
                "Delete this file to store them in your user profile instead.\n",
                encoding="utf-8",
            )
        elif marker.exists():
            marker.unlink()
        return True
    except OSError:
        return False
