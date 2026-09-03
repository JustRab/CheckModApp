"""Desktop shortcut and start-with-Windows integration.

Both are per-user, both write into folders the user already owns, and neither
needs administrator rights:

* the desktop shortcut goes in the user's own Desktop folder;
* the start-up entry goes in ``%APPDATA%\\...\\Start Menu\\Programs\\Startup``,
  which Windows runs at login for that user only. No registry key, no service,
  no scheduled task - so this stays consistent with the promise that CheckMod
  never needs IT involvement.

Windows shortcuts (``.lnk``) are a COM format with no standard-library writer,
so they are created by asking PowerShell - which ships with Windows - to do
it. Linux gets a freedesktop ``.desktop`` file. macOS has no equivalent that
can be written safely without extra tooling, so it reports "unsupported"
rather than pretending.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import APP_NAME, APP_TAGLINE, paths

#: Filename used for both the desktop and the start-up entry.
SHORTCUT_STEM = APP_NAME


def is_supported() -> bool:
    """Whether shortcuts can be created on this platform."""
    return sys.platform.startswith("win") or sys.platform.startswith("linux")


def launch_target() -> Tuple[str, str]:
    """Return ``(program, arguments)`` that start CheckMod on this machine.

    Frozen builds point at the executable itself. Running from source points
    at ``pythonw.exe`` (no console window) with the package as the argument.
    """
    if paths.is_frozen():
        return str(Path(sys.executable).resolve()), ""

    interpreter = Path(sys.executable)
    if sys.platform.startswith("win"):
        windowless = interpreter.with_name("pythonw.exe")
        if windowless.exists():
            interpreter = windowless
    return str(interpreter.resolve()), "-m checkmod"


def desktop_dir() -> Optional[Path]:
    """The user's Desktop folder, or ``None`` when it cannot be located."""
    if sys.platform.startswith("win"):
        base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        candidate = Path(base) / "Desktop"
        if candidate.is_dir():
            return candidate
        # OneDrive-redirected profiles keep the Desktop under the sync root.
        onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveCommercial")
        if onedrive and (Path(onedrive) / "Desktop").is_dir():
            return Path(onedrive) / "Desktop"
        return candidate
    candidate = Path.home() / "Desktop"
    return candidate if candidate.is_dir() else None


def startup_dir() -> Optional[Path]:
    """The per-user auto-start folder for this platform."""
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return (Path(appdata) / "Microsoft" / "Windows" / "Start Menu"
                / "Programs" / "Startup")
    if sys.platform.startswith("linux"):
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
        return Path(base) / "autostart"
    return None


def _shortcut_path(folder: Optional[Path]) -> Optional[Path]:
    """Full path of our shortcut inside ``folder``."""
    if folder is None:
        return None
    suffix = ".lnk" if sys.platform.startswith("win") else ".desktop"
    return folder / f"{SHORTCUT_STEM}{suffix}"


def desktop_shortcut_path() -> Optional[Path]:
    return _shortcut_path(desktop_dir())


def startup_shortcut_path() -> Optional[Path]:
    return _shortcut_path(startup_dir())


def has_desktop_shortcut() -> bool:
    path = desktop_shortcut_path()
    return bool(path and path.exists())


def has_startup_shortcut() -> bool:
    path = startup_shortcut_path()
    return bool(path and path.exists())


# ----------------------------------------------------------------------
# Creation / removal
# ----------------------------------------------------------------------
def _powershell_create(target: Path, program: str, arguments: str,
                       icon: Optional[Path]) -> bool:
    """Create a Windows ``.lnk`` through the WScript.Shell COM object."""
    def quote(value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    script = [
        "$ErrorActionPreference='Stop';",
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(%s);" % quote(target),
        "$s.TargetPath=%s;" % quote(program),
        "$s.Arguments=%s;" % quote(arguments),
        "$s.WorkingDirectory=%s;" % quote(Path(program).parent),
        "$s.Description=%s;" % quote(f"{APP_NAME} - {APP_TAGLINE}"),
    ]
    if icon and icon.exists():
        script.append("$s.IconLocation=%s;" % quote(icon))
    script.append("$s.Save();")

    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", " ".join(script)],
            capture_output=True, timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return completed.returncode == 0 and target.exists()
    except (OSError, subprocess.SubprocessError):
        return False


def _write_desktop_entry(target: Path, program: str, arguments: str,
                         icon: Optional[Path]) -> bool:
    """Write a freedesktop ``.desktop`` launcher."""
    exec_line = f"{program} {arguments}".strip()
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={APP_NAME}",
        f"Comment={APP_TAGLINE}",
        f"Exec={exec_line}",
        "Terminal=false",
        "X-GNOME-Autostart-enabled=true",
    ]
    if icon and icon.exists():
        lines.append(f"Icon={icon}")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        target.chmod(0o755)
        return True
    except OSError:
        return False


def create(target: Optional[Path]) -> bool:
    """Create the shortcut at ``target``. Returns ``True`` on success."""
    if target is None:
        return False
    program, arguments = launch_target()
    icon_dir = paths.resource_dir() / "assets"
    icon = icon_dir / ("icon.ico" if sys.platform.startswith("win") else "icon.png")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    if sys.platform.startswith("win"):
        return _powershell_create(target, program, arguments, icon)
    if sys.platform.startswith("linux"):
        return _write_desktop_entry(target, program, arguments, icon)
    return False


def remove(target: Optional[Path]) -> bool:
    """Delete the shortcut at ``target`` (missing is success)."""
    if target is None:
        return False
    try:
        if target.exists():
            target.unlink()
        return True
    except OSError:
        return False


def set_desktop_shortcut(enabled: bool) -> bool:
    """Create or remove the desktop shortcut."""
    path = desktop_shortcut_path()
    return create(path) if enabled else remove(path)


def set_startup_shortcut(enabled: bool) -> bool:
    """Create or remove the run-at-login entry."""
    path = startup_shortcut_path()
    return create(path) if enabled else remove(path)


def describe() -> List[str]:
    """Human-readable paths, for display in Dev Mode."""
    out: List[str] = []
    for label, path in (("Desktop", desktop_shortcut_path()),
                        ("Start-up", startup_shortcut_path())):
        out.append(f"{label}: {path if path else 'unavailable'}")
    return out
