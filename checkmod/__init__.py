"""CheckMod - Moderation Checklist & AHT companion.

A zero-dependency, portable, always-on-top desktop checklist designed for
Trust & Safety moderation workflows.

Design constraints that drive this whole package:

* **No installation, no admin rights.** Pure standard library (Tkinter only)
  so the app can be shipped as a single portable executable that runs from a
  USB stick, Desktop or network share without touching the registry, the
  Program Files directory or requiring elevation.
* **Privacy first.** The app performs zero network I/O. Everything it knows
  lives in a couple of plain-text files the user can read, move or delete.
  See :mod:`checkmod.paths` and ``docs/PRIVACY.md``.
* **Two audiences.** ``User Mode`` is a deliberately tiny surface: pick a case
  type, run the timer, tick four adherence checks. ``Dev Mode`` exposes the
  full configuration surface for power users and team leads.
"""

__all__ = ["__version__", "APP_NAME", "APP_TAGLINE"]

#: Semantic version, surfaced in the About panel and in built artifacts.
__version__ = "1.1.0"

#: Product name used for window titles and the data directory.
APP_NAME = "CheckMod"

#: One-line description shown in the About panel.
APP_TAGLINE = "Moderation checklist & AHT companion"
