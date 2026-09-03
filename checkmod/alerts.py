"""Audible alerts, generated from code rather than shipped as audio files.

``winsound.Beep`` produces one flat square-wave tone. It is easy to miss in a
room with a headset on, which defeats the point of an AHT alert. So the tones
here are synthesised into a small in-memory WAV and handed to
``winsound.PlaySound`` on a worker thread, which plays through the normal
audio device (and therefore the user's headset) at the system volume.

Two distinct patterns, so they can be told apart without looking:

``prealert``
    A rising two-note chime, repeated. "Wrap up" - not alarming.
``over``
    An alternating high/low warble, three cycles. Deliberately urgent; this
    is the sound of an AHT target already missed.

Everything is standard library (``wave``, ``struct``, ``math``), matching how
the icon is produced - the recipe is in the repository, so the alert can be
retuned without any audio tooling.
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


def wav_for(kind: str) -> bytes:
    """Return (and memoise) the WAV bytes for a named pattern."""
    if kind not in _cache:
        _cache[kind] = render({"prealert": PREALERT, "over": OVER,
                               "test": TEST}.get(kind, TEST))
    return _cache[kind]


def _play_windows(kind: str, repeats: int) -> bool:
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
            # Rendered here rather than by the caller: the first render of a
            # pattern costs ~15 ms, which would otherwise land on the UI
            # thread at the exact moment the alert is due.
            data = wav_for(kind)
            for _ in range(repeats):
                winsound.PlaySound(data, winsound.SND_MEMORY)
        except Exception:
            pass          # a missing or busy audio device is not fatal

    try:
        thread = threading.Thread(target=worker, name="checkmod-alert", daemon=True)
        thread.start()
        return True
    except Exception:
        return False


def play(kind: str = "test", root=None, repeats: int = 1) -> bool:
    """Play an alert.

    Returns ``True`` only when the real tones were played. A ``False`` return
    with a ``root`` still rings Tk's bell, which is all a platform without
    dependency-free audio can offer - audible, if plainer.
    """
    repeats = max(1, min(5, int(repeats)))
    if sys.platform.startswith("win") and _play_windows(kind, repeats):
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
