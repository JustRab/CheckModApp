"""Custom window chrome.

When ``frameless`` is enabled the OS title bar is removed and replaced by
this widget, which gives CheckMod a consistent look on every machine and lets
the window stay small and unobtrusive. It provides:

* a drag handle that moves the window (with optional edge snapping);
* a live status dot that mirrors the current case colour / AHT state;
* the mode switch (User <-> Dev), tutorial, always-on-top pin, compact
  toggle and close.

Only ASCII/Latin-1 glyphs are used for the icons ("?", "×", "—") because
emoji and symbol-block characters are missing from some corporate font
installs, and a missing glyph in a title bar looks broken.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .primitives import Button, Tooltip, draw_round_rect


class TitleBar(tk.Frame):
    """Draggable header with the app's window controls."""

    HEIGHT = 34

    def __init__(self, parent, app) -> None:
        self.app = app
        theme = app.theme
        super().__init__(parent, bg=theme["bg_alt"], height=self.HEIGHT)
        self.pack_propagate(False)

        self._drag_origin: Optional[tuple] = None
        self._status_color = theme["accent"]

        # --- drag handle (dot + title) --------------------------------
        self.handle = tk.Canvas(self, bg=theme["bg_alt"], highlightthickness=0,
                                bd=0, height=self.HEIGHT)
        self.handle.pack(side="left", fill="both", expand=True)
        for sequence, callback in (
            ("<Button-1>", self._on_press),
            ("<B1-Motion>", self._on_drag),
            ("<ButtonRelease-1>", self._on_release),
            ("<Double-Button-1>", self._on_double),
        ):
            self.handle.bind(sequence, callback)
            self.bind(sequence, callback)

        # --- window controls ------------------------------------------
        self.btn_close = self._icon_button("×", app.request_close, "tb.close", 18)
        self.btn_compact = self._icon_button("—", app.toggle_compact, "tb.compact", 15)
        self.btn_pin = self._icon_button("•", app.toggle_on_top, "tb.pin_on", 16)
        self.btn_mode = Button(
            self, theme, app.fonts, text="DEV", command=app.toggle_mode,
            variant="outline", height=22, radius=6, bg_token="bg_alt",
            font_key="tiny_bold", width=46, tooltip=app.t("mode.to_dev"),
        )
        self.btn_mode.pack(side="right", padx=(4, 6), pady=6)
        self.btn_help = self._icon_button("?", app.show_tutorial, "tb.help", 14)

        self.refresh()

    # ------------------------------------------------------------------
    def _icon_button(self, glyph: str, command: Callable[[], None],
                     tooltip_key: str, size: int) -> Button:
        """Create one square icon button, packed to the right edge."""
        button = Button(
            self, self.app.theme, self.app.fonts, text=glyph, command=command,
            variant="icon", height=24, radius=6, bg_token="bg_alt",
            font_key="glyph", width=26, tooltip=self.app.t(tooltip_key),
        )
        button.pack(side="right", padx=1, pady=5)
        return button

    # ------------------------------------------------------------------
    # Dragging
    # ------------------------------------------------------------------
    def _on_press(self, event) -> None:
        self._drag_origin = (event.x_root - self.app.root.winfo_x(),
                             event.y_root - self.app.root.winfo_y())

    def _on_drag(self, event) -> None:
        if not self._drag_origin:
            return
        x = event.x_root - self._drag_origin[0]
        y = event.y_root - self._drag_origin[1]
        self.app.move_window(x, y)

    def _on_release(self, _event=None) -> None:
        self._drag_origin = None
        self.app.snap_and_store()

    def _on_double(self, _event=None) -> None:
        self.app.toggle_compact()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def set_status_color(self, color: str) -> None:
        """Tint the status dot (case colour, or red when over the target)."""
        if color != self._status_color:
            self._status_color = color
            self._paint_handle()

    def _paint_handle(self) -> None:
        canvas = self.handle
        canvas.delete("all")
        height = canvas.winfo_height() or self.HEIGHT
        theme = self.app.theme
        cy = height / 2
        # Status dot with a soft halo.
        canvas.create_oval(10, cy - 7, 24, cy + 7, fill="", outline=self._status_color,
                           width=1)
        canvas.create_oval(14, cy - 3, 20, cy + 3, fill=self._status_color, outline="")
        canvas.create_text(32, cy, anchor="w", text="CheckMod", fill=theme["text"],
                           font=self.app.fonts["title"])
        # Mode chip so the current mode is obvious without opening anything.
        label = self.app.t("mode.dev" if self.app.config.get("mode") == "dev" else "mode.user")
        x = 32 + self.app.fonts.measure("CheckMod", "title") + 10
        width = self.app.fonts.measure(label, "tiny") + 14
        if x + width < (canvas.winfo_width() or 0):
            draw_round_rect(canvas, x, cy - 8, x + width, cy + 8, 8,
                            fill=theme["surface"], outline=theme["border"])
            canvas.create_text(x + width / 2, cy, text=label, fill=theme["text_faint"],
                               font=self.app.fonts["tiny"])

    def refresh(self) -> None:
        """Re-sync every control with the current configuration."""
        app = self.app
        is_dev = app.config.get("mode") == "dev"
        self.btn_mode.set_text("USER" if is_dev else "DEV")
        Tooltip(self.btn_mode, app.t("mode.to_user" if is_dev else "mode.to_dev"))

        on_top = bool(app.config.get("always_on_top"))
        self.btn_pin.set_text("●" if on_top else "○")
        self.btn_pin.accent_override = app.theme["accent"] if on_top else None
        Tooltip(self.btn_pin, app.t("tb.pin_on" if on_top else "tb.pin_off"))

        self.btn_compact.set_text("▫" if app.config.get("compact") else "—")
        self._paint_handle()

    def restyle(self, theme, fonts) -> None:
        """Repaint after a theme or font change."""
        self.configure(bg=theme["bg_alt"])
        self.handle.configure(bg=theme["bg_alt"])
        for button in (self.btn_close, self.btn_compact, self.btn_pin,
                       self.btn_mode, self.btn_help):
            button.restyle(theme, fonts)
        self.refresh()


class ResizeGrip(tk.Canvas):
    """Bottom-right corner grip used to resize a frameless window."""

    SIZE = 14

    def __init__(self, parent, app) -> None:
        self.app = app
        super().__init__(parent, width=self.SIZE, height=self.SIZE,
                         bg=app.theme["bg_alt"], highlightthickness=0, bd=0,
                         cursor="bottom_right_corner")
        self._origin = None
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda _e: self.app.snap_and_store())
        self.bind("<Configure>", lambda _e: self._paint())

    def _on_press(self, event) -> None:
        self._origin = (event.x_root, event.y_root,
                        self.app.root.winfo_width(), self.app.root.winfo_height())

    def _on_drag(self, event) -> None:
        if not self._origin:
            return
        x0, y0, w0, h0 = self._origin
        self.app.resize_window(w0 + (event.x_root - x0), h0 + (event.y_root - y0))

    def _paint(self) -> None:
        self.delete("all")
        color = self.app.theme["text_faint"]
        for offset in (3, 7, 11):
            self.create_line(self.SIZE - offset, self.SIZE - 2,
                             self.SIZE - 2, self.SIZE - offset, fill=color)

    def restyle(self, theme, _fonts) -> None:
        self.configure(bg=theme["bg_alt"])
        self._paint()
