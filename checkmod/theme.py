"""Colour system: presets, token resolution and small colour utilities.

Every widget reads colours through a *token* name (``"surface"``,
``"text_dim"``, ``"accent"``...) rather than a literal hex value. A theme is
therefore just a mapping of tokens to colours, which is what makes the app
re-skinnable at runtime and what lets Dev Mode override a single token
without breaking the rest of the interface.

Resolution order (last one wins)::

    preset palette  ->  accent override  ->  per-token overrides
"""

from __future__ import annotations

from typing import Dict, List, Tuple

#: Token names every palette must provide.
TOKENS = (
    "bg",            # window background
    "bg_alt",        # title bar / footer background
    "surface",       # cards and rows
    "surface_hi",    # hovered card
    "border",        # hairlines
    "text",          # primary text
    "text_dim",      # secondary text
    "text_faint",    # tertiary text, hints
    "accent",        # brand / primary action
    "accent_text",   # text drawn on top of accent
    "ok",            # within target
    "warn",          # approaching target
    "danger",        # over target / destructive action
    "track",         # progress track
)


def _palette(**kwargs: str) -> Dict[str, str]:
    """Small helper so preset definitions below stay readable."""
    return dict(kwargs)


#: Built-in themes. Dev Mode lists these and can override any token on top.
PRESETS: Dict[str, Dict[str, str]] = {
    "midnight": _palette(
        label="Midnight", dark="1",
        bg="#0E1219", bg_alt="#141A24", surface="#182030", surface_hi="#1F2939",
        border="#28324A", text="#EAF0FA", text_dim="#9AA9C4", text_faint="#67748E",
        accent="#5B8CFF", accent_text="#08101F",
        ok="#3DD68C", warn="#F5B942", danger="#FF6B6B", track="#232D42",
    ),
    "graphite": _palette(
        label="Graphite", dark="1",
        bg="#121212", bg_alt="#181818", surface="#1E1E1E", surface_hi="#272727",
        border="#333333", text="#F2F2F2", text_dim="#A8A8A8", text_faint="#767676",
        accent="#E4E4E4", accent_text="#141414",
        ok="#69D18B", warn="#E5B567", danger="#EB6F6F", track="#2A2A2A",
    ),
    "nord": _palette(
        label="Nord", dark="1",
        bg="#2E3440", bg_alt="#333A47", surface="#3B4252", surface_hi="#434C5E",
        border="#4C566A", text="#ECEFF4", text_dim="#B8C1D1", text_faint="#8B96A8",
        accent="#88C0D0", accent_text="#1F2530",
        ok="#A3BE8C", warn="#EBCB8B", danger="#BF616A", track="#434C5E",
    ),
    "aurora": _palette(
        label="Aurora", dark="1",
        bg="#14101F", bg_alt="#1A1430", surface="#221A3A", surface_hi="#2C2249",
        border="#3A2E5E", text="#F2ECFF", text_dim="#B3A6D6", text_faint="#7E72A0",
        accent="#B478FF", accent_text="#160F22",
        ok="#4FE0B0", warn="#FFC46B", danger="#FF7597", track="#2C2249",
    ),
    "forest": _palette(
        label="Forest", dark="1",
        bg="#0F1712", bg_alt="#14201A", surface="#1A2A21", surface_hi="#22362B",
        border="#2C4436", text="#E9F5EE", text_dim="#9CBCA9", text_faint="#6C8A79",
        accent="#4ED17F", accent_text="#08150E",
        ok="#4ED17F", warn="#E8C15C", danger="#F0736B", track="#22362B",
    ),
    "daylight": _palette(
        label="Daylight", dark="0",
        bg="#F4F6FB", bg_alt="#EAEEF7", surface="#FFFFFF", surface_hi="#F0F4FC",
        border="#D9E0EE", text="#141A26", text_dim="#5A6679", text_faint="#8B95A8",
        accent="#2F6BFF", accent_text="#FFFFFF",
        ok="#12A05C", warn="#C9820A", danger="#D8453F", track="#E2E8F4",
    ),
    "paper": _palette(
        label="Paper", dark="0",
        bg="#F6F2E9", bg_alt="#EFE9DC", surface="#FFFCF6", surface_hi="#F4EEE2",
        border="#E0D7C6", text="#24201A", text_dim="#645C4E", text_faint="#938979",
        accent="#B4601F", accent_text="#FFFFFF",
        ok="#3F8A3F", warn="#B4841F", danger="#B33A32", track="#E7DFD0",
    ),
    "contrast": _palette(
        label="High contrast", dark="1",
        bg="#000000", bg_alt="#000000", surface="#0A0A0A", surface_hi="#1A1A1A",
        border="#FFFFFF", text="#FFFFFF", text_dim="#E0E0E0", text_faint="#BFBFBF",
        accent="#FFD400", accent_text="#000000",
        ok="#00E676", warn="#FFD400", danger="#FF3B30", track="#2B2B2B",
    ),
}

#: Accent swatches offered as one-click choices in Dev Mode.
ACCENT_SWATCHES: List[str] = [
    "#5B8CFF", "#7C5CFF", "#B478FF", "#FF6FA5", "#FF7A59",
    "#F2A03D", "#3DD68C", "#2BB3A3", "#4CC2FF", "#E4E4E4",
]


# ----------------------------------------------------------------------
# Colour maths
# ----------------------------------------------------------------------
def hex_to_rgb(color: str) -> Tuple[int, int, int]:
    """Convert ``"#rrggbb"`` (or ``"#rgb"``) to an ``(r, g, b)`` tuple."""
    value = (color or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return (0, 0, 0)
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return (0, 0, 0)


def rgb_to_hex(rgb) -> str:
    """Convert an ``(r, g, b)`` tuple back to ``"#rrggbb"``."""
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def mix(color_a: str, color_b: str, t: float) -> str:
    """Linear blend: ``t=0`` returns ``color_a``, ``t=1`` returns ``color_b``."""
    t = max(0.0, min(1.0, t))
    ra, ga, ba = hex_to_rgb(color_a)
    rb, gb, bb = hex_to_rgb(color_b)
    return rgb_to_hex((ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t))


def lighten(color: str, amount: float = 0.12) -> str:
    """Blend ``color`` towards white."""
    return mix(color, "#ffffff", amount)


def darken(color: str, amount: float = 0.12) -> str:
    """Blend ``color`` towards black."""
    return mix(color, "#000000", amount)


def luminance(color: str) -> float:
    """Relative luminance (WCAG) used to pick readable foregrounds."""
    def channel(value: int) -> float:
        srgb = value / 255.0
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two colours (1.0 - 21.0)."""
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def readable_on(background: str, light: str = "#FFFFFF", dark: str = "#101418") -> str:
    """Pick whichever of ``light``/``dark`` reads better on ``background``."""
    return dark if contrast_ratio(dark, background) >= contrast_ratio(light, background) else light


def is_valid_hex(color: str) -> bool:
    """Return ``True`` for ``"#rgb"`` / ``"#rrggbb"`` strings."""
    value = (color or "").strip()
    if not value.startswith("#"):
        return False
    body = value[1:]
    return len(body) in (3, 6) and all(ch in "0123456789abcdefABCDEF" for ch in body)


class Theme:
    """Resolved, read-only colour set handed to every widget.

    Instances are cheap and immutable in practice: when settings change the
    app builds a brand new :class:`Theme` and repaints, which avoids any
    partially-restyled state.
    """

    def __init__(self, preset: str = "midnight", accent: str = "",
                 overrides=None) -> None:
        base = PRESETS.get(preset) or PRESETS["midnight"]
        self.name = preset if preset in PRESETS else "midnight"
        self.label = base.get("label", self.name.title())
        self.is_dark = base.get("dark", "1") == "1"

        colors = {token: base[token] for token in TOKENS}

        if is_valid_hex(accent):
            colors["accent"] = accent
            colors["accent_text"] = readable_on(accent)

        for token, value in (overrides or {}).items():
            if token in TOKENS and is_valid_hex(value):
                colors[token] = value

        self.colors = colors

        # Derived colours used often enough to be worth precomputing.
        self.accent_soft = mix(colors["accent"], colors["surface"], 0.72)
        self.accent_hover = lighten(colors["accent"], 0.12 if self.is_dark else 0.0) \
            if self.is_dark else darken(colors["accent"], 0.08)
        self.shadow = darken(colors["bg"], 0.5) if self.is_dark else "#C9D2E4"

    def __getitem__(self, token: str) -> str:
        """``theme["accent"]`` - the common access pattern in widget code."""
        return self.colors.get(token, "#FF00FF")

    def get(self, token: str, default: str = "#FF00FF") -> str:
        return self.colors.get(token, default)

    def status_color(self, status: str) -> str:
        """Map a timer status (``ok``/``warn``/``over``) to a colour."""
        return {"ok": self["ok"], "warn": self["warn"], "over": self["danger"]}.get(
            status, self["accent"])


def build_theme(config) -> Theme:
    """Construct a :class:`Theme` from a :class:`checkmod.config.Config`."""
    return Theme(
        preset=config.get("theme", "midnight"),
        accent=config.get("accent", ""),
        overrides=config.get("palette_overrides", {}) or {},
    )
