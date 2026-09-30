"""Unit tests for the generated alert tones.

The audio device cannot be exercised here, so these check the thing that can
be: that each pattern renders to a well-formed, non-silent WAV of a sensible
length, and that playback degrades instead of raising when there is no
platform audio.
"""

from __future__ import annotations

import io
import sys
import threading
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod import alerts


def read(kind: str):
    with wave.open(io.BytesIO(alerts.wav_for(kind))) as handle:
        frames = handle.readframes(handle.getnframes())
        return handle, frames


def test_every_pattern_renders_a_valid_wav():
    for kind in ("prealert", "over", "test"):
        with wave.open(io.BytesIO(alerts.wav_for(kind))) as handle:
            assert handle.getnchannels() == 1
            assert handle.getsampwidth() == 2
            assert handle.getframerate() == alerts.SAMPLE_RATE
            assert handle.getnframes() > 0


def test_the_alerts_are_long_enough_to_notice_but_not_annoying():
    lengths = {}
    for kind in ("prealert", "over"):
        with wave.open(io.BytesIO(alerts.wav_for(kind))) as handle:
            lengths[kind] = handle.getnframes() / handle.getframerate()
    # A single beep was the complaint; these are multi-tone patterns.
    assert 0.4 <= lengths["prealert"] <= 1.5
    assert 0.4 <= lengths["over"] <= 2.0


def test_the_two_alerts_are_actually_different():
    assert alerts.wav_for("prealert") != alerts.wav_for("over")


def test_the_audio_is_not_silent():
    _handle, frames = read("over")
    assert max(frames) > 0, "rendered a silent buffer"


def test_rendering_is_memoised():
    assert alerts.wav_for("over") is alerts.wav_for("over")


def test_a_silence_step_renders_as_silence():
    data = alerts.render([(0.0, 0.05)])
    with wave.open(io.BytesIO(data)) as handle:
        frames = handle.readframes(handle.getnframes())
    assert set(frames) == {0}


class FakeWinsound:
    """Stand-in for the Windows module, recording how it was called."""

    SND_MEMORY = 0x0004
    SND_ASYNC = 0x0001
    SND_FILENAME = 0x00020000

    def __init__(self) -> None:
        self.calls = []

    def PlaySound(self, data, flags):        # noqa: N802 - mirrors winsound
        # CPython rejects this combination outright rather than degrading:
        #   RuntimeError: Cannot play asynchronously from memory
        if flags & self.SND_ASYNC and flags & self.SND_MEMORY:
            raise RuntimeError("Cannot play asynchronously from memory")
        self.calls.append((data, flags))


def test_windows_playback_does_not_use_the_rejected_flag_combination(monkeypatch):
    """SND_MEMORY|SND_ASYNC raises, which the alert would swallow silently."""
    fake = FakeWinsound()
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(sys, "platform", "win32")

    assert alerts.play("over", root=None, repeats=2) is True
    for thread in threading.enumerate():
        if thread.name == "checkmod-alert":
            thread.join(timeout=5)

    assert fake.calls, "no sound was played"
    for _data, flags in fake.calls:
        assert not (flags & fake.SND_ASYNC), "uses the combination CPython rejects"
        assert flags & fake.SND_MEMORY
    assert len(fake.calls) == 2, "repeats did not play"
    assert fake.calls[0][0] == alerts.wav_for("over")


def test_windows_playback_survives_a_missing_audio_device(monkeypatch):
    class Broken(FakeWinsound):
        def PlaySound(self, data, flags):    # noqa: N802
            raise RuntimeError("no audio device")

    monkeypatch.setitem(sys.modules, "winsound", Broken())
    monkeypatch.setattr(sys, "platform", "win32")
    # The thread starts, so the call reports success; the failure inside it
    # must not propagate or crash the app.
    assert alerts.play("over", root=None) is True
    for thread in threading.enumerate():
        if thread.name == "checkmod-alert":
            thread.join(timeout=5)


def test_without_winsound_play_reports_that_no_real_audio_happened(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert alerts.play("over", root=None) is False


def test_the_bell_fallback_rings_once_per_repeat(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    class FakeRoot:
        def __init__(self):
            self.scheduled = 0

        def after(self, _delay, _callback):
            self.scheduled += 1

        def bell(self):
            pass

    root = FakeRoot()
    # False: the bell rang, but the real tones did not play.
    assert alerts.play("over", root=root, repeats=3) is False
    assert root.scheduled == 3


def test_repeats_are_clamped_to_a_sane_range(monkeypatch):
    fake = FakeWinsound()
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(sys, "platform", "win32")

    alerts.play("test", root=None, repeats=99)
    for thread in threading.enumerate():
        if thread.name == "checkmod-alert":
            thread.join(timeout=5)
    assert len(fake.calls) == 5


# ----------------------------------------------------------------------
# Styles and custom sounds (1.4.0)
# ----------------------------------------------------------------------
def test_every_style_renders_every_role():
    for style in alerts.STYLES:
        for role in alerts.ROLES:
            with wave.open(io.BytesIO(alerts.wav_for(role, style))) as handle:
                assert handle.getnframes() > 0, f"{style}/{role} is empty"


def test_the_calm_style_is_a_different_and_quieter_sound():
    default = alerts.wav_for("over", "default")
    calm = alerts.wav_for("over", "calm")
    assert default != calm
    assert max(calm) <= max(default), "the calm alert is not quieter"


def test_an_unknown_style_falls_back_to_default_rather_than_silence():
    assert alerts.wav_for("over", "klingon") == alerts.wav_for("over", "default")


def test_an_unknown_role_still_produces_audio():
    assert len(alerts.wav_for("no-such-role", "calm")) > 44   # > WAV header


def test_validate_custom_accepts_a_real_wav(tmp_path):
    path = tmp_path / "ok.wav"
    path.write_bytes(alerts.render([(440.0, 0.2)]))
    assert alerts.validate_custom(path) == (True, "")


def test_validate_custom_rejects_a_file_that_is_not_a_wav(tmp_path):
    """An MP3 would fail at the moment the alarm was needed, not before."""
    path = tmp_path / "song.mp3"
    path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00not really audio")
    assert alerts.validate_custom(path) == (False, "not_wav")


def test_validate_custom_reports_a_missing_file():
    ok, reason = alerts.validate_custom("/nope/does-not-exist.wav")
    assert ok is False and reason in ("unreadable", "not_wav")


def test_validate_custom_rejects_a_marathon_sound(tmp_path):
    path = tmp_path / "long.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * (8000 * 31))
    assert alerts.validate_custom(path) == (False, "too_long")


def test_a_custom_sound_is_played_from_the_file(monkeypatch, tmp_path):
    path = tmp_path / "mine.wav"
    path.write_bytes(alerts.render([(500.0, 0.1)]))
    fake = FakeWinsound()
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(sys, "platform", "win32")

    assert alerts.play("over", root=None, style="custom", custom_path=path) is True
    for thread in threading.enumerate():
        if thread.name == "checkmod-alert":
            thread.join(timeout=5)

    assert fake.calls
    payload, flags = fake.calls[0]
    assert payload == str(path)
    assert flags & fake.SND_FILENAME
    assert not (flags & fake.SND_MEMORY)


def test_the_custom_style_without_a_file_still_makes_a_sound(monkeypatch):
    """A misconfigured custom alert must never be a silent alarm."""
    fake = FakeWinsound()
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(sys, "platform", "win32")

    assert alerts.play("over", root=None, style="custom") is True
    for thread in threading.enumerate():
        if thread.name == "checkmod-alert":
            thread.join(timeout=5)
    assert fake.calls[0][0] == alerts.wav_for("over", "default")
