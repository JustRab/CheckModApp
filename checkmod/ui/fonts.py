"""Font resolution and the app's small type scale.

Tkinter takes fonts as ``(family, size, style)`` tuples. Rather than sprinkle
those literals across the views, every widget asks for a *role*
(``"display"``, ``"body"``, ``"tiny"``...). Roles are resolved once here, so
changing the text scale in Dev Mode is a single object swap plus a repaint.
"""

from __future__ import annotations

import tkinter.font as tkfont
from typing import Dict, List

#: Families tried in order until one is installed. Segoe UI is the Windows
#: system font (the primary target), the rest cover macOS and Linux.
PREFERRED_FAMILIES: List[str] = [
    "Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue",
    "Ubuntu", "Noto Sans", "DejaVu Sans", "Arial",
]

PREFERRED_MONO: List[str] = [
    "Cascadia Mono", "Consolas", "SF Mono", "JetBrains Mono",
    "DejaVu Sans Mono", "Courier New",
]

#: Base point sizes per role, before the user's scale factor is applied.
SCALE: Dict[str, tuple] = {
    "display": (26, "bold"),
    "h1": (14, "bold"),
    "title": (11, "bold"),
    "body": (10, "normal"),
    "body_bold": (10, "bold"),
    "small": (9, "normal"),
    "small_bold": (9, "bold"),
    "tiny": (8, "normal"),
    "tiny_bold": (8, "bold"),
}


def available_families() -> List[str]:
    """Sorted list of font families Tk can actually render."""
    try:
        return sorted({name for name in tkfont.families()})
    except Exception:  # pragma: no cover - no Tk root yet
        return []


def resolve_family(preferred: str = "", candidates=None) -> str:
    """Pick ``preferred`` if installed, otherwise the best known fallback."""
    try:
        installed = {name.lower() for name in tkfont.families()}
    except Exception:  # pragma: no cover
        installed = set()
    if preferred and preferred.lower() in installed:
        return preferred
    for family in (candidates or PREFERRED_FAMILIES):
        if family.lower() in installed:
            return family
    return "TkDefaultFont"


class Fonts:
    """Immutable font set for one (family, scale) combination.

    Access roles by key: ``fonts["body"]`` returns a Tk font tuple.
    """

    def __init__(self, family: str = "", scale: float = 1.0) -> None:
        self.scale = max(0.7, min(1.6, float(scale or 1.0)))
        self.family = resolve_family(family)
        self.mono = resolve_family("", PREFERRED_MONO)
        self._cache: Dict[str, tuple] = {}
        for role, (size, style) in SCALE.items():
            points = max(7, int(round(size * self.scale)))
            self._cache[role] = (self.family, points, style)
        self._cache["mono"] = (self.mono, max(7, int(round(9 * self.scale))), "normal")
        # Glyph-only role for the title bar icons; kept slightly larger.
        self._cache["glyph"] = (self.family, max(9, int(round(12 * self.scale))), "normal")

    def __getitem__(self, role: str) -> tuple:
        return self._cache.get(role, self._cache["body"])

    def get(self, role: str, default=None):
        return self._cache.get(role, default or self._cache["body"])

    def height(self, role: str = "body") -> int:
        """Line height in pixels for ``role`` (used for manual layout)."""
        try:
            return tkfont.Font(font=self[role]).metrics("linespace")
        except Exception:  # pragma: no cover
            return int(self[role][1] * 1.6)

    def measure(self, text: str, role: str = "body") -> int:
        """Pixel width of ``text`` in ``role``."""
        try:
            return tkfont.Font(font=self[role]).measure(text)
        except Exception:  # pragma: no cover
            return len(text) * 7


def build_fonts(config) -> Fonts:
    """Construct a :class:`Fonts` from the current configuration."""
    return Fonts(config.get("font_family", ""), config.get("font_scale", 1.0))
