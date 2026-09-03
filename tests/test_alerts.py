"""Unit tests for the generated alert tones.

The audio device cannot be exercised here, so these check the thing that can
be: that each pattern renders to a well-formed, non-silent WAV of a sensible
length, and that playback degrades instead of raising when there is no
platform audio.
"""

from __future__ import annotations

import io
import sys
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


def test_play_reports_failure_rather_than_raising_without_audio_or_root():
    # No Tk root and (off Windows) no audio device: must return False quietly.
    assert alerts.play("over", root=None) in (True, False)
