"""Unit tests for storage-location resolution.

These encode the "no installation, no admin rights" promise: the app must
only ever write to a folder the user already owns, and it must degrade to the
per-user profile when the folder next to the executable is read-only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod import paths


def test_env_override_wins_over_every_other_rule(tmp_path, monkeypatch):
    target = tmp_path / "custom"
    monkeypatch.setenv(paths.ENV_OVERRIDE, str(target))
    assert paths.data_dir() == target
    assert target.is_dir()


def test_settings_and_history_live_inside_the_data_folder(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.ENV_OVERRIDE, str(tmp_path))
    assert paths.settings_file().parent == tmp_path
    assert paths.history_file().parent == tmp_path
    assert paths.history_file().name.endswith(".jsonl")


def test_portable_mode_is_off_until_the_marker_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path)
    assert paths.is_portable() is False

    assert paths.enable_portable(True)
    assert paths.is_portable() is True
    assert (tmp_path / paths.PORTABLE_MARKER).exists()

    assert paths.enable_portable(False)
    assert paths.is_portable() is False


def test_portable_mode_stores_data_next_to_the_application(tmp_path, monkeypatch):
    monkeypatch.delenv(paths.ENV_OVERRIDE, raising=False)
    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path)
    paths.enable_portable(True)
    assert paths.data_dir() == tmp_path / paths.PORTABLE_DIR_NAME


def test_a_read_only_application_folder_falls_back_to_the_user_profile(tmp_path, monkeypatch):
    """Copied into Program Files? Still runs, still needs no admin rights."""
    monkeypatch.delenv(paths.ENV_OVERRIDE, raising=False)
    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "is_portable", lambda: True)
    monkeypatch.setattr(paths, "_roaming_dir", lambda: tmp_path / "roaming")

    def refuse(path):
        if paths.PORTABLE_DIR_NAME in str(path):
            raise OSError("read-only location")
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(paths, "_ensure", refuse)
    assert paths.data_dir() == tmp_path / "roaming"


def test_disabling_portable_mode_twice_is_harmless(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path)
    assert paths.enable_portable(False)
    assert paths.enable_portable(False)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX path layout")
def test_the_roaming_folder_is_inside_the_user_home(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert str(Path.home()) in str(paths._roaming_dir())
