"""Audible alerts, generated from code rather than shipped as audio files.

``winsound.Beep`` produces one flat square-wave tone. It is easy to miss in a
room with a headset on, which defeats the point of an AHT alert. So the tones
here are synthesised into a small in-memory WAV and handed to
``winsound.PlaySound`` on a worker thread, which plays through the normal
audio device (and therefore the user's headset) at the system volume.

Each alert has a *role*, and the user picks the *style* that fills it:

======== ============================== ==============================
role     default style                  calm style
======== ============================== ==============================
prealert rising two-note chime, twice   one soft low chime
over     urgent high/low warble x3      two gentle mid tones
nudge    soft low chime (No Content)    the same, quieter
======== ============================== ==============================

The third style, ``custom``, plays a WAV the user supplied for every role.
Only WAV is supported because ``winsound`` plays nothing else without a
dependency - :func:`validate_custom` says so plainly rather than failing at
the moment the alarm was needed.

Everything generated is standard library (``wave``, ``struct``, ``math``),
matching how the icon is produced - the recipe is in the repository, so the
alerts can be retuned without any audio tooling.
"""

from __future__ import annotations

import io
import math
import struct
import sys
import threading
import wave
from typing import Dict, Sequence, Tuple

#: Sample rate. 22 050 Hz is ample for tones and keeps the buffer small.
SAMPLE_RATE = 22050

#: Peak amplitude as a fraction of full scale. Loud enough to cut through a
#: headset without clipping or sounding harsh.
AMPLITUDE = 0.55

#: (frequency_hz, duration_s) pairs; a frequency of 0 is silence.
Pattern = Sequence[Tuple[float, float]]

#: Rising two-note chime, twice: "you have a few seconds left".
PREALERT: Pattern = [
    (880.0, 0.10), (0.0, 0.04), (1174.0, 0.14), (0.0, 0.10),
    (880.0, 0.10), (0.0, 0.04), (1174.0, 0.16),
]

#: Urgent high/low warble, three cycles: "you are over target".
OVER: Pattern = [
    (988.0, 0.13), (659.0, 0.13),
    (988.0, 0.13), (659.0, 0.13),
    (988.0, 0.13), (659.0, 0.20),
]

#: Short confirmation used by the "test sound" buttons in Dev Mode.
TEST: Pattern = [(660.0, 0.09), (0.0, 0.03), (990.0, 0.12)]

#: A single soft chime. Used for the No Content nudge, and as the whole calm
#: style: present enough to notice, not enough to startle.
NUDGE: Pattern = [(587.0, 0.16), (0.0, 0.05), (440.0, 0.22)]

#: The calm style's "over target": two unhurried mid tones instead of a
#: warble. Still clearly an alert, just not an alarm.
CALM_OVER: Pattern = [
    (659.0, 0.18), (0.0, 0.08), (523.0, 0.26), (0.0, 0.12),
    (659.0, 0.18), (0.0, 0.08), (523.0, 0.30),
]

#: Amplitude multiplier per style - the calm set is quieter as well as softer.
STYLE_GAIN = {"default": 1.0, "calm": 0.62, "custom": 1.0}

#: role -> pattern, per style.
STYLES: Dict[str, Dict[str, Pattern]] = {
    "default": {"prealert": PREALERT, "over": OVER, "nudge": NUDGE, "test": TEST},
    "calm": {"prealert": NUDGE, "over": CALM_OVER, "nudge": NUDGE, "test": NUDGE},
}

#: Roles the app can ask for.
ROLES = ("prealert", "over", "nudge", "test")

_cache: Dict[str, bytes] = {}


def _envelope(index: int, total: int, fade: int) -> float:
    """Short fade in/out so tones do not click at the edges."""
    if fade <= 0:
        return 1.0
    if index < fade:
        return index / float(fade)
    if index > total - fade:
        return max(0.0, (total - index) / float(fade))
    return 1.0


def render(pattern: Pattern, amplitude: float = AMPLITUDE) -> bytes:
    """Render ``pattern`` to 16-bit mono WAV bytes.

    A little second harmonic is mixed in: a pure sine is easy to overlook,
    while the harmonic gives the tone an edge that carries.
    """
    frames = bytearray()
    for frequency, duration in pattern:
        count = max(1, int(SAMPLE_RATE * duration))
        fade = min(int(SAMPLE_RATE * 0.006), count // 2)
        for index in range(count):
            if frequency <= 0:
                frames += struct.pack("<h", 0)
                continue
            t = index / float(SAMPLE_RATE)
            value = math.sin(2.0 * math.pi * frequency * t)
            value += 0.30 * math.sin(4.0 * math.pi * frequency * t)
            value *= amplitude * _envelope(index, count, fade) / 1.30
            frames += struct.pack("<h", int(max(-1.0, min(1.0, value)) * 32767))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


def wav_for(kind: str, style: str = "default") -> bytes:
    """Return (and memoise) the WAV bytes for ``kind`` in ``style``."""
    style = style if style in STYLES else "default"
    key = f"{style}:{kind}"
    if key not in _cache:
        patterns = STYLES[style]
        pattern = patterns.get(kind, patterns["test"])
        _cache[key] = render(pattern, AMPLITUDE * STYLE_GAIN.get(style, 1.0))
    return _cache[key]


def validate_custom(path) -> Tuple[bool, str]:
    """Check a user-supplied sound file. Returns ``(ok, reason)``.

    ``winsound`` plays WAV and nothing else without a third-party decoder, so
    an MP3 is rejected here - with an explanation - rather than silently
    failing the first time an alarm was actually needed.
    """
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate() or 1
    except wave.Error:
        return False, "not_wav"
    except (OSError, EOFError):
        return False, "unreadable"
    if frames <= 0:
        return False, "empty"
    if frames / float(rate) > 30.0:
        return False, "too_long"
    return True, ""


def _play_windows(kind: str, repeats: int, style: str = "default",
                  custom_path=None) -> bool:
    """Play a pattern on Windows, off the UI thread. ``True`` if it started.

    ``winsound`` refuses ``SND_MEMORY | SND_ASYNC`` outright - CPython raises
    ``RuntimeError("Cannot play asynchronously from memory")`` rather than
    degrading - so playing a generated buffer without blocking means calling
    the *synchronous* form on a worker thread. ``PlaySound`` releases the GIL,
    so the interface stays responsive and the repeats space themselves
    naturally, each starting as the previous one finishes.
    """
    try:
        import winsound
    except Exception:
        return False

    def worker() -> None:
        try:
            if style == "custom" and custom_path:
                # A file on disk, so SND_FILENAME rather than SND_MEMORY.
                flags = winsound.SND_FILENAME
                payload = str(custom_path)
            else:
                # Rendered here rather than by the caller: the first render of
                # a pattern costs ~15 ms, which would otherwise land on the UI
                # thread at the exact moment the alert is due.
                flags = winsound.SND_MEMORY
                payload = wav_for(kind, style)
            for _ in range(repeats):
                winsound.PlaySound(payload, flags)
        except Exception:
            pass          # a missing or busy audio device is not fatal

    try:
        thread = threading.Thread(target=worker, name="checkmod-alert", daemon=True)
        thread.start()
        return True
    except Exception:
        return False


def play(kind: str = "test", root=None, repeats: int = 1,
         style: str = "default", custom_path=None) -> bool:
    """Play an alert in the requested style.

    Returns ``True`` only when real audio was played. A ``False`` return with
    a ``root`` still rings Tk's bell, which is all a platform without
    dependency-free audio can offer - audible, if plainer.
    """
    repeats = max(1, min(5, int(repeats)))
    if style == "custom" and not custom_path:
        style = "default"       # nothing uploaded yet: do not fall silent
    if sys.platform.startswith("win") and _play_windows(
            kind, repeats, style, custom_path):
        return True

    if root is not None:
        try:
            for step in range(repeats):
                root.after(step * 220, root.bell)
        except Exception:
            pass
    return False


def available() -> bool:
    """Whether real audio (rather than the terminal bell) is available."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import winsound

        return hasattr(winsound, "PlaySound")
    except Exception:
        return False
