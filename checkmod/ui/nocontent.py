"""The No Content strip: a countdown that has to be answered.

Some packages arrive with nothing to look at. The rule is to wait a fixed
span - three minutes by default - and then say explicitly whether content
turned up. This panel is that rule on screen, and it is visible at all times
so the wait is one click away rather than something to remember.

Two states share one strip:

**Idle** - a single "No Content" button.

**Waiting** - the countdown, a progress bar that turns amber at the calm
nudge and red when the span runs out, and the two answers the moderator
owes: *Content* (the wait is over, back to normal) and *No Content* (still
nothing; the countdown restarts and the cycle count goes up).

The state machine and both alerts live in
:class:`~checkmod.session.NoContentCycle`; this file only paints it. The
compact layout uses the same class with shorter labels and no bar, because
the strip still has to fit a corner of the screen.
"""

from __future__ import annotations

import tkinter as tk

from ..session import format_duration
from .primitives import Bar, Button


class NoContentPanel(tk.Frame):
    """Always-visible No Content control, in either layout."""

    def __init__(self, parent, app, compact: bool = False) -> None:
        self.app = app
        self.compact = compact
        super().__init__(parent, bg=app.theme["bg"], highlightthickness=0, bd=0)
        self.build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def build(self) -> None:
        """(Re)create the strip. Called on build and on any restyle."""
        for child in self.winfo_children():
            child.destroy()
        app = self.app
        theme, fonts = app.theme, app.fonts
        radius = 6 if self.compact else max(4, int(app.config.get("corner_radius", 12)) - 4)
        height = 24 if self.compact else 30

        self.row = tk.Frame(self, bg=theme["bg"])
        self.row.pack(fill="x")

        # Idle: one button, the width of the strip.
        self.btn_start = Button(
            self.row, theme, fonts,
            text=app.t("nc.short") if self.compact else app.t("nc.start"),
            command=app.start_no_content, variant="outline", height=height,
            radius=radius, bg_token="bg",
            font_key="tiny_bold" if self.compact else "small",
            width=52 if self.compact else 10,
            tooltip=app.t("nc.tip"),
        )

        # Waiting: countdown plus the two answers.
        self.countdown = tk.Label(self.row, text="", bg=theme["bg"], fg=theme["text"],
                                  font=fonts["body_bold" if self.compact else "h2"],
                                  anchor="w")
        self.btn_content = Button(
            self.row, theme, fonts,
            text=app.t("nc.content"), command=app.end_no_content,
            variant="primary", height=height, radius=radius, bg_token="bg",
            font_key="tiny_bold" if self.compact else "small",
            width=64 if self.compact else 96,
            tooltip=app.t("nc.content_tip"),
        )
        self.btn_again = Button(
            self.row, theme, fonts,
            text=app.t("nc.short") if self.compact else app.t("nc.again"),
            command=app.start_no_content, variant="soft", height=height,
            radius=radius, bg_token="bg",
            font_key="tiny_bold" if self.compact else "small",
            width=52 if self.compact else 96,
            tooltip=app.t("nc.again_tip"),
        )

        # The bar is full-layout only: the compact strip has no room, and the
        # countdown text already changes colour there.
        self.bar = None if self.compact else Bar(self, theme, fonts, height=5, bg_token="bg")
        self.note = None
        if not self.compact:
            self.note = tk.Label(self, text="", bg=theme["bg"], fg=theme["text_faint"],
                                 font=fonts["tiny"], anchor="w")

        self._packed = None        # force the first sync to lay the row out
        self.sync()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def sync(self) -> None:
        """Show the controls for the current state, then repaint."""
        active = bool(self.app.no_content.active)
        if self._packed != active:
            # Re-packing on every tick would fight the geometry manager, so
            # the layout is only rebuilt when the state actually flips.
            for widget in (self.btn_start, self.countdown, self.btn_content,
                           self.btn_again):
                widget.pack_forget()
            if self.bar is not None:
                self.bar.pack_forget()
            if self.note is not None:
                self.note.pack_forget()

            if active:
                self.countdown.pack(side="left")
                self.btn_again.pack(side="right")
                self.btn_content.pack(side="right", padx=(0, 6))
                if self.bar is not None:
                    self.bar.pack(fill="x", pady=(6, 0))
                if self.note is not None:
                    self.note.pack(fill="x", pady=(4, 0))
            else:
                self.btn_start.pack(fill="x" if not self.compact else "none",
                                    side="left" if self.compact else "top",
                                    expand=not self.compact)
            self._packed = active
        self.tick()

    def tick(self) -> None:
        """Advance the countdown display (~5x/second, like the case timer)."""
        cycle = self.app.no_content
        if not cycle.active:
            return
        app = self.app
        theme = app.theme
        status = cycle.status()
        remaining = cycle.remaining
        text = (f"+{format_duration(-remaining)}" if remaining < 0
                else format_duration(remaining))
        color = theme["text"] if status == "ok" else theme.status_color(status)
        self.countdown.configure(text=f"{app.t('nc.label')}  {text}", fg=color)
        if self.bar is not None:
            self.bar.update_values(cycle.progress, status)
        if self.note is not None:
            if cycle.cycles > 1:
                note = app.t("nc.cycles", n=cycle.cycles)
            else:
                note = app.t("nc.answer")
            self.note.configure(text=note)

    # ------------------------------------------------------------------
    def restyle(self, theme, fonts) -> None:
        """Theme/font change: rebuild, like the rest of the views."""
        self.configure(bg=theme["bg"])
        self.build()
