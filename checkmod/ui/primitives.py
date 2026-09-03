"""Canvas-drawn building blocks: buttons, sliders, switches, rings, scrolling.

Every widget in this module follows the same contract:

``__init__(parent, theme, fonts, ...)``
    Build the widget in its initial state.
``restyle(theme, fonts)``
    Adopt a new colour set / font set and repaint.
``_redraw()``
    Render the current state; always safe to call again.

Widgets never read the global config directly - they are handed exactly what
they need. That keeps them reusable and makes the view code the single place
where application state and presentation meet.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import Callable, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------


def round_rect_points(x1: float, y1: float, x2: float, y2: float,
                      radius: float, steps: int = 5) -> List[float]:
    """Flat ``[x, y, x, y, ...]`` outline of a rounded rectangle.

    Corners are real quarter-circle arcs rather than Tk's ``smooth=True``
    spline approximation, which keeps small radii crisp at 100% zoom.
    """
    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)
    radius = max(0.0, min(radius, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    if radius <= 0.5:
        return [x1, y1, x2, y1, x2, y2, x1, y2]

    points: List[float] = []
    # (centre_x, centre_y, start_angle) for each corner, clockwise from top-left
    corners = (
        (x1 + radius, y1 + radius, 180.0),
        (x2 - radius, y1 + radius, 270.0),
        (x2 - radius, y2 - radius, 0.0),
        (x1 + radius, y2 - radius, 90.0),
    )
    for cx, cy, start in corners:
        for step in range(steps + 1):
            angle = math.radians(start + 90.0 * step / steps)
            points.extend((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def draw_round_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius,
                    fill: str = "", outline: str = "", width: float = 1.0,
                    tags: str = "") -> int:
    """Draw a rounded rectangle and return its canvas item id."""
    points = round_rect_points(x1, y1, x2, y2, radius)
    return canvas.create_polygon(
        points, fill=fill or "", outline=outline or "",
        width=width if outline else 0, tags=tags or (),
    )


def widget_size(widget, fallback_width: float, fallback_height: float):
    """``(width, height)`` for a widget, substituting sizes before layout.

    ``winfo_width()``/``winfo_height()`` return **1** until Tk has laid the
    widget out, and ``1`` is truthy - so the obvious ``winfo_width() or
    fallback`` keeps the 1 and paints a one-pixel widget. That is exactly how
    the title bar came to draw its contents at y=0. Every canvas widget here
    goes through this instead.
    """
    try:
        width = widget.winfo_width()
        height = widget.winfo_height()
    except tk.TclError:                     # pragma: no cover - destroyed
        return float(fallback_width), float(fallback_height)
    return (float(width) if width > 1 else float(fallback_width),
            float(height) if height > 1 else float(fallback_height))


def ellipsize(text: str, limit: int) -> str:
    """Trim ``text`` to ``limit`` characters with a trailing ellipsis."""
    text = text or ""
    return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"


# ----------------------------------------------------------------------
# Base class
# ----------------------------------------------------------------------
class CanvasWidget(tk.Canvas):
    """A borderless canvas that repaints itself whenever it is resized."""

    def __init__(self, parent, theme, fonts, height: int = 32,
                 width: int = 10, bg_token: str = "surface", **kwargs) -> None:
        self.theme = theme
        self.fonts = fonts
        self.bg_token = bg_token
        super().__init__(
            parent, height=height, width=width, highlightthickness=0,
            bd=0, bg=theme[bg_token], takefocus=0, **kwargs
        )
        self.bind("<Configure>", lambda _event: self._redraw())

    def restyle(self, theme, fonts) -> None:
        """Adopt a new theme/font set and repaint."""
        self.theme = theme
        self.fonts = fonts
        try:
            self.configure(bg=theme[self.bg_token])
        except tk.TclError:  # pragma: no cover - widget already destroyed
            return
        self._redraw()

    def _redraw(self) -> None:  # pragma: no cover - overridden by subclasses
        """Paint the current state. Subclasses must implement this."""


# ----------------------------------------------------------------------
# Button
# ----------------------------------------------------------------------
class Button(CanvasWidget):
    """A flat, rounded, hover-aware button.

    Variants
    --------
    ``primary``  filled with the accent colour - the main action
    ``soft``     tinted surface - secondary actions
    ``ghost``    transparent until hovered - tertiary / inline actions
    ``outline``  hairline border, transparent fill
    ``danger``   destructive actions
    ``icon``     square, glyph only
    """

    PAD_X = 14

    def __init__(self, parent, theme, fonts, text: str = "",
                 command: Optional[Callable[[], None]] = None,
                 variant: str = "soft", height: int = 34, radius: int = 10,
                 bg_token: str = "surface", font_key: str = "body",
                 accent: Optional[str] = None, width: int = 10,
                 tooltip: str = "") -> None:
        self.text = text
        self.command = command
        self.variant = variant
        self.radius = radius
        self.font_key = font_key
        self.accent_override = accent
        self.enabled = True
        self._hover = False
        self._pressed = False
        super().__init__(parent, theme, fonts, height=height, width=width, bg_token=bg_token)
        self.configure(cursor="hand2")
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        if tooltip:
            Tooltip(self, tooltip)

    # -- state ---------------------------------------------------------
    def set_text(self, text: str) -> None:
        if text != self.text:
            self.text = text
            self._redraw()

    def set_enabled(self, enabled: bool) -> None:
        if enabled != self.enabled:
            self.enabled = enabled
            self.configure(cursor="hand2" if enabled else "arrow")
            self._redraw()

    def set_variant(self, variant: str) -> None:
        if variant != self.variant:
            self.variant = variant
            self._redraw()

    # -- events --------------------------------------------------------
    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_press(self, _event=None) -> None:
        if not self.enabled:
            return
        self._pressed = True
        self._redraw()

    def _on_release(self, _event=None) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        if was_pressed and self.enabled and self.command:
            self.command()

    # -- painting ------------------------------------------------------
    def _palette(self) -> Tuple[str, str, str]:
        """Return ``(fill, foreground, outline)`` for the current state."""
        from .. import theme as theme_mod

        t = self.theme
        accent = self.accent_override or t["accent"]
        if not self.enabled:
            return t["surface_hi"], t["text_faint"], ""

        if self.variant == "primary":
            fill = theme_mod.lighten(accent, 0.10) if self._hover else accent
            if self._pressed:
                fill = theme_mod.darken(accent, 0.12)
            return fill, theme_mod.readable_on(fill), ""
        if self.variant == "danger":
            base = t["danger"]
            fill = theme_mod.lighten(base, 0.10) if self._hover else base
            if self._pressed:
                fill = theme_mod.darken(base, 0.12)
            return fill, theme_mod.readable_on(fill), ""
        if self.variant == "outline":
            fill = t["surface_hi"] if self._hover else ""
            return fill, t["text"], accent if self._hover else t["border"]
        if self.variant in ("ghost", "icon"):
            fill = t["surface_hi"] if (self._hover or self._pressed) else ""
            return fill, t["text"] if self._hover else t["text_dim"], ""
        # "soft"
        fill = t["surface_hi"] if self._hover else t["surface"]
        if self._pressed:
            fill = theme_mod.darken(t["surface_hi"], 0.06)
        return fill, t["text"], ""

    def _redraw(self) -> None:
        self.delete("all")
        width, height = widget_size(self, int(self["width"]), int(self["height"]))
        if width <= 1 or height <= 1:
            return
        fill, fg, outline = self._palette()
        offset = 1 if self._pressed and self.enabled else 0
        if fill or outline:
            draw_round_rect(self, 0.5, 0.5 + offset, width - 0.5, height - 0.5 + offset,
                            self.radius, fill=fill, outline=outline, width=1.0)
        if self.text:
            self.create_text(width / 2, height / 2 + offset, text=self.text,
                             fill=fg, font=self.fonts[self.font_key])

    def measure(self) -> int:
        """Ideal width in pixels for the current label."""
        try:
            return self.fonts.measure(self.text, self.font_key) + self.PAD_X * 2
        except Exception:  # pragma: no cover
            return len(self.text) * 8 + self.PAD_X * 2


# ----------------------------------------------------------------------
# Segmented control
# ----------------------------------------------------------------------
class Segmented(CanvasWidget):
    """Horizontal pill selector - used to choose the active case type.

    Each option carries its own accent colour so a moderator can recognise
    "Voice Chat" by colour alone from the corner of their eye.
    """

    def __init__(self, parent, theme, fonts, options: Sequence[dict],
                 on_select: Optional[Callable[[str], None]] = None,
                 height: int = 38, radius: int = 9, bg_token: str = "bg") -> None:
        self.options = list(options)
        self.on_select = on_select
        self.selected: Optional[str] = None
        self.radius = radius
        self._hover_index = -1
        super().__init__(parent, theme, fonts, height=height, bg_token=bg_token)
        self.configure(cursor="hand2")
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def set_options(self, options: Sequence[dict]) -> None:
        self.options = list(options)
        if self.selected not in [o["id"] for o in self.options]:
            self.selected = None
        self._redraw()

    def set_selected(self, option_id: Optional[str], notify: bool = False) -> None:
        self.selected = option_id
        self._redraw()
        if notify and self.on_select and option_id:
            self.on_select(option_id)

    # -- hit testing ---------------------------------------------------
    def _index_at(self, x: float) -> int:
        if not self.options:
            return -1
        # Guards the division, not the layout: an unmapped control cannot be
        # clicked, so there is no first-paint case to fall back for here.
        width = max(1, self.winfo_width())
        slot = width / float(len(self.options))
        index = int(x // slot)
        return index if 0 <= index < len(self.options) else -1

    def _on_motion(self, event) -> None:
        index = self._index_at(event.x)
        if index != self._hover_index:
            self._hover_index = index
            self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hover_index = -1
        self._redraw()

    def _on_click(self, event) -> None:
        index = self._index_at(event.x)
        if index >= 0:
            self.set_selected(self.options[index]["id"], notify=True)

    # -- painting ------------------------------------------------------
    def _redraw(self) -> None:
        from .. import theme as theme_mod

        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1 or not self.options:
            return
        gap = 4
        slot = width / float(len(self.options))
        for index, option in enumerate(self.options):
            x1 = index * slot + (gap / 2 if index else 0)
            x2 = (index + 1) * slot - (gap / 2 if index < len(self.options) - 1 else 0)
            color = option.get("color") or self.theme["accent"]
            is_selected = option["id"] == self.selected
            if is_selected:
                fill, fg, outline = color, theme_mod.readable_on(color), ""
            elif index == self._hover_index:
                fill = theme_mod.mix(color, self.theme["surface"], 0.80)
                fg, outline = self.theme["text"], ""
            else:
                fill, fg, outline = self.theme["surface"], self.theme["text_dim"], self.theme["border"]
            draw_round_rect(self, x1 + 0.5, 0.5, x2 - 0.5, height - 0.5, self.radius,
                            fill=fill, outline=outline, width=1.0)
            label = ellipsize(option.get("name", ""), max(6, int(slot / 8)))
            self.create_text((x1 + x2) / 2, height / 2, text=label, fill=fg,
                             font=self.fonts["small_bold" if is_selected else "small"])


# ----------------------------------------------------------------------
# Progress ring
# ----------------------------------------------------------------------
class Ring(CanvasWidget):
    """Circular AHT gauge: elapsed time inside, progress arc around it.

    The arc colour is driven by the session status (ok / warn / over) and the
    ring keeps filling past 100% as a second, darker sweep so "how far over"
    stays readable at a glance.
    """

    def __init__(self, parent, theme, fonts, size: int = 168,
                 thickness: int = 12, bg_token: str = "bg") -> None:
        self.size = size
        self.thickness = thickness
        self.progress = 0.0
        self.status = "ok"
        self.center_text = "00:00"
        self.top_text = ""
        self.bottom_text = ""
        self.accent: Optional[str] = None
        super().__init__(parent, theme, fonts, height=size, width=size, bg_token=bg_token)

    def update_values(self, progress: float, status: str, center: str,
                      top: str = "", bottom: str = "",
                      accent: Optional[str] = None) -> None:
        """Feed new values in and repaint."""
        self.progress = max(0.0, float(progress))
        self.status = status
        self.center_text = center
        self.top_text = top
        self.bottom_text = bottom
        self.accent = accent
        self._redraw()

    def _redraw(self) -> None:
        from .. import theme as theme_mod

        self.delete("all")
        width, height = widget_size(self, self.size, self.size)
        if width <= 1 or height <= 1:
            return
        size = min(width, height)
        pad = self.thickness / 2 + 3
        box = (width / 2 - size / 2 + pad, height / 2 - size / 2 + pad,
               width / 2 + size / 2 - pad, height / 2 + size / 2 - pad)

        color = self.accent or self.theme.status_color(self.status)
        # Track
        self.create_oval(*box, outline=self.theme["track"], width=self.thickness)

        first = min(1.0, self.progress)
        if first > 0.0005:
            self.create_arc(*box, start=90, extent=-359.999 * first, style=tk.ARC,
                            outline=color, width=self.thickness)
        if self.progress > 1.0:
            over = min(1.0, self.progress - 1.0)
            self.create_arc(*box, start=90, extent=-359.999 * over, style=tk.ARC,
                            outline=theme_mod.darken(self.theme["danger"], 0.28),
                            width=max(3, self.thickness - 5))

        cx, cy = width / 2, height / 2
        if self.top_text:
            self.create_text(cx, cy - size * 0.20, text=self.top_text,
                             fill=self.theme["text_faint"], font=self.fonts["tiny"])
        self.create_text(cx, cy, text=self.center_text, fill=self.theme["text"],
                         font=self.fonts["display"])
        if self.bottom_text:
            self.create_text(cx, cy + size * 0.20, text=self.bottom_text,
                             fill=color, font=self.fonts["small_bold"])


class Bar(CanvasWidget):
    """Slim horizontal alternative to :class:`Ring` for the compact layout."""

    def __init__(self, parent, theme, fonts, height: int = 8, bg_token: str = "bg") -> None:
        self.progress = 0.0
        self.status = "ok"
        self.accent: Optional[str] = None
        super().__init__(parent, theme, fonts, height=height, bg_token=bg_token)

    def update_values(self, progress: float, status: str,
                      accent: Optional[str] = None) -> None:
        self.progress = max(0.0, float(progress))
        self.status = status
        self.accent = accent
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return
        radius = height / 2
        draw_round_rect(self, 0, 0, width, height, radius, fill=self.theme["track"])
        filled = min(1.0, self.progress) * width
        if filled > 1:
            color = self.accent or self.theme.status_color(self.status)
            draw_round_rect(self, 0, 0, filled, height, radius, fill=color)


# ----------------------------------------------------------------------
# Slider
# ----------------------------------------------------------------------
class Slider(CanvasWidget):
    """Themed replacement for ``ttk.Scale`` (which cannot be flat-styled)."""

    def __init__(self, parent, theme, fonts, minimum: float = 0.0, maximum: float = 1.0,
                 value: float = 0.5, step: float = 0.01,
                 on_change: Optional[Callable[[float], None]] = None,
                 height: int = 26, bg_token: str = "surface") -> None:
        self.minimum = minimum
        self.maximum = maximum
        self.value = value
        self.step = step
        self.on_change = on_change
        self._dragging = False
        super().__init__(parent, theme, fonts, height=height, bg_token=bg_token)
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_value(self, value: float, notify: bool = False) -> None:
        value = max(self.minimum, min(self.maximum, value))
        if self.step:
            steps = round((value - self.minimum) / self.step)
            value = self.minimum + steps * self.step
            value = max(self.minimum, min(self.maximum, value))
        changed = abs(value - self.value) > 1e-9
        self.value = value
        self._redraw()
        if notify and changed and self.on_change:
            self.on_change(value)

    def _value_at(self, x: float) -> float:
        width = max(1, self.winfo_width() - 20)
        ratio = max(0.0, min(1.0, (x - 10) / float(width)))
        return self.minimum + ratio * (self.maximum - self.minimum)

    def _on_press(self, event) -> None:
        self._dragging = True
        self.set_value(self._value_at(event.x), notify=True)

    def _on_drag(self, event) -> None:
        if self._dragging:
            self.set_value(self._value_at(event.x), notify=True)

    def _on_release(self, _event=None) -> None:
        self._dragging = False

    def _redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return
        cy = height / 2
        track_h = 5
        span = self.maximum - self.minimum or 1
        ratio = (self.value - self.minimum) / float(span)
        x1, x2 = 10.0, width - 10.0
        draw_round_rect(self, x1, cy - track_h / 2, x2, cy + track_h / 2,
                        track_h / 2, fill=self.theme["track"])
        knob_x = x1 + ratio * (x2 - x1)
        if knob_x > x1 + 1:
            draw_round_rect(self, x1, cy - track_h / 2, knob_x, cy + track_h / 2,
                            track_h / 2, fill=self.theme["accent"])
        radius = 7 if not self._dragging else 8
        self.create_oval(knob_x - radius, cy - radius, knob_x + radius, cy + radius,
                         fill=self.theme["text"], outline=self.theme["bg"], width=2)


# ----------------------------------------------------------------------
# Switch
# ----------------------------------------------------------------------
class Switch(CanvasWidget):
    """Animated on/off pill toggle."""

    WIDTH = 42
    HEIGHT = 22

    def __init__(self, parent, theme, fonts, value: bool = False,
                 on_change: Optional[Callable[[bool], None]] = None,
                 bg_token: str = "surface") -> None:
        self.value = bool(value)
        self.on_change = on_change
        self._anim = 1.0 if value else 0.0
        self._job = None
        super().__init__(parent, theme, fonts, height=self.HEIGHT,
                         width=self.WIDTH, bg_token=bg_token)
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._on_click)

    def set_value(self, value: bool, notify: bool = False, animate: bool = True) -> None:
        value = bool(value)
        changed = value != self.value
        self.value = value
        if animate:
            self._animate()
        else:
            self._anim = 1.0 if value else 0.0
            self._redraw()
        if notify and changed and self.on_change:
            self.on_change(value)

    def _on_click(self, _event=None) -> None:
        self.set_value(not self.value, notify=True)

    def _animate(self) -> None:
        target = 1.0 if self.value else 0.0
        delta = target - self._anim
        if abs(delta) < 0.06:
            self._anim = target
            self._redraw()
            return
        self._anim += delta * 0.45
        self._redraw()
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:  # pragma: no cover
                pass
        self._job = self.after(16, self._animate)

    def _redraw(self) -> None:
        from .. import theme as theme_mod

        self.delete("all")
        width, height = widget_size(self, self.WIDTH, self.HEIGHT)
        if width <= 1 or height <= 1:
            return
        radius = height / 2
        off = self.theme["track"]
        on = self.theme["accent"]
        fill = theme_mod.mix(off, on, self._anim)
        draw_round_rect(self, 1, 1, width - 1, height - 1, radius - 1, fill=fill)
        knob_r = radius - 4
        x1 = 1 + radius
        x2 = width - 1 - radius
        cx = x1 + (x2 - x1) * self._anim
        self.create_oval(cx - knob_r, height / 2 - knob_r, cx + knob_r, height / 2 + knob_r,
                         fill="#FFFFFF" if self._anim > 0.5 else self.theme["text_dim"],
                         outline="")


# ----------------------------------------------------------------------
# Scrollable container
# ----------------------------------------------------------------------
class ScrollFrame(tk.Frame):
    """Vertically scrollable container with a slim, themed indicator.

    Content goes into :attr:`body`. The native scrollbar is replaced with a
    2px canvas indicator so Dev Mode keeps the same flat look as the rest of
    the app on every platform.
    """

    def __init__(self, parent, theme, fonts, bg_token: str = "bg") -> None:
        self.theme = theme
        self.fonts = fonts
        self.bg_token = bg_token
        super().__init__(parent, bg=theme[bg_token], highlightthickness=0, bd=0)

        self.canvas = tk.Canvas(self, bg=theme[bg_token], highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.indicator = tk.Canvas(self, width=4, bg=theme[bg_token],
                                   highlightthickness=0, bd=0)
        self.indicator.pack(side="right", fill="y")

        self.body = tk.Frame(self.canvas, bg=theme[bg_token])
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_wheel(self)
        # Global bindings outlive the widget unless they are released, and a
        # stale handler keeps firing against a destroyed canvas.
        self.bind("<Destroy>", self._release_wheel)

    # -- scrolling -----------------------------------------------------
    #: Wheel events differ per platform: a delta on Windows/macOS, buttons 4
    #: and 5 on X11.
    WHEEL_SEQUENCES = ("<MouseWheel>", "<Button-4>", "<Button-5>")

    def _bind_wheel(self, widget) -> None:
        """Bind wheel events on the whole subtree (Windows/macOS + X11).

        These have to be global: Tk delivers a wheel event to the widget under
        the pointer and then up its *bind tags*, not to ancestor widgets, so
        binding the container alone would miss every row inside it.
        :meth:`_release_wheel` gives them back on destroy.
        """
        for sequence in self.WHEEL_SEQUENCES:
            widget.bind_all(sequence, self._on_wheel, add="+")

    def _release_wheel(self, event=None) -> None:
        """Drop the global wheel bindings when this container goes away."""
        if event is not None and event.widget is not self:
            return          # a child was destroyed, not the container
        for sequence in self.WHEEL_SEQUENCES:
            try:
                self.unbind_all(sequence)
            except tk.TclError:
                pass

    def _on_wheel(self, event) -> None:
        try:
            if not self.winfo_exists() or not self.winfo_ismapped():
                return
        except tk.TclError:
            return          # destroyed between the event and this callback
        # Only scroll when the pointer is actually over this container.
        widget = self.winfo_containing(event.x_root, event.y_root)
        node = widget
        while node is not None:
            if node is self:
                break
            node = getattr(node, "master", None)
        if node is not self:
            return
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        try:
            self.canvas.yview_scroll(delta * 2, "units")
            self._draw_indicator()
        except tk.TclError:
            pass

    def _on_body_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._draw_indicator()

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self._draw_indicator()

    def _draw_indicator(self) -> None:
        self.indicator.delete("all")
        height = self.indicator.winfo_height()
        first, last = self.canvas.yview()
        if height <= 1 or (last - first) >= 0.999:
            return
        y1 = first * height
        y2 = max(y1 + 18, last * height)
        draw_round_rect(self.indicator, 0, y1, 4, y2, 2, fill=self.theme["border"])

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0.0)
        self._draw_indicator()

    def restyle(self, theme, fonts) -> None:
        self.theme = theme
        self.fonts = fonts
        for widget in (self, self.canvas, self.indicator, self.body):
            try:
                widget.configure(bg=theme[self.bg_token])
            except tk.TclError:  # pragma: no cover
                pass
        self._draw_indicator()


# ----------------------------------------------------------------------
# Tooltip
# ----------------------------------------------------------------------
class Tooltip:
    """Lightweight hover tooltip.

    Uses a borderless, top-most ``Toplevel`` so it is still visible above an
    always-on-top main window.
    """

    DELAY_MS = 550

    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._tip: Optional[tk.Toplevel] = None
        self._job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        self.text = text

    def _schedule(self, _event=None) -> None:
        self._cancel()
        if self.text:
            self._job = self.widget.after(self.DELAY_MS, self._show)

    def _cancel(self) -> None:
        if self._job:
            try:
                self.widget.after_cancel(self._job)
            except tk.TclError:  # pragma: no cover
                pass
            self._job = None

    def _show(self) -> None:
        if self._tip or not self.text:
            return
        try:
            theme = getattr(self.widget, "theme", None)
            bg = theme["surface_hi"] if theme else "#222222"
            fg = theme["text"] if theme else "#FFFFFF"
            border = theme["border"] if theme else "#444444"
            tip = tk.Toplevel(self.widget)
            tip.wm_overrideredirect(True)
            try:
                tip.wm_attributes("-topmost", True)
            except tk.TclError:
                pass
            frame = tk.Frame(tip, bg=border, bd=0)
            frame.pack()
            label = tk.Label(frame, text=self.text, bg=bg, fg=fg, bd=0,
                             padx=8, pady=4, justify="left", wraplength=240,
                             font=getattr(self.widget, "fonts", {}).get("tiny", ("", 8)))
            label.pack(padx=1, pady=1)
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            tip.wm_geometry(f"+{x}+{y}")
            self._tip = tip
        except tk.TclError:  # pragma: no cover
            self._tip = None

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:  # pragma: no cover
                pass
            self._tip = None
