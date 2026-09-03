"""Unit tests for desktop / start-up shortcut integration.

The Windows path shells out to PowerShell, so it cannot run here; the
platform-independent decisions - where the files go, what the launcher points
at, and that failures are reported rather than swallowed - are what these
cover, plus the Linux ``.desktop`` writer end to end.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod import shortcuts


def test_the_launcher_points_at_the_executable_when_frozen(monkeypatch):
    monkeypatch.setattr(shortcuts.paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", "/opt/CheckMod/CheckMod.exe")
    program, arguments = shortcuts.launch_target()
    assert program.endswith("CheckMod.exe")
    assert arguments == ""


def test_the_launcher_runs_the_package_when_not_frozen(monkeypatch):
    monkeypatch.setattr(shortcuts.paths, "is_frozen", lambda: False)
    program, arguments = shortcuts.launch_target()
    assert arguments == "-m checkmod"
    assert "python" in program.lower()


def test_the_startup_folder_is_inside_the_user_profile():
    """No admin rights: never a machine-wide location."""
    folder = shortcuts.startup_dir()
    assert folder is not None
    assert str(Path.home()) in str(folder)


def test_shortcut_filenames_match_the_platform():
    path = shortcuts.startup_shortcut_path()
    expected = ".lnk" if sys.platform.startswith("win") else ".desktop"
    assert path.suffix == expected
    assert path.stem == "CheckMod"


def test_removing_a_missing_shortcut_is_success():
    assert shortcuts.remove(Path("/nonexistent/CheckMod.desktop")) is True


def test_create_and_remove_report_failure_for_a_missing_target():
    assert shortcuts.create(None) is False
    assert shortcuts.remove(None) is False


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="freedesktop only")
def test_the_desktop_entry_is_written_and_launches_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = shortcuts.startup_shortcut_path()

    assert shortcuts.create(target)
    body = target.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in body
    assert "Name=CheckMod" in body
    assert "Exec=" in body and "checkmod" in body
    assert "Terminal=false" in body
    assert shortcuts.has_startup_shortcut()

    assert shortcuts.remove(target)
    assert not shortcuts.has_startup_shortcut()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="freedesktop only")
def test_set_startup_shortcut_toggles_both_ways(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert shortcuts.set_startup_shortcut(True)
    assert shortcuts.has_startup_shortcut()
    assert shortcuts.set_startup_shortcut(False)
    assert not shortcuts.has_startup_shortcut()
